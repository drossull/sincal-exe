"""Biblioteca visual de sesiones del generador de armaduras."""

from __future__ import annotations

import os
from datetime import datetime

import customtkinter as ctk
import ttkbootstrap as ttk

from sincal.sessions import normalized_search_text
from sincal.ui.theme import (
    COLOR_ACENTO, COLOR_BORDE, COLOR_FONDO, COLOR_GRIS_BOTON,
    COLOR_GRIS_BOTON_HOVER, COLOR_MOSTAZA, COLOR_PANEL, COLOR_TEXTO,
    COLOR_TEXTO_SUAVE, FUENTE_NORMAL, FUENTE_NORMAL_PEQUENA,
    FUENTE_SUBTITULO, RADIO_CONTROL,
)
from sincal.ui.widgets import ShadowButton


class TabSessions(ctk.CTkFrame):
    PAGE_SIZE = 4

    def __init__(self, master, parent_app, store, armaduras_tab, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.store = store
        self.armaduras_tab = armaduras_tab
        self._page = 0
        self._items = []
        self._filtered = []
        self._selected_path = None
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        header.pack(fill="x", padx=20, pady=(14, 8))
        ctk.CTkLabel(
            header, text="SESIONES", font=FUENTE_SUBTITULO,
            text_color=COLOR_MOSTAZA,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Retoma el estado de un puente sin depender del DWG que esté abierto.",
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
        ).pack(anchor="w", pady=(3, 0))

        search_row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        search_row.pack(fill="x", padx=20, pady=(2, 10))
        ctk.CTkLabel(search_row, text="Buscar", font=FUENTE_NORMAL).pack(side="left")
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        self.search_entry = ttk.Entry(
            search_row, textvariable=self.search_var, font=FUENTE_NORMAL,
            bootstyle="secondary",
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(10, 8))
        self.sort_var = ctk.StringVar(value="Más recientes")
        ttk.Combobox(
            search_row, textvariable=self.sort_var,
            values=("Más recientes", "Nombre A–Z"), state="readonly", width=16,
            font=FUENTE_NORMAL, bootstyle="secondary",
        ).pack(side="right")
        self.sort_var.trace_add("write", lambda *_: self._apply_filter())

        ttk.Separator(self, orient="horizontal", bootstyle="secondary").pack(
            fill="x", padx=20, pady=(0, 10))
        self.cards = ctk.CTkFrame(self, fg_color=COLOR_FONDO, corner_radius=0)
        self.cards.pack(fill="both", expand=True, padx=20)
        for column in (0, 1):
            self.cards.grid_columnconfigure(column, weight=1, uniform="session-card")
        for row in (0, 1):
            self.cards.grid_rowconfigure(row, weight=1, uniform="session-card")

        footer = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        footer.pack(fill="x", padx=20, pady=(10, 16))
        self.prev_button = ShadowButton(
            footer, text="‹", width=44, height=34, font=FUENTE_SUBTITULO,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=lambda: self._change_page(-1),
        )
        self.prev_button.pack(side="left")
        self.page_label = ctk.CTkLabel(
            footer, text="Página 1 de 1", font=FUENTE_NORMAL,
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.page_label.pack(side="left", expand=True)
        self.next_button = ShadowButton(
            footer, text="›", width=44, height=34, font=FUENTE_SUBTITULO,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=lambda: self._change_page(1),
        )
        self.next_button.pack(side="right")

    def refresh(self):
        self._items = self.store.summaries()
        self._apply_filter(reset=True)

    def _apply_filter(self, *_args, reset=False):
        query = normalized_search_text(self.search_var.get())
        self._filtered = [item for item in self._items if query in item["search_text"]]
        if self.sort_var.get() == "Nombre A–Z":
            self._filtered.sort(key=lambda item: normalized_search_text(
                item["metadata"].get("name", "")))
        if reset:
            self._page = 0
        self._render()

    def _render(self):
        for child in self.cards.winfo_children():
            child.destroy()
        pages = max(1, (len(self._filtered) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page = min(self._page, pages - 1)
        start = self._page * self.PAGE_SIZE
        visible = self._filtered[start:start + self.PAGE_SIZE]
        if not visible:
            ctk.CTkLabel(
                self.cards,
                text="No hay sesiones guardadas.\nGuarda una desde el Generador de armadura.",
                font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE, justify="center",
            ).grid(row=0, column=0, columnspan=2, rowspan=2, sticky="nsew")
        for index, item in enumerate(visible):
            self._build_card(index // 2, index % 2, item)
        self.page_label.configure(text=f"Página {self._page + 1} de {pages}")
        self.prev_button.configure(state="normal" if self._page else "disabled")
        self.next_button.configure(state="normal" if self._page + 1 < pages else "disabled")

    def _build_card(self, row, column, item):
        metadata, project, overview = item["metadata"], item["project"], item["overview"]
        name = metadata.get("name") or "Sesión sin nombre"
        bridge = project.get("bridge_name") or "Puente sin identificar"
        plan = project.get("plan_name") or "Plano sin identificar"
        json_name = project.get("json_name") or "Sin JSON"
        structure = "Estribos"
        types = " / ".join(filter(None, (
            project.get("abutment_entry_type"), project.get("abutment_exit_type"))))
        skew = project.get("skew_degrees", "0")
        updated = metadata.get("updated_at", "")
        try:
            updated = datetime.fromisoformat(updated).astimezone().strftime("%d-%m-%Y · %H:%M")
        except (ValueError, TypeError):
            updated = "Fecha no disponible"
        detail = (
            f"{name}\n\n{bridge}\n{plan}\n{structure}"
            f"{f' · {types}' if types else ''} · Esviaje {skew}°\nJSON: {json_name}\n"
            f"{overview.get('mark_count', 0)} marcas · {overview.get('total_kg', 0):.1f} kg\n"
            f"Estado: {overview.get('milestone', 'configuración')}\n"
            f"Actualizada: {updated}"
        )
        wrapper = ctk.CTkFrame(
            self.cards, fg_color=COLOR_PANEL, border_width=1,
            border_color=COLOR_BORDE, corner_radius=0,
        )
        wrapper.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
        card = ShadowButton(
            wrapper, text=detail, font=FUENTE_NORMAL, anchor="w", justify="left",
            flat=True, fg_color=COLOR_PANEL, hover_color=COLOR_GRIS_BOTON,
            text_color=COLOR_TEXTO, corner_radius=0,
            command=lambda current=item: self._select(current),
        )
        card.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        ShadowButton(
            wrapper, text="Cargar", height=30, font=FUENTE_NORMAL_PEQUENA,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=lambda path=item["path"]: self._load(path),
        ).pack(anchor="e", padx=10, pady=(3, 10))

    def _select(self, item):
        self._selected_path = item["path"]
        self.parent_app.log_r(
            f"[*] Sesión seleccionada: {item['metadata'].get('name', os.path.basename(item['path']))}")

    def _load(self, path):
        if self.armaduras_tab.abrir_sesion_desde_ruta(path):
            self.parent_app.seleccionar_seccion("estructural")

    def _change_page(self, delta):
        self._page += delta
        self._render()

    def ir_a_seccion(self, anchor):
        if anchor == "buscar":
            self.search_entry.focus_set()
        elif anchor == "biblioteca":
            self.cards.focus_set()
