"""Archivos de proyecto elegidos por el usuario, con guardado local seguro.

El cliente recibe un identificador opaco de sesión. Nunca puede proporcionar
una ruta para leer o escribir: esas rutas sólo salen del selector de Windows.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import secrets
import tempfile
import threading

from .proyecto import convertir_a_portable


MAX_PROJECT_BYTES = 20 * 1024 * 1024


class FileConflict(ValueError):
    """El archivo cambió fuera del editor desde su última lectura/escritura."""


class FileBusy(RuntimeError):
    """Ya hay una operación de archivo o un selector abierto."""


def _windows_dialog(*, save=False, suggested="pasarela.json"):
    """Selector Unicode nativo, sin Tk, procesos auxiliares ni consola."""
    if os.name != "nt":
        raise OSError("El guardado local requiere la aplicación de Windows.")
    import ctypes
    from ctypes import wintypes

    class OPENFILENAMEW(ctypes.Structure):
        _fields_ = [
            ("lStructSize", wintypes.DWORD), ("hwndOwner", wintypes.HWND),
            ("hInstance", wintypes.HINSTANCE), ("lpstrFilter", wintypes.LPCWSTR),
            ("lpstrCustomFilter", wintypes.LPWSTR), ("nMaxCustFilter", wintypes.DWORD),
            ("nFilterIndex", wintypes.DWORD), ("lpstrFile", wintypes.LPWSTR),
            ("nMaxFile", wintypes.DWORD), ("lpstrFileTitle", wintypes.LPWSTR),
            ("nMaxFileTitle", wintypes.DWORD), ("lpstrInitialDir", wintypes.LPCWSTR),
            ("lpstrTitle", wintypes.LPCWSTR), ("Flags", wintypes.DWORD),
            ("nFileOffset", wintypes.WORD), ("nFileExtension", wintypes.WORD),
            ("lpstrDefExt", wintypes.LPCWSTR), ("lCustData", wintypes.LPARAM),
            ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", wintypes.LPCWSTR),
            ("pvReserved", ctypes.c_void_p), ("dwReserved", wintypes.DWORD),
            ("FlagsEx", wintypes.DWORD),
        ]

    dialogs = ctypes.WinDLL("comdlg32", use_last_error=True)
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetForegroundWindow.argtypes = []
    user.GetForegroundWindow.restype = wintypes.HWND
    dialogs.CommDlgExtendedError.argtypes = []
    dialogs.CommDlgExtendedError.restype = wintypes.DWORD
    choose = dialogs.GetSaveFileNameW if save else dialogs.GetOpenFileNameW
    choose.argtypes = [ctypes.POINTER(OPENFILENAMEW)]
    choose.restype = wintypes.BOOL
    buffer = ctypes.create_unicode_buffer(32768)
    if save:
        buffer.value = suggested
    params = OPENFILENAMEW()
    params.lStructSize = ctypes.sizeof(params)
    params.hwndOwner = user.GetForegroundWindow()
    params.lpstrFilter = "Proyecto de Pasarela BIM (*.json)\0*.json\0\0"
    params.nFilterIndex = 1
    params.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    params.nMaxFile = len(buffer)
    params.lpstrDefExt = "json"
    params.lpstrTitle = "Guardar proyecto de Pasarela BIM" if save else "Abrir proyecto de Pasarela BIM"
    # EXPLORER | PATHMUSTEXIST | NOCHANGEDIR; Windows confirma los reemplazos.
    params.Flags = 0x00080000 | 0x00000800 | 0x00000008
    params.Flags |= 0x00000002 if save else 0x00001000  # OVERWRITEPROMPT / FILEMUSTEXIST
    if choose(ctypes.byref(params)):
        return Path(buffer.value)
    error = dialogs.CommDlgExtendedError()
    if error:
        raise OSError(f"No se pudo abrir el selector de archivos (código {error}).")
    return None


def _suggested_name(value):
    if value is not None and not isinstance(value, str):
        raise ValueError("El nombre sugerido debe ser un texto.")
    # Es sólo un nombre: ni directorios ni rutas del cliente llegan al selector.
    name = PureWindowsPath(value or "pasarela.json").name
    name = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in name).strip(" .")
    if name.lower().endswith(".json"):
        name = name[:-5]
    return (name[:160].strip(" .") or "pasarela") + ".json"


def _json_bytes(model):
    try:
        portable = convertir_a_portable(model)
        data = (json.dumps(portable, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
    except (TypeError, UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("El proyecto contiene datos que no se pueden guardar como JSON.") from error
    if len(data) > MAX_PROJECT_BYTES:
        raise ValueError("El proyecto supera el límite de 20 MiB.")
    return portable, data


def _reject_constant(value):
    raise ValueError(f"Valor numérico JSON no válido: {value}.")


def _digest(path):
    try:
        with path.open("rb") as source:
            result = hashlib.sha256()
            while chunk := source.read(65536):
                result.update(chunk)
            return result.hexdigest()
    except FileNotFoundError:
        return None


@dataclass(frozen=True)
class _Document:
    path: Path
    digest: str


class ProjectFiles:
    """Una instancia por servidor/sesión; selectores inyectables para pruebas."""

    def __init__(self, *, select_open=None, select_save=None):
        self.available = os.name == "nt" or (select_open is not None and select_save is not None)
        self._select_open = select_open or (lambda: _windows_dialog())
        self._select_save = select_save or (lambda name: _windows_dialog(save=True, suggested=name))
        self._documents = {}
        self._lock = threading.Lock()

    @contextmanager
    def _operation(self):
        if not self._lock.acquire(blocking=False):
            raise FileBusy("Ya hay una operación de archivo en curso. Completa el selector abierto.")
        try:
            yield
        finally:
            self._lock.release()

    @staticmethod
    def _path(selected):
        path = Path(selected).resolve()
        if path.suffix.lower() != ".json":
            raise ValueError("Selecciona un archivo de proyecto con extensión .json.")
        return path

    @staticmethod
    def _info(token, document):
        return {"id": token, "nombre": document.path.name, "ruta": str(document.path)}

    def open_project(self):
        with self._operation():
            selected = self._select_open()
            if selected is None:
                return {"cancelado": True}
            path = self._path(selected)
            with path.open("rb") as source:
                raw = source.read(MAX_PROJECT_BYTES + 1)
            if len(raw) > MAX_PROJECT_BYTES:
                raise ValueError("El proyecto supera el límite de 20 MiB.")
            try:
                model = json.loads(raw.decode("utf-8-sig"), parse_constant=_reject_constant)
                portable, _ = _json_bytes(model)
            except (UnicodeError, RecursionError) as error:
                raise ValueError("El archivo no contiene un proyecto JSON válido en UTF-8.") from error
            token = secrets.token_urlsafe(32)
            document = _Document(path, hashlib.sha256(raw).hexdigest())
            self._documents[token] = document
            return {"documento": self._info(token, document), "modelo": portable}

    def save_project(self, payload):
        with self._operation():
            if not isinstance(payload, dict):
                raise ValueError("La solicitud de guardado debe ser un objeto JSON.")
            allowed = {"modelo", "documento_id", "guardar_como", "nombre_sugerido"}
            if set(payload) - allowed:
                raise ValueError("El guardado sólo admite un modelo y el identificador del archivo elegido; no admite rutas.")
            save_as = payload.get("guardar_como", False)
            if not isinstance(save_as, bool):
                raise ValueError("guardar_como debe ser verdadero o falso.")
            token = payload.get("documento_id")
            current = None
            if token is not None:
                if not isinstance(token, str) or token not in self._documents:
                    raise ValueError("El archivo no pertenece a esta sesión. Ábrelo de nuevo o usa Guardar como.")
                current = self._documents[token]
            suggested_value = payload.get("nombre_sugerido")
            if suggested_value is not None and not isinstance(suggested_value, str):
                raise ValueError("El nombre sugerido debe ser un texto.")
            suggested = _suggested_name(suggested_value or (current.path.name if current else None))
            _, data = _json_bytes(payload.get("modelo"))
            choosing = current is None or save_as
            if choosing:
                selected = self._select_save(suggested)
                if selected is None:
                    return {"cancelado": True}
                path = self._path(selected)
                previous = _digest(path)
            else:
                path, previous = current.path, current.digest
            self._write_atomic(path, data, previous)
            if choosing:
                token = secrets.token_urlsafe(32)
            document = _Document(path, hashlib.sha256(data).hexdigest())
            self._documents[token] = document
            return {"guardado": True, "documento": self._info(token, document)}

    @staticmethod
    def _write_atomic(path, data, expected):
        def check_unchanged():
            if _digest(path) != expected:
                raise FileConflict("El archivo fue modificado o eliminado fuera del editor. Usa Guardar como para conservar tus cambios sin sobrescribirlo.")

        check_unchanged()
        temporary = None
        try:
            # El mismo directorio permite reemplazar atómicamente también en otro disco.
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".pasarela-", suffix=".tmp", dir=path.parent, delete=False) as target:
                temporary = Path(target.name)
                target.write(data)
                target.flush()
                os.fsync(target.fileno())
            check_unchanged()
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
