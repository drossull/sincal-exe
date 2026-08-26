import ctypes
import json
import logging
import os

from sincal.ui.display import configurar_dpi_windows

# Debe ejecutarse antes de importar Tk/CustomTkinter para evitar rasterizado
# borroso cuando Windows usa escalado por monitor.
configurar_dpi_windows()

import queue
import shutil
import subprocess
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from datetime import datetime
from logging.handlers import RotatingFileHandler
from tkinter import messagebox

import customtkinter as ctk
import pythoncom
import requests
import ttkbootstrap as ttk
import win32com.client
from customtkinter import filedialog
from PIL import Image, ImageTk

from sincal.ui.tabs.armaduras import TabArmaduras
from sincal.ui.tabs.diagnostico import TabDiagnostico
from sincal.ui.tabs.documentacion import TabDocs
from sincal.ui.tabs.ubicacion import TabUbicacion
from sincal.cad.engine import ensure_cad_engine
from sincal.cad.integration import registrar_ruta_cad_usuario, registrar_scripts_en_path
from sincal.diagnostics import record_incident
from sincal.resources import (
    active_resource_paths,
    apply_resource_updates,
    check_resource_updates,
    distribution_manifest_revision,
    materialize_cad_resources,
    record_resource_state,
)
from sincal.runtime import (
    RUTA_DATOS_USUARIO,
    RUTA_LOGS,
    VERSION_ACTUAL,
    asegurar_directorios,
    is_newer_version,
    ruta_cad_usuario,
)
from sincal.ui.icons import obtener_icono
from sincal.runtime import (
    ruta_recurso as runtime_ruta_recurso,
)
from sincal.update_config import (
    DISTRIBUTION_RELEASES_URL,
    api_url as distribution_api_url,
)
from sincal.ui.theme import (
    COLOR_ACENTO,
    COLOR_ACENTO_HOVER,
    COLOR_BORDE,
    COLOR_FONDO,
    COLOR_GRIS_BOTON,
    COLOR_GRIS_BOTON_HOVER,
    COLOR_MOSTAZA,
    COLOR_PANEL,
    COLOR_PANEL_OSCURO,
    COLOR_SELECCION,
    COLOR_TEXTO,
    COLOR_TEXTO_SUAVE,
    FUENTE_CONSOLA,
    FUENTE_CAMPO,
    FUENTE_MENU,
    FUENTE_NORMAL,
    FUENTE_NORMAL_PEQUENA,
    FUENTE_SUBTITULO,
    FUENTE_SUBTITULO_PEQUENO,
    FUENTE_TITULO,
    FUENTE_TITULO_PEQUENO,
    PALETA_CLARA,
    PALETA_OSCURA,
    RADIO_CONTROL,
    RADIO_PANEL,
    TTK_PRESET_CLARO,
    TTK_PRESET_OSCURO,
    armonizar_estilos_ttk,
    crear_estilo_bootstrap,
    agregar_tooltip,
    registrar_fuentes,
)

# --- CONFIGURACIÓN GLOBALES ---
URL_RELEASES = DISTRIBUTION_RELEASES_URL
RESOURCE_POLL_INTERVAL_MS = 60 * 1000

COLOR_TITULO = COLOR_MOSTAZA

ctk.set_appearance_mode("dark")


def obtener_ruta_recurso(ruta_relativa):
    return runtime_ruta_recurso(ruta_relativa)


def configurar_logging():
    asegurar_directorios()
    logger = logging.getLogger("sincal")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        os.path.join(RUTA_LOGS, "sincal.log"),
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


class ActualizadorCAD(ctk.CTk):
    def __init__(self):
        if os.name == "nt":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "SINCAL.Workbench.2")
            except Exception:
                pass
        registrar_fuentes()
        super().__init__()
        self.bootstrap_style = crear_estilo_bootstrap()
        asegurar_directorios()
        self.logger = configurar_logging()
        self.historial_logs = []
        self._cerrando = False
        self._ui_queue = queue.Queue()
        self.title("SINCAL Suite — Workbench")
        self.geometry("1280x820")
        self.minsize(980, 640)
        self.configure(fg_color=COLOR_FONDO)
        icon_path = obtener_ruta_recurso("assets/icons/logo.ico")
        try:
            with Image.open(icon_path) as icon_source:
                icon_image = icon_source.convert("RGBA")
                icon_image.thumbnail((56, 56), Image.Resampling.LANCZOS)
                icon_canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                icon_canvas.paste(
                    icon_image,
                    ((64 - icon_image.width) // 2, (64 - icon_image.height) // 2),
                    icon_image,
                )
                self._window_icon = ImageTk.PhotoImage(icon_canvas)
                alpha = icon_canvas.getchannel("A")
                logo_light = Image.new("RGBA", icon_canvas.size, PALETA_CLARA["texto"])
                logo_dark = Image.new("RGBA", icon_canvas.size, PALETA_OSCURA["texto"])
                logo_light.putalpha(alpha)
                logo_dark.putalpha(alpha)
                self._brand_logo = ctk.CTkImage(
                    light_image=logo_light, dark_image=logo_dark, size=(30, 30))
            self.iconphoto(True, self._window_icon)
        except Exception:
            pass
        try:
            self.iconbitmap(icon_path)
        except Exception:
            pass

        self.version_local_actual = VERSION_ACTUAL
        self.tutoriales, self.cad_exe_path, self.es_zwcad, self.cancelar_comando_vivo = {
        }, None, False, False
        self.ruta_renombre, self.checkboxes_archivos = "", []
        self._resource_check_running = False
        self._last_resource_offer_tree = ""
        self._resource_manifest_revision = ""
        self._resource_poll_job = None
        self._sidebar_width = 270
        self._sidebar_animation_job = None
        self._sidebar_auto_hidden = False
        self._sidebar_user_hidden = False
        self._font_scale = 1.0
        self._zoom_target = 1.0
        self._zoom_buttons = {}
        self._console_mode = "Oculta"
        self._sections = {}
        self._nav_buttons = {}
        self._nav_indicators = {}
        self._page_nav_buttons = {}
        self._page_anchors = {}
        self.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        self.after(50, self._procesar_ui_queue)
        self.bind("<Configure>", self._adaptar_layout_principal, add="+")

        self._construir_shell()
        self._crear_secciones()
        self._construir_menu_superior()
        self.setup_tab_sincronizador()
        self.setup_tab_comandos()
        self.setup_tab_renombrado()
        self.setup_tab_conversion_dxf()
        self.setup_tab_armaduras()
        self.vista_docs = TabDocs(
            self.tab_docs, parent_app=self, fg_color="transparent")
        self.vista_docs.pack(fill="both", expand=True)
        self.seleccionar_seccion("sincronizador")

        threading.Thread(target=self.cargar_info_github, daemon=True).start()

    def _construir_shell(self):
        self.sidebar = ctk.CTkFrame(
            self, width=self._sidebar_width, fg_color=COLOR_PANEL_OSCURO,
            corner_radius=0,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=14, pady=(18, 4))
        if getattr(self, "_brand_logo", None) is not None:
            ctk.CTkLabel(
                brand, text="", image=self._brand_logo, width=30,
                fg_color="transparent",
            ).pack(side="left", padx=(0, 8))
        self.brand_title = ctk.CTkLabel(
            brand, text="SINCAL SUITE", font=FUENTE_TITULO_PEQUENO,
            text_color=COLOR_TEXTO,
        )
        self.brand_title.pack(side="left", anchor="w")
        self.brand_subtitle = ctk.CTkLabel(
            self.sidebar, text="WORKBENCH DE INGENIERÍA", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.brand_subtitle.pack(anchor="w", padx=16, pady=(0, 18))

        self.nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_container.pack(fill="both", expand=True, padx=8)
        self.nav_items = (
            ("sincronizador", "home", "Home", "Home"),
            ("documentacion", "book", "Documentación", "Documentación"),
            ("comandos", "terminal", "Comandos en vivo", "Comandos en vivo"),
            ("conversion", "convert", "Conversión DXF–DWG", "Conversión DXF–DWG"),
            ("procesamiento", "rename", "Renombrado", "Renombrado"),
            ("ubicacion", "pin", "Ubicación", "Ubicación"),
            ("estructural", "structure", "Generador de armadura", "Generador de armadura"),
            ("diagnostico", "diagnostic", "Diagnóstico", "Diagnóstico"),
        )
        for key, icon_name, label, title in self.nav_items:
            row = ctk.CTkFrame(self.nav_container, fg_color=COLOR_FONDO, corner_radius=0)
            row.pack(fill="x", pady=1)
            indicator = ctk.CTkFrame(
                row, width=3, height=34, fg_color=COLOR_FONDO, corner_radius=0)
            indicator.pack(side="left", fill="y", pady=4)
            indicator.pack_propagate(False)
            button = ctk.CTkButton(
                row, text=label, font=FUENTE_MENU, anchor="w",
                image=obtener_icono(icon_name, 18), compound="left",
                fg_color="transparent", hover_color=COLOR_FONDO, text_color=COLOR_TEXTO,
                corner_radius=RADIO_CONTROL, height=42,
                command=lambda selected=key: self.seleccionar_seccion(selected),
            )
            button.pack(side="left", fill="x", expand=True, padx=(5, 2))
            self._nav_buttons[key] = button
            self._nav_indicators[key] = indicator

        self.sidebar_grip = ctk.CTkFrame(
            self.sidebar, width=6, corner_radius=0, fg_color=COLOR_BORDE,
            cursor="sb_h_double_arrow",
        )
        self.sidebar_grip.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")
        self.sidebar_grip.bind("<ButtonPress-1>", self._iniciar_redimension_menu)
        self.sidebar_grip.bind("<B1-Motion>", self._redimensionar_menu)

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(8, 12))
        font_controls = ctk.CTkFrame(footer, fg_color="transparent", corner_radius=0)
        font_controls.pack(fill="x", pady=(0, 6))
        zoom_options = (
            (0.90, FUENTE_CAMPO, "Zoom pequeño · 90 %"),
            (1.00, FUENTE_NORMAL, "Zoom normal · 100 %"),
            (1.15, FUENTE_SUBTITULO_PEQUENO, "Zoom grande · 115 %"),
        )
        for scale, font, help_text in zoom_options:
            button = ctk.CTkButton(
                font_controls, text="Aa", height=32, font=font,
                fg_color="transparent", hover_color=COLOR_GRIS_BOTON_HOVER,
                text_color=COLOR_TEXTO, border_width=1, border_color=COLOR_BORDE,
                corner_radius=RADIO_CONTROL,
                command=lambda selected=scale: self.cambiar_tamano_letra(selected),
            )
            button.pack(side="left", fill="x", expand=True, padx=2)
            agregar_tooltip(button, help_text)
            self._zoom_buttons[scale] = button
        self.zoom_value_label = ctk.CTkLabel(
            footer, text="100 %", font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
        )
        self.zoom_value_label.pack(anchor="center", pady=(0, 5))
        self._actualizar_indicador_zoom()
        ctk.CTkLabel(
            footer, text="Por Gonzalo M. para SINCAL Ltda. 2026.",
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
            anchor="w", justify="left",
        ).pack(fill="x", pady=(8, 0))
        self.workspace = ctk.CTkFrame(self, fg_color=COLOR_FONDO, corner_radius=0)
        self.workspace.pack(side="right", fill="both", expand=True)
        header = ctk.CTkFrame(self.workspace, height=58, fg_color=COLOR_PANEL, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.btn_mostrar_menu = ctk.CTkButton(
            header, text="", image=obtener_icono("menu", 19), width=36, height=34,
            fg_color="transparent", hover_color=COLOR_GRIS_BOTON, corner_radius=RADIO_CONTROL,
            command=self.alternar_menu_lateral,
        )
        self.btn_mostrar_menu.pack(side="left", padx=(10, 0), pady=12)
        agregar_tooltip(self.btn_mostrar_menu, "Mostrar u ocultar menú lateral")
        path_bar = ctk.CTkFrame(
            header, fg_color=COLOR_PANEL_OSCURO, corner_radius=RADIO_CONTROL,
        )
        path_bar.pack(side="left", fill="x", expand=True, padx=14, pady=10)
        self.section_title = ctk.CTkLabel(
            path_bar, text="Home", font=FUENTE_NORMAL,
            text_color=COLOR_TEXTO, anchor="w",
        )
        self.section_title.pack(fill="x", padx=12, pady=7)
        ctk.CTkLabel(
            header, text="SINCAL SUITE · 2.0", font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="right", padx=(8, 18))
        self.content_shell = ctk.CTkFrame(
            self.workspace, fg_color=COLOR_FONDO, corner_radius=0)
        self.content_shell.pack(fill="both", expand=True, padx=(32, 44), pady=(10, 18))
        self.page_nav_column = ctk.CTkFrame(
            self.content_shell, width=260, fg_color=COLOR_FONDO, corner_radius=0)
        self.page_nav_column.pack(side="right", fill="y", padx=(18, 8))
        self.page_nav_column.pack_propagate(False)
        ttk.Separator(
            self.page_nav_column, orient="vertical", bootstyle="secondary",
        ).pack(side="left", fill="y", padx=(0, 12), pady=14)
        page_nav_content = ctk.CTkFrame(
            self.page_nav_column, fg_color=COLOR_FONDO, corner_radius=0)
        page_nav_content.pack(side="left", fill="both", expand=True, pady=(16, 10))
        ctk.CTkLabel(
            page_nav_content, text="EN ESTA PÁGINA", font=FUENTE_NORMAL,
            text_color=COLOR_TEXTO, anchor="w",
        ).pack(fill="x", padx=(2, 0), pady=(0, 7))
        self.page_nav_container = ctk.CTkFrame(
            page_nav_content, fg_color=COLOR_FONDO, corner_radius=0)
        self.page_nav_container.pack(fill="x")
        self.content_host = ctk.CTkFrame(
            self.content_shell, fg_color=COLOR_FONDO, corner_radius=0)
        self.content_host.pack(side="left", fill="both", expand=True)
        self.console_panel = ctk.CTkFrame(
            self.workspace, fg_color=COLOR_PANEL_OSCURO, corner_radius=0,
        )
        self.console_grip = ctk.CTkFrame(
            self.console_panel, height=6, corner_radius=0, fg_color=COLOR_BORDE,
            cursor="sb_v_double_arrow",
        )
        self.console_grip.bind("<ButtonPress-1>", self._iniciar_redimension_consola)
        self.console_grip.bind("<B1-Motion>", self._redimensionar_consola)
        console_header = ctk.CTkFrame(self.console_panel, fg_color="transparent")
        console_header.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(
            console_header, text="CONSOLA", font=FUENTE_SUBTITULO_PEQUENO, text_color=COLOR_TEXTO,
        ).pack(side="left")
        ctk.CTkButton(
            console_header, text="Limpiar", font=FUENTE_NORMAL_PEQUENA, width=70, height=26,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=RADIO_CONTROL, command=self.limpiar_consola_global,
        ).pack(side="right")
        self.txt_log_global = ctk.CTkTextbox(
            self.console_panel, font=FUENTE_CONSOLA, fg_color=COLOR_FONDO,
            text_color=COLOR_TEXTO,
            corner_radius=0, state="disabled",
        )
        self.txt_log_global.pack(fill="both", expand=True, padx=12, pady=(2, 12))

    def _crear_secciones(self):
        definitions = (
            ("sincronizador", "Home"),
            ("documentacion", "Documentación"),
            ("comandos", "Comandos en vivo"),
            ("conversion", "Conversión DXF–DWG"),
            ("procesamiento", "Renombrado"),
            ("ubicacion", "Ubicación"),
            ("estructural", "Generador de armadura"),
            ("diagnostico", "Diagnóstico"),
        )
        for key, title in definitions:
            frame = ctk.CTkFrame(self.content_host, fg_color=COLOR_FONDO, corner_radius=0)
            self._sections[key] = (frame, title)
        self.tab_main = self._sections["sincronizador"][0]
        self.tab_docs = self._sections["documentacion"][0]
        self.tab_comandos = self._sections["comandos"][0]
        self.tab_renombrado = self._sections["procesamiento"][0]
        self.tab_ubicacion = self._sections["ubicacion"][0]
        self.tab_armaduras = self._sections["estructural"][0]
        self.tab_conversion = self._sections["conversion"][0]
        tab_diagnostico = self._sections["diagnostico"][0]
        self.tab_ubicacion_widget = TabUbicacion(self.tab_ubicacion, parent_app=self)
        self.tab_ubicacion_widget.pack(expand=True, fill="both")
        self.tab_diagnostico = TabDiagnostico(tab_diagnostico, parent_app=self, fg_color="transparent")
        self.tab_diagnostico.pack(expand=True, fill="both")

    def seleccionar_seccion(self, key):
        if key not in self._sections:
            return
        for frame, _title in self._sections.values():
            frame.pack_forget()
        frame, title = self._sections[key]
        frame.pack(fill="both", expand=True)
        self.actualizar_ruta_interna(title)
        for item_key, button in self._nav_buttons.items():
            selected = item_key == key
            button.configure(
                fg_color="transparent", hover_color=COLOR_FONDO,
                text_color=COLOR_ACENTO if selected else COLOR_TEXTO,
            )
            self._nav_indicators[item_key].configure(
                fg_color=COLOR_ACENTO if selected else COLOR_FONDO)
        self.configurar_navegacion_pagina(key)
        if key == "estructural" and hasattr(self, "vista_armaduras"):
            self.after_idle(self.vista_armaduras.actualizar_breadcrumb)

    def configurar_navegacion_pagina(self, key, entries=None):
        """Construye el índice contextual situado en la esquina superior derecha."""
        if not hasattr(self, "page_nav_container"):
            return
        for widget in self.page_nav_container.winfo_children():
            widget.destroy()
        self._page_nav_buttons = {}
        if entries is None:
            definitions = {
                "sincronizador": (("Presentación", "inicio"), ("Sincronizador", "acciones"), ("Historial", "historial")),
                "comandos": (("Ejecutar comando", "comando"), ("Glosario", "glosario")),
                "procesamiento": (("Archivos", "archivos"), ("Buscar y reemplazar", "reemplazo")),
                "ubicacion": (("Datos del proyecto", "datos"), ("Ubicación y mapa", "mapa"), ("Generar croquis", "generar")),
                "estructural": (("Dimensiones", "dimensiones"), ("Revisión y marcas", "revision"), ("Despiece", "despiece")),
                "conversion": (("Carpeta DXF", "carpeta"), ("Archivos", "archivos"), ("Conversión", "conversion")),
                "diagnostico": (("Estado", "estado"), ("Informe", "informe")),
            }
            if key == "documentacion" and hasattr(self, "vista_docs"):
                entries = self.vista_docs.obtener_navegacion()
            else:
                entries = definitions.get(key, ())
        for label, anchor in entries:
            display_label = label if len(label) <= 36 else label[:35].rstrip() + "…"
            row = ctk.CTkFrame(
                self.page_nav_container, fg_color=COLOR_FONDO, corner_radius=0)
            row.pack(fill="x")
            indicator = ctk.CTkFrame(
                row, width=3, height=28, fg_color=COLOR_FONDO, corner_radius=0)
            indicator.pack(side="left", fill="y", pady=3)
            button = ctk.CTkButton(
                row, text=display_label, font=FUENTE_NORMAL, anchor="w", height=27,
                fg_color="transparent", hover_color=COLOR_FONDO,
                text_color=COLOR_TEXTO, corner_radius=0,
                command=lambda selected=anchor, section=key:
                    self._navegar_pagina(section, selected))
            button.pack(side="left", fill="x", expand=True, padx=(5, 0))
            if display_label != label:
                agregar_tooltip(button, label)
            self._page_nav_buttons[anchor] = (button, indicator)
        if entries:
            self.marcar_navegacion_pagina(entries[0][1])

    def marcar_navegacion_pagina(self, anchor):
        for item_anchor, (button, indicator) in self._page_nav_buttons.items():
            selected = item_anchor == anchor
            button.configure(text_color=COLOR_ACENTO if selected else COLOR_TEXTO)
            indicator.configure(fg_color=COLOR_ACENTO if selected else COLOR_FONDO)

    def _navegar_pagina(self, section, anchor):
        self.marcar_navegacion_pagina(anchor)
        if section == "estructural" and hasattr(self, "vista_armaduras"):
            self.vista_armaduras.ir_a_seccion(anchor)
        elif section == "ubicacion" and hasattr(self, "tab_ubicacion_widget"):
            self.tab_ubicacion_widget.ir_a_seccion(anchor)
        elif section == "documentacion" and hasattr(self, "vista_docs"):
            self.vista_docs.mostrar_tema_por_id(anchor)
        elif section == "diagnostico" and hasattr(self, "tab_diagnostico"):
            self.tab_diagnostico.ir_a_seccion(anchor)
        else:
            self._enfocar_ancla_pagina(section, anchor)

    def _registrar_ancla_pagina(self, section, anchor, widget):
        """Asocia un enlace contextual con un control visible del módulo."""
        self._page_anchors[(section, anchor)] = widget

    def _enfocar_ancla_pagina(self, section, anchor):
        """Lleva el foco al destino y lo realza brevemente cuando no hay scroll."""
        target = self._page_anchors.get((section, anchor))
        if target is None or not target.winfo_exists():
            return
        target.update_idletasks()
        try:
            target.focus_set()
        except tk.TclError:
            pass

        # Si el destino vive dentro de una página desplazable, llévalo a la
        # parte superior. En páginas compactas, el pulso confirma la navegación.
        ancestor = target
        y_offset = 0
        while ancestor is not None:
            if isinstance(ancestor, ctk.CTkScrollableFrame):
                try:
                    total = max(1, ancestor._parent_frame.winfo_reqheight())
                    ancestor._parent_canvas.yview_moveto(
                        max(0.0, min(1.0, y_offset / total)))
                except (AttributeError, tk.TclError):
                    pass
                break
            try:
                y_offset += ancestor.winfo_y()
                ancestor = ancestor.master
            except (AttributeError, tk.TclError):
                break

        try:
            original = target.cget("fg_color")
            target.configure(fg_color=COLOR_GRIS_BOTON)
            target.after(420, lambda: target.winfo_exists() and target.configure(fg_color=original))
        except (ValueError, tk.TclError, AttributeError):
            pass

    def actualizar_ruta_interna(self, *segments):
        """Muestra la ubicación funcional actual como una ruta de exploración."""
        route = " > ".join(str(segment) for segment in segments if segment)
        self.section_title.configure(text=route or "SINCAL Suite")

    def ocultar_menu_lateral(self):
        self._animar_menu_lateral(0, ocultar_al_final=True)

    def mostrar_menu_lateral(self):
        if not self.sidebar.winfo_manager():
            self.sidebar.configure(width=1)
            self.sidebar.pack(side="left", fill="y", before=self.workspace)
        self._animar_menu_lateral(self._sidebar_width)

    def _animar_menu_lateral(self, target, ocultar_al_final=False):
        """Desplaza el panel lateral suavemente al mostrarlo u ocultarlo."""
        if self._sidebar_animation_job is not None:
            try:
                self.after_cancel(self._sidebar_animation_job)
            except Exception:
                pass
            self._sidebar_animation_job = None
        current = max(0, self.sidebar.winfo_width())
        difference = target - current
        if abs(difference) <= 4:
            if ocultar_al_final:
                self.sidebar.pack_forget()
            else:
                self.sidebar.configure(width=target)
            return
        self.sidebar.configure(width=max(1, round(current + difference * 0.28)))
        self._sidebar_animation_job = self.after(
            12, lambda: self._continuar_animacion_menu(target, ocultar_al_final))

    def _continuar_animacion_menu(self, target, ocultar_al_final):
        self._sidebar_animation_job = None
        self._animar_menu_lateral(target, ocultar_al_final)

    def alternar_menu_lateral(self):
        if self.sidebar.winfo_manager():
            self._sidebar_user_hidden = True
            self._sidebar_auto_hidden = False
            self.ocultar_menu_lateral()
        else:
            self._sidebar_user_hidden = False
            self._sidebar_auto_hidden = False
            self.mostrar_menu_lateral()

    def _adaptar_layout_principal(self, event):
        """Libera espacio de trabajo automáticamente en ventanas angostas."""
        if event.widget is not self:
            return
        width = event.width
        if width < 1080 and self.sidebar.winfo_manager() and not self._sidebar_user_hidden:
            self._sidebar_auto_hidden = True
            self.ocultar_menu_lateral()
        elif width >= 1160 and self._sidebar_auto_hidden and not self._sidebar_user_hidden:
            self._sidebar_auto_hidden = False
            self.mostrar_menu_lateral()

    def _iniciar_redimension_menu(self, event):
        self._sidebar_drag_origin = event.x_root
        self._sidebar_drag_width = self.sidebar.winfo_width()

    def _redimensionar_menu(self, event):
        delta = event.x_root - getattr(self, "_sidebar_drag_origin", event.x_root)
        width = max(190, min(430, getattr(self, "_sidebar_drag_width", self._sidebar_width) + delta))
        self._sidebar_width = width
        self.sidebar.configure(width=width)

    def cambiar_tamano_letra(self, value):
        try:
            escala = float(value)
        except (TypeError, ValueError):
            escala = {"Letra pequeña": 0.90, "Letra normal": 1.0, "Letra grande": 1.15}.get(value, 1.0)
        self._zoom_target = max(0.85, min(1.25, escala))
        self._font_scale = self._zoom_target
        ctk.set_widget_scaling(self._font_scale)
        self._actualizar_indicador_zoom()

    def _actualizar_indicador_zoom(self, value=None):
        percentage = round((self._font_scale if value is None else value) * 100)
        if hasattr(self, "zoom_value_label"):
            self.zoom_value_label.configure(text=f"{percentage} %")
        for scale, button in getattr(self, "_zoom_buttons", {}).items():
            selected = abs(scale - (self._font_scale if value is None else value)) < 0.001
            button.configure(
                fg_color=COLOR_ACENTO if selected else "transparent",
                text_color=COLOR_FONDO if selected else COLOR_TEXTO,
                border_color=COLOR_ACENTO if selected else COLOR_BORDE,
            )
        if hasattr(self, "_zoom_mode_var"):
            self._zoom_mode_var.set(self._font_scale)
        if hasattr(self, "menu_ver") and hasattr(self, "_zoom_menu_index"):
            try:
                self.menu_ver.entryconfigure(
                    self._zoom_menu_index, label=f"Zoom texto · {percentage} %")
            except tk.TclError:
                pass

    def cambiar_tema(self, value):
        modo = {"Tema oscuro": "dark", "Tema claro": "light", "Tema del sistema": "system"}.get(value, "dark")
        ctk.set_appearance_mode(modo)
        resolved_dark = ctk.get_appearance_mode() == "Dark"
        ttk_theme = TTK_PRESET_OSCURO if resolved_dark else TTK_PRESET_CLARO
        self.bootstrap_style.theme_use(ttk_theme)
        armonizar_estilos_ttk(self.bootstrap_style, dark=resolved_dark)
        if hasattr(self, "_theme_mode_var"):
            self._theme_mode_var.set(value)
        self._actualizar_menu_nativo(modo)

    def _construir_menu_superior(self):
        self.menu_superior = tk.Menu(self, tearoff=False)

        archivo = tk.Menu(self.menu_superior, tearoff=False)
        archivo.add_command(label="Abrir carpeta local", command=self.abrir_carpeta_local)
        archivo.add_command(label="Preparar integración CAD", command=self.forzar_path_manual)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.cerrar_aplicacion)
        self.menu_superior.add_cascade(label="Archivo", menu=archivo)

        editar = tk.Menu(self.menu_superior, tearoff=False)
        editar.add_command(label="Renombrado", command=lambda: self.seleccionar_seccion("procesamiento"))
        editar.add_command(label="Comandos en vivo", command=lambda: self.seleccionar_seccion("comandos"))
        editar.add_separator()
        editar.add_command(label="Limpiar consola", command=self.limpiar_consola_global)
        self.menu_superior.add_cascade(label="Editar", menu=editar)

        self.menu_ver = tk.Menu(self.menu_superior, tearoff=False)
        self.menu_ver.add_command(
            label="Mostrar/ocultar menú lateral", command=self.alternar_menu_lateral)
        self.menu_ver.add_separator()
        self._console_visible_var = tk.BooleanVar(value=False)
        self.menu_ver.add_checkbutton(
            label="Consola", variable=self._console_visible_var,
            command=self.alternar_consola_inferior)
        self.menu_ver.add_separator()
        zoom_menu = tk.Menu(self.menu_ver, tearoff=False)
        self._zoom_mode_var = tk.DoubleVar(value=self._font_scale)
        for label, scale in (("Aa  ·  90 %", 0.90), ("Aa  ·  100 %", 1.00), ("Aa  ·  115 %", 1.15)):
            zoom_menu.add_radiobutton(
                label=label, value=scale, variable=self._zoom_mode_var,
                command=lambda selected=scale: self.cambiar_tamano_letra(selected))
        self._zoom_menu_index = self.menu_ver.index("end") + 1
        self.menu_ver.add_cascade(label="Zoom texto · 100 %", menu=zoom_menu)
        self.menu_ver.add_separator()
        self._theme_mode_var = tk.StringVar(value="Tema oscuro")
        theme_menu = tk.Menu(self.menu_ver, tearoff=False)
        for label in ("Tema oscuro", "Tema claro", "Tema del sistema"):
            theme_menu.add_radiobutton(
                label=label.replace("Tema ", "").title(), value=label,
                variable=self._theme_mode_var,
                command=lambda selected=label: self._seleccionar_tema(selected))
        self.menu_ver.add_cascade(label="Tema", menu=theme_menu)
        self.menu_superior.add_cascade(label="Ver", menu=self.menu_ver)

        ayuda = tk.Menu(self.menu_superior, tearoff=False)
        ayuda.add_command(label="Documentación", command=lambda: self.seleccionar_seccion("documentacion"))
        ayuda.add_command(label="Diagnóstico", command=lambda: self.seleccionar_seccion("diagnostico"))
        ayuda.add_command(label="Releases oficiales", command=lambda: webbrowser.open(URL_RELEASES))
        ayuda.add_separator()
        ayuda.add_command(label="Acerca de SINCAL Suite", command=self.mostrar_acerca_de)
        self.menu_superior.add_cascade(label="Ayuda", menu=ayuda)

        self.config(menu=self.menu_superior)
        self._actualizar_menu_nativo("dark")

    def alternar_consola_inferior(self):
        self.cambiar_modo_consola(
            "Consola: inferior" if self._console_visible_var.get() else "Consola: oculta")

    def _seleccionar_tema(self, option):
        self.cambiar_tema(option)

    def restablecer_tamano_letra(self):
        self.cambiar_tamano_letra(1.0)

    def mostrar_acerca_de(self):
        messagebox.showinfo(
            "Acerca de SINCAL Suite",
            f"SINCAL Suite — Workbench de ingeniería\nVersión de producto: 2.0\nVersión técnica: {self.version_local_actual}",
            parent=self,
        )

    def _actualizar_menu_nativo(self, modo):
        if not hasattr(self, "menu_superior"):
            return
        claro = modo == "light" or (modo == "system" and ctk.get_appearance_mode() == "Light")
        palette = PALETA_CLARA if claro else PALETA_OSCURA
        fondo = palette["fondo"]
        texto = palette["texto"]
        activo = palette.get("suave", palette.get("panel"))
        try:
            def apply_menu(menu):
                menu.configure(
                    bg=fondo, fg=texto, activebackground=activo,
                    activeforeground=texto, selectcolor=fondo)
                end = menu.index("end")
                if end is None:
                    return
                for index in range(end + 1):
                    submenu_name = menu.entrycget(index, "menu")
                    if submenu_name:
                        apply_menu(self.nametowidget(submenu_name))
            apply_menu(self.menu_superior)
        except Exception:
            pass

    def cambiar_modo_consola(self, option):
        modes = {
            "Consola: oculta": "Oculta",
            "Consola: inferior": "Inferior",
        }
        self._console_mode = modes.get(option, "Oculta")
        if hasattr(self, "_console_visible_var"):
            self._console_visible_var.set(self._console_mode == "Inferior")
        self.content_shell.pack_forget()
        self.console_panel.pack_forget()
        if self._console_mode == "Inferior":
            self.content_shell.pack(side="top", fill="both", expand=True)
            self.console_panel.configure(height=210, width=1)
            self.console_panel.pack(side="bottom", fill="x")
            self.console_panel.pack_propagate(False)
            self.console_grip.configure(width=1, height=6, cursor="sb_v_double_arrow")
            self.console_grip.place(x=0, y=0, relwidth=1.0)
        else:
            self.console_grip.place_forget()
            self.content_shell.pack(fill="both", expand=True)
        self._actualizar_consola_global()

    def _iniciar_redimension_consola(self, event):
        self._console_drag_x = event.x_root
        self._console_drag_y = event.y_root
        self._console_drag_width = self.console_panel.winfo_width()
        self._console_drag_height = self.console_panel.winfo_height()

    def _redimensionar_consola(self, event):
        if self._console_mode == "Inferior":
            height = self._console_drag_height + (self._console_drag_y - event.y_root)
            self.console_panel.configure(height=max(120, min(520, height)))

    def mostrar_ventana_log(self):
        self.cambiar_modo_consola("Consola: inferior")

    def limpiar_consola_global(self):
        self.historial_logs.clear()
        self._set_textbox_content(self.txt_log_global, "")

    def _actualizar_consola_global(self):
        if hasattr(self, "txt_log_global"):
            self._set_textbox_content(self.txt_log_global, "\n".join(self.historial_logs) + ("\n" if self.historial_logs else ""))

    def _ui(self, callback, *args, **kwargs):
        if getattr(self, '_cerrando', False):
            return
        self._ui_queue.put((callback, args, kwargs))

    def report_callback_exception(self, exc_type, value, tb):
        detail = "".join(traceback.format_exception(exc_type, value, tb))
        self.logger.error("Error no controlado en la interfaz:\n%s", detail)
        record_incident(
            "interfaz",
            "error",
            {"type": exc_type.__name__, "error": str(value), "traceback": detail},
        )
        try:
            messagebox.showerror(
                "Error de SINCAL Suite",
                "Ocurrió un error inesperado. El detalle quedó guardado en Diagnóstico y soporte.\n\n"
                f"{value}",
                parent=self,
            )
        except Exception:
            pass

    def _procesar_ui_queue(self):
        try:
            while True:
                callback, args, kwargs = self._ui_queue.get_nowait()
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    self.logger.warning("Error UI callback: %s", e)
                    record_incident(
                        "interfaz_callback",
                        "error",
                        {"callback": getattr(callback, "__name__", repr(callback)), "error": str(e)},
                    )
        except queue.Empty:
            pass
        finally:
            if not getattr(self, '_cerrando', False) and self.winfo_exists():
                self.after(50, self._procesar_ui_queue)

    def _set_textbox_content(self, widget, texto):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", texto)
        widget.see("end")
        widget.configure(state="disabled")

    def _append_textbox(self, widget, texto):
        widget.configure(state="normal")
        widget.insert("end", texto)
        widget.see("end")
        widget.configure(state="disabled")

    # ==========================================================
    # CICLO DE VIDA DE LA APLICACIÓN
    # ==========================================================
    def cerrar_aplicacion(self):
        if getattr(self, '_cerrando', False):
            return
        self._cerrando = True
        self.cancelar_comando_vivo = True
        if self._resource_poll_job is not None:
            try:
                self.after_cancel(self._resource_poll_job)
            except Exception:
                pass
            self._resource_poll_job = None
        self.logger.info("Cierre solicitado: SINCAL Suite finalizará sin permanecer en segundo plano.")
        record_incident("cierre_aplicacion", "ok")
        try:
            self.quit()
        finally:
            self.destroy()

    def setup_tab_armaduras(self):
        self.vista_armaduras = TabArmaduras(
            master=self.tab_armaduras, parent_app=self, fg_color="transparent")
        self.vista_armaduras.pack(fill="both", expand=True)

    # ==========================================================
    # PARTE COMÚN Y SOPORTE DE ACTUALIZACIONES
    # ==========================================================
    @staticmethod
    def _resumir_commit(mensaje):
        """Devuelve título y una explicación breve apta para el panel angosto."""
        lineas = [linea.strip() for linea in (mensaje or "").splitlines() if linea.strip()]
        titulo = (lineas[0] if lineas else "Cambio sin descripción")[:76]
        if len(lineas) > 1:
            return titulo, " ".join(lineas[1:])[:150]
        texto = titulo.lower()
        categorias = (
            (("armadura", "zapata", "fierro", "estribo", "rebar"),
             "Mejora el generador y la representación de armaduras."),
            (("interfaz", "tema", "fuente", "menú", "layout", "ui"),
             "Ajusta la interfaz, su navegación o accesibilidad visual."),
            (("release", "instalador", "manifiesto", "actualiz"),
             "Actualiza el flujo de publicación o distribución."),
            (("lisp", "cad", "dwg", "master", "zwcad", "autocad"),
             "Ajusta recursos CAD o su integración con el programa."),
            (("document", "tutorial", "readme"),
             "Amplía o corrige la documentación disponible."),
            (("mapa", "ubicaci", "kmz"),
             "Mejora las herramientas de ubicación y cartografía."),
            (("diagnóst", "error", "bug", "fix", "corrige"),
             "Corrige un problema y refuerza la estabilidad."),
        )
        descripcion = next(
            (detalle for claves, detalle in categorias if any(clave in texto for clave in claves)),
            "Ajuste técnico y mantenimiento general de SINCAL Suite.",
        )
        return titulo, descripcion

    def cargar_info_github(self):
        try:
            commits_response = requests.get(
                distribution_api_url("commits"), params={"per_page": 10}, timeout=5)
            releases_response = requests.get(
                distribution_api_url("releases"), params={"per_page": 4}, timeout=5)
            if commits_response.status_code == 200:
                lineas = ["RELEASES"]
                if releases_response.status_code == 200:
                    for release in releases_response.json()[:4]:
                        tag = release.get("tag_name") or release.get("name") or "release"
                        detalle = (release.get("name") or release.get("body") or "Publicada").splitlines()[0].strip()
                        lineas.append(f"• {tag} — {detalle[:54]}")
                else:
                    lineas.append("• No se pudieron consultar releases.")
                lineas.extend(("", "COMMITS"))

                meses = {"01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
                         "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"}

                for c in commits_response.json()[:6]:
                    raw_date = c['commit']['author']['date']
                    dt_local = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).astimezone()

                    mes_str = meses[dt_local.strftime("%m")]
                    fecha_formateada = f"{dt_local.strftime('%d')} {mes_str} {dt_local.strftime('%y %H:%M')}"

                    sha_completo = c['sha']
                    version_mostrar = sha_completo[:7]

                    titulo, descripcion = self._resumir_commit(c['commit']['message'])
                    lineas.append(
                        f"• {version_mostrar} · {fecha_formateada}\n"
                        f"  {titulo}\n"
                        f"  {descripcion}"
                    )

                self._ui(self._set_textbox_content, self.txt_history, "\n".join(lineas))
        except Exception as e:
            self.logger.warning("No se pudo cargar el historial de cambios: %s", e)

    def cad_esta_ejecutandose(self):
        try:
            salida = subprocess.check_output("tasklist", creationflags=0x08000000).decode(
                'utf-8', errors='ignore').lower()
            return any(x in salida for x in ["acad.exe", "zwcad.exe", "accoreconsole.exe"])
        except:
            return False

    def mostrar_popup_actualizacion(self, nueva_version, desc_commit):
        self.deiconify()
        self.focus_force()

        msg = (
            f"Versión detectada: {nueva_version}\n\n"
            f"Novedades:\n{desc_commit}\n\n"
            "SINCAL Suite ya no descarga código ejecutable en caliente.\n"
            "¿Deseas abrir la página oficial de releases para instalar la actualización?"
        )

        if messagebox.askyesno("¡Actualización de SINCAL Suite disponible!", msg):
            webbrowser.open(URL_RELEASES)
            self.log("[!] Abriendo la página oficial para actualizar SINCAL Suite.")
        else:
            self.log(
                f"[!] Actualización a {nueva_version} pospuesta por el usuario.")

    def setup_tab_sincronizador(self):
        portada = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        portada.pack(fill="x", padx=40, pady=(38, 20))
        ctk.CTkLabel(
            portada, text="SINCAL SUITE", font=FUENTE_TITULO, text_color=COLOR_TEXTO,
        ).pack(pady=(4, 12))
        ctk.CTkLabel(
            portada,
            text=("Una suite de ingeniería para estandarizar dibujos CAD, automatizar planos, "
                  "organizar recursos de proyecto y generar armaduras con control del usuario."),
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO, justify="center", wraplength=720,
        ).pack(padx=30)
        ctk.CTkLabel(
            portada,
            text=("Integra documentación, comandos en vivo, conversión DXF–DWG, renombrado, "
                  "ubicación, diagnóstico y herramientas estructurales en un solo entorno."),
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
            justify="center", wraplength=700,
        ).pack(padx=30, pady=(7, 0))
        ctk.CTkLabel(
            portada, text="Por Gonzalo M. para SINCAL Ltda. · 2026",
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
        ).pack(pady=(12, 2))

        ttk.Separator(self.tab_main, orient="horizontal", bootstyle="secondary").pack(
            fill="x", padx=46, pady=(0, 14))
        ctk.CTkLabel(
            self.tab_main, text="SINCRONIZADOR", font=FUENTE_SUBTITULO,
            text_color=COLOR_MOSTAZA, anchor="w",
        ).pack(fill="x", padx=46, pady=(0, 3))
        ctk.CTkLabel(
            self.tab_main,
            text="Mantiene el programa, los recursos CAD y el historial de distribución en un mismo lugar.",
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE, anchor="w",
        ).pack(fill="x", padx=46, pady=(0, 8))

        botones_sec_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        botones_sec_frame.pack(fill="x", padx=46, pady=(4, 18))
        self._home_action_buttons = []

        def boton_accion(icono, ayuda, comando):
            boton = ctk.CTkButton(
                botones_sec_frame, text="", image=obtener_icono(icono, 20), width=50, height=44,
                fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
                text_color=COLOR_TEXTO, corner_radius=RADIO_CONTROL, command=comando,
            )
            agregar_tooltip(boton, ayuda)
            self._home_action_buttons.append(boton)
            return boton

        boton_accion("download", "Abrir instalador oficial", lambda: webbrowser.open(URL_RELEASES))
        boton_accion("folder", "Abrir carpeta local", self.abrir_carpeta_local)
        boton_accion("settings", "Preparar integración CAD", self.forzar_path_manual)
        self.btn_sync_resources = boton_accion("refresh", "Actualizar recursos CAD", self.verificar_recursos_manual)
        self.btn_verificar_update = boton_accion("update", "Verificar nueva actualización", self.verificar_actualizacion_manual)
        botones_sec_frame.bind("<Configure>", self._reordenar_acciones_inicio, add="+")
        self.after_idle(lambda: self._reordenar_acciones_inicio(None))

        history_panel = ctk.CTkFrame(
            self.tab_main, fg_color=COLOR_PANEL, corner_radius=RADIO_PANEL,
            border_width=1, border_color=COLOR_BORDE,
        )
        history_panel.pack(fill="both", expand=True, padx=46, pady=(4, 24))
        ctk.CTkLabel(
            history_panel, text="HISTORIAL DE CAMBIOS", font=FUENTE_SUBTITULO_PEQUENO,
            text_color=COLOR_MOSTAZA,
        ).pack(anchor="w", padx=16, pady=(14, 6))
        self.txt_history = ctk.CTkTextbox(
            history_panel, height=190, font=FUENTE_NORMAL_PEQUENA,
            fg_color=COLOR_PANEL, text_color=COLOR_TEXTO_SUAVE,
            state="disabled", corner_radius=RADIO_CONTROL, wrap="word",
        )
        self.txt_history.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self._registrar_ancla_pagina("sincronizador", "inicio", portada)
        self._registrar_ancla_pagina("sincronizador", "acciones", botones_sec_frame)
        self._registrar_ancla_pagina("sincronizador", "historial", history_panel)

        self._iniciar_verificacion_recursos()
        self._programar_monitoreo_recursos()

    def _reordenar_acciones_inicio(self, event):
        """Refluye las acciones principales según el ancho disponible."""
        if not getattr(self, "_home_action_buttons", None):
            return
        width = event.width if event is not None else 600
        columns = 5 if width >= 500 else 3 if width >= 310 else 2
        for column in range(5):
            self._home_action_buttons[0].master.grid_columnconfigure(column, weight=1 if column < columns else 0)
        for index, button in enumerate(self._home_action_buttons):
            button.grid(row=index // columns, column=index % columns, padx=5, pady=5, sticky="ew")

    def verificar_recursos_manual(self):
        self.log("\n[*] Buscando actualizaciones menores de recursos CAD en GitHub...")
        self.btn_sync_resources.configure(state="disabled", text="…")
        if not self._iniciar_verificacion_recursos(manual=True):
            self.log("[*] Ya hay una comprobación de recursos en curso.")
            self.btn_sync_resources.configure(state="normal", text="")

    def _iniciar_verificacion_recursos(self, manual=False, periodic=False, manifest_only=False):
        if self._resource_check_running or self._cerrando:
            return False
        self._resource_check_running = True
        threading.Thread(
            target=self._hilo_verificar_recursos,
            args=(manual, periodic, manifest_only),
            daemon=True,
        ).start()
        return True

    def _programar_monitoreo_recursos(self):
        if self._cerrando:
            return
        self._resource_poll_job = self.after(
            RESOURCE_POLL_INTERVAL_MS,
            self._verificar_recursos_periodicamente,
        )

    def _verificar_recursos_periodicamente(self):
        if self._cerrando:
            return
        self._iniciar_verificacion_recursos(periodic=True, manifest_only=True)
        self._programar_monitoreo_recursos()

    def _preparar_archivos_cad(self):
        copiados = materialize_cad_resources()
        archivos_lisp = active_resource_paths(("lisps/", "startup/"))
        self.generar_archivos_lisp(archivos_lisp)
        engine = ensure_cad_engine()
        if engine:
            self.cad_exe_path = engine.path
            self.es_zwcad = engine.product == "ZWCAD"
        registros = registrar_ruta_cad_usuario()
        scripts_path = registrar_scripts_en_path()
        registros = tuple(registros) + (f"PATH::{scripts_path}",)
        return copiados, registros

    def _hilo_verificar_recursos(self, manual, periodic=False, manifest_only=False):
        actualizacion_ofrecida = False
        try:
            manifest_revision = ""
            try:
                manifest_revision = distribution_manifest_revision()
            except Exception as e:
                self.logger.warning("No se pudo consultar el manifiesto público: %s", e)
                if manifest_only:
                    return

            if (
                manifest_only
                and self._resource_manifest_revision
                and manifest_revision == self._resource_manifest_revision
            ):
                return

            plan = check_resource_updates()
            if manifest_revision:
                self._resource_manifest_revision = manifest_revision
            if plan.has_changes:
                if not manual and plan.tree_sha == self._last_resource_offer_tree:
                    return
                actualizacion_ofrecida = True
                self._last_resource_offer_tree = plan.tree_sha
                rutas_cambiadas = [entry.path for entry in plan.changed] + [
                    f"{path} (eliminado)" for path in plan.removed
                ]
                self.log(
                    f"[!] Actualización menor disponible: {len(plan.changed)} archivo(s) nuevo(s) o modificado(s)"
                    f" y {len(plan.removed)} eliminado(s): {', '.join(rutas_cambiadas)}"
                )
                self._ui(self._ofrecer_actualizacion_recursos, plan, manual)
                return

            record_resource_state(plan)
            self._preparar_archivos_cad()
            if not periodic:
                self.log("[OK] Los LISPs, scripts, estilos y el master DWG ya están actualizados.")
            if manual:
                self._ui(
                    messagebox.showinfo,
                    "Workbench",
                    "Los recursos CAD ya coinciden con la rama main de GitHub.",
                )
        except Exception as e:
            self.logger.warning("No se pudieron verificar los recursos CAD: %s", e)
            record_incident("verificar_recursos", "error", {"error": str(e)})
            self.log(f"[!] No se pudieron verificar los recursos CAD; se conservarán las copias locales: {e}")
            if manual:
                self._ui(
                    messagebox.showwarning,
                    "Recursos CAD",
                    "No fue posible consultar GitHub. Se conservarán los últimos recursos válidos.\n\n"
                    f"Detalle: {e}",
                )
        finally:
            self._resource_check_running = False
            if manual and not actualizacion_ofrecida:
                self._ui(self.btn_sync_resources.configure, state="normal", text="")

    def _ofrecer_actualizacion_recursos(self, plan, manual):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(250, lambda: self.attributes("-topmost", False))
        self.focus_force()
        rutas = [entry.path for entry in plan.changed] + [f"{path} (eliminado)" for path in plan.removed]
        vista = "\n".join(f"• {path}" for path in rutas[:12])
        if len(rutas) > 12:
            vista += f"\n• ... y {len(rutas) - 12} archivo(s) más"
        mensaje = (
            "Hay una actualización menor de recursos CAD disponible.\n\n"
            f"{vista}\n\n"
            "Se actualizarán LISPs, scripts, estilos, mapas o el master DWG; el ejecutable no será reemplazado.\n"
            "¿Deseas descargarla ahora?"
        )
        if messagebox.askyesno("Actualización de recursos de SINCAL Suite", mensaje, parent=self):
            self.btn_sync_resources.configure(state="disabled", text="…")
            threading.Thread(target=self._hilo_aplicar_recursos, args=(plan,), daemon=True).start()
        else:
            self.log("[!] Actualización menor pospuesta por el usuario.")
            if manual:
                self.btn_sync_resources.configure(state="normal", text="")

    def _hilo_aplicar_recursos(self, plan):
        try:
            resultado = apply_resource_updates(plan)
        except Exception as e:
            self.logger.exception("Falló la actualización de recursos CAD")
            record_incident("actualizar_recursos", "error", {"error": str(e)})
            self.log(f"[X] No se pudo completar la actualización menor: {e}")
            self._ui(
                messagebox.showerror,
                "Actualización incompleta",
                "No se aplicó completamente la actualización. SINCAL Suite volverá a intentarlo al iniciar.\n\n"
                f"Detalle: {e}",
            )
            self._ui(self.btn_sync_resources.configure, state="normal", text="")
            return

        avisos = []
        integracion_preparada = False
        try:
            self._preparar_archivos_cad()
            integracion_preparada = True
        except Exception as e:
            self.logger.warning(
                "Los recursos se instalaron, pero no se pudo preparar la integración CAD: %s",
                e,
            )
            avisos.append(
                "No fue posible refrescar la carpeta de integración CAD. "
                "Pulsa Preparar integración CAD cuando el programa CAD esté disponible."
            )

        recargados = 0
        if integracion_preparada:
            try:
                recargados = self._recargar_lisps_cad_abierto()
            except Exception as e:
                self.logger.warning(
                    "Los recursos se instalaron, pero AutoCAD/ZWCAD rechazó la recarga en vivo: %s",
                    e,
                )
                avisos.append(
                    "AutoCAD/ZWCAD no aceptó la recarga en vivo. Reinicia CAD para cargar los comandos nuevos."
                )

        self._ui(self._refrescar_interfaces_recursos)
        rutas_actualizadas = list(resultado.updated) + [
            f"{path} (eliminado)" for path in resultado.removed
        ]
        self.log(
            f"[OK] Actualización menor instalada: {len(resultado.updated)} archivo(s) actualizado(s)"
            f" y {len(resultado.removed)} eliminado(s): {', '.join(rutas_actualizadas)}"
        )
        record_incident(
            "actualizar_recursos",
            "ok",
            {"updated": list(resultado.updated), "removed": list(resultado.removed)},
        )
        estado_cad = (
            f"Los comandos LISP se recargaron en {recargados} dibujo(s) abierto(s)."
            if recargados
            else "Abre un dibujo nuevo o reinicia AutoCAD/ZWCAD para cargar comandos LISP nuevos."
        )
        mensaje = (
            "Los recursos fueron descargados, validados e instalados correctamente.\n\n"
            "Cierra y vuelve a abrir SINCAL Suite para refrescar toda la interfaz. "
            + estado_cad
        )
        if avisos:
            mensaje += "\n\n" + "\n".join(avisos)
        self._ui(
            messagebox.showwarning if avisos else messagebox.showinfo,
            "Workbench",
            mensaje,
        )
        self._ui(self.btn_sync_resources.configure, state="normal", text="")

    def _refrescar_interfaces_recursos(self):
        if hasattr(self, "tab_ubicacion_widget"):
            self.tab_ubicacion_widget.recargar_recursos()
        if hasattr(self, "vista_docs"):
            self.vista_docs.recargar_documentacion()

    def _recargar_lisps_cad_abierto(self):
        loader = ruta_cad_usuario("acaddoc.lsp").replace("\\", "/")
        command = f'(load "{loader}")\n'
        pythoncom.CoInitialize()
        try:
            prog_ids = ["ZWCAD.Application", "AutoCAD.Application"]
            for version in range(15, 36):
                prog_ids.extend((f"ZWCAD.Application.{version}", f"AutoCAD.Application.{version}"))

            processed = set()
            count = 0
            for prog_id in prog_ids:
                try:
                    app = win32com.client.GetActiveObject(prog_id)
                    documents = app.Documents
                    document_count = documents.Count
                except Exception:
                    continue
                for index in range(document_count):
                    try:
                        document = documents.Item(index)
                        identity = f"{document.FullName}|{document.Name}"
                        if identity in processed:
                            continue
                        processed.add(identity)
                        document.SendCommand(command)
                        count += 1
                    except Exception as e:
                        self.logger.warning("No se pudo recargar LISP en un dibujo abierto: %s", e)
            return count
        finally:
            pythoncom.CoUninitialize()

    def verificar_actualizacion_manual(self):
        self.log("\n[*] Verificando nueva actualización en GitHub...")
        self.btn_verificar_update.configure(
            state="disabled", text="…")
        threading.Thread(
            target=self._hilo_verificar_actualizacion, daemon=True).start()

    def _hilo_verificar_actualizacion(self):
        try:
            r = requests.get(
                distribution_api_url("releases/latest"),
                timeout=5,
            )
            r.raise_for_status()
            release = r.json()
            nueva_version = release.get("tag_name") or release.get("name") or self.version_local_actual

            if is_newer_version(nueva_version, self.version_local_actual):
                desc_commit = (release.get("body") or "Mejoras generales y corrección de errores.").strip()[:1200]

                self.log(
                    f"[!] Nueva versión disponible: {nueva_version}. Novedades: {desc_commit}")
                self._ui(self.mostrar_popup_actualizacion, nueva_version, desc_commit)
            else:
                self.log(
                    "[OK] El sistema ya se encuentra en su última versión.")
                self._ui(messagebox.showinfo,
                         "Workbench", "El sistema ya se encuentra en su última versión.")
        except Exception as e:
            self.log(f"[X] Fallo al verificar versión en GitHub: {e}")
        finally:
            self._ui(self.btn_verificar_update.configure,
                     state="normal", text="")

    def setup_tab_renombrado(self):
        lbl_titulo = ctk.CTkLabel(
            self.tab_renombrado, text="RENOMBRADO", font=FUENTE_TITULO, text_color=COLOR_TEXTO)
        lbl_titulo.pack(pady=(10, 5))

        top_frame = ctk.CTkFrame(self.tab_renombrado, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=5)
        top_frame.grid_columnconfigure(0, weight=1)
        self.btn_browse_adv = ctk.CTkButton(top_frame, text="Seleccionar carpeta DWG/DXF", font=FUENTE_NORMAL, width=220,
                                            corner_radius=0, fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER, command=self.cargar_archivos_renombrado)
        self.btn_browse_adv.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top_frame, text="Limpiar ruta", font=FUENTE_NORMAL_PEQUENA, width=94,
                      fg_color="transparent", hover_color=COLOR_GRIS_BOTON, text_color=COLOR_TEXTO_SUAVE,
                      corner_radius=0, command=self.limpiar_ruta_renombrado).grid(row=0, column=1, sticky="e")
        self.ruta_adv_var = ctk.StringVar(value="Ruta: Ninguna")
        self.ent_ruta_adv = ctk.CTkEntry(
            top_frame, textvariable=self.ruta_adv_var, font=FUENTE_CAMPO,
            corner_radius=0, state="readonly",
        )
        self.ent_ruta_adv.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(7, 0))

        left_frame = ctk.CTkFrame(self.tab_renombrado, fg_color="transparent", corner_radius=0)
        left_frame.pack(fill="x", padx=20, pady=(6, 2))

        ctk.CTkLabel(left_frame, text="1. Archivos a procesar:", font=FUENTE_SUBTITULO,
                     text_color=COLOR_TEXTO).pack(pady=(8, 5), padx=2, anchor="w")

        btn_tools = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_tools.pack(fill="x", padx=2, pady=5)
        ctk.CTkButton(btn_tools, text="Marcar", width=80, corner_radius=0, font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
                      hover_color=COLOR_GRIS_BOTON_HOVER, command=self.marcar_todos).pack(side="left", padx=(0, 4))
        ctk.CTkButton(btn_tools, text="Desmarcar", width=95, corner_radius=0, font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
                      hover_color=COLOR_GRIS_BOTON_HOVER, command=self.desmarcar_todos).pack(side="left")

        self.scroll_archivos = ctk.CTkScrollableFrame(
            left_frame, height=205, fg_color=COLOR_PANEL, corner_radius=0)
        self.scroll_archivos.pack(
            fill="x", padx=2, pady=(5, 8))

        h1_frame = ctk.CTkFrame(self.tab_renombrado, fg_color="transparent", corner_radius=0)
        h1_frame.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(h1_frame, text="2. Buscar y Reemplazar (Renombrado Automático)",
                     font=FUENTE_SUBTITULO, text_color=COLOR_TEXTO).pack(anchor="w", padx=2, pady=(4, 5))

        entry_row = ctk.CTkFrame(h1_frame, fg_color="transparent")
        entry_row.pack(fill="x", padx=2, pady=5)
        self.ent_buscar_adv = ctk.CTkEntry(
            entry_row, placeholder_text="Buscar texto (Ej: HL-)", font=FUENTE_CAMPO, corner_radius=0)
        self.ent_buscar_adv.pack(
            side="left", fill="x", expand=True, padx=(0, 10))
        self.ent_reemplazo_adv = ctk.CTkEntry(
            entry_row, placeholder_text="Reemplazar con (Ej: PL-)", font=FUENTE_CAMPO, corner_radius=0)
        self.ent_reemplazo_adv.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(h1_frame, text="Aplicar reemplazo a la selección", font=FUENTE_NORMAL, corner_radius=0,
                      fg_color=COLOR_GRIS_BOTON, text_color=COLOR_TEXTO, hover_color=COLOR_GRIS_BOTON_HOVER,
                      command=self.aplicar_reemplazo_adv).pack(pady=8, padx=2, fill="x")
        self._registrar_ancla_pagina("procesamiento", "archivos", left_frame)
        self._registrar_ancla_pagina("procesamiento", "reemplazo", h1_frame)

    def setup_tab_comandos(self):
        page = ctk.CTkScrollableFrame(
            self.tab_comandos, fg_color=COLOR_FONDO, corner_radius=0,
            scrollbar_button_color=COLOR_GRIS_BOTON,
            scrollbar_button_hover_color=COLOR_GRIS_BOTON_HOVER,
        )
        page.pack(fill="both", expand=True, padx=(0, 4))
        ctk.CTkLabel(page, text="COMANDOS EN VIVO", font=FUENTE_TITULO,
                     text_color=COLOR_TEXTO).pack(pady=(36, 8))
        ctk.CTkLabel(
            page,
            text="Envía un comando a cada plano abierto en AutoCAD o ZWCAD. No uses comandos que requieran clics distintos por dibujo.",
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE, justify="center", wraplength=760,
        ).pack(padx=30, pady=(0, 20))
        controls = ctk.CTkFrame(page, fg_color="transparent")
        controls.pack(fill="x", padx=60, pady=8)
        self.entrada_comando = ctk.CTkEntry(
            controls, font=FUENTE_CAMPO,
            placeholder_text="Escribe un comando y presiona Enter · Ejemplo: ZE o _QSAVE",
            corner_radius=0,
        )
        self.entrada_comando.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_enviar_cmd = ctk.CTkButton(
            controls, text="Ejecutar", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
            hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=0, width=105,
            command=self.enviar_comando_en_vivo,
        )
        self.btn_enviar_cmd.pack(side="left", padx=(0, 8))
        self.btn_cancelar_cmd = ctk.CTkButton(
            controls, text="Cancelar", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
            hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=0, width=105,
            state="disabled", command=self.detener_comando_en_vivo,
        )
        self.btn_cancelar_cmd.pack(side="left")
        self.entrada_comando.bind("<Return>", self._ejecutar_comando_enter)
        self.entrada_comando.bind("<KP_Enter>", self._ejecutar_comando_enter)

        ttk.Separator(page, orient="horizontal", bootstyle="secondary").pack(
            fill="x", padx=36, pady=(26, 14))
        glossary = ctk.CTkFrame(page, fg_color=COLOR_FONDO, corner_radius=0)
        glossary.pack(fill="x", padx=38, pady=(0, 28))
        ctk.CTkLabel(
            glossary, text="GLOSARIO DE COMANDOS", font=FUENTE_SUBTITULO,
            text_color=COLOR_MOSTAZA, anchor="w",
        ).pack(fill="x", pady=(0, 3))
        ctk.CTkLabel(
            glossary,
            text="Estos comandos pueden escribirse arriba cuando no requieran selecciones diferentes en cada plano.",
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
            anchor="w", justify="left", wraplength=760,
        ).pack(fill="x", pady=(0, 12))
        try:
            with open(obtener_ruta_recurso("tutoriales.json"), "r", encoding="utf-8") as source:
                commands = (json.load(source).get("comandos_lisp") or {})
        except (OSError, ValueError, TypeError):
            commands = {}
        for index, (command, detail) in enumerate(commands.items()):
            if index:
                ttk.Separator(glossary, orient="horizontal", bootstyle="secondary").pack(
                    fill="x", pady=5)
            row = ctk.CTkFrame(glossary, fg_color="transparent", corner_radius=0)
            row.pack(fill="x")
            ctk.CTkLabel(
                row, text=command, width=145, font=FUENTE_NORMAL,
                text_color=COLOR_ACENTO, anchor="nw", justify="left",
            ).pack(side="left", padx=(0, 14), pady=3)
            description = detail.get("descripcion") or detail.get("titulo") or "Sin descripción."
            ctk.CTkLabel(
                row, text=description, font=FUENTE_NORMAL,
                text_color=COLOR_TEXTO, anchor="nw", justify="left", wraplength=590,
            ).pack(side="left", fill="x", expand=True, pady=3)
        self._registrar_ancla_pagina("comandos", "comando", controls)
        self._registrar_ancla_pagina("comandos", "glosario", glossary)

    def _ejecutar_comando_enter(self, _event=None):
        """Permite ejecutar desde el campo sin abandonar el teclado."""
        if str(self.btn_enviar_cmd.cget("state")) != "disabled":
            self.enviar_comando_en_vivo()
        return "break"

    def setup_tab_conversion_dxf(self):
        ctk.CTkLabel(
            self.tab_conversion, text="CONVERSIÓN DXF A DWG", font=FUENTE_TITULO,
            text_color=COLOR_MOSTAZA,
        ).pack(pady=(30, 6))
        ctk.CTkLabel(
            self.tab_conversion,
            text=("Convierte una selección de archivos DXF con una instancia CAD temporal. "
                  "Cierra AutoCAD/ZWCAD antes de comenzar y revisa el resultado en la consola."),
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO, justify="center", wraplength=760,
        ).pack(padx=30, pady=(0, 18))

        controls = ctk.CTkFrame(self.tab_conversion, fg_color="transparent")
        controls.pack(fill="x", padx=32, pady=6)
        controls.grid_columnconfigure(0, weight=1)
        action_row = ctk.CTkFrame(controls, fg_color="transparent", corner_radius=0)
        action_row.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            action_row, text="Seleccionar DXF", font=FUENTE_NORMAL,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=self.seleccionar_archivos_dxf,
        ).pack(side="left")
        ctk.CTkButton(
            action_row, text="Cargar carpeta", font=FUENTE_NORMAL_PEQUENA,
            fg_color="transparent", hover_color=COLOR_GRIS_BOTON,
            text_color=COLOR_TEXTO_SUAVE, corner_radius=0, command=self.cargar_archivos_conversion,
        ).pack(side="left", padx=(6, 0))
        ctk.CTkButton(
            action_row, text="Limpiar ruta", font=FUENTE_NORMAL_PEQUENA, width=94,
            fg_color="transparent", hover_color=COLOR_GRIS_BOTON,
            text_color=COLOR_TEXTO_SUAVE, corner_radius=0, command=self.limpiar_ruta_conversion,
        ).pack(side="right")
        self.ruta_conversion_var = ctk.StringVar(value="Ruta: Ninguna")
        self.ent_ruta_conversion = ctk.CTkEntry(
            controls, textvariable=self.ruta_conversion_var, font=FUENTE_CAMPO,
            corner_radius=0, state="readonly",
        )
        self.ent_ruta_conversion.grid(row=1, column=0, sticky="ew", pady=(7, 0))

        panel = ctk.CTkFrame(
            self.tab_conversion, fg_color="transparent", corner_radius=0,
        )
        panel.pack(fill="both", expand=True, padx=32, pady=(8, 20))
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(row, text="Archivos DXF seleccionados", font=FUENTE_SUBTITULO, text_color=COLOR_MOSTAZA).pack(side="left")
        ctk.CTkButton(row, text="Marcar todos", font=FUENTE_NORMAL_PEQUENA, width=92, height=26,
                      fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=0,
                      command=self.marcar_todos_dxf).pack(side="right", padx=(6, 0))
        ctk.CTkButton(row, text="Desmarcar", font=FUENTE_NORMAL_PEQUENA, width=86, height=26,
                      fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=0,
                      command=self.desmarcar_todos_dxf).pack(side="right")
        self.scroll_dxf = ctk.CTkScrollableFrame(panel, fg_color=COLOR_FONDO, corner_radius=0)
        self.scroll_dxf.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.checkboxes_dxf = []
        self.ruta_conversion = ""
        self.archivos_conversion = []
        self.btn_convertir_dxf = ctk.CTkButton(
            panel, text="Convertir DXF a DWG", font=FUENTE_SUBTITULO_PEQUENO,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=0,
            command=self.convertir_dxf_a_dwg,
        )
        self.btn_convertir_dxf.pack(fill="x", padx=16, pady=(0, 16))
        self._registrar_ancla_pagina("conversion", "carpeta", controls)
        self._registrar_ancla_pagina("conversion", "archivos", self.scroll_dxf)
        self._registrar_ancla_pagina("conversion", "conversion", self.btn_convertir_dxf)

    def cargar_archivos_conversion(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta con archivos DXF")
        if not carpeta:
            return
        self.ruta_conversion = carpeta
        self.archivos_conversion = []
        self.ruta_conversion_var.set(f"Ruta: {carpeta}")
        self.refrescar_lista_conversion()

    def seleccionar_archivos_dxf(self):
        rutas = filedialog.askopenfilenames(
            title="Seleccionar archivos DXF",
            filetypes=[("Archivos DXF", "*.dxf"), ("Todos los archivos", "*.*")],
        )
        if not rutas:
            return
        carpetas = {os.path.dirname(ruta) for ruta in rutas}
        if len(carpetas) != 1:
            return messagebox.showwarning(
                "Workbench", "Selecciona archivos DXF que pertenezcan a una sola carpeta.")
        self.ruta_conversion = carpetas.pop()
        self.archivos_conversion = [os.path.basename(ruta) for ruta in rutas]
        self.ruta_conversion_var.set(
            f"Ruta: {self.ruta_conversion} · {len(self.archivos_conversion)} DXF")
        self.refrescar_lista_conversion()

    def limpiar_ruta_conversion(self):
        self.ruta_conversion = ""
        self.archivos_conversion = []
        self.ruta_conversion_var.set("Ruta: Ninguna")
        self.refrescar_lista_conversion()

    def refrescar_lista_conversion(self):
        for widget in self.scroll_dxf.winfo_children():
            widget.destroy()
        self.checkboxes_dxf = []
        if not self.ruta_conversion:
            return
        archivos = self.archivos_conversion or sorted(
            nombre for nombre in os.listdir(self.ruta_conversion) if nombre.lower().endswith(".dxf")
        )
        for nombre in archivos:
            checkbox = ctk.CTkCheckBox(
                self.scroll_dxf, text=nombre, font=FUENTE_NORMAL, text_color=COLOR_TEXTO,
                fg_color=COLOR_ACENTO, hover_color=COLOR_ACENTO_HOVER,
            )
            checkbox.pack(anchor="w", padx=8, pady=4)
            checkbox.select()
            self.checkboxes_dxf.append(checkbox)
        self.log_script(f"[*] Conversión DXF: {len(archivos)} archivo(s) cargado(s).\n")

    def marcar_todos_dxf(self):
        for checkbox in self.checkboxes_dxf:
            checkbox.select()

    def desmarcar_todos_dxf(self):
        for checkbox in self.checkboxes_dxf:
            checkbox.deselect()

    def cargar_archivos_renombrado(self):
        c = filedialog.askdirectory(
            title="Seleccionar carpeta con planos DWG o DXF")
        if not c:
            return
        self.ruta_renombre = c
        self.ruta_adv_var.set(f"Ruta: {c}")
        self.refrescar_lista_archivos()

    def limpiar_ruta_renombrado(self):
        self.ruta_renombre = ""
        self.ruta_adv_var.set("Ruta: Ninguna")
        self.refrescar_lista_archivos()

    def refrescar_lista_archivos(self):
        for w in self.scroll_archivos.winfo_children():
            w.destroy()
        self.checkboxes_archivos = []
        if not self.ruta_renombre:
            self.log_r("[*] Ruta de renombrado limpiada.")
            return
        arcs = [f for f in os.listdir(
            self.ruta_renombre) if f.lower().endswith(('.dwg', '.dxf'))]
        for arc in arcs:
            cb = ctk.CTkCheckBox(self.scroll_archivos, text=arc, font=FUENTE_NORMAL,
                                 text_color=COLOR_TEXTO, fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER)
            cb.pack(anchor="w", pady=5, padx=5)
            cb.select()
            self.checkboxes_archivos.append(cb)
        self.log_r(f"[*] {len(arcs)} archivos cargados en memoria.")

    def marcar_todos(self): [cb.select() for cb in self.checkboxes_archivos]

    def desmarcar_todos(self): [cb.deselect()
                                for cb in self.checkboxes_archivos]

    def aplicar_reemplazo_adv(self):
        if not self.ruta_renombre:
            return self.log_r("[X] Carga una carpeta primero.")
        b, r = self.ent_buscar_adv.get(), self.ent_reemplazo_adv.get()
        if not b:
            return self.log_r("[X] Ingresa texto a buscar.")
        cont = 0
        for cb in self.checkboxes_archivos:
            if cb.get() == 1 and b in cb.cget("text"):
                old = cb.cget("text")
                new = old.replace(b, r)
                try:
                    os.rename(os.path.join(self.ruta_renombre, old),
                              os.path.join(self.ruta_renombre, new))
                    cb.configure(text=new)
                    cont += 1
                except Exception as e:
                    self.log_r(f"[X] Error: {e}")
        self.log_r(f"[OK] {cont} procesados.")

    def convertir_dxf_a_dwg(self):
        ruta = getattr(self, "ruta_conversion", "")
        checkboxes = getattr(self, "checkboxes_dxf", [])
        if not ruta:
            return messagebox.showwarning("Sin ruta", "Selecciona primero una carpeta con archivos DXF.")

        dxfs = [checkbox.cget("text") for checkbox in checkboxes if checkbox.get() == 1]

        if not dxfs:
            return messagebox.showinfo("Nada que convertir", "No hay archivos DXF marcados en la lista.")

        if self.cad_esta_ejecutandose():
            return messagebox.showwarning("CAD en Uso", "Por favor cierra AutoCAD/ZWCAD para que la conversión se haga en segundo plano sin interrupciones.")

        self.mostrar_ventana_log()
        threading.Thread(target=self._hilo_convertir_dxf,
                         args=(dxfs, ruta), daemon=True).start()

    def _hilo_convertir_dxf(self, dxfs, ruta_conversion):
        self.log_script(
            f"[*] Encendiendo motor CAD en segundo plano...\n[*] Se convertirán {len(dxfs)} archivos.\n" + "-"*60 + "\n")
        import pythoncom
        pythoncom.CoInitialize()
        try:
            app = None
            for motor in ["ZWCAD.Application", "AutoCAD.Application"]:
                try:
                    app = win32com.client.DispatchEx(motor)
                    break
                except:
                    pass

            if not app:
                return self.log_script("[X] No se pudo iniciar ni ZWCAD ni AutoCAD en segundo plano.\n")

            try:
                app.Visible = False
            except:
                pass

            for f in dxfs:
                ruta_dxf = os.path.join(ruta_conversion, f)
                ruta_dwg = os.path.join(ruta_conversion, f[:-4] + ".dwg")

                self.log_script(f"> Convirtiendo: {f} ... ")
                try:
                    doc = app.Documents.Open(ruta_dxf)
                    try:
                        doc.SaveAs(ruta_dwg, 64)
                    except:
                        doc.SaveAs(ruta_dwg)

                    doc.Close(False)
                    if os.path.exists(ruta_dwg) and os.path.getsize(ruta_dwg) > 0:
                        self.log_script("OK\n")
                    else:
                        self.log_script("Error (DWG no generado o vacío)\n")
                except Exception as e:
                    self.log_script(f"Error ({str(e)})\n")

            try:
                app.Quit()
            except:
                pass

            self.log_script(
                "\n[!] Conversión finalizada. Actualizando lista...\n")
            self._ui(self.refrescar_lista_conversion)

        except Exception as e:
            self.log_script(f"\n[X] Error fatal de COM: {e}\n")
        finally:
            pythoncom.CoUninitialize()

    def detener_comando_en_vivo(self):
        self.cancelar_comando_vivo = True
        self.btn_cancelar_cmd.configure(state="disabled", text="Deteniendo...")

    def enviar_comando_en_vivo(self):
        c = self.entrada_comando.get()
        if not c:
            return
        self.cancelar_comando_vivo = False
        self.btn_enviar_cmd.configure(state="disabled", text="Enviando...")
        self.btn_cancelar_cmd.configure(state="normal", text="Cancelar")
        threading.Thread(target=self._hilo_comando_en_vivo,
                         args=(c.strip() + "\n",), daemon=True).start()

    def enviar_comando_cad_activo(self, comando, descripcion="Comando estructural"):
        """Envía una orden sólo al documento CAD activo.

        Las herramientas de lectura estructural deben evitar aplicar comandos
        sobre todas las pestañas abiertas: el usuario confirma primero el plano
        activo y sus moldajes antes de generar cualquier resultado.
        """
        threading.Thread(
            target=self._hilo_comando_cad_activo,
            args=(comando, descripcion), daemon=True,
        ).start()

    def _hilo_comando_cad_activo(self, comando, descripcion):
        pythoncom.CoInitialize()
        try:
            prog_ids = ["ZWCAD.Application", "AutoCAD.Application"]
            for index in range(15, 36):
                prog_ids.extend((f"ZWCAD.Application.{index}", f"AutoCAD.Application.{index}"))

            visited = set()
            for prog_id in prog_ids:
                try:
                    app = win32com.client.GetActiveObject(prog_id)
                    doc = app.ActiveDocument
                    identity = f"{doc.FullName}_{doc.Name}"
                    if identity in visited:
                        continue
                    visited.add(identity)
                    doc.SendCommand(comando)
                    self.log(f"  > {descripcion} aplicado en el dibujo activo: {doc.Name}")
                    return
                except Exception as error:
                    self.logger.debug("No se pudo usar %s para el comando activo: %s", prog_id, error)
                    continue

            # Algunas instalaciones registran AutoCAD en la tabla de objetos
            # activos (ROT) con un moniker GUID y no lo devuelven de forma
            # consistente mediante GetActiveObject. Consultar la ROT no crea
            # una instancia nueva: sólo recupera programas ya abiertos.
            try:
                rot = pythoncom.GetRunningObjectTable()
                enum = rot.EnumRunning()
                while True:
                    monikers = enum.Next(1)
                    if not monikers:
                        break
                    try:
                        raw = rot.GetObject(monikers[0])
                        dispatch = raw.QueryInterface(pythoncom.IID_IDispatch)
                        app = win32com.client.Dispatch(dispatch)
                        app_name = str(getattr(app, "Name", "")).lower()
                        if "autocad" not in app_name and "zwcad" not in app_name:
                            continue
                        doc = app.ActiveDocument
                        identity = f"{doc.FullName}_{doc.Name}"
                        if identity in visited:
                            continue
                        visited.add(identity)
                        doc.SendCommand(comando)
                        self.log(f"  > {descripcion} aplicado mediante ROT en el dibujo activo: {doc.Name}")
                        return
                    except Exception as error:
                        self.logger.debug("Objeto ROT no utilizable para el comando activo: %s", error)
                        continue
            except Exception:
                pass
            self.log(f"\n[X] {descripcion}: no se detecta un dibujo CAD activo accesible.")
        except Exception as error:
            self.log(f"\n[X] {descripcion}: fallo COM: {error}")
        finally:
            pythoncom.CoUninitialize()

    def _hilo_comando_en_vivo(self, comando):
        pythoncom.CoInitialize()
        try:
            prog_ids = ["ZWCAD.Application", "AutoCAD.Application"]
            for i in range(15, 36):
                prog_ids.append(f"ZWCAD.Application.{i}")
                prog_ids.append(f"AutoCAD.Application.{i}")

            apps_encontradas = []

            for s in prog_ids:
                try:
                    app = win32com.client.GetActiveObject(s)
                    if app:
                        apps_encontradas.append(app)
                except:
                    pass

            if not apps_encontradas:
                return self.log("\n[X] Error: No se detecta CAD abierto o accesible para la sesión actual.")

            docs_procesados = set()
            ejecuciones = 0

            for app in apps_encontradas:
                if self.cancelar_comando_vivo:
                    break
                try:
                    docs = app.Documents
                    for i in range(docs.Count):
                        if self.cancelar_comando_vivo:
                            break
                        try:
                            doc = docs.Item(i)
                            doc_id = f"{doc.FullName}_{doc.Name}"

                            if doc_id in docs_procesados:
                                continue

                            docs_procesados.add(doc_id)

                            if app.ActiveDocument.Name != doc.Name:
                                app.ActiveDocument = doc
                                time.sleep(0.2)

                            try:
                                doc.SendCommand("\x03\x03")
                            except:
                                pass

                            doc.SendCommand(comando)
                            self.log(f"  > Aplicado en: {doc.Name}")
                            ejecuciones += 1
                        except Exception as e:
                            self.log(f"  > [X] Error pestaña: {e}")
                except:
                    pass

            if ejecuciones == 0:
                self.log(
                    " [!] No hay planos abiertos en los programas detectados.")

        except Exception as e:
            self.log(f"\n[X] Fallo COM: {e}")
        finally:
            self._ui(self.btn_enviar_cmd.configure, state="normal", text="Ejecutar")
            self._ui(self.btn_cancelar_cmd.configure, state="disabled", text="Cancelar")
            pythoncom.CoUninitialize()

    def abrir_carpeta_local(self): os.startfile(
        RUTA_DATOS_USUARIO) if os.path.exists(RUTA_DATOS_USUARIO) else None

    def forzar_path_manual(self):
        try:
            copiados, registros = self._preparar_archivos_cad()
            engine = self.buscar_y_configurar_consolas()
            self.log(
                f"[OK] Integración CAD preparada: {len(copiados)} recurso(s) materializado(s) y "
                f"{len(registros)} ruta(s) de perfil actualizada(s). "
                f"Motor: {engine.label if engine else 'no detectado'}."
            )
            record_incident(
                "preparar_integracion_cad",
                "ok" if engine else "warning",
                {"engine": engine.to_dict() if engine else None, "copied": len(copiados)},
            )
            messagebox.showinfo(
                "Workbench",
                "La integración quedó preparada. Reinicia AutoCAD/ZWCAD una vez para activar "
                "las rutas de confianza y el cargador automático. Cierra y vuelve a abrir CMD "
                "antes de ejecutar AUDIT, ZE, PURGEALL u otro script masivo.",
            )
        except Exception as e:
            self.logger.exception("No se pudo preparar la integración CAD")
            record_incident("preparar_integracion_cad", "error", {"error": str(e)})
            messagebox.showerror("Integración CAD", f"No se pudo completar la preparación.\n\nDetalle: {e}")

    def iniciar_actualizacion_hilo(self):
        webbrowser.open(URL_RELEASES)
        self.log("[!] Los cambios del ejecutable se instalan desde Releases; los recursos CAD se actualizan desde main.")

    def motor_actualizacion(self):
        self.log("[!] La actualización en caliente está limitada a recursos CAD autorizados.")

    def buscar_y_configurar_consolas(self):
        engine = ensure_cad_engine()
        self.cad_exe_path = engine.path if engine else None
        self.es_zwcad = bool(engine and engine.product == "ZWCAD")
        return engine

    def actualizar_rutas_registro(self):
        self.log("[!] Integración automática de rutas CAD deshabilitada por seguridad.")

    def actualizar_variable_entorno(self):
        self.log("[!] Modificación automática de PATH deshabilitada por seguridad.")

    def registrar_menu_contextual(self):
        self.log("[!] Menú contextual deshabilitado hasta tener una ruta de ejecución validada.")

    def generar_archivos_lisp(self, archivos=None):
        contenido_arranque = ""

        if archivos is None:
            archivos = active_resource_paths(("lisps/", "startup/"))

        for a in archivos:
            if a.lower().endswith('.lsp') and os.path.basename(a).lower() not in ["acaddoc.lsp", "zwcaddoc.lsp"]:
                ruta_lisp = ruta_cad_usuario(*a.replace("\\", "/").split("/")).replace("\\", "/")
                nombre = os.path.basename(a)
                contenido_arranque += f'(princ (load "{ruta_lisp}" "\\n[X] SINCAL: Fallo al cargar {nombre}"))\n'

        if "startup/SINCAL_STARTUP.lsp" in archivos or "SINCAL_STARTUP.lsp" in archivos:
            contenido_arranque += '(princ "\\n[SINCAL] Políticas de empresa y variables aplicadas.")\n'

        contenido_arranque += '(princ "\\n[OK] SINCAL: Todos los LISPs procesados correctamente.")\n(princ)\n'

        r_acad = ruta_cad_usuario("acaddoc.lsp")
        r_zwcad = ruta_cad_usuario("zwcaddoc.lsp")

        with open(r_acad, 'w', encoding='utf-8') as f:
            f.write(contenido_arranque)

        with open(r_zwcad, 'w', encoding='utf-8') as f:
            f.write(contenido_arranque)

    # ==========================================================
    # SISTEMA DE LOGS Y CONSOLA FLOTANTE
    # ==========================================================
    def log(self, m):
        self.logger.info(m)
        self.escribir_en_consola_global(m)

    def log_r(self, m):
        self.logger.info(m)
        self.escribir_en_consola_global("[PROCESAMIENTO MASIVO] " + m)

    def log_script(self, texto):
        self.logger.info(texto.strip())
        self.escribir_en_consola_global(texto.strip('\n'))

    def escribir_en_consola_global(self, m):
        self.historial_logs.append(m)
        if hasattr(self, 'txt_log_global'):
            self._ui(self._append_if_exists, self.txt_log_global, m + "\n")

    def _append_if_exists(self, widget, texto):
        if widget.winfo_exists():
            self._append_textbox(widget, texto)

def arrancar():
    app = ActualizadorCAD()
    app.mainloop()
