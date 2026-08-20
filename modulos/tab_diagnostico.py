import os
import threading
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from sincal_cad_engine import discover_cad_engines, save_engine_selection
from sincal_diagnostics import collect_diagnostics, create_diagnostic_bundle, format_summary, record_incident
from sincal_runtime import RUTA_DATOS_USUARIO
from sincal_ui import (
    COLOR_ACENTO,
    COLOR_GRIS_BOTON,
    COLOR_GRIS_BOTON_HOVER,
    COLOR_MOSTAZA,
    COLOR_PANEL,
    COLOR_TEXTO,
    FUENTE_NORMAL,
    FUENTE_SUBTITULO,
    FUENTE_TITULO,
)


class TabDiagnostico(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.engines_by_label = {}
        self._running = False
        self._setup_ui()
        self.after(300, self.ejecutar_diagnostico)

    def _setup_ui(self):
        title_font = FUENTE_TITULO
        subtitle_font = FUENTE_SUBTITULO
        normal_font = FUENTE_NORMAL
        color_title = COLOR_MOSTAZA
        color_text = COLOR_TEXTO

        container = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            container, text="DIAGNÓSTICO Y SOPORTE", font=title_font, text_color=color_title,
        ).pack(anchor="w", padx=8, pady=(4, 2))
        ctk.CTkLabel(
            container,
            text=(
                "Comprueba recursos, CMD, PowerShell y motores CAD. Los informes son locales, "
                "no incluyen DWG ni credenciales y anonimizan rutas personales."
            ),
            font=normal_font, text_color=color_text, wraplength=850, justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 12))

        engine_frame = ctk.CTkFrame(container, fg_color=COLOR_PANEL, corner_radius=0)
        engine_frame.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(
            engine_frame, text="Motor para procesamiento masivo", font=subtitle_font,
            text_color=color_title,
        ).pack(anchor="w", padx=12, pady=(10, 4))
        engine_row = ctk.CTkFrame(engine_frame, fg_color="transparent")
        engine_row.pack(fill="x", padx=12, pady=(0, 10))
        self.engine_menu = ctk.CTkOptionMenu(
            engine_row, values=["Buscando motores CAD..."], font=normal_font,
            dropdown_font=normal_font, corner_radius=0,
        )
        self.engine_menu.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_save_engine = ctk.CTkButton(
            engine_row, text="Usar este motor", font=normal_font, corner_radius=0,
            command=self.guardar_motor, state="disabled",
        )
        self.btn_save_engine.pack(side="right")

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=6)
        self.btn_run = ctk.CTkButton(
            actions, text="Ejecutar diagnóstico", font=normal_font, corner_radius=0,
            command=self.ejecutar_diagnostico,
        )
        self.btn_run.pack(side="left", padx=(0, 8))
        self.btn_report = ctk.CTkButton(
            actions, text="Generar informe ZIP", font=normal_font, corner_radius=0,
            fg_color=COLOR_ACENTO, command=self.generar_informe,
        )
        self.btn_report.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions, text="Abrir datos locales", font=normal_font, corner_radius=0,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER, command=lambda: os.startfile(RUTA_DATOS_USUARIO),
        ).pack(side="left")

        ctk.CTkLabel(
            container, text="Descripción opcional del problema", font=subtitle_font,
            text_color=color_title,
        ).pack(anchor="w", padx=8, pady=(10, 4))
        self.description = ctk.CTkTextbox(
            container, height=80, font=normal_font, fg_color=COLOR_PANEL, corner_radius=0,
        )
        self.description.pack(fill="x", padx=8, pady=(0, 8))

        self.status = ctk.CTkLabel(
            container, text="Preparando diagnóstico...", font=normal_font,
            text_color="#AAAAAA",
        )
        self.status.pack(anchor="w", padx=8, pady=(6, 2))
        self.results = ctk.CTkTextbox(
            container, height=310, font=normal_font, fg_color="#111111",
            text_color="#DDDDDD", state="disabled", corner_radius=0,
        )
        self.results.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    def _ui(self, callback, *args, **kwargs):
        if hasattr(self.parent_app, "_ui"):
            self.parent_app._ui(callback, *args, **kwargs)
        else:
            self.after(0, lambda: callback(*args, **kwargs))

    def _set_running(self, running):
        self._running = running
        state = "disabled" if running else "normal"
        self.btn_run.configure(state=state)
        self.btn_report.configure(state=state)

    def ejecutar_diagnostico(self):
        if self._running:
            return
        self._set_running(True)
        self.status.configure(text="Comprobando recursos, comandos y motores CAD...", text_color=COLOR_MOSTAZA)
        threading.Thread(target=self._worker_diagnostico, daemon=True).start()

    def _worker_diagnostico(self):
        try:
            project_path = getattr(self.parent_app, "ruta_renombre", None) or None
            report = collect_diagnostics(project_path=project_path)
            engines = discover_cad_engines()
            self._ui(self._render_report, report, engines)
        except Exception as error:
            record_incident("diagnostico", "error", {"error": str(error)})
            self._ui(self._show_error, str(error))

    def _render_report(self, report, engines):
        self.engines_by_label = {engine.label: engine for engine in engines}
        labels = list(self.engines_by_label) or ["No se detectaron motores CAD"]
        self.engine_menu.configure(values=labels)
        selected = (report.get("cad") or {}).get("selected") or {}
        selected_path = selected.get("path")
        selected_label = next(
            (engine.label for engine in engines if engine.path == selected_path),
            labels[0],
        )
        self.engine_menu.set(selected_label)
        self.btn_save_engine.configure(state="normal" if engines else "disabled")

        summary = format_summary(report)
        incidents = report.get("incidents") or []
        if incidents:
            summary += f"\nINCIDENTES LOCALES RECIENTES: {len(incidents)}\n"
            for incident in incidents[-8:]:
                summary += (
                    f"- {incident.get('timestamp', '')} · {incident.get('operation', '')} "
                    f"· {incident.get('status', '')}\n"
                )
        self.results.configure(state="normal")
        self.results.delete("1.0", "end")
        self.results.insert("1.0", summary)
        self.results.configure(state="disabled")
        has_error = any(item.get("level") == "error" for item in report.get("findings") or [])
        self.status.configure(
            text="Se encontraron elementos que requieren atención." if has_error else "Diagnóstico completado sin bloqueos.",
            text_color="#FF6B6B" if has_error else "#57D163",
        )
        self._set_running(False)

    def _show_error(self, detail):
        self.status.configure(text="El diagnóstico no pudo completarse.", text_color="#FF6B6B")
        self._set_running(False)
        messagebox.showerror("Diagnóstico SINCAL", f"No se pudo completar el diagnóstico.\n\n{detail}")

    def guardar_motor(self):
        engine = self.engines_by_label.get(self.engine_menu.get())
        if not engine:
            return messagebox.showwarning("Motor CAD", "Selecciona un motor CAD válido.")
        try:
            selected = save_engine_selection(engine, tuple(self.engines_by_label.values()))
            self.parent_app.cad_exe_path = selected.path
            self.parent_app.es_zwcad = selected.product == "ZWCAD"
            record_incident("seleccion_motor_cad", "ok", {"engine": selected.to_dict()})
            messagebox.showinfo(
                "Workbench",
                f"Motor guardado para procesamiento masivo:\n\n{selected.label}\n{selected.path}",
            )
            self.ejecutar_diagnostico()
        except Exception as error:
            record_incident("seleccion_motor_cad", "error", {"error": str(error)})
            messagebox.showerror("Motor CAD", f"No fue posible guardar el motor.\n\n{error}")

    def generar_informe(self):
        if self._running:
            return
        default_name = f"SINCAL_Diagnostico_{datetime.now():%Y%m%d_%H%M}.zip"
        destination = filedialog.asksaveasfilename(
            title="Guardar informe de diagnóstico",
            defaultextension=".zip",
            initialfile=default_name,
            filetypes=[("Informe ZIP", "*.zip")],
        )
        if not destination:
            return
        self._set_running(True)
        self.status.configure(text="Generando informe anonimizado...", text_color=COLOR_MOSTAZA)
        description = self.description.get("1.0", "end").strip()
        project_path = getattr(self.parent_app, "ruta_renombre", None) or None
        threading.Thread(
            target=self._worker_report,
            args=(destination, project_path, description),
            daemon=True,
        ).start()

    def _worker_report(self, destination, project_path, description):
        try:
            path, report = create_diagnostic_bundle(
                destination,
                project_path=project_path,
                description=description,
            )
            record_incident("informe_diagnostico", "ok", {"report_id": report["report_id"]})
            self._ui(self._report_ready, path, report["report_id"])
        except Exception as error:
            record_incident("informe_diagnostico", "error", {"error": str(error)})
            self._ui(self._show_error, str(error))

    def _report_ready(self, path, report_id):
        self._set_running(False)
        self.status.configure(text=f"Informe {report_id} generado correctamente.", text_color="#57D163")
        messagebox.showinfo(
            "Workbench",
            "Informe generado correctamente. Puedes enviarlo al responsable de SINCAL.\n\n"
            f"{path}",
        )
