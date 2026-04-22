import os
import sys
import json
import requests
import winreg
import threading
import ctypes
import shutil
from PIL import Image
import customtkinter as ctk

# --- CONFIGURACIÓN ---
USUARIO_GITHUB = "drossull" 
REPO_GITHUB = "sincal-exe"
RAMA = "main" 
URL_BASE_RAW = f"https://raw.githubusercontent.com/{USUARIO_GITHUB}/{REPO_GITHUB}/{RAMA}/"
RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estándar SINCAL") 

# 👇 PEGA AQUÍ TU URL DE GOOGLE APPS SCRIPT 👇
URL_WEBHOOK_SHEETS = "https://script.google.com/macros/s/AKfycbywJwskXQrAhNYHV559ngE5WAPa-bhvrfgcYg0ej_WDfxQMP5vmT31b66mEPqeFCchaPQ/exec"

# Definición de Colores SINCAL
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
        self.title("SINCAL - Suite de Herramientas v1.1.1")
        self.geometry("850x660")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_FONDO)

        try:
            self.iconbitmap(obtener_ruta_recurso("logo.ico"))
        except:
            pass

        self.tutoriales = {}

        # --- SISTEMA DE PESTAÑAS ---
        self.tabview = ctk.CTkTabview(self, 
                                      width=810, 
                                      height=610, 
                                      fg_color=COLOR_FONDO,
                                      segmented_button_selected_color=COLOR_ACENTO,
                                      segmented_button_selected_hover_color=COLOR_ACENTO,
                                      segmented_button_unselected_hover_color="#444444")
        self.tabview.pack(padx=20, pady=10)
        
        self.tabview._segmented_button.configure(font=FUENTE_NORMAL, text_color=COLOR_TEXTO)
        
        self.tab_main = self.tabview.add("Sincronizador")
        self.tab_lisp = self.tabview.add("Instructivo LISP")
        self.tab_cmd = self.tabview.add("Instructivo CMD")

        for tab in [self.tab_main, self.tab_lisp, self.tab_cmd]:
            tab.configure(fg_color=COLOR_FONDO)

        self.setup_tab_sincronizador()
        self.setup_tab_lisp()
        self.setup_tab_cmd()

    def setup_tab_sincronizador(self):
        header_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        header_frame.pack(pady=10, fill="x", padx=10)

        try:
            logo_path = obtener_ruta_recurso("logo.ico")
            img_logo = Image.open(logo_path)
            self.logo_image = ctk.CTkImage(light_image=img_logo, dark_image=img_logo, size=(40, 40))
            lbl_logo = ctk.CTkLabel(header_frame, image=self.logo_image, text="")
            lbl_logo.pack(side="left")
        except:
            pass

        lbl_titulo = ctk.CTkLabel(header_frame, text="ESTÁNDAR SINCAL", font=FUENTE_TITULO, text_color=COLOR_TITULO)
        lbl_titulo.pack(expand=True)

        self.btn_actualizar = ctk.CTkButton(self.tab_main, 
                                           text="Instalar / Actualizar Todo", 
                                           font=FUENTE_NORMAL,
                                           fg_color=COLOR_ACENTO, 
                                           hover_color="#005BBF",
                                           text_color="white",
                                           command=self.iniciar_actualizacion_hilo)
        self.btn_actualizar.pack(pady=15)

        botones_sec_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        botones_sec_frame.pack(pady=5)

        self.btn_folder = ctk.CTkButton(botones_sec_frame, 
                                       text="Abrir carpeta local", 
                                       font=FUENTE_NORMAL, 
                                       fg_color="transparent",
                                       border_width=1,
                                       border_color=COLOR_ACENTO,
                                       text_color=COLOR_TEXTO,
                                       hover_color="#444444",
                                       command=self.abrir_carpeta_local)
        self.btn_folder.pack(side="left", padx=10)

        self.btn_forzar_path = ctk.CTkButton(botones_sec_frame, 
                                       text="Reparar / Forzar PATH", 
                                       font=FUENTE_NORMAL, 
                                       fg_color="transparent",
                                       border_width=1,
                                       border_color=COLOR_TITULO,
                                       text_color=COLOR_TITULO,
                                       hover_color="#444444",
                                       command=self.forzar_path_manual)
        self.btn_forzar_path.pack(side="left", padx=10)

        self.consola = ctk.CTkTextbox(self.tab_main, 
                                     width=750, 
                                     height=280, 
                                     font=FUENTE_CONSOLA, 
                                     fg_color="#222222", 
                                     text_color=COLOR_TEXTO,
                                     state="disabled")
        self.consola.pack(pady=15)

    def setup_tab_lisp(self):
        self.help_frame = ctk.CTkFrame(self.tab_lisp, fg_color="transparent")
        self.help_frame.pack(fill="both", expand=True)

        self.list_frame = ctk.CTkScrollableFrame(self.help_frame, 
                                                width=220, 
                                                label_text="Comandos", 
                                                label_text_color=COLOR_TITULO,
                                                fg_color="#222222")
        self.list_frame._label.configure(font=FUENTE_NORMAL)
        self.list_frame.pack(side="left", fill="y", padx=(0, 10), pady=10)

        self.content_frame = ctk.CTkFrame(self.help_frame, fg_color="#222222")
        self.content_frame.pack(side="right", fill="both", expand=True, pady=10)

        self.help_title = ctk.CTkLabel(self.content_frame, text="LISP: Selecciona un comando", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO)
        self.help_title.pack(pady=20)

        self.help_desc = ctk.CTkLabel(self.content_frame, 
                                      text="Selecciona una rutina en la lista para ver su descripción técnica.", 
                                      wraplength=450, 
                                      justify="left", 
                                      font=FUENTE_NORMAL, 
                                      text_color=COLOR_TEXTO)
        self.help_desc.pack(padx=30, pady=20)

        self.cargar_lista_tutoriales()

    def setup_tab_cmd(self):
        lbl_cmd_title = ctk.CTkLabel(self.tab_cmd, text="Guía de Procesamiento por Lotes (CMD)", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO)
        lbl_cmd_title.pack(pady=(10, 5))

        readme_text = (
            "💻 PROCESAMIENTO MASIVO DE ARCHIVOS DWG\n"
            "--------------------------------------------------\n\n"
            "Esta función permite ejecutar procesos automáticos sobre múltiples\n"
            "archivos DWG sin necesidad de abrirlos uno por uno, utilizando\n"
            "el motor de fondo de AutoCAD o ZWCAD.\n\n"
            "🛠️ COMANDOS DISPONIBLES:\n"
            "- AUDIT:        Repara y audita errores en todos los DWG.\n"
            "- PURGEALL:     Limpieza profunda de capas, bloques y estilos.\n"
            "- PUBLISH:      Genera PDFs automáticos de cada plano.\n"
            "- ZE:           Aplica 'Zoom Extents' y guarda cada archivo.\n"
            "- RC-CAPAS:     Normaliza los colores al estándar SINCAL.\n"
            "- CUSTOM-PROPS: Inyección masiva de propiedades de viñeta.\n"
            "                (Ver detalles más abajo).\n\n"
            "📖 INSTRUCCIONES DE USO GENERAL:\n"
            "1. Abra la carpeta de Windows que contiene sus archivos .dwg.\n"
            "2. Haga clic en la barra de direcciones superior.\n"
            "3. Escriba 'cmd' y presione ENTER.\n"
            "4. En la ventana negra, escriba el comando (ej: AUDIT) y ENTER.\n"
            "5. El sistema procesará cada archivo automáticamente.\n\n"
            "📝 DETALLE ESPECIAL: USO DE 'CUSTOM-PROPS'\n"
            "Este comando es interactivo. Al escribir 'CUSTOM-PROPS' y dar\n"
            "ENTER, la consola hará una pausa y le pedirá escribir los\n"
            "datos para 5 campos paramétricos de su proyecto:\n"
            "  1. Nombre_Estructura\n"
            "  2. Revision\n"
            "  3. Fecha_Rev\n"
            "  4. Fecha_Inf\n"
            "  5. No_total_planos\n\n"
            "Escriba el valor de cada uno y presione ENTER. Al terminar el\n"
            "último, el sistema inyectará esa información en TODOS los planos\n"
            "de la carpeta a la vez, actualizando las carátulas al instante.\n\n"
            "--------------------------------------------------\n"
            "Nota: El tiempo dependerá de la cantidad y peso de los planos."
        )

        self.cmd_readme = ctk.CTkTextbox(self.tab_cmd, 
                                        width=750, 
                                        height=430, 
                                        font=FUENTE_CONSOLA, 
                                        fg_color="#222222", 
                                        text_color=COLOR_TEXTO)
        self.cmd_readme.insert("0.0", readme_text)
        self.cmd_readme.configure(state="disabled")
        self.cmd_readme.pack(pady=10)

    def log(self, mensaje):
        self.consola.configure(state="normal")
        self.consola.insert("end", mensaje + "\n")
        self.consola.see("end")
        self.consola.configure(state="disabled")

    def abrir_carpeta_local(self):
        if os.path.exists(RUTA_LOCAL_APP): os.startfile(RUTA_LOCAL_APP)

    def forzar_path_manual(self):
        self.log("\n--- REPARACIÓN DE VARIABLES DE ENTORNO (PATH) ---")
        r_scripts = os.path.join(RUTA_LOCAL_APP, "scripts")
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
                try: p, _ = winreg.QueryValueEx(key, "Path")
                except: p = ""
                if r_scripts.lower() not in p.lower():
                    nuevo_path = f"{p};{r_scripts}" if p else r_scripts
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, nuevo_path)
                    self.log(f" [+] ÉXITO: Ruta inyectada en el registro.")
                else:
                    self.log(f" [OK] La ruta ya existe en el registro.")
                ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
                self.log(" [!] Cierra cualquier CMD abierto para aplicar los cambios.\n")
        except PermissionError:
            self.log(" [X] ERROR: Ejecuta SINCAL como administrador.\n")

    def cargar_lista_tutoriales(self):
        for widget in self.list_frame.winfo_children(): widget.destroy()
        ruta_json = os.path.join(RUTA_LOCAL_APP, "tutoriales.json")
        if os.path.exists(ruta_json):
            try:
                with open(ruta_json, 'r', encoding='utf-8') as f:
                    self.tutoriales = json.load(f)
                for cmd in self.tutoriales.keys():
                    btn = ctk.CTkButton(self.list_frame, text=cmd, font=FUENTE_NORMAL, 
                                        fg_color="transparent", text_color=COLOR_TEXTO,
                                        border_width=1, border_color="#444444",
                                        hover_color=COLOR_ACENTO,
                                        command=lambda c=cmd: self.mostrar_tutorial(c))
                    btn.pack(fill="x", pady=2, padx=5)
            except: pass

    def mostrar_tutorial(self, cmd):
        data = self.tutoriales.get(cmd, {})
        self.help_title.configure(text=data.get("titulo", cmd))
        self.help_desc.configure(text=data.get("descripcion", "Descripción no disponible."))

    def iniciar_actualizacion_hilo(self):
        self.btn_actualizar.configure(state="disabled", text="Sincronizando...")
        self.consola.configure(state="normal")
        self.consola.delete("1.0", "end")
        self.consola.configure(state="disabled")
        threading.Thread(target=self.motor_actualizacion).start()

    # --- NUEVA FUNCIÓN DE TELEMETRÍA ---
    def enviar_telemetria(self, version_instalada):
        if "TU_CODIGO_AQUI" in URL_WEBHOOK_SHEETS:
            return # Evita enviar si no has configurado la URL aún
        try:
            usuario_windows = os.environ.get('USERNAME', 'Desconocido')
            payload = {
                "usuario": usuario_windows,
                "version": version_instalada,
                "accion": "Actualización Completada"
            }
            # Se envía de forma silenciosa, timeout corto para no colgar la app
            requests.post(URL_WEBHOOK_SHEETS, json=payload, timeout=3)
        except:
            pass # Si no hay internet o falla, falla silenciosamente

    def motor_actualizacion(self):
        self.log("--- INICIANDO ACTUALIZACIÓN ---")
        os.makedirs(RUTA_LOCAL_APP, exist_ok=True)
        version_nube = "Desconocida"
        try:
            r = requests.get(URL_BASE_RAW + "version.json")
            data = r.json()
            version_nube = data.get("version", "Desconocida")
            archivos = data.get("archivos", [])
            for a in archivos:
                r_save = os.path.join(RUTA_LOCAL_APP, a)
                os.makedirs(os.path.dirname(r_save), exist_ok=True)
                res = requests.get(URL_BASE_RAW + a)
                with open(r_save, 'wb') as f: f.write(res.content)
                self.log(f"  > Descargado: {os.path.basename(a)}")
            
            self.generar_archivos_lisp(archivos)
            self.actualizar_rutas_registro()
            self.actualizar_variable_entorno()
            self.buscar_y_configurar_consolas()
            
            self.log(f"\n[!] PROCESO FINALIZADO. VERSIÓN INSTALADA: {version_nube}")
            self.after(0, self.cargar_lista_tutoriales)
            
            # --- ENVÍO DE DATOS A GOOGLE SHEETS ---
            self.enviar_telemetria(version_nube)
            
        except Exception as e: self.log(f"[!] Error: {e}")
        self.btn_actualizar.configure(state="normal", text="Actualizar Todo")

    def buscar_y_configurar_consolas(self):
        ruta_env = os.path.join(RUTA_LOCAL_APP, "scripts", "cad_env.bat")
        exe = None
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
                                    exe = os.path.join(path, "accoreconsole.exe")
                                    break
        except: pass
        if not exe:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\ZWSOFT\ZWCAD") as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        v = winreg.EnumKey(k, i)
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SOFTWARE\\ZWSOFT\\ZWCAD\\{v}") as vk:
                            path, _ = winreg.QueryValueEx(vk, "InstallPath")
                            if os.path.exists(os.path.join(path, "ZWCADConsole.exe")):
                                exe = os.path.join(path, "ZWCADConsole.exe")
                                break
            except: pass
        if exe:
            with open(ruta_env, 'w') as f: f.write(f'@set "CAD_CONSOLE={exe}"')
            self.log(f" [+] Consola vinculada: {os.path.basename(exe)}")

    def actualizar_rutas_registro(self):
        carpeta_ctb = os.path.join(RUTA_LOCAL_APP, "plotstyles")
        targets = [{"r": r"Software\Autodesk\AutoCAD", "v": "ACAD"}, {"r": r"Software\ZWSOFT\ZWCAD", "v": "ACAD"}]
        for t in targets:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, t["r"]) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        v_n = winreg.EnumKey(key, i)
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{t['r']}\\{v_n}") as vk:
                            for j in range(winreg.QueryInfoKey(vk)[0]):
                                p_n = winreg.EnumKey(vk, j)
                                profs = f"{t['r']}\\{v_n}\\{p_n}\\Profiles"
                                try:
                                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, profs) as pk:
                                        for k in range(winreg.QueryInfoKey(pk)[0]):
                                            p = winreg.EnumKey(pk, k)
                                            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{profs}\\{p}\\General", 0, winreg.KEY_ALL_ACCESS) as gk:
                                                try: paths, _ = winreg.QueryValueEx(gk, t["v"])
                                                except: 
                                                    paths, _ = winreg.QueryValueEx(gk, "SEARCHPATH")
                                                    t["v"] = "SEARCHPATH"
                                                if RUTA_LOCAL_APP.lower() not in paths.lower():
                                                    winreg.SetValueEx(gk, t["v"], 0, winreg.REG_SZ, f"{paths};{RUTA_LOCAL_APP}")
                                                if os.path.exists(carpeta_ctb):
                                                    try: r_ctb, _ = winreg.QueryValueEx(gk, "PrinterStyleSheetDir")
                                                    except: r_ctb = ""
                                                    if r_ctb:
                                                        r_ctb = os.path.expandvars(r_ctb)
                                                        for c in os.listdir(carpeta_ctb):
                                                            if c.lower().endswith('.ctb'): shutil.copy2(os.path.join(carpeta_ctb, c), os.path.join(r_ctb, c))
                                except: pass
            except: pass

    def actualizar_variable_entorno(self):
        r_scripts = os.path.join(RUTA_LOCAL_APP, "scripts")
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
                try: p, _ = winreg.QueryValueEx(key, "Path")
                except: p = ""
                if r_scripts.lower() not in p.lower():
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, f"{p};{r_scripts}")
                    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
        except: pass

    def generar_archivos_lisp(self, archivos):
        r_dwg = os.path.join(RUTA_LOCAL_APP, "masters", "FORMATOS ANOTATIVOS ACAD_2025.dwg").replace('\\', '\\\\')
        r_sincal = os.path.join(RUTA_LOCAL_APP, "lisps", "SINCAL.lsp")
        lisp_code = f'''(defun c:SINCAL (/ R n c a e) (vl-load-com) (setq R "{r_dwg}") (setq c (getvar "CMDECHO") a (getvar "ATTREQ")) (setvar "CMDECHO" 0) (setvar "ATTREQ" 0) (if (findfile R) (progn (setq n (vl-filename-base R)) (if (tblsearch "BLOCK" n) (command "._-INSERT" (strcat n "=" R) "_Y" "0,0,0" "1" "1" "0") (command "._-INSERT" R "0,0,0" "1" "1" "0")) (setq e (entlast)) (if e (entdel e)) (vl-cmdf "._-PURGE" "_B" n "_N") (if (tblsearch "STYLE" "RomanD") (setvar "TEXTSTYLE" "RomanD")) (if (tblsearch "DIMSTYLE" "GSG_COTAS") (command "._-DIMSTYLE" "_R" "GSG_COTAS")) (princ (strcat "\\n[OK] " R))) (alert "Error Maestro")) (setvar "ATTREQ" a) (setvar "CMDECHO" c) (princ))'''
        
        os.makedirs(os.path.dirname(r_sincal), exist_ok=True)
        with open(r_sincal, 'w', encoding='utf-8') as f: f.write(lisp_code)
        
        r_acc = os.path.join(RUTA_LOCAL_APP, "acaddoc.lsp")
        with open(r_acc, 'w', encoding='utf-8') as f:
            r_sincal_escaped = r_sincal.replace("\\", "\\\\")
            f.write(f'(load "{r_sincal_escaped}")\n')
            for a in archivos:
                if a.endswith('.lsp') and "SINCAL.lsp" not in a:
                    r = os.path.join(RUTA_LOCAL_APP, a).replace('\\', '\\\\')
                    f.write(f'(if (findfile "{r}") (load "{r}"))\n')

if __name__ == "__main__":
    app = ActualizadorCAD()
    app.mainloop()