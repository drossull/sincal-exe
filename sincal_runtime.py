import json
import os
import sys


APP_NOMBRE = "SINCAL"
VERSION_POR_DEFECTO = "v0.0.0"


def parse_version(version: str):
    text = (version or '').strip()
    if text.lower().startswith('v'):
        text = text[1:]
    parts = text.split('.')
    numbers = []
    for part in parts:
        digits = ''.join(ch for ch in part if ch.isdigit())
        numbers.append(int(digits) if digits else 0)
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers[:3])


def is_newer_version(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def _ruta_instalacion() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _ruta_base() -> str:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return meipass
    return _ruta_instalacion()


RUTA_BASE = _ruta_base()
RUTA_INSTALACION = _ruta_instalacion()
RUTA_RECURSOS = RUTA_INSTALACION
RUTA_DATOS_USUARIO = os.path.join(
    os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or RUTA_BASE,
    APP_NOMBRE,
)
RUTA_RUNTIME = os.path.join(RUTA_DATOS_USUARIO, "runtime")
RUTA_LOGS = os.path.join(RUTA_DATOS_USUARIO, "logs")


def asegurar_directorios() -> None:
    for ruta in (RUTA_DATOS_USUARIO, RUTA_RUNTIME, RUTA_LOGS):
        os.makedirs(ruta, exist_ok=True)


def ruta_recurso(*partes: str) -> str:
    return os.path.join(RUTA_RECURSOS, *partes)


def ruta_datos(*partes: str) -> str:
    asegurar_directorios()
    return os.path.join(RUTA_DATOS_USUARIO, *partes)


def ruta_runtime(*partes: str) -> str:
    asegurar_directorios()
    return os.path.join(RUTA_RUNTIME, *partes)


def leer_version() -> str:
    ruta_version = ruta_recurso("version.json")
    try:
        with open(ruta_version, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return str(datos.get("version") or VERSION_POR_DEFECTO)
    except Exception:
        return VERSION_POR_DEFECTO


VERSION_ACTUAL = leer_version()