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
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 1. FORZAR MODO ADMINISTRADOR ---
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
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
    ("Consolas", 24, "bold"), ("Consolas", 18, "bold"), ("Consolas", 13), ("Consolas", 12), ("Consolas", 11)
]

ctk.set_appearance_mode("dark") 

def obtener_ruta_recurso(ruta_relativa):
    try: return os.path.join(sys._MEIPASS, ruta_relativa)
    except: return os.path.abspath(ruta_relativa)

class ActualizadorCAD(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SINCAL - Suite de Herramientas Professional")
        self.geometry("1000x800")
        self.configure(fg_color=COLOR_FONDO)
        try: self.iconbitmap(obtener_ruta_recurso("logo.ico"))
        except: pass
        
        self.version_local_actual = "v1.5.6"
        self.tutoriales, self.cad_exe_path, self.es_zwcad, self.cancelar_comando_vivo = {}, None, False, False
        self.ruta_renombre, self.checkboxes_archivos, self.tray_activo = "", [], False

        self.protocol("WM_DELETE_WINDOW", self.ocultar_a_bandeja)
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_FONDO, corner_radius=0)
        self.main_scroll.pack(fill="both", expand=True)

        self.tabview = ctk.CTkTabview(self.main_scroll, width=950, height=750, fg_color=COLOR_FONDO, segmented_button_selected_color=COLOR_ACENTO)
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
        
        self.vista_docs = TabDocs(self.tab_docs, parent_app=self, fg_color="transparent")
        self.vista_docs.pack(fill="both", expand=True)

        # Redirige el botón "X" de Windows a nuestra función de la bandeja
        self.protocol("WM_DELETE_WINDOW", self.ocultar_a_bandeja)

        if getattr(sys, 'frozen', False): self.configurar_inicio_con_windows()
        threading.Thread(target=self.cargar_info_github, daemon=True).start()
        threading.Thread(target=self.loop_verificador_actualizaciones_silencioso, daemon=True).start()

    # ==========================================================
    # LÓGICA DE WINDOWS (SYSTEM TRAY / AUTOSTART)
    # ==========================================================
    def ocultar_a_bandeja(self):
        self.withdraw()  # Oculta la ventana principal
        try:
            ruta_logo = ruta_recurso('logo.ico')
            # Forzamos la conversión a RGBA. Si pystray no ve el canal Alfa, falla en silencio en Windows
            icono = Image.open(ruta_logo).convert("RGBA")
        except Exception as e: 
            self.log_r(f"Error cargando ícono: {e}")
            # El cuadrado de respaldo también debe ser RGBA estricto
            icono = Image.new('RGBA', (64, 64), color=(43, 43, 43, 255))
            
        menu = pystray.Menu(
            item('Abrir', self.mostrar_desde_bandeja), 
            item('Salir', self.salir_completamente)
        )
        
        self.icono_bandeja = pystray.Icon("SINCAL", icono, "SINCAL Suite", menu)
        threading.Thread(target=self.icono_bandeja.run, daemon=True).start()

    def mostrar_desde_bandeja(self, icon, item):
        # Detenemos el ícono de la bandeja
        self.icono_bandeja.stop()
        # Le decimos a la interfaz que se vuelva a dibujar (de forma segura)
        self.after(0, self.deiconify)

    def salir_completamente(self, icon, item):
        # Detenemos el ícono y destruimos el programa
        self.icono_bandeja.stop()
        self.after(0, self.destroy)

    def mostrar_notificacion(self, titulo, mensaje):
        if getattr(self, 'tray_activo', False) and hasattr(self, 'tray'):
            try: self.tray.notify(mensaje, titulo)
            except: pass

    def configurar_inicio_con_windows(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
            winreg.SetValueEx(key, "SINCAL_Suite", 0, winreg.REG_SZ, f'"{sys.executable}" --background')
            winreg.CloseKey(key)
        except: pass

    def setup_tab_armaduras(self):
     # Conectamos el módulo externo a la pestaña de armaduras
     self.vista_armaduras = TabArmaduras(master=self.tab_armaduras, parent_app=self, fg_color="transparent")
     self.vista_armaduras.pack(fill="both", expand=True)

    # ==========================================================
    # PARTE COMÚN Y SOPORTE DE ACTUALIZACIONES (MANTENIDO/OPTIMIZADO)
    # ==========================================================
    def cargar_info_github(self):
        try:
            r = requests.get(f"https://api.github.com/repos/{USUARIO_GITHUB}/{REPO_GITHUB}/commits", params={"per_page": 10}, timeout=5)
            if r.status_code == 200:
                self.txt_updates.configure(state="normal")
                self.txt_updates.delete("1.0", "end")
                
                # Diccionario para meses en español
                meses = {"01":"Ene", "02":"Feb", "03":"Mar", "04":"Abr", "05":"May", "06":"Jun", 
                         "07":"Jul", "08":"Ago", "09":"Sep", "10":"Oct", "11":"Nov", "12":"Dic"}
                
                for c in r.json():
                    # 1. Fecha y Hora (Transformando UTC a hora local de Chile: UTC-4)
                    raw_date = c['commit']['author']['date'] # Ej: "2026-07-15T13:30:00Z"
                    dt_utc = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%SZ")
                    dt_local = dt_utc - timedelta(hours=4) # Ajuste horario
                    
                    mes_str = meses[dt_local.strftime("%m")]
                    fecha_formateada = f"{dt_local.strftime('%d')} {mes_str} {dt_local.strftime('%y %H:%M')}"
                    
                    # 2. Versión: Usamos los primeros 7 caracteres del SHA del commit
                    version_sha = c['sha'][:7]
                    
                    # 3. Formatear el Mensaje (Summary + Description)
                    mensaje = c['commit']['message'].strip()
                    # Aplanamos los saltos de línea reemplazándolos con " + "
                    mensaje = mensaje.replace("\r\n", " + ").replace("\n\n", " + ").replace("\n", " + ")
                    
                    # Ensamblar la línea y mostrarla
                    linea = f"• ({version_sha}) / {fecha_formateada} / {mensaje}\n"
                    self.txt_updates.insert("end", linea)
                    
                self.txt_updates.configure(state="disabled")
        except Exception as e: 
            pass
    
    def cad_esta_ejecutandose(self):
        try:
            # Ponytail: Verificación simple de strings en la tasklist de Windows.
            # Ceiling: Falsos positivos si otro software contiene "acad" en su proceso. Upgrade: Validar PID y firmas ejecutables reales de Autodesk/ZWSoft.
            salida = subprocess.check_output("tasklist", creationflags=0x08000000).decode('utf-8', errors='ignore').lower()
            return any(x in salida for x in ["acad.exe", "zwcad.exe", "accoreconsole.exe"])
        except: return False

    def loop_verificador_actualizaciones_silencioso(self):
        # Revisión súper rápida cada 30 segundos
        while True:
            time.sleep(30)
            try:
                r = requests.get(URL_BASE_RAW + "version.json", timeout=5)
                nueva_version = r.json().get("version")
                if nueva_version != self.version_local_actual:
                    
                    # 1. Rescatamos la descripción del último commit en GitHub
                    desc_commit = "Mejoras generales y corrección de errores."
                    try:
                        r_commit = requests.get(f"https://api.github.com/repos/{USUARIO_GITHUB}/{REPO_GITHUB}/commits", params={"per_page": 1}, timeout=5)
                        if r_commit.status_code == 200:
                            desc_commit = r_commit.json()[0]['commit']['message']
                    except: pass
                    
                    # 2. Llamamos al pop-up de forma segura en el hilo principal de la interfaz
                    self.after(0, lambda: self.mostrar_popup_actualizacion(nueva_version, desc_commit))
                    
                    # 3. Detenemos este loop para que no le salgan 100 pop-ups seguidos
                    break 
            except: pass

    def mostrar_popup_actualizacion(self, nueva_version, desc_commit):
        # Forzar la ventana principal al frente si estaba minimizada o en la bandeja
        self.deiconify()
        self.focus_force()
        
        # Armar el mensaje
        msg = f"Versión detectada: {nueva_version}\n\nNovedades:\n{desc_commit}\n\n¿Deseas instalar esta actualización ahora?"
        
        # Lanzar el Pop-Up
        if messagebox.askyesno("¡Actualización SINCAL Disponible!", msg):
            # Verificamos si tiene el CAD abierto para proteger la inyección
            if self.cad_esta_ejecutandose():
                messagebox.showwarning(
                    "Software CAD en uso", 
                    "Para que los cambios se apliquen correctamente, por favor cierra ZWCAD o AutoCAD y luego presiona 'Instalar / Actualizar Todo' en esta ventana."
                )
            else:
                self.iniciar_actualizacion_hilo()
        else:
            self.log(f"[!] Actualización a {nueva_version} pospuesta por el usuario.")

    def setup_tab_sincronizador(self):
        lbl_titulo = ctk.CTkLabel(self.tab_main, text="ESTÁNDAR SINCAL", font=FUENTE_TITULO, text_color=COLOR_TITULO); lbl_titulo.pack(pady=10)
        self.btn_actualizar = ctk.CTkButton(self.tab_main, text="Instalar / Actualizar Todo", font=FUENTE_SUBTITULO, fg_color="transparent", border_width=2, border_color=COLOR_ACENTO, corner_radius=0, hover_color="#444444", text_color=COLOR_TEXTO, border_spacing=8, command=self.iniciar_actualizacion_hilo); self.btn_actualizar.pack(pady=5)
        
        botones_sec_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent"); botones_sec_frame.pack(pady=5)
        ctk.CTkButton(botones_sec_frame, text="Abrir carpeta local", font=FUENTE_NORMAL, fg_color="transparent", border_width=1, border_color=COLOR_ACENTO, corner_radius=0, text_color=COLOR_TEXTO, hover_color="#444444", command=self.abrir_carpeta_local).pack(side="left", padx=10)
        ctk.CTkButton(botones_sec_frame, text="Reparar / Forzar PATH", font=FUENTE_NORMAL, fg_color="transparent", border_width=1, border_color=COLOR_TITULO, corner_radius=0, text_color=COLOR_TITULO, hover_color="#444444", command=self.forzar_path_manual).pack(side="left", padx=10)
        
        self.consola = ctk.CTkTextbox(self.tab_main, width=850, height=180, font=FUENTE_CONSOLA, fg_color="#1E1E1E", text_color=COLOR_TEXTO, state="disabled"); self.consola.pack(pady=10)
        
        self.frame_live = ctk.CTkFrame(self.tab_main, fg_color="#1E1E1E", border_width=1, border_color="#444444", corner_radius=0)
        self.frame_live.pack(fill="x", padx=40, pady=(10, 10))
        top_live_frame = ctk.CTkFrame(self.frame_live, fg_color="transparent")
        top_live_frame.pack(fill="x", padx=15, pady=(15, 5))
        ctk.CTkLabel(top_live_frame, text="Comandos en vivo:", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(side="left")
        
        bot_live_frame = ctk.CTkFrame(self.frame_live, fg_color="transparent")
        bot_live_frame.pack(fill="x", padx=15, pady=(0, 15))
        self.entrada_comando = ctk.CTkEntry(bot_live_frame, font=FUENTE_NORMAL, width=300, placeholder_text="Ej: ZE, _QSAVE", corner_radius=0)
        self.entrada_comando.pack(side="left", padx=(0, 10))
        
        self.btn_enviar_cmd = ctk.CTkButton(bot_live_frame, text="Ejecutar", font=FUENTE_NORMAL, fg_color="transparent", border_width=1, border_color=COLOR_ACENTO, corner_radius=0, hover_color="#444444", text_color=COLOR_TEXTO, width=80, command=self.enviar_comando_en_vivo)
        self.btn_enviar_cmd.pack(side="left", padx=(0, 10))
        self.btn_cancelar_cmd = ctk.CTkButton(bot_live_frame, text="Cancelar", font=FUENTE_NORMAL, fg_color="#D9534F", hover_color="#C9302C", width=80, corner_radius=0, state="disabled", command=self.detener_comando_en_vivo)
        self.btn_cancelar_cmd.pack(side="left")

        self.frame_updates = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        self.frame_updates.pack(fill="x", padx=40, pady=5)
        ctk.CTkLabel(self.frame_updates, text="Historial de cambios", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(anchor="w")
        self.txt_updates = ctk.CTkTextbox(self.frame_updates, width=850, height=160, font=FUENTE_NORMAL, fg_color="#1E1E1E", state="disabled")
        self.txt_updates.pack(pady=5)

    def setup_tab_renombrado(self):
        lbl_titulo = ctk.CTkLabel(self.tab_renombrado, text="RENOMBRADO PARAMÉTRICO DE PLANOS", font=FUENTE_TITULO, text_color=COLOR_TITULO)
        lbl_titulo.pack(pady=10)
        top_frame = ctk.CTkFrame(self.tab_renombrado, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=5)
        self.btn_browse_adv = ctk.CTkButton(top_frame, text="📁 Cargar Carpeta DWG", font=FUENTE_NORMAL, width=150, corner_radius=0, fg_color="#444444", hover_color="#555555", command=self.cargar_archivos_renombrado)
        self.btn_browse_adv.pack(side="left")
        self.lbl_ruta_adv = ctk.CTkLabel(top_frame, text="Ruta: Ninguna", font=FUENTE_NORMAL, text_color="#888888")
        self.lbl_ruta_adv.pack(side="left", padx=15)
        split_frame = ctk.CTkFrame(self.tab_renombrado, fg_color="transparent")
        split_frame.pack(fill="both", expand=True, padx=20, pady=10)
        left_frame = ctk.CTkFrame(split_frame, fg_color="#1E1E1E", corner_radius=0, border_width=1, border_color="#444444")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        lbl_lista = ctk.CTkLabel(left_frame, text="1. Selecciona los archivos a modificar:", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(pady=(15, 5), padx=15, anchor="w")
        btn_tools = ctk.CTkFrame(left_frame, fg_color="transparent"); btn_tools.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(btn_tools, text="Marcar Todos", width=100, corner_radius=0, font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555", command=self.marcar_todos).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btn_tools, text="Desmarcar Todos", width=100, corner_radius=0, font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555", command=self.desmarcar_todos).pack(side="left")
        self.scroll_archivos = ctk.CTkScrollableFrame(left_frame, fg_color="#2B2B2B", corner_radius=0); self.scroll_archivos.pack(fill="both", expand=True, padx=15, pady=(5, 15))
        right_frame = ctk.CTkFrame(split_frame, fg_color="transparent", width=350); right_frame.pack(side="right", fill="y"); right_frame.pack_propagate(False)
        lbl_tools = ctk.CTkLabel(right_frame, text="2. Aplicar a la selección:", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(pady=(15, 5), anchor="w")
        h1_frame = ctk.CTkFrame(right_frame, fg_color="#1E1E1E", corner_radius=0, border_width=1, border_color="#444444"); h1_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(h1_frame, text="A. Buscar y Reemplazar", font=FUENTE_SUBTITULO, text_color=COLOR_ACENTO).pack(anchor="w", padx=15, pady=(15, 5))
        self.ent_buscar_adv = ctk.CTkEntry(h1_frame, placeholder_text="Buscar texto (Ej: HL-)", font=FUENTE_NORMAL, corner_radius=0); self.ent_buscar_adv.pack(fill="x", padx=15, pady=5)
        self.ent_reemplazo_adv = ctk.CTkEntry(h1_frame, placeholder_text="Reemplazar con (Ej: PL-)", font=FUENTE_NORMAL, corner_radius=0); self.ent_reemplazo_adv.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(h1_frame, text="Aplicar Reemplazo", font=FUENTE_NORMAL, corner_radius=0, fg_color="transparent", border_width=1, border_color=COLOR_TITULO, text_color=COLOR_TITULO, hover_color="#444444", command=self.aplicar_reemplazo_adv).pack(pady=15, padx=15, fill="x")
        h2_frame = ctk.CTkFrame(right_frame, fg_color="#1E1E1E", corner_radius=0, border_width=1, border_color="#444444"); h2_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(h2_frame, text="B. Cambio de Revisión", font=FUENTE_SUBTITULO, text_color=COLOR_ACENTO).pack(anchor="w", padx=15, pady=(15, 5))
        self.ent_rev_adv = ctk.CTkEntry(h2_frame, placeholder_text="Nueva letra/número (Ej: D)", font=FUENTE_NORMAL, corner_radius=0); self.ent_rev_adv.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(h2_frame, text="Aplicar Revisión", font=FUENTE_NORMAL, corner_radius=0, fg_color="transparent", border_width=1, border_color=COLOR_TITULO, text_color=COLOR_TITULO, hover_color="#444444", command=self.aplicar_revision_adv).pack(pady=15, padx=15, fill="x")
        self.log_rename = ctk.CTkTextbox(right_frame, height=120, font=FUENTE_CONSOLA, fg_color="#1E1E1E", state="disabled", corner_radius=0); self.log_rename.pack(fill="both", expand=True, pady=(0, 10))

    def log_r(self, m):
        self.log_rename.configure(state="normal"); self.log_rename.insert("end", m + "\n"); self.log_rename.see("end"); self.log_rename.configure(state="disabled")

    def cargar_archivos_renombrado(self):
        c = filedialog.askdirectory(title="Seleccionar carpeta con planos DWG")
        if not c: return
        self.ruta_renombre = c; self.lbl_ruta_adv.configure(text=f"Ruta: {c}", text_color=COLOR_TEXTO)
        for w in self.scroll_archivos.winfo_children(): w.destroy()
        self.checkboxes_archivos = []
        arcs = [f for f in os.listdir(self.ruta_renombre) if f.lower().endswith('.dwg')]
        for arc in arcs:
            cb = ctk.CTkCheckBox(self.scroll_archivos, text=arc, font=FUENTE_NORMAL, text_color=COLOR_TEXTO, fg_color=COLOR_ACENTO, hover_color="#005BBF"); cb.pack(anchor="w", pady=5, padx=5); cb.select(); self.checkboxes_archivos.append(cb)
        self.log_r(f"[*] {len(arcs)} archivos cargados.")

    def marcar_todos(self): [cb.select() for cb in self.checkboxes_archivos]
    def desmarcar_todos(self): [cb.deselect() for cb in self.checkboxes_archivos]

    def aplicar_reemplazo_adv(self):
        if not self.ruta_renombre: return self.log_r("[X] Carga una carpeta primero.")
        b, r = self.ent_buscar_adv.get(), self.ent_reemplazo_adv.get()
        if not b: return self.log_r("[X] Ingresa texto a buscar.")
        cont = 0
        for cb in self.checkboxes_archivos:
            if cb.get() == 1 and b in cb.cget("text"):
                old = cb.cget("text"); new = old.replace(b, r)
                try: os.rename(os.path.join(self.ruta_renombre, old), os.path.join(self.ruta_renombre, new)); cb.configure(text=new); cont += 1
                except Exception as e: self.log_r(f"[X] Error: {e}")
        self.log_r(f"[OK] {cont} procesados.")

    def aplicar_revision_adv(self):
        if not self.ruta_renombre: return self.log_r("[X] Carga una carpeta primero.")
        nr = self.ent_rev_adv.get().strip()
        if not nr: return self.log_r("[X] Ingresa la nueva revisión.")
        cont = 0
        for cb in self.checkboxes_archivos:
            if cb.get() == 1:
                old = cb.cget("text"); nb, ext = os.path.splitext(old)
                if len(nb) > 0:
                    new = nb[:-1] + nr + ext
                    try: os.rename(os.path.join(self.ruta_renombre, old), os.path.join(self.ruta_renombre, new)); cb.configure(text=new); cont += 1
                    except Exception as e: self.log_r(f"[X] Error: {e}")
        self.log_r(f"[OK] {cont} revisiones actualizadas.")

    def detener_comando_en_vivo(self):
        self.cancelar_comando_vivo = True; self.btn_cancelar_cmd.configure(state="disabled", text="Deteniendo...")

    def enviar_comando_en_vivo(self):
        c = self.entrada_comando.get()
        if not c: return
        self.cancelar_comando_vivo = False
        self.btn_enviar_cmd.configure(state="disabled", text="Enviando..."); self.btn_cancelar_cmd.configure(state="normal", text="Cancelar")
        threading.Thread(target=self._hilo_comando_en_vivo, args=(c.strip() + "\n",), daemon=True).start()

    def _hilo_comando_en_vivo(self, comando):
        pythoncom.CoInitialize()
        try:
            # 1. Armamos la lista masiva de versiones (15 a 35)
            prog_ids = ["ZWCAD.Application", "AutoCAD.Application"]
            for i in range(15, 36):
                prog_ids.append(f"ZWCAD.Application.{i}")
                prog_ids.append(f"AutoCAD.Application.{i}")
                
            apps_encontradas = []
            
            # 2. Recolectamos TODOS los programas CAD que estén abiertos
            for s in prog_ids:
                try: 
                    app = win32com.client.GetActiveObject(s)
                    if app: apps_encontradas.append(app)
                except: pass
                
            if not apps_encontradas: 
                return self.log("\n[X] Error: No se detecta CAD abierto. (Recuerda abrirlo como Administrador).")
                
            # Memoria para no repetir el comando en la misma pestaña si el ID de versión se cruza
            docs_procesados = set()
            ejecuciones = 0
            
            # 3. Disparamos a las pestañas de TODOS los programas encontrados
            for app in apps_encontradas:
                if self.cancelar_comando_vivo: break
                try:
                    docs = app.Documents
                    for i in range(docs.Count):
                        if self.cancelar_comando_vivo: break
                        try:
                            doc = docs.Item(i)
                            
                            # Identificador único del plano (Ruta + Nombre)
                            doc_id = f"{doc.FullName}_{doc.Name}"
                            
                            # Si ya procesamos esta pestaña, saltamos a la siguiente
                            if doc_id in docs_procesados:
                                continue
                                
                            docs_procesados.add(doc_id)
                            
                            # Activamos la pestaña y enviamos el comando
                            if app.ActiveDocument.Name != doc.Name: 
                                app.ActiveDocument = doc
                                time.sleep(0.2)
                                
                            try: doc.SendCommand("\x03\x03") # Cancelamos comandos previos (ESC ESC)
                            except: pass
                            
                            doc.SendCommand(comando)
                            self.log(f"  > Aplicado en: {doc.Name}")
                            ejecuciones += 1
                        except Exception as e: 
                            self.log(f"  > [X] Error pestaña: {e}")
                except:
                    pass # Falla silenciosa si la aplicación no responde (ej. si el usuario la cerró de golpe)
                    
            if ejecuciones == 0:
                self.log(" [!] No hay planos abiertos en los programas detectados.")
                
        except Exception as e: 
            self.log(f"\n[X] Fallo COM: {e}")
        finally:
            self.btn_enviar_cmd.configure(state="normal", text="Ejecutar")
            self.btn_cancelar_cmd.configure(state="disabled", text="Cancelar")
            pythoncom.CoUninitialize()

    def log(self, m): self.consola.configure(state="normal"); self.consola.insert("end", m + "\n"); self.consola.see("end"); self.consola.configure(state="disabled")
    def abrir_carpeta_local(self): os.startfile(RUTA_LOCAL_APP) if os.path.exists(RUTA_LOCAL_APP) else None
    def forzar_path_manual(self): 
        self.actualizar_rutas_registro()
        self.actualizar_variable_entorno()
        self.log("[!] PATH y Registro CAD reparados.")

    def iniciar_actualizacion_hilo(self):
        self.btn_actualizar.configure(state="disabled", text="Sincronizando...")
        self.consola.configure(state="normal"); self.consola.delete("1.0", "end"); self.consola.configure(state="disabled")
        threading.Thread(target=self.motor_actualizacion, daemon=True).start()

    def motor_actualizacion(self):
        try:
            # Detecta el nombre exacto del ejecutable actual (ej: SINCAL.exe)
            nombre_exe_actual = os.path.basename(sys.executable).lower()
            
            if os.path.exists(RUTA_LOCAL_APP):
                for elemento in os.listdir(RUTA_LOCAL_APP):
                    ruta_elemento = os.path.join(RUTA_LOCAL_APP, elemento)
                    
                    # SALVAVIDAS: Protege el programa actual y el desinstalador de Inno Setup
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
            # Ahora le decimos que descargue ambos archivos de texto
            archivos = r.get("archivos", []) + ["README.md", "TUTORIAL.md"]
            total_archivos = len(archivos)
            spinner = ['|', '/', '-', '\\']
            
            # Imprimimos la línea base que será animada
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
                
                # --- ANIMACIÓN Y PORCENTAJE ---
                porcentaje = int(((idx + 1) / total_archivos) * 100)
                simbolo = spinner[idx % 4]
                
                self.consola.configure(state="normal")
                # Borramos la última línea y la reemplazamos con la animada
                self.consola.delete("end-2l", "end-1c")
                self.consola.insert("end", f"[{simbolo}] Actualizando SINCAL... {porcentaje}% ({idx+1}/{total_archivos})\n")
                self.consola.see("end")
                self.consola.configure(state="disabled")
            
            self.generar_archivos_lisp(archivos)
            self.actualizar_rutas_registro()
            self.actualizar_variable_entorno()
            self.buscar_y_configurar_consolas()
            
            self.version_local_actual = r.get("version", "v1.0.0")
            self.log(f"\n[!] SINCAL Sincronizado: {self.version_local_actual}")
            self.mostrar_notificacion("SINCAL Actualizado", f"Instalada versión {self.version_local_actual}")
            
        except Exception as e: 
            self.log(f"[!] Error crítico en actualización: {e}")
        finally: 
            self.btn_actualizar.configure(state="normal", text="Instalar / Actualizar Todo")

    def buscar_y_configurar_consolas(self):
        self.cad_exe_path = None
        for p in [r"C:\Program Files\Autodesk", r"C:\Program Files\ZWSOFT"]:
            if os.path.exists(p):
                for root, dirs, files in os.walk(p):
                    for f in files:
                        if f.lower() in ["accoreconsole.exe", "zwcad.exe"]:
                            self.cad_exe_path = os.path.join(root, f)
                            if "zwcad" in f.lower(): self.es_zwcad = True
                            
                            # --- NUEVA CONEXIÓN: Crear el cad_wrapper.bat para PowerShell ---
                            ruta_wrapper = os.path.join(RUTA_LOCAL_APP, "cad_wrapper.bat")
                            try:
                                with open(ruta_wrapper, 'w', encoding='utf-8') as wf:
                                    # Genera un bat que recibe los comandos (/i, /s) y se los pasa a la consola CAD oculta (%*)
                                    wf.write(f'@echo off\n"{self.cad_exe_path}" %*\n')
                            except Exception as e:
                                self.log(f"[X] Error creando wrapper CAD: {e}")
                            # ----------------------------------------------------------------
                            
                            return

    def actualizar_rutas_registro(self):
        """Inyecta la bóveda SINCAL en la prioridad 1 de AutoCAD/ZWCAD y neutraliza fantasmas"""
        
        # --- 1. CAZAFANTASMAS: Neutralizar acaddoc/zwcaddoc antiguos ---
        appdata = os.getenv('APPDATA')
        for carpeta_cad in ["Autodesk", "ZWSOFT"]:
            base = os.path.join(appdata, carpeta_cad)
            if os.path.exists(base):
                for root, dirs, files in os.walk(base):
                    for file in files:
                        if file.lower() in ["acaddoc.lsp", "zwcaddoc.lsp"]:
                            ruta_fantasma = os.path.join(root, file)
                            # Verificamos que no esté intentando borrar nuestro propio archivo en la bóveda
                            if RUTA_LOCAL_APP.lower() not in ruta_fantasma.lower():
                                try:
                                    os.rename(ruta_fantasma, ruta_fantasma + ".bak")
                                    self.log(f"[*] Fantasma neutralizado en: {os.path.basename(root)}")
                                except: pass

        # --- 2. INYECTOR DE REGISTRO UNIVERSAL ---
        def inyectar_ruta_recursivo(ruta_reg):
            try:
                llave = winreg.OpenKey(winreg.HKEY_CURRENT_USER, ruta_reg, 0, winreg.KEY_ALL_ACCESS)
                
                # Buscamos directamente las variables maestras sin importar en qué subcarpeta estén
                for nombre_valor in ["ACAD", "ZWCAD", "ZWCADSEARCHPATH", "SRCHPATH", "TRUSTEDPATHS"]:
                    try:
                        valor_actual, tipo = winreg.QueryValueEx(llave, nombre_valor)
                        if RUTA_LOCAL_APP.lower() not in valor_actual.lower():
                            # Inyectamos nuestra bóveda de primera (Separada por punto y coma)
                            nuevo_valor = f"{RUTA_LOCAL_APP};{valor_actual}"
                            winreg.SetValueEx(llave, nombre_valor, 0, tipo, nuevo_valor)
                            self.log(f"[*] SINCAL inyectado en registro: {nombre_valor}")
                    except OSError:
                        pass

                # Exploración profunda en todas las subcarpetas del registro
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

        # Disparamos la inyección en las dos marcas de software
        inyectar_ruta_recursivo(r"Software\Autodesk\AutoCAD")
        inyectar_ruta_recursivo(r"Software\ZWSOFT\ZWCAD")

    def actualizar_variable_entorno(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
            p, _ = winreg.QueryValueEx(key, "Path")
            if RUTA_LOCAL_APP.lower() not in p.lower(): winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, f"{p};{RUTA_LOCAL_APP}")
            winreg.CloseKey(key)
        except: pass

    def generar_archivos_lisp(self, archivos):
        contenido_arranque = ""
        
        for a in archivos:
            if a.lower().endswith('.lsp') and os.path.basename(a).lower() not in ["acaddoc.lsp", "zwcaddoc.lsp"]:
                # Convertimos la ruta a estándar puro de LISP (slashes frontales)
                ruta_lisp = os.path.normpath(os.path.join(RUTA_LOCAL_APP, a)).replace("\\", "/")
                nombre = os.path.basename(a)
                contenido_arranque += f'(princ (load "{ruta_lisp}" "\\n[X] SINCAL: Fallo al cargar {nombre}"))\n'
        
        # --- Cargar Startup Automáticamente ---
        if "startup/SINCAL_STARTUP.lsp" in archivos or "SINCAL_STARTUP.lsp" in archivos:
             contenido_arranque += '(princ "\\n[SINCAL] Políticas de empresa y variables aplicadas.")\n'

        contenido_arranque += '(princ "\\n[OK] SINCAL: Todos los LISPs procesados correctamente.")\n(princ)\n'

        # --- GUARDAR PARA AMBOS PROGRAMAS ---
        r_acad = os.path.join(RUTA_LOCAL_APP, "acaddoc.lsp")
        r_zwcad = os.path.join(RUTA_LOCAL_APP, "zwcaddoc.lsp")
        
        with open(r_acad, 'w', encoding='utf-8') as f:
            f.write(contenido_arranque)
            
        with open(r_zwcad, 'w', encoding='utf-8') as f:
            f.write(contenido_arranque)

def arrancar():
    import sys
    app = ActualizadorCAD()
    if "--background" in sys.argv: app.ocultar_a_bandeja()
    app.mainloop()