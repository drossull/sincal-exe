"""Lightweight host for the optional Pasarela package; never imports its engine.

Installation is explicit, from a validated local package or the official asset
pinned to this core release. The separate module process owns its editor and
data, so closing SINCAL does not discard it.
"""
from __future__ import annotations

import hashlib
import io
from http.client import HTTPException
from contextlib import contextmanager
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler, HTTPSHandler, ProxyHandler
import uuid
import webbrowser
import zipfile

MODULE_ID = "pasarela-bim"
ENTRYPOINT = "SINCAL-Pasarela.exe"
MAX_PACKAGE_BYTES = 150 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
HOST_API = 1
RELEASE_REPOSITORY = "https://github.com/drossull/sincal-updates"
MAX_RELEASE_MANIFEST_BYTES = 1024 * 1024
NETWORK_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 180
_DLL_LOCK = threading.Lock()


def _release_context():
    # Read the installed core's version, never a latest-release/channel pointer.
    from .runtime import leer_version
    version = leer_version()
    if not isinstance(version,str) or not re.fullmatch(r"v\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?",version) or version == "v0.0.0":
        return None
    base = f"{RELEASE_REPOSITORY}/releases/download/{version}"
    return {"version":version,"base_url":base,"release_url":f"{RELEASE_REPOSITORY}/releases/tag/{version}",
            "manifest_url":f"{base}/release-manifest_{version}.json"}


def _allowed_download_url(url, original):
    try:
        parsed = urlsplit(url)
        invalid = parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.fragment
    except (TypeError,ValueError):
        return False
    if invalid:
        return False
    # GitHub's public release endpoint redirects to its asset CDN. Never follow
    # a release-provided URL to a different repository, arbitrary host or HTTP.
    return url == original or parsed.hostname in {"release-assets.githubusercontent.com","objects.githubusercontent.com"}


class _ReleaseRedirects(HTTPRedirectHandler):
    def __init__(self, original):
        super().__init__()
        self.original = original

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed_download_url(newurl,self.original):
            raise ValueError("La descarga oficial redirigió a una ubicación no autorizada.")
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def _open_release_download(url):
    import ssl
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()),_ReleaseRedirects(url))
    request = Request(url,headers={"User-Agent":"SINCAL-OptionalModules/1","Accept-Encoding":"identity"})
    return opener.open(request,timeout=NETWORK_TIMEOUT)


def _stream_release(url, output, limit, *, expected_size=None, expected_hash=None):
    """Bounded TLS download; no credentials and no installation side effects."""
    total, checksum = 0,hashlib.sha256()
    deadline = time.monotonic()+DOWNLOAD_TIMEOUT
    try:
        with _open_release_download(url) as response:
            if not _allowed_download_url(response.geturl(),url):
                raise ValueError("La descarga oficial devolvió una ubicación no autorizada.")
            if response.status != 200:
                raise ValueError("El servidor no entregó un archivo completo para instalar.")
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    length = int(length)
                except (ValueError,TypeError) as exc:
                    raise ValueError("La descarga declara un tamaño no válido.") from exc
                if length < 0 or length > limit or expected_size is not None and length != expected_size:
                    raise ValueError("El tamaño de la descarga no coincide con el paquete oficial.")
            while True:
                if time.monotonic() >= deadline:
                    raise ValueError("La descarga agotó el tiempo permitido; vuelve a intentarlo.")
                chunk = response.read(min(65536,limit-total+1))
                if not chunk:
                    break
                total += len(chunk)
                if total > limit or expected_size is not None and total > expected_size:
                    raise ValueError("La descarga excede el tamaño autorizado del paquete.")
                checksum.update(chunk)
                output.write(chunk)
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError("Este release de SINCAL todavía no publica el módulo Pasarela BIM compatible.") from None
        raise ValueError(f"No se pudo descargar el módulo oficial (respuesta HTTP {exc.code}); vuelve a intentarlo.") from None
    except (URLError,OSError,TimeoutError,HTTPException):
        # Do not include exception URLs/reasons: a configured proxy may contain
        # credentials. The TLS verifier remains enabled with system defaults.
        raise ValueError("No se pudo descargar el módulo oficial. Comprueba la conexión y vuelve a intentarlo.") from None
    if not total or expected_size is not None and total != expected_size:
        raise ValueError("La descarga está incompleta; no se instaló el módulo.")
    if expected_hash is not None and checksum.hexdigest() != expected_hash:
        raise ValueError("La comprobación SHA-256 del paquete falló; no se instaló el módulo.")
    return total


def _online_asset(raw, release):
    try:
        manifest = json.loads(raw.decode("utf-8-sig"))
    except (ValueError,UnicodeError,AttributeError,RecursionError):
        raise ValueError("El manifiesto oficial de este release no es válido.") from None
    if not isinstance(manifest,dict) or type(manifest.get("schema")) is not int or manifest["schema"] != 1 or manifest.get("product") != "SINCAL Suite" or manifest.get("release") != release["version"]:
        raise ValueError("El manifiesto oficial no corresponde a la versión instalada de SINCAL.")
    assets = manifest.get("assets")
    asset = assets.get("pasarela_bim") if isinstance(assets,dict) else None
    if not isinstance(asset,dict):
        raise ValueError("Este release de SINCAL no incluye el módulo opcional Pasarela BIM.")
    version = asset.get("version")
    if not isinstance(version,str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?",version):
        raise ValueError("El release no declara una versión válida de Pasarela BIM.")
    name = f"SINCAL_Pasarela_v{version}.zip"
    if asset.get("name") != name or asset.get("url") != f"{release['base_url']}/{name}":
        raise ValueError("El paquete de Pasarela BIM debe pertenecer al mismo release oficial de SINCAL.")
    if type(asset.get("host_api")) is not int or asset["host_api"] != HOST_API:
        raise ValueError("El módulo publicado requiere otra versión de SINCAL.")
    if type(asset.get("bytes")) is not int or not 0 < asset["bytes"] <= MAX_PACKAGE_BYTES:
        raise ValueError("El tamaño publicado del módulo no es válido o supera 150 MiB.")
    if not isinstance(asset.get("sha256"),str) or not re.fullmatch("[0-9a-f]{64}",asset["sha256"]):
        raise ValueError("El release no declara una comprobación SHA-256 válida.")
    return asset


@contextmanager
def _external_dlls():
    if os.name != "nt" or not getattr(sys, "frozen", False):
        yield
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetDllDirectoryW.argtypes = (wintypes.DWORD, wintypes.LPWSTR)
    kernel.GetDllDirectoryW.restype = wintypes.DWORD
    kernel.SetDllDirectoryW.argtypes = (wintypes.LPCWSTR,)
    kernel.SetDllDirectoryW.restype = wintypes.BOOL
    with _DLL_LOCK:
        buffer = ctypes.create_unicode_buffer(kernel.GetDllDirectoryW(0, None) + 1)
        kernel.GetDllDirectoryW(len(buffer), buffer)
        previous = buffer.value or None
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield
        finally:
            kernel.SetDllDirectoryW(previous)


def _read_manifest(raw):
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("El manifiesto del módulo no es válido.") from exc
    if not isinstance(manifest, dict) or type(manifest.get("schema")) is not int or type(manifest.get("host_api")) is not int or any(manifest.get(k) != v for k, v in
            (("schema", 1), ("id", MODULE_ID), ("host_api", HOST_API), ("entrypoint", ENTRYPOINT))):
        raise ValueError("Este paquete no corresponde a Pasarela BIM o requiere otra versión de SINCAL.")
    if not isinstance(manifest.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][\w.-]+)?", manifest["version"]):
        raise ValueError("El paquete no tiene una versión válida.")
    if "embedding" in manifest and (type(manifest["embedding"]) is not int or manifest["embedding"] < 1):
        raise ValueError("El paquete no declara una integración válida con SINCAL.")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files or ENTRYPOINT not in files:
        raise ValueError("El paquete no declara todos sus archivos y comprobaciones de integridad.")
    for name, digest in files.items():
        _archive_path(name)
        if name == "module.json" or not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("La lista de integridad del paquete no es válida.")
    return manifest


def _archive_path(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError("El paquete contiene una ruta no permitida.")
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ("", ".", "..") for p in name.rstrip("/").split("/")):
        raise ValueError("El paquete contiene una ruta no permitida.")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if any(p.endswith((" ", ".")) or p.split(".")[0].upper() in reserved or any(c in p for c in '<>"|?*') for p in path.parts):
        raise ValueError("El paquete contiene un nombre de archivo no permitido.")
    return path


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _remove_owned_directory(path, parent):
    if path.is_symlink() or path.resolve().parent != parent.resolve() or not path.name.startswith((".pasarela-stage-", ".pasarela-backup-")):
        raise ValueError("La carpeta temporal del módulo está fuera de su ubicación permitida.")
    shutil.rmtree(path)


def _parent_origin(origin):
    # An origin is exact: no path, credentials, whitespace, alternate loopback
    # spelling, query or fragment. Never accept a client-supplied embed target.
    if not isinstance(origin, str) or not re.fullmatch(r"http://127\.0\.0\.1:[1-9]\d{0,4}", origin) or int(origin.rsplit(":", 1)[1]) > 65535:
        raise ValueError("La dirección de integración con SINCAL no es válida.")
    return origin


def _local_url(url):
    try:
        origin = _parent_origin(url[:-1] if isinstance(url, str) and url.endswith("/") else url)
    except ValueError:
        raise ValueError("El módulo devolvió una dirección de inicio no válida.")
    return origin + "/"


class _NoLocalRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("El módulo devolvió una redirección no autorizada.")


def _control_request(info, route, *, payload=None, timeout=5):
    """Send the private control token only to the validated local endpoint."""
    token = info.get("control_token")
    if not isinstance(token, str) or not 20 <= len(token) <= 200:
        raise ValueError("El módulo no permite gestionar esta sesión. Actualiza su paquete.")
    headers = {"X-Pasarela-Token": token}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(_local_url(info.get("url")) + route, data=data, headers=headers)
    # Ignore ambient proxy settings and refuse redirects, including redirects
    # to another loopback service. The control token must stay in this process.
    opener = build_opener(ProxyHandler({}), _NoLocalRedirects())
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("El módulo devolvió una respuesta no válida.")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("El módulo devolvió una respuesta no válida.")
    return result


def _embedding_supported(manifest):
    return bool(manifest) and type(manifest.get("embedding")) is int and manifest["embedding"] == 1


def _embedding_update_message(running=False):
    return ("Guarda el JSON y usa «Cerrar módulo» antes de actualizar Pasarela BIM para abrirlo dentro de SINCAL."
            if running else "Actualiza Pasarela BIM para abrir el editor dentro de SINCAL.")


def _wait_windows_process(pid, timeout):
    """Wait only; never stop a recovered PID or an unrelated process."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
    if not handle:
        return ctypes.get_last_error() == 87  # PID no longer exists
    try:
        return kernel.WaitForSingleObject(handle, max(0, int(timeout * 1000))) == 0
    finally:
        kernel.CloseHandle(handle)


def _freecad_available():
    configured = os.environ.get("PASARELA_FREECAD")
    if configured and Path(configured).is_file():
        return True
    if shutil.which("FreeCAD.exe") or shutil.which("FreeCAD"):
        return True
    for key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        directory = os.environ.get(key)
        if directory and any(Path(directory).glob("FreeCAD*/bin/FreeCAD.exe")):
            return True
    return False


class PasarelaModule:
    def __init__(self, *, user_dir=None, application_dir=None, source_dir=None, allow_source=None):
        root = Path(__file__).resolve().parents[1]
        self.user_dir = Path(user_dir) if user_dir is not None else Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "SINCAL"
        self.application_dir = Path(application_dir) if application_dir is not None else Path(sys.executable).parent if getattr(sys, "frozen", False) else root
        self.source_dir = Path(source_dir) if source_dir is not None else root
        self.allow_source = not getattr(sys, "frozen", False) if allow_source is None else allow_source
        self.lock = threading.RLock()
        self.process = None
        self.url = None
        self.ready = None
        self._online_thread = None

    @property
    def target(self):
        return self.user_dir / "modules" / MODULE_ID

    @property
    def active_file(self):
        return self.user_dir / "pasarela-bim" / "active-launch.json"

    def _running_info(self):
        if self.process is not None and self.process.poll() is None and self.ready:
            return self.ready
        self.process, self.ready, self.url = None, None, None
        try:
            if self.active_file.stat().st_size > 8192:
                return None
            info = json.loads(self.active_file.read_text(encoding="utf-8"))
            url = _local_url(info["url"])
            token = info["control_token"]
            if not isinstance(token, str) or not 20 <= len(token) <= 200:
                return None
            current = _control_request(info, "api/host-status", timeout=.6)
            if current.get("pid") != info.get("pid") or current.get("version") != info.get("version"):
                return None
            info = {**info, "embedding": current.get("embedding"), "url": url}
            self.ready, self.url = info, url
            return info
        except (OSError, ValueError, KeyError, TypeError, HTTPException):
            return None

    def _discover(self):
        for location, source in ((self.target, "user"), (self.application_dir / "modules" / MODULE_ID, "application")):
            if not location.exists():
                continue
            try:
                manifest_path = location / "module.json"
                if manifest_path.stat().st_size > 1024 * 1024:
                    raise ValueError("Manifiesto demasiado grande.")
                manifest = _read_manifest(manifest_path.read_bytes())
                if not (location / ENTRYPOINT).is_file():
                    raise ValueError("Falta el ejecutable del módulo.")
                return location, source, manifest
            except (OSError, ValueError) as exc:
                raise ValueError("La instalación de Pasarela BIM está incompleta. Vuelve a instalar su paquete. " + str(exc)) from exc
        if self.allow_source and (self.source_dir / "pasarela_bim" / "__main__.py").is_file():
            init = (self.source_dir / "pasarela_bim" / "__init__.py").read_text(encoding="utf-8")
            match = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)', init)
            return self.source_dir, "development", {"version": match[1] if match else "desarrollo", "embedding": 1}
        return None, None, None

    def status(self):
        with self.lock:
            error = None
            try:
                _, source, manifest = self._discover()
            except ValueError as exc:
                source, manifest, error = None, None, str(exc)
            installed = manifest is not None
            release = _release_context()
            running = self._running_info()
            embedded_supported = _embedding_supported(manifest) and (running is None or _embedding_supported(running))
            return {"id": MODULE_ID, "nombre": "Pasarela BIM", "installed": installed,
                    "source": source, "version": manifest["version"] if installed else None,
                    "embedded_supported": embedded_supported,
                    "freecad_available": _freecad_available(), "max_package_bytes": MAX_PACKAGE_BYTES,
                    "running": running is not None,
                    "installing": self._online_thread is not None,
                    "online_install_available": release is not None,
                    "release_url": release["release_url"] if release else None,
                    "install_message": (f"Se descargará el módulo oficial correspondiente a SINCAL {release['version']}; su disponibilidad se comprueba al instalar."
                                        if release else "No se pudo identificar un release de SINCAL. Puedes instalar un paquete local compatible."),
                    "message": error or (_embedding_update_message(running is not None) if installed and not embedded_supported else
                        "Disponible desde el código de desarrollo." if source == "development" else
                        "Módulo instalado. Puedes abrir el editor." if installed else
                        "Módulo opcional. Instala el paquete Pasarela BIM cuando lo necesites.")}

    def install(self, package, *, expected_version=None):
        package = Path(package)
        with self.lock:
            if self._online_thread is not None and self._online_thread != threading.get_ident():
                raise ValueError("Ya se está instalando Pasarela BIM; espera a que termine.")
            if self._running_info() is not None:
                raise ValueError("Guarda el JSON y usa «Cerrar módulo» antes de actualizar Pasarela BIM.")
            if not package.is_file() or not 0 < package.stat().st_size <= MAX_PACKAGE_BYTES:
                raise ValueError("Selecciona un paquete ZIP de Pasarela BIM de hasta 150 MB.")
            parent = self.target.parent
            parent.mkdir(parents=True, exist_ok=True)
            if parent.is_symlink() or self.target.is_symlink():
                raise ValueError("La carpeta del módulo no puede ser un vínculo a otra ubicación.")
            stage = Path(tempfile.mkdtemp(prefix=".pasarela-stage-", dir=parent))
            backup = parent / (".pasarela-backup-" + uuid.uuid4().hex)
            replaced = False
            try:
                try:
                    with zipfile.ZipFile(package) as archive:
                        entries = archive.infolist()
                        if len(entries) > 2000 or sum(e.file_size for e in entries) > MAX_EXPANDED_BYTES:
                            raise ValueError("El paquete supera el tamaño admitido del módulo.")
                        names = set()
                        for entry in entries:
                            _archive_path(entry.filename)
                            normalized = entry.filename.rstrip("/").casefold()
                            if normalized in names:
                                raise ValueError("El paquete contiene rutas duplicadas.")
                            names.add(normalized)
                            mode = entry.external_attr >> 16
                            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)) or entry.flag_bits & 1:
                                raise ValueError("El paquete contiene vínculos o archivos no admitidos.")
                        if "module.json" not in archive.namelist() or archive.getinfo("module.json").file_size > 1024 * 1024:
                            raise ValueError("Falta el manifiesto del módulo.")
                        manifest = _read_manifest(archive.read("module.json"))
                        if expected_version is not None and manifest["version"] != expected_version:
                            raise ValueError("La versión interna del paquete no coincide con el release oficial.")
                        files = {e.filename for e in entries if not e.is_dir()}
                        if files != {"module.json", *manifest["files"]}:
                            raise ValueError("El contenido del paquete no coincide con su manifiesto.")
                        for entry in entries:
                            destination = stage.joinpath(*PurePosixPath(entry.filename).parts)
                            if entry.is_dir():
                                destination.mkdir(parents=True, exist_ok=True)
                                continue
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            with archive.open(entry) as src, destination.open("xb") as dst:
                                shutil.copyfileobj(src, dst, 1024 * 1024)
                            if entry.filename != "module.json" and _sha256(destination) != manifest["files"][entry.filename]:
                                raise ValueError("La comprobación de integridad falló. Obtén de nuevo el paquete del módulo.")
                        with (stage / ENTRYPOINT).open("rb") as executable:
                            if executable.read(2) != b"MZ":
                                raise ValueError("El paquete no incluye un ejecutable Windows válido.")
                except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
                    raise ValueError("No se pudo leer el paquete ZIP del módulo.") from exc
                if self.target.exists():
                    self.target.rename(backup)
                try:
                    stage.rename(self.target)
                    replaced = True
                except OSError:
                    if backup.exists():
                        backup.rename(self.target)
                    raise
                if backup.exists():
                    _remove_owned_directory(backup, parent)
                return self.status()
            except OSError as exc:
                raise ValueError("No se pudo instalar el módulo. Comprueba que el editor esté cerrado y que haya espacio disponible.") from exc
            finally:
                if not replaced and stage.exists():
                    _remove_owned_directory(stage, parent)

    def install_online(self):
        """Install only the module pinned by this installed core's release.

        Status never fetches a manifest. This explicit action downloads to a
        private temporary directory and verifies bytes/SHA before ZIP handling.
        """
        with self.lock:
            if self._online_thread is not None:
                raise ValueError("Ya se está instalando Pasarela BIM; espera a que termine.")
            if self._running_info() is not None:
                raise ValueError("Guarda el JSON y usa «Cerrar módulo» antes de instalar Pasarela BIM.")
            release = _release_context()
            if release is None:
                raise ValueError("No se pudo identificar el release instalado de SINCAL. Instala un paquete local compatible.")
            self._online_thread = threading.get_ident()
        try:
            manifest = io.BytesIO()
            _stream_release(release["manifest_url"],manifest,MAX_RELEASE_MANIFEST_BYTES)
            asset = _online_asset(manifest.getvalue(),release)
            downloads = self.user_dir/"pasarela-bim"/"downloads"
            downloads.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".pasarela-download-",dir=downloads) as directory:
                package = Path(directory)/asset["name"]
                with package.open("xb") as output:
                    _stream_release(asset["url"],output,MAX_PACKAGE_BYTES,
                                    expected_size=asset["bytes"],expected_hash=asset["sha256"])
                self.install(package,expected_version=asset["version"])
        except OSError:
            raise ValueError("No se pudo guardar la descarga del módulo. Comprueba que haya espacio disponible y vuelve a intentarlo.") from None
        finally:
            with self.lock:
                self._online_thread = None
        return self.status()

    def _bind_parent(self, info, parent_origin):
        try:
            result = _control_request(info, "api/host/embed", payload={"parent_origin": parent_origin})
        except (OSError, ValueError, HTTPException):
            raise ValueError("No se pudo integrar el editor con SINCAL. Actualiza Pasarela BIM o vuelve a intentarlo.") from None
        if not _embedding_supported(result) or result.get("parent_origin") != parent_origin:
            raise ValueError("El módulo no confirmó la integración con esta ventana de SINCAL.")
        return {"url": _local_url(info["url"]), "embedding": 1, "parent_origin": parent_origin,
                "message": "Editor abierto dentro de SINCAL. Sus proyectos se guardan mediante JSON."}

    def launch(self, *, open_browser=True, timeout=45, parent_origin=None):
        with self.lock:
            if parent_origin is not None:
                parent_origin = _parent_origin(parent_origin)
                open_browser = False
            if self._online_thread is not None:
                raise ValueError("Espera a que termine la instalación de Pasarela BIM antes de abrirlo.")
            running = self._running_info()
            if parent_origin is not None:
                _, _, manifest = self._discover()
                if manifest is not None and (not _embedding_supported(manifest) or running is not None and not _embedding_supported(running)):
                    raise ValueError(_embedding_update_message(running is not None))
            if running is not None:
                if parent_origin is not None:
                    if not _embedding_supported(manifest):
                        raise ValueError(_embedding_update_message(True))
                    return self._bind_parent(running, parent_origin)
                if open_browser:
                    webbrowser.open(self.url)
                return {"url": self.url, "message": "El editor de Pasarela BIM está abierto."}
            location, source, manifest = self._discover()
            if location is None:
                raise ValueError("Instala primero el módulo opcional Pasarela BIM.")
            if source == "development":
                command = [sys.executable, "-B", "-m", "pasarela_bim"]
            else:
                # Verify installed content before execution, not just when unzipping.
                for name, digest in manifest["files"].items():
                    file = location.joinpath(*PurePosixPath(name).parts)
                    if not file.is_file() or _sha256(file) != digest:
                        raise ValueError("El módulo cambió o está incompleto. Vuelve a instalar su paquete.")
                command = [str(location / ENTRYPOINT)]
            runtime = self.user_dir / "pasarela-bim" / "launches" / uuid.uuid4().hex
            runtime.mkdir(parents=True, exist_ok=False)
            info = runtime / "ready.json"
            env = dict(os.environ)
            env["PASARELA_DATA_DIR"] = str(self.user_dir / "pasarela-bim")
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            if getattr(sys, "frozen", False):
                for key in ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
                    env.pop(key, None)
            self.url = None
            try:
                with (runtime / "launcher.log").open("wb") as log, _external_dlls():
                    self.process = subprocess.Popen([*command, "--port", "0", "--sin-navegador", "--launch-info", str(info)],
                        cwd=location, stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError as exc:
                raise ValueError("No se pudo ejecutar Pasarela BIM. Vuelve a instalar su paquete compatible con Windows.") from exc
            deadline = time.monotonic() + timeout
            try:
                while time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        raise ValueError("No se pudo iniciar Pasarela BIM. Revisa su instalación.")
                    if info.is_file():
                        try:
                            ready = json.loads(info.read_text(encoding="utf-8"))
                            url = _local_url(ready.get("url", ""))
                            if not isinstance(ready.get("control_token"), str) or not 20 <= len(ready["control_token"]) <= 200:
                                raise ValueError("El módulo no permite gestionar su cierre. Actualiza su paquete.")
                            with urlopen(url.rstrip("/") + "/api/estado", timeout=2) as response:
                                status = json.load(response)
                            if status.get("version") != manifest["version"]:
                                raise ValueError("El módulo iniciado no corresponde a la versión instalada.")
                            self.url = url.rstrip("/") + "/"
                            self.ready = {**ready, "url": self.url, "version": manifest["version"],
                                          "launcher_pid": self.process.pid, "embedding": manifest.get("embedding")}
                            temporary = self.active_file.with_suffix(".tmp")
                            temporary.write_text(json.dumps(self.ready), encoding="utf-8")
                            temporary.replace(self.active_file)
                            if parent_origin is not None:
                                return self._bind_parent(self.ready, parent_origin)
                            if open_browser:
                                webbrowser.open(self.url)
                            return {"url": self.url, "message": "Editor abierto. Sus proyectos se guardan mediante JSON."}
                        except (OSError, json.JSONDecodeError):
                            pass
                    time.sleep(.1)
                raise ValueError("Pasarela BIM no terminó de iniciar. Revisa su instalación y vuelve a intentarlo.")
            except Exception:
                if self.process.poll() is None:
                    if os.name == "nt":
                        # A onefile bootloader owns a child server. Stop only
                        # this failed launch, including its own descendants.
                        subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    else:
                        self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=5)
                self.url = None
                raise

    def close(self):
        with self.lock:
            info = self._running_info()
            if info is None:
                return {"message": "El módulo ya está cerrado.", "running": False}
            try:
                result = _control_request(info, "api/cerrar", payload={})
            except OSError as exc:
                try:
                    detail = json.loads(exc.read()).get("mensaje", "")
                except (AttributeError, ValueError):
                    detail = ""
                raise ValueError(detail or "No se pudo cerrar el módulo; espera a que termine su operación y vuelve a intentarlo.") from exc
            if not result.get("ok"):
                raise ValueError("El módulo no confirmó su cierre.")
            if self.process is not None:
                try:
                    self.process.wait(timeout=8)
                except subprocess.TimeoutExpired as exc:
                    raise ValueError("El módulo aún está cerrando; espera unos segundos antes de actualizar.") from exc
            elif os.name == "nt":
                deadline = time.monotonic() + 8
                for pid in set((info.get("pid"), info.get("launcher_pid", info.get("pid")))):
                    if not _wait_windows_process(pid, deadline - time.monotonic()):
                        raise ValueError("El módulo aún está cerrando; espera unos segundos antes de actualizar.")
            else:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    try:
                        _control_request(info, "api/host-status", timeout=.5)
                    except OSError:
                        break
                    time.sleep(.1)
                else:
                    raise ValueError("El módulo aún está cerrando; espera unos segundos antes de actualizar.")
            try:
                stored = json.loads(self.active_file.read_text(encoding="utf-8"))
                if stored.get("control_token") == info["control_token"]:
                    self.active_file.unlink()
            except (OSError, ValueError):
                pass
            self.process, self.url, self.ready = None, None, None
            return {"message": "Módulo cerrado. Ya puedes actualizar su paquete.", "running": False}


_default = PasarelaModule()


def pasarela_status():
    return _default.status()


def install_pasarela_package(path):
    return _default.install(path)


def install_pasarela_online():
    return _default.install_online()


def launch_pasarela():
    return _default.launch()


def close_pasarela():
    return _default.close()
