import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sincal_runtime import ruta_runtime


ENGINE_STATE_SCHEMA = 1
PREFERRED_AUTOCAD_YEAR = 2025
ENGINE_FILENAMES = {
    "accoreconsole.exe": ("AutoCAD Core Console", True),
    "zwcad.exe": ("ZWCAD", False),
}


@dataclass(frozen=True)
class CadEngine:
    path: str
    product: str
    version: str
    year: int
    headless: bool

    @property
    def label(self) -> str:
        mode = "consola" if self.headless else "aplicación"
        year = f" {self.year}" if self.year else ""
        version = "" if self.version == str(self.year) else f" · {self.version}"
        return f"{self.product}{year}{version} · {mode}"

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["label"] = self.label
        return payload


def engine_state_path() -> str:
    return ruta_runtime("cad_engine.json")


def legacy_wrapper_path() -> str:
    return ruta_runtime("cad_wrapper.bat")


def _default_search_roots() -> tuple[str, ...]:
    roots = []
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        base = os.getenv(variable)
        if not base:
            continue
        roots.extend((os.path.join(base, "Autodesk"), os.path.join(base, "ZWSOFT")))
    unique = []
    seen = set()
    for root in roots:
        normalized = os.path.normcase(os.path.abspath(root))
        if normalized not in seen and os.path.isdir(root):
            seen.add(normalized)
            unique.append(root)
    return tuple(unique)


def _path_year(path: str) -> int:
    years = [int(value) for value in re.findall(r"(?<!\d)(20\d{2})(?!\d)", path)]
    return max(years, default=0)


def _file_version(path: str) -> str:
    try:
        import win32api

        info = win32api.GetFileVersionInfo(path, "\\")
        major = info["FileVersionMS"] >> 16
        minor = info["FileVersionMS"] & 0xFFFF
        build = info["FileVersionLS"] >> 16
        revision = info["FileVersionLS"] & 0xFFFF
        return f"{major}.{minor}.{build}.{revision}"
    except Exception:
        year = _path_year(path)
        return str(year) if year else "desconocida"


def _engine_from_path(path: str) -> CadEngine | None:
    absolute = os.path.abspath(path)
    filename = os.path.basename(absolute).lower()
    policy = ENGINE_FILENAMES.get(filename)
    if policy is None or not os.path.isfile(absolute):
        return None
    product, headless = policy
    return CadEngine(
        path=absolute,
        product=product,
        version=_file_version(absolute),
        year=_path_year(absolute),
        headless=headless,
    )


def _version_numbers(version: str) -> tuple[int, ...]:
    values = tuple(int(value) for value in re.findall(r"\d+", version))
    return values or (0,)


def discover_cad_engines(search_roots=None) -> tuple[CadEngine, ...]:
    roots = tuple(search_roots) if search_roots is not None else _default_search_roots()
    discovered = {}
    for root in roots:
        if os.path.isfile(root):
            candidate = _engine_from_path(root)
            if candidate:
                discovered[os.path.normcase(candidate.path)] = candidate
            continue
        if not os.path.isdir(root):
            continue
        for current, directories, files in os.walk(root):
            directories[:] = [name for name in directories if not name.startswith((".", "$"))]
            for filename in files:
                if filename.lower() not in ENGINE_FILENAMES:
                    continue
                candidate = _engine_from_path(os.path.join(current, filename))
                if candidate:
                    discovered[os.path.normcase(candidate.path)] = candidate

    return tuple(sorted(
        discovered.values(),
        key=lambda item: (
            1 if item.headless else 0,
            1 if item.year == PREFERRED_AUTOCAD_YEAR else 0,
            item.year,
            _version_numbers(item.version),
            os.path.normcase(item.path),
        ),
        reverse=True,
    ))


def load_engine_state() -> CadEngine | None:
    try:
        with open(engine_state_path(), encoding="utf-8") as source:
            state = json.load(source)
        if state.get("schema") != ENGINE_STATE_SCHEMA:
            return None
        selected = state.get("selected") or {}
        return _engine_from_path(str(selected.get("path") or ""))
    except (OSError, ValueError, TypeError):
        return None


def _atomic_json(path: str, payload: dict) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".sincal-engine-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as target:
            json.dump(payload, target, indent=2, ensure_ascii=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise


def _write_legacy_wrapper(engine: CadEngine) -> None:
    if '"' in engine.path:
        raise ValueError("La ruta del motor CAD contiene comillas inválidas.")
    content = f'@echo off\r\n"{engine.path}" %*\r\n'
    path = legacy_wrapper_path()
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".sincal-wrapper-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as target:
            target.write(content)
        os.replace(temporary, path)
    except Exception:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise


def save_engine_selection(engine, candidates=None) -> CadEngine:
    selected = engine if isinstance(engine, CadEngine) else _engine_from_path(str(engine))
    if selected is None:
        raise FileNotFoundError("El motor CAD seleccionado no existe o no está autorizado.")
    available = tuple(candidates) if candidates is not None else discover_cad_engines()
    if not any(os.path.normcase(item.path) == os.path.normcase(selected.path) for item in available):
        available = (selected,) + available
    payload = {
        "schema": ENGINE_STATE_SCHEMA,
        "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "selected": selected.to_dict(),
        "candidates": [item.to_dict() for item in available],
    }
    _atomic_json(engine_state_path(), payload)
    _write_legacy_wrapper(selected)
    return selected


def ensure_cad_engine(search_roots=None) -> CadEngine | None:
    current = load_engine_state()
    candidates = discover_cad_engines(search_roots=search_roots)
    if current:
        match = next(
            (item for item in candidates if os.path.normcase(item.path) == os.path.normcase(current.path)),
            current,
        )
        return save_engine_selection(match, candidates)
    if not candidates:
        return None
    return save_engine_selection(candidates[0], candidates)
