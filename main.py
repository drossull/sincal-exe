import os
import sys
import json
import requests
import winreg
import threading
import customtkinter as ctk

# --- CONFIGURACIÓN ---
USUARIO_GITHUB = "drossull" 
REPO_GITHUB = "sincal-exe"
RAMA = "main" 

URL_BASE_RAW = f"https://raw.githubusercontent.com/{USUARIO_GITHUB}/{REPO_GITHUB}/{RAMA}/"
# Nombre de carpeta actualizado a Estándar SINCAL
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
        self.title("SINCAL - Instalador de Estándares")
        self.geometry("550x500") 
        self.resizable(False, False)

        try:
            self.iconbitmap(obtener_ruta_recurso("logo.ico"))
        except:
            pass

        fuente_titulo = ("Consolas", 20, "bold")
        fuente_texto = ("Consolas", 12)
        fuente_boton = ("Consolas", 14, "bold")

        self.lbl_titulo = ctk.CTkLabel(self, text="Estándar SINCAL", font=fuente_titulo)
        self.lbl_titulo.pack(pady=(20, 5))

        self.lbl_desc = ctk.CTkLabel(self, text="Sincronización de Lisps y Formatos Maestros", font=fuente_texto)
        self.lbl_desc.pack(pady=(0, 15))

        self.btn_actualizar = ctk.CTkButton(
            self, text="Instalar / Actualizar", font=fuente_boton,
            fg_color="transparent", border_width=2,
            text_color=("#1F6AA5", "#569BCC"), border_color=("#1F6AA5", "#569BCC"),
            command=self.iniciar_actualizacion_hilo
        )
        self.btn_actualizar.pack(pady=10, ipady=5)

        self.btn_abrir_ruta = ctk.CTkButton(
            self, text="Ver archivos locales", font=fuente_texto,
            fg_color="transparent", text_color=("gray30", "gray70"),
            command=self.abrir_carpeta_local
        )
        self.btn_abrir_ruta.pack(pady=(0, 10))

        self.consola = ctk.CTkTextbox(self, width=500, height=220, font=fuente_texto, state="disabled")
        self.consola.pack(pady=5)

    def log(self, mensaje):
        self.consola.configure(state="normal") 
        self.consola.insert("end", mensaje + "\n")
        self.consola.see("end") 
        self.consola.configure(state="disabled") 

    def abrir_carpeta_local(self):
        if os.path.exists(RUTA_LOCAL_APP):
            os.startfile(RUTA_LOCAL_APP)
        else:
            self.log("[!] Carpeta no encontrada.")

    def iniciar_actualizacion_hilo(self):
        self.btn_actualizar.configure(state="disabled", text="Sincronizando...")
        self.consola.configure(state="normal")
        self.consola.delete("1.0", "end") 
        self.consola.configure(state="disabled")
        threading.Thread(target=self.motor_actualizacion).start()

    def actualizar_rutas_registro(self):
        self.log("[-] Configurando rutas de soporte en CAD...")
        targets = [
            {"n": "AutoCAD", "r": r"Software\Autodesk\AutoCAD", "v": "ACAD"},
            {"n": "ZWCAD", "r": r"Software\ZWSOFT\ZWCAD", "v": "ACAD"}
        ]
        for t in targets:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, t["r"]) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        v_name = winreg.EnumKey(key, i)
                        v_path = f"{t['r']}\\{v_name}"
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, v_path) as vk:
                            for j in range(winreg.QueryInfoKey(vk)[0]):
                                p_name = winreg.EnumKey(vk, j)
                                profiles = f"{v_path}\\{p_name}\\Profiles"
                                try:
                                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, profiles) as pk:
                                        for k in range(winreg.QueryInfoKey(pk)[0]):
                                            prof = winreg.EnumKey(pk, k)
                                            gen = f"{profiles}\\{prof}\\General"
                                            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, gen, 0, winreg.KEY_ALL_ACCESS) as gk:
                                                try:
                                                    paths, _ = winreg.QueryValueEx(gk, t["v"])
                                                except:
                                                    paths, _ = winreg.QueryValueEx(gk, "SEARCHPATH")
                                                    t["v"] = "SEARCHPATH"
                                                
                                                if RUTA_LOCAL_APP.lower() not in paths.lower():
                                                    winreg.SetValueEx(gk, t["v"], 0, winreg.REG_SZ, f"{paths};{RUTA_LOCAL_APP}")
                                                    self.log(f" [+] Vinculado: {t['n']} ({prof})")
                                except: pass
            except: pass

    def generar_archivos_lisp(self, archivos):
        """Genera el cargador y el comando SINCAL con rutas dinámicas"""
        self.log("[-] Generando cargadores dinámicos...")
        
        # 1. Generar SINCAL.lsp dinámico
        ruta_dwg_maestro = os.path.join(RUTA_LOCAL_APP, "masters", "FORMATOS ANOTATIVOS ACAD_2025.dwg").replace('\\', '\\\\')
        ruta_sincal_lsp = os.path.join(RUTA_LOCAL_APP, "lisps", "SINCAL.lsp")
        
        codigo_sincal = f'''
(defun c:SINCAL (/ RutaArchivoMaestro nombreBloque cmdecho_ini attreq_ini entUltima)
  (vl-load-com) 
  (setq RutaArchivoMaestro "{ruta_dwg_maestro}")
  (setq cmdecho_ini (getvar "CMDECHO"))
  (setq attreq_ini (getvar "ATTREQ"))
  (setvar "CMDECHO" 0)
  (setvar "ATTREQ" 0) 
  (princ "\\n[SINCAL] Buscando archivo de normas...")
  (if (findfile RutaArchivoMaestro)
    (progn
      (setq nombreBloque (vl-filename-base RutaArchivoMaestro))
      (if (tblsearch "BLOCK" nombreBloque)
        (command "._-INSERT" (strcat nombreBloque "=" RutaArchivoMaestro) "_Y" "0,0,0" "1" "1" "0")
        (command "._-INSERT" RutaArchivoMaestro "0,0,0" "1" "1" "0")
      )
      (setq entUltima (entlast))
      (if entUltima (entdel entUltima))
      (vl-cmdf "._-PURGE" "_B" nombreBloque "_N")
      (if (tblsearch "STYLE" "RomanD") (setvar "TEXTSTYLE" "RomanD"))
      (if (tblsearch "DIMSTYLE" "GSG_COTAS") (command "._-DIMSTYLE" "_R" "GSG_COTAS"))
      (princ (strcat "\\n[EXITO] Estándares importados desde: " RutaArchivoMaestro))
    )
    (alert (strcat "ERROR: No se encuentra el maestro en:\\n" RutaArchivoMaestro))
  )
  (setvar "ATTREQ" attreq_ini)
  (setvar "CMDECHO" cmdecho_ini)
  (princ)
)
(princ "\\nComando SINCAL cargado correctamente.") (princ)
'''
        with open(ruta_sincal_lsp, 'w', encoding='utf-8') as f:
            f.write(codigo_sincal)

        # 2. Generar acaddoc.lsp (Cargador de todo)
        ruta_acaddoc = os.path.join(RUTA_LOCAL_APP, "acaddoc.lsp")
        with open(ruta_acaddoc, 'w', encoding='utf-8') as f:
            f.write(';; CARGADOR ESTANDAR SINCAL\n(princ "\\nCargando Estándar SINCAL...")\n')
            
            # SOLUCIÓN DEL ERROR DE SINTAXIS (Variable intermedia)
            ruta_sincal_escapada = ruta_sincal_lsp.replace('\\', '\\\\')
            f.write(f'(load "{ruta_sincal_escapada}")\n')
            
            # Cargar el resto de archivos
            for a in archivos:
                if a.endswith('.lsp') and "SINCAL.lsp" not in a:
                    r = os.path.join(RUTA_LOCAL_APP, a).replace('\\', '\\\\')
                    f.write(f'(if (findfile "{r}") (load "{r}"))\n')
            f.write('(princ "\\n[OK] Todos los Lisps de SINCAL cargados.")(princ)\n')

    def motor_actualizacion(self):
        self.log("--- INICIANDO ACTUALIZACIÓN ---")
        os.makedirs(RUTA_LOCAL_APP, exist_ok=True)
        
        try:
            r = requests.get(URL_BASE_RAW + "version.json")
            r.raise_for_status()
            data = r.json()
            v_nube = data.get("version")
            archivos = data.get("archivos", [])
        except Exception as e:
            self.log(f"[!] Error de red: {e}")
            self.btn_actualizar.configure(state="normal", text="Reintentar")
            return

        # Sincronizar archivos
        self.log(f"[-] Versión nube: {v_nube}. Descargando...")
        for a in archivos:
            r_save = os.path.join(RUTA_LOCAL_APP, a)
            os.makedirs(os.path.dirname(r_save), exist_ok=True)
            res = requests.get(URL_BASE_RAW + a)
            if res.status_code == 200:
                with open(r_save, 'wb') as f: f.write(res.content)
                self.log(f"  > {os.path.basename(a)}")

        # Configuración final
        self.generar_archivos_lisp(archivos)
        self.actualizar_rutas_registro()
        
        self.log("\n[!] PROCESO FINALIZADO.")
        self.log("Reinicia AutoCAD para aplicar cambios.")
        self.btn_actualizar.configure(state="normal", text="Sincronizado")

if __name__ == "__main__":
    app = ActualizadorCAD()
    app.mainloop()