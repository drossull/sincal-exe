"""Tema sobrio, tipografías y ayudas breves de SINCAL Suite."""

import ctypes
import os

import customtkinter as ctk
from ttkbootstrap import Style as BootstrapStyle
from ttkbootstrap.style import Colors, ThemeDefinition

from sincal.runtime import ruta_recurso_instalado


TTK_PRESET_OSCURO = "sincal-dark"
TTK_PRESET_CLARO = "sincal-light"

# Paletas corporativas cerradas. No se introducen fondos negros ni blancos puros.
PALETA_OSCURA = {
    "fondo": "#1E1F25", "panel": "#3B3F4A", "acento": "#FFB000",
    "texto": "#F2F5F8",
}
PALETA_CLARA = {
    "acento": "#B1482C", "activo": "#E36F4A", "suave": "#FFB38A",
    "fondo": "#F7E6D6", "texto": "#3A2F2B",
}


def _bootstrap_colors(palette, dark=False):
    """Convierte una paleta SINCAL en los roles exigidos por ttkbootstrap."""
    if dark:
        return {
            "primary": palette["acento"], "secondary": palette["panel"],
            "success": palette["acento"], "info": palette["texto"],
            "warning": palette["acento"], "danger": palette["acento"],
            "light": palette["texto"], "dark": palette["fondo"],
            "bg": palette["fondo"], "fg": palette["texto"],
            "selectbg": palette["panel"], "selectfg": palette["texto"],
            "border": palette["panel"], "inputfg": palette["texto"],
            "inputbg": palette["panel"], "active": palette["panel"],
        }
    return {
        "primary": palette["acento"], "secondary": palette["suave"],
        "success": palette["acento"], "info": palette["activo"],
        "warning": palette["activo"], "danger": palette["acento"],
        "light": palette["fondo"], "dark": palette["texto"],
        "bg": palette["fondo"], "fg": palette["texto"],
        "selectbg": palette["suave"], "selectfg": palette["texto"],
        "border": palette["activo"], "inputfg": palette["texto"],
        "inputbg": palette["fondo"], "active": palette["suave"],
    }


def crear_estilo_bootstrap():
    """Registra únicamente los temas corporativos oscuro y claro."""
    style = BootstrapStyle()
    definitions = (
        (TTK_PRESET_OSCURO, "dark", _bootstrap_colors(PALETA_OSCURA, dark=True)),
        (TTK_PRESET_CLARO, "light", _bootstrap_colors(PALETA_CLARA)),
    )
    for name, theme_type, colors in definitions:
        if name not in style.theme_names():
            style.register_theme(ThemeDefinition(
                name=name, themetype=theme_type, colors=Colors(**colors)))
    style.theme_use(TTK_PRESET_OSCURO)
    armonizar_estilos_ttk(style, dark=True)
    return style


def armonizar_estilos_ttk(style, dark=True):
    """Evita marcos ajenos a la paleta en Notebook, PanedWindow y LabelFrame."""
    palette = PALETA_OSCURA if dark else PALETA_CLARA
    background = palette["fondo"]
    panel = palette.get("panel", palette.get("suave"))
    accent = palette["acento"]
    foreground = palette["texto"]
    style.configure(
        ".", background=background, foreground=foreground,
        font=FUENTE_TTK_NORMAL, fieldbackground=background)
    style.configure("TFrame", background=background)
    style.configure("TPanedwindow", background=background)
    style.configure(
        "SincalLabelframeTitle.TLabel",
        background=background,
        foreground=foreground,
        font=FUENTE_TTK_NORMAL,
        bordercolor=panel,
        borderwidth=1,
        relief="solid",
        padding=(7, 3),
    )
    for widget_style in (
        "TLabel", "TEntry", "TCombobox", "TSpinbox", "TButton",
        "TRadiobutton", "TCheckbutton", "symbol.Link.TButton",
    ):
        style.configure(widget_style, font=FUENTE_TTK_NORMAL)
    for prefix in ("", "primary.", "secondary."):
        style.configure(
            f"{prefix}TLabelframe", background=background,
            bordercolor=panel, lightcolor=panel, darkcolor=panel)
        style.configure(
            f"{prefix}TLabelframe.Label", background=background,
            foreground=foreground, font=FUENTE_TTK_NORMAL)
        style.configure(f"{prefix}TNotebook", background=background, borderwidth=0)
        style.configure(
            f"{prefix}TNotebook.Tab", background=panel,
            foreground=foreground, font=FUENTE_TTK_NORMAL, padding=(10, 6))
        style.map(
            f"{prefix}TNotebook.Tab",
            background=[("selected", accent), ("active", panel)],
            foreground=[("selected", background), ("active", foreground)])
    # Tableview crea estilos prefijados según bootstyle. Un tamaño negativo
    # expresa píxeles en Tk y evita que Windows vuelva a escalarlo como puntos.
    for prefix in ("", "primary.", "secondary.", "info.", "warning."):
        style.configure(
            f"{prefix}Table.Treeview", font=FUENTE_TTK_TABLA,
            rowheight=23, borderwidth=0)
        style.configure(
            f"{prefix}Table.Treeview.Heading",
            font=FUENTE_TTK_TABLA_ENCABEZADO, padding=(5, 4))


COLOR_FONDO = (PALETA_CLARA["fondo"], PALETA_OSCURA["fondo"])
COLOR_PANEL = COLOR_FONDO
COLOR_PANEL_OSCURO = COLOR_FONDO
COLOR_BORDE = (PALETA_CLARA["activo"], PALETA_OSCURA["panel"])
COLOR_TEXTO = (PALETA_CLARA["texto"], PALETA_OSCURA["texto"])
COLOR_TEXTO_SUAVE = (PALETA_CLARA["texto"], PALETA_OSCURA["texto"])
COLOR_ACENTO = (PALETA_CLARA["acento"], PALETA_OSCURA["acento"])
COLOR_ACENTO_HOVER = (PALETA_CLARA["activo"], PALETA_OSCURA["acento"])
COLOR_MOSTAZA = COLOR_ACENTO
COLOR_GRIS_BOTON = (PALETA_CLARA["suave"], PALETA_OSCURA["panel"])
COLOR_GRIS_BOTON_HOVER = (PALETA_CLARA["activo"], PALETA_OSCURA["acento"])
COLOR_SELECCION = (PALETA_CLARA["suave"], PALETA_OSCURA["panel"])
COLOR_EXITO = COLOR_ACENTO
COLOR_ERROR = COLOR_ACENTO

RADIO_CONTROL = 6
RADIO_PANEL = 10

FAMILIA_PRESSURA = "GT Pressura"
FAMILIA_CUERPO = "Helvetica Neue"
# Se conserva el nombre para diagnosticar el archivo distribuido, pero toda la
# interfaz usa una sola familia. Así números y letras comparten métricas.
FAMILIA_PRESSURA_BOLD = "GTPressura-Bold"
FUENTE_TITULO = (FAMILIA_PRESSURA, 28, "bold")
FUENTE_TITULO_PEQUENO = (FAMILIA_PRESSURA, 20, "bold")
FUENTE_SUBTITULO = (FAMILIA_PRESSURA, 18, "bold")
FUENTE_SUBTITULO_PEQUENO = (FAMILIA_PRESSURA, 15, "bold")
FUENTE_MENU = (FAMILIA_CUERPO, 13)
FUENTE_NORMAL = (FAMILIA_CUERPO, 13)
FUENTE_NORMAL_PEQUENA = FUENTE_NORMAL
FUENTE_CAMPO = (FAMILIA_CUERPO, 13)
FUENTE_CONSOLA = ("Consolas", 13)
# ttk/Tk interpreta los tamaños positivos como puntos; CustomTkinter los trata
# como píxeles escalados. Estas variantes negativas unifican su altura visual.
FUENTE_TTK_NORMAL = (FAMILIA_CUERPO, -13)
FUENTE_TTK_CAMPO = (FAMILIA_CUERPO, -13)
FUENTE_TTK_TABLA = (FAMILIA_CUERPO, -12)
FUENTE_TTK_TABLA_ENCABEZADO = (FAMILIA_CUERPO, -12, "bold")


_FUENTES_REGISTRADAS = False


def registrar_fuentes() -> None:
    """Registra la familia tipográfica incluida sin instalarla en Windows."""
    global _FUENTES_REGISTRADAS
    if _FUENTES_REGISTRADAS:
        return
    if os.name != "nt":
        return
    try:
        add_font = ctypes.windll.gdi32.AddFontResourceExW
    except Exception:
        return
    _FUENTES_REGISTRADAS = True
    font_dir = ruta_recurso_instalado("assets", "fonts")
    try:
        font_names = sorted(
            name for name in os.listdir(font_dir)
            if os.path.splitext(name)[1].lower() in (".ttf", ".otf")
        )
    except OSError:
        return
    for name in font_names:
        path = os.path.join(font_dir, name)
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
