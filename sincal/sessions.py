"""Persistencia segura de sesiones del generador de armaduras."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sincal.runtime import VERSION_ACTUAL, ruta_datos


SESSION_SCHEMA = 1
SESSION_SUFFIX = ".sincal-session.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: str | os.PathLike | None) -> str:
    if not path or not os.path.isfile(path):
        return ""
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_search_text(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).lower()


def safe_session_filename(name: str) -> str:
    clean = unicodedata.normalize("NFKD", name or "Sesion")
    clean = "".join(char for char in clean if not unicodedata.combining(char))
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", clean).strip("-._") or "Sesion"
    return f"{clean}{SESSION_SUFFIX}"


def default_sessions_directory() -> Path:
    documents = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"
    return documents / "SINCAL" / "Sesiones"


def atomic_json_write(path: str | os.PathLike, payload: dict, backup: bool = True) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if backup and target.exists():
        shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
    handle, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return target


class SessionStore:
    def __init__(self, sessions_dir=None, recovery_dir=None):
        self.sessions_dir = Path(sessions_dir or default_sessions_directory())
        self.recovery_dir = Path(recovery_dir or ruta_datos("sessions"))

    def save(self, payload: dict, path=None) -> tuple[dict, Path]:
        document = self._prepare_document(payload)
        metadata = document["metadata"]
        if path is None:
            candidate = self.sessions_dir / safe_session_filename(metadata.get("name", "Sesion"))
            if candidate.exists():
                stem = candidate.name[:-len(SESSION_SUFFIX)]
                candidate = candidate.with_name(
                    f"{stem}-{metadata['id'][:8]}{SESSION_SUFFIX}")
            path = candidate
        target = atomic_json_write(path, document)
        return document, target

    @staticmethod
    def _prepare_document(payload: dict) -> dict:
        document = dict(payload)
        metadata = dict(document.get("metadata") or {})
        now = utc_now_iso()
        metadata.setdefault("id", str(uuid.uuid4()))
        metadata.setdefault("created_at", now)
        metadata["updated_at"] = now
        metadata["app_version"] = VERSION_ACTUAL
        document["schema_version"] = SESSION_SCHEMA
        document["metadata"] = metadata
        return document

    def load(self, path) -> dict:
        with open(path, "r", encoding="utf-8") as source:
            document = json.load(source)
        if not isinstance(document, dict):
            raise ValueError("El archivo de sesión no contiene un objeto JSON.")
        version = int(document.get("schema_version", 0))
        if version != SESSION_SCHEMA:
            raise ValueError(f"Esquema de sesión no compatible: {version}.")
        if not isinstance(document.get("metadata"), dict):
            raise ValueError("La sesión no contiene metadatos.")
        return document

    def summaries(self) -> list[dict]:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        summaries = []
        for path in self.sessions_dir.glob(f"*{SESSION_SUFFIX}"):
            try:
                document = self.load(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            metadata = dict(document.get("metadata") or {})
            project = dict(document.get("project") or {})
            overview = dict(document.get("overview") or {})
            summaries.append({
                "path": str(path),
                "metadata": metadata,
                "project": project,
                "overview": overview,
                "search_text": normalized_search_text(" ".join(map(str, (
                    metadata.get("name", ""), project.get("bridge_name", ""),
                    project.get("project_code", ""), project.get("plan_name", ""),
                    project.get("ot", ""), project.get("revision", ""),
                    project.get("structure_name", ""),
                    project.get("json_name", ""), metadata.get("tags", ""),
                )))),
            })
        return sorted(
            summaries,
            key=lambda item: item["metadata"].get("updated_at", ""), reverse=True)

    def autosave(self, payload: dict) -> Path:
        document = self._prepare_document(payload)
        session_id = document["metadata"]["id"]
        target = self.recovery_dir / f"recovery-{session_id}.json"
        return atomic_json_write(target, document, backup=False)

    def pending_recoveries(self) -> list[dict]:
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        formal_dates = {
            item["metadata"].get("id"): item["metadata"].get("updated_at", "")
            for item in self.summaries()
        }
        pending = []
        for path in self.recovery_dir.glob("recovery-*.json"):
            try:
                document = self.load(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            metadata = document["metadata"]
            session_id = metadata.get("id")
            if formal_dates.get(session_id, "") >= metadata.get("updated_at", ""):
                continue
            pending.append({"path": str(path), "document": document})
        return sorted(
            pending,
            key=lambda item: item["document"]["metadata"].get("updated_at", ""),
            reverse=True,
        )

    def clear_autosave(self, session_id: str | None):
        if not session_id:
            return
        target = self.recovery_dir / f"recovery-{session_id}.json"
        try:
            target.unlink()
        except FileNotFoundError:
            pass
