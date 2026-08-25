"""Tema sobrio, tipografías y ayudas breves de SINCAL 2.0."""

import ctypes
import os

import customtkinter as ctk
from ttkbootstrap import Style as BootstrapStyle
from ttkbootstrap.style import Colors, ThemeDefinition

try:
    from ttkbootstrap.themes.standard import STANDARD_THEMES
except ImportError:  # Permite mostrar un diagnóstico legible en instalaciones antiguas.
    STANDARD_THEMES = {}

from sincal.runtime import ruta_recurso_instalado


TTK_PRESET_OSCURO = "nord"
TTK_PRESET_CLARO = "sandstone"


def _preset_colors(name, fallback):
    definition = STANDARD_THEMES.get(name, {})
    return dict(fallback, **definition.get("colors", {}))


_NORD = {
    "primary": "#88C0D0", "secondary": "#81A1C1", "success": "#A3BE8C",
    "info": "#8FBCBB", "warning": "#EBCB8B", "danger": "#BF616A",
    "light": "#ECEFF4", "dark": "#2E3440", "bg": "#2E3440",
    "fg": "#ECEFF4", "selectbg": "#5E81AC", "selectfg": "#ECEFF4",
    "border": "#4C566A", "inputfg": "#E5E9F0", "inputbg": "#3B4252",
    "active": "#434C5E",
}


def crear_estilo_bootstrap():
    """Registra Nord localmente para no depender del catálogo de ttkbootstrap."""
    style = BootstrapStyle()
    if TTK_PRESET_OSCURO not in style.theme_names():
        style.register_theme(ThemeDefinition(
            name=TTK_PRESET_OSCURO,
            themetype="dark",
            colors=Colors(**_NORD),
        ))
    style.theme_use(TTK_PRESET_OSCURO)
    return style


_NORD_COLORS = _preset_colors(TTK_PRESET_OSCURO, {
    "primary": _NORD["primary"], "secondary": _NORD["secondary"],
    "bg": _NORD["bg"], "fg": _NORD["fg"], "border": _NORD["border"],
    "inputfg": _NORD["inputfg"], "inputbg": _NORD["inputbg"],
    "selectbg": _NORD["selectbg"], "active": _NORD["active"],
})
_SANDSTONE = _preset_colors(TTK_PRESET_CLARO, {
    "secondary": "#8e8c84", "fg": "#3e3f3a", "inputfg": "#6E6D69",
    "border": "#ced4da", "light": "#F8F5F0",
})

# La variante clara conserva Sandstone cálido; la oscura usa la paleta Nord.
COLOR_FONDO = ("#F8F5F0", _NORD_COLORS["bg"])
COLOR_PANEL = ("#EEE9E1", _NORD_COLORS["inputbg"])
COLOR_PANEL_OSCURO = ("#E4DDD3", _NORD_COLORS["border"])
COLOR_BORDE = (_SANDSTONE["secondary"], _NORD_COLORS["selectbg"])
COLOR_TEXTO = (_SANDSTONE["fg"], _NORD_COLORS["fg"])
COLOR_TEXTO_SUAVE = (_SANDSTONE["inputfg"], _NORD_COLORS["inputfg"])
COLOR_ACENTO = ("#B38B18", _NORD_COLORS["primary"])
COLOR_ACENTO_HOVER = ("#967412", "#8FBCBB")
COLOR_MOSTAZA = COLOR_ACENTO
COLOR_GRIS_BOTON = ("#DED7CD", _NORD_COLORS["inputbg"])
COLOR_GRIS_BOTON_HOVER = ("#D0C6B8", _NORD_COLORS["active"])
COLOR_SELECCION = ("#E7DDBE", _NORD_COLORS["selectbg"])
COLOR_EXITO = ("#477A52", _NORD["success"])
COLOR_ERROR = ("#A84842", _NORD["danger"])

RADIO_CONTROL = 6
RADIO_PANEL = 10

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
