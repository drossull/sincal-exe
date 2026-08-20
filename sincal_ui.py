"""Tema sobrio, tipografías y ayudas breves de SINCAL 2.0."""

import ctypes
import os

import customtkinter as ctk

from sincal_runtime import ruta_recurso_instalado


COLOR_FONDO = "#1E1E1E"
COLOR_PANEL = "#252526"
COLOR_PANEL_OSCURO = "#181818"
COLOR_BORDE = "#303030"
COLOR_TEXTO = "#D4D4D4"
COLOR_TEXTO_SUAVE = "#9D9D9D"
COLOR_ACENTO = "#B89B4A"
COLOR_ACENTO_HOVER = "#D0B25D"
COLOR_MOSTAZA = COLOR_ACENTO
COLOR_GRIS_BOTON = "#333333"
COLOR_GRIS_BOTON_HOVER = "#454545"

FUENTE_TITULO = ("Consolas", 28, "bold")
FUENTE_TITULO_PEQUENO = ("Consolas", 20, "bold")
FUENTE_SUBTITULO = ("Consolas", 18, "bold")
FUENTE_SUBTITULO_PEQUENO = ("Consolas", 15, "bold")
FUENTE_MENU = ("Roboto Mono", 13)
FUENTE_NORMAL = ("Roboto Mono", 13)
FUENTE_NORMAL_PEQUENA = ("Roboto Mono", 11)
FUENTE_CONSOLA = ("Consolas", 11)


def registrar_fuentes() -> None:
    """Registra Roboto Mono para la sesión actual, sin instalarla en Windows."""
    if os.name != "nt":
        return
    try:
        add_font = ctypes.windll.gdi32.AddFontResourceExW
    except Exception:
        return
    path = ruta_recurso_instalado("assets", "fonts", "RobotoMono.ttf")
    if os.path.isfile(path):
        try:
            add_font(path, 0x10, 0)  # FR_PRIVATE: sólo visible para SINCAL.
        except Exception:
            pass


class Tooltip:
    """Ayuda contextual ligera para botones que se muestran sólo como iconos."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _event=None):
        if self.window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self.window = ctk.CTkToplevel(self.widget)
            self.window.overrideredirect(True)
            self.window.attributes("-topmost", True)
            self.window.geometry(f"+{x}+{y}")
            ctk.CTkLabel(
                self.window, text=self.text, font=FUENTE_NORMAL_PEQUENA,
                fg_color=COLOR_PANEL_OSCURO, text_color=COLOR_TEXTO,
                corner_radius=4,
            ).pack(padx=7, pady=4)
        except Exception:
            self.window = None

    def hide(self, _event=None):
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None


def agregar_tooltip(widget, text: str):
    """Conserva la referencia del tooltip mientras el control esté vivo."""
    widget._sincal_tooltip = Tooltip(widget, text)
    return widget
