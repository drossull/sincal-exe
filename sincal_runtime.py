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
RUTA_RECURSOS_USUARIO = os.path.join(RUTA_DATOS_USUARIO, "resources")
RUTA_CAD_USUARIO = os.path.join(
    os.getenv("APPDATA") or RUTA_DATOS_USUARIO,
    "Estandar SINCAL",
)

RECURSOS_EXACTOS = {
    "tutoriales.json",
    "masters/FORMATOS ANOTATIVOS ACAD_2025.dwg",
}
RECURSOS_POR_CARPETA = {
    "lisps/": {".lsp"},
    "startup/": {".lsp"},
    "scripts/": {".bat", ".ps1", ".scr"},
    "plotstyles/": {".ctb"},
    "mapas/": {".json", ".png"},
}


def asegurar_directorios() -> None:
    for ruta in (RUTA_DATOS_USUARIO, RUTA_RUNTIME, RUTA_LOGS, RUTA_RECURSOS_USUARIO):
        os.makedirs(ruta, exist_ok=True)


def _ruta_relativa(*partes: str) -> str:
    return "/".join(str(parte).replace("\\", "/").strip("/") for parte in partes if parte)


def es_recurso_actualizable(ruta_relativa: str) -> bool:
    ruta = ruta_relativa.replace("\\", "/").strip("/")
    if not ruta or ruta.startswith(".") or "/../" in f"/{ruta}/":
        return False
    if ruta in RECURSOS_EXACTOS:
        return True
    ruta_lower = ruta.lower()
    for prefijo, extensiones in RECURSOS_POR_CARPETA.items():
        if ruta_lower.startswith(prefijo) and os.path.splitext(ruta_lower)[1] in extensiones:
            return True
    return False


def ruta_recurso_instalado(*partes: str) -> str:
    return os.path.join(RUTA_RECURSOS, *partes)


def _estado_recursos_publicados():
    ruta_estado = os.path.join(RUTA_RECURSOS_USUARIO, "resource_sync.json")
    try:
        with open(ruta_estado, encoding="utf-8") as archivo:
            estado = json.load(archivo)
        recursos = estado.get("resources")
        return recursos if isinstance(recursos, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def ruta_recurso(*partes: str) -> str:
    if not partes:
        return RUTA_RECURSOS

    relativa = _ruta_relativa(*partes)
    instalada = ruta_recurso_instalado(*partes)
    if not es_recurso_actualizable(relativa):
        return instalada

    estado = _estado_recursos_publicados()
    if estado is None:
        return instalada

    override = os.path.join(RUTA_RECURSOS_USUARIO, *relativa.split("/"))
    if relativa not in estado:
        return override
    if os.path.isfile(override):
        return override
    return instalada


def ruta_datos(*partes: str) -> str:
    asegurar_directorios()
    return os.path.join(RUTA_DATOS_USUARIO, *partes)


def ruta_runtime(*partes: str) -> str:
    asegurar_directorios()
    return os.path.join(RUTA_RUNTIME, *partes)


def ruta_cad_usuario(*partes: str) -> str:
    os.makedirs(RUTA_CAD_USUARIO, exist_ok=True)
    return os.path.join(RUTA_CAD_USUARIO, *partes)


def leer_version() -> str:
    ruta_version = ruta_recurso_instalado("version.json")
    try:
        with open(ruta_version, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return str(datos.get("version") or VERSION_POR_DEFECTO)
    except Exception:
        return VERSION_POR_DEFECTO


VERSION_ACTUAL = leer_version()
