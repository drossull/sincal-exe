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
from PIL import Image

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

        self.tab_main = self.tabview.add("Sincronizador")
        self.tab_renombrado = self.tabview.add("Renombrado Avanzado")
        self.tab_armaduras = self.tabview.add("Módulo Estructural")
        self.tab_docs = self.tabview.add("Documentación")

        self.setup_tab_sincronizador()
        self.setup_tab_renombrado()
        self.setup_tab_armaduras()
        self.setup_tab_docs()

        if getattr(sys, 'frozen', False): self.configurar_inicio_con_windows()
        threading.Thread(target=self.cargar_info_github, daemon=True).start()
        threading.Thread(target=self.loop_verificador_actualizaciones_silencioso, daemon=True).start()

    # ==========================================================
    # LÓGICA DE WINDOWS (SYSTEM TRAY / AUTOSTART)
    # ==========================================================
    def ocultar_a_bandeja(self):
        self.withdraw()
        if not self.tray_activo:
            try: icono = Image.open(obtener_ruta_recurso("logo.ico"))
            except: icono = Image.new('RGB', (64, 64), color=(43, 43, 43))
            self.tray = pystray.Icon("SINCAL", icono, "SINCAL Suite", menu=pystray.Menu(
                pystray.MenuItem("Abrir SINCAL", lambda icon, item: [icon.stop(), setattr(self, 'tray_activo', False), self.deiconify()], default=True),
                pystray.MenuItem("Cerrar por completo", lambda icon, item: [icon.stop(), os._exit(0)])
            ))
            self.tray_activo = True
            threading.Thread(target=self.tray.run, daemon=True).start()

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

    # ==========================================================
    # PESTAÑA: MÓDULO ESTRUCTURAL (ARMADURAS PARAMÉTRICAS)
    # ==========================================================
    def setup_tab_armaduras(self):
        frame_top = ctk.CTkFrame(self.tab_armaduras, fg_color="#1E1E1E", border_width=1, border_color="#444444", corner_radius=0)
        frame_top.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_top, text="DICCIONARIO DE DATOS (ESTRIBOS)", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(side="left", padx=15, pady=15)
        ctk.CTkButton(frame_top, text="📁 Cargar JSON de Proyecto", font=FUENTE_NORMAL, fg_color="#444444", hover_color="#555555", corner_radius=0, command=self.cargar_json_bim).pack(side="right", padx=15, pady=15)

        self.tab_estribo = ctk.CTkTabview(self.tab_armaduras, width=800, height=420, fg_color="#1E1E1E", segmented_button_selected_color=COLOR_ACENTO)
        self.tab_estribo.pack(padx=20, pady=5, fill="x")
        self.tab_estribo._segmented_button.configure(font=FUENTE_NORMAL)

        tab_zap, tab_muros, tab_consola = [self.tab_estribo.add(x) for x in ["Geometría Zapata", "Muros", "Consola y Topes"]]

        # --- I. DIMENSIONES GENERALES ---
        ctk.CTkLabel(tab_zap, text="I. DIMENSIONES GENERALES (cm):", font=FUENTE_SUBTITULO, text_color=COLOR_ACENTO).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10,0))
        
        ctk.CTkLabel(tab_zap, text="Largo:", font=FUENTE_NORMAL).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.ent_z_largo = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=80, corner_radius=0); self.ent_z_largo.grid(row=1, column=1, padx=5, pady=5)
        
        ctk.CTkLabel(tab_zap, text="Ancho:", font=FUENTE_NORMAL).grid(row=1, column=2, sticky="w", padx=10, pady=5)
        self.ent_z_ancho = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=80, corner_radius=0); self.ent_z_ancho.grid(row=1, column=3, padx=5, pady=5)
        
        ctk.CTkLabel(tab_zap, text="Alto:", font=FUENTE_NORMAL).grid(row=1, column=4, sticky="w", padx=10, pady=5)
        self.ent_z_alto = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=80, corner_radius=0); self.ent_z_alto.grid(row=1, column=5, padx=5, pady=5)

        # --- II. RECUBRIMIENTOS ---
        ctk.CTkLabel(tab_zap, text="II. RECUBRIMIENTOS (cm):", font=FUENTE_SUBTITULO, text_color=COLOR_ACENTO).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(15,0))
        
        ctk.CTkLabel(tab_zap, text="Cara inferior:", font=FUENTE_NORMAL).grid(row=3, column=0, sticky="w", padx=10, pady=5)
        self.ent_rec_inf = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=80, corner_radius=0); self.ent_rec_inf.grid(row=3, column=1, padx=5, pady=5)
        
        ctk.CTkLabel(tab_zap, text="Cara superior:", font=FUENTE_NORMAL).grid(row=3, column=2, sticky="w", padx=10, pady=5)
        self.ent_rec_sup = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=80, corner_radius=0); self.ent_rec_sup.grid(row=3, column=3, padx=5, pady=5)
        
        ctk.CTkLabel(tab_zap, text="Caras laterales:", font=FUENTE_NORMAL).grid(row=3, column=4, sticky="w", padx=10, pady=5)
        self.ent_rec_lat = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=80, corner_radius=0); self.ent_rec_lat.grid(row=3, column=5, padx=5, pady=5)

        # --- III. ARMADURA ---
        ctk.CTkLabel(tab_zap, text="III. ARMADURA:", font=FUENTE_SUBTITULO, text_color=COLOR_ACENTO).grid(row=4, column=0, sticky="w", padx=10, pady=(15,0))
        
        ctk.CTkLabel(tab_zap, text="Malla inferior:", font=FUENTE_NORMAL).grid(row=5, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(tab_zap, text="Ø (mm):", font=FUENTE_NORMAL).grid(row=5, column=1, sticky="e", padx=5, pady=5)
        self.ent_phi_inf = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=60, corner_radius=0); self.ent_phi_inf.grid(row=5, column=2, sticky="w", padx=5, pady=5)
        ctk.CTkLabel(tab_zap, text="@ (cm):", font=FUENTE_NORMAL).grid(row=5, column=3, sticky="e", padx=5, pady=5)
        self.ent_espac_inf = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=60, corner_radius=0); self.ent_espac_inf.grid(row=5, column=4, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(tab_zap, text="Malla superior:", font=FUENTE_NORMAL).grid(row=6, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(tab_zap, text="Ø (mm):", font=FUENTE_NORMAL).grid(row=6, column=1, sticky="e", padx=5, pady=5)
        self.ent_phi_sup = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=60, corner_radius=0); self.ent_phi_sup.grid(row=6, column=2, sticky="w", padx=5, pady=5)
        ctk.CTkLabel(tab_zap, text="@ (cm):", font=FUENTE_NORMAL).grid(row=6, column=3, sticky="e", padx=5, pady=5)
        self.ent_espac_sup = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=60, corner_radius=0); self.ent_espac_sup.grid(row=6, column=4, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(tab_zap, text="Laterales:", font=FUENTE_NORMAL).grid(row=7, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(tab_zap, text="Ø (mm):", font=FUENTE_NORMAL).grid(row=7, column=1, sticky="e", padx=5, pady=5)
        self.ent_phi_lat = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=60, corner_radius=0); self.ent_phi_lat.grid(row=7, column=2, sticky="w", padx=5, pady=5)
        ctk.CTkLabel(tab_zap, text="@ (cm):", font=FUENTE_NORMAL).grid(row=7, column=3, sticky="e", padx=5, pady=5)
        self.ent_espac_lat = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=60, corner_radius=0); self.ent_espac_lat.grid(row=7, column=4, sticky="w", padx=5, pady=5)
        
        ctk.CTkLabel(tab_zap, text="Gancho (cm):", font=FUENTE_NORMAL).grid(row=7, column=5, sticky="e", padx=5, pady=5)
        self.ent_gancho = ctk.CTkEntry(tab_zap, font=FUENTE_NORMAL, width=60, corner_radius=0); self.ent_gancho.grid(row=7, column=6, sticky="w", padx=5, pady=5)

        # Inicialización
        for ent, val in [(self.ent_z_largo, "750"), (self.ent_z_ancho, "1159.6"), (self.ent_z_alto, "150"), 
                         (self.ent_rec_inf, "7.5"), (self.ent_rec_sup, "5"), (self.ent_rec_lat, "5"), 
                         (self.ent_phi_inf, "22"), (self.ent_espac_inf, "15"),
                         (self.ent_phi_sup, "22"), (self.ent_espac_sup, "15"),
                         (self.ent_phi_lat, "16"), (self.ent_espac_lat, "20"),
                         (self.ent_gancho, "20")]:
            ent.insert(0, val)

        frame_vistas = ctk.CTkFrame(self.tab_armaduras, fg_color="transparent"); frame_vistas.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(frame_vistas, text="GENERACIÓN DE VISTAS 2D:", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO).pack(anchor="w", pady=(0,10))
        btn_container = ctk.CTkFrame(frame_vistas, fg_color="transparent"); btn_container.pack(fill="x")
        
        for txt, vista in [("1. Vista Frontal", "FRONTAL"), ("2. Sección A-A", "SEC_A"), ("3. Sección B-B", "SEC_B"), ("4. Sección C-C", "SEC_C")]:
            ctk.CTkButton(btn_container, text=txt, font=FUENTE_NORMAL, corner_radius=0, height=40, fg_color="transparent", border_width=1, border_color=COLOR_ACENTO, text_color=COLOR_TEXTO, hover_color="#444444", command=lambda v=vista: self.generar_vista_cad(v)).pack(side="left", expand=True, fill="x", padx=2)

    def generar_vista_cad(self, tipo_vista):
        try:
            # 1. Dimensiones a METROS
            lz = float(self.ent_z_largo.get()) / 100.0
            az = float(self.ent_z_ancho.get()) / 100.0
            hz = float(self.ent_z_alto.get()) / 100.0
            
            # Recubrimientos a METROS
            r_inf = float(self.ent_rec_inf.get()) / 100.0
            r_sup = float(self.ent_rec_sup.get()) / 100.0
            r_lat = float(self.ent_rec_lat.get()) / 100.0
            
            # Diámetros y Separaciones a METROS
            phi_inf, esp_inf = float(self.ent_phi_inf.get()) / 1000.0, float(self.ent_espac_inf.get()) / 100.0
            phi_sup, esp_sup = float(self.ent_phi_sup.get()) / 1000.0, float(self.ent_espac_sup.get()) / 100.0
            phi_lat, esp_lat = float(self.ent_phi_lat.get()) / 1000.0, float(self.ent_espac_lat.get()) / 100.0
            
            # Gancho GUI a METROS
            l_gancho = float(self.ent_gancho.get()) / 100.0
            
            # Tabla de traslapes en METROS según diámetro (Normativo)
            traslapes = {12: 0.80, 16: 1.10, 18: 1.20, 22: 1.50, 25: 1.70, 28: 1.90, 32: 2.20, 36: 2.50}
            t_lap_inf = traslapes.get(int(self.ent_phi_inf.get()), 1.50)
            t_lap_sup = traslapes.get(int(self.ent_phi_sup.get()), 1.50)

        except ValueError: 
            return messagebox.showerror("Error", "Entradas numéricas inválidas.")

        ruta_temp = os.path.join(RUTA_LOCAL_APP, f"Estribo_{tipo_vista}.lsp")
        
        # Limpieza de entorno y capa
        lisp_safe_header = f"""(setvar "CMDECHO" 0) (setq old_att (getvar "ATTREQ") old_fillet (getvar "FILLETRAD")) (setvar "ATTREQ" 0)
          (if (not (tblsearch "LAYER" "FIERROS")) (command "._layer" "_M" "FIERROS" "_C" "5" "" "") (command "._layer" "_T" "FIERROS" "_ON" "FIERROS" "_S" "FIERROS" "" "._layer" "_C" "5" "FIERROS" ""))"""
        lisp_safe_footer = """(setvar "ATTREQ" old_att) (setvar "FILLETRAD" old_fillet) (princ)"""

        if tipo_vista == "FRONTAL":
            lisp_code = f"""(defun c:SINCAL-DIBUJAR (/ p1 p2 X_left X_right Y_bot Y_top cv_xl cv_xr cv_yb cv_yt cx_l cx_r cy_b cy_t rad_b rad_t arr_x_start arr_x_end arr_y_b arr_y_t arr_xl arr_xr arr_y_start arr_y_end len_u_bot len_u_top pti_b pbi_b pbd_b ptd_b x_split_b pt_s1_b pt_s2_start pbd_b_up ptd_b_up pbi_t pti_t ptd_t pbd_t x_split_t pt_s1_t pt_s2_start_t pti_t_dn pbi_t_dn draw-circles-hatch old_att old_fillet c_ent)
              {lisp_safe_header}
              
              ;; Dibujo puro de circulos + Hatch ANSI31 color bylayer
              (defun draw-circles-hatch (pt1 pt2 esp phi_m / dist ang current_dist pto c_ent)
                (setq dist (distance pt1 pt2) ang (angle pt1 pt2) current_dist 0.0)
                (if (> dist 0)
                  (progn
                    (while (<= current_dist dist)
                      (setq pto (polar pt1 ang current_dist))
                      (command "._circle" "_NON" pto (/ phi_m 2.0))
                      (setq c_ent (entlast))
                      (command "._-hatch" "_P" "ANSI31" "1.6" "0" "_S" c_ent "" "")
                      (setq current_dist (+ current_dist esp))
                    )
                    (if (> (- dist (- current_dist esp)) 0.001)
                      (progn
                        (command "._circle" "_NON" pt2 (/ phi_m 2.0))
                        (setq c_ent (entlast))
                        (command "._-hatch" "_P" "ANSI31" "1.6" "0" "_S" c_ent "" "")
                      )
                    )
                  )
                )
              )

              (setq p1 (getpoint "\\n[SINCAL] Clic esquina INFERIOR-IZQUIERDA (Hormigon): "))
              (if p1 (progn
                (setq p2 (getcorner p1 "\\n[SINCAL] Clic esquina SUPERIOR-DERECHA (Hormigon): "))
                (if p2 (progn
                    (setq X_left (min (car p1) (car p2)) X_right (max (car p1) (car p2)))
                    (setq Y_bot (min (cadr p1) (cadr p2)) Y_top (max (cadr p1) (cadr p2)))
                    
                    ;; 1. Lineas de Recubrimiento Puro (0 width lines)
                    (setq cv_xl (+ X_left {r_lat}))
                    (setq cv_xr (- X_right {r_lat}))
                    (setq cv_yb (+ Y_bot {r_inf}))
                    (setq cv_yt (- Y_top {r_sup}))
                    
                    ;; 2. Coordenadas EJE de las U-Bars
                    (setq cy_b cv_yb)
                    (setq cy_t cv_yt)
                    ;; Tangentes verticales abrazando circulos laterales por DENTRO
                    (setq cx_l (+ cv_xl {phi_lat}))
                    (setq cx_r (- cv_xr {phi_lat}))
                    
                    (setq rad_b (* 3.0 {phi_inf}))
                    (setq rad_t (* 3.0 {phi_sup}))
                    
                    ;; --- DIBUJO DE MALS (CIRCULOS + HATCH) ---
                    ;; Limites en X (respetando tangencia de curvas)
                    (setq arr_x_start (+ cx_l rad_b))
                    (setq arr_x_end (- cx_r rad_b))
                    
                    ;; Inferior (Sentada SOBRE U-Bar)
                    (setq arr_y_b (+ cy_b (/ {phi_inf} 2.0)))
                    (draw-circles-hatch (list arr_x_start arr_y_b 0.0) (list arr_x_end arr_y_b 0.0) {esp_inf} {phi_inf})
                    
                    ;; Superior (Colgando DEBAJO U-Bar)
                    (setq arr_y_t (- cy_t (/ {phi_sup} 2.0)))
                    (draw-circles-hatch (list arr_x_start arr_y_t 0.0) (list arr_x_end arr_y_t 0.0) {esp_sup} {phi_sup})
                    
                    ;; Laterales
                    (setq arr_xl (+ cv_xl (/ {phi_lat} 2.0)))
                    (setq arr_xr (- cv_xr (/ {phi_lat} 2.0)))
                    (setq arr_y_start (+ cy_b rad_b))
                    (setq arr_y_end (- cy_t rad_t))
                    
                    (draw-circles-hatch (list arr_xl arr_y_start 0.0) (list arr_xl arr_y_end 0.0) {esp_lat} {phi_lat})
                    (draw-circles-hatch (list arr_xr arr_y_start 0.0) (list arr_xr arr_y_end 0.0) {esp_lat} {phi_lat})
                    
                    ;; --- DIBUJO U-BAR INFERIOR (12m MAX, TRASLAPE DERECHA) ---
                    (setq len_u_bot (+ (* 2.0 {l_gancho}) (- cx_r cx_l)))
                    (setq pti_b (list cx_l (+ cy_b {l_gancho})))
                    (setq pbi_b (list cx_l cy_b))
                    (setq pbd_b (list cx_r cy_b))
                    (setq ptd_b (list cx_r (+ cy_b {l_gancho})))
                    
                    (setvar "FILLETRAD" rad_b)
                    (if (<= len_u_bot 12.0)
                      (progn
                        (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" pbd_b "_NON" ptd_b "")
                        (command "._fillet" "P" (entlast))
                      )
                      (progn
                        ;; Barra 1: Arranca desde Izquierda por la tangente inferior (cy_b)
                        (setq x_split_b (+ cx_l (- 12.0 {l_gancho})))
                        (setq pt_s1_b (list x_split_b cy_b))
                        (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" pt_s1_b "")
                        (command "._fillet" "P" (entlast))
                        
                        ;; Barra 2: Traslape estrictamente colineal, comparte cy_b
                        (setq pt_s2_start_b (list (- x_split_b {t_lap_inf}) cy_b))
                        (command "._pline" "_NON" pt_s2_start_b "_NON" pbd_b "_NON" ptd_b "")
                        (command "._fillet" "P" (entlast))
                      )
                    )
                    
                    ;; --- DIBUJO U-BAR SUPERIOR (12m MAX, TRASLAPE DERECHA) ---
                    (setq len_u_top (+ (* 2.0 {l_gancho}) (- cx_r cx_l)))
                    
                    ;; NUEVO: Forzamos el Y a la tangente INFERIOR de los círculos
                    (setq cy_t_estricto (- cy_t {phi_sup}))

                    (setq pbi_t (list cx_l (- cy_t_estricto {l_gancho})))
                    (setq pti_t (list cx_l cy_t_estricto))
                    (setq ptd_t (list cx_r cy_t_estricto))
                    (setq pbd_t (list cx_r (- cy_t_estricto {l_gancho})))
                    
                    (setvar "FILLETRAD" rad_t)
                    (if (<= len_u_top 12.0)
                      (progn
                        (command "._pline" "_NON" pbi_t "_NON" pti_t "_NON" ptd_t "_NON" pbd_t "")
                        (command "._fillet" "P" (entlast))
                      )
                      (progn
                        ;; Barra 1: Arranca desde Derecha (bajó a la tangente inferior)
                        (setq x_split_t (- cx_r (- 12.0 {l_gancho})))
                        (setq pt_s1_t (list x_split_t cy_t_estricto))
                        (command "._pline" "_NON" pbd_t "_NON" ptd_t "_NON" pt_s1_t "")
                        (command "._fillet" "P" (entlast))
                        
                        ;; Barra 2: Traslape hacia izquierda (estrictamente colineal, SIN DESFASE)
                        (setq pt_s2_start_t (list (+ x_split_t {t_lap_sup}) cy_t_estricto))
                        (setq pti_t_dn (list cx_l cy_t_estricto))
                        (setq pbi_t_dn (list cx_l (- cy_t_estricto {l_gancho})))
                        (command "._pline" "_NON" pt_s2_start_t "_NON" pti_t_dn "_NON" pbi_t_dn "")
                        (command "._fillet" "P" (entlast))
                      )
                    )
                    (princ "\\n[SINCAL] Armadura estructural calculada e inyectada.")
                ))
              )) 
              {lisp_safe_footer}
            )"""

        elif tipo_vista == "SEC_A":
            lisp_code = f"""(defun c:SINCAL-DIBUJAR (/ p1 p2 X_left X_right Y_bot Y_top cx_l cx_r cy_b cy_t rad_b rad_t arr_x_start arr_x_end arr_y_start arr_y_end y_bot_perim y_top_perim x_left_perim x_right_perim pti_b pbi_b pbd_b ptd_b len_u_bot x_split_b pt_s2_start_b pbi_t pti_t ptd_t pbd_t len_u_top x_split_t pt_s1_t pt_s2_start_t pti_t_dn pbi_t_dn draw-circles-hatch old_att old_fillet c_ent)
              {lisp_safe_header}
              
              ;; Función interna para dibujar círculos + Hatch
              (defun draw-circles-hatch (pt1 pt2 esp phi_m / dist ang current_dist pto c_ent)
                (setq dist (distance pt1 pt2) ang (angle pt1 pt2) current_dist 0.0)
                (if (> dist 0)
                  (progn
                    (while (<= current_dist dist)
                      (setq pto (polar pt1 ang current_dist))
                      (command "._circle" "_NON" pto (/ phi_m 2.0))
                      (setq c_ent (entlast))
                      (command "._-hatch" "_P" "ANSI31" "1.6" "0" "_S" c_ent "" "")
                      (setq current_dist (+ current_dist esp))
                    )
                    (if (> (- dist (- current_dist esp)) 0.001)
                      (progn
                        (command "._circle" "_NON" pt2 (/ phi_m 2.0))
                        (setq c_ent (entlast))
                        (command "._-hatch" "_P" "ANSI31" "1.6" "0" "_S" c_ent "" "")
                      )
                    )
                  )
                )
              )

              (setq p1 (getpoint "\\n[SINCAL] Clic esquina INFERIOR-IZQUIERDA (Zapata): "))
              (if p1 (progn
                (setq p2 (getcorner p1 "\\n[SINCAL] Clic esquina SUPERIOR-DERECHA (Zapata): "))
                (if p2 (progn
                    (setq X_left (min (car p1) (car p2)) X_right (max (car p1) (car p2)))
                    (setq Y_bot (min (cadr p1) (cadr p2)) Y_top (max (cadr p1) (cadr p2)))
                    
                    ;; 1. Coordenadas de los CENTROS de los círculos (Fierros longitudinales)
                    (setq cy_b (+ Y_bot {r_inf} (/ {phi_inf} 2.0)))
                    (setq cy_t (- Y_top {r_sup} (/ {phi_sup} 2.0)))
                    (setq cx_l (+ X_left {r_lat} (/ {phi_lat} 2.0)))
                    (setq cx_r (- X_right {r_lat} (/ {phi_lat} 2.0)))
                    
                    (setq rad_b (* 3.0 {phi_inf}))
                    (setq rad_t (* 3.0 {phi_sup}))
                    
                    ;; 2. DIBUJO DE CÍRCULOS (Mallas longitudinales)
                    (setq arr_x_start (+ cx_l rad_b))
                    (setq arr_x_end (- cx_r rad_b))
                    
                    (draw-circles-hatch (list arr_x_start cy_b 0.0) (list arr_x_end cy_b 0.0) {esp_inf} {phi_inf}) ;; Inferiores
                    (draw-circles-hatch (list arr_x_start cy_t 0.0) (list arr_x_end cy_t 0.0) {esp_sup} {phi_sup}) ;; Superiores
                    
                    (setq arr_y_start (+ cy_b rad_b))
                    (setq arr_y_end (- cy_t rad_t))
                    (draw-circles-hatch (list cx_l arr_y_start 0.0) (list cx_l arr_y_end 0.0) {esp_lat} {phi_lat}) ;; Laterales Izq
                    (draw-circles-hatch (list cx_r arr_y_start 0.0) (list cx_r arr_y_end 0.0) {esp_lat} {phi_lat}) ;; Laterales Der
                    
                    ;; 3. CÁLCULO ESTRICTO DE TANGENCIAS (Ejes para polilíneas perimetrales)
                    (setq y_bot_perim (+ cy_b (/ {phi_inf} 2.0))) ;; Tangente superior de círculos inferiores
                    (setq y_top_perim (+ cy_t (/ {phi_sup} 2.0))) ;; Tangente superior de círculos superiores
                    (setq x_left_perim (- cx_l (/ {phi_lat} 2.0))) ;; Tangente izquierda
                    (setq x_right_perim (+ cx_r (/ {phi_lat} 2.0))) ;; Tangente derecha
                    
                    ;; 4. DIBUJO U-BAR INFERIOR (Con traslape colineal hacia la derecha)
                    (setq len_u_bot (+ (* 2.0 {l_gancho}) (- x_right_perim x_left_perim)))
                    (setq pti_b (list x_left_perim (+ y_bot_perim {l_gancho})))
                    (setq pbi_b (list x_left_perim y_bot_perim))
                    (setq pbd_b (list x_right_perim y_bot_perim))
                    (setq ptd_b (list x_right_perim (+ y_bot_perim {l_gancho})))
                    
                    (setvar "FILLETRAD" rad_b)
                    (if (<= len_u_bot 12.0)
                      (progn
                        (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" pbd_b "_NON" ptd_b "")
                        (command "._fillet" "P" (entlast))
                      )
                      (progn
                        ;; Barra 1: Izquierda
                        (setq x_split_b (+ x_left_perim (- 12.0 {l_gancho})))
                        (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" (list x_split_b y_bot_perim) "")
                        (command "._fillet" "P" (entlast))
                        
                        ;; Barra 2: Traslape
                        (setq pt_s2_start_b (list (- x_split_b {t_lap_inf}) y_bot_perim))
                        (command "._pline" "_NON" pt_s2_start_b "_NON" pbd_b "_NON" ptd_b "")
                        (command "._fillet" "P" (entlast))
                      )
                    )
                    
                    ;; 5. DIBUJO U-BAR SUPERIOR (Con traslape colineal hacia la izquierda)
                    (setq len_u_top (+ (* 2.0 {l_gancho}) (- x_right_perim x_left_perim)))
                    (setq pbi_t (list x_left_perim (- y_top_perim {l_gancho})))
                    (setq pti_t (list x_left_perim y_top_perim))
                    (setq ptd_t (list x_right_perim y_top_perim))
                    (setq pbd_t (list x_right_perim (- y_top_perim {l_gancho})))
                    
                    (setvar "FILLETRAD" rad_t)
                    (if (<= len_u_top 12.0)
                      (progn
                        (command "._pline" "_NON" pbi_t "_NON" pti_t "_NON" ptd_t "_NON" pbd_t "")
                        (command "._fillet" "P" (entlast))
                      )
                      (progn
                        ;; Barra 1: Derecha
                        (setq x_split_t (- x_right_perim (- 12.0 {l_gancho})))
                        (command "._pline" "_NON" pbd_t "_NON" ptd_t "_NON" (list x_split_t y_top_perim) "")
                        (command "._fillet" "P" (entlast))
                        
                        ;; Barra 2: Traslape
                        (setq pt_s2_start_t (list (+ x_split_t {t_lap_sup}) y_top_perim))
                        (command "._pline" "_NON" pt_s2_start_t "_NON" pti_t "_NON" pbi_t "")
                        (command "._fillet" "P" (entlast))
                      )
                    )
                    
                    (princ "\\n[SINCAL] Sección A-A (Zapata) calculada e inyectada.")
                ))
              ))
              {lisp_safe_footer}
            )"""

        else: 
            lisp_code = f'(defun c:SINCAL-DIBUJAR () {lisp_safe_header} (princ "\\n[SINCAL] Lógica para {tipo_vista} en desarrollo...") {lisp_safe_footer})'

        with open(ruta_temp, 'w', encoding='utf-8') as f: f.write(lisp_code)
        
        self.cancelar_comando_vivo = False
        ruta_lisp = ruta_temp.replace("\\", "\\\\")
        threading.Thread(target=self._hilo_comando_en_vivo, args=(f'(load "{ruta_lisp}") (c:SINCAL-DIBUJAR)\n',), daemon=True).start()

    def cargar_json_bim(self):
        ruta = filedialog.askopenfilename(title="Seleccionar Archivo JSON del Puente", filetypes=[("JSON Files", "*.json")])
        if not ruta: return
        try:
            with open(ruta, 'r', encoding='utf-8') as f: datos = json.load(f)
            e_data = datos.get("estribos", {})
            # Ponytail: Conversión /10.0 asume que el JSON de FreeCAD viene estrictamente en mm y convertimos a cm para el dibujo.
            # Upgrade path: Leer clave de unidades de metadatos del JSON del proyecto si cambia la especificación.
            for ent, key in [(self.ent_z_largo, "dado_muro_frontal_largo_entrada"), (self.ent_z_ancho, "dado_muro_frontal_ancho_entrada"), (self.ent_z_alto, "dado_muro_frontal_espesor_entrada")]:
                ent.delete(0, 'end')
                ent.insert(0, str(e_data.get(key, 0) / 10.0))
            self.log_r(f"[*] JSON cargado: {os.path.basename(ruta)}")
            messagebox.showinfo("BIM", "Datos mapeados exitosamente en centímetros.")
        except Exception as e: messagebox.showerror("Error JSON", f"Fallo al leer archivo:\n{e}")

    # ==========================================================
    # PARTE COMÚN Y SOPORTE DE ACTUALIZACIONES (MANTENIDO/OPTIMIZADO)
    # ==========================================================
    def cargar_info_github(self):
        try:
            r = requests.get(f"https://api.github.com/repos/{USUARIO_GITHUB}/{REPO_GITHUB}/commits", params={"per_page": 10}, timeout=5)
            if r.status_code == 200:
                self.txt_updates.configure(state="normal"); self.txt_updates.delete("1.0", "end")
                for c in r.json(): self.txt_updates.insert("end", f"• {c['commit']['author']['date'][:10]} : {c['commit']['message']}\n")
                self.txt_updates.configure(state="disabled")
        except: pass
    
    def cad_esta_ejecutandose(self):
        try:
            # Ponytail: Verificación simple de strings en la tasklist de Windows.
            # Ceiling: Falsos positivos si otro software contiene "acad" en su proceso. Upgrade: Validar PID y firmas ejecutables reales de Autodesk/ZWSoft.
            salida = subprocess.check_output("tasklist", creationflags=0x08000000).decode('utf-8', errors='ignore').lower()
            return any(x in salida for x in ["acad.exe", "zwcad.exe", "accoreconsole.exe"])
        except: return False

    def loop_verificador_actualizaciones_silencioso(self):
        while True:
            time.sleep(3600)
            try:
                r = requests.get(URL_BASE_RAW + "version.json", timeout=5)
                if r.json().get("version") != self.version_local_actual:
                    while self.cad_esta_ejecutandose(): time.sleep(300)
                    self.iniciar_actualizacion_hilo()
            except: pass

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
            app = None
            for s in ["ZWCAD.Application", "AutoCAD.Application", "AutoCAD.Application.25"]:
                try: app = win32com.client.GetActiveObject(s); break
                except: pass
            if not app: return self.log("\n[X] Error: No se detecta CAD abierto como Administrador.")
            docs = app.Documents
            if docs.Count == 0: return self.log(" [!] No hay ningún plano abierto.")
            
            for i in range(docs.Count):
                if self.cancelar_comando_vivo: break
                try:
                    doc = docs.Item(i)
                    if app.ActiveDocument.Name != doc.Name: app.ActiveDocument = doc; time.sleep(0.2)
                    try: doc.SendCommand("\x03\x03")
                    except: pass
                    doc.SendCommand(comando)
                    self.log(f"  > Aplicado en: {doc.Name}")
                except Exception as e: self.log(f"  > [X] Error pestaña: {e}")
        except Exception as e: self.log(f"\n[X] Fallo COM: {e}")
        finally:
            self.btn_enviar_cmd.configure(state="normal", text="Ejecutar"); self.btn_cancelar_cmd.configure(state="disabled", text="Cancelar")
            pythoncom.CoUninitialize()

    def setup_tab_docs(self):
        m = ctk.CTkFrame(self.tab_docs, fg_color="transparent"); m.pack(fill="both", expand=True, padx=10, pady=10)
        self.menu_container = ctk.CTkFrame(m, width=220, fg_color="transparent"); self.menu_container.pack(side="left", fill="y")
        ctk.CTkFrame(m, width=1, fg_color="#555555").pack(side="left", fill="y", padx=15)
        c_cont = ctk.CTkFrame(m, fg_color="transparent"); c_cont.pack(side="right", fill="both", expand=True)
        self.lbl_wiki_title = ctk.CTkLabel(c_cont, text="Seleccione un tema", font=FUENTE_SUBTITULO, text_color=COLOR_TITULO); self.lbl_wiki_title.pack(anchor="w", padx=20, pady=(10, 0))
        self.txt_wiki_content = ctk.CTkTextbox(c_cont, font=FUENTE_NORMAL, fg_color="transparent", text_color=COLOR_TEXTO, wrap="word", border_width=0); self.txt_wiki_content.pack(fill="both", expand=True, padx=20, pady=10)
        
        for t, cmd in [("README", self.mostrar_readme), ("INICIO AUTOMÁTICO", self.mostrar_comandos_lisp), ("COMANDOS LISP", self.mostrar_comandos_lisp), ("PROCESAMIENTO MASIVO", self.mostrar_procesamiento_lote)]:
            lbl = ctk.CTkLabel(self.menu_container, text=t, font=FUENTE_MENU, text_color=COLOR_TEXTO, cursor="hand2"); lbl.pack(fill="x", pady=8, padx=10)
            lbl.bind("<Button-1>", lambda e, c=cmd: c())

    def mostrar_texto_wiki(self, t, c):
        self.lbl_wiki_title.configure(text=t.upper()); self.txt_wiki_content.configure(state="normal"); self.txt_wiki_content.delete("1.0", "end"); self.txt_wiki_content.insert("0.0", c); self.txt_wiki_content.configure(state="disabled")

    def mostrar_readme(self): r = os.path.join(RUTA_LOCAL_APP, "README.md"); self.mostrar_texto_wiki("README", open(r, 'r', encoding='utf-8').read() if os.path.exists(r) else "No disponible.")
    def mostrar_comandos_lisp(self): self.mostrar_texto_wiki("Comandos", "Diccionario de comandos LISP.")
    def mostrar_procesamiento_lote(self): self.mostrar_texto_wiki("Lotes", "Scripts masivos por PowerShell corporativo.")

    def log(self, m): self.consola.configure(state="normal"); self.consola.insert("end", m + "\n"); self.consola.see("end"); self.consola.configure(state="disabled")
    def abrir_carpeta_local(self): os.startfile(RUTA_LOCAL_APP) if os.path.exists(RUTA_LOCAL_APP) else None
    def forzar_path_manual(self): self.actualizar_variable_entorno(); self.log("[!] PATH reparado de fondo.")

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
            archivos = r.get("archivos", []) + ["README.md"]
            
            for a in archivos:
                r_save = os.path.join(RUTA_LOCAL_APP, a)
                os.makedirs(os.path.dirname(r_save), exist_ok=True)
                res = requests.get(URL_BASE_RAW + a)
                if res.status_code == 200: 
                    with open(r_save, 'wb') as f:
                        f.write(res.content)
            
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
        for base in [r"Software\Autodesk\AutoCAD", r"Software\ZWSOFT\ZWCAD"]:
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base)
                winreg.CloseKey(k)
            except: pass

    def actualizar_variable_entorno(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
            p, _ = winreg.QueryValueEx(key, "Path")
            if RUTA_LOCAL_APP.lower() not in p.lower(): winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, f"{p};{RUTA_LOCAL_APP}")
            winreg.CloseKey(key)
        except: pass

    def generar_archivos_lisp(self, archivos):
        # 1. Definimos la ruta del puente de arranque (acaddoc.lsp)
        r_acc = os.path.join(RUTA_LOCAL_APP, "acaddoc.lsp")
        
        # 2. Escribimos el archivo abriéndolo en modo escritura ('w')
        with open(r_acc, 'w', encoding='utf-8') as f:
            
            # 3. Iteramos dinámicamente sobre TODOS los archivos descargados
            for a in archivos:
                # Filtramos para que solo intente cargar archivos .lsp y evite cargarse a sí mismo
                if a.lower().endswith('.lsp') and os.path.basename(a).lower() != "acaddoc.lsp":
                    
                    # Construimos la ruta segura para AutoLISP
                    ruta_lisp = os.path.join(RUTA_LOCAL_APP, a)
                    ruta_lisp_esc = ruta_lisp.replace("\\", "\\\\")
                    
                    # Inyectamos la línea de carga en el acaddoc
                    f.write(f'(load "{ruta_lisp_esc}")\n')

if __name__ == "__main__":
    app = ActualizadorCAD()
    if "--background" in sys.argv: app.ocultar_a_bandeja()
    app.mainloop()