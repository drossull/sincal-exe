"""Tema visual y tipografías privadas de SINCAL 2.0."""

import ctypes
import os

from sincal_runtime import ruta_recurso_instalado


COLOR_FONDO = "#2B2B2B"
COLOR_PANEL = "#1E1E1E"
COLOR_PANEL_OSCURO = "#171717"
COLOR_BORDE = "#4B4B4B"
COLOR_TEXTO = "#D8D8D8"
COLOR_TEXTO_SUAVE = "#9B9B9B"
COLOR_ACENTO = "#007FFF"
COLOR_ACENTO_HOVER = "#005BBF"
COLOR_MOSTAZA = "#FFBF00"
COLOR_GRIS_BOTON = "#555555"
COLOR_GRIS_BOTON_HOVER = "#6A6A6A"

FUENTE_TITULO = ("Workbench", 32)
FUENTE_TITULO_PEQUENO = ("Workbench", 22)
FUENTE_SUBTITULO = ("Passion One", 22)
FUENTE_SUBTITULO_PEQUENO = ("Passion One", 17)
FUENTE_MENU = ("Lekton", 14)
FUENTE_NORMAL = ("Lekton", 13)
FUENTE_NORMAL_PEQUENA = ("Lekton", 11)
FUENTE_CONSOLA = ("Consolas", 11)


def registrar_fuentes() -> None:
    """Registra fuentes OFL para esta sesión, sin instalarlas en Windows."""
    if os.name != "nt":
        return
    try:
        add_font = ctypes.windll.gdi32.AddFontResourceExW
    except Exception:
        return
    for filename in (
        "Workbench.ttf",
        "PassionOne-Bold.ttf",
        "Lekton-Regular.ttf",
        "Lekton-Bold.ttf",
    ):
        path = ruta_recurso_instalado("assets", "fonts", filename)
        if os.path.isfile(path):
            try:
                add_font(path, 0x10, 0)  # FR_PRIVATE: sólo visible para SINCAL.
            except Exception:
                pass
