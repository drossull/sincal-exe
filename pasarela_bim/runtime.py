"""Rutas de lectura, datos de usuario y procesos externos del módulo opcional.

No importa SINCAL ni crea carpetas durante el import. El motor FreeCAD utiliza
fuentes Python reales incluidas como datos, nunca el ejecutable congelado.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import sys
import threading


_DLL_LOCK = threading.Lock()


def congelado():
    return bool(getattr(sys,"frozen",False))


def raiz_recursos():
    """Paquete de recursos estáticos, sólo lectura, en fuente o PyInstaller."""
    if congelado():
        base = Path(getattr(sys,"_MEIPASS",Path(sys.executable).resolve().parent))
        return base / "pasarela_bim"
    return Path(__file__).resolve().parent


def raiz_codigo_motor():
    """Directorio padre del paquete importable por el Python de FreeCAD."""
    if congelado():
        base = Path(getattr(sys,"_MEIPASS",Path(sys.executable).resolve().parent)) / "runtime"
    else:
        base = Path(__file__).resolve().parent.parent
    requeridos = ("__init__.py","worker.py","freecad_backend.py","topologia.py","proyecto.py","ejes.py")
    if not all((base/"pasarela_bim"/nombre).is_file() for nombre in requeridos):
        raise RuntimeError("La instalación no contiene las fuentes del motor FreeCAD; reinstala el módulo Pasarela BIM.")
    return base.resolve()


def raiz_datos():
    """Datos escribibles; PASARELA_DATA_DIR reemplaza la raíz del módulo."""
    configurada = os.environ.get("PASARELA_DATA_DIR")
    if configurada:
        return Path(configurada).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home()/"AppData"/"Local"
    else:
        base = Path(os.environ["XDG_DATA_HOME"]) if os.environ.get("XDG_DATA_HOME") else Path.home()/".local"/"share"
    return (base/"SINCAL"/"pasarela-bim").resolve()


def carpeta_generados():
    return raiz_datos()/"generados"


def entorno_externo():
    """Evita que un motor instalado cargue bibliotecas del bundle PyInstaller."""
    entorno = os.environ.copy()
    if not congelado():
        return entorno
    for clave in ("PYTHONHOME","PYTHONPATH","QT_PLUGIN_PATH","QT_QPA_PLATFORM_PLUGIN_PATH","QML2_IMPORT_PATH"):
        entorno.pop(clave,None)
    for clave in ("LD_LIBRARY_PATH","LIBPATH"):
        original = entorno.get(clave+"_ORIG")
        if original is None:
            entorno.pop(clave,None)
        else:
            entorno[clave] = original
    bundle = getattr(sys,"_MEIPASS",None)
    if bundle:
        base = os.path.normcase(os.path.abspath(bundle))
        rutas = []
        for ruta in entorno.get("PATH","").split(os.pathsep):
            normal = os.path.normcase(os.path.abspath(ruta.strip('"'))) if ruta else ""
            if normal != base and not normal.startswith(base+os.sep):
                rutas.append(ruta)
        entorno["PATH"] = os.pathsep.join(rutas)
    return entorno


@contextmanager
def bibliotecas_sistema():
    """Restablece temporalmente la búsqueda de DLL sólo durante el spawn.

    FreeCAD/CoreConsole son programas externos, con sus propias bibliotecas.
    La ruta de DLL del proceso principal se restaura incluso si Popen falla.
    """
    if os.name != "nt" or not congelado():
        yield
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.GetDllDirectoryW.argtypes = (wintypes.DWORD,wintypes.LPWSTR)
    kernel.GetDllDirectoryW.restype = wintypes.DWORD
    kernel.SetDllDirectoryW.argtypes = (wintypes.LPCWSTR,)
    kernel.SetDllDirectoryW.restype = wintypes.BOOL
    with _DLL_LOCK:
        largo = kernel.GetDllDirectoryW(0,None)
        buffer = ctypes.create_unicode_buffer(largo+1)
        kernel.GetDllDirectoryW(len(buffer),buffer)
        anterior = buffer.value or None
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield
        finally:
            if not kernel.SetDllDirectoryW(anterior):
                raise ctypes.WinError(ctypes.get_last_error())
