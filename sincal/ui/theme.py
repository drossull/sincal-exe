"""Tema sobrio, tipografías y ayudas breves de SINCAL Suite."""

import ctypes
import os

import customtkinter as ctk
from ttkbootstrap import Style as BootstrapStyle
from ttkbootstrap.style import Colors, ThemeDefinition

from sincal.runtime import ruta_recurso_instalado
from sincal.ui.cadence_palettes import FAMILIES


TTK_PRESET_OSCURO = "sincal-dark"
TTK_PRESET_CLARO = "sincal-light"

# Cadence es la paleta inicial; las demás familias conservan sus colores originales.
PALETA_OSCURA = {
    "fondo": "#1E1F25", "panel": "#3B3F4A", "acento": "#FFB000",
    "texto": "#F2F5F8", "elevado": "#24262D", "muted": "#B8BCC5",
    "exito": "#77B99F", "error": "#F26D5B",
}
PALETA_CLARA = {
    "acento": "#B1482C", "activo": "#E36F4A", "suave": "#FFB38A",
    "fondo": "#F7E6D6", "texto": "#3A2F2B",
    "elevado": "#FBEEE3", "muted": "#735F56",
    "exito": "#4B7868", "error": "#A73724",
}
_CADENCE_DARK = dict(PALETA_OSCURA)
_CADENCE_LIGHT = dict(PALETA_CLARA)
THEME_LABELS = {"cadence": "Cadence", **{
    key: {"pydata": "PyData", "tokyo-night": "Tokyo Night"}.get(key, key.title())
    for key in FAMILIES}}


def mix_colors(first, second, weight):
    def channel(index):
        a, b = int(first[index:index+2], 16), int(second[index:index+2], 16)
        return f"{int(a + (b - a) * weight + .5):02x}"
    return "#" + "".join(channel(i) for i in (1, 3, 5))


def palette_for(family, dark):
    if family not in FAMILIES:
        return dict(_CADENCE_DARK if dark else _CADENCE_LIGHT)
    colors = FAMILIES[family]
    bg, fg = colors["dark" if dark else "light"]
    return {"fondo": bg, "texto": fg, "panel": mix_colors(bg, fg, .24),
            "acento": colors["primary"], "activo": colors["primary"],
            "suave": mix_colors(bg, fg, .14),
            "elevado": mix_colors(bg, fg, .075 if dark else .045),
            "muted": mix_colors(bg, fg, .68),
            "exito": colors["success"], "error": colors["danger"]}


def _bootstrap_colors(palette, dark=False):
    """Convierte una paleta SINCAL en los roles exigidos por ttkbootstrap."""
    if dark:
        return {
            "primary": palette["acento"], "secondary": palette["panel"],
            "success": palette["exito"], "info": palette["texto"],
            "warning": palette["acento"], "danger": palette["error"],
            "light": palette["texto"], "dark": palette["fondo"],
            "bg": palette["fondo"], "fg": palette["texto"],
            "selectbg": palette["panel"], "selectfg": palette["texto"],
            "border": palette["panel"], "inputfg": palette["texto"],
            "inputbg": palette["fondo"], "active": palette["elevado"],
        }
    return {
        "primary": palette["acento"], "secondary": palette["suave"],
        "success": palette["exito"], "info": palette["activo"],
        "warning": palette["activo"], "danger": palette["error"],
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


def aplicar_familia(style, family, dark):
    """Actualiza referencias compartidas para controles abiertos y futuros."""
    family = family if family in THEME_LABELS else "cadence"
    PALETA_CLARA.clear()
    PALETA_CLARA.update(palette_for(family, False))
    PALETA_OSCURA.clear()
    PALETA_OSCURA.update(palette_for(family, True))
    for role, colors in _COLOR_ROLES:
        colors[:] = [PALETA_CLARA[role], PALETA_OSCURA[role]]
    COLOR_GRIS_BOTON[:] = [PALETA_CLARA["suave"], PALETA_OSCURA["panel"]]
    COLOR_BORDE[:] = [PALETA_CLARA["activo"], PALETA_OSCURA["panel"]]
    COLOR_ACENTO_HOVER[:] = [PALETA_CLARA["activo"], PALETA_OSCURA["acento"]]
    # Los controles que no declaran colores también siguen la paleta actual.
    defaults = ctk.ThemeManager.theme
    defaults["CTkFont"].update(family=FAMILIA_CUERPO, size=14, weight="normal")
    for widget, options in {
        "CTkFrame": {"fg_color": COLOR_FONDO, "top_fg_color": COLOR_FONDO, "border_color": COLOR_BORDE},
        "CTkLabel": {"text_color": COLOR_TEXTO},
        "CTkButton": {"fg_color": COLOR_GRIS_BOTON, "hover_color": COLOR_ACENTO_HOVER, "text_color": COLOR_TEXTO},
        "CTkEntry": {"fg_color": COLOR_FONDO, "border_color": COLOR_BORDE, "text_color": COLOR_TEXTO},
        "CTkTextbox": {"fg_color": COLOR_FONDO, "text_color": COLOR_TEXTO},
        "CTkCheckBox": {"fg_color": COLOR_ACENTO, "hover_color": COLOR_ACENTO_HOVER, "text_color": COLOR_TEXTO},
        "CTkSwitch": {"progress_color": COLOR_ACENTO, "text_color": COLOR_TEXTO},
        "CTkOptionMenu": {"fg_color": COLOR_GRIS_BOTON, "button_color": COLOR_GRIS_BOTON, "text_color": COLOR_TEXTO},
        "CTkScrollableFrame": {"label_fg_color": COLOR_FONDO},
    }.items():
        defaults.get(widget, {}).update(options)
    name = f"sincal-{family}-{'dark' if dark else 'light'}"
    if name not in style.theme_names():
        style.register_theme(ThemeDefinition(name=name, themetype="dark" if dark else "light",
            colors=Colors(**_bootstrap_colors(PALETA_OSCURA if dark else PALETA_CLARA, dark))))
    style.theme_use(name)
    armonizar_estilos_ttk(style, dark)
    return family


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
    style.configure("TButton", font=(FAMILIA_BOTONES, -14))
    style.configure("TSpinbox", font=FUENTE_TTK_CAMPO)
    for prefix in ("", "primary.", "secondary."):
        style.configure(
            f"{prefix}TLabelframe", background=background,
            bordercolor=panel, lightcolor=panel, darkcolor=panel)
        style.configure(
            f"{prefix}TLabelframe.Label", background=background,
            foreground=foreground, font=FUENTE_TTK_NORMAL)
        style.configure(f"{prefix}TNotebook", background=background, borderwidth=0)
        style.configure(
            f"{prefix}TNotebook.Tab", background=background,
            foreground=foreground, font=FUENTE_TTK_NORMAL, padding=(10, 6))
        style.map(
            f"{prefix}TNotebook.Tab",
            background=[("selected", background), ("active", palette["elevado"])],
            foreground=[("selected", accent), ("active", foreground)])
    # Tableview crea estilos prefijados según bootstyle. Un tamaño negativo
    # expresa píxeles en Tk y evita que Windows vuelva a escalarlo como puntos.
    for prefix in ("", "primary.", "secondary.", "info.", "warning."):
        style.configure(
            f"{prefix}Table.Treeview", font=FUENTE_TTK_TABLA,
            rowheight=28, borderwidth=0,
            background=background, fieldbackground=background, foreground=foreground)
        style.configure(
            f"{prefix}Table.Treeview.Heading",
            font=FUENTE_TTK_TABLA_ENCABEZADO, padding=(8, 7),
            background=palette["elevado"], foreground=foreground)


COLOR_FONDO = [PALETA_CLARA["fondo"], PALETA_OSCURA["fondo"]]
COLOR_PANEL = COLOR_FONDO
COLOR_PANEL_OSCURO = COLOR_FONDO
COLOR_BORDE = [PALETA_CLARA["activo"], PALETA_OSCURA["panel"]]
COLOR_TEXTO = [PALETA_CLARA["texto"], PALETA_OSCURA["texto"]]
COLOR_TEXTO_SUAVE = [PALETA_CLARA["muted"], PALETA_OSCURA["muted"]]
COLOR_ACENTO = [PALETA_CLARA["acento"], PALETA_OSCURA["acento"]]
COLOR_ACENTO_HOVER = [PALETA_CLARA["activo"], PALETA_OSCURA["acento"]]
COLOR_MOSTAZA = COLOR_ACENTO
COLOR_GRIS_BOTON = [PALETA_CLARA["suave"], PALETA_OSCURA["panel"]]
COLOR_GRIS_BOTON_HOVER = COLOR_ACENTO_HOVER
COLOR_MARCO_BOTON = ("#000000", "#000000")
COLOR_SELECCION = COLOR_GRIS_BOTON
COLOR_EXITO = [PALETA_CLARA["exito"], PALETA_OSCURA["exito"]]
COLOR_ERROR = [PALETA_CLARA["error"], PALETA_OSCURA["error"]]
_COLOR_ROLES = [("fondo", COLOR_FONDO), ("texto", COLOR_TEXTO),
                ("muted", COLOR_TEXTO_SUAVE), ("acento", COLOR_ACENTO),
                ("exito", COLOR_EXITO), ("error", COLOR_ERROR)]

RADIO_CONTROL = 0
RADIO_PANEL = 0

FAMILIA_PRESSURA = "GT Pressura"
FAMILIA_CUERPO = "Roboto"
FAMILIA_TITULOS = "Roboto Condensed"
FAMILIA_BOTONES = "Roboto Flex"
FAMILIA_NUMEROS = "Roboto Mono"
# Pressura se conserva para la animación; roles tipográficos como Cadence.
FAMILIA_PRESSURA_BOLD = "GTPressura-Bold"
FUENTE_TITULO = (FAMILIA_TITULOS, 28, "bold")
FUENTE_TITULO_PEQUENO = (FAMILIA_TITULOS, 22, "bold")
FUENTE_SUBTITULO = (FAMILIA_TITULOS, 18, "bold")
FUENTE_SUBTITULO_PEQUENO = (FAMILIA_TITULOS, 15, "bold")
FUENTE_MENU = (FAMILIA_CUERPO, 14)
FUENTE_NORMAL = (FAMILIA_CUERPO, 14)
FUENTE_NORMAL_PEQUENA = FUENTE_NORMAL
FUENTE_CARGA = (FAMILIA_PRESSURA, 13)
FUENTE_CAMPO = (FAMILIA_CUERPO, 14)
FUENTE_CONSOLA = (FAMILIA_NUMEROS, 14)
FUENTE_BOTON = (FAMILIA_BOTONES, 14)
# ttk/Tk interpreta los tamaños positivos como puntos; CustomTkinter los trata
# como píxeles escalados. Estas variantes negativas unifican su altura visual.
FUENTE_TTK_NORMAL = (FAMILIA_CUERPO, -14)
FUENTE_TTK_CAMPO = (FAMILIA_NUMEROS, -14)
FUENTE_TTK_TABLA = (FAMILIA_CUERPO, -14)
FUENTE_TTK_TABLA_ENCABEZADO = (FAMILIA_CUERPO, -14, "bold")


def sincronizar_tipografia(root, style, scale=1.0):
    """Tk/ttk usan píxeles reales; CTk ya aplica el DPI y zoom al dibujar."""
    import tkinter as tk
    from tkinter import font as tkfont, ttk
    size = -round(14 * scale)
    style.configure(".", font=(FAMILIA_CUERPO, size))
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name, root=root).configure(family=FAMILIA_CUERPO, size=size)
    for name in style._style_registry:
        # Sólo estilos tipográficos; conserva símbolos y fuentes de iconos.
        if any(part in name for part in ("TLabel", "TButton", "TEntry", "TCombobox", "TSpinbox", "TNotebook.Tab", "Treeview", "TLabelframe.Label", "TCheckbutton", "TRadiobutton")) and not name.startswith("symbol."):
            family = FAMILIA_BOTONES if "TButton" in name else FAMILIA_CUERPO
            style.configure(name, font=(family, size, "bold" if name.endswith("Heading") else "normal"))
            if "Treeview" in name and not name.endswith("Heading"):
                style.configure(name, rowheight=round(30 * scale))
    def visit(widget):
        if isinstance(widget, ttk.Widget):
            try:
                current = widget.cget("font")
                if current:
                    actual = tkfont.Font(root=root, font=current).actual()
                    if actual["family"] in (FAMILIA_CUERPO, FAMILIA_NUMEROS, FAMILIA_BOTONES):
                        widget.configure(font=(actual["family"], size, actual["weight"]))
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            visit(child)
    visit(root)
    root.option_add("*TCombobox*Listbox.font", (FAMILIA_CUERPO, size))


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
    # Windows puede asociar erróneamente la variante Italic como estilo base
    # cuando todas las subfamilias Helvetica Neue se registran a la vez. Las
    # variantes TTF incorporan hinting TrueType y una tabla GASP explícita para
    # que Tk/GDI use ClearType también en los cuerpos pequeños de la interfaz.
    font_names = (
        "GT Pressura Regular.ttf",
        "GTPressura-Bold.ttf",
        "HelveticaNeueRoman.ttf",
        "HelveticaNeueBold.ttf",
        "roboto-400.ttf",
        "roboto-700.ttf",
        "roboto-condensed-700.ttf",
        "roboto-flex-400.ttf",
        "roboto-mono-400.ttf",
        "roboto-mono-700.ttf",
    )
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
