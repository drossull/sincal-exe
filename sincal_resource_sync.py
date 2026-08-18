import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from urllib.parse import quote

from sincal_runtime import (
    RUTA_RECURSOS_USUARIO,
    es_recurso_actualizable,
    ruta_cad_usuario,
    ruta_recurso,
    ruta_recurso_instalado,
)
from sincal_update_config import (
    DISTRIBUTION_BRANCH,
    DISTRIBUTION_OWNER,
    DISTRIBUTION_REPOSITORY,
    api_url as distribution_api_url,
)

REQUEST_TIMEOUT = (3.05, 30)
STATE_SCHEMA = 1
MAX_TOTAL_UPDATE_BYTES = 250 * 1024 * 1024
REQUIRED_RESOURCES = {
    "lisps/SINCAL.lsp",
    "masters/FORMATOS ANOTATIVOS ACAD_2025.dwg",
}
CAD_RESOURCE_PREFIXES = ("lisps/", "startup/", "scripts/", "plotstyles/", "masters/")
TEXT_EXTENSIONS = {".lsp", ".ps1", ".bat", ".scr", ".json"}


@dataclass(frozen=True)
class ResourceEntry:
    path: str
    sha: str
    size: int


@dataclass(frozen=True)
class ResourceUpdatePlan:
    tree_sha: str
    resources: tuple[ResourceEntry, ...]
    changed: tuple[ResourceEntry, ...]
    removed: tuple[str, ...]
    initial: bool

    @property
    def has_changes(self) -> bool:
        return bool(self.changed or self.removed)


@dataclass(frozen=True)
class ResourceSyncResult:
    updated: tuple[str, ...]
    removed: tuple[str, ...]
    tree_sha: str


def state_path() -> str:
    return os.path.join(RUTA_RECURSOS_USUARIO, "resource_sync.json")


def resource_cache_path(relative_path: str) -> str:
    normalized = _normalize_relative_path(relative_path)
    return os.path.join(RUTA_RECURSOS_USUARIO, *normalized.split("/"))


def git_blob_sha(data: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(f"blob {len(data)}\0".encode("ascii"))
    digest.update(data)
    return digest.hexdigest()


def _file_git_blob_sha(path: str, size: int, normalize_text: bool = False) -> str:
    if normalize_text:
        with open(path, "rb") as source:
            data = source.read().replace(b"\r\n", b"\n")
        return git_blob_sha(data)

    digest = hashlib.sha1()
    digest.update(f"blob {size}\0".encode("ascii"))
    with open(path, "rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_relative_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized or normalized.startswith(".") or "/../" in f"/{normalized}/":
        raise ValueError(f"Ruta de recurso inválida: {path}")
    if not es_recurso_actualizable(normalized):
        raise ValueError(f"Recurso fuera de la política de actualización: {path}")
    return normalized


def _max_size_for_path(path: str) -> int:
    extension = os.path.splitext(path.lower())[1]
    if extension == ".png":
        return 30 * 1024 * 1024
    if extension == ".dwg":
        return 25 * 1024 * 1024
    if extension == ".ctb":
        return 10 * 1024 * 1024
    return 5 * 1024 * 1024


def _validate_resource_data(entry: ResourceEntry, data: bytes) -> None:
    if len(data) != entry.size:
        raise ValueError(f"Tamaño inesperado para {entry.path}.")
    if len(data) > _max_size_for_path(entry.path):
        raise ValueError(f"{entry.path} excede el tamaño permitido.")
    if git_blob_sha(data) != entry.sha:
        raise ValueError(f"El SHA de {entry.path} no coincide con GitHub.")

    extension = os.path.splitext(entry.path.lower())[1]
    if extension == ".dwg" and re.fullmatch(rb"AC\d{4}", data[:6]) is None:
        raise ValueError(f"{entry.path} no tiene una cabecera DWG válida.")
    if extension == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"{entry.path} no tiene una cabecera PNG válida.")
    if extension in TEXT_EXTENSIONS:
        if b"\x00" in data:
            raise ValueError(f"{entry.path} contiene bytes nulos inesperados.")
        text = data.decode("utf-8-sig")
        if extension == ".json":
            json.loads(text)


def _load_state() -> dict:
    try:
        with open(state_path(), encoding="utf-8") as source:
            state = json.load(source)
        if state.get("schema") != STATE_SCHEMA:
            return {}
        if state.get("repository") != f"{DISTRIBUTION_OWNER}/{DISTRIBUTION_REPOSITORY}":
            return {}
        if state.get("branch") != DISTRIBUTION_BRANCH:
            return {}
        if not isinstance(state.get("resources"), dict):
            return {}
        return state
    except (OSError, ValueError, TypeError):
        return {}


def _atomic_write(path: str, data: bytes) -> None:
    target_dir = os.path.dirname(path)
    os.makedirs(target_dir, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".sincal-", suffix=".tmp", dir=target_dir)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


def _serialize_state(plan: ResourceUpdatePlan) -> bytes:
    resources = {
        entry.path: {"sha": entry.sha, "size": entry.size}
        for entry in plan.resources
    }
    state = {
        "schema": STATE_SCHEMA,
        "repository": f"{DISTRIBUTION_OWNER}/{DISTRIBUTION_REPOSITORY}",
        "branch": DISTRIBUTION_BRANCH,
        "tree_sha": plan.tree_sha,
        "resources": resources,
    }
    return json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")


def record_resource_state(plan: ResourceUpdatePlan) -> None:
    _atomic_write(state_path(), _serialize_state(plan))


def _tree_url() -> str:
    branch = quote(DISTRIBUTION_BRANCH, safe="")
    return distribution_api_url(f"git/trees/{branch}?recursive=1")


def _session_or_requests(session):
    if session is not None:
        return session
    import requests

    return requests


def _headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SINCAL-Resource-Sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _entry_from_tree(raw: dict) -> ResourceEntry | None:
    if raw.get("type") != "blob" or raw.get("mode") not in {"100644", "100755"}:
        return None
    path = str(raw.get("path") or "")
    if not es_recurso_actualizable(path):
        return None
    path = _normalize_relative_path(path)
    sha = str(raw.get("sha") or "").lower()
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError(f"SHA inválido para {path}.")
    size = int(raw.get("size") or 0)
    if not 0 < size <= _max_size_for_path(path):
        raise ValueError(f"Tamaño publicado fuera de rango para {path}.")
    return ResourceEntry(path, sha, size)


def _effective_file_matches(entry: ResourceEntry, previous_resources: dict) -> bool:
    path = ruta_recurso(*entry.path.split("/"))
    extension = os.path.splitext(entry.path.lower())[1]
    try:
        local_size = os.path.getsize(path)
        if extension in TEXT_EXTENSIONS:
            return _file_git_blob_sha(path, local_size, normalize_text=True) == entry.sha
        if local_size != entry.size:
            return False
        previous = previous_resources.get(entry.path)
        if isinstance(previous, dict) and previous.get("sha") == entry.sha:
            return True
        return _file_git_blob_sha(path, entry.size) == entry.sha
    except OSError:
        return False


def check_resource_updates(session=None) -> ResourceUpdatePlan:
    client = _session_or_requests(session)
    response = client.get(_tree_url(), headers=_headers(), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if payload.get("truncated"):
        raise ValueError("GitHub devolvió un árbol truncado; no se aplicarán cambios.")

    tree_sha = str(payload.get("sha") or "").lower()
    if re.fullmatch(r"[0-9a-f]{40}", tree_sha) is None:
        raise ValueError("GitHub devolvió un SHA de árbol inválido.")

    entries = []
    for raw in payload.get("tree") or []:
        entry = _entry_from_tree(raw)
        if entry is not None:
            entries.append(entry)
    entries.sort(key=lambda item: item.path.lower())

    paths = {entry.path for entry in entries}
    missing_required = sorted(REQUIRED_RESOURCES - paths)
    if missing_required:
        raise ValueError("Faltan recursos esenciales en GitHub: " + ", ".join(missing_required))

    state = _load_state()
    previous_resources = state.get("resources") or {}
    changed = [
        entry for entry in entries
        if not _effective_file_matches(entry, previous_resources)
    ]
    removed = sorted(set(previous_resources) - paths)
    total = sum(entry.size for entry in changed)
    if total > MAX_TOTAL_UPDATE_BYTES:
        raise ValueError("La actualización excede el tamaño total permitido.")

    return ResourceUpdatePlan(
        tree_sha=tree_sha,
        resources=tuple(entries),
        changed=tuple(changed),
        removed=tuple(removed),
        initial=not bool(state),
    )


def _raw_url(path: str) -> str:
    encoded = quote(_normalize_relative_path(path), safe="/")
    return (
        f"https://raw.githubusercontent.com/{DISTRIBUTION_OWNER}/"
        f"{DISTRIBUTION_REPOSITORY}/{DISTRIBUTION_BRANCH}/{encoded}"
    )


def _download_resource(entry: ResourceEntry, client) -> bytes:
    installed = ruta_recurso_instalado(*entry.path.split("/"))
    try:
        installed_size = os.path.getsize(installed)
        extension = os.path.splitext(entry.path.lower())[1]
        installed_sha = _file_git_blob_sha(
            installed,
            installed_size,
            normalize_text=extension in TEXT_EXTENSIONS,
        )
        if installed_sha == entry.sha:
            with open(installed, "rb") as source:
                data = source.read()
            _validate_resource_data(entry, data)
            return data
    except OSError:
        pass

    response = client.get(
        _raw_url(entry.path),
        headers={"User-Agent": _headers()["User-Agent"]},
        timeout=REQUEST_TIMEOUT,
        stream=True,
    )
    response.raise_for_status()
    chunks = []
    downloaded = 0
    limit = _max_size_for_path(entry.path)
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if not chunk:
            continue
        downloaded += len(chunk)
        if downloaded > limit:
            raise ValueError(f"La descarga de {entry.path} excede el límite permitido.")
        chunks.append(chunk)
    data = b"".join(chunks)
    _validate_resource_data(entry, data)
    return data


def apply_resource_updates(plan: ResourceUpdatePlan, session=None) -> ResourceSyncResult:
    client = _session_or_requests(session)
    os.makedirs(RUTA_RECURSOS_USUARIO, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sincal-update-", dir=RUTA_RECURSOS_USUARIO) as staging:
        staged = []
        for entry in plan.changed:
            data = _download_resource(entry, client)
            staged_path = os.path.join(staging, *entry.path.split("/"))
            os.makedirs(os.path.dirname(staged_path), exist_ok=True)
            with open(staged_path, "wb") as target:
                target.write(data)
            staged.append((entry, staged_path))

        for entry, staged_path in staged:
            destination = resource_cache_path(entry.path)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            os.replace(staged_path, destination)

    for removed_path in plan.removed:
        try:
            os.remove(resource_cache_path(removed_path))
        except FileNotFoundError:
            pass

    record_resource_state(plan)
    return ResourceSyncResult(
        updated=tuple(entry.path for entry in plan.changed),
        removed=plan.removed,
        tree_sha=plan.tree_sha,
    )


def active_resource_paths(prefixes: tuple[str, ...] | None = None) -> list[str]:
    state = _load_state()
    resources = state.get("resources") or {}
    if resources:
        paths = list(resources)
    else:
        paths = []
        for root_name in ("lisps", "startup", "scripts", "plotstyles", "masters", "mapas"):
            root = ruta_recurso_instalado(root_name)
            if not os.path.isdir(root):
                continue
            for current, _, files in os.walk(root):
                for name in files:
                    relative = os.path.relpath(os.path.join(current, name), ruta_recurso_instalado())
                    relative = relative.replace("\\", "/")
                    if es_recurso_actualizable(relative):
                        paths.append(relative)
        for exact in ("tutoriales.json",):
            if os.path.isfile(ruta_recurso_instalado(exact)):
                paths.append(exact)

    if prefixes:
        paths = [path for path in paths if path.startswith(prefixes)]
    return sorted(set(paths), key=str.lower)


def _cad_state_path() -> str:
    return ruta_cad_usuario(".sincal_resources.json")


def materialize_cad_resources() -> tuple[str, ...]:
    active = active_resource_paths(CAD_RESOURCE_PREFIXES)
    copied = []
    for relative in active:
        source = ruta_recurso(*relative.split("/"))
        if not os.path.isfile(source):
            raise FileNotFoundError(f"No está disponible el recurso CAD {relative}.")
        destination = ruta_cad_usuario(*relative.split("/"))
        source_size = os.path.getsize(source)
        same = False
        try:
            same = (
                os.path.getsize(destination) == source_size
                and _file_git_blob_sha(destination, source_size) == _file_git_blob_sha(source, source_size)
            )
        except OSError:
            pass
        if not same:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix=".sincal-cad-", suffix=".tmp", dir=os.path.dirname(destination))
            os.close(fd)
            try:
                shutil.copy2(source, temp_path)
                os.replace(temp_path, destination)
            except Exception:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
                raise
            copied.append(relative)

    try:
        with open(_cad_state_path(), encoding="utf-8") as source:
            previous = set(json.load(source).get("resources") or [])
    except (OSError, ValueError, TypeError):
        previous = set()
    active_set = set(active)
    for removed in previous - active_set:
        if removed.startswith(CAD_RESOURCE_PREFIXES):
            try:
                os.remove(ruta_cad_usuario(*removed.split("/")))
            except FileNotFoundError:
                pass

    payload = json.dumps({"resources": active}, indent=2, ensure_ascii=False).encode("utf-8")
    _atomic_write(_cad_state_path(), payload)
    return tuple(copied)
