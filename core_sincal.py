import os
import sys
import json
import requests
import winreg
import threading
import ctypes
import shutil
import subprocess
import time
import customtkinter as ctk
from customtkinter import filedialog
from tkinter import messagebox
import win32com.client
import pythoncom
import pystray
from pystray import MenuItem as item
from PIL import Image
from modulos.tab_armaduras import TabArmaduras
from modulos.tab_ubicacion import TabUbicacion
from modulos.tab_docs import TabDocs
from datetime import datetime, timedelta


def ruta_recurso(relative_path):
    """Obtiene la ruta absoluta al recurso, funciona para dev y para PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 1. FORZAR MODO ADMINISTRADOR ---


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# --- CONFIGURACIÓN GLOBALES ---
USUARIO_GITHUB = "drossull"
REPO_GITHUB = "sincal-exe"
RAMA = "main"
URL_BASE_RAW = f"https://raw.githubusercontent.com/{USUARIO_GITHUB}/{REPO_GITHUB}/{RAMA}/"
RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estandar SINCAL")
URL_WEBHOOK_SHEETS = "https://script.google.com/macros/s/AKfycbywJwskXQrAhNYHV559ngE5WAPa-bhvrfgcYg0ej_WDfxQMP5vmT31b66mEPqeFCchaPQ/exec"

COLOR_FONDO, COLOR_TITULO, COLOR_TEXTO, COLOR_ACENTO = "#2B2B2B", "#FFBF00", "#CCCCCC", "#007FFF"
FUENTE_TITULO, FUENTE_SUBTITULO, FUENTE_MENU, FUENTE_NORMAL, FUENTE_CONSOLA = [
    ("Consolas", 24, "bold"), ("Consolas", 18,
                               "bold"), ("Consolas", 13), ("Consolas", 12), ("Consolas", 11)
]

ctk.set_appearance_mode("dark")


def obtener_ruta_recurso(ruta_relativa):
    try:
        return os.path.join(sys._MEIPASS, ruta_relativa)
    except:
        return os.path.abspath(ruta_relativa)


class ActualizadorCAD(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SINCAL - Suite de Herramientas Professional")
        self.geometry("1000x800")
        self.configure(fg_color=COLOR_FONDO)
        try:
            self.iconbitmap(obtener_ruta_recurso("logo.ico"))
        except:
            pass

        self.version_local_actual = "v1.5.6"
        self.tutoriales, self.cad_exe_path, self.es_zwcad, self.cancelar_comando_vivo = {
        }, None, False, False
        self.ruta_renombre, self.checkboxes_archivos, self.tray_activo = "", [], False

        self.protocol("WM_DELETE_WINDOW", self.ocultar_a_bandeja)
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
        self.historial_logs = []
        self.btn_consola = ctk.CTkButton(self, text="💻 Consola", font=FUENTE_NORMAL, width=90, fg_color="#333333",
                                         hover_color="#555555", border_width=1, border_color="#444444", corner_radius=5, command=self.mostrar_ventana_log)
        self.btn_consola.place(relx=0.97, rely=0.03, anchor="ne")

        self.protocol("WM_DELETE_WINDOW", self.ocultar_a_bandeja)

        if getattr(sys, 'frozen', False):
            self.configurar_inicio_con_windows()
        threading.Thread(target=self.cargar_info_github, daemon=True).start()

    # ==========================================================
    # LÓGICA DE WINDOWS (SYSTEM TRAY / AUTOSTART)
    # ==========================================================
    def ocultar_a_bandeja(self):
        self.withdraw()
        try:
            ruta_logo = ruta_recurso('logo.ico')
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
        threading.Thread(target=self.icono_bandeja.run, daemon=True).start()

    def mostrar_desde_bandeja(self, icon, item):
        self.icono_bandeja.stop()
        self.after(0, self.deiconify)

    def salir_completamente(self, icon, item):
        self.icono_bandeja.stop()
        self.after(0, self.destroy)

    def mostrar_notificacion(self, titulo, mensaje):
        if getattr(self, 'tray_activo', False) and hasattr(self, 'tray'):
            try:
                self.tray.notify(mensaje, titulo)
            except:
                pass

    def configurar_inicio_con_windows(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
            winreg.SetValueEx(key, "SINCAL_Suite", 0,
                              winreg.REG_SZ, f'"{sys.executable}" --background')
            winreg.CloseKey(key)
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
                self.txt_updates.configure(state="normal")
                self.txt_updates.delete("1.0", "end")

                meses = {"01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
                         "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"}

                for c in r.json():
                    raw_date = c['commit']['author']['date']
                    dt_utc = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%SZ")
                    dt_local = dt_utc - timedelta(hours=4)

                    mes_str = meses[dt_local.strftime("%m")]
                    fecha_formateada = f"{dt_local.strftime('%d')} {mes_str} {dt_local.strftime('%y %H:%M')}"

                    sha_completo = c['sha']
                    version_mostrar = sha_completo[:7]
                    try:
                        url_hist = f"https://raw.githubusercontent.com/{USUARIO_GITHUB}/{REPO_GITHUB}/{sha_completo}/version.json"
                        r_json = requests.get(url_hist, timeout=3)
                        if r_json.status_code == 200:
                            version_mostrar = r_json.json().get("version", version_mostrar)
                    except:
                        pass

                    mensaje = c['commit']['message'].strip()
                    mensaje = mensaje.replace(
                        "\r\n", " + ").replace("\n\n", " + ").replace("\n", " + ")

                    linea = f"• ({version_mostrar}) / {fecha_formateada} / {mensaje}\n"
                    self.txt_updates.insert("end", linea)

                self.txt_updates.configure(state="disabled")
        except Exception as e:
            pass

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

        msg = f"Versión detectada: {nueva_version}\n\nNovedades:\n{desc_commit}\n\n¿Deseas instalar esta actualización ahora?"

        if messagebox.askyesno("¡Actualización SINCAL Disponible!", msg):
            if self.cad_esta_ejecutandose():
                messagebox.showwarning(
                    "Software CAD en uso",
                    "Para que los cambios se apliquen correctamente, por favor cierra ZWCAD o AutoCAD y luego presiona 'Instalar / Actualizar Todo' en esta ventana."
                )
            else:
                self.iniciar_actualizacion_hilo()
        else:
            self.log(
                f"[!] Actualización a {nueva_version} pospuesta por el usuario.")

    def setup_tab_sincronizador(self):
        lbl_titulo = ctk.CTkLabel(
            self.tab_main, text="ESTÁNDAR SINCAL", font=FUENTE_TITULO, text_color=COLOR_TITULO)
        lbl_titulo.pack(pady=10)
        self.btn_actualizar = ctk.CTkButton(self.tab_main, text="Instalar / Actualizar Todo", font=FUENTE_SUBTITULO, fg_color="transparent", border_width=2,
                                            border_color=COLOR_ACENTO, corner_radius=0, hover_color="#444444", text_color=COLOR_TEXTO, border_spacing=8, command=self.iniciar_actualizacion_hilo)
        self.btn_actualizar.pack(pady=5)

        botones_sec_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        botones_sec_frame.pack(pady=5)
        ctk.CTkButton(botones_sec_frame, text="Abrir carpeta local", font=FUENTE_NORMAL, fg_color="transparent", border_width=1, border_color=COLOR_ACENTO,
                      corner_radius=0, text_color=COLOR_TEXTO, hover_color="#444444", command=self.abrir_carpeta_local).pack(side="left", padx=10)
        ctk.CTkButton(botones_sec_frame, text="Reparar / Forzar PATH", font=FUENTE_NORMAL, fg_color="transparent", border_width=1, border_color=COLOR_TITULO,
                      corner_radius=0, text_color=COLOR_TITULO, hover_color="#444444", command=self.forzar_path_manual).pack(side="left", padx=10)

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

    def verificar_actualizacion_manual(self):
        self.log("\n[*] Verificando nueva actualización en GitHub...")
        self.btn_verificar_update.configure(
            state="disabled", text="Verificando...")
        threading.Thread(
            target=self._hilo_verificar_actualizacion, daemon=True).start()

    def _hilo_verificar_actualizacion(self):
        try:
            import time
            timestamp = str(time.time())
            url_fresca = f"{URL_BASE_RAW}version.json?t={timestamp}"
            r = requests.get(url_fresca, timeout=5)
            nueva_version = r.json().get("version")

            if nueva_version != self.version_local_actual:
                desc_commit = "Mejoras generales y corrección de errores."
                try:
                    url_api = f"https://api.github.com/repos/{USUARIO_GITHUB}/{REPO_GITHUB}/commits"
                    r_commit = requests.get(
                        url_api, params={"per_page": 1, "t": timestamp}, timeout=5)
                    if r_commit.status_code == 200:
                        desc_commit = r_commit.json()[0]['commit']['message']
                except:
                    pass

                self.log(
                    f"[!] Nueva versión disponible: {nueva_version}. Novedades: {desc_commit}")
                self.after(0, lambda v=nueva_version,
                           d=desc_commit: self.mostrar_popup_actualizacion(v, d))
            else:
                self.log(
                    "[OK] El sistema ya se encuentra en su última versión.")
                self.after(0, lambda: messagebox.showinfo(
                    "Actualización", "El sistema ya se encuentra en su última versión."))
        except Exception as e:
            self.log(f"[X] Fallo al verificar versión en GitHub: {e}")
        finally:
            self.btn_verificar_update.configure(
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
            ruta = os.path.join(RUTA_LOCAL_APP, "scripts",
                                f"{nombre_script}.ps1")
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
            self.log_script(
                f"\n[OK] Script finalizado (Código de salida: {proceso.returncode})\n")

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
                    self.log_script("OK\n")
                except Exception as e:
                    self.log_script(f"Error ({str(e)})\n")

            try:
                app.Quit()
            except:
                pass

            self.log_script(
                "\n[!] Conversión finalizada. Actualizando lista...\n")
            self.after(1000, self.refrescar_lista_archivos)

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
                return self.log("\n[X] Error: No se detecta CAD abierto. (Recuerda abrirlo como Administrador).")

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
            self.btn_enviar_cmd.configure(state="normal", text="Ejecutar")
            self.btn_cancelar_cmd.configure(state="disabled", text="Cancelar")
            pythoncom.CoUninitialize()

    def abrir_carpeta_local(self): os.startfile(
        RUTA_LOCAL_APP) if os.path.exists(RUTA_LOCAL_APP) else None

    def forzar_path_manual(self):
        self.actualizar_rutas_registro()
        self.actualizar_variable_entorno()
        self.log("[!] PATH y Registro CAD reparados.")

    def reiniciar_aplicacion(self):
        """Mata el hilo de la bandeja y usa un script puente con entorno sanitizado para reiniciar SINCAL limpio."""
        try:
            if hasattr(self, 'icono_bandeja'):
                self.icono_bandeja.stop()
        except:
            pass

        exe_path = sys.executable
        bat_path = os.path.join(os.environ.get(
            'TEMP', 'C:\\Temp'), "restart_sincal.bat")
        meipass = getattr(sys, '_MEIPASS', '')

        # 1. Limpieza a nivel MS-DOS (Reemplazo de strings para arrancar la ruta vieja del PATH)
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write("timeout /t 2 /nobreak > NUL\n")
            f.write("set _MEIPASS2=\n")
            f.write("set _MEIPASS=\n")
            if meipass:
                f.write(f'set PATH=%PATH:{meipass};=%\n')
                f.write(f'set PATH=%PATH:{meipass}=%\n')
            f.write(f'start "" "{exe_path}"\n')
            f.write('del "%~f0"\n')

        # 2. Limpieza a nivel Python (El lavado de cerebro definitivo)
        env_limpio = os.environ.copy()
        env_limpio.pop('_MEIPASS2', None)
        env_limpio.pop('_MEIPASS', None)
        if meipass and 'PATH' in env_limpio:
            env_limpio['PATH'] = os.pathsep.join(
                [p for p in env_limpio['PATH'].split(
                    os.pathsep) if p.lower() != meipass.lower()]
            )

        # 3. Lanzamos el .bat totalmente desvinculado (0x08000000 = CREATE_NO_WINDOW)
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=0x08000000,
            env=env_limpio
        )

        # Permitimos que la versión actual se cierre y borre su carpeta temporal
        sys.exit(0)

    def iniciar_actualizacion_hilo(self):
        self.btn_actualizar.configure(
            state="disabled", text="Sincronizando...")
        self.consola.configure(state="normal")
        self.consola.delete("1.0", "end")
        self.consola.configure(state="disabled")
        threading.Thread(target=self.motor_actualizacion, daemon=True).start()

    def motor_actualizacion(self):
        try:
            nombre_exe_actual = os.path.basename(sys.executable).lower()

            if os.path.exists(RUTA_LOCAL_APP):
                for elemento in os.listdir(RUTA_LOCAL_APP):
                    ruta_elemento = os.path.join(RUTA_LOCAL_APP, elemento)
                    if elemento.lower() == nombre_exe_actual or elemento.lower().startswith("unins"):
                        continue
                    try:
                        if os.path.isdir(ruta_elemento):
                            shutil.rmtree(ruta_elemento)
                        else:
                            os.remove(ruta_elemento)
                    except Exception:
                        pass

            os.makedirs(RUTA_LOCAL_APP, exist_ok=True)

            r = requests.get(URL_BASE_RAW + "version.json").json()
            archivos = r.get("archivos", []) + ["README.md", "TUTORIAL.md"]
            total_archivos = len(archivos)
            spinner = ['|', '/', '-', '\\']

            self.consola.configure(state="normal")
            self.consola.insert("end", "[|] Iniciando descarga...\n")
            self.consola.configure(state="disabled")

            for idx, a in enumerate(archivos):
                r_save = os.path.normpath(os.path.join(RUTA_LOCAL_APP, a))
                os.makedirs(os.path.dirname(r_save), exist_ok=True)
                res = requests.get(URL_BASE_RAW + a)
                if res.status_code == 200:
                    if a.lower().endswith('.lsp'):
                        with open(r_save, 'w', encoding='utf-8', errors='ignore') as f:
                            f.write(res.text)
                    else:
                        with open(r_save, 'wb') as f:
                            f.write(res.content)

                porcentaje = int(((idx + 1) / total_archivos) * 100)
                simbolo = spinner[idx % 4]

                self.consola.configure(state="normal")
                self.consola.delete("end-2l", "end-1c")
                self.consola.insert(
                    "end", f"[{simbolo}] Actualizando SINCAL... {porcentaje}% ({idx+1}/{total_archivos})\n")
                self.consola.see("end")
                self.consola.configure(state="disabled")

            self.generar_archivos_lisp(archivos)
            self.actualizar_rutas_registro()
            self.actualizar_variable_entorno()
            self.registrar_menu_contextual()
            self.buscar_y_configurar_consolas()

            self.version_local_actual = r.get("version", "v1.0.0")
            self.log(f"\n[!] SINCAL Sincronizado: {self.version_local_actual}")
            self.mostrar_notificacion(
                "SINCAL Actualizado", f"Instalada versión {self.version_local_actual}")

            self.log(
                "\n[!] Aplicando cambios... Reiniciando SINCAL en 3 segundos.")
            self.after(3000, self.reiniciar_aplicacion)

        except Exception as e:
            self.log(f"[!] Error crítico en actualización: {e}")
            self.btn_actualizar.configure(
                state="normal", text="Instalar / Actualizar Todo")

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

                            ruta_wrapper = os.path.join(
                                RUTA_LOCAL_APP, "cad_wrapper.bat")
                            try:
                                with open(ruta_wrapper, 'w', encoding='utf-8') as wf:
                                    wf.write(
                                        f'@echo off\n"{self.cad_exe_path}" %*\n')
                            except Exception as e:
                                self.log(f"[X] Error creando wrapper CAD: {e}")

                            return

    def actualizar_rutas_registro(self):
        appdata = os.getenv('APPDATA')
        for carpeta_cad in ["Autodesk", "ZWSOFT"]:
            base = os.path.join(appdata, carpeta_cad)
            if os.path.exists(base):
                for root, dirs, files in os.walk(base):
                    for file in files:
                        if file.lower() in ["acaddoc.lsp", "zwcaddoc.lsp"]:
                            ruta_fantasma = os.path.join(root, file)
                            if RUTA_LOCAL_APP.lower() not in ruta_fantasma.lower():
                                try:
                                    os.rename(ruta_fantasma,
                                              ruta_fantasma + ".bak")
                                    self.log(
                                        f"[*] Fantasma neutralizado en: {os.path.basename(root)}")
                                except:
                                    pass

        def inyectar_ruta_recursivo(ruta_reg):
            try:
                llave = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, ruta_reg, 0, winreg.KEY_ALL_ACCESS)

                for nombre_valor in ["ACAD", "ZWCAD", "ZWCADSEARCHPATH", "SRCHPATH", "TRUSTEDPATHS"]:
                    try:
                        valor_actual, tipo = winreg.QueryValueEx(
                            llave, nombre_valor)
                        if RUTA_LOCAL_APP.lower() not in valor_actual.lower():
                            nuevo_valor = f"{RUTA_LOCAL_APP};{valor_actual}"
                            winreg.SetValueEx(
                                llave, nombre_valor, 0, tipo, nuevo_valor)
                            self.log(
                                f"[*] SINCAL inyectado en registro: {nombre_valor}")
                    except OSError:
                        pass

                i = 0
                while True:
                    try:
                        sub_llave = winreg.EnumKey(llave, i)
                        inyectar_ruta_recursivo(f"{ruta_reg}\\{sub_llave}")
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(llave)
            except Exception:
                pass

        inyectar_ruta_recursivo(r"Software\Autodesk\AutoCAD")
        inyectar_ruta_recursivo(r"Software\ZWSOFT\ZWCAD")

    def actualizar_variable_entorno(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 "Environment", 0, winreg.KEY_ALL_ACCESS)
            p, _ = winreg.QueryValueEx(key, "Path")
            if RUTA_LOCAL_APP.lower() not in p.lower():
                winreg.SetValueEx(
                    key, "Path", 0, winreg.REG_EXPAND_SZ, f"{p};{RUTA_LOCAL_APP}")
            winreg.CloseKey(key)
        except:
            pass

    def registrar_menu_contextual(self):
        try:
            import winreg
            exe_path = sys.executable

            ruta_llave = r"Directory\shell\SINCAL_Plotear"
            llave = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, ruta_llave)
            winreg.SetValue(llave, "", winreg.REG_SZ, "Plotear con SINCAL")
            winreg.SetValueEx(llave, "Icon", 0, winreg.REG_SZ, f'"{exe_path}"')

            llave_comando = winreg.CreateKey(llave, "command")
            comando_ejecucion = f'"{exe_path}" --plotear "%1"'
            winreg.SetValue(llave_comando, "",
                            winreg.REG_SZ, comando_ejecucion)

            winreg.CloseKey(llave_comando)
            winreg.CloseKey(llave)

            ruta_llave_fondo = r"Directory\Background\shell\SINCAL_Plotear"
            llave_fondo = winreg.CreateKey(
                winreg.HKEY_CLASSES_ROOT, ruta_llave_fondo)
            winreg.SetValue(llave_fondo, "", winreg.REG_SZ,
                            "Plotear con SINCAL")
            winreg.SetValueEx(llave_fondo, "Icon", 0,
                              winreg.REG_SZ, f'"{exe_path}"')
            llave_comando_fondo = winreg.CreateKey(llave_fondo, "command")
            comando_fondo = f'"{exe_path}" --plotear "%V"'
            winreg.SetValue(llave_comando_fondo, "",
                            winreg.REG_SZ, comando_fondo)
            winreg.CloseKey(llave_comando_fondo)
            winreg.CloseKey(llave_fondo)

        except Exception as e:
            pass

    def generar_archivos_lisp(self, archivos):
        contenido_arranque = ""

        for a in archivos:
            if a.lower().endswith('.lsp') and os.path.basename(a).lower() not in ["acaddoc.lsp", "zwcaddoc.lsp"]:
                ruta_lisp = os.path.normpath(os.path.join(
                    RUTA_LOCAL_APP, a)).replace("\\", "/")
                nombre = os.path.basename(a)
                contenido_arranque += f'(princ (load "{ruta_lisp}" "\\n[X] SINCAL: Fallo al cargar {nombre}"))\n'

        if "startup/SINCAL_STARTUP.lsp" in archivos or "SINCAL_STARTUP.lsp" in archivos:
            contenido_arranque += '(princ "\\n[SINCAL] Políticas de empresa y variables aplicadas.")\n'

        contenido_arranque += '(princ "\\n[OK] SINCAL: Todos los LISPs procesados correctamente.")\n(princ)\n'

        r_acad = os.path.join(RUTA_LOCAL_APP, "acaddoc.lsp")
        r_zwcad = os.path.join(RUTA_LOCAL_APP, "zwcaddoc.lsp")

        with open(r_acad, 'w', encoding='utf-8') as f:
            f.write(contenido_arranque)

        with open(r_zwcad, 'w', encoding='utf-8') as f:
            f.write(contenido_arranque)

    # ==========================================================
    # SISTEMA DE LOGS Y CONSOLA FLOTANTE
    # ==========================================================
    def log(self, m):
        self.consola.configure(state="normal")
        self.consola.insert("end", m + "\n")
        self.consola.see("end")
        self.consola.configure(state="disabled")
        self.escribir_en_consola_global(m)

    def log_r(self, m):
        self.log_rename.configure(state="normal")
        self.log_rename.insert("end", m + "\n")
        self.log_rename.see("end")
        self.log_rename.configure(state="disabled")
        self.escribir_en_consola_global("[PROCESAMIENTO MASIVO] " + m)

    def log_script(self, texto):
        self.consola_scripts.configure(state="normal")
        self.consola_scripts.insert("end", texto)
        self.consola_scripts.see("end")
        self.consola_scripts.configure(state="disabled")
        self.escribir_en_consola_global(texto.strip('\n'))

    def escribir_en_consola_global(self, m):
        self.historial_logs.append(m)
        if hasattr(self, 'ventana_log') and self.ventana_log.winfo_exists():
            self.txt_log_global.configure(state="normal")
            self.txt_log_global.insert("end", m + "\n")
            self.txt_log_global.see("end")
            self.txt_log_global.configure(state="disabled")

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
    import sys
    app = ActualizadorCAD()
    if "--background" in sys.argv:
        app.ocultar_a_bandeja()
    app.mainloop()
