import os
import sys
import json
import requests
import winreg
import threading
import ctypes
import shutil
import customtkinter as ctk

# --- CONFIGURACIÓN ---
USUARIO_GITHUB = "drossull" 
REPO_GITHUB = "sincal-exe"
RAMA = "main" 
URL_BASE_RAW = f"https://raw.githubusercontent.com/{USUARIO_GITHUB}/{REPO_GITHUB}/{RAMA}/"
RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estándar SINCAL") 

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

def obtener_ruta_recurso(ruta_relativa):
    try:
        ruta_base = sys._MEIPASS
    except Exception:
        ruta_base = os.path.abspath(".")
    return os.path.join(ruta_base, ruta_relativa)

class ActualizadorCAD(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SINCAL - Suite de Herramientas v1.0.9")
        self.geometry("850x550")
        self.resizable(False, False)

        try:
            self.iconbitmap(obtener_ruta_recurso("logo.ico"))
        except:
            pass

        self.tutoriales = {}

        # --- SISTEMA DE PESTAÑAS ---
        self.tabview = ctk.CTkTabview(self, width=810, height=510)
        self.tabview.pack(padx=20, pady=10)
        
        self.tab_main = self.tabview.add("Sincronizador")
        self.tab_help = self.tabview.add("Instructivo")

        self.setup_tab_sincronizador()
        self.setup_tab_instructivo()

    def setup_tab_sincronizador(self):
        lbl = ctk.CTkLabel(self.tab_main, text="Estándar SINCAL", font=("Consolas", 24, "bold"))
        lbl.pack(pady=10)

        self.btn_actualizar = ctk.CTkButton(self.tab_main, text="Instalar / Actualizar Todo", font=("Consolas", 14, "bold"),
                                           fg_color="transparent", border_width=2, command=self.iniciar_actualizacion_hilo)
        self.btn_actualizar.pack(pady=10)

        self.btn_folder = ctk.CTkButton(self.tab_main, text="Abrir carpeta local", command=self.abrir_carpeta_local)
        self.btn_folder.pack(pady=5)

        self.consola = ctk.CTkTextbox(self.tab_main, width=750, height=280, font=("Consolas", 12), state="disabled")
        self.consola.pack(pady=10)

    def setup_tab_instructivo(self):
        self.help_frame = ctk.CTkFrame(self.tab_help, fg_color="transparent")
        self.help_frame.pack(fill="both", expand=True)

        self.list_frame = ctk.CTkScrollableFrame(self.help_frame, width=200, label_text="Comandos Disponibles")
        self.list_frame.pack(side="left", fill="y", padx=(0, 10), pady=10)

        self.content_frame = ctk.CTkFrame(self.help_frame)
        self.content_frame.pack(side="right", fill="both", expand=True, pady=10)

        self.help_title = ctk.CTkLabel(self.content_frame, text="Bienvenido al Instructivo", font=("Consolas", 18, "bold"))
        self.help_title.pack(pady=20)

        self.help_desc = ctk.CTkLabel(self.content_frame, text="Selecciona un comando en la lista de la izquierda para ver su descripción y modo de uso.", 
                                      wraplength=450, justify="left", font=("Consolas", 14))
        self.help_desc.pack(padx=30, pady=20)

        self.cargar_lista_tutoriales()

    def log(self, mensaje):
        self.consola.configure(state="normal")
        self.consola.insert("end", mensaje + "\n")
        self.consola.see("end")
        self.consola.configure(state="disabled")

    def abrir_carpeta_local(self):
        if os.path.exists(RUTA_LOCAL_APP): os.startfile(RUTA_LOCAL_APP)

    def cargar_lista_tutoriales(self):
        for widget in self.list_frame.winfo_children(): widget.destroy()
        ruta_json = os.path.join(RUTA_LOCAL_APP, "tutoriales.json")
        if os.path.exists(ruta_json):
            try:
                with open(ruta_json, 'r', encoding='utf-8') as f:
                    self.tutoriales = json.load(f)
                for cmd in self.tutoriales.keys():
                    btn = ctk.CTkButton(self.list_frame, text=cmd, fg_color="transparent", border_width=1,
                                        command=lambda c=cmd: self.mostrar_tutorial(c))
                    btn.pack(fill="x", pady=2, padx=5)
            except: pass

    def mostrar_tutorial(self, cmd):
        data = self.tutoriales.get(cmd, {})
        self.help_title.configure(text=data.get("titulo", cmd))
        self.help_desc.configure(text=data.get("descripcion", "Descripción no disponible."))

    # --- MOTOR DE ACTUALIZACIÓN ---
    def iniciar_actualizacion_hilo(self):
        self.btn_actualizar.configure(state="disabled", text="Sincronizando...")
        self.consola.configure(state="normal")
        self.consola.delete("1.0", "end")
        self.consola.configure(state="disabled")
        threading.Thread(target=self.motor_actualizacion).start()

    def motor_actualizacion(self):
        self.log("--- INICIANDO ACTUALIZACIÓN ---")
        os.makedirs(RUTA_LOCAL_APP, exist_ok=True)
        try:
            r = requests.get(URL_BASE_RAW + "version.json")
            data = r.json()
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
            
            self.log("\n[!] PROCESO FINALIZADO.")
            self.after(0, self.cargar_lista_tutoriales)
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
                p, _ = winreg.QueryValueEx(key, "Path")
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
            # AQUÍ ESTÁ LA CORRECCIÓN APLICADA DE NUEVO
            r_sincal_escaped = r_sincal.replace("\\", "\\\\")
            f.write(f'(load "{r_sincal_escaped}")\n')
            for a in archivos:
                if a.endswith('.lsp') and "SINCAL.lsp" not in a:
                    r = os.path.join(RUTA_LOCAL_APP, a).replace('\\', '\\\\')
                    f.write(f'(if (findfile "{r}") (load "{r}"))\n')

if __name__ == "__main__":
    app = ActualizadorCAD()
    app.mainloop()