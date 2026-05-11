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
import win32com.client
import pythoncom

# --- 1. FORZAR MODO ADMINISTRADOR ---
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
RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estandar SINCAL") 
URL_WEBHOOK_SHEETS = "https://script.google.com/macros/s/AKfycbywJwskXQrAhNYHV559ngE5WAPa-bhvrfgcYg0ej_WDfxQMP5vmT31b66mEPqeFCchaPQ/exec"

# Colores SINCAL
COLOR_FONDO = "#2B2B2B"      
COLOR_TITULO = "#FFBF00"     
COLOR_TEXTO = "#CCCCCC"      
COLOR_ACENTO = "#007FFF"     
COLOR_MENU_HOVER = "#404040"

# Fuentes Restauradas a Consolas
FUENTE_TITULO = ("Consolas", 24, "bold")
FUENTE_SUBTITULO = ("Consolas", 18, "bold")
FUENTE_MENU = ("Consolas", 13)
FUENTE_NORMAL = ("Consolas", 12)
FUENTE_CONSOLA = ("Consolas", 11)

ctk.set_appearance_mode("dark") 

# --- FUNCIÓN PARA EL ÍCONO ---
def obtener_ruta_recurso(ruta_relativa):
    try:
        # PyInstaller crea una carpeta temporal _MEIPASS
        ruta_base = sys._MEIPASS
    except Exception:
        ruta_base = os.path.abspath(".")
    return os.path.join(ruta_base, ruta_relativa)

class ActualizadorCAD(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SINCAL - Suite de Herramientas Professional")
        self.geometry("1000x750")
        self.configure(fg_color=COLOR_FONDO)
        
        # Cargar Ícono Oficial
        try:
            self.iconbitmap(obtener_ruta_recurso("logo.ico"))
        except: pass
        
        self.version_local_actual = "v1.4.8"
        self.tutoriales = {}
        self.cad_exe_path = None
        self.es_zwcad = False
        self.cancelar_comando_vivo = False  # <-- BANDERA DE CANCELACIÓN

        # Contenedor Principal
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_FONDO, corner_radius=0)
        self.main_scroll.pack(fill="both", expand=True)

        # Tabview
        self.tabview = ctk.CTkTabview(self.main_scroll, width=950, height=680, fg_color=COLOR_FONDO,
                                      segmented_button_selected_color=COLOR_ACENTO)
        self.tabview.pack(padx=20, pady=10)
        
        self.tab_main = self.tabview.add("Sincronizador")
        self.tab_docs = self.tabview.add("Documentación")

        self.setup_tab_sincronizador()
        self.setup_tab_docs()

        threading.Thread(target=self.cargar_info_github, daemon=True).start()
        threading.Thread(target=self.loop_verificador_actualizaciones, daemon=True).start()

    def setup_tab_sincronizador(self):
        lbl_titulo = ctk.CTkLabel(self.tab_main, text="ESTÁNDAR SINCAL", font=FUENTE_TITULO, text_color=COLOR_TITULO)
        lbl_titulo.pack(pady=20)

        # Botón Actualizar (Cuadrado, Contorno, Sin fondo)
        self.btn_actualizar = ctk.CTkButton(self.tab_main, text="Instalar / Actualizar Todo", font=FUENTE_SUBTITULO,
                                           fg_color="transparent", border_width=2, border_color=COLOR_ACENTO,
                                           corner_radius=0, hover_color="#444444", text_color=COLOR_TEXTO,
                                           height=45, command=self.iniciar_actualizacion_hilo)
        self.btn_actualizar.pack(pady=10)

        # Restauración de Botones Secundarios
        botones_sec_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        botones_sec_frame.pack(pady=5)

        self.btn_folder = ctk.CTkButton(botones_sec_frame, text="Abrir carpeta local", font=FUENTE_NORMAL, 
                                       fg_color="transparent", border_width=1, border_color=COLOR_ACENTO, corner_radius=0,
                                       text_color=COLOR_TEXTO, hover_color="#444444", command=self.abrir_carpeta_local)
        self.btn_folder.pack(side="left", padx=10)

        self.btn_forzar_path = ctk.CTkButton(botones_sec_frame, text="Reparar / Forzar PATH", font=FUENTE_NORMAL, 
                                       fg_color="transparent", border_width=1, border_color=COLOR_TITULO, corner_radius=0,
                                       text_color=COLOR_TITULO, hover_color="#444444", command=self.forzar_path_manual)
        self.btn_forzar_path.pack(side="left", padx=10)

        self.consola = ctk.CTkTextbox(self.tab_main, width=850, height=180, font=FUENTE_CONSOLA, 
                                     fg_color="#1E1E1E", text_color=COLOR_TEXTO, state="disabled")
        self.consola.pack(pady=15)

        # --- CONSOLA EN VIVO PARA ARCHIVOS ABIERTOS ---
        self.frame_live = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        self.frame_live.pack(fill="x", padx=40, pady=(5, 10))
        
        ctk.CTkLabel(self.frame_live, text="Ejecutar en planos abiertos:", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(side="left")
        
        self.entrada_comando = ctk.CTkEntry(self.frame_live, font=FUENTE_NORMAL, width=250, placeholder_text="Ej: ZE, _QSAVE", corner_radius=0)
        self.entrada_comando.pack(side="left", padx=10)
        
        self.btn_enviar_cmd = ctk.CTkButton(self.frame_live, text="Enviar", font=FUENTE_NORMAL, 
                                            fg_color="transparent", border_width=1, border_color=COLOR_ACENTO, corner_radius=0,
                                            hover_color="#444444", text_color=COLOR_TEXTO, width=80,
                                            command=self.enviar_comando_en_vivo)
        self.btn_enviar_cmd.pack(side="left", padx=(0, 10))
        
        # --- NUEVO BOTÓN CANCELAR ---
        self.btn_cancelar_cmd = ctk.CTkButton(self.frame_live, text="Cancelar", font=FUENTE_NORMAL, 
                                              fg_color="#D9534F", hover_color="#C9302C", width=80, corner_radius=0,
                                              state="disabled", command=self.detener_comando_en_vivo)
        self.btn_cancelar_cmd.pack(side="left")

        # Historial de cambios
        self.frame_updates = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        self.frame_updates.pack(fill="x", padx=40)
        ctk.CTkLabel(self.frame_updates, text="Historial de cambios (Últimos 10)", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(anchor="w")
        self.txt_updates = ctk.CTkTextbox(self.frame_updates, width=850, height=130, font=FUENTE_NORMAL, fg_color="#1E1E1E", state="disabled")
        self.txt_updates.pack(pady=5)

    def setup_tab_docs(self):
        self.wiki_master = ctk.CTkFrame(self.tab_docs, fg_color="transparent")
        self.wiki_master.pack(fill="both", expand=True, padx=10, pady=10)

        self.menu_container = ctk.CTkFrame(self.wiki_master, width=220, fg_color="transparent")
        self.menu_container.pack(side="left", fill="y", padx=(0, 5))

        self.linea_div = ctk.CTkFrame(self.wiki_master, width=1, fg_color="#555555")
        self.linea_div.pack(side="left", fill="y", padx=15)

        self.content_container = ctk.CTkFrame(self.wiki_master, fg_color="transparent")
        self.content_container.pack(side="right", fill="both", expand=True)

        self.lbl_wiki_title = ctk.CTkLabel(self.content_container, text="Seleccione un tema", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO, justify="left")
        self.lbl_wiki_title.pack(anchor="w", padx=20, pady=(10, 0))

        self.txt_wiki_content = ctk.CTkTextbox(self.content_container, font=FUENTE_NORMAL, fg_color="transparent", 
                                               text_color=COLOR_TEXTO, wrap="word", border_width=0)
        self.txt_wiki_content.pack(fill="both", expand=True, padx=20, pady=10)

        self.renderizar_menu_wiki()

    def renderizar_menu_wiki(self):
        for child in self.menu_container.winfo_children(): child.destroy()

        def crear_link(parent, texto, comando):
            lbl = ctk.CTkLabel(parent, text=texto, font=FUENTE_MENU, text_color=COLOR_TEXTO, 
                               cursor="hand2", anchor="e")
            lbl.pack(fill="x", pady=8, padx=10)
            lbl.bind("<Enter>", lambda e: lbl.configure(text_color=COLOR_TITULO))
            lbl.bind("<Leave>", lambda e: lbl.configure(text_color=COLOR_TEXTO))
            lbl.bind("<Button-1>", lambda e: comando())
            return lbl

        crear_link(self.menu_container, "README", self.mostrar_readme)
        crear_link(self.menu_container, "INICIO AUTOMÁTICO", self.mostrar_inicio_auto)
        crear_link(self.menu_container, "COMANDOS LISP", self.mostrar_comandos_lisp)
        crear_link(self.menu_container, "PROCESAMIENTO MASIVO", self.mostrar_procesamiento_lote)

    def mostrar_texto_wiki(self, titulo, contenido):
        self.lbl_wiki_title.configure(text=titulo.upper())
        self.txt_wiki_content.configure(state="normal")
        self.txt_wiki_content.delete("1.0", "end")
        self.txt_wiki_content.insert("0.0", contenido)
        self.txt_wiki_content.configure(state="disabled")

    def mostrar_readme(self):
        ruta = os.path.join(RUTA_LOCAL_APP, "README.md")
        contenido = open(ruta, 'r', encoding='utf-8').read() if os.path.exists(ruta) else "README no descargado."
        self.mostrar_texto_wiki("Guía de Inicio", contenido)

    def mostrar_inicio_auto(self):
        self.cargar_datos_tutoriales()
        texto = ""
        for k in ["AutoCrearPropiedad", "AUTO-DYNMODE", "Atajos de Color"]:
            item = self.tutoriales.get(k, {})
            texto += f"■ {item.get('titulo', k)}\n{item.get('descripcion', '')}\n\n"
        self.mostrar_texto_wiki("Archivos de Inicio Automático", texto)

    def mostrar_comandos_lisp(self):
        self.cargar_datos_tutoriales()
        texto = "Ejecute estos comandos directamente en la barra de AutoCAD/ZWCAD:\n\n"
        excluir = ["AutoCrearPropiedad", "AUTO-DYNMODE", "Atajos de Color"]
        for k, v in self.tutoriales.items():
            if k not in excluir:
                t = v.get('titulo', k)
                if t.lower().startswith("comando:"):
                    t = t[8:].strip()
                if t.startswith(k):
                    t = t[len(k):].strip()
                if t.startswith("-") or t.startswith(":"):
                    t = t[1:].strip()
                if t.startswith("("):
                    t = t.strip()
                texto += f"► COMANDO {k}: {t}\n{v.get('descripcion', '')}\n\n"
        self.mostrar_texto_wiki("Diccionario de Comandos", texto)

    def mostrar_procesamiento_lote(self):
        guia = (
            "HERRAMIENTAS DE PROCESAMIENTO MASIVO (CMD/PWSH)\n\n"
            "Estas herramientas permiten trabajar sobre carpetas completas de planos sin tener que abrir AutoCAD o ZWCAD manualmente. Utilizan la consola de fondo (PowerShell) para procesar a alta velocidad.\n\n"
            "CÓMO USAR:\n"
            "1. Abra la carpeta de Windows donde se encuentran sus archivos .dwg.\n"
            "2. Haga clic en la barra de direcciones superior de la carpeta.\n"
            "3. Borre la ruta, escriba 'cmd' y presione Enter. Se abrirá una consola negra.\n"
            "4. Escriba el nombre del comando deseado (ver lista abajo) y presione Enter.\n\n"
            "COMANDOS DISPONIBLES:\n\n"
            "► AUDIT\n"
            "Reparación de base de datos. Abre cada archivo en segundo plano y ejecuta el comando de auditoría para encontrar y solucionar errores internos del dibujo que puedan causar cierres inesperados.\n\n"
            "► BV\n"
            "Bloqueo masivo de Viewports. Escanea todos los layouts de los planos de la carpeta y bloquea (Display Locked = Yes) todas las ventanas gráficas para evitar cambios accidentales de escala.\n\n"
            "► DL2\n"
            "Eliminar Layout 2. Borra automáticamente la pestaña 'Layout2' sobrante en todos los dibujos, dejando el archivo limpio y listo para publicación.\n\n"
            "► PAGESETUP-A1\n"
            "Configuración de página masiva. Asigna a todos los layouts el tamaño de papel ISO A1 (841x594), la impresora PDF de alta calidad, escala 1:1, la plumilla oficial SINCAL_A1 y centra el trazado automáticamente.\n\n"
            "► PUBLISH\n"
            "Publicación en Lote. Genera archivos PDF de alta calidad para todos los planos DWG de la carpeta, utilizando la configuración de página actual, y los guarda en el mismo directorio sin requerir intervención manual.\n\n"
            "► PURGEALL\n"
            "Limpieza profunda. Ejecuta de forma intensiva la purga de bloques, capas, tipos de línea, estilos no utilizados y aplicaciones registradas sobrantes para reducir drásticamente el peso de todos los archivos.\n\n"
            "► ZE\n"
            "Zoom Extents. Realiza un ajuste de ventana general (Zoom Extents) en todos los planos de la carpeta y los guarda. Muy útil para que la vista previa de los archivos y la visualización inicial al abrirlos sea la correcta."
        )
        self.mostrar_texto_wiki("Procesamiento Masivo", guia)

    def cargar_datos_tutoriales(self):
        ruta_json = os.path.join(RUTA_LOCAL_APP, "tutoriales.json")
        if os.path.exists(ruta_json):
            with open(ruta_json, 'r', encoding='utf-8') as f:
                self.tutoriales = json.load(f)

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

    # --- LÓGICA CONSOLA EN VIVO (COM) ---
    def detener_comando_en_vivo(self):
        self.cancelar_comando_vivo = True
        self.btn_cancelar_cmd.configure(state="disabled", text="Deteniendo...")

    def enviar_comando_en_vivo(self):
        comando_crudo = self.entrada_comando.get()
        if not comando_crudo:
            return
            
        comando = comando_crudo.strip() + "\n"
        
        self.cancelar_comando_vivo = False
        self.btn_enviar_cmd.configure(state="disabled", text="Enviando...")
        self.btn_cancelar_cmd.configure(state="normal", text="Cancelar")
        
        threading.Thread(target=self._hilo_comando_en_vivo, args=(comando,), daemon=True).start()

    def _hilo_comando_en_vivo(self, comando):
        pythoncom.CoInitialize() 
        try:
            app = None
            try:
                app = win32com.client.GetActiveObject("ZWCAD.Application")
                self.log(f"\n--- CONECTADO A ZWCAD EN VIVO ---")
            except:
                try:
                    app = win32com.client.GetActiveObject("AutoCAD.Application")
                    self.log(f"\n--- CONECTADO A AUTOCAD EN VIVO ---")
                except:
                    try:
                        app = win32com.client.GetActiveObject("AutoCAD.Application.25")
                        self.log(f"\n--- CONECTADO A AUTOCAD 2025 EN VIVO ---")
                    except:
                        self.log("\n[X] Error: No se detecta CAD abierto.")
                        self.log(" [!] NOTA: AutoCAD/ZWCAD debe estar abierto como Administrador.")
                        return

            documentos = app.Documents
            total = documentos.Count
            
            if total == 0:
                self.log(" [!] No hay ningún plano abierto en este momento.")
                return

            self.log(f" Ejecutando comando en {total} pestañas...")
            
            # TRUCO PRO: \x03 es el código ASCII para la tecla ESC.
            # Enviamos dos ESC antes del comando para limpiar la línea de comandos de AutoCAD.
            comando_seguro = "\x03\x03" + comando

            for i in range(total):
                if self.cancelar_comando_vivo:
                    self.log(" [!] PROCESO ABORTADO POR EL USUARIO.")
                    break
                
                try:
                    doc = documentos.Item(i)
                except:
                    continue 

                try:
                    # 1. Comprobación anti-redundancia: Solo activar si NO es la pestaña actual
                    if app.ActiveDocument.Name != doc.Name:
                        doc.Activate()
                        time.sleep(0.1) 
                    
                    # 2. Enviar el comando seguro (Doble ESC + Tu Comando + Enter)
                    doc.SendCommand(comando_seguro)
                    self.log(f"  > Aplicado en: {doc.Name}")
                    
                except Exception as e:
                    # 3. Reintento forzado por si la interfaz gráfica de ZWCAD tuvo lag
                    try:
                        time.sleep(0.5)
                        app.ActiveDocument = doc # Método alternativo de activación COM
                        doc.SendCommand(comando_seguro)
                        self.log(f"  > Aplicado en: {doc.Name} (Vía reintento)")
                    except Exception as ex:
                        self.log(f"  > [X] Omitido '{doc.Name}': Hay una ventana emergente bloqueando el CAD.")
                
                time.sleep(0.1) 

            if not self.cancelar_comando_vivo:
                self.log(" Proceso en vivo finalizado.")
                
            self.entrada_comando.delete(0, 'end')

        except Exception as e:
            self.log(f"\n[X] Fallo crítico en la comunicación COM: {e}")
        finally:
            self.btn_enviar_cmd.configure(state="normal", text="Ejecutar")
            self.btn_cancelar_cmd.configure(state="disabled", text="Cancelar")
            pythoncom.CoUninitialize()

    # --- LÓGICA CORE RESTAURADA ---
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
            r = requests.get(URL_BASE_RAW + "version.json")
            data = r.json()
            version_nube = data.get("version", "v1.0.0")
            archivos = data.get("archivos", [])
            archivos.append("README.md")

            for a in archivos:
                r_save = os.path.join(RUTA_LOCAL_APP, a)
                os.makedirs(os.path.dirname(r_save), exist_ok=True)
                res = requests.get(URL_BASE_RAW + a)
                if res.status_code == 200:
                    with open(r_save, 'wb') as f: f.write(res.content)
                    self.log(f"  > Descargado: {os.path.basename(a)}")
            
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
            self.renderizar_menu_wiki()
            
        except Exception as e: 
            self.log(f"[!] Error durante la descarga: {e}")
        
        self.btn_actualizar.configure(state="normal", text="Instalar / Actualizar Todo")

    def buscar_y_configurar_consolas(self):
        ruta_env = os.path.join(RUTA_LOCAL_APP, "scripts", "cad_env.bat")
        ruta_wrapper = os.path.join(RUTA_LOCAL_APP, "scripts", "cad_wrapper.bat")
        self.cad_exe_path = None
        self.es_zwcad = False
        
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

    def cargar_info_github(self):
        try:
            url_api = f"https://api.github.com/repos/{USUARIO_GITHUB}/{REPO_GITHUB}/commits"
            r = requests.get(url_api, params={"per_page": 10}, timeout=5)
            if r.status_code == 200:
                self.txt_updates.configure(state="normal")
                self.txt_updates.delete("1.0", "end")
                for c in r.json():
                    self.txt_updates.insert("end", f"• {c['commit']['author']['date'][:10]} : {c['commit']['message']}\n")
                self.txt_updates.configure(state="disabled")
        except: pass

    def loop_verificador_actualizaciones(self):
        while True:
            time.sleep(3600)
            try:
                r = requests.get(URL_BASE_RAW + "version.json", timeout=5)
                if r.json().get("version") != self.version_local_actual:
                    self.mostrar_popup_actualizacion(r.json().get("version"))
            except: pass

    def mostrar_popup_actualizacion(self, v):
        if messagebox.askyesno("Actualización", f"Nueva versión disponible: {v}\n¿Actualizar ahora?"):
            self.iniciar_actualizacion_hilo()

if __name__ == "__main__":
    app = ActualizadorCAD()
    app.mainloop()