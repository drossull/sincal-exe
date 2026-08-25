import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone

from sincal.cad.engine import (
    discover_cad_engines,
    engine_state_path,
    legacy_wrapper_path,
    load_engine_state,
)
from sincal.resources import active_resource_paths, state_path
from sincal.runtime import (
    RUTA_DATOS_USUARIO,
    RUTA_INSTALACION,
    RUTA_LOGS,
    VERSION_ACTUAL,
    asegurar_directorios,
    ruta_recurso,
    ruta_recurso_instalado,
)


DIAGNOSTIC_SCHEMA = 1
INCIDENT_LIMIT_BYTES = 1024 * 1024
_incident_lock = threading.Lock()
CRITICAL_RESOURCES = (
    "lisps/SINCAL.lsp",
    "startup/SINCAL_STARTUP.lsp",
    "scripts/SINCAL_ENGINE.ps1",
    "scripts/AUDIT.ps1",
    "scripts/AUDIT.scr",
    "plotstyles/SINCAL_A1 (2025).ctb",
    "masters/FORMATOS ANOTATIVOS ACAD_2025.dwg",
    "mapas/mapas_calibrados.json",
    "tutoriales.json",
)


def diagnostics_directory() -> str:
    path = os.path.join(RUTA_DATOS_USUARIO, "diagnostics")
    os.makedirs(path, exist_ok=True)
    return path


def incidents_path() -> str:
    return os.path.join(diagnostics_directory(), "incidents.jsonl")


def _replacement_pairs(extra_paths=()) -> list[tuple[str, str]]:
    pairs = []
    values = (
        (os.getenv("USERPROFILE"), "%USERPROFILE%"),
        (os.getenv("LOCALAPPDATA"), "%LOCALAPPDATA%"),
        (os.getenv("APPDATA"), "%APPDATA%"),
        (os.getenv("USERNAME"), "<USUARIO>"),
        (os.getenv("COMPUTERNAME"), "<EQUIPO>"),
    )
    for source, replacement in values:
        if source and len(source) >= 3:
            pairs.append((source, replacement))
    for path in extra_paths:
        if path:
            pairs.append((os.path.abspath(path), "<PROYECTO>"))
    return sorted(pairs, key=lambda item: len(item[0]), reverse=True)


def redact_text(value, extra_paths=(), redact_filenames=True) -> str:
    text = str(value or "")
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "<EMAIL>", text, flags=re.IGNORECASE)
    for source, replacement in _replacement_pairs(extra_paths):
        variants = {source, source.replace("\\", "/"), source.replace("/", "\\")}
        for variant in variants:
            text = re.sub(re.escape(variant), replacement, text, flags=re.IGNORECASE)
    if redact_filenames:
        extensions = r"dwg|dxf|kmz|kml|pdf"
        text = re.sub(
            rf"(?i)(?<=en: )[^\r\n]+?\.({extensions})\b",
            lambda match: f"<ARCHIVO>.{match.group(1).lower()}",
            text,
        )
        text = re.sub(
            rf"(?i)\b[\w][\w().-]*\.({extensions})\b",
            lambda match: f"<ARCHIVO>.{match.group(1).lower()}",
            text,
        )
    return text


def _redact_value(value, extra_paths=(), redact_filenames=True):
    if isinstance(value, dict):
        return {
            str(key): _redact_value(item, extra_paths, redact_filenames)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_value(item, extra_paths, redact_filenames) for item in value]
    if isinstance(value, str):
        return redact_text(value, extra_paths, redact_filenames)
    return value


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _run_probe(command: list[str], timeout=8) -> dict:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "output": output[-4000:],
        }
    except Exception as error:
        return {
            "ok": False,
            "returncode": None,
            "seconds": round(time.monotonic() - started, 3),
            "output": f"{type(error).__name__}: {error}",
        }


def _write_probe(directory: str) -> dict:
    if not directory or not os.path.isdir(directory):
        return {"ok": False, "detail": "Directorio no disponible."}
    try:
        fd, path = tempfile.mkstemp(prefix=".sincal-write-test-", suffix=".tmp", dir=directory)
        with os.fdopen(fd, "wb") as target:
            target.write(b"SINCAL")
        os.remove(path)
        return {"ok": True, "detail": "Escritura y eliminación temporal correctas."}
    except Exception as error:
        return {"ok": False, "detail": f"{type(error).__name__}: {error}"}


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as source:
            payload = json.load(source)
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _resource_inventory() -> dict:
    version_data = _read_json(ruta_recurso_instalado("version.json"))
    expected_lisps = sorted(
        path for path in version_data.get("archivos") or []
        if isinstance(path, str) and path.lower().startswith("lisps/") and path.lower().endswith(".lsp")
    )
    missing_lisps = [
        relative for relative in expected_lisps
        if not os.path.isfile(ruta_recurso(*relative.split("/")))
    ]
    critical = []
    for relative in CRITICAL_RESOURCES:
        path = ruta_recurso(*relative.split("/"))
        exists = os.path.isfile(path)
        item = {"path": relative, "exists": exists}
        if exists:
            try:
                item.update({"bytes": os.path.getsize(path), "sha256": _sha256(path)})
            except OSError as error:
                item["error"] = str(error)
        critical.append(item)

    sync_state = _read_json(state_path())
    return {
        "expected_lisp_count": len(expected_lisps),
        "active_lisp_count": len(active_resource_paths(("lisps/",))),
        "missing_lisps": missing_lisps,
        "critical": critical,
        "sync": {
            "repository": sync_state.get("repository"),
            "branch": sync_state.get("branch"),
            "tree_sha": sync_state.get("tree_sha"),
            "resource_count": len(sync_state.get("resources") or {}),
        },
    }


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _running_cad_processes() -> list[str]:
    tasklist = shutil.which("tasklist.exe") or shutil.which("tasklist")
    if not tasklist:
        return []
    probe = _run_probe([tasklist, "/fo", "csv", "/nh"], timeout=8)
    names = []
    for line in probe.get("output", "").splitlines():
        lowered = line.lower()
        if any(name in lowered for name in ("acad.exe", "accoreconsole.exe", "zwcad.exe")):
            names.append(line.split(",", 1)[0].strip('"'))
    return sorted(set(names), key=str.lower)


def _tail_text(path: str, max_bytes=200_000) -> str:
    try:
        with open(path, "rb") as source:
            source.seek(0, os.SEEK_END)
            size = source.tell()
            source.seek(max(0, size - max_bytes))
            return source.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def load_incidents(limit=100) -> list[dict]:
    try:
        with open(incidents_path(), encoding="utf-8") as source:
            lines = source.readlines()[-limit:]
    except OSError:
        return []
    incidents = []
    for line in lines:
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                incidents.append(payload)
        except (ValueError, TypeError):
            continue
    return incidents


def record_incident(operation: str, status: str, details=None, sensitive_paths=()) -> None:
    asegurar_directorios()
    event = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "version": VERSION_ACTUAL,
        "operation": operation,
        "status": status,
        "details": _redact_value(details or {}, sensitive_paths),
    }
    encoded = json.dumps(event, ensure_ascii=False, default=str) + "\n"
    path = incidents_path()
    with _incident_lock:
        try:
            if os.path.isfile(path) and os.path.getsize(path) >= INCIDENT_LIMIT_BYTES:
                os.replace(path, path + ".1")
            with open(path, "a", encoding="utf-8", newline="\n") as target:
                target.write(encoded)
        except OSError:
            pass


def collect_diagnostics(project_path=None, description="") -> dict:
    asegurar_directorios()
    extra_paths = (project_path,) if project_path else ()
    cmd = shutil.which("cmd.exe") or shutil.which("cmd")
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    engines = discover_cad_engines()
    selected = load_engine_state()
    project = {
        "configured": bool(project_path),
        "path": project_path or "",
        "exists": bool(project_path and os.path.isdir(project_path)),
    }
    if project["exists"]:
        try:
            project["dwg_count"] = len([
                name for name in os.listdir(project_path) if name.lower().endswith(".dwg")
            ])
        except OSError as error:
            project["list_error"] = str(error)
        project["write_probe"] = _write_probe(project_path)

    commands = {
        "cmd": {
            "path": cmd,
            "probe": _run_probe([cmd, "/d", "/c", "echo SINCAL_CMD_OK"]) if cmd else {"ok": False, "output": "cmd.exe no encontrado"},
        },
        "powershell": {
            "path": powershell,
            "probe": _run_probe([
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "[Console]::OutputEncoding=[Text.Encoding]::UTF8; 'SINCAL_PS_OK|' + $PSVersionTable.PSVersion",
            ]) if powershell else {"ok": False, "output": "powershell.exe no encontrado"},
        },
    }

    resources = _resource_inventory()
    critical_missing = [item["path"] for item in resources["critical"] if not item["exists"]]
    findings = []
    if critical_missing:
        findings.append({"level": "error", "message": "Faltan recursos esenciales: " + ", ".join(critical_missing)})
    if resources["missing_lisps"]:
        findings.append({"level": "error", "message": "Faltan LISPs: " + ", ".join(resources["missing_lisps"])})
    if not engines:
        findings.append({"level": "error", "message": "No se detectó un motor AutoCAD/ZWCAD compatible."})
    elif selected is None:
        findings.append({"level": "warning", "message": "Hay motores CAD instalados, pero ninguno está seleccionado."})
    if not commands["cmd"]["probe"].get("ok"):
        findings.append({"level": "error", "message": "La prueba de cmd.exe falló."})
    if not commands["powershell"]["probe"].get("ok"):
        findings.append({"level": "error", "message": "La prueba de PowerShell falló."})
    if project.get("write_probe") and not project["write_probe"].get("ok"):
        findings.append({"level": "error", "message": "SINCAL no puede escribir temporalmente en la carpeta del proyecto."})
    if not findings:
        findings.append({"level": "ok", "message": "Las comprobaciones locales no detectaron bloqueos."})

    report = {
        "schema": DIAGNOSTIC_SCHEMA,
        "report_id": uuid.uuid4().hex[:8].upper(),
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "description": redact_text(description, extra_paths),
        "application": {
            "version": VERSION_ACTUAL,
            "frozen": bool(getattr(__import__("sys"), "frozen", False)),
            "installation": RUTA_INSTALACION,
            "data": RUTA_DATOS_USUARIO,
            "admin": _is_admin(),
        },
        "system": {
            "os": platform.platform(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "resources": resources,
        "cad": {
            "selected": selected.to_dict() if selected else None,
            "engines": [engine.to_dict() for engine in engines],
            "state_exists": os.path.isfile(engine_state_path()),
            "legacy_wrapper_exists": os.path.isfile(legacy_wrapper_path()),
            "running_processes": _running_cad_processes(),
        },
        "commands": commands,
        "permissions": {
            "data": _write_probe(RUTA_DATOS_USUARIO),
            "logs": _write_probe(RUTA_LOGS),
        },
        "project": project,
        "findings": findings,
        "incidents": load_incidents(),
    }
    return _redact_value(report, extra_paths, redact_filenames=False)


def format_summary(report: dict) -> str:
    lines = [
        "SINCAL — INFORME DE DIAGNÓSTICO",
        f"ID: {report.get('report_id', '')}",
        f"Fecha: {report.get('created_at', '')}",
        f"Versión: {(report.get('application') or {}).get('version', '')}",
        "",
        "RESULTADOS",
    ]
    for finding in report.get("findings") or []:
        lines.append(f"[{str(finding.get('level', '')).upper()}] {finding.get('message', '')}")
    cad = report.get("cad") or {}
    selected = cad.get("selected") or {}
    lines.extend([
        "",
        "MOTOR CAD",
        f"Seleccionado: {selected.get('label') or 'Ninguno'}",
        f"Ruta: {selected.get('path') or 'No disponible'}",
        f"Motores detectados: {len(cad.get('engines') or [])}",
        f"Wrapper heredado: {'sí' if cad.get('legacy_wrapper_exists') else 'no'}",
        "",
        "RECURSOS",
        f"LISPs esperados: {(report.get('resources') or {}).get('expected_lisp_count', 0)}",
        f"LISPs activos: {(report.get('resources') or {}).get('active_lisp_count', 0)}",
    ])
    return "\n".join(lines) + "\n"


def create_diagnostic_bundle(destination: str, project_path=None, description="") -> tuple[str, dict]:
    report = collect_diagnostics(project_path=project_path, description=description)
    destination = os.path.abspath(destination)
    if not destination.lower().endswith(".zip"):
        destination += ".zip"
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    temporary = destination + ".tmp"
    log_text = redact_text(_tail_text(os.path.join(RUTA_LOGS, "sincal.log")), (project_path,) if project_path else ())
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("diagnostico.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            archive.writestr("resumen.txt", format_summary(report))
            archive.writestr("sincal.log", log_text)
            archive.writestr(
                "PRIVACIDAD.txt",
                "Este informe no contiene archivos DWG ni credenciales. "
                "Las rutas de usuario, equipo y proyecto fueron anonimizadas.\n",
            )
        os.replace(temporary, destination)
    except Exception:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise
    return destination, report
