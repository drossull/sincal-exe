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
from tkinter import messagebox

# --- 1. FORZAR MODO ADMINISTRADOR ESTRICTO ---
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

# --- CONFIGURACIÓN ---
USUARIO_GITHUB = "drossull" 
REPO_GITHUB = "sincal-exe"
RAMA = "main" 
URL_BASE_RAW = f"https://raw.githubusercontent.com/{USUARIO_GITHUB}/{REPO_GITHUB}/{RAMA}/"

# RUTA DEFINITIVA SIN TILDE
RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estandar SINCAL") 

# URL DEL WEBHOOK (Google Sheets)
URL_WEBHOOK_SHEETS = "https://script.google.com/macros/s/AKfycbywJwskXQrAhNYHV559ngE5WAPa-bhvrfgcYg0ej_WDfxQMP5vmT31b66mEPqeFCchaPQ/exec"

# Colores SINCAL
COLOR_FONDO = "#333333"      
COLOR_TITULO = "#FFBF00"     
COLOR_TEXTO = "#CCCCCC"      
COLOR_ACENTO = "#007FFF"     

# Fuentes
FUENTE_TITULO = ("Consolas", 24, "bold")
FUENTE_SUBTITULO = ("Consolas", 18, "bold")
FUENTE_NORMAL = ("Consolas", 14)
FUENTE_CONSOLA = ("Consolas", 12)

ctk.set_appearance_mode("dark") 

def obtener_ruta_recurso(ruta_relativa):
    try:
        ruta_base = sys._MEIPASS
    except Exception:
        ruta_base = os.path.abspath(".")
    return os.path.join(ruta_base, ruta_relativa)

class ActualizadorCAD(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SINCAL - Suite de Herramientas (Modo Admin)")
        self.geometry("900x700")
        self.minsize(700, 500) 
        self.resizable(True, True) 
        self.configure(fg_color=COLOR_FONDO)
        
        self.cad_exe_path = None
        self.es_zwcad = False
        self.version_local_actual = "v1.4.7" # Versión base inicial

        try:
            self.iconbitmap(obtener_ruta_recurso("logo.ico"))
        except: pass

        self.tutoriales = {}

        # --- CONTENEDOR PRINCIPAL CON SCROLL VERTICAL ---
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_FONDO, corner_radius=0)
        self.main_scroll.pack(fill="both", expand=True)

        # --- SISTEMA DE PESTAÑAS (FUSIONADO) ---
        self.tabview = ctk.CTkTabview(self.main_scroll, width=850, height=650, fg_color=COLOR_FONDO,
                                      segmented_button_selected_color=COLOR_ACENTO,
                                      segmented_button_selected_hover_color=COLOR_ACENTO,
                                      segmented_button_unselected_hover_color="#444444")
        self.tabview.pack(padx=20, pady=10)
        self.tabview._segmented_button.configure(font=FUENTE_NORMAL, text_color=COLOR_TEXTO)
        
        self.tab_main = self.tabview.add("Sincronizador")
        self.tab_docs = self.tabview.add("Documentación Wiki")

        for tab in [self.tab_main, self.tab_docs]:
            tab.configure(fg_color=COLOR_FONDO)

        self.setup_tab_sincronizador()
        self.setup_tab_docs()

        # Hilos en segundo plano
        threading.Thread(target=self.cargar_info_github, daemon=True).start()
        threading.Thread(target=self.loop_verificador_actualizaciones, daemon=True).start()

    def setup_tab_sincronizador(self):
        header_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        header_frame.pack(pady=10, fill="x", padx=10)
        lbl_titulo = ctk.CTkLabel(header_frame, text="ESTÁNDAR SINCAL", font=FUENTE_TITULO, text_color=COLOR_TITULO)
        lbl_titulo.pack(expand=True)

        self.btn_actualizar = ctk.CTkButton(self.tab_main, text="Instalar / Actualizar Todo", font=FUENTE_NORMAL,
                                           fg_color=COLOR_ACENTO, hover_color="#005BBF", text_color="white",
                                           command=self.iniciar_actualizacion_hilo)
        self.btn_actualizar.pack(pady=15)

        botones_sec_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        botones_sec_frame.pack(pady=5)

        self.btn_folder = ctk.CTkButton(botones_sec_frame, text="Abrir carpeta local", font=FUENTE_NORMAL, 
                                       fg_color="transparent", border_width=1, border_color=COLOR_ACENTO,
                                       text_color=COLOR_TEXTO, hover_color="#444444", command=self.abrir_carpeta_local)
        self.btn_folder.pack(side="left", padx=10)

        self.btn_forzar_path = ctk.CTkButton(botones_sec_frame, text="Reparar / Forzar PATH", font=FUENTE_NORMAL, 
                                       fg_color="transparent", border_width=1, border_color=COLOR_TITULO,
                                       text_color=COLOR_TITULO, hover_color="#444444", command=self.forzar_path_manual)
        self.btn_forzar_path.pack(side="left", padx=10)

        self.consola = ctk.CTkTextbox(self.tab_main, width=800, height=180, font=FUENTE_CONSOLA, 
                                     fg_color="#222222", text_color=COLOR_TEXTO, state="disabled")
        self.consola.pack(pady=15)

        # --- SECCIÓN DE ÚLTIMAS ACTUALIZACIONES (10 COMMITS) ---
        self.frame_updates = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        self.frame_updates.pack(fill="x", padx=30, pady=(0, 10))

        self.lbl_updates_title = ctk.CTkLabel(self.frame_updates, text="Últimas 10 actualizaciones", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO)
        self.lbl_updates_title.pack(anchor="w", pady=(0, 5))

        self.txt_updates = ctk.CTkTextbox(self.frame_updates, width=800, height=120, font=FUENTE_NORMAL, 
                                          fg_color="#1E1E1E", text_color=COLOR_TEXTO, state="disabled")
        self.txt_updates.pack(anchor="w")

    def setup_tab_docs(self):
        # Layout tipo Wiki: Menú Izquierda, Contenido Derecha
        self.wiki_frame = ctk.CTkFrame(self.tab_docs, fg_color="transparent")
        self.wiki_frame.pack(fill="both", expand=True)
        
        self.menu_frame = ctk.CTkScrollableFrame(self.wiki_frame, width=220, label_text="Índice", 
                                                label_text_color=COLOR_TITULO, fg_color="#222222")
        self.menu_frame._label.configure(font=FUENTE_NORMAL)
        self.menu_frame.pack(side="left", fill="y", padx=(0, 10), pady=10)
        
        self.content_frame = ctk.CTkFrame(self.wiki_frame, fg_color="#222222")
        self.content_frame.pack(side="right", fill="both", expand=True, pady=10)
        
        self.lbl_wiki_title = ctk.CTkLabel(self.content_frame, text="Documentación SINCAL", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO)
        self.lbl_wiki_title.pack(pady=15)
        
        self.txt_wiki_content = ctk.CTkTextbox(self.content_frame, width=500, height=450, font=FUENTE_NORMAL, fg_color="#1E1E1E", text_color=COLOR_TEXTO)
        self.txt_wiki_content.pack(padx=20, pady=10, fill="both", expand=True)
        
        self.cargar_lista_tutoriales()

    def cargar_info_github(self):
        try:
            r_ver = requests.get(URL_BASE_RAW + "version.json", timeout=5)
            if r_ver.status_code == 200:
                self.version_local_actual = r_ver.json().get("version", "Desconocida")

            # Pedir los últimos 10 commits
            url_api = f"https://api.github.com/repos/{USUARIO_GITHUB}/{REPO_GITHUB}/commits"
            params = {"sha": RAMA, "per_page": 10}
            r_commit = requests.get(url_api, params=params, timeout=5)
            
            self.txt_updates.configure(state="normal")
            self.txt_updates.delete("1.0", "end")

            if r_commit.status_code == 200:
                commits = r_commit.json()
                self.txt_updates.insert("end", f"Versión actual en la nube: {self.version_local_actual}\n\n")
                for c in commits:
                    fecha = c['commit']['author']['date'].split("T")[0] 
                    mensaje = c['commit']['message'].split("\n")[0]
                    self.txt_updates.insert("end", f"🗓️ {fecha} | 📝 {mensaje}\n")
            else:
                self.txt_updates.insert("end", "No se pudo conectar con el registro de commits de GitHub.")
            
            self.txt_updates.configure(state="disabled")
        except Exception:
            self.txt_updates.configure(state="normal")
            self.txt_updates.insert("end", "Error obteniendo la información de actualizaciones.")
            self.txt_updates.configure(state="disabled")

    def loop_verificador_actualizaciones(self):
        """Sabueso en segundo plano: Revisa cada 60 min si hay cambios en version.json"""
        while True:
            time.sleep(3600) # Espera 1 hora
            try:
                r_ver = requests.get(URL_BASE_RAW + "version.json", timeout=5)
                if r_ver.status_code == 200:
                    version_nube = r_ver.json().get("version")
                    # Validar si version_local_actual existe y es distinta
                    if version_nube and version_nube != self.version_local_actual:
                        self.mostrar_popup_actualizacion(version_nube)
            except:
                pass

    def mostrar_popup_actualizacion(self, nueva_version):
        respuesta = messagebox.askyesno(
            title="¡Nueva Actualización SINCAL!", 
            message=f"Se ha detectado una nueva versión del Estándar en la nube ({nueva_version}).\n\n¿Deseas descargarla y aplicarla ahora?"
        )
        if respuesta:
            self.iniciar_actualizacion_hilo()

    def cargar_lista_tutoriales(self):
        for widget in self.menu_frame.winfo_children(): widget.destroy()
        
        # 1. Botón fijo para el README
        btn_readme = ctk.CTkButton(self.menu_frame, text="Guía de Inicio (README)", font=FUENTE_NORMAL, fg_color="#444444", text_color=COLOR_TITULO,
                                    hover_color=COLOR_ACENTO, command=self.mostrar_readme)
        btn_readme.pack(fill="x", pady=(5, 15), padx=5)

        # 2. Cargar Comandos desde JSON
        ruta_json = os.path.join(RUTA_LOCAL_APP, "tutoriales.json")
        if os.path.exists(ruta_json):
            try:
                with open(ruta_json, 'r', encoding='utf-8') as f:
                    self.tutoriales = json.load(f)
                
                for cmd, data in self.tutoriales.items():
                    btn = ctk.CTkButton(self.menu_frame, text=cmd, font=FUENTE_NORMAL, fg_color="transparent", text_color=COLOR_TEXTO,
                                        border_width=1, border_color="#555555", hover_color=COLOR_ACENTO,
                                        command=lambda c=cmd: self.mostrar_comando_wiki(c))
                    btn.pack(fill="x", pady=2, padx=5)
            except: pass
        
        self.mostrar_readme()

    def mostrar_readme(self):
        self.lbl_wiki_title.configure(text="Guía de Inicio y Configuración")
        self.txt_wiki_content.configure(state="normal")
        self.txt_wiki_content.delete("1.0", "end")
        
        # Leer el README local descargado, si no existe, texto por defecto
        ruta_readme = os.path.join(RUTA_LOCAL_APP, "README.md")
        if os.path.exists(ruta_readme):
            with open(ruta_readme, 'r', encoding='utf-8') as f:
                contenido = f.read()
        else:
            contenido = "El archivo README.md aún no se ha descargado. Por favor, presiona 'Actualizar Todo'."
            
        self.txt_wiki_content.insert("0.0", contenido)
        self.txt_wiki_content.configure(state="disabled")

    def mostrar_comando_wiki(self, cmd):
        data = self.tutoriales.get(cmd, {})
        titulo = data.get("titulo", cmd)
        descripcion = data.get("descripcion", "Descripción no disponible.")
        
        self.lbl_wiki_title.configure(text=titulo)
        self.txt_wiki_content.configure(state="normal")
        self.txt_wiki_content.delete("1.0", "end")
        self.txt_wiki_content.insert("0.0", descripcion)
        self.txt_wiki_content.configure(state="disabled")

    def log(self, mensaje):
        self.consola.configure(state="normal")
        self.consola.insert("end", mensaje + "\n")
        self.consola.see("end")
        self.consola.configure(state="disabled")

    def abrir_carpeta_local(self):
        if os.path.exists(RUTA_LOCAL_APP): os.startfile(RUTA_LOCAL_APP)

    def forzar_path_manual(self):
        self.log("\n--- REPARACIÓN DE VARIABLES DE ENTORNO (PATH) ---")
        self.actualizar_variable_entorno()
        self.log(" [!] Cierra cualquier consola o programa abierto para aplicar los cambios.\n")

    def iniciar_actualizacion_hilo(self):
        self.btn_actualizar.configure(state="disabled", text="Sincronizando...")
        self.consola.configure(state="normal")
        self.consola.delete("1.0", "end")
        self.consola.configure(state="disabled")
        threading.Thread(target=self.motor_actualizacion, daemon=True).start()

    def enviar_telemetria(self, version_instalada):
        try:
            usuario_windows = os.environ.get('USERNAME', 'Desconocido')
            payload = {"usuario": usuario_windows, "version": version_instalada, "accion": "Actualización Completada"}
            requests.post(URL_WEBHOOK_SHEETS, json=payload, timeout=5)
        except: pass 

    def motor_actualizacion(self):
        self.log("--- INICIANDO ACTUALIZACIÓN ---")
        
        # 1. LIMPIEZA AGRESIVA
        old_folder = os.path.join(os.getenv('APPDATA'), "Estándar SINCAL")
        if os.path.exists(old_folder):
            try: shutil.rmtree(old_folder)
            except: pass

        if os.path.exists(RUTA_LOCAL_APP):
            try:
                shutil.rmtree(RUTA_LOCAL_APP)
                self.log(" [!] Carpeta local eliminada para instalación limpia.")
            except Exception as e:
                self.log(f" [X] Aviso al limpiar carpeta: Cierre archivos abiertos. ({e})")

        os.makedirs(RUTA_LOCAL_APP, exist_ok=True)
        
        try:
            # 2. DESCARGA DE RECURSOS
            r = requests.get(URL_BASE_RAW + "version.json")
            data = r.json()
            version_nube = data.get("version", "v1.0.0")
            archivos = data.get("archivos", [])
            
            # Forzar descarga de README.md
            archivos.append("README.md")

            for a in archivos:
                r_save = os.path.join(RUTA_LOCAL_APP, a)
                os.makedirs(os.path.dirname(r_save), exist_ok=True)
                res = requests.get(URL_BASE_RAW + a)
                if res.status_code == 200:
                    with open(r_save, 'wb') as f: f.write(res.content)
                    self.log(f"  > Descargado: {os.path.basename(a)}")
            
            # 3. CONFIGURACIONES NATIVAS
            self.generar_archivos_lisp(archivos)
            self.actualizar_rutas_registro()
            self.actualizar_variable_entorno()
            
            self.buscar_y_configurar_consolas()
            
            if self.cad_exe_path and self.es_zwcad:
                self.inyectar_via_comando_directo()
            
            self.version_local_actual = version_nube
            self.log(f"\n[!] PROCESO FINALIZADO. VERSIÓN: {version_nube}")
            self.enviar_telemetria(version_nube)
            self.cargar_info_github()
            self.cargar_lista_tutoriales()
            
        except Exception as e: 
            self.log(f"[!] Error durante la descarga: {e}")
        
        self.btn_actualizar.configure(state="normal", text="Instalar / Actualizar Todo")

    def buscar_y_configurar_consolas(self):
        ruta_env = os.path.join(RUTA_LOCAL_APP, "scripts", "cad_env.bat")
        ruta_wrapper = os.path.join(RUTA_LOCAL_APP, "scripts", "cad_wrapper.bat")
        self.cad_exe_path = None
        self.es_zwcad = False
        
        # Búsqueda AutoCAD en Registro
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Autodesk\AutoCAD") as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    v = winreg.EnumKey(k, i)
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SOFTWARE\\Autodesk\\AutoCAD\\{v}") as vk:
                        for j in range(winreg.QueryInfoKey(vk)[0]):
                            p = winreg.EnumKey(vk, j)
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SOFTWARE\\Autodesk\\AutoCAD\\{v}\\{p}") as pk:
                                path, _ = winreg.QueryValueEx(pk, "InstallPath")
                                if os.path.exists(os.path.join(path, "accoreconsole.exe")):
                                    self.cad_exe_path = os.path.join(path, "accoreconsole.exe")
                                    break
        except: pass

        # Búsqueda AutoCAD Fuerza Bruta
        if not self.cad_exe_path:
            try:
                base_dir = r"C:\Program Files\Autodesk"
                if os.path.exists(base_dir):
                    carpetas = sorted(os.listdir(base_dir), reverse=True)
                    for folder in carpetas:
                        if "AutoCAD" in folder:
                            posible_exe = os.path.join(base_dir, folder, "accoreconsole.exe")
                            if os.path.exists(posible_exe):
                                self.cad_exe_path = posible_exe
                                break
            except: pass

        # Búsqueda ZWCAD
        if not self.cad_exe_path:
            try:
                base_dir = r"C:\Program Files\ZWSOFT"
                if os.path.exists(base_dir):
                    carpetas = sorted(os.listdir(base_dir), reverse=True)
                    for folder in carpetas:
                        if "ZWCAD" in folder.upper():
                            posible_exe = os.path.join(base_dir, folder, "ZWCAD.exe")
                            if os.path.exists(posible_exe):
                                self.cad_exe_path = posible_exe
                                self.es_zwcad = True
                                break
            except: pass

        if self.cad_exe_path:
            os.makedirs(os.path.dirname(ruta_wrapper), exist_ok=True)
            with open(ruta_wrapper, 'w') as f:
                f.write('@echo off\n')
                f.write('set "DWG_FILE=%~2"\nset "SCR_FILE=%~4"\n')
                f.write(f'set "CAD_EXE={self.cad_exe_path}"\n')
                if self.es_zwcad: 
                    f.write('start /wait "" "%CAD_EXE%" "%DWG_FILE%" /b "%SCR_FILE%"\n')
                else: 
                    f.write('"%CAD_EXE%" /i "%DWG_FILE%" /s "%SCR_FILE%"\n')
            with open(ruta_env, 'w') as f: 
                f.write(f'@set "CAD_CONSOLE={ruta_wrapper}"')
            
            tipo = "ZWCAD (Gráfico)" if self.es_zwcad else "AutoCAD (Silencioso)"
            self.log(f" [+] Motor Batch vinculado a: {tipo}")

    def inyectar_via_comando_directo(self):
        self.log(" [!] Lanzando ZWCAD para auto-configurar rutas (Espere un momento)...")
        ruta_escapada = RUTA_LOCAL_APP.replace("\\", "\\\\")
        lisp_cmd = (
            f'(vl-load-com) '
            f'(setq p (vla-get-Files (vla-get-Preferences (vlax-get-acad-object)))) '
            f'(setq s (vla-get-SupportPath p)) '
            f'(if (not (vl-string-search "SINCAL" s)) (vla-put-SupportPath p (strcat s ";{ruta_escapada}"))) '
            f'(setvar "TRUSTEDPATHS" (strcat (getvar "TRUSTEDPATHS") ";{ruta_escapada}")) '
            f'_.QSAVE (command "_QUIT")'
        )
        try:
            subprocess.Popen([self.cad_exe_path, "/cmd", lisp_cmd])
        except Exception as e:
            self.log(f" [X] Falló el auto-lanzamiento: {e}")

    def actualizar_rutas_registro(self):
        carpeta_ctb = os.path.join(RUTA_LOCAL_APP, "plotstyles")
        bases = [r"Software\Autodesk\AutoCAD", r"Software\ZWSOFT\ZWCAD"]
        old_folder = os.path.join(os.getenv('APPDATA'), "Estándar SINCAL") 
        
        for base in bases:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as k1:
                    for i in range(winreg.QueryInfoKey(k1)[0]):
                        v1 = winreg.EnumKey(k1, i)
                        try:
                            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{base}\\{v1}") as k2:
                                for j in range(winreg.QueryInfoKey(k2)[0]):
                                    v2 = winreg.EnumKey(k2, j)
                                    profs_path = f"{base}\\{v1}\\{v2}\\Profiles"
                                    try:
                                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, profs_path) as k3:
                                            for k in range(winreg.QueryInfoKey(k3)[0]):
                                                prof_name = winreg.EnumKey(k3, k)
                                                gen_path = f"{profs_path}\\{prof_name}\\General"
                                                try:
                                                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, gen_path, 0, winreg.KEY_ALL_ACCESS) as gk:
                                                        for var in ["SearchPath", "SEARCHPATH", "ACAD", "ZWCAD", "TrustedPaths"]:
                                                            try:
                                                                val, _ = winreg.QueryValueEx(gk, var)
                                                                if old_folder in val:
                                                                    val = val.replace(old_folder, RUTA_LOCAL_APP)
                                                                if RUTA_LOCAL_APP.lower() not in val.lower():
                                                                    winreg.SetValueEx(gk, var, 0, winreg.REG_SZ, f"{val};{RUTA_LOCAL_APP}")
                                                                else:
                                                                    winreg.SetValueEx(gk, var, 0, winreg.REG_SZ, val) 
                                                            except:
                                                                if var == "TrustedPaths": winreg.SetValueEx(gk, var, 0, winreg.REG_SZ, RUTA_LOCAL_APP)
                                                        try:
                                                            r_ctb, _ = winreg.QueryValueEx(gk, "PrinterStyleSheetDir")
                                                            if r_ctb:
                                                                r_ctb = os.path.expandvars(r_ctb)
                                                                for c in os.listdir(carpeta_ctb):
                                                                    if c.lower().endswith('.ctb'): shutil.copy2(os.path.join(carpeta_ctb, c), os.path.join(r_ctb, c))
                                                        except: pass
                                                except: pass
                                    except: pass
                        except: pass
            except: pass
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)

    def actualizar_variable_entorno(self):
        r_scripts = os.path.join(RUTA_LOCAL_APP, "scripts")
        old_scripts = os.path.join(os.getenv('APPDATA'), "Estándar SINCAL", "scripts")
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
                try: p, _ = winreg.QueryValueEx(key, "Path")
                except: p = ""
                if old_scripts in p:
                    p = p.replace(old_scripts, r_scripts)
                if r_scripts.lower() not in p.lower():
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, f"{p};{r_scripts}")
                else:
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, p) 
                ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
        except: pass

    def generar_archivos_lisp(self, archivos):
        r_dwg = os.path.join(RUTA_LOCAL_APP, "masters", "FORMATOS ANOTATIVOS ACAD_2025.dwg").replace('\\', '\\\\')
        r_sincal = os.path.join(RUTA_LOCAL_APP, "lisps", "SINCAL.lsp")
        lisp_code = f'''(defun c:SINCAL (/ R n c a e) (vl-load-com) (setq R "{r_dwg}") (setq c (getvar "CMDECHO") a (getvar "ATTREQ")) (setvar "CMDECHO" 0) (setvar "ATTREQ" 0) (if (findfile R) (progn (setq n (vl-filename-base R)) (if (tblsearch "BLOCK" n) (command "._-INSERT" (strcat n "=" R) "_Y" "0,0,0" "1" "1" "0") (command "._-INSERT" R "0,0,0" "1" "1" "0")) (setq e (entlast)) (if e (entdel e)) (vl-cmdf "._-PURGE" "_B" n "_N") (if (tblsearch "STYLE" "RomanD") (setvar "TEXTSTYLE" "RomanD")) (if (tblsearch "DIMSTYLE" "GSG_COTAS") (command "._-DIMSTYLE" "_R" "GSG_COTAS")) (princ (strcat "\\n[OK] " R))) (alert "Error Maestro")) (setvar "ATTREQ" a) (setvar "CMDECHO" c) (princ))'''
        
        os.makedirs(os.path.dirname(r_sincal), exist_ok=True)
        with open(r_sincal, 'w', encoding='utf-8') as f: f.write(lisp_code)
        
        ruta_escapada = RUTA_LOCAL_APP.replace("\\", "\\\\")
        lisp_hack_rutas = f'''
(vl-load-com)
(vl-catch-all-apply
  '(lambda ( / pref paths newpath )
    (setq pref (vla-get-Files (vla-get-Preferences (vlax-get-acad-object))))
    (setq paths (vla-get-SupportPath pref))
    (setq newpath "{ruta_escapada}")
    (if (not (vl-string-search "SINCAL" paths))
      (vla-put-SupportPath pref (strcat paths ";" newpath))
    )
  )
)
'''
        r_acc = os.path.join(RUTA_LOCAL_APP, "acaddoc.lsp")
        with open(r_acc, 'w', encoding='utf-8') as f:
            f.write(lisp_hack_rutas)
            r_sincal_escapado = r_sincal.replace("\\", "\\\\")
            f.write(f'(load "{r_sincal_escapado}")\n')
            
            for a in archivos:
                if a.endswith('.lsp') and "SINCAL.lsp" not in a:
                    ruta_lisp = os.path.join(RUTA_LOCAL_APP, a).replace("\\", "\\\\")
                    f.write(f'(if (findfile "{ruta_lisp}") (load "{ruta_lisp}"))\n')
        
        r_zwcdoc = os.path.join(RUTA_LOCAL_APP, "zwcaddoc.lsp")
        r_zwc = os.path.join(RUTA_LOCAL_APP, "zwcad.lsp")
        shutil.copy2(r_acc, r_zwcdoc)
        shutil.copy2(r_acc, r_zwc)
        
        self.inyectar_arranque_nativo(r_acc, r_zwcdoc, r_zwc)

    def inyectar_arranque_nativo(self, r_acc, r_zwcdoc, r_zwc):
        appdata = os.getenv('APPDATA')
        if os.path.exists(os.path.join(appdata, "ZWSOFT")):
            for root, dirs, files in os.walk(os.path.join(appdata, "ZWSOFT")):
                if os.path.basename(root).lower() == "support":
                    try:
                        shutil.copy2(r_zwcdoc, os.path.join(root, "zwcaddoc.lsp"))
                        shutil.copy2(r_zwc, os.path.join(root, "zwcad.lsp"))
                        self.log(f" [+] Arranque inyectado en: ZWSOFT\\..\\Support")
                    except: pass
        if os.path.exists(os.path.join(appdata, "Autodesk")):
            for root, dirs, files in os.walk(os.path.join(appdata, "Autodesk")):
                if os.path.basename(root).lower() == "support":
                    try:
                        shutil.copy2(r_acc, os.path.join(root, "acaddoc.lsp"))
                        self.log(f" [+] Arranque inyectado en: Autodesk\\..\\Support")
                    except: pass

if __name__ == "__main__":
    app = ActualizadorCAD()
    app.mainloop()