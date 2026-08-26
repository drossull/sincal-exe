"""Configuración de pantalla aplicada antes de crear la raíz de Tk."""

import ctypes
import os


_DPI_CONFIGURADO = False


def configurar_dpi_windows() -> str:
    """Activa escalado nítido por monitor sin fallar fuera de Windows."""
    global _DPI_CONFIGURADO
    if _DPI_CONFIGURADO:
        return "configurado"
    if os.name != "nt":
        return "no-windows"

    _DPI_CONFIGURADO = True
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return "per-monitor"
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return "system"
    except Exception:
        return "sin-cambios"
