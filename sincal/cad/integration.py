import ctypes
import os
import winreg

from sincal.runtime import RUTA_CAD_USUARIO

REGISTRY_ROOTS = (
    r"Software\Autodesk\AutoCAD",
    r"Software\ZWSOFT\ZWCAD",
)
PROFILE_MARKER = "\\profiles\\"


def _normalized_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.expandvars(path.strip())))


def _append_path_value(key, value_name: str, directory: str) -> bool:
    try:
        current, value_type = winreg.QueryValueEx(key, value_name)
    except FileNotFoundError:
        return False
    if value_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
        return False

    segments = [segment.strip() for segment in str(current).split(";") if segment.strip()]
    wanted = _normalized_path(directory)
    if any(_normalized_path(segment) == wanted for segment in segments):
        return False
    segments.append(directory)
    winreg.SetValueEx(key, value_name, 0, value_type, ";".join(segments))
    return True


def _walk_registry(path: str, depth: int = 0):
    if depth > 8:
        return
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            path,
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        ) as key:
            yield path, key
            index = 0
            children = []
            while True:
                try:
                    children.append(winreg.EnumKey(key, index))
                    index += 1
                except OSError:
                    break
    except OSError:
        return

    for child in children:
        yield from _walk_registry(f"{path}\\{child}", depth + 1)


def registrar_ruta_cad_usuario() -> tuple[str, ...]:
    updated = []
    for root in REGISTRY_ROOTS:
        for path, key in _walk_registry(root):
            if PROFILE_MARKER not in path.lower():
                continue
            for value_name in ("ACAD", "TRUSTEDPATHS"):
                try:
                    if _append_path_value(key, value_name, RUTA_CAD_USUARIO):
                        updated.append(f"{path}::{value_name}")
                except OSError:
                    continue
    return tuple(updated)


def registrar_scripts_en_path() -> str:
    """Expone AUDIT, ZE, PURGEALL, etc. a las nuevas ventanas de CMD."""
    scripts = os.path.join(RUTA_CAD_USUARIO, "scripts")
    if not os.path.isdir(scripts):
        raise FileNotFoundError(f"No existe la carpeta de scripts materializados: {scripts}")

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
        try:
            current, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, value_type = "", winreg.REG_EXPAND_SZ
        segments = [segment.strip() for segment in str(current).split(";") if segment.strip()]
        wanted = _normalized_path(scripts)
        if not any(_normalized_path(segment) == wanted for segment in segments):
            segments.append(scripts)
            winreg.SetValueEx(key, "Path", 0, value_type, ";".join(segments))

    process_segments = [segment for segment in os.environ.get("PATH", "").split(";") if segment]
    if not any(_normalized_path(segment) == wanted for segment in process_segments):
        os.environ["PATH"] = ";".join(process_segments + [scripts])

    try:
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
    except Exception:
        pass
    return scripts
