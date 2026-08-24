"""Tema sobrio, tipografías y ayudas breves de SINCAL 2.0."""

import ctypes
import os

import customtkinter as ctk

from sincal_runtime import ruta_recurso_instalado


COLOR_FONDO = ("#F1E7D8", "#1E1E1E")
COLOR_PANEL = ("#E7DAC7", "#252526")
COLOR_PANEL_OSCURO = ("#DCCBB5", "#181818")
COLOR_BORDE = ("#B7A58D", "#303030")
COLOR_TEXTO = ("#352F29", "#D4D4D4")
COLOR_TEXTO_SUAVE = ("#71675C", "#9D9D9D")
COLOR_ACENTO = ("#8A6A1F", "#B89B4A")
COLOR_ACENTO_HOVER = ("#A47F28", "#D0B25D")
COLOR_MOSTAZA = COLOR_ACENTO
COLOR_GRIS_BOTON = ("#D2C2AD", "#333333")
COLOR_GRIS_BOTON_HOVER = ("#C2AE94", "#454545")

FAMILIA_PRESSURA = "GT Pressura"
# El archivo Bold aportado se identifica ante Windows como una familia propia,
# no como una variante de GT Pressura. Usarlo explícitamente evita que Tk
# sintetice una negrita distinta o sustituya la fuente silenciosamente.
FAMILIA_PRESSURA_BOLD = "GTPressura-Bold"
FUENTE_TITULO = (FAMILIA_PRESSURA_BOLD, 28)
FUENTE_TITULO_PEQUENO = (FAMILIA_PRESSURA_BOLD, 20)
FUENTE_SUBTITULO = (FAMILIA_PRESSURA_BOLD, 18)
FUENTE_SUBTITULO_PEQUENO = (FAMILIA_PRESSURA_BOLD, 15)
FUENTE_MENU = (FAMILIA_PRESSURA, 13)
FUENTE_NORMAL = (FAMILIA_PRESSURA, 13)
FUENTE_NORMAL_PEQUENA = (FAMILIA_PRESSURA, 11)
FUENTE_CONSOLA = ("Consolas", 11)


def registrar_fuentes() -> None:
    """Registra fuentes privadas incluidas, sin instalarlas permanentemente."""
    if os.name != "nt":
        return
    try:
        add_font = ctypes.windll.gdi32.AddFontResourceExW
    except Exception:
        return
    font_names = (
        "GT Pressura Regular.ttf", "GT Pressura Regular.otf",
        "GTPressura-Bold.ttf",
        "GT Pressura Pro Bold.ttf", "GT Pressura Pro Bold.otf",
        "GT-Pressura-Pro-Regular.ttf", "GT-Pressura-Pro-Regular.otf",
        "GT-Pressura-Pro-Bold.ttf", "GT-Pressura-Pro-Bold.otf",
        "GTPressuraPro-Regular.ttf", "GTPressuraPro-Regular.otf",
        "GTPressuraPro-Bold.ttf", "GTPressuraPro-Bold.otf",
    )
    for name in font_names:
        path = ruta_recurso_instalado("assets", "fonts", name)
        if not os.path.isfile(path):
            continue
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
        self.show_job = None
        self.hide_job = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _event=None):
        if self.window or self.show_job or not self.text:
            return
        self.show_job = self.widget.after(350, self._show_now)

    def _show_now(self):
        self.show_job = None
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
            self.window.bind("<Leave>", self.hide, add="+")
            self.hide_job = self.widget.after(3500, self.hide)
        except Exception:
            self.window = None

    def hide(self, _event=None):
        if self.show_job:
            try:
                self.widget.after_cancel(self.show_job)
            except Exception:
                pass
            self.show_job = None
        if self.hide_job:
            try:
                self.widget.after_cancel(self.hide_job)
            except Exception:
                pass
            self.hide_job = None
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
