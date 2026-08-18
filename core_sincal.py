import logging
import os
import queue
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from logging.handlers import RotatingFileHandler
from tkinter import messagebox

import customtkinter as ctk
import pystray
import pythoncom
import requests
import win32com.client
from customtkinter import filedialog
from PIL import Image
from pystray import MenuItem as item

from modulos.tab_armaduras import TabArmaduras
from modulos.tab_docs import TabDocs
from modulos.tab_ubicacion import TabUbicacion
from sincal_cad_integration import registrar_ruta_cad_usuario
from sincal_resource_sync import (
    active_resource_paths,
    apply_resource_updates,
    check_resource_updates,
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
    ruta_runtime,
)
from sincal_runtime import (
    ruta_recurso as runtime_ruta_recurso,
)

# --- CONFIGURACIÓN GLOBALES ---
USUARIO_GITHUB = "drossull"
REPO_GITHUB = "sincal-exe"
URL_RELEASES = f"https://github.com/{USUARIO_GITHUB}/{REPO_GITHUB}/releases"

COLOR_FONDO, COLOR_TITULO, COLOR_TEXTO, COLOR_ACENTO = "#2B2B2B", "#FFBF00", "#CCCCCC", "#007FFF"
FUENTE_TITULO, FUENTE_SUBTITULO, FUENTE_MENU, FUENTE_NORMAL, FUENTE_CONSOLA = [
    ("Consolas", 24, "bold"), ("Consolas", 18,
                               "bold"), ("Consolas", 13), ("Consolas", 12), ("Consolas", 11)
]

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
        asegurar_directorios()
        self.logger = configurar_logging()
        self.historial_logs = []
        self._cerrando = False
        self._ui_queue = queue.Queue()
        self.title("SINCAL - Suite de Herramientas Professional")
        self.geometry("1000x800")
        self.configure(fg_color=COLOR_FONDO)
        try:
            self.iconbitmap(obtener_ruta_recurso("logo.ico"))
        except:
            pass

        self.version_local_actual = VERSION_ACTUAL
        self.tutoriales, self.cad_exe_path, self.es_zwcad, self.cancelar_comando_vivo = {
        }, None, False, False
        self.ruta_renombre, self.checkboxes_archivos, self.tray_activo = "", [], False
        self.icono_bandeja = None
        self.protocol("WM_DELETE_WINDOW", self.ocultar_a_bandeja)
        self.after(50, self._procesar_ui_queue)

        self.main_scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLOR_FONDO, corner_radius=0)
        self.main_scroll.pack(fill="both", expand=True)

        self.tabview = ctk.CTkTabview(self.main_scroll, width=950, height=750,
                                      fg_color=COLOR_FONDO, segmented_button_selected_color=COLOR_ACENTO)
        self.tabview.pack(padx=20, pady=10)
        self.tabview._segmented_button.configure(font=FUENTE_NORMAL)

        # --- CREACIÓN DE PESTAÑAS (ORDENADAS Y CON SEPARADOR VISUAL) ---
        self.tab_main = self.tabview.add("Sincronizador / ")

        tab_ubicacion_frame = self.tabview.add("Ubicación / ")
        self.tab_ubicacion = TabUbicacion(tab_ubicacion_frame, parent_app=self)
        self.tab_ubicacion.pack(expand=True, fill="both")

        self.tab_armaduras = self.tabview.add("Módulo Estructural / ")

        self.tab_renombrado = self.tabview.add("Procesamiento Masivo / ")

        self.tab_docs = self.tabview.add("Documentación")

        # --- INICIALIZACIÓN DEL CONTENIDO ---
        self.setup_tab_sincronizador()
        self.setup_tab_renombrado()
        self.setup_tab_armaduras()

        self.vista_docs = TabDocs(
            self.tab_docs, parent_app=self, fg_color="transparent")
        self.vista_docs.pack(fill="both", expand=True)

        # --- CONSOLA FLOTANTE GLOBAL ---
        self.btn_consola = ctk.CTkButton(self, text="💻 Consola", font=FUENTE_NORMAL, width=90, fg_color="#333333",
                                         hover_color="#555555", border_width=1, border_color="#444444", corner_radius=5, command=self.mostrar_ventana_log)
        self.btn_consola.place(relx=0.97, rely=0.03, anchor="ne")

        threading.Thread(target=self.cargar_info_github, daemon=True).start()

    def _ui(self, callback, *args, **kwargs):
        if getattr(self, '_cerrando', False):
            return
        self._ui_queue.put((callback, args, kwargs))

    def _procesar_ui_queue(self):
        try:
            while True:
                callback, args, kwargs = self._ui_queue.get_nowait()
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    self.logger.warning("Error UI callback: %s", e)
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
    # LÓGICA DE WINDOWS (SYSTEM TRAY / AUTOSTART)
    # ==========================================================
    def ocultar_a_bandeja(self):
        if getattr(self, '_cerrando', False):
            return
        self.withdraw()
        if self.icono_bandeja:
            self.tray_activo = True
            return
        try:
            ruta_logo = runtime_ruta_recurso('logo.ico')
            icono = Image.open(ruta_logo).convert("RGBA")
        except Exception as e:
            self.log_r(f"Error cargando ícono: {e}")
            icono = Image.new('RGBA', (64, 64), color=(43, 43, 43, 255))

        menu = pystray.Menu(
            item('Abrir', self.mostrar_desde_bandeja),
            item('Salir', self.salir_completamente)
        )

        self.icono_bandeja = pystray.Icon(
            "SINCAL", icono, "SINCAL Suite", menu)
        self.tray_activo = True
        threading.Thread(target=self.icono_bandeja.run, daemon=True).start()

    def mostrar_desde_bandeja(self, icon, item):
        if self.icono_bandeja:
            self.icono_bandeja.stop()
            self.icono_bandeja = None
        self.tray_activo = False
        self._ui(self.deiconify)

    def salir_completamente(self, icon, item):
        self._cerrando = True
        if self.icono_bandeja:
            self.icono_bandeja.stop()
            self.icono_bandeja = None
        self.tray_activo = False
        self.destroy()

    def mostrar_notificacion(self, titulo, mensaje):
        if getattr(self, 'tray_activo', False) and self.icono_bandeja:
            try:
                self.icono_bandeja.notify(mensaje, titulo)
            except:
                pass

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
                f"https://api.github.com/repos/{USUARIO_GITHUB}/{REPO_GITHUB}/commits", params={"per_page": 10}, timeout=5)
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
        lbl_titulo = ctk.CTkLabel(
            self.tab_main, text="ESTÁNDAR SINCAL", font=FUENTE_TITULO, text_color=COLOR_TITULO)
        lbl_titulo.pack(pady=10)
        self.btn_actualizar = ctk.CTkButton(self.tab_main, text="Abrir instalador oficial", font=FUENTE_SUBTITULO, fg_color="transparent", border_width=2,
                                            border_color=COLOR_ACENTO, corner_radius=0, hover_color="#444444", text_color=COLOR_TEXTO, border_spacing=8, command=lambda: webbrowser.open(URL_RELEASES))
        self.btn_actualizar.pack(pady=5)

        botones_sec_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        botones_sec_frame.pack(pady=5)
        ctk.CTkButton(botones_sec_frame, text="Abrir carpeta local", font=FUENTE_NORMAL, fg_color="transparent", border_width=1, border_color=COLOR_ACENTO,
                      corner_radius=0, text_color=COLOR_TEXTO, hover_color="#444444", command=self.abrir_carpeta_local).pack(side="left", padx=10)
        ctk.CTkButton(botones_sec_frame, text="Preparar integración CAD", font=FUENTE_NORMAL, fg_color="transparent", border_width=1, border_color=COLOR_TITULO,
                      corner_radius=0, text_color=COLOR_TITULO, hover_color="#444444", command=self.forzar_path_manual).pack(side="left", padx=10)

        self.btn_sync_resources = ctk.CTkButton(botones_sec_frame, text="Actualizar recursos CAD", font=FUENTE_NORMAL, fg_color="transparent", border_width=1, border_color=COLOR_ACENTO,
                                                corner_radius=0, text_color=COLOR_TEXTO, hover_color="#444444", command=self.verificar_recursos_manual)
        self.btn_sync_resources.pack(side="left", padx=10)

        self.btn_verificar_update = ctk.CTkButton(botones_sec_frame, text="Verificar nueva actualización", font=FUENTE_NORMAL, fg_color="transparent", border_width=1, border_color="#00FF00",
                                                  corner_radius=0, text_color="#00FF00", hover_color="#444444", command=self.verificar_actualizacion_manual)
        self.btn_verificar_update.pack(side="left", padx=10)

        self.consola = ctk.CTkTextbox(self.tab_main, width=850, height=180, font=FUENTE_CONSOLA,
                                      fg_color="#1E1E1E", text_color=COLOR_TEXTO, state="disabled")
        self.consola.pack(pady=10)

        self.frame_updates = ctk.CTkFrame(
            self.tab_main, fg_color="transparent")
        self.frame_updates.pack(fill="x", padx=40, pady=5)
        ctk.CTkLabel(self.frame_updates, text="Historial de cambios",
                     font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(anchor="w")
        self.txt_updates = ctk.CTkTextbox(
            self.frame_updates, width=850, height=160, font=FUENTE_NORMAL, fg_color="#1E1E1E", state="disabled")
        self.txt_updates.pack(pady=5)

        threading.Thread(target=self._hilo_verificar_recursos, args=(False,), daemon=True).start()

    def verificar_recursos_manual(self):
        self.log("\n[*] Buscando actualizaciones menores de recursos CAD en GitHub...")
        self.btn_sync_resources.configure(state="disabled", text="Verificando...")
        threading.Thread(target=self._hilo_verificar_recursos, args=(True,), daemon=True).start()

    def _preparar_archivos_cad(self):
        copiados = materialize_cad_resources()
        archivos_lisp = active_resource_paths(("lisps/", "startup/"))
        self.generar_archivos_lisp(archivos_lisp)
        registros = registrar_ruta_cad_usuario()
        return copiados, registros

    def _hilo_verificar_recursos(self, manual):
        actualizacion_ofrecida = False
        try:
            plan = check_resource_updates()
            if plan.has_changes:
                actualizacion_ofrecida = True
                self.log(
                    f"[!] Actualización menor disponible: {len(plan.changed)} archivo(s) nuevo(s) o modificado(s)"
                    f" y {len(plan.removed)} eliminado(s)."
                )
                self._ui(self._ofrecer_actualizacion_recursos, plan, manual)
                return

            record_resource_state(plan)
            self._preparar_archivos_cad()
            self.log("[OK] Los LISPs, scripts, estilos y el master DWG ya están actualizados.")
            if manual:
                self._ui(
                    messagebox.showinfo,
                    "Recursos CAD",
                    "Los recursos CAD ya coinciden con la rama main de GitHub.",
                )
        except Exception as e:
            self.logger.warning("No se pudieron verificar los recursos CAD: %s", e)
            self.log(f"[!] No se pudieron verificar los recursos CAD; se conservarán las copias locales: {e}")
            if manual:
                self._ui(
                    messagebox.showwarning,
                    "Recursos CAD",
                    "No fue posible consultar GitHub. Se conservarán los últimos recursos válidos.\n\n"
                    f"Detalle: {e}",
                )
        finally:
            if manual and not actualizacion_ofrecida:
                self._ui(self.btn_sync_resources.configure, state="normal", text="Actualizar recursos CAD")

    def _ofrecer_actualizacion_recursos(self, plan, manual):
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
        if messagebox.askyesno("Actualización de recursos SINCAL", mensaje):
            self.btn_sync_resources.configure(state="disabled", text="Actualizando...")
            threading.Thread(target=self._hilo_aplicar_recursos, args=(plan,), daemon=True).start()
        else:
            self.log("[!] Actualización menor pospuesta por el usuario.")
            if manual:
                self.btn_sync_resources.configure(state="normal", text="Actualizar recursos CAD")

    def _hilo_aplicar_recursos(self, plan):
        try:
            resultado = apply_resource_updates(plan)
            self._preparar_archivos_cad()
            recargados = self._recargar_lisps_cad_abierto()
            self.log(
                f"[OK] Actualización menor instalada: {len(resultado.updated)} archivo(s) actualizado(s)"
                f" y {len(resultado.removed)} eliminado(s)."
            )
            estado_cad = (
                f"Los comandos LISP se recargaron en {recargados} dibujo(s) abierto(s)."
                if recargados
                else "Si AutoCAD/ZWCAD estaba abierto, abre un dibujo nuevo o reinícialo para cargar comandos LISP nuevos."
            )
            self._ui(
                messagebox.showinfo,
                "Actualización lista",
                "Los recursos fueron actualizados correctamente.\n\n"
                "Cierra y vuelve a abrir SINCAL para refrescar toda la interfaz. "
                + estado_cad,
            )
        except Exception as e:
            self.logger.exception("Falló la actualización de recursos CAD")
            self.log(f"[X] No se pudo completar la actualización menor: {e}")
            self._ui(
                messagebox.showerror,
                "Actualización incompleta",
                "No se aplicó completamente la actualización. SINCAL volverá a intentarlo al iniciar.\n\n"
                f"Detalle: {e}",
            )
        finally:
            self._ui(self.btn_sync_resources.configure, state="normal", text="Actualizar recursos CAD")

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
                except Exception:
                    continue
                for index in range(documents.Count):
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
                f"https://api.github.com/repos/{USUARIO_GITHUB}/{REPO_GITHUB}/releases/latest",
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
                         "Actualización", "El sistema ya se encuentra en su última versión.")
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

        bottom_frame = ctk.CTkFrame(self.tab_renombrado, fg_color="#1E1E1E",
                                    corner_radius=0, border_width=1, border_color="#444444")
        bottom_frame.pack(fill="x", padx=20, pady=(10, 15))

        ctk.CTkLabel(bottom_frame, text="4. Consola de Automatización (Inyectar a planos cerrados):",
                     font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(anchor="w", padx=15, pady=(10, 5))

        btn_container = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        btn_container.pack(fill="x", padx=15, pady=5)

        def cmd_ps(nombre_script):
            ruta = runtime_ruta_recurso("scripts", f"{nombre_script}.ps1")
            return f"& '{ruta}'"

        for i in range(4):
            btn_container.grid_columnconfigure(
                i, weight=1, uniform="botones_script")

        ctk.CTkButton(btn_container, text="▶ Auditar", font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555",
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("AUDIT"))).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Purgar", font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555", corner_radius=0,
                      command=lambda: self.lanzar_script(cmd_ps("PURGEALL"))).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Encuadrar vista", font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555",
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("ZE"))).grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Eliminar Layout2", font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555",
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("DL2"))).grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(btn_container, text="▶ Bloquear Viewports", font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555",
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("BV"))).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Configurar en A1", font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555",
                      corner_radius=0, command=lambda: self.lanzar_script(cmd_ps("PAGESETUP-A1"))).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="▶ Ploteo A1", font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555", corner_radius=0,
                      command=lambda: self.lanzar_script(cmd_ps("PUBLISH-A1"))).grid(row=1, column=2, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(btn_container, text="🔄 Convertir DXF a DWG", font=FUENTE_NORMAL, fg_color="#005BBF", hover_color="#004A9E",
                      corner_radius=0, command=self.convertir_dxf_a_dwg).grid(row=1, column=3, padx=5, pady=5, sticky="ew")

        self.consola_scripts = ctk.CTkTextbox(bottom_frame, height=120, font=FUENTE_CONSOLA,
                                              fg_color="#000000", text_color="#00FF00", state="disabled", corner_radius=0)
        self.consola_scripts.pack(fill="x", padx=15, pady=(5, 15))

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

        self.consola_scripts.configure(state="normal")
        self.consola_scripts.delete("1.0", "end")
        self.consola_scripts.configure(state="disabled")

        threading.Thread(target=self._hilo_script, args=(
            comando_ps,), daemon=True).start()

    def _hilo_script(self, comando_ps):
        self.log_script(
            f"> Directorio Activo: {self.ruta_renombre}\n> Comando: {comando_ps}\n" + "-"*60 + "\n")

        comando = ["powershell", "-NoProfile",
                   "-ExecutionPolicy", "Bypass", "-Command", comando_ps]

        try:
            proceso = subprocess.Popen(
                comando,
                cwd=self.ruta_renombre,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            for linea in iter(proceso.stdout.readline, ''):
                self.log_script(linea)

            proceso.stdout.close()
            proceso.wait()
            if proceso.returncode == 0:
                self.log_script(
                    f"\n[OK] Script finalizado (Código de salida: {proceso.returncode})\n")
            else:
                self.log_script(
                    f"\n[X] Script finalizado con error (Código de salida: {proceso.returncode})\n")

        except Exception as e:
            self.log_script(
                f"\n[X] Fallo crítico al lanzar PowerShell:\n{e}\n")

    def convertir_dxf_a_dwg(self):
        if not getattr(self, 'ruta_renombre', None):
            return messagebox.showwarning("Sin ruta", "Por favor, carga una carpeta primero en el Paso 1.")

        dxfs = [cb.cget("text") for cb in self.checkboxes_archivos if cb.get(
        ) == 1 and cb.cget("text").lower().endswith('.dxf')]

        if not dxfs:
            return messagebox.showinfo("Nada que convertir", "No hay archivos DXF marcados en la lista.")

        if self.cad_esta_ejecutandose():
            return messagebox.showwarning("CAD en Uso", "Por favor cierra AutoCAD/ZWCAD para que la conversión se haga en segundo plano sin interrupciones.")

        self.consola_scripts.configure(state="normal")
        self.consola_scripts.delete("1.0", "end")
        self.consola_scripts.configure(state="disabled")

        threading.Thread(target=self._hilo_convertir_dxf,
                         args=(dxfs,), daemon=True).start()

    def _hilo_convertir_dxf(self, dxfs):
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
                ruta_dxf = os.path.join(self.ruta_renombre, f)
                ruta_dwg = os.path.join(self.ruta_renombre, f[:-4] + ".dwg")

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
            self._ui(self.refrescar_lista_archivos)

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
            self.buscar_y_configurar_consolas()
            self.log(
                f"[OK] Integración CAD preparada: {len(copiados)} recurso(s) materializado(s) y "
                f"{len(registros)} ruta(s) de perfil actualizada(s)."
            )
            messagebox.showinfo(
                "Integración CAD",
                "La integración quedó preparada. Reinicia AutoCAD/ZWCAD una vez para activar "
                "las rutas de confianza y el cargador automático.",
            )
        except Exception as e:
            self.logger.exception("No se pudo preparar la integración CAD")
            messagebox.showerror("Integración CAD", f"No se pudo completar la preparación.\n\nDetalle: {e}")

    def iniciar_actualizacion_hilo(self):
        webbrowser.open(URL_RELEASES)
        self.log("[!] Los cambios del ejecutable se instalan desde Releases; los recursos CAD se actualizan desde main.")

    def motor_actualizacion(self):
        self.log("[!] La actualización en caliente está limitada a recursos CAD autorizados.")

    def buscar_y_configurar_consolas(self):
        self.cad_exe_path = None
        for p in [r"C:\Program Files\Autodesk", r"C:\Program Files\ZWSOFT"]:
            if os.path.exists(p):
                for root, dirs, files in os.walk(p):
                    for f in files:
                        if f.lower() in ["accoreconsole.exe", "zwcad.exe"]:
                            self.cad_exe_path = os.path.join(root, f)
                            if "zwcad" in f.lower():
                                self.es_zwcad = True

                            ruta_wrapper = ruta_runtime("cad_wrapper.bat")
                            try:
                                with open(ruta_wrapper, 'w', encoding='utf-8') as wf:
                                    wf.write(
                                        f'@echo off\n"{self.cad_exe_path}" %*\n')
                            except Exception as e:
                                self.log(f"[X] Error creando wrapper CAD: {e}")

                            return

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
        if hasattr(self, 'consola'):
            self._ui(self._append_textbox, self.consola, m + "\n")
        self.escribir_en_consola_global(m)

    def log_r(self, m):
        self.logger.info(m)
        if hasattr(self, 'log_rename'):
            self._ui(self._append_textbox, self.log_rename, m + "\n")
        self.escribir_en_consola_global("[PROCESAMIENTO MASIVO] " + m)

    def log_script(self, texto):
        self.logger.info(texto.strip())
        if hasattr(self, 'consola_scripts'):
            self._ui(self._append_textbox, self.consola_scripts, texto)
        self.escribir_en_consola_global(texto.strip('\n'))

    def escribir_en_consola_global(self, m):
        self.historial_logs.append(m)
        if hasattr(self, 'ventana_log') and hasattr(self, 'txt_log_global'):
            self._ui(self._append_if_exists, self.txt_log_global, m + "\n")

    def _append_if_exists(self, widget, texto):
        if widget.winfo_exists():
            self._append_textbox(widget, texto)

    def mostrar_ventana_log(self):
        if hasattr(self, 'ventana_log') and self.ventana_log.winfo_exists():
            self.ventana_log.focus()
            return

        self.ventana_log = ctk.CTkToplevel(self)
        self.ventana_log.title("Consola de Diagnóstico - SINCAL")
        self.ventana_log.geometry("750x450")
        self.ventana_log.transient(self)

        self.txt_log_global = ctk.CTkTextbox(
            self.ventana_log, font=FUENTE_CONSOLA, fg_color="#000000", text_color="#00FF00", corner_radius=0)
        self.txt_log_global.pack(fill="both", expand=True, padx=10, pady=10)

        self.txt_log_global.configure(state="normal")
        self.txt_log_global.insert(
            "end", "\n".join(self.historial_logs) + "\n")
        self.txt_log_global.see("end")
        self.txt_log_global.configure(state="disabled")


def arrancar():
    app = ActualizadorCAD()
    app.mainloop()
