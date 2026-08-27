"""Consulta de solo lectura del proyecto activo."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import ttkbootstrap as ttk

from sincal.project import project_sections, project_text
from sincal.ui.scroll import SafeScrollableFrame
from sincal.ui.theme import (
    COLOR_ACENTO, COLOR_BORDE, COLOR_FONDO, COLOR_GRIS_BOTON,
    COLOR_GRIS_BOTON_HOVER, COLOR_MOSTAZA, COLOR_TEXTO, COLOR_TEXTO_SUAVE,
    FUENTE_CAMPO, FUENTE_NORMAL, FUENTE_NORMAL_PEQUENA, FUENTE_SUBTITULO,
)
from sincal.ui.widgets import ShadowButton


class TabProject(ctk.CTkFrame):
    """Puerta de entrada al JSON que comparten los módulos de Proyecto."""

    def __init__(self, master, parent_app, context, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.context = context
        self._anchors = {}
        self._render_token = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        header.pack(fill="x", padx=20, pady=(14, 8))
        ctk.CTkLabel(
            header, text="CONSULTA DE PROYECTO", font=FUENTE_SUBTITULO,
            text_color=COLOR_MOSTAZA,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=("Carga una única fuente JSON para consultar el puente y alimentar "
                  "el Generador de armadura."),
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
        ).pack(anchor="w", pady=(3, 0))

        self.page = SafeScrollableFrame(
            self, fg_color=COLOR_FONDO, corner_radius=0,
            scrollbar_button_color=COLOR_GRIS_BOTON,
            scrollbar_button_hover_color=COLOR_GRIS_BOTON_HOVER,
        )
        self.page.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        self.identity_panel = self._labelframe(
            self.page, "IDENTIFICACIÓN OBLIGATORIA")
        self.identity_panel.pack(fill="x", pady=(2, 10))
        identity = ctk.CTkFrame(
            self.identity_panel, fg_color=COLOR_FONDO, corner_radius=0)
        identity.pack(fill="x", padx=10, pady=10)
        identity.grid_columnconfigure(1, weight=1)
        identity.grid_columnconfigure(3, weight=1)
        identity.grid_columnconfigure(5, weight=2)
        self.identity_vars = {
            "ot": tk.StringVar(),
            "revision": tk.StringVar(),
            "structure_name": tk.StringVar(),
        }
        labels = (
            ("OT *", "ot", 0), ("Revisión *", "revision", 2),
            ("Nombre de estructura *", "structure_name", 4),
        )
        for label, key, column in labels:
            ctk.CTkLabel(
                identity, text=label, font=FUENTE_NORMAL,
                text_color=COLOR_TEXTO, anchor="w",
            ).grid(row=0, column=column, sticky="w", padx=(0 if column == 0 else 14, 6))
            ttk.Entry(
                identity, textvariable=self.identity_vars[key],
                font=FUENTE_CAMPO, bootstyle="secondary",
            ).grid(row=0, column=column + 1, sticky="ew")
        ShadowButton(
            identity, text="Guardar identificación", font=FUENTE_NORMAL,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=self.save_identification,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.identity_status = ctk.CTkLabel(
            identity, text="Completa los tres campos.", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE, anchor="w",
        )
        self.identity_status.grid(
            row=1, column=2, columnspan=4, sticky="w", padx=(14, 0), pady=(10, 0))

        self.source_panel = self._labelframe(self.page, "FUENTE JSON")
        self.source_panel.pack(fill="x", pady=(0, 10))
        source = ctk.CTkFrame(
            self.source_panel, fg_color=COLOR_FONDO, corner_radius=0)
        source.pack(fill="x", padx=10, pady=10)
        self.path_var = tk.StringVar(value="Ningún proyecto cargado")
        path_entry = ttk.Entry(
            source, textvariable=self.path_var, state="readonly",
            font=FUENTE_CAMPO, bootstyle="secondary",
        )
        path_entry.pack(side="left", fill="x", expand=True)
        ShadowButton(
            source, text="Cargar JSON", font=FUENTE_NORMAL,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=self.choose_json,
        ).pack(side="left", padx=(8, 0))
        self.copy_button = ShadowButton(
            source, text="Copiar ruta", font=FUENTE_NORMAL_PEQUENA,
            fg_color="transparent", hover_color=COLOR_GRIS_BOTON,
            corner_radius=0, state="disabled", command=self.copy_path,
        )
        self.copy_button.pack(side="left", padx=(8, 0))
        self.clear_button = ShadowButton(
            source, text="Limpiar", font=FUENTE_NORMAL_PEQUENA,
            fg_color="transparent", hover_color=COLOR_GRIS_BOTON,
            corner_radius=0, state="disabled", command=self.clear_project,
        )
        self.clear_button.pack(side="left", padx=(8, 0))

        status_row = ctk.CTkFrame(
            self.source_panel, fg_color=COLOR_FONDO, corner_radius=0)
        status_row.pack(fill="x", padx=10, pady=(0, 10))
        self.source_status = ctk.CTkLabel(
            status_row, text="Carga un archivo para comenzar.",
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
            anchor="w",
        )
        self.source_status.pack(side="left", fill="x", expand=True)
        self.export_button = ShadowButton(
            status_row, text="Exportar consulta .txt", font=FUENTE_NORMAL,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, state="disabled", command=self.export_txt,
        )
        self.export_button.pack(side="right")

        self.notice = ctk.CTkLabel(
            self.page,
            text=("Las coordenadas Norte, Este y Cota pertenecen al sistema local PTL. "
                  "No se envían al módulo Ubicación."),
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
            anchor="w", justify="left",
        )
        self.notice.pack(fill="x", padx=6, pady=(0, 10))

        self.sections_host = ctk.CTkFrame(
            self.page, fg_color=COLOR_FONDO, corner_radius=0)
        self.sections_host.pack(fill="x")

    @staticmethod
    def _labelframe(parent, title):
        title_widget = ttk.Label(
            parent, text=title, style="SincalLabelframeTitle.TLabel")
        return ttk.Labelframe(
            parent, labelwidget=title_widget, bootstyle="secondary", padding=4)

    def choose_json(self):
        path = filedialog.askopenfilename(
            title="Seleccionar JSON del proyecto",
            filetypes=(("Proyecto JSON", "*.json"), ("Todos los archivos", "*.*")),
        )
        if not path:
            return
        identification = {
            key: variable.get().strip() for key, variable in self.identity_vars.items()
        }
        if self.parent_app.load_project(path, identification=identification):
            self.refresh()

    def save_identification(self):
        values = {key: variable.get().strip() for key, variable in self.identity_vars.items()}
        missing = [key for key, value in values.items() if not value]
        if missing:
            messagebox.showwarning(
                "Identificación incompleta",
                "OT, Revisión y Nombre de estructura son obligatorios.",
                parent=self.winfo_toplevel(),
            )
            return False
        if not self.context.active:
            messagebox.showinfo(
                "Consulta de proyecto",
                "La identificación está preparada. Carga el JSON para asociarla al proyecto.",
                parent=self.winfo_toplevel(),
            )
            self.identity_status.configure(
                text="Identificación preparada; falta cargar el JSON.",
                text_color=COLOR_ACENTO,
            )
            return True
        self.parent_app.update_project_identification(values)
        self.refresh()
        messagebox.showinfo(
            "Consulta de proyecto", "Identificación guardada localmente.",
            parent=self.winfo_toplevel(),
        )
        return True

    def clear_project(self):
        if self.parent_app.clear_project():
            self.refresh()

    def copy_path(self):
        if not self.context.path:
            return
        self.clipboard_clear()
        self.clipboard_append(self.context.path)
        self.source_status.configure(text="Ruta copiada al portapapeles.")

    def export_txt(self):
        if not self.context.active:
            return
        identity = self.context.identification
        stem = "_".join(filter(None, (
            identity.get("ot", ""), identity.get("structure_name", ""),
            identity.get("revision", ""),
        ))) or Path(self.context.filename).stem
        safe_stem = "".join(
            char if char.isalnum() or char in "-_. " else "-" for char in stem).strip()
        path = filedialog.asksaveasfilename(
            title="Exportar consulta del proyecto",
            defaultextension=".txt",
            initialfile=f"{safe_stem} - Consulta.txt",
            filetypes=(("Archivo de texto", "*.txt"),),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as output:
                output.write(project_text(self.context))
        except OSError as error:
            messagebox.showerror(
                "Exportar consulta", f"No se pudo crear el archivo:\n{error}",
                parent=self.winfo_toplevel(),
            )
            return
        self.parent_app.log_r(f"[OK] Consulta de proyecto exportada: {path}")
        messagebox.showinfo(
            "Exportar consulta", f"Consulta exportada correctamente:\n{path}",
            parent=self.winfo_toplevel(),
        )

    def refresh(self):
        for key, variable in self.identity_vars.items():
            variable.set(self.context.identification.get(key, ""))
        complete = self.context.complete_identification
        self.identity_status.configure(
            text=("Identificación completa y guardada."
                  if complete else "Completa OT, Revisión y Nombre de estructura."),
            text_color=COLOR_ACENTO if complete else COLOR_TEXTO_SUAVE,
        )
        active = self.context.active
        self.path_var.set(self.context.path or "Ningún proyecto cargado")
        for button in (self.copy_button, self.clear_button, self.export_button):
            button.configure(state="normal" if active else "disabled")
        if active:
            warning_count = len(self.context.warnings)
            self.source_status.configure(
                text=(f"JSON válido · {self.context.filename} · "
                      f"{warning_count} advertencia(s)"),
                text_color=COLOR_ACENTO if not warning_count else COLOR_MOSTAZA,
            )
        else:
            self.source_status.configure(
                text="Carga un archivo para comenzar.", text_color=COLOR_TEXTO_SUAVE)
        token = (
            self.context.sha256 or id(self.context.data),
            tuple(self.context.warnings), bool(self.context.active),
        )
        if token != self._render_token:
            self._render_token = token
            self._render_sections()
        else:
            self._sync_page_navigation()

    def _render_sections(self):
        for child in self.sections_host.winfo_children():
            child.destroy()
        self._anchors = {
            "identificacion": self.identity_panel,
            "fuente": self.source_panel,
        }
        if not self.context.active:
            ctk.CTkLabel(
                self.sections_host,
                text="La información técnica aparecerá aquí después de cargar el JSON.",
                font=FUENTE_NORMAL, text_color=COLOR_TEXTO_SUAVE,
            ).pack(anchor="w", padx=6, pady=20)
            self._sync_page_navigation()
            return

        for section_data in project_sections(self.context.data):
            panel = self._labelframe(self.sections_host, section_data["title"].upper())
            panel.pack(fill="x", pady=(0, 10))
            self._anchors[section_data["anchor"]] = panel
            content = ctk.CTkFrame(panel, fg_color=COLOR_FONDO, corner_radius=0)
            content.pack(fill="x", padx=10, pady=8)
            for group_index, group in enumerate(section_data["groups"]):
                if group_index:
                    ttk.Separator(
                        content, orient="horizontal", bootstyle="secondary",
                    ).pack(fill="x", pady=(10, 7))
                ctk.CTkLabel(
                    content, text=group["title"].upper(), font=FUENTE_NORMAL,
                    text_color=COLOR_ACENTO, anchor="w",
                ).pack(fill="x", pady=(0, 5))
                table = ctk.CTkFrame(content, fg_color=COLOR_FONDO, corner_radius=0)
                table.pack(fill="x")
                table.grid_columnconfigure(1, weight=1)
                for row, (_path, label, value) in enumerate(group["rows"]):
                    ctk.CTkLabel(
                        table, text=label, font=FUENTE_NORMAL_PEQUENA,
                        text_color=COLOR_TEXTO_SUAVE, anchor="w",
                    ).grid(row=row, column=0, sticky="nw", padx=(0, 18), pady=2)
                    ctk.CTkLabel(
                        table, text=value, font=FUENTE_NORMAL,
                        text_color=COLOR_TEXTO, anchor="w", justify="left",
                        wraplength=680,
                    ).grid(row=row, column=1, sticky="ew", pady=2)
        if self.context.warnings:
            warning = self._labelframe(self.sections_host, "ADVERTENCIAS")
            warning.pack(fill="x", pady=(0, 10))
            self._anchors["advertencias"] = warning
            ctk.CTkLabel(
                warning, text="\n".join(f"• {item}" for item in self.context.warnings),
                font=FUENTE_NORMAL, text_color=COLOR_MOSTAZA,
                anchor="w", justify="left",
            ).pack(fill="x", padx=12, pady=10)
        self._sync_page_navigation()

    def _sync_page_navigation(self):
        if not self.winfo_manager():
            return
        entries = [("Identificación", "identificacion"), ("Fuente JSON", "fuente")]
        entries.extend(
            (section["title"], section["anchor"])
            for section in project_sections(self.context.data) if self.context.active
        )
        if self.context.warnings:
            entries.append(("Advertencias", "advertencias"))
        self.parent_app.configurar_navegacion_pagina("consulta", tuple(entries))

    def ir_a_seccion(self, anchor):
        target = self._anchors.get(anchor)
        if target is None:
            return
        self.page.update_idletasks()
        total = max(1, self.page.winfo_reqheight())
        y = target.winfo_y()
        ancestor = target.master
        while ancestor is not None and ancestor is not self.page:
            y += ancestor.winfo_y()
            ancestor = getattr(ancestor, "master", None)
        self.page._parent_canvas.yview_moveto(max(0.0, min(1.0, y / total)))
        self.parent_app.marcar_navegacion_pagina(anchor)
