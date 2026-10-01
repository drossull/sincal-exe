import json
import math
import os
import threading
import time
import tkinter as tk
import uuid
from dataclasses import asdict
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk
import ttkbootstrap as ttk
from PIL import Image
from ttkbootstrap.widgets import ToolTip
from ttkbootstrap.widgets.tableview import Tableview
from sincal.ui.scroll import SafeScrollableFrame
from sincal.ui.widgets import ShadowButton

from sincal.cad.moldajes import parse_moldaje_detection
from sincal.rebar.model import (
    CAPAS_ZAPATA,
    Cover,
    RebarRule,
    ZapataGeometry,
    build_zapata_schedule,
    default_zapata_rules,
)
from sincal.cad.zapata_views import ZapataCadError, build_zapata_lisp
from sincal.cad.zapata_detail import build_zapata_detail_lisp
from sincal.rebar.detail import build_detail_groups, polyline_render_points
from sincal.runtime import ruta_recurso, ruta_runtime
from sincal.sessions import sha256_file
from sincal.ui.theme import (
    COLOR_ACENTO,
    COLOR_ACENTO_HOVER,
    COLOR_BORDE,
    COLOR_FONDO,
    COLOR_GRIS_BOTON,
    COLOR_GRIS_BOTON_HOVER,
    COLOR_MOSTAZA,
    COLOR_PANEL,
    COLOR_TEXTO_SUAVE,
    FUENTE_TTK_CAMPO as FUENTE_CAMPO,
    FUENTE_NORMAL,
    FUENTE_NORMAL_PEQUENA,
    FUENTE_SUBTITULO,
    RADIO_CONTROL,
    RADIO_PANEL,
)

RUTA_TEMPORAL = ruta_runtime()

SIGLAS_ZAPATA = {
    "FR_ZAP": "Vista frontal del moldaje de zapata.",
    "AA_ZAP": "Sección longitudinal A-A por el centro del estribo.",
    "BB_ZAP": "Sección B-B observada desde el extremo izquierdo.",
    "CC_ZAP": "Sección C-C observada desde el extremo derecho.",
    "DD_ZAP": "Sección horizontal D-D por los muros del estribo.",
    "EE_ZAP": "Sección E-E: planta de la fundación.",
}


class TabArmaduras(ctk.CTkFrame):
    def __init__(self, master, parent_app, project_context=None, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.project_context = project_context
        self._abutments = {}
        self._session_metadata = {}
        self._session_path = None
        self._session_dirty = False
        self._restoring_session = False
        self._json_path = ""
        self._json_snapshot = None
        self._json_sha256 = ""
        self.setup_ui()
        self._blank_workspace = self._capture_workspace()
        self._bind_session_change_tracking()
        self._autosave_job = self.after(60_000, self._autosave_tick)
        self.after(1_200, self._comprobar_recuperacion_pendiente)

    def setup_ui(self):
        # --- Frame Superior: JSON ---
        frame_top = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        frame_top.pack(fill="x", padx=20, pady=(12, 6))
        frame_top.grid_columnconfigure(0, weight=1)

        fuente_subtitulo = FUENTE_SUBTITULO
        fuente_normal = FUENTE_NORMAL

        ctk.CTkLabel(frame_top, text="GENERADOR DE ARMADURA",
                     font=fuente_subtitulo, text_color=COLOR_MOSTAZA).grid(
                         row=0, column=0, sticky="w", padx=8, pady=(2, 10))

        session_row = ctk.CTkFrame(frame_top, fg_color="transparent", corner_radius=0)
        session_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.btn_abrir_sesion = ShadowButton(
            session_row, text="Abrir sesión", font=fuente_normal,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=self.abrir_biblioteca_sesiones,
        )
        self.btn_abrir_sesion.pack(side="left")
        self.btn_guardar_sesion = ShadowButton(
            session_row, text="Guardar sesión", font=fuente_normal,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, state="disabled", command=self.guardar_sesion,
        )
        self.btn_guardar_sesion.pack(side="left", padx=(8, 0))
        self.btn_nueva_sesion = ShadowButton(
            session_row, text="Nueva sesión", font=fuente_normal,
            fg_color="transparent", hover_color=COLOR_GRIS_BOTON,
            corner_radius=0, state="disabled", command=self.nueva_sesion,
        )
        self.btn_nueva_sesion.pack(side="left", padx=(8, 0))
        self.lbl_session_status = ctk.CTkLabel(
            session_row, text="Sin sesión activa", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE, anchor="w",
        )
        self.lbl_session_status.pack(side="left", padx=(14, 0))

        project_row = ctk.CTkFrame(frame_top, fg_color="transparent", corner_radius=0)
        project_row.grid(row=2, column=0, sticky="ew")
        project_row.grid_columnconfigure(2, weight=1)

        self.lbl_json_status = ctk.CTkLabel(
            project_row, text="Proyecto: ninguno", font=fuente_normal,
            text_color=COLOR_TEXTO_SUAVE, anchor="w", justify="left", wraplength=430)
        self.lbl_json_status.grid(row=0, column=2, sticky="ew", padx=(14, 4))
        ShadowButton(
            project_row, text="Ir a Consulta", font=FUENTE_NORMAL_PEQUENA,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0,
            command=lambda: self.parent_app.seleccionar_seccion("consulta"),
        ).grid(row=0, column=3, sticky="e", padx=(8, 0))
        self.ent_z_esviaje = ttk.Entry(
            project_row, width=7, font=FUENTE_CAMPO, bootstyle="secondary")
        self.ent_z_esviaje.insert(0, "0")
        self.ent_z_esviaje.grid(row=0, column=1, sticky="w", padx=(4, 0))
        ctk.CTkLabel(project_row, text="Esviaje (°):", font=FUENTE_NORMAL_PEQUENA,
                     text_color=COLOR_TEXTO_SUAVE).grid(row=0, column=0, sticky="w")

        # =========================================================
        # NOTEBOOK MAESTRO (Elementos Estructurales)
        # =========================================================
        self.tab_maestro = ttk.Notebook(self, bootstyle="primary")
        self.tab_maestro.pack(padx=20, pady=5, fill="both", expand=True)
        tab_estribos = ctk.CTkFrame(self.tab_maestro, fg_color=COLOR_FONDO, corner_radius=0)
        tab_travesanos = ctk.CTkFrame(self.tab_maestro, fg_color=COLOR_FONDO, corner_radius=0)
        self.tab_maestro.add(tab_estribos, text="ESTRIBOS")
        self.tab_maestro.add(tab_travesanos, text="TRAVESAÑOS")
        ttk.Separator(tab_estribos, orient="horizontal", bootstyle="secondary").pack(
            fill="x", padx=8, pady=(8, 4))
        ttk.Separator(tab_travesanos, orient="horizontal", bootstyle="secondary").pack(
            fill="x", padx=8, pady=(8, 4))

        # =========================================================
        # CONTENIDO: 1. ESTRIBOS
        # =========================================================
        self.tab_estribo = ttk.Notebook(tab_estribos, bootstyle="secondary")
        self.tab_estribo.pack(fill="both", expand=True)
        tab_entrada = ctk.CTkFrame(self.tab_estribo, fg_color=COLOR_PANEL, corner_radius=0)
        tab_salida = ctk.CTkFrame(self.tab_estribo, fg_color=COLOR_PANEL, corner_radius=0)
        self.tab_estribo.add(tab_entrada, text="Estribo de entrada")
        self.tab_estribo.add(tab_salida, text="Estribo de salida")
        self._setup_abutment_page(tab_entrada, "entrada", "ESTRIBO DE ENTRADA")
        self._setup_abutment_page(tab_salida, "salida", "ESTRIBO DE SALIDA")

        # =========================================================
        # CONTENIDO: 2. TRAVESAÑOS
        # =========================================================
        self.tab_sub_travesanos = ttk.Notebook(tab_travesanos, bootstyle="secondary")
        self.tab_sub_travesanos.pack(fill="both", expand=True)
        tab_trav_host = ctk.CTkFrame(
            self.tab_sub_travesanos, fg_color=COLOR_PANEL, corner_radius=0)
        self.tab_sub_travesanos.add(
            tab_trav_host, text="Configuración y generación")
        tab_trav_main = SafeScrollableFrame(
            tab_trav_host, fg_color=COLOR_PANEL, corner_radius=0,
            scrollbar_button_color=COLOR_GRIS_BOTON,
            scrollbar_button_hover_color=COLOR_GRIS_BOTON_HOVER)
        tab_trav_main.pack(fill="both", expand=True)

        # --- I. PARÁMETROS GLOBALES ---
        frame_params = ctk.CTkFrame(tab_trav_main, fg_color="transparent")
        frame_params.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_params, text="I. PARÁMETROS GLOBALES:", font=fuente_subtitulo,
                     text_color=COLOR_ACENTO).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        btn_ayuda = ShadowButton(frame_params, text="?  Abrir ayuda", font=fuente_normal, width=100,
                                  fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
                                  corner_radius=0, border_width=1, border_color=COLOR_BORDE,
                                  command=self.mostrar_ayuda_travesano)
        btn_ayuda.grid(row=0, column=4, columnspan=2,
                       sticky="e", padx=5, pady=(0, 10))

        ctk.CTkLabel(frame_params, text="Recubrimiento general (cm):", font=fuente_normal).grid(
            row=1, column=0, sticky="w", padx=5, pady=5)
        self.ent_t_rec = ttk.Spinbox(
            frame_params, from_=0, to=30, increment=0.5, width=7,
            font=FUENTE_CAMPO, bootstyle="secondary")
        self.ent_t_rec.grid(row=1, column=1, padx=5, pady=5)
        self.ent_t_rec.insert(0, "2.5")

        ctk.CTkLabel(frame_params, text="Espesor del travesaño (cm):", font=fuente_normal).grid(
            row=1, column=2, sticky="w", padx=20, pady=5)
        self.ent_t_espesor = ttk.Spinbox(
            frame_params, from_=1, to=1000, increment=1, width=7,
            font=FUENTE_CAMPO, bootstyle="secondary")
        self.ent_t_espesor.grid(row=1, column=3, padx=5, pady=5)
        self.ent_t_espesor.insert(0, "25")

        ctk.CTkLabel(frame_params, text="Ángulo de esviaje (°):", font=fuente_normal).grid(
            row=1, column=4, sticky="w", padx=20, pady=5)
        self.ent_t_esviaje = ttk.Entry(
            frame_params, width=7, font=FUENTE_CAMPO, bootstyle="secondary")
        self.ent_t_esviaje.grid(row=1, column=5, padx=5, pady=5)
        self.ent_t_esviaje.insert(0, "0")

        ctk.CTkLabel(frame_params, text="Ø Fierros externos (mm):", font=fuente_normal).grid(
            row=2, column=0, sticky="w", padx=5, pady=5)
        self.ent_t_phi_ext = ttk.Spinbox(
            frame_params, values=(12, 16, 18, 22, 25, 28, 32, 36), width=7,
            font=FUENTE_CAMPO, bootstyle="secondary")
        self.ent_t_phi_ext.grid(row=2, column=1, padx=5, pady=5)
        self.ent_t_phi_ext.insert(0, "22")

        ctk.CTkLabel(frame_params, text="Ø Fierros horizontales (mm):", font=fuente_normal).grid(
            row=2, column=2, sticky="w", padx=20, pady=5)
        self.ent_t_phi_horiz = ttk.Spinbox(
            frame_params, values=(12, 16, 18, 22, 25, 28, 32, 36), width=7,
            font=FUENTE_CAMPO, bootstyle="secondary")
        self.ent_t_phi_horiz.grid(row=2, column=3, padx=5, pady=5)
        self.ent_t_phi_horiz.insert(0, "12")

        ctk.CTkLabel(frame_params, text="Ø Estribos (mm):", font=fuente_normal).grid(
            row=2, column=4, sticky="w", padx=20, pady=5)
        self.ent_t_phi_estr = ttk.Spinbox(
            frame_params, values=(12, 16, 18, 22, 25, 28, 32, 36), width=7,
            font=FUENTE_CAMPO, bootstyle="secondary")
        self.ent_t_phi_estr.grid(row=2, column=5, padx=5, pady=5)
        self.ent_t_phi_estr.insert(0, "12")

        ctk.CTkLabel(frame_params, text="Longitud fierros viga (cm):", font=fuente_normal).grid(
            row=3, column=0, sticky="w", padx=5, pady=5)
        self.ent_viga_largo = ttk.Spinbox(
            frame_params, from_=1, to=1200, increment=1, width=7,
            font=FUENTE_CAMPO, bootstyle="secondary")
        self.ent_viga_largo.grid(row=3, column=1, padx=5, pady=5)
        self.ent_viga_largo.insert(0, "200")

        ctk.CTkLabel(frame_params, text="Cantidad de travesaños:", font=fuente_normal).grid(
            row=3, column=2, sticky="w", padx=20, pady=5)
        self.ent_t_cantidad = ttk.Spinbox(
            frame_params, from_=1, to=100, increment=1, width=7,
            font=FUENTE_CAMPO, bootstyle="secondary")
        self.ent_t_cantidad.grid(row=3, column=3, padx=5, pady=5)
        self.ent_t_cantidad.insert(0, "1")

        # --- II. HERRAMIENTAS DE GENERACIÓN ---
        frame_botones_t = ctk.CTkFrame(tab_trav_main, fg_color="transparent")
        frame_botones_t.pack(fill="x", padx=10, pady=15)

        ctk.CTkLabel(frame_botones_t, text="II. SELECCIÓN DE CUADRANTE (AutoCAD):", font=fuente_subtitulo,
                     text_color=COLOR_ACENTO).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        def crear_btn_cuadrante(parent, texto, comando_gen, comando_desp, fila, col, colspan=1, is_viga=False):
            frm = ctk.CTkFrame(parent, fg_color="transparent")
            frm.grid(row=fila, column=col, columnspan=colspan,
                     padx=5, pady=5, sticky="ew")

            hover_c = COLOR_MOSTAZA if is_viga else COLOR_ACENTO
            text_c = COLOR_FONDO if is_viga else COLOR_TEXTO_SUAVE

            btn_gen = ShadowButton(frm, text=texto, font=fuente_normal, fg_color=COLOR_GRIS_BOTON,
                                    hover_color=hover_c, text_color=text_c, corner_radius=0, command=comando_gen)
            btn_gen.pack(side="left", expand=True, fill="x")

            btn_desp = ShadowButton(frm, text="D", font=fuente_subtitulo, corner_radius=0, width=30,
                                     fg_color=COLOR_ACENTO, hover_color=COLOR_ACENTO_HOVER, text_color=COLOR_FONDO,
                                     command=comando_desp)
            btn_desp.pack(side="right", padx=(2, 0))
            return frm

        crear_btn_cuadrante(frame_botones_t, "1. Extremo Izquierdo",
                            lambda: self.generar_travesano_cad("EXT_IZQ"),
                            lambda: self.generar_despiece_travesano_cad("EXT_IZQ"), 1, 0)

        crear_btn_cuadrante(frame_botones_t, "2. Extremo Derecho",
                            lambda: self.generar_travesano_cad("EXT_DER"),
                            lambda: self.generar_despiece_travesano_cad("EXT_DER"), 1, 1)

        crear_btn_cuadrante(frame_botones_t, "3. Cuadrante sobre Tope",
                            lambda: self.generar_travesano_cad("INT_TOPE"),
                            lambda: self.generar_despiece_travesano_cad("INT_TOPE"), 2, 0)

        crear_btn_cuadrante(frame_botones_t, "4. Cuadrante Macizo",
                            lambda: self.generar_travesano_cad("INT_MACIZO"),
                            lambda: self.generar_despiece_travesano_cad("INT_MACIZO"), 2, 1)

        crear_btn_cuadrante(frame_botones_t, "5. Cuadrante Viga",
                            lambda: self.generar_travesano_cad("INT_VIGA"),
                            lambda: self.generar_despiece_travesano_cad("INT_VIGA"), 3, 0, colspan=2, is_viga=True)

        frame_botones_t.grid_columnconfigure(0, weight=1)
        frame_botones_t.grid_columnconfigure(1, weight=1)
        for notebook in (self.tab_maestro, self.tab_estribo, self.tab_sub_travesanos):
            notebook.bind("<<NotebookTabChanged>>", self.actualizar_breadcrumb, add="+")
        self.after_idle(self.actualizar_breadcrumb)

    def actualizar_breadcrumb(self, _event=None):
        """Sincroniza la ruta superior con los notebooks estructurales."""
        try:
            main_text = self.tab_maestro.tab(self.tab_maestro.select(), "text")
        except Exception:
            return
        if main_text == "ESTRIBOS":
            detail = self.tab_estribo.tab(self.tab_estribo.select(), "text")
            segments = ("Proyecto", "Generador de armadura", "Estribos", detail)
        else:
            detail = self.tab_sub_travesanos.tab(self.tab_sub_travesanos.select(), "text")
            segments = ("Proyecto", "Generador de armadura", "Travesaños", detail)
        if self.parent_app._sections.get("estructural", (None,))[0].winfo_manager():
            self.parent_app.actualizar_ruta_interna(*segments)

    def ir_a_seccion(self, anchor):
        """Desplaza la página del estribo actual desde el índice contextual."""
        if self.tab_maestro.tab(self.tab_maestro.select(), "text") != "ESTRIBOS":
            return
        key = "entrada" if self.tab_estribo.index("current") == 0 else "salida"
        state = self._abutments[key]
        target = {
            "dimensiones": state.get("configuration_panel"),
            "revision": state.get("revision_panel"),
            "despiece": state.get("geometry_group"),
        }.get(anchor)
        page = state.get("page")
        if target is None or page is None:
            return
        page.update_idletasks()
        total = max(1, page.winfo_reqheight())
        page._parent_canvas.yview_moveto(max(0.0, min(1.0, target.winfo_y() / total)))

    def _setup_abutment_page(self, parent, key, title):
        """Construye un estribo independiente en un panel redimensionable."""
        state = {
            "key": key,
            "title": title,
            "entries": {},
            "rule_widgets": {},
            "schedule": None,
            "moldaje_option_vars": {},
            "moldaje_choices": {},
            "confirmed_moldajes": {},
            "moldajes_use_metres": False,
            "generated_views": set(),
            "detail_generated": False,
        }
        self._abutments[key] = state

        ttk.Separator(parent, orient="horizontal", bootstyle="secondary").pack(
            fill="x", padx=10, pady=(8, 0))
        page = SafeScrollableFrame(
            parent, fg_color=COLOR_FONDO, corner_radius=0,
            scrollbar_button_color=COLOR_GRIS_BOTON,
            scrollbar_button_hover_color=COLOR_GRIS_BOTON_HOVER)
        page.pack(fill="both", expand=True, padx=10, pady=10)
        configuration_pane = self._labelframe(
            page, "1. DIMENSIONES Y CONFIGURACIÓN")
        configuration_pane.pack(fill="x", padx=2, pady=(2, 10))
        revision_pane = self._labelframe(page, "2. REVISIÓN Y MARCAS")
        revision_pane.pack(fill="x", padx=2, pady=(0, 10))
        configuration = ctk.CTkFrame(
            configuration_pane, fg_color=COLOR_FONDO, corner_radius=0,
        )
        configuration.pack(fill="both", expand=True)
        revision = ctk.CTkFrame(
            revision_pane, fg_color=COLOR_FONDO, corner_radius=0)
        revision.pack(fill="both", expand=True)
        state["parent"] = parent
        state["page"] = page
        state["revision_panel"] = revision_pane
        state["configuration_panel"] = configuration_pane

        self._setup_abutment_configuration(configuration, state)
        self._setup_zapata_revision(revision, state)
        self.actualizar_revision_zapata(key, notificar=False)

    @staticmethod
    def _section_heading(parent, text):
        ttk.Separator(parent, orient="horizontal", bootstyle="secondary").pack(
            fill="x", padx=8, pady=(14, 2))
        label = ctk.CTkLabel(
            parent, text=text, font=FUENTE_SUBTITULO, text_color=COLOR_MOSTAZA,
        )
        label.pack(anchor="w", padx=8, pady=(4, 6))
        if "CONTRAFUERTE" in text:
            ToolTip(label, text="CTF: contrafuerte del estribo.", bootstyle="info-inverse")

    @staticmethod
    def _labelframe(parent, title, bootstyle="secondary"):
        """Crea un LabelFrame cuyo rótulo también tiene un marco visible."""
        label = ttk.Label(
            parent, text=title, style="SincalLabelframeTitle.TLabel")
        return ttk.Labelframe(
            parent, labelwidget=label, bootstyle=bootstyle)

    def _labeled_entry(
        self, parent, state, key, label, default, row, column, increment=0.5
    ):
        ctk.CTkLabel(parent, text=label, font=FUENTE_NORMAL).grid(
            row=row, column=column, sticky="w", padx=(0, 6), pady=4)
        entry = ttk.Spinbox(
            parent, from_=0, to=100000, increment=increment, width=10,
            font=FUENTE_CAMPO, bootstyle="secondary")
        entry.insert(0, default)
        entry.grid(row=row, column=column + 1, sticky="w", padx=(0, 14), pady=4)
        state["entries"][key] = entry
        return entry

    def _setup_abutment_configuration(self, parent, state):
        """Página única desplazable: zapata, muros, consolas, topes y contrafuerte."""
        ctk.CTkLabel(
            parent, text=state["title"], font=FUENTE_SUBTITULO, text_color=COLOR_MOSTAZA,
        ).pack(anchor="w", padx=8, pady=(4, 0))
        ctk.CTkLabel(
            parent,
            text="Geometría y criterios del elemento. Las armaduras se editan una sola vez en Revisión y marcas.",
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
            justify="left", wraplength=640,
        ).pack(anchor="w", padx=8, pady=(2, 8))

        geometry_group = self._labelframe(parent, "ZAPATA")
        state["geometry_group"] = geometry_group
        geometry_group.pack(fill="x", padx=8, pady=(8, 4))
        geometry = ctk.CTkFrame(
            geometry_group, fg_color=COLOR_FONDO, corner_radius=0)
        geometry.pack(fill="x", padx=8, pady=8)
        self._labeled_entry(
            geometry, state, "largo", "Largo (cm):", "750", 0, 0, increment=100)
        self._labeled_entry(
            geometry, state, "ancho", "Ancho (cm):", "1159.6", 0, 2, increment=100)
        self._labeled_entry(
            geometry, state, "alto", "Alto (cm):", "150", 1, 0, increment=50)
        self._labeled_entry(
            geometry, state, "rec_inf", "Rec. inferior (cm):", "7.5", 2, 0, increment=0.5)
        self._labeled_entry(
            geometry, state, "rec_sup", "Rec. superior (cm):", "5", 2, 2, increment=0.5)
        self._labeled_entry(
            geometry, state, "rec_lat", "Rec. lateral (cm):", "5", 3, 0, increment=0.5)

        ctk.CTkLabel(
            geometry, text="Vistas y despieces", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE,
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(14, 5))
        views = (
            ("Frontal", "FR"), ("A-A", "AA"), ("B-B", "BB"),
            ("C-C", "CC"), ("D-D", "DD"), ("E-E", "EE"),
        )
        view_buttons = ttk.Frame(geometry)
        view_buttons.grid(row=5, column=0, columnspan=4, sticky="w")
        for index, (text, view) in enumerate(views):
            row = index // 3
            column = index % 3
            ShadowButton(
                view_buttons, text=text, width=82, height=30,
                font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
                hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=RADIO_CONTROL,
                command=lambda v=view, k=state["key"]: self.generar_vista_cad(v, k),
            ).grid(row=row, column=column, padx=(0, 5), pady=3)
        ShadowButton(
            geometry, text="Generar despiece general de zapata", width=270,
            font=FUENTE_NORMAL, fg_color=COLOR_ACENTO,
            hover_color=COLOR_ACENTO_HOVER, corner_radius=RADIO_CONTROL,
            command=lambda k=state["key"]: self.generar_despiece_zapata(k),
        ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(10, 3))

        pending_sections = (
            ("MUROS", "Muro frontal, muro espaldar y alas."),
            ("CONSOLAS", "Consola de muro espaldar y consola frontal opcional."),
            ("TOPES", "Topes sísmicos del estribo."),
            ("CONTRAFUERTE", "Contrafuerte opcional (CTF)."),
        )
        for title, description in pending_sections:
            group = self._labelframe(parent, title)
            group.pack(fill="x", padx=8, pady=5)
            ttk.Separator(group, orient="horizontal", bootstyle="secondary").pack(
                fill="x", padx=8, pady=(5, 2))
            ctk.CTkLabel(
                group, text=f"{description} Configuración pendiente de la lógica de armaduras.",
                font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
                justify="left", wraplength=640,
            ).pack(anchor="w", padx=8, pady=(2, 10))

    def _setup_zapata_revision(self, parent, state):
        """Tabla editable y única de armadura para un estribo."""
        ctk.CTkLabel(
            parent, text="ARMADURAS Y MARCAS", font=FUENTE_SUBTITULO,
            text_color=COLOR_MOSTAZA,
        ).pack(anchor="w", padx=14, pady=(14, 2))
        ctk.CTkLabel(
            parent,
            text=(f"{state['title'].title()}: set independiente. Cada barra física se calcula una sola vez; "
                  "las vistas no vuelven a sumar acero."),
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
            justify="left", wraplength=600,
        ).pack(anchor="w", padx=14, pady=(0, 10))

        detector_group = self._labelframe(parent, "MOLDAJES CAD — DIBUJO ACTIVO")
        detector_group.pack(fill="x", padx=14, pady=(0, 8))
        detector = ctk.CTkFrame(
            detector_group, fg_color=COLOR_FONDO, corner_radius=0)
        detector.pack(fill="x", padx=8, pady=8)
        detect_button = ShadowButton(
            detector, text="Detectar moldajes", font=FUENTE_NORMAL, corner_radius=0,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            command=lambda k=state["key"]: self.detectar_moldajes_cad(k),
        )
        detect_button.grid(row=0, column=0, sticky="w", padx=(0, 10))
        confirm_button = ShadowButton(
            detector, text="Confirmar selección", font=FUENTE_NORMAL, corner_radius=0,
            fg_color="transparent", border_width=1, border_color=COLOR_ACENTO,
            hover_color=COLOR_GRIS_BOTON,
            command=lambda k=state["key"]: self.confirmar_moldajes_cad(k),
        )
        confirm_button.grid(row=0, column=1, sticky="w")
        moldaje_status = ctk.CTkLabel(
            detector, text="Sin lectura CAD.", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE,
        )
        moldaje_status.grid(row=0, column=2, columnspan=2, sticky="w", padx=12)

        for index, layer in enumerate(CAPAS_ZAPATA):
            row = 1 + index
            column = 0
            layer_label = ctk.CTkLabel(
                detector, text=layer, font=FUENTE_NORMAL_PEQUENA)
            layer_label.grid(row=row, column=column, sticky="w", padx=(0, 5), pady=3)
            ToolTip(
                layer_label, text=SIGLAS_ZAPATA[layer], wraplength=320,
                bootstyle="info-inverse")
            value = ctk.StringVar(value="Sin detectar")
            option = ctk.CTkOptionMenu(
                detector, variable=value, values=["Sin detectar"], width=300,
                font=FUENTE_NORMAL_PEQUENA, corner_radius=0,
                fg_color=COLOR_GRIS_BOTON, button_color=COLOR_GRIS_BOTON_HOVER,
            )
            option.grid(row=row, column=column + 1, columnspan=3, sticky="ew", padx=(0, 5), pady=3)
            state["moldaje_option_vars"][layer] = (value, option)

        table_group = self._labelframe(parent, "PARÁMETROS DE ARMADURA")
        table_group.pack(fill="x", padx=14, pady=(0, 8))
        table = ctk.CTkFrame(
            table_group, fg_color=COLOR_FONDO, corner_radius=0)
        table.pack(fill="x", padx=8, pady=8)
        headers = ("Grupo", "Marca base", "Ø mm", "@ cm", "Gancho cm", "Origen", "Activo")
        for column, text in enumerate(headers):
            header = ctk.CTkLabel(
                table, text=text, font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_ACENTO,
            )
            header.grid(row=0, column=column, sticky="w", padx=5, pady=(0, 4))
            if text == "Ø mm":
                ToolTip(header, text="Diámetro nominal del fierro en milímetros.")
            elif text == "@ cm":
                ToolTip(header, text="Separación entre fierros, medida en centímetros.")
            elif text == "Gancho cm":
                ToolTip(header, text="Largo recto del gancho en centímetros; 0 usa el cálculo automático.")
            elif text == "Origen":
                ToolTip(header, text="Extremo desde el cual comienza la distribución de barras.")
            elif text == "Activo":
                ToolTip(header, text="Incluye o excluye este grupo del cálculo y del dibujo.")

        for row, rule in enumerate(default_zapata_rules(), 1):
            ctk.CTkLabel(table, text=rule.label, font=FUENTE_NORMAL, anchor="w").grid(
                row=row, column=0, sticky="ew", padx=5, pady=3)
            widgets = {}
            mark_entry = ttk.Entry(table, width=8, font=FUENTE_CAMPO, bootstyle="secondary")
            mark_entry.insert(0, rule.mark)
            mark_entry.grid(row=row, column=1, sticky="w", padx=5, pady=3)
            widgets["mark"] = mark_entry
            diameter = ttk.Combobox(
                table, values=(12, 16, 18, 22, 25, 28, 32, 36), width=6,
                font=FUENTE_CAMPO, bootstyle="secondary", state="readonly")
            diameter.set(f"{rule.diameter_mm:g}")
            diameter.grid(row=row, column=2, sticky="w", padx=5, pady=3)
            widgets["diameter"] = diameter
            spacing = ttk.Entry(
                table, width=6, font=FUENTE_CAMPO, bootstyle="secondary")
            spacing.insert(0, f"{rule.spacing_cm:g}")
            spacing.grid(row=row, column=3, sticky="w", padx=5, pady=3)
            widgets["spacing"] = spacing
            hook = ttk.Entry(
                table, width=8, font=FUENTE_CAMPO, bootstyle="secondary")
            hook.insert(0, f"{rule.hook_cm:g}")
            hook.grid(row=row, column=4, sticky="w", padx=5, pady=3)
            widgets["hook"] = hook
            enabled = ctk.BooleanVar(value=rule.enabled)
            origin = ctk.StringVar(value=rule.origin.title())
            origin_frame = ttk.Frame(table)
            origin_frame.grid(row=row, column=5, sticky="w", padx=5, pady=3)
            start_radio = ttk.Radiobutton(
                origin_frame, text="I", value="Inicio", variable=origin,
                bootstyle="primary-toolbutton")
            end_radio = ttk.Radiobutton(
                origin_frame, text="F", value="Final", variable=origin,
                bootstyle="primary-toolbutton")
            start_radio.pack(side="left")
            end_radio.pack(side="left", padx=(2, 0))
            ToolTip(start_radio, text="I: distribuir desde el inicio topológico.")
            ToolTip(end_radio, text="F: distribuir desde el final topológico.")
            active_toggle = ttk.Checkbutton(
                table, text="", variable=enabled, bootstyle="success-round-toggle")
            active_toggle.grid(row=row, column=6, sticky="w", padx=5, pady=3)
            ToolTip(active_toggle, text="Activar o desactivar este grupo de fierros.")
            widgets["enabled"] = enabled
            widgets["origin"] = origin
            widgets["template"] = rule
            state["rule_widgets"][rule.key] = widgets

        controls = ctk.CTkFrame(parent, fg_color="transparent")
        controls.pack(fill="x", padx=14, pady=(0, 8))
        ShadowButton(
            controls, text="Actualizar revisión", width=150,
            font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
            hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=RADIO_CONTROL,
            command=lambda k=state["key"]: self.actualizar_revision_zapata(k),
        ).pack(side="left")
        ShadowButton(
            controls, text="Vista previa completa", width=165,
            font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
            hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=RADIO_CONTROL,
            command=lambda k=state["key"]: self.mostrar_vista_previa_marcas(k),
        ).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(
            controls, text="Gancho 0 = automático. Suple 3-A es opcional.",
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="left", padx=12)

        state["review_progress"] = ttk.Progressbar(
            parent, mode="determinate", maximum=100, value=0,
            bootstyle="success-striped")
        state["review_progress"].pack(fill="x", padx=14, pady=(2, 6))
        state["revision_status"] = ctk.CTkLabel(
            parent, text="Sin calcular.", font=FUENTE_NORMAL,
            text_color=COLOR_TEXTO_SUAVE, justify="left", anchor="nw",
            wraplength=620,
        )
        state["revision_status"].pack(fill="both", expand=True, padx=14, pady=(0, 14))
        state["moldaje_status"] = moldaje_status

    @staticmethod
    def _entry_number(entry, label):
        raw = entry.get().strip().replace(",", ".")
        try:
            return float(raw)
        except ValueError as error:
            raise ValueError(f"{label} debe ser numérico.") from error

    @staticmethod
    def _lisp_detector_moldajes(ruta_salida):
        ruta_lisp = ruta_salida.replace("\\", "\\\\")
        layers = " ".join(f'\"{layer}\"' for layer in CAPAS_ZAPATA)
        return f'''(vl-load-com)
(defun sincal:vertices (data)
  (length (vl-remove-if-not '(lambda (pair) (= (car pair) 10)) data))
)
(defun sincal:cerrada-p (data)
  (/= 0 (logand 1 (cdr (assoc 70 data))))
)
(defun sincal:arco-p (data / found)
  (setq found nil)
  (foreach pair data
    (if (and (= (car pair) 42) (> (abs (cdr pair)) 0.0000001)) (setq found T))
  )
  found
)
(defun sincal:vertices-text (data / result point)
  (setq result "")
  (foreach pair data
    (if (= (car pair) 10)
      (progn
        (setq point (cdr pair))
        (setq result
          (strcat result (if (= result "") "" ";")
                  (rtos (car point) 2 9) "," (rtos (cadr point) 2 9)))
      )
    )
  )
  result
)
(defun c:SINCAL-DETECTAR-ZAPATA (/ out layer ss index ent data status count obj area-result area)
  (setq out (open "{ruta_lisp}" "w"))
  (write-line "SINCAL_MOLDAJES_V1" out)
  (write-line (strcat "META|INSUNITS|" (itoa (getvar "INSUNITS"))) out)
  (foreach layer '({layers})
    (setq ss (ssget "_X" (list (cons 0 "LWPOLYLINE") (cons 8 layer))))
    (if ss
      (progn
        (setq index 0)
        (repeat (sslength ss)
          (setq ent (ssname ss index) data (entget ent) count (sincal:vertices data))
          (cond
            ((not (sincal:cerrada-p data)) (setq status "OPEN"))
            ((sincal:arco-p data) (setq status "ARC"))
            ((< count 3) (setq status "INVALID"))
            (T (setq status "OK"))
          )
          (setq obj (vlax-ename->vla-object ent))
          (setq area-result (vl-catch-all-apply 'vla-get-Area (list obj)))
          (setq area (if (vl-catch-all-error-p area-result) 0.0 area-result))
          (write-line
            (strcat "CANDIDATE|" layer "|" (cdr (assoc 5 data)) "|" status "|"
                    (itoa count) "|" (rtos area 2 6)) out)
          (write-line
            (strcat "VERTICES|" layer "|" (cdr (assoc 5 data)) "|"
                    (sincal:vertices-text data)) out)
          (setq index (1+ index))
        )
      )
      (write-line (strcat "CANDIDATE|" layer "||MISSING|0|0.0") out)
    )
  )
  (close out)
  (princ "\\n[SINCAL] Lectura de moldajes terminada. Vuelva a SINCAL para confirmar.")
  (princ)
)'''

    def detectar_moldajes_cad(self, abutment_key="entrada"):
        state = self._abutments[abutment_key]
        if not hasattr(self.parent_app, "enviar_comando_cad_activo"):
            messagebox.showerror("Workbench", "La versión actual no admite lectura del dibujo CAD activo.")
            return
        token = str(int(time.time() * 1000))
        ruta_salida = ruta_runtime(f"moldajes_zapata_{token}.txt")
        ruta_lisp = ruta_runtime(f"SINCAL_DETECTAR_ZAPATA_{token}.lsp")
        try:
            with open(ruta_lisp, "w", encoding="utf-8") as archivo:
                archivo.write(self._lisp_detector_moldajes(ruta_salida))
            if os.path.exists(ruta_salida):
                os.remove(ruta_salida)
        except OSError as error:
            messagebox.showerror("Workbench", f"No se pudo preparar la lectura CAD:\n{error}")
            return

        state["confirmed_moldajes"] = {}
        state["moldaje_result_path"] = ruta_salida
        state["moldaje_deadline"] = time.monotonic() + 18
        state["moldaje_status"].configure(text="Leyendo dibujo activo…", text_color=COLOR_ACENTO)
        self.parent_app.iniciar_actividad(
            f"moldajes_{abutment_key}",
            f"Detectando moldajes · {state['title']}",
        )
        ruta_cad = ruta_lisp.replace("\\", "\\\\")
        comando = f'(progn (load "{ruta_cad}") (c:SINCAL-DETECTAR-ZAPATA))\n'
        self.parent_app.enviar_comando_cad_activo(
            comando, f"Lectura de moldajes de zapata ({state['title'].lower()})")
        self.after(400, lambda k=abutment_key: self._esperar_moldajes_cad(k))

    def _esperar_moldajes_cad(self, abutment_key):
        state = self._abutments[abutment_key]
        ruta = state.get("moldaje_result_path", "")
        if ruta and os.path.isfile(ruta):
            try:
                with open(ruta, "r", encoding="utf-8") as archivo:
                    detection = parse_moldaje_detection(archivo.read())
            except (OSError, ValueError) as error:
                state["moldaje_status"].configure(
                    text=f"Error leyendo resultado: {error}", text_color="#D06A5D")
                self.parent_app.finalizar_actividad(f"moldajes_{abutment_key}")
                return
            self._aplicar_moldajes_detectados(detection, abutment_key)
            self.parent_app.finalizar_actividad(f"moldajes_{abutment_key}")
            return
        if time.monotonic() < state.get("moldaje_deadline", 0):
            self.after(400, lambda k=abutment_key: self._esperar_moldajes_cad(k))
            return
        state["moldaje_status"].configure(
            text="Sin respuesta CAD. Verifica que el dibujo esté abierto y accesible.", text_color="#D06A5D")
        self.parent_app.finalizar_actividad(f"moldajes_{abutment_key}")

    def _aplicar_moldajes_detectados(self, detection, abutment_key):
        state = self._abutments[abutment_key]
        state["moldajes_use_metres"] = detection.uses_metres
        state["moldaje_choices"] = {}
        valid_count = 0
        for layer, (variable, option) in state["moldaje_option_vars"].items():
            choices = {"Sin candidato": None}
            for candidate in detection.for_layer(layer):
                if candidate.is_valid:
                    choices[candidate.label] = candidate
            state["moldaje_choices"][layer] = choices
            option.configure(values=list(choices))
            if len(choices) == 2:
                variable.set(next(label for label in choices if label != "Sin candidato"))
                valid_count += 1
            else:
                variable.set("Sin candidato")
                valid_count += max(0, len(choices) - 1)

        if not detection.uses_metres:
            state["moldaje_status"].configure(
                text="INSUNITS no está en metros (6). Corrige unidades antes de confirmar.", text_color="#D06A5D")
        else:
            state["moldaje_status"].configure(
                text=f"{valid_count} moldaje(s) válido(s). Selecciona y confirma.", text_color=COLOR_ACENTO)

    def confirmar_moldajes_cad(self, abutment_key="entrada"):
        state = self._abutments[abutment_key]
        if not state["moldajes_use_metres"]:
            messagebox.showwarning("Workbench", "El dibujo debe declarar unidades en metros (INSUNITS = 6).")
            return
        confirmed = {}
        for layer, (variable, _option) in state["moldaje_option_vars"].items():
            candidate = state["moldaje_choices"].get(layer, {}).get(variable.get())
            if candidate:
                confirmed[layer] = candidate
        if not confirmed:
            messagebox.showwarning("Workbench", "No hay moldajes válidos seleccionados para confirmar.")
            return
        state["confirmed_moldajes"] = confirmed
        state["moldaje_status"].configure(
            text=f"{len(confirmed)} moldaje(s) confirmado(s). El DWG no se ha modificado.", text_color=COLOR_ACENTO)
        self.parent_app.log_r(
            f"[*] Moldajes de zapata confirmados para {state['title'].lower()}: {', '.join(confirmed)}")
        self.marcar_sesion_modificada()

    def _read_zapata_rules(self, abutment_key):
        state = self._abutments[abutment_key]
        rules = []
        for widgets in state["rule_widgets"].values():
            template = widgets["template"]
            rules.append(replace(
                template,
                mark=widgets["mark"].get().strip(),
                diameter_mm=self._entry_number(widgets["diameter"], f"Diámetro de {template.label}"),
                spacing_cm=self._entry_number(widgets["spacing"], f"Espaciamiento de {template.label}"),
                hook_cm=self._entry_number(widgets["hook"], f"Gancho de {template.label}"),
                enabled=widgets["enabled"].get(),
                origin=widgets["origin"].get().lower(),
            ))
        return tuple(rules)

    def actualizar_revision_zapata(self, abutment_key="entrada", notificar=True):
        state = self._abutments[abutment_key]
        entries = state["entries"]
        state["review_progress"].configure(value=15, bootstyle="info-striped")
        self.update_idletasks()
        try:
            geometry = ZapataGeometry.from_centimetres(
                self._entry_number(entries["largo"], "Largo"),
                self._entry_number(entries["ancho"], "Ancho"),
                self._entry_number(entries["alto"], "Alto"),
                self._entry_number(self.ent_z_esviaje, "Esviaje"),
            )
            cover = Cover.from_centimetres(
                self._entry_number(entries["rec_inf"], "Recubrimiento inferior"),
                self._entry_number(entries["rec_sup"], "Recubrimiento superior"),
                self._entry_number(entries["rec_lat"], "Recubrimiento lateral"),
            )
            state["schedule"] = build_zapata_schedule(
                geometry, cover, self._read_zapata_rules(abutment_key))
        except ValueError as error:
            state["schedule"] = None
            resumen = f"Error de entrada: {error}"
            state["review_progress"].configure(value=0, bootstyle="danger-striped")
        else:
            resumen = (
                f"{len(state['schedule'].marks)} marcas calculadas · "
                f"{state['schedule'].total_kg:.1f} kg provisionales. "
                "Usa Vista previa completa para revisar todas las magnitudes."
            )
            if state["schedule"].issues:
                resumen += "\n" + "\n".join(
                    f"[{issue.severity.upper()}] {issue.message}"
                    for issue in state["schedule"].issues)
            state["review_progress"].configure(
                value=100,
                bootstyle="success-striped" if state["schedule"].is_valid else "warning-striped",
            )

        state["revision_status"].configure(text=resumen)
        if notificar and state["schedule"]:
            self.parent_app.log_r(
                f"[*] Revisión de marcas actualizada para {state['title'].lower()}; aún no se modifica CAD.")
        return state["schedule"]

    def mostrar_vista_previa_marcas(self, abutment_key="entrada"):
        """Abre una tabla amplia y no destructiva con toda la cubicación provisional."""
        state = self._abutments[abutment_key]
        schedule = self.actualizar_revision_zapata(abutment_key, notificar=False)
        if not schedule:
            messagebox.showwarning(
                "Vista previa de marcas", "Corrige los parámetros antes de abrir la tabla.")
            return

        window = ctk.CTkToplevel(self)
        window.title(f"Vista previa de marcas — {state['title'].title()}")
        window.geometry("1240x680")
        window.minsize(980, 520)
        window.transient(self.winfo_toplevel())

        header = ctk.CTkFrame(window, fg_color="transparent", corner_radius=0)
        header.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(
            header, text=f"MARCAS · {state['title']}",
            font=FUENTE_SUBTITULO, text_color=COLOR_MOSTAZA,
        ).pack(side="left")
        ctk.CTkLabel(
            header, text=f"Total provisional: {schedule.total_kg:.1f} kg",
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="right")
        ttk.Separator(window, orient="horizontal", bootstyle="secondary").pack(
            fill="x", padx=18, pady=(0, 8))
        ctk.CTkLabel(
            window,
            text="Haz clic sobre el número de una marca para revisar su forma y sus longitudes.",
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 6))

        columns = (
            "Marca", "Parte del estribo", "Grupo / ubicación", "Cantidad", "Ø mm", "@ cm",
            "Largo unit. cm", "Largo total cm", "Área cm²", "kg",
            "Vistas", "Rol constructivo",
        )
        rows = [
            (
                mark.mark, mark.element, mark.location, mark.quantity, f"{mark.diameter_mm:g}",
                f"{state['rule_widgets'][mark.key]['spacing'].get()}",
                f"{mark.unit_length_cm:.0f}", f"{mark.total_length_cm:.0f}",
                f"{mark.area_m2 * 10000:.3f}", f"{mark.kg_steel:.1f}",
                ", ".join(mark.views), mark.piece_role,
            )
            for mark in schedule.marks
        ]
        table = Tableview(
            window, coldata=columns, rowdata=rows, searchable=True,
            paginated=True, pagesize=15, yscrollbar=True, autofit=True,
            autoalign=True, bootstyle="primary", height=16,
        )
        table.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        marks_by_name = {mark.mark: mark for mark in schedule.marks}
        entries = state["entries"]

        def open_mark_preview(event):
            tree = table.view
            if tree.identify_region(event.x, event.y) != "cell":
                return
            if tree.identify_column(event.x) != "#1":
                return
            item_id = tree.identify_row(event.y)
            values = tree.item(item_id, "values") if item_id else ()
            mark_name = str(values[0]) if values else ""
            mark = marks_by_name.get(mark_name)
            if mark is not None:
                # Los parámetros pueden editarse mientras esta tabla permanece
                # abierta. Se reconstruye el contexto para que el gancho y las
                # demás magnitudes nunca provengan de una captura anterior.
                live_schedule = self.actualizar_revision_zapata(
                    abutment_key, notificar=False)
                live_rules = self._read_zapata_rules(abutment_key)
                live_geometry = ZapataGeometry.from_centimetres(
                    self._entry_number(entries["largo"], "Largo"),
                    self._entry_number(entries["ancho"], "Ancho"),
                    self._entry_number(entries["alto"], "Alto"),
                    self._entry_number(self.ent_z_esviaje, "Esviaje"),
                )
                live_mark = next(
                    (candidate for candidate in live_schedule.marks
                     if candidate.mark == mark_name), None,
                ) if live_schedule else None
                if live_mark is None:
                    messagebox.showwarning(
                        "Vista previa del fierro",
                        f"La marca {mark_name} ya no está activa.", parent=window)
                    return
                self.mostrar_vista_previa_fierro(
                    live_mark, live_schedule, live_rules, live_geometry, window)

        def update_mark_cursor(event):
            is_mark = (
                table.view.identify_region(event.x, event.y) == "cell"
                and table.view.identify_column(event.x) == "#1"
            )
            table.view.configure(cursor="hand2" if is_mark else "")

        table.view.bind("<ButtonRelease-1>", open_mark_preview, add="+")
        table.view.bind("<Motion>", update_mark_cursor, add="+")

        issues = "Sin observaciones de validación."
        if schedule.issues:
            issues = " · ".join(
                f"{issue.severity.upper()}: {issue.message}" for issue in schedule.issues)
        ctk.CTkLabel(
            window, text=issues, font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE, anchor="w", justify="left",
            wraplength=1180,
        ).pack(fill="x", padx=18, pady=(0, 12))
        if hasattr(self.parent_app, "_schedule_typography"):
            self.parent_app._schedule_typography()

    @staticmethod
    def _resolved_color(value):
        if isinstance(value, (tuple, list)):
            return value[0] if ctk.get_appearance_mode() == "Light" else value[1]
        return value

    def mostrar_vista_previa_fierro(
        self, mark, schedule, rules, geometry, owner=None
    ):
        """Dibuja un representante de la marca con parciales y largo total."""
        piece = None
        for group in build_detail_groups(schedule, rules, geometry):
            piece = next(
                (candidate for candidate in group.pieces if candidate.mark == mark.mark),
                None,
            )
            if piece is not None:
                break
        if piece is None:
            messagebox.showwarning(
                "Vista previa del fierro",
                f"No se pudo construir la geometría de la marca {mark.mark}.",
                parent=owner,
            )
            return

        window = ctk.CTkToplevel(self)
        window.title(f"Marca {mark.mark} — {mark.element}")
        window.geometry("820x500")
        window.minsize(640, 420)
        window.transient(owner or self.winfo_toplevel())

        header = ctk.CTkFrame(window, fg_color="transparent", corner_radius=0)
        header.pack(fill="x", padx=22, pady=(18, 8))
        ctk.CTkLabel(
            header, text=f"MARCA {mark.mark}", font=FUENTE_SUBTITULO,
            text_color=COLOR_MOSTAZA,
        ).pack(side="left")
        ctk.CTkLabel(
            header, text=f"{mark.element} · {mark.location}",
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="right")
        ttk.Separator(window, orient="horizontal", bootstyle="secondary").pack(
            fill="x", padx=22, pady=(0, 8))

        canvas = tk.Canvas(
            window, background=self._resolved_color(COLOR_FONDO),
            borderwidth=0, highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True, padx=22, pady=(0, 8))
        footer = ctk.CTkLabel(
            window,
            text=(
                f"{piece.quantity} Ø{piece.diameter_mm} @{piece.spacing_cm:g} · "
                f"L={piece.total_cm} cm · Parciales: "
                + " + ".join(f"{value} cm" for value in piece.partials_cm)
            ),
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
        )
        footer.pack(pady=(0, 18))

        raw_points = [piece.partial_segments_m[0][0]]
        raw_points.extend(segment[1] for segment in piece.partial_segments_m)
        render_points = polyline_render_points(piece)

        def redraw(_event=None):
            canvas.configure(background=self._resolved_color(COLOR_FONDO))
            canvas.delete("all")
            canvas_font = (FUENTE_NORMAL[0], -round(FUENTE_NORMAL[1] * self._get_widget_scaling()))
            width = max(1, canvas.winfo_width())
            height = max(1, canvas.winfo_height())
            xs = [point[0] for point in render_points]
            ys = [point[1] for point in render_points]
            span_x = max(xs) - min(xs)
            span_y = max(ys) - min(ys)
            visual_height = max(span_y, span_x * 0.18, 0.01)
            scale = max(1.0, min(
                (width - 150) / max(span_x, 0.01),
                (height - 120) / visual_height,
            ))
            origin_x = (width - span_x * scale) / 2.0 - min(xs) * scale
            origin_y = (height + span_y * scale) / 2.0 + min(ys) * scale

            def point_to_canvas(point):
                return origin_x + point[0] * scale, origin_y - point[1] * scale

            coordinates = []
            for point in render_points:
                coordinates.extend(point_to_canvas(point))
            accent = self._resolved_color(COLOR_ACENTO)
            text_color = self._resolved_color(COLOR_TEXTO_SUAVE)
            canvas.create_line(
                *coordinates, fill=accent, width=5, capstyle=tk.ROUND,
                joinstyle=tk.ROUND, smooth=False,
            )

            raw_coordinates = [point_to_canvas(point) for point in raw_points]
            center_x = sum(point[0] for point in raw_coordinates) / len(raw_points)
            center_y = sum(point[1] for point in raw_coordinates) / len(raw_points)
            for segment, partial in zip(piece.partial_segments_m, piece.partials_cm):
                x1, y1 = point_to_canvas(segment[0])
                x2, y2 = point_to_canvas(segment[1])
                dx, dy = x2 - x1, y2 - y1
                length = math.hypot(dx, dy)
                if length < 1:
                    continue
                nx, ny = -dy / length, dx / length
                mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                if nx * (mid_x - center_x) + ny * (mid_y - center_y) < 0:
                    nx, ny = -nx, -ny
                offset = 34
                ax1, ay1 = x1 + nx * offset, y1 + ny * offset
                ax2, ay2 = x2 + nx * offset, y2 + ny * offset
                canvas.create_line(x1, y1, ax1, ay1, fill=text_color, width=1)
                canvas.create_line(x2, y2, ax2, ay2, fill=text_color, width=1)
                canvas.create_line(
                    ax1, ay1, ax2, ay2, fill=text_color, width=1,
                    arrow=tk.BOTH, arrowshape=(6, 7, 2),
                )
                canvas.create_text(
                    (ax1 + ax2) / 2.0 + nx * 11,
                    (ay1 + ay2) / 2.0 + ny * 11,
                    text=f"{partial} cm", fill=text_color,
                    font=canvas_font,
                )
            canvas.create_text(
                width / 2.0, height - 18,
                text=f"LONGITUD DESARROLLADA TOTAL  L={piece.total_cm} cm",
                fill=accent, font=canvas_font,
            )

        canvas.bind("<Configure>", redraw, add="+")
        canvas._sincal_theme_refresh = redraw
        window.after_idle(redraw)
        return window

    def generar_vista_cad(self, vista, abutment_key="entrada"):
        state = self._abutments[abutment_key]
        schedule = self.actualizar_revision_zapata(abutment_key, notificar=False)
        if not schedule or not schedule.is_valid:
            messagebox.showwarning("Workbench", "Corrige las validaciones de la revisión antes de preparar una vista.")
            return
        layer = f"{vista}_ZAP"
        candidate = state["confirmed_moldajes"].get(layer)
        if not candidate:
            messagebox.showwarning(
                "Workbench",
                f"Confirma primero un moldaje válido para {layer}. SINCAL no adivina ni modifica contornos.",
            )
            return
        entries = state["entries"]
        try:
            geometry = ZapataGeometry.from_centimetres(
                self._entry_number(entries["largo"], "Largo"),
                self._entry_number(entries["ancho"], "Ancho"),
                self._entry_number(entries["alto"], "Alto"),
                self._entry_number(self.ent_z_esviaje, "Esviaje"),
            )
            cover = Cover.from_centimetres(
                self._entry_number(entries["rec_inf"], "Recubrimiento inferior"),
                self._entry_number(entries["rec_sup"], "Recubrimiento superior"),
                self._entry_number(entries["rec_lat"], "Recubrimiento lateral"),
            )
            rules = self._read_zapata_rules(abutment_key)
            master_path = ruta_recurso(
                "masters", "FORMATOS ANOTATIVOS ACAD_2025.dwg")
            lisp = build_zapata_lisp(
                vista, candidate, geometry, cover, rules, abutment_key,
                master_path=master_path,
            )
            token = str(int(time.time() * 1000))
            ruta_lisp = ruta_runtime(f"SINCAL_ZAPATA_{abutment_key}_{vista}_{token}.lsp")
            with open(ruta_lisp, "w", encoding="utf-8") as archivo:
                archivo.write(lisp)
        except (OSError, ValueError, ZapataCadError) as error:
            messagebox.showerror("Workbench", f"No se pudo preparar la vista {vista}:\n{error}")
            return
        ruta_cad = ruta_lisp.replace("\\", "\\\\")
        self.parent_app.enviar_comando_cad_activo(
            f'(progn (load "{ruta_cad}") (c:SINCAL-ZAPATA-GENERAR))\n',
            f"Generación de zapata {state['title'].lower()} · {vista}",
        )
        self.parent_app.log_r(
            f"[*] Vista {vista} enviada a CAD para {state['title'].lower()}; "
            "sólo se reemplazan entidades SINCAL de esa vista."
        )
        state["generated_views"].add(vista)
        self.marcar_sesion_modificada()

    def generar_despiece_zapata(self, abutment_key="entrada"):
        state = self._abutments[abutment_key]
        schedule = self.actualizar_revision_zapata(abutment_key, notificar=False)
        if not schedule or not schedule.is_valid:
            messagebox.showwarning("Workbench", "Corrige las validaciones antes de revisar el despiece.")
            return
        entries = state["entries"]
        try:
            geometry = ZapataGeometry.from_centimetres(
                self._entry_number(entries["largo"], "Largo"),
                self._entry_number(entries["ancho"], "Ancho"),
                self._entry_number(entries["alto"], "Alto"),
                self._entry_number(self.ent_z_esviaje, "Esviaje"),
            )
            rules = self._read_zapata_rules(abutment_key)
            master_path = ruta_recurso(
                "masters", "FORMATOS ANOTATIVOS ACAD_2025.dwg")
            lisp = build_zapata_detail_lisp(
                schedule, rules, geometry, abutment_key, master_path)
            token = str(int(time.time() * 1000))
            ruta_lisp = ruta_runtime(
                f"SINCAL_DESPIECE_ZAPATA_{abutment_key}_{token}.lsp")
            with open(ruta_lisp, "w", encoding="utf-8") as archivo:
                archivo.write(lisp)
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Workbench", f"No se pudo preparar el despiece de zapata:\n{error}")
            return
        ruta_cad = ruta_lisp.replace("\\", "\\\\")
        self.parent_app.enviar_comando_cad_activo(
            f'(progn (load "{ruta_cad}") (c:SINCAL-ZAPATA-DESPIECE))\n',
            f"Despiece general de zapata · {state['title'].lower()}",
        )
        self.parent_app.log_r(
            f"[*] Despiece general enviado a CAD para {state['title'].lower()}; "
            "AutoCAD/ZWCAD solicitará el punto o confirmará los grupos modificados."
        )
        state["detail_generated"] = True
        self.marcar_sesion_modificada()

    def mostrar_ayuda_travesano(self):
        visor = ctk.CTkToplevel(self)
        visor.title("SINCAL Suite — Ayuda de travesaños")
        visor.geometry("900x350")
        visor.transient(self)

        ruta_img = ruta_recurso("mapas", "ayuda_travesano.png")

        if not os.path.exists(ruta_img):
            base_dir = os.path.dirname(os.path.dirname(__file__))
            ruta_img = os.path.abspath(os.path.join(
                base_dir, "mapas", "ayuda_travesano.png"))

        if os.path.exists(ruta_img):
            try:
                img = Image.open(ruta_img)
                ctk_img = ctk.CTkImage(
                    light_image=img, dark_image=img, size=(850, 300))
                lbl_img = ctk.CTkLabel(visor, image=ctk_img, text="")
                lbl_img.pack(fill="both", expand=True, padx=10, pady=10)
            except Exception as e:
                ctk.CTkLabel(
                    visor, text=f"Error cargando imagen:\n{e}").pack(pady=20)
        else:
            ctk.CTkLabel(
                visor, text=f"No se encontró la imagen de ayuda en:\n{ruta_img}\n\nPor favor, guarda el DXF como 'ayuda_travesano.png' en la carpeta 'mapas'.").pack(pady=20)

    def generar_travesano_cad(self, tipo_cuadrante):
        try:
            recub = float(self.ent_t_rec.get())
            espesor = float(self.ent_t_espesor.get())
            esviaje = float(self.ent_t_esviaje.get())
            phi_ext = int(self.ent_t_phi_ext.get())
            phi_horiz = int(self.ent_t_phi_horiz.get())
            phi_estr = int(self.ent_t_phi_estr.get())
            largo_viga = float(self.ent_viga_largo.get())
        except ValueError:
            return messagebox.showerror("Error", "Por favor, ingresa solo valores numéricos válidos en los parámetros del travesaño.")

        ruta_temp = os.path.join(
            RUTA_TEMPORAL, f"Travesano_{tipo_cuadrante}.lsp")
        ruta_lisp = ruta_temp.replace("\\", "\\\\")

        from sincal.cad.crossbeam import build_crossbeam_lisp
        lisp_code = build_crossbeam_lisp(tipo_cuadrante, recub, espesor, esviaje,
            phi_ext, phi_horiz, phi_estr, largo_viga)

        with open(ruta_temp, 'w', encoding='utf-8') as f:
            f.write(lisp_code)

        self.parent_app.cancelar_comando_vivo = False
        ruta_lisp = ruta_temp.replace("\\", "\\\\")
        threading.Thread(target=self.parent_app._hilo_comando_en_vivo, args=(
            f'(load "{ruta_lisp}") (c:SINCAL-TRAVESANO)\n',), daemon=True).start()

    def generar_despiece_travesano_cad(self, tipo_cuadrante):
        try:
            recub = float(self.ent_t_rec.get())
            espesor = float(self.ent_t_espesor.get())
            esviaje = float(self.ent_t_esviaje.get())
            phi_ext = int(self.ent_t_phi_ext.get())
            phi_horiz = int(self.ent_t_phi_horiz.get())
            phi_estr = int(self.ent_t_phi_estr.get())
            cant_trav = int(self.ent_t_cantidad.get())
            largo_viga = float(self.ent_viga_largo.get())
        except ValueError:
            return messagebox.showerror("Error", "Entradas numéricas inválidas.")

        ruta_temp = os.path.join(
            RUTA_TEMPORAL, f"Despiece_Trav_{tipo_cuadrante}.lsp")

        from sincal.cad.crossbeam import build_crossbeam_detail_lisp
        lisp_code = build_crossbeam_detail_lisp(tipo_cuadrante, recub, espesor, esviaje,
            phi_ext, phi_horiz, phi_estr, largo_viga, cant_trav)

        with open(ruta_temp, 'w', encoding='utf-8') as f:
            f.write(lisp_code)

        self.parent_app.cancelar_comando_vivo = False
        ruta_lisp = ruta_temp.replace("\\", "\\\\")
        threading.Thread(target=self.parent_app._hilo_comando_en_vivo, args=(
            f'(load "{ruta_lisp}") (c:SINCAL-DESPIECE-TRAV)\n',), daemon=True).start()

    def _aplicar_json_bim(self, datos, ruta="", notificar=True):
        """Mapea una instantánea BIM sin modificar nunca su archivo de origen."""
        e_data = datos.get("estribos", {})
        for abutment_key, state in self._abutments.items():
            mapped = (
                (state["entries"]["largo"], f"dado_muro_frontal_largo_{abutment_key}"),
                (state["entries"]["ancho"], f"dado_muro_frontal_ancho_{abutment_key}"),
                (state["entries"]["alto"], f"dado_muro_frontal_espesor_{abutment_key}"),
            )
            for entry, json_key in mapped:
                if json_key in e_data:
                    self._set_entry(entry, e_data[json_key] / 10.0)

        travesanos = datos.get("elementos_comunes", {}).get("travesanos", {})
        if travesanos.get("espesor_travesano") is not None:
            self._set_entry(self.ent_t_espesor, travesanos["espesor_travesano"] / 10.0)
        esviaje = datos.get("parametros_generales", {}).get("angulo_esviaje_puente")
        if esviaje is not None:
            self._set_entry(self.ent_z_esviaje, esviaje)
            self._set_entry(self.ent_t_esviaje, esviaje)
        for abutment_key in self._abutments:
            self.actualizar_revision_zapata(abutment_key, notificar=False)

        self._json_path = str(ruta or "")
        self._json_snapshot = datos
        self._json_sha256 = sha256_file(ruta)
        nombre = os.path.basename(ruta) if ruta else "Instantánea de sesión"
        self.lbl_json_status.configure(text=f"Proyecto: {nombre}", text_color=COLOR_ACENTO)
        if notificar:
            self.parent_app.log_r(f"[*] JSON cargado: {nombre}")
            messagebox.showinfo(
                "SINCAL Suite", "Datos mapeados exitosamente en centímetros y grados.")

    def cargar_json_bim(self):
        """Compatibilidad interna: la carga se realiza desde Proyecto > Consulta."""
        self.parent_app.seleccionar_seccion("consulta")

    def limpiar_json_bim(self):
        self.parent_app.clear_project()

    def confirm_project_change(self):
        return self._confirmar_descartar_cambios()

    def _reset_session_identity(self):
        if hasattr(self.parent_app, "vista_prospecciones"):
            self.parent_app.vista_prospecciones.restore()
        old_id = self._session_metadata.get("id")
        self._session_metadata = {}
        self._session_path = None
        self._session_dirty = False
        self.lbl_session_status.configure(
            text="Sin sesión activa", text_color=COLOR_TEXTO_SUAVE)
        self.btn_guardar_sesion.configure(state="disabled")
        self.btn_nueva_sesion.configure(state="disabled")
        self.parent_app.session_store.clear_autosave(old_id)

    def switch_project(self, context):
        """Inicia un espacio limpio y aplica el proyecto compartido."""
        self._restore_workspace(self._blank_workspace)
        self._reset_session_identity()
        self._aplicar_json_bim(context.data, context.path, notificar=False)
        self._json_sha256 = context.sha256
        self.parent_app.log_r(
            f"[*] Generador vinculado al proyecto: {context.filename}")

    def clear_shared_project(self):
        self._restore_workspace(self._blank_workspace)
        self._reset_session_identity()
        self._json_path = ""
        self._json_snapshot = None
        self._json_sha256 = ""
        self.lbl_json_status.configure(
            text="Proyecto: ninguno", text_color=COLOR_TEXTO_SUAVE)

    # =========================================================
    # SESIONES DE TRABAJO
    # =========================================================
    @staticmethod
    def _set_entry(entry, value):
        state = None
        try:
            state = str(entry.cget("state"))
            if state == "readonly":
                entry.configure(state="normal")
        except (tk.TclError, AttributeError):
            pass
        entry.delete(0, "end")
        entry.insert(0, str(value))
        if state == "readonly":
            entry.configure(state="readonly")

    @staticmethod
    def _json_value_by_keys(data, keys):
        if isinstance(data, dict):
            for key, value in data.items():
                if str(key).lower() in keys and value not in (None, ""):
                    return str(value)
            for value in data.values():
                found = TabArmaduras._json_value_by_keys(value, keys)
                if found:
                    return found
        elif isinstance(data, list):
            for value in data:
                found = TabArmaduras._json_value_by_keys(value, keys)
                if found:
                    return found
        return ""

    def _capture_workspace(self):
        abutments = {}
        for key, state in self._abutments.items():
            rules = {}
            for rule_key, widgets in state["rule_widgets"].items():
                rules[rule_key] = {
                    "mark": widgets["mark"].get(),
                    "diameter": widgets["diameter"].get(),
                    "spacing": widgets["spacing"].get(),
                    "hook": widgets["hook"].get(),
                    "origin": widgets["origin"].get(),
                    "enabled": bool(widgets["enabled"].get()),
                }
            references = {
                layer: asdict(candidate)
                for layer, candidate in state["confirmed_moldajes"].items()
            }
            abutments[key] = {
                "entries": {name: widget.get() for name, widget in state["entries"].items()},
                "rules": rules,
                "moldaje_references": references,
                "generated_views": sorted(state.get("generated_views", set())),
                "detail_generated": bool(state.get("detail_generated")),
            }
        travesano_names = (
            "ent_t_rec", "ent_t_espesor", "ent_t_esviaje", "ent_t_phi_ext",
            "ent_t_phi_horiz", "ent_t_phi_estr", "ent_viga_largo", "ent_t_cantidad",
        )
        return {
            "skew": self.ent_z_esviaje.get(),
            "abutments": abutments,
            "crossbeam": {
                name: getattr(self, name).get() for name in travesano_names
                if hasattr(self, name)
            },
            "active_tabs": {
                "main": self.tab_maestro.index("current"),
                "abutment": self.tab_estribo.index("current"),
                "crossbeam": self.tab_sub_travesanos.index("current"),
            },
        }

    def _restore_workspace(self, workspace):
        self._restoring_session = True
        try:
            self._set_entry(self.ent_z_esviaje, workspace.get("skew", "0"))
            for key, saved in workspace.get("abutments", {}).items():
                state = self._abutments.get(key)
                if not state:
                    continue
                for name, value in saved.get("entries", {}).items():
                    if name in state["entries"]:
                        self._set_entry(state["entries"][name], value)
                for rule_key, values in saved.get("rules", {}).items():
                    widgets = state["rule_widgets"].get(rule_key)
                    if not widgets:
                        continue
                    for field in ("mark", "diameter", "spacing", "hook"):
                        if field in values:
                            self._set_entry(widgets[field], values[field])
                    widgets["origin"].set(values.get("origin", "Inicio"))
                    widgets["enabled"].set(bool(values.get("enabled", True)))
                # Los handles CAD son sólo una huella informativa. Nunca se
                # restauran como selección válida en otro dibujo o sesión.
                state["confirmed_moldajes"] = {}
                for value, option in state["moldaje_option_vars"].values():
                    value.set("Sin detectar")
                    option.configure(values=["Sin detectar"])
                refs = saved.get("moldaje_references", {})
                if refs:
                    state["moldaje_status"].configure(
                        text=f"{len(refs)} referencia(s) guardada(s); vuelve a detectar y confirmar en el DWG activo.",
                        text_color=COLOR_MOSTAZA,
                    )
                else:
                    state["moldaje_status"].configure(
                        text="Sin lectura CAD.", text_color=COLOR_TEXTO_SUAVE)
                state["generated_views"] = set(saved.get("generated_views", ()))
                state["detail_generated"] = bool(saved.get("detail_generated"))
                self.actualizar_revision_zapata(key, notificar=False)
            for name, value in workspace.get("crossbeam", {}).items():
                if hasattr(self, name):
                    self._set_entry(getattr(self, name), value)
            tabs = workspace.get("active_tabs", {})
            for notebook, name in (
                (self.tab_maestro, "main"), (self.tab_estribo, "abutment"),
                (self.tab_sub_travesanos, "crossbeam"),
            ):
                try:
                    notebook.select(int(tabs.get(name, 0)))
                except (tk.TclError, ValueError):
                    pass
        finally:
            self._restoring_session = False

    def _project_metadata(self):
        data = self._json_snapshot or {}
        identification = (
            dict(self.project_context.identification)
            if self.project_context is not None else {}
        )
        json_name = os.path.basename(self._json_path) if self._json_path else ""
        bridge_name = identification.get("structure_name") or self._json_value_by_keys(
            data, {"nombre_puente", "nombre_estructura", "puente"})
        if not bridge_name and json_name:
            bridge_name = Path(json_name).stem
        revision = identification.get("revision", "")
        plan_name = self._json_value_by_keys(data, {"nombre_plano"}) or (
            f"Revisión {revision}" if revision else "")
        project_code = identification.get("ot") or self._json_value_by_keys(
            data, {"codigo_proyecto", "codigo", "project_code"})
        e_data = data.get("estribos", {}) if isinstance(data, dict) else {}
        return {
            "bridge_name": bridge_name,
            "project_code": project_code,
            "ot": identification.get("ot", ""),
            "revision": revision,
            "structure_name": identification.get("structure_name", ""),
            "plan_name": plan_name,
            "json_name": json_name,
            "json_path": self._json_path,
            "skew_degrees": self.ent_z_esviaje.get(),
            "abutment_entry_type": e_data.get("tipo_estribo_entrada", ""),
            "abutment_exit_type": e_data.get("tipo_estribo_salida", ""),
        }

    def _session_document(self):
        mark_count = 0
        total_kg = 0.0
        for key, state in self._abutments.items():
            schedule = self.actualizar_revision_zapata(key, notificar=False)
            if schedule:
                mark_count += len(schedule.marks)
                total_kg += schedule.total_kg
        metadata = dict(self._session_metadata)
        metadata.setdefault("id", str(uuid.uuid4()))
        metadata.setdefault("name", "Sesión sin guardar")
        return {
            "metadata": metadata,
            "formal_path": self._session_path,
            "project": self._project_metadata(),
            "source_json": {
                "path": self._json_path,
                "sha256": self._json_sha256,
                "snapshot": self._json_snapshot,
            },
            "workspace": self._capture_workspace(),
            "prospecciones": (
                self.parent_app.vista_prospecciones.snapshot()
                if hasattr(self.parent_app, "vista_prospecciones") else None),
            "overview": {
                "mark_count": mark_count,
                "total_kg": round(total_kg, 3),
                "milestone": "despiece" if any(
                    state.get("detail_generated") for state in self._abutments.values())
                    else "vistas" if any(
                        state.get("generated_views") for state in self._abutments.values())
                    else "configuración",
            },
        }

    def _bind_session_change_tracking(self):
        widgets = [self.ent_z_esviaje]
        for state in self._abutments.values():
            widgets.extend(state["entries"].values())
            for rule in state["rule_widgets"].values():
                widgets.extend(rule[field] for field in ("mark", "diameter", "spacing", "hook"))
                rule["origin"].trace_add("write", lambda *_: self.marcar_sesion_modificada())
                rule["enabled"].trace_add("write", lambda *_: self.marcar_sesion_modificada())
        widgets.extend(
            getattr(self, name) for name in (
                "ent_t_rec", "ent_t_espesor", "ent_t_esviaje", "ent_t_phi_ext",
                "ent_t_phi_horiz", "ent_t_phi_estr", "ent_viga_largo", "ent_t_cantidad",
            ) if hasattr(self, name)
        )
        for widget in widgets:
            widget.bind("<KeyRelease>", lambda _event: self.marcar_sesion_modificada(), add="+")
            widget.bind("<<ComboboxSelected>>", lambda _event: self.marcar_sesion_modificada(), add="+")

    def marcar_sesion_modificada(self):
        if self._restoring_session:
            return
        self._session_metadata.setdefault("id", str(uuid.uuid4()))
        self._session_dirty = True
        self.btn_guardar_sesion.configure(state="normal")
        self.btn_nueva_sesion.configure(state="normal")
        name = self._session_metadata.get("name", "Sesión sin guardar")
        self.lbl_session_status.configure(
            text=f"{name} · Cambios sin guardar", text_color=COLOR_MOSTAZA)

    def abrir_biblioteca_sesiones(self):
        self.parent_app.seleccionar_seccion("sesiones")

    def guardar_sesion(self):
        if not self._session_metadata.get("name"):
            suggestion = self._project_metadata().get("bridge_name") or "Nueva sesión"
            name = simpledialog.askstring(
                "Guardar sesión", "Nombre de la sesión:", initialvalue=suggestion,
                parent=self.winfo_toplevel())
            if not name or not name.strip():
                return False
            tags = simpledialog.askstring(
                "Etiquetas de sesión",
                "Etiquetas opcionales, separadas por comas:",
                parent=self.winfo_toplevel(),
            )
            self._session_metadata = {
                "id": str(uuid.uuid4()), "name": name.strip(),
                "tags": [tag.strip() for tag in (tags or "").split(",") if tag.strip()],
            }
        try:
            document, path = self.parent_app.session_store.save(
                self._session_document(), self._session_path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Guardar sesión", f"No se pudo guardar la sesión:\n{error}")
            return False
        self._session_metadata = document["metadata"]
        self._session_path = str(path)
        self._session_dirty = False
        self.parent_app.session_store.clear_autosave(self._session_metadata.get("id"))
        self.lbl_session_status.configure(
            text=f"Sesión: {self._session_metadata['name']}", text_color=COLOR_ACENTO)
        self.btn_guardar_sesion.configure(state="disabled")
        self.btn_nueva_sesion.configure(state="normal")
        self.parent_app.log_r(f"[OK] Sesión guardada: {path}")
        messagebox.showinfo("Guardar sesión", f"Sesión guardada correctamente en:\n{path}")
        if hasattr(self.parent_app, "vista_sessions"):
            self.parent_app.vista_sessions.refresh()
        return True

    def _confirmar_descartar_cambios(self):
        if not self._session_dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Cambios sin guardar",
            "La sesión actual tiene cambios sin guardar.\n\n"
            "Sí: guardar y continuar.\nNo: descartar los cambios.\nCancelar: volver.",
        )
        if answer is None:
            return False
        return self.guardar_sesion() if answer else True

    def nueva_sesion(self):
        if not self._confirmar_descartar_cambios():
            return False
        self._restore_workspace(self._blank_workspace)
        self._reset_session_identity()
        if self.project_context is not None and self.project_context.active:
            self._aplicar_json_bim(
                self.project_context.data, self.project_context.path, notificar=False)
            self._json_sha256 = self.project_context.sha256
        else:
            self._json_path = ""
            self._json_snapshot = None
            self._json_sha256 = ""
            self.lbl_json_status.configure(
                text="Proyecto: ninguno", text_color=COLOR_TEXTO_SUAVE)
        return True

    def abrir_sesion_desde_ruta(self, path):
        if not self._confirmar_descartar_cambios():
            return False
        try:
            document = self.parent_app.session_store.load(path)
            if hasattr(self.parent_app, "vista_prospecciones"):
                self.parent_app.vista_prospecciones.validate_snapshot(document.get("prospecciones"))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            messagebox.showerror("Abrir sesión", f"No se pudo abrir la sesión:\n{error}")
            return False
        source = document.get("source_json") or {}
        source_path = source.get("path", "")
        current_data = None
        if source_path and os.path.isfile(source_path):
            current_hash = sha256_file(source_path)
            if source.get("sha256") and current_hash != source.get("sha256"):
                answer = messagebox.askyesnocancel(
                    "JSON modificado",
                    "El JSON original cambió desde que se guardó esta sesión.\n\n"
                    "Sí: recargar el JSON actual y recalcular.\n"
                    "No: usar la instantánea guardada.\nCancelar: no abrir la sesión.",
                )
                if answer is None:
                    return False
                if answer:
                    try:
                        with open(source_path, "r", encoding="utf-8") as source_file:
                            current_data = json.load(source_file)
                    except (OSError, json.JSONDecodeError) as error:
                        messagebox.showerror("Abrir sesión", f"No se pudo leer el JSON actual:\n{error}")
                        return False
        self._restore_workspace(document.get("workspace") or {})
        if hasattr(self.parent_app, "vista_prospecciones"):
            self.parent_app.vista_prospecciones.restore(document.get("prospecciones"))
        snapshot = source.get("snapshot")
        project = document.get("project") or {}
        identification = {
            "ot": project.get("ot") or project.get("project_code", ""),
            "revision": project.get("revision", ""),
            "structure_name": project.get("structure_name") or project.get("bridge_name", ""),
        }
        active_data = current_data if current_data is not None else (snapshot or {})
        active_hash = sha256_file(source_path) if current_data is not None else source.get("sha256", "")
        self.parent_app.activate_project_snapshot(
            active_data, source_path, active_hash, identification)
        if current_data is not None:
            self._aplicar_json_bim(current_data, source_path, notificar=False)
        else:
            self._json_path = source_path
            self._json_snapshot = snapshot
            self._json_sha256 = source.get("sha256", "")
            json_name = os.path.basename(source_path) if source_path else "Instantánea de sesión"
            self.lbl_json_status.configure(text=f"Proyecto: {json_name}", text_color=COLOR_ACENTO)
        self._session_metadata = dict(document.get("metadata") or {})
        is_recovery = Path(path).name.startswith("recovery-")
        formal_path = document.get("formal_path") if is_recovery else str(path)
        self._session_path = formal_path or None
        self._session_dirty = bool(current_data is not None or is_recovery)
        name = self._session_metadata.get("name", "Sesión")
        self.lbl_session_status.configure(
            text=f"Sesión: {name}" + (
                " · Recuperada, guarda para confirmar" if is_recovery
                else " · JSON recalculado" if current_data is not None else ""),
            text_color=COLOR_MOSTAZA if self._session_dirty else COLOR_ACENTO,
        )
        self.btn_guardar_sesion.configure(state="normal" if self._session_dirty else "disabled")
        self.btn_nueva_sesion.configure(state="normal")
        self.parent_app.log_r(f"[OK] Sesión cargada: {name}. Revalida los moldajes en el DWG activo.")
        return True

    def _comprobar_recuperacion_pendiente(self):
        if self._session_dirty or self._session_path:
            return
        pending = self.parent_app.session_store.pending_recoveries()
        if not pending:
            return
        newest = pending[0]
        metadata = newest["document"].get("metadata") or {}
        name = metadata.get("name", "sesión sin guardar")
        if messagebox.askyesno(
            "Recuperar sesión",
            f"SINCAL Suite encontró cambios recuperables de «{name}».\n\n"
            "¿Quieres restaurarlos ahora? Los moldajes CAD deberán revalidarse.",
        ):
            if self.abrir_sesion_desde_ruta(newest["path"]):
                self.parent_app.seleccionar_seccion("estructural")

    def _autosave_tick(self):
        if self._session_dirty:
            try:
                self.parent_app.session_store.autosave(self._session_document())
            except OSError as error:
                self.parent_app.log_r(f"[!] No se pudo guardar la recuperación automática: {error}")
        self._autosave_job = self.after(60_000, self._autosave_tick)

    def guardar_recuperacion_al_cerrar(self):
        if not self._session_dirty:
            return
        try:
            self.parent_app.session_store.autosave(self._session_document())
        except OSError:
            pass
