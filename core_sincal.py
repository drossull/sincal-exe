import logging
import os
import queue
import shutil
import subprocess
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from logging.handlers import RotatingFileHandler
from tkinter import messagebox

import customtkinter as ctk
import pythoncom
import requests
import win32com.client
from customtkinter import filedialog

from modulos.tab_armaduras import TabArmaduras
from modulos.tab_diagnostico import TabDiagnostico
from modulos.tab_docs import TabDocs
from modulos.tab_ubicacion import TabUbicacion
from sincal_cad_engine import ensure_cad_engine
from sincal_cad_integration import registrar_ruta_cad_usuario
from sincal_diagnostics import record_incident
from sincal_resource_sync import (
    active_resource_paths,
    apply_resource_updates,
    check_resource_updates,
    distribution_manifest_revision,
    materialize_cad_resources,
    record_resource_state,
)
from sincal_runtime import (
    RUTA_DATOS_USUARIO,
    RUTA_LOGS,
    VERSION_ACTUAL,
    asegurar_directorios,
    is_newer_version,
    ruta_cad_usuario,
)
from sincal_runtime import (
    ruta_recurso as runtime_ruta_recurso,
)
from sincal_update_config import (
    DISTRIBUTION_RELEASES_URL,
    api_url as distribution_api_url,
)
from sincal_ui import (
    COLOR_ACENTO,
    COLOR_ACENTO_HOVER,
    COLOR_BORDE,
    COLOR_FONDO,
    COLOR_GRIS_BOTON,
    COLOR_GRIS_BOTON_HOVER,
    COLOR_MOSTAZA,
    COLOR_PANEL,
    COLOR_PANEL_OSCURO,
    COLOR_TEXTO,
    COLOR_TEXTO_SUAVE,
    FUENTE_CONSOLA,
    FUENTE_MENU,
    FUENTE_NORMAL,
    FUENTE_NORMAL_PEQUENA,
    FUENTE_SUBTITULO,
    FUENTE_SUBTITULO_PEQUENO,
    FUENTE_TITULO,
    FUENTE_TITULO_PEQUENO,
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
        super().__init__()
        registrar_fuentes()
        asegurar_directorios()
        self.logger = configurar_logging()
        self.historial_logs = []
        self._cerrando = False
        self._ui_queue = queue.Queue()
        self.title("SINCAL 2.0 — Workbench")
        self.geometry("1280x820")
        self.minsize(980, 640)
        self.configure(fg_color=COLOR_FONDO)
        try:
            self.iconbitmap(obtener_ruta_recurso("logo.ico"))
        except:
            pass

        self.version_local_actual = VERSION_ACTUAL
        self.tutoriales, self.cad_exe_path, self.es_zwcad, self.cancelar_comando_vivo = {
        }, None, False, False
        self.ruta_renombre, self.checkboxes_archivos = "", []
        self._resource_check_running = False
        self._last_resource_offer_tree = ""
        self._resource_manifest_revision = ""
        self._resource_poll_job = None
        self._sidebar_collapsed = False
        self._sidebar_widths = {"Compacto": 210, "Estándar": 270, "Amplio": 340}
        self._sidebar_size = "Estándar"
        self._console_mode = "Oculta"
        self._sections = {}
        self._nav_buttons = {}
        self.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        self.after(50, self._procesar_ui_queue)

        self._construir_shell()
        self._crear_secciones()
        self.setup_tab_sincronizador()
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
            self, width=self._sidebar_widths[self._sidebar_size], fg_color=COLOR_PANEL_OSCURO,
            corner_radius=0, border_width=1, border_color=COLOR_BORDE,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=14, pady=(18, 10))
        self.brand_title = ctk.CTkLabel(
            brand, text="SINCAL 2.0", font=FUENTE_TITULO_PEQUENO, text_color=COLOR_MOSTAZA,
        )
        self.brand_title.pack(side="left", anchor="w")
        self.btn_retraer = ctk.CTkButton(
            brand, text="‹", width=32, height=30, font=FUENTE_SUBTITULO_PEQUENO,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            command=self.alternar_menu, corner_radius=0,
        )
        self.btn_retraer.pack(side="right")
        self.brand_subtitle = ctk.CTkLabel(
            self.sidebar, text="WORKBENCH DE INGENIERÍA", font=FUENTE_NORMAL_PEQUENA,
            text_color=COLOR_TEXTO_SUAVE,
        )
        self.brand_subtitle.pack(anchor="w", padx=16, pady=(0, 18))

        self.nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_container.pack(fill="both", expand=True, padx=8)
        self.nav_items = (
            ("sincronizador", "⌂  Sincronizador", "Sincronizador"),
            ("documentacion", "▤  Documentación", "Documentación"),
            ("procesamiento", "▣  Procesamiento masivo", "Procesamiento masivo"),
            ("ubicacion", "⌖  Ubicación", "Ubicación"),
            ("estructural", "▦  Módulo estructural", "Módulo estructural"),
            ("conversion", "⇄  Conversión DXF", "Conversión DXF"),
            ("diagnostico", "◈  Diagnóstico", "Diagnóstico"),
        )
        for key, label, title in self.nav_items:
            button = ctk.CTkButton(
                self.nav_container, text=label, font=FUENTE_MENU, anchor="w",
                fg_color="transparent", hover_color="#3A3A3A", text_color=COLOR_TEXTO,
                corner_radius=0, height=38,
                command=lambda selected=key: self.seleccionar_seccion(selected),
            )
            button.pack(fill="x", pady=2)
            self._nav_buttons[key] = button

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=12)
        self.lbl_menu_size = ctk.CTkLabel(
            footer, text="Tamaño del menú", font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
        )
        self.lbl_menu_size.pack(anchor="w", pady=(0, 4))
        self.menu_size = ctk.CTkOptionMenu(
            footer, values=list(self._sidebar_widths), command=self.cambiar_ancho_menu,
            font=FUENTE_NORMAL_PEQUENA, dropdown_font=FUENTE_NORMAL_PEQUENA,
            fg_color=COLOR_GRIS_BOTON, button_color=COLOR_ACENTO, button_hover_color=COLOR_ACENTO_HOVER,
            corner_radius=0,
        )
        self.menu_size.set(self._sidebar_size)
        self.menu_size.pack(fill="x")

        self.workspace = ctk.CTkFrame(self, fg_color=COLOR_FONDO, corner_radius=0)
        self.workspace.pack(side="right", fill="both", expand=True)
        header = ctk.CTkFrame(self.workspace, height=58, fg_color=COLOR_PANEL, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.section_title = ctk.CTkLabel(
            header, text="Sincronizador", font=FUENTE_SUBTITULO, text_color=COLOR_MOSTAZA,
        )
        self.section_title.pack(side="left", padx=22, pady=10)
        ctk.CTkLabel(
            header, text="SINCAL 2.0", font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
        ).pack(side="right", padx=(8, 18))
        self.console_menu = ctk.CTkOptionMenu(
            header, values=["Consola: oculta", "Consola: inferior", "Consola: derecha"],
            command=self.cambiar_modo_consola, font=FUENTE_NORMAL_PEQUENA,
            dropdown_font=FUENTE_NORMAL_PEQUENA, width=156, corner_radius=0,
            fg_color=COLOR_GRIS_BOTON, button_color=COLOR_ACENTO, button_hover_color=COLOR_ACENTO_HOVER,
        )
        self.console_menu.set("Consola: oculta")
        self.console_menu.pack(side="right", padx=10, pady=12)

        self.content_host = ctk.CTkFrame(self.workspace, fg_color=COLOR_FONDO, corner_radius=0)
        self.content_host.pack(fill="both", expand=True)
        self.console_panel = ctk.CTkFrame(
            self.workspace, fg_color=COLOR_PANEL_OSCURO, corner_radius=0,
            border_width=1, border_color=COLOR_BORDE,
        )
        console_header = ctk.CTkFrame(self.console_panel, fg_color="transparent")
        console_header.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(
            console_header, text="CONSOLA", font=FUENTE_SUBTITULO_PEQUENO, text_color=COLOR_MOSTAZA,
        ).pack(side="left")
        ctk.CTkButton(
            console_header, text="Limpiar", font=FUENTE_NORMAL_PEQUENA, width=70, height=26,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=self.limpiar_consola_global,
        ).pack(side="right")
        self.txt_log_global = ctk.CTkTextbox(
            self.console_panel, font=FUENTE_CONSOLA, fg_color="#090909", text_color="#C9FFC9",
            corner_radius=0, state="disabled",
        )
        self.txt_log_global.pack(fill="both", expand=True, padx=12, pady=(2, 12))

    def _crear_secciones(self):
        definitions = (
            ("sincronizador", "Sincronizador"),
            ("documentacion", "Documentación"),
            ("procesamiento", "Procesamiento masivo"),
            ("ubicacion", "Ubicación"),
            ("estructural", "Módulo estructural"),
            ("conversion", "Conversión DXF"),
            ("diagnostico", "Diagnóstico"),
        )
        for key, title in definitions:
            frame = ctk.CTkFrame(self.content_host, fg_color=COLOR_FONDO, corner_radius=0)
            self._sections[key] = (frame, title)
        self.tab_main = self._sections["sincronizador"][0]
        self.tab_docs = self._sections["documentacion"][0]
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
        self.section_title.configure(text=title)
        for item_key, button in self._nav_buttons.items():
            selected = item_key == key
            button.configure(
                fg_color=COLOR_ACENTO if selected else "transparent",
                hover_color=COLOR_ACENTO_HOVER if selected else "#3A3A3A",
                text_color="#FFFFFF" if selected else COLOR_TEXTO,
            )

    def alternar_menu(self):
        self._sidebar_collapsed = not self._sidebar_collapsed
        width = 70 if self._sidebar_collapsed else self._sidebar_widths[self._sidebar_size]
        self.sidebar.configure(width=width)
        self.brand_title.configure(text="S" if self._sidebar_collapsed else "SINCAL 2.0")
        self.brand_subtitle.configure(text="" if self._sidebar_collapsed else "WORKBENCH DE INGENIERÍA")
        self.btn_retraer.configure(text="›" if self._sidebar_collapsed else "‹")
        for key, label, _title in self.nav_items:
            self._nav_buttons[key].configure(text=label.split("  ")[0] if self._sidebar_collapsed else label, anchor="center" if self._sidebar_collapsed else "w")
        if self._sidebar_collapsed:
            self.lbl_menu_size.pack_forget()
            self.menu_size.pack_forget()
        else:
            self.lbl_menu_size.pack(anchor="w", pady=(0, 4))
            self.menu_size.pack(fill="x")

    def cambiar_ancho_menu(self, size):
        if size not in self._sidebar_widths:
            return
        self._sidebar_size = size
        if not self._sidebar_collapsed:
            self.sidebar.configure(width=self._sidebar_widths[size])

    def cambiar_modo_consola(self, option):
        modes = {
            "Consola: oculta": "Oculta",
            "Consola: inferior": "Inferior",
            "Consola: derecha": "Derecha",
        }
        self._console_mode = modes.get(option, "Oculta")
        self.content_host.pack_forget()
        self.console_panel.pack_forget()
        if self._console_mode == "Inferior":
            self.content_host.pack(side="top", fill="both", expand=True)
            self.console_panel.configure(height=210, width=1)
            self.console_panel.pack(side="bottom", fill="x")
            self.console_panel.pack_propagate(False)
        elif self._console_mode == "Derecha":
            self.console_panel.configure(width=390, height=1)
            self.console_panel.pack(side="right", fill="y")
            self.console_panel.pack_propagate(False)
            self.content_host.pack(side="left", fill="both", expand=True)
        else:
            self.content_host.pack(fill="both", expand=True)
        self._actualizar_consola_global()

    def mostrar_ventana_log(self):
        self.console_menu.set("Consola: inferior")
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
                "Error SINCAL",
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
        self.logger.info("Cierre solicitado: SINCAL finalizará sin permanecer en segundo plano.")
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
    def cargar_info_github(self):
        try:
            r = requests.get(
                distribution_api_url("commits"), params={"per_page": 10}, timeout=5)
            if r.status_code == 200:
                lineas = []

                meses = {"01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
                         "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"}

                for c in r.json():
                    raw_date = c['commit']['author']['date']
                    dt_local = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).astimezone()

                    mes_str = meses[dt_local.strftime("%m")]
                    fecha_formateada = f"{dt_local.strftime('%d')} {mes_str} {dt_local.strftime('%y %H:%M')}"

                    sha_completo = c['sha']
                    version_mostrar = sha_completo[:7]

                    mensaje = c['commit']['message'].strip()
                    mensaje = mensaje.replace(
                        "\r\n", " + ").replace("\n\n", " + ").replace("\n", " + ")

                    lineas.append(f"• ({version_mostrar}) / {fecha_formateada} / {mensaje}\n")

                self._ui(self._set_textbox_content, self.txt_updates, "".join(lineas))
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
            "SINCAL ya no descarga código ejecutable en caliente.\n"
            "¿Deseas abrir la página oficial de releases para instalar la actualización?"
        )

        if messagebox.askyesno("¡Actualización SINCAL Disponible!", msg):
            webbrowser.open(URL_RELEASES)
            self.log("[!] Abriendo página oficial de releases para actualizar SINCAL.")
        else:
            self.log(
                f"[!] Actualización a {nueva_version} pospuesta por el usuario.")

    def setup_tab_sincronizador(self):
        portada = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        portada.pack(fill="x", padx=40, pady=(38, 20))
        ctk.CTkLabel(
            portada, text="SINCAL 2.0", font=FUENTE_TITULO, text_color=COLOR_MOSTAZA,
        ).pack(pady=(4, 12))
        ctk.CTkLabel(
            portada,
            text=("Un workbench para estandarizar CAD, automatizar planos y concentrar las "
                  "herramientas de ingeniería que acompañan cada proyecto."),
            font=FUENTE_NORMAL, text_color=COLOR_TEXTO, justify="center", wraplength=720,
        ).pack(padx=30)

        self.btn_actualizar = ctk.CTkButton(
            self.tab_main, text="Abrir instalador oficial", font=FUENTE_SUBTITULO_PEQUENO,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=lambda: webbrowser.open(URL_RELEASES),
        )
        self.btn_actualizar.pack(pady=(0, 14))

        botones_sec_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        botones_sec_frame.pack(pady=5)
        ctk.CTkButton(botones_sec_frame, text="Abrir carpeta local", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
                      corner_radius=0, text_color=COLOR_TEXTO, hover_color=COLOR_GRIS_BOTON_HOVER, command=self.abrir_carpeta_local).pack(side="left", padx=6)
        ctk.CTkButton(botones_sec_frame, text="Preparar integración CAD", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
                      corner_radius=0, text_color=COLOR_TEXTO, hover_color=COLOR_GRIS_BOTON_HOVER, command=self.forzar_path_manual).pack(side="left", padx=6)

        self.btn_sync_resources = ctk.CTkButton(botones_sec_frame, text="Actualizar recursos CAD", font=FUENTE_NORMAL, fg_color=COLOR_ACENTO,
                                                corner_radius=0, text_color="#FFFFFF", hover_color=COLOR_ACENTO_HOVER, command=self.verificar_recursos_manual)
        self.btn_sync_resources.pack(side="left", padx=6)

        self.btn_verificar_update = ctk.CTkButton(botones_sec_frame, text="Verificar nueva actualización", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON,
                                                  corner_radius=0, text_color=COLOR_TEXTO, hover_color=COLOR_GRIS_BOTON_HOVER, command=self.verificar_actualizacion_manual)
        self.btn_verificar_update.pack(side="left", padx=6)

        self.frame_updates = ctk.CTkFrame(
            self.tab_main, fg_color="transparent")
        self.frame_updates.pack(fill="x", padx=40, pady=5)
        ctk.CTkLabel(self.frame_updates, text="Historial de cambios",
                     font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(anchor="w")
        self.txt_updates = ctk.CTkTextbox(
            self.frame_updates, width=850, height=220, font=FUENTE_NORMAL, fg_color=COLOR_PANEL, text_color=COLOR_TEXTO, state="disabled", corner_radius=0)
        self.txt_updates.pack(pady=5)

        self._iniciar_verificacion_recursos()
        self._programar_monitoreo_recursos()

    def verificar_recursos_manual(self):
        self.log("\n[*] Buscando actualizaciones menores de recursos CAD en GitHub...")
        self.btn_sync_resources.configure(state="disabled", text="Verificando...")
        if not self._iniciar_verificacion_recursos(manual=True):
            self.log("[*] Ya hay una comprobación de recursos en curso.")
            self.btn_sync_resources.configure(state="normal", text="Actualizar recursos CAD")

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
                self._ui(self.btn_sync_resources.configure, state="normal", text="Actualizar recursos CAD")

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
        if messagebox.askyesno("Actualización de recursos SINCAL", mensaje, parent=self):
            self.btn_sync_resources.configure(state="disabled", text="Actualizando...")
            threading.Thread(target=self._hilo_aplicar_recursos, args=(plan,), daemon=True).start()
        else:
            self.log("[!] Actualización menor pospuesta por el usuario.")
            if manual:
                self.btn_sync_resources.configure(state="normal", text="Actualizar recursos CAD")

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
                "No se aplicó completamente la actualización. SINCAL volverá a intentarlo al iniciar.\n\n"
                f"Detalle: {e}",
            )
            self._ui(self.btn_sync_resources.configure, state="normal", text="Actualizar recursos CAD")
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
            "Cierra y vuelve a abrir SINCAL para refrescar toda la interfaz. "
            + estado_cad
        )
        if avisos:
            mensaje += "\n\n" + "\n".join(avisos)
        self._ui(
            messagebox.showwarning if avisos else messagebox.showinfo,
            "Workbench",
            mensaje,
        )
        self._ui(self.btn_sync_resources.configure, state="normal", text="Actualizar recursos CAD")

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
            state="disabled", text="Verificando...")
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
                     state="normal", text="Verificar nueva actualización")

    def setup_tab_renombrado(self):
        lbl_titulo = ctk.CTkLabel(
            self.tab_renombrado, text="PROCESAMIENTO MASIVO DE PLANOS", font=FUENTE_TITULO, text_color=COLOR_TITULO)
        lbl_titulo.pack(pady=(10, 5))

        top_frame = ctk.CTkFrame(self.tab_renombrado, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=5)
        self.btn_browse_adv = ctk.CTkButton(top_frame, text="📁 Cargar Carpeta DWG/DXF", font=FUENTE_NORMAL, width=180,
                                            corner_radius=0, fg_color="#444444", hover_color="#555555", command=self.cargar_archivos_renombrado)
        self.btn_browse_adv.pack(side="left")
        self.lbl_ruta_adv = ctk.CTkLabel(
            top_frame, text="Ruta: Ninguna", font=FUENTE_NORMAL, text_color="#888888")
        self.lbl_ruta_adv.pack(side="left", padx=15)

        split_frame = ctk.CTkFrame(self.tab_renombrado, fg_color="transparent")
        split_frame.pack(fill="both", expand=True, padx=20, pady=5)
        split_frame.grid_columnconfigure(0, weight=1)
        split_frame.grid_columnconfigure(1, weight=2)
        split_frame.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(split_frame, fg_color="#1E1E1E",
                                  corner_radius=0, border_width=1, border_color="#444444")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(left_frame, text="1. Archivos a procesar:", font=FUENTE_SUBTITULO,
                     text_color=COLOR_TITULO).pack(pady=(15, 5), padx=15, anchor="w")

        btn_tools = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_tools.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(btn_tools, text="Marcar", width=60, corner_radius=0, font=FUENTE_NORMAL, fg_color="#444444",
                      hover_color="#555555", command=self.marcar_todos).pack(side="left", expand=True, fill="x", padx=(0, 2))
        ctk.CTkButton(btn_tools, text="Desmarcar", width=60, corner_radius=0, font=FUENTE_NORMAL, fg_color="#444444",
                      hover_color="#555555", command=self.desmarcar_todos).pack(side="left", expand=True, fill="x", padx=(2, 0))

        self.scroll_archivos = ctk.CTkScrollableFrame(
            left_frame, fg_color="#2B2B2B", corner_radius=0)
        self.scroll_archivos.pack(
            fill="both", expand=True, padx=15, pady=(5, 15))

        right_frame = ctk.CTkFrame(split_frame, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew")

        h1_frame = ctk.CTkFrame(right_frame, fg_color="#1E1E1E",
                                corner_radius=0, border_width=1, border_color="#444444")
        h1_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(h1_frame, text="2. Buscar y Reemplazar (Renombrado Automático)",
                     font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(anchor="w", padx=15, pady=(15, 5))

        entry_row = ctk.CTkFrame(h1_frame, fg_color="transparent")
        entry_row.pack(fill="x", padx=15, pady=5)
        self.ent_buscar_adv = ctk.CTkEntry(
            entry_row, placeholder_text="Buscar texto (Ej: HL-)", font=FUENTE_NORMAL, corner_radius=0)
        self.ent_buscar_adv.pack(
            side="left", fill="x", expand=True, padx=(0, 10))
        self.ent_reemplazo_adv = ctk.CTkEntry(
            entry_row, placeholder_text="Reemplazar con (Ej: PL-)", font=FUENTE_NORMAL, corner_radius=0)
        self.ent_reemplazo_adv.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(h1_frame, text="Aplicar Reemplazo a la Selección", font=FUENTE_NORMAL, corner_radius=0, fg_color="transparent", border_width=1,
                      border_color=COLOR_ACENTO, text_color=COLOR_ACENTO, hover_color="#444444", command=self.aplicar_reemplazo_adv).pack(pady=15, padx=15, fill="x")

        self.log_rename = ctk.CTkTextbox(h1_frame, height=60, font=FUENTE_CONSOLA,
                                         fg_color="#000000", text_color="#AAAAAA", state="disabled", corner_radius=0)
        self.log_rename.pack(fill="x", padx=15, pady=(0, 15))

        self.frame_live = ctk.CTkFrame(
            right_frame, fg_color="#1E1E1E", border_width=1, border_color="#444444", corner_radius=0)
        self.frame_live.pack(fill="x")

        top_live_frame = ctk.CTkFrame(self.frame_live, fg_color="transparent")
        top_live_frame.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(top_live_frame, text="3. Comandos en vivo (Inyectar en planos abiertos):",
                     font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(side="left")

        bot_live_frame = ctk.CTkFrame(self.frame_live, fg_color="transparent")
        bot_live_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.entrada_comando = ctk.CTkEntry(
            bot_live_frame, font=FUENTE_NORMAL, placeholder_text="Ej: ZE, _QSAVE", corner_radius=0)
        self.entrada_comando.pack(
            side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_enviar_cmd = ctk.CTkButton(bot_live_frame, text="Ejecutar", font=FUENTE_NORMAL, fg_color="transparent", border_width=1,
                                            border_color=COLOR_ACENTO, corner_radius=0, hover_color="#444444", text_color=COLOR_TEXTO, width=80, command=self.enviar_comando_en_vivo)
        self.btn_enviar_cmd.pack(side="left", padx=(0, 10))

        self.btn_cancelar_cmd = ctk.CTkButton(bot_live_frame, text="Cancelar", font=FUENTE_NORMAL, fg_color="#D9534F",
                                              hover_color="#C9302C", width=80, corner_radius=0, state="disabled", command=self.detener_comando_en_vivo)
        self.btn_cancelar_cmd.pack(side="left")

        bottom_frame = ctk.CTkFrame(self.tab_renombrado, fg_color=COLOR_PANEL,
                                    corner_radius=0, border_width=1, border_color=COLOR_BORDE)
        bottom_frame.pack(fill="x", padx=20, pady=(10, 15))

        ctk.CTkLabel(bottom_frame, text="4. Automatización de planos cerrados",
                     font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(anchor="w", padx=15, pady=(10, 5))
        ctk.CTkLabel(
            bottom_frame, text="Los resultados se muestran en la consola acoplable.",
            font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
        ).pack(anchor="w", padx=15, pady=(0, 4))

        btn_container = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        btn_container.pack(fill="x", padx=15, pady=5)

        def cmd_ps(nombre_script):
            ruta = runtime_ruta_recurso("scripts", f"{nombre_script}.ps1")
            return f"& '{ruta}'"

        for i in range(4):
            btn_container.grid_columnconfigure(
                i, weight=1, uniform="botones_script")

        ctk.CTkButton(btn_container, text="▶ Auditar", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("AUDIT"))).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Purgar", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=0,
                      command=lambda: self.lanzar_script(cmd_ps("PURGEALL"))).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Encuadrar vista", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("ZE"))).grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Eliminar Layout2", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("DL2"))).grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(btn_container, text="▶ Bloquear Viewports", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("BV"))).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Configurar en A1", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("PAGESETUP-A1"))).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Ploteo A1", font=FUENTE_NORMAL, fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER, corner_radius=0,
                      command=lambda: self.lanzar_script(cmd_ps("PUBLISH-A1"))).grid(row=1, column=2, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="Abrir consola", font=FUENTE_NORMAL, fg_color=COLOR_ACENTO, hover_color=COLOR_ACENTO_HOVER, corner_radius=0,
                      command=self.mostrar_ventana_log).grid(row=1, column=3, padx=5, pady=5, sticky="ew")

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
        ctk.CTkButton(
            controls, text="Seleccionar carpeta DXF", font=FUENTE_NORMAL,
            fg_color=COLOR_GRIS_BOTON, hover_color=COLOR_GRIS_BOTON_HOVER,
            corner_radius=0, command=self.cargar_archivos_conversion,
        ).pack(side="left")
        self.lbl_ruta_conversion = ctk.CTkLabel(
            controls, text="Ruta: Ninguna", font=FUENTE_NORMAL_PEQUENA, text_color=COLOR_TEXTO_SUAVE,
        )
        self.lbl_ruta_conversion.pack(side="left", padx=14)

        panel = ctk.CTkFrame(
            self.tab_conversion, fg_color=COLOR_PANEL, corner_radius=0,
            border_width=1, border_color=COLOR_BORDE,
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
        ctk.CTkButton(
            panel, text="Convertir DXF a DWG", font=FUENTE_SUBTITULO_PEQUENO,
            fg_color=COLOR_ACENTO, hover_color=COLOR_ACENTO_HOVER, corner_radius=0,
            command=self.convertir_dxf_a_dwg,
        ).pack(fill="x", padx=16, pady=(0, 16))

    def cargar_archivos_conversion(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta con archivos DXF")
        if not carpeta:
            return
        self.ruta_conversion = carpeta
        self.lbl_ruta_conversion.configure(text=f"Ruta: {carpeta}", text_color=COLOR_TEXTO)
        self.refrescar_lista_conversion()

    def refrescar_lista_conversion(self):
        for widget in self.scroll_dxf.winfo_children():
            widget.destroy()
        self.checkboxes_dxf = []
        if not self.ruta_conversion:
            return
        archivos = sorted(
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
        self.lbl_ruta_adv.configure(text=f"Ruta: {c}", text_color=COLOR_TEXTO)
        self.refrescar_lista_archivos()

    def refrescar_lista_archivos(self):
        for w in self.scroll_archivos.winfo_children():
            w.destroy()
        self.checkboxes_archivos = []
        arcs = [f for f in os.listdir(
            self.ruta_renombre) if f.lower().endswith(('.dwg', '.dxf'))]
        for arc in arcs:
            cb = ctk.CTkCheckBox(self.scroll_archivos, text=arc, font=FUENTE_NORMAL,
                                 text_color=COLOR_TEXTO, fg_color=COLOR_ACENTO, hover_color="#005BBF")
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

    def lanzar_script(self, comando_ps):
        if not getattr(self, 'ruta_renombre', None):
            return messagebox.showwarning("Sin ruta", "Por favor, carga una carpeta DWG primero en el paso 1.")

        if self.cad_esta_ejecutandose():
            return messagebox.showwarning(
                "CAD en Uso",
                "Por favor, cierra AutoCAD o ZWCAD completamente antes de ejecutar rutinas masivas.\n\nEsto evita que los archivos estén bloqueados por el programa."
            )

        self.mostrar_ventana_log()
        self.log_script("\n[PROCESAMIENTO MASIVO] Inicio de automatización.\n")

        threading.Thread(target=self._hilo_script, args=(
            comando_ps,), daemon=True).start()

    def _hilo_script(self, comando_ps):
        engine = ensure_cad_engine()
        if engine is None:
            detail = "No se detectó un motor CAD. Abre Diagnóstico y soporte y selecciona uno."
            self.log_script(f"[X] {detail}\n")
            record_incident(
                "procesamiento_masivo", "error", {"error": detail},
                sensitive_paths=(self.ruta_renombre,),
            )
            return

        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            detail = "No se encontró powershell.exe en el equipo."
            self.log_script(f"[X] {detail}\n")
            record_incident(
                "procesamiento_masivo", "error", {"error": detail},
                sensitive_paths=(self.ruta_renombre,),
            )
            return

        self.log_script(
            f"> Directorio Activo: {self.ruta_renombre}\n"
            f"> Motor CAD: {engine.label}\n"
            f"> Ejecutable: {engine.path}\n"
            f"> Comando: {comando_ps}\n" + "-"*60 + "\n"
        )

        comando = [powershell, "-NoProfile", "-NonInteractive",
                   "-ExecutionPolicy", "Bypass", "-Command", comando_ps]
        environment = os.environ.copy()
        environment["SINCAL_CAD_ENGINE"] = engine.path
        started = time.monotonic()
        output_tail = []

        try:
            proceso = subprocess.Popen(
                comando,
                cwd=self.ruta_renombre,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            for linea in iter(proceso.stdout.readline, ''):
                self.log_script(linea)
                output_tail.append(linea)
                if len(output_tail) > 120:
                    output_tail.pop(0)

            proceso.stdout.close()
            proceso.wait()
            if proceso.returncode == 0:
                self.log_script(
                    f"\n[OK] Script finalizado (Código de salida: {proceso.returncode})\n")
                record_incident(
                    "procesamiento_masivo",
                    "ok",
                    {
                        "engine": engine.to_dict(),
                        "returncode": proceso.returncode,
                        "seconds": round(time.monotonic() - started, 3),
                    },
                    sensitive_paths=(self.ruta_renombre,),
                )
            else:
                self.log_script(
                    f"\n[X] Script finalizado con error (Código de salida: {proceso.returncode})\n")
                record_incident(
                    "procesamiento_masivo",
                    "error",
                    {
                        "engine": engine.to_dict(),
                        "returncode": proceso.returncode,
                        "seconds": round(time.monotonic() - started, 3),
                        "output": "".join(output_tail)[-12000:],
                    },
                    sensitive_paths=(self.ruta_renombre,),
                )

        except Exception as e:
            self.log_script(
                f"\n[X] Fallo crítico al lanzar PowerShell:\n{e}\n")
            record_incident(
                "procesamiento_masivo",
                "error",
                {
                    "engine": engine.to_dict(),
                    "error": str(e),
                    "seconds": round(time.monotonic() - started, 3),
                },
                sensitive_paths=(self.ruta_renombre,),
            )

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
                "las rutas de confianza y el cargador automático.",
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
        if hasattr(self, 'log_rename'):
            self._ui(self._append_textbox, self.log_rename, m + "\n")
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
