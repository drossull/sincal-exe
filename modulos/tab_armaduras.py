import os
import json
import threading
import math
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image

RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estandar SINCAL")


class TabArmaduras(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.setup_ui()

    def setup_ui(self):
        # --- Frame Superior: JSON ---
        frame_top = ctk.CTkFrame(
            self, fg_color="#1E1E1E", border_width=1, border_color="#444444", corner_radius=0)
        frame_top.pack(fill="x", padx=20, pady=10)

        fuente_subtitulo = ("Consolas", 18, "bold")
        fuente_normal = ("Consolas", 12)

        ctk.CTkLabel(frame_top, text="MÓDULO ESTRUCTURAL (ARMADURAS)",
                     font=fuente_subtitulo, text_color="#FFBF00").pack(side="left", padx=15, pady=15)

        self.btn_cargar_json = ctk.CTkButton(frame_top, text="📁 Cargar JSON de Proyecto", font=fuente_normal,
                                             fg_color="#444444", hover_color="#555555", corner_radius=0, command=self.cargar_json_bim)
        self.btn_cargar_json.pack(side="right", padx=15, pady=15)
        self.lbl_json_status = ctk.CTkLabel(
            frame_top, text="Archivo: Ninguno", font=fuente_normal, text_color="#888888")
        self.lbl_json_status.pack(side="right", padx=(15, 0), pady=15)

        # =========================================================
        # TABVIEW MAESTRO (Elementos Estructurales)
        # =========================================================
        self.tab_maestro = ctk.CTkTabview(
            self, width=800, height=520, fg_color="transparent", segmented_button_selected_color="#007FFF")
        self.tab_maestro.pack(padx=20, pady=5, fill="both", expand=True)
        self.tab_maestro._segmented_button.configure(font=fuente_normal)

        tab_estribos = self.tab_maestro.add("1. Estribos")
        tab_travesanos = self.tab_maestro.add("2. Travesaños")

        # =========================================================
        # CONTENIDO: 1. ESTRIBOS
        # =========================================================
        self.tab_estribo = ctk.CTkTabview(
            tab_estribos, fg_color="#1E1E1E", segmented_button_selected_color="#005BBF")
        self.tab_estribo.pack(fill="both", expand=True)
        self.tab_estribo._segmented_button.configure(font=fuente_normal)

        tab_zap = self.tab_estribo.add("Geometría Zapata")
        self.tab_estribo.add("Muros")
        self.tab_estribo.add("Consola y Topes")

        # I. DIMENSIONES GENERALES (Estribos)
        ctk.CTkLabel(tab_zap, text="I. DIMENSIONES GENERALES (cm):", font=fuente_subtitulo, text_color="#007FFF").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 0))

        ctk.CTkLabel(tab_zap, text="Largo:", font=fuente_normal).grid(
            row=1, column=0, sticky="w", padx=10, pady=5)
        self.ent_z_largo = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=80, corner_radius=0)
        self.ent_z_largo.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(tab_zap, text="Ancho:", font=fuente_normal).grid(
            row=1, column=2, sticky="w", padx=10, pady=5)
        self.ent_z_ancho = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=80, corner_radius=0)
        self.ent_z_ancho.grid(row=1, column=3, padx=5, pady=5)

        ctk.CTkLabel(tab_zap, text="Alto:", font=fuente_normal).grid(
            row=1, column=4, sticky="w", padx=10, pady=5)
        self.ent_z_alto = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=80, corner_radius=0)
        self.ent_z_alto.grid(row=1, column=5, padx=5, pady=5)

        # II. RECUBRIMIENTOS (Estribos)
        ctk.CTkLabel(tab_zap, text="II. RECUBRIMIENTOS (cm):", font=fuente_subtitulo, text_color="#007FFF").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 0))

        ctk.CTkLabel(tab_zap, text="Cara inferior:", font=fuente_normal).grid(
            row=3, column=0, sticky="w", padx=10, pady=5)
        self.ent_rec_inf = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=80, corner_radius=0)
        self.ent_rec_inf.grid(row=3, column=1, padx=5, pady=5)

        ctk.CTkLabel(tab_zap, text="Cara superior:", font=fuente_normal).grid(
            row=3, column=2, sticky="w", padx=10, pady=5)
        self.ent_rec_sup = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=80, corner_radius=0)
        self.ent_rec_sup.grid(row=3, column=3, padx=5, pady=5)

        ctk.CTkLabel(tab_zap, text="Caras laterales:", font=fuente_normal).grid(
            row=3, column=4, sticky="w", padx=10, pady=5)
        self.ent_rec_lat = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=80, corner_radius=0)
        self.ent_rec_lat.grid(row=3, column=5, padx=5, pady=5)

        # III. ARMADURA (Estribos)
        ctk.CTkLabel(tab_zap, text="III. ARMADURA:", font=fuente_subtitulo, text_color="#007FFF").grid(
            row=4, column=0, sticky="w", padx=10, pady=(15, 0))

        ctk.CTkLabel(tab_zap, text="Malla inferior:", font=fuente_normal).grid(
            row=5, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(tab_zap, text="Ø (mm):", font=fuente_normal).grid(
            row=5, column=1, sticky="e", padx=5, pady=5)
        self.ent_phi_inf = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=60, corner_radius=0)
        self.ent_phi_inf.grid(row=5, column=2, sticky="w", padx=5, pady=5)
        ctk.CTkLabel(tab_zap, text="@ (cm):", font=fuente_normal).grid(row=5,
                                                                       column=3, sticky="e", padx=5, pady=5)
        self.ent_espac_inf = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=60, corner_radius=0)
        self.ent_espac_inf.grid(row=5, column=4, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(tab_zap, text="Malla superior:", font=fuente_normal).grid(
            row=6, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(tab_zap, text="Ø (mm):", font=fuente_normal).grid(
            row=6, column=1, sticky="e", padx=5, pady=5)
        self.ent_phi_sup = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=60, corner_radius=0)
        self.ent_phi_sup.grid(row=6, column=2, sticky="w", padx=5, pady=5)
        ctk.CTkLabel(tab_zap, text="@ (cm):", font=fuente_normal).grid(row=6,
                                                                       column=3, sticky="e", padx=5, pady=5)
        self.ent_espac_sup = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=60, corner_radius=0)
        self.ent_espac_sup.grid(row=6, column=4, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(tab_zap, text="Laterales:", font=fuente_normal).grid(
            row=7, column=0, sticky="w", padx=10, pady=5)
        ctk.CTkLabel(tab_zap, text="Ø (mm):", font=fuente_normal).grid(
            row=7, column=1, sticky="e", padx=5, pady=5)
        self.ent_phi_lat = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=60, corner_radius=0)
        self.ent_phi_lat.grid(row=7, column=2, sticky="w", padx=5, pady=5)
        ctk.CTkLabel(tab_zap, text="@ (cm):", font=fuente_normal).grid(row=7,
                                                                       column=3, sticky="e", padx=5, pady=5)
        self.ent_espac_lat = ctk.CTkEntry(
            tab_zap, font=fuente_normal, width=60, corner_radius=0)
        self.ent_espac_lat.grid(row=7, column=4, sticky="w", padx=5, pady=5)

        for ent, val in [(self.ent_z_largo, "750"), (self.ent_z_ancho, "1159.6"), (self.ent_z_alto, "150"),
                         (self.ent_rec_inf, "7.5"), (self.ent_rec_sup,
                                                     "5"), (self.ent_rec_lat, "5"),
                         (self.ent_phi_inf, "22"), (self.ent_espac_inf, "15"),
                         (self.ent_phi_sup, "22"), (self.ent_espac_sup, "15"),
                         (self.ent_phi_lat, "16"), (self.ent_espac_lat, "20")]:
            ent.insert(0, val)

        # GENERACIÓN DE VISTAS Y DESPIECES (Integrado en pestaña de Zapata)
        frame_vistas = ctk.CTkFrame(tab_zap, fg_color="transparent")
        frame_vistas.grid(row=8, column=0, columnspan=6,
                          sticky="ew", pady=(20, 0))

        ctk.CTkLabel(frame_vistas, text="GENERACIÓN DE VISTAS Y DESPIECES:",
                     font=fuente_subtitulo, text_color="#FFBF00").pack(anchor="w", pady=(0, 10))

        btn_container = ctk.CTkFrame(frame_vistas, fg_color="transparent")
        btn_container.pack(fill="x")

        vistas = [("1. Vista Frontal", "FRONTAL"), ("2. Sección A-A", "SEC_A"),
                  ("3. Sección B-B", "SEC_B"), ("4. Sección C-C", "SEC_C")]

        for txt, vista in vistas:
            frame_btn = ctk.CTkFrame(btn_container, fg_color="transparent")
            frame_btn.pack(side="left", expand=True, fill="x", padx=2)

            btn_v = ctk.CTkButton(frame_btn, text=txt, font=fuente_normal, corner_radius=0, height=40,
                                  fg_color="transparent", border_width=1, border_color="#007FFF", text_color="#CCCCCC",
                                  hover_color="#444444", command=lambda v=vista: self.generar_vista_cad(v))
            btn_v.pack(side="left", expand=True, fill="x")

            btn_d = ctk.CTkButton(frame_btn, text="D", font=fuente_subtitulo, corner_radius=0, height=40, width=30,
                                  fg_color="#007FFF", hover_color="#0066CC", text_color="#FFFFFF",
                                  command=lambda v=vista: self.generar_despiece_cad(v))
            btn_d.pack(side="left", padx=(2, 0))

        # =========================================================
        # CONTENIDO: 2. TRAVESAÑOS
        # =========================================================
        self.tab_sub_travesanos = ctk.CTkTabview(
            tab_travesanos, fg_color="#1E1E1E", segmented_button_selected_color="#005BBF")
        self.tab_sub_travesanos.pack(fill="both", expand=True)
        self.tab_sub_travesanos._segmented_button.configure(font=fuente_normal)

        tab_trav_main = self.tab_sub_travesanos.add(
            "Configuración y Generación")

        # --- I. PARÁMETROS GLOBALES ---
        frame_params = ctk.CTkFrame(tab_trav_main, fg_color="transparent")
        frame_params.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_params, text="I. PARÁMETROS GLOBALES:", font=fuente_subtitulo,
                     text_color="#007FFF").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        btn_ayuda = ctk.CTkButton(frame_params, text="❓ Abrir ayuda", font=fuente_normal, width=100, fg_color="#333333",
                                  hover_color="#555555", corner_radius=0, border_width=1, border_color="#555555", command=self.mostrar_ayuda_travesano)
        btn_ayuda.grid(row=0, column=4, columnspan=2,
                       sticky="e", padx=5, pady=(0, 10))

        # Fila 1: Recubrimiento, Espesor, Esviaje
        ctk.CTkLabel(frame_params, text="Recubrimiento general (cm):", font=fuente_normal).grid(
            row=1, column=0, sticky="w", padx=5, pady=5)
        self.ent_t_rec = ctk.CTkEntry(
            frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_rec.grid(row=1, column=1, padx=5, pady=5)
        self.ent_t_rec.insert(0, "2.5")

        ctk.CTkLabel(frame_params, text="Espesor del travesaño (cm):", font=fuente_normal).grid(
            row=1, column=2, sticky="w", padx=20, pady=5)
        self.ent_t_espesor = ctk.CTkEntry(
            frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_espesor.grid(row=1, column=3, padx=5, pady=5)
        self.ent_t_espesor.insert(0, "25")

        ctk.CTkLabel(frame_params, text="Ángulo de esviaje (°):", font=fuente_normal).grid(
            row=1, column=4, sticky="w", padx=20, pady=5)
        self.ent_t_esviaje = ctk.CTkEntry(
            frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_esviaje.grid(row=1, column=5, padx=5, pady=5)
        self.ent_t_esviaje.insert(0, "0")

        # Fila 2: Diámetros (Externos, Horizontales, Estribos)
        ctk.CTkLabel(frame_params, text="Ø Fierros externos (mm):", font=fuente_normal).grid(
            row=2, column=0, sticky="w", padx=5, pady=5)
        self.ent_t_phi_ext = ctk.CTkEntry(
            frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_phi_ext.grid(row=2, column=1, padx=5, pady=5)
        self.ent_t_phi_ext.insert(0, "22")

        ctk.CTkLabel(frame_params, text="Ø Fierros horizontales (mm):", font=fuente_normal).grid(
            row=2, column=2, sticky="w", padx=20, pady=5)
        self.ent_t_phi_horiz = ctk.CTkEntry(
            frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_phi_horiz.grid(row=2, column=3, padx=5, pady=5)
        self.ent_t_phi_horiz.insert(0, "12")

        ctk.CTkLabel(frame_params, text="Ø Estribos (mm):", font=fuente_normal).grid(
            row=2, column=4, sticky="w", padx=20, pady=5)
        self.ent_t_phi_estr = ctk.CTkEntry(
            frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_phi_estr.grid(row=2, column=5, padx=5, pady=5)
        self.ent_t_phi_estr.insert(0, "12")

        # --- II. HERRAMIENTAS DE GENERACIÓN ---
        frame_botones_t = ctk.CTkFrame(tab_trav_main, fg_color="transparent")
        frame_botones_t.pack(fill="x", padx=10, pady=15)

        ctk.CTkLabel(frame_botones_t, text="II. SELECCIÓN DE CUADRANTE (AutoCAD):", font=fuente_subtitulo,
                     text_color="#007FFF").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        btn_ext_izq = ctk.CTkButton(frame_botones_t, text="1. Extremo Izquierdo", font=fuente_normal, fg_color="#444444",
                                    hover_color="#007FFF", corner_radius=0, command=lambda: self.generar_travesano_cad("EXT_IZQ"))
        btn_ext_izq.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        btn_ext_der = ctk.CTkButton(frame_botones_t, text="2. Extremo Derecho", font=fuente_normal, fg_color="#444444",
                                    hover_color="#007FFF", corner_radius=0, command=lambda: self.generar_travesano_cad("EXT_DER"))
        btn_ext_der.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        btn_tope = ctk.CTkButton(frame_botones_t, text="3. Cuadrante sobre Tope", font=fuente_normal, fg_color="#444444",
                                 hover_color="#007FFF", corner_radius=0, command=lambda: self.generar_travesano_cad("INT_TOPE"))
        btn_tope.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        btn_macizo = ctk.CTkButton(frame_botones_t, text="4. Cuadrante Macizo", font=fuente_normal, fg_color="#444444",
                                   hover_color="#007FFF", corner_radius=0, command=lambda: self.generar_travesano_cad("INT_MACIZO"))
        btn_macizo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        frame_botones_t.grid_columnconfigure(0, weight=1)
        frame_botones_t.grid_columnconfigure(1, weight=1)

    # =========================================================
    # FUNCIONES INTERACTIVAS (Visores)
    # =========================================================
    def mostrar_ayuda_travesano(self):
        visor = ctk.CTkToplevel(self)
        visor.title("SINCAL - Ayuda Cuadrantes de Travesaño")
        visor.geometry("900x350")
        visor.transient(self)

        ruta_img = os.path.join(RUTA_LOCAL_APP, "mapas", "ayuda_travesano.png")
        if not os.path.exists(ruta_img):
            base_dir = os.path.dirname(os.path.dirname(__file__))
            ruta_img = os.path.abspath(os.path.join(
                base_dir, "mapas", "ayuda_travesano.png"))

        if os.path.exists(ruta_img):
            try:
                img = Image.open(ruta_img)
                ctk_img = ctk.CTkImage(
                    light_image=img, dark_image=img, size=(850, 300))
                lbl_img = ctk.CTkLabel(visor, image=ctk_img, text="")
                lbl_img.pack(fill="both", expand=True, padx=10, pady=10)
            except Exception as e:
                ctk.CTkLabel(
                    visor, text=f"Error cargando imagen:\n{e}").pack(pady=20)
        else:
            ctk.CTkLabel(
                visor, text=f"No se encontró la imagen de ayuda en:\n{ruta_img}\n\nPor favor, guarda el DXF como 'ayuda_travesano.png' en la carpeta 'mapas'.").pack(pady=20)

    # =========================================================
    # FUNCIONES DE EJECUCIÓN (AutoCAD)
    # =========================================================
    def generar_travesano_cad(self, tipo_cuadrante):
        try:
            recub = float(self.ent_t_rec.get())
            espesor = float(self.ent_t_espesor.get())
            esviaje = float(self.ent_t_esviaje.get())
            phi_ext = int(self.ent_t_phi_ext.get())
            phi_horiz = int(self.ent_t_phi_horiz.get())
            phi_estr = int(self.ent_t_phi_estr.get())
        except ValueError:
            return messagebox.showerror("Error", "Por favor, ingresa solo valores numéricos válidos en los parámetros del travesaño.")

        ruta_temp = os.path.join(
            RUTA_LOCAL_APP, f"Travesano_{tipo_cuadrante}.lsp")
        ruta_lisp = ruta_temp.replace("\\", "\\\\")

        lisp_code = f"""(defun c:SINCAL-TRAVESANO (/ ent obj old_osnap recub_m offset_obj offset_res coords i pts pts_by_x left_pts right_pts mid_pts mid_by_y lowest_two highest_two middle_two v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 y_ext dx dy t_val x_end y_curr x_curr ray_start ray_end ray_obj int_pts min_x max_x min_y k lowest_four lowest_by_x rem_pts rem_by_y bot_pts rem_pts2 rem_pts3 rem_by_y3 rem_pts4 p)
          (vl-load-com)
          (setvar "CMDECHO" 0)
          (setq old_osnap (getvar "OSMODE"))
          (setvar "OSMODE" 0)
          
          ;; CAPA MAESTRA UNICA
          (if (not (tblsearch "LAYER" "FIERROS")) (command "._layer" "_M" "FIERROS" "_C" "5" "" ""))
          (setvar "CLAYER" "FIERROS")
          
          (princ "\\n[SINCAL] Cuadrante: {tipo_cuadrante} | Extrayendo y ordenando vertices...")
          (setq ent (car (entsel "\\nSeleccione la polilinea cerrada del cuadrante: ")))
          
          (if ent
            (progn
              (setq obj (vlax-ename->vla-object ent))
              (if (= (vla-get-Closed obj) :vlax-true)
                (progn
                  (setq recub_m (/ {recub} 100.0))
                  
                  ;; GENERAR JAULA (OFFSET)
                  ;; Algoritmo a prueba de fallos para offset interno
                  (setq offset_res (vl-catch-all-apply 'vla-offset (list obj (- recub_m))))
                  (if (not (vl-catch-all-error-p offset_res))
                    (setq offset_obj (car (vlax-safearray->list (vlax-variant-value offset_res))))
                    (progn
                      (setq offset_res (vl-catch-all-apply 'vla-offset (list obj recub_m)))
                      (if (not (vl-catch-all-error-p offset_res))
                        (setq offset_obj (car (vlax-safearray->list (vlax-variant-value offset_res))))
                      )
                    )
                  )
                  
                  (if offset_obj
                    (progn
                      (if (> (vla-get-Area offset_obj) (vla-get-Area obj))
                        (progn
                          (vla-delete offset_obj)
                          (setq offset_obj (car (vlax-safearray->list (vlax-variant-value (vla-offset obj recub_m)))))
                        )
                      )
                      
                      ;; EXTRAER Y ORDENAR LOS 10 VERTICES GEOMETRICAMENTE
                      (setq coords (vlax-safearray->list (vlax-variant-value (vla-get-Coordinates offset_obj))))
                      (setq pts nil i 0)
                      (while (< i (length coords))
                        (setq pts (append pts (list (list (nth i coords) (nth (1+ i) coords)))))
                        (setq i (+ i 2))
                      )
                      
                      (if (= (length pts) 10)
                        (cond
                          ;; ========================================================
                          ;; ALGORITMO EXTREMO IZQUIERDO (V1 a V10 Original)
                          ;; ========================================================
                          ((= "{tipo_cuadrante}" "EXT_IZQ")
                            (setq pts_by_x (vl-sort pts '(lambda (a b) (< (car a) (car b)))))
                            (setq left_pts (list (nth 0 pts_by_x) (nth 1 pts_by_x)))
                            (setq right_pts (list (nth 8 pts_by_x) (nth 9 pts_by_x)))
                            (setq mid_pts (list (nth 2 pts_by_x) (nth 3 pts_by_x) (nth 4 pts_by_x) (nth 5 pts_by_x) (nth 6 pts_by_x) (nth 7 pts_by_x)))
                            
                            (if (> (cadr (car left_pts)) (cadr (cadr left_pts)))
                              (setq v1 (car left_pts) v2 (cadr left_pts))
                              (setq v1 (cadr left_pts) v2 (car left_pts)))
                              
                            (if (> (cadr (car right_pts)) (cadr (cadr right_pts)))
                              (setq v8 (car right_pts) v7 (cadr right_pts))
                              (setq v8 (cadr right_pts) v7 (car right_pts)))
                              
                            (setq mid_by_y (vl-sort mid_pts '(lambda (a b) (< (cadr a) (cadr b)))))
                            (setq lowest_two (list (nth 0 mid_by_y) (nth 1 mid_by_y)))
                            (setq highest_two (list (nth 4 mid_by_y) (nth 5 mid_by_y)))
                            (setq middle_two (list (nth 2 mid_by_y) (nth 3 mid_by_y)))
                            
                            (if (< (car (car lowest_two)) (car (cadr lowest_two)))
                              (setq v4 (car lowest_two) v5 (cadr lowest_two))
                              (setq v4 (cadr lowest_two) v5 (car lowest_two)))
                              
                            (if (< (car (car highest_two)) (car (cadr highest_two)))
                              (setq v10 (car highest_two) v9 (cadr highest_two))
                              (setq v10 (cadr highest_two) v9 (car highest_two)))
                              
                            (if (< (car (car middle_two)) (car (cadr middle_two)))
                              (setq v3 (car middle_two) v6 (cadr middle_two))
                              (setq v3 (cadr middle_two) v6 (car middle_two)))

                            (setq y_ext (+ (cadr v1) 0.18))
                            
                            ;; 1. LINEA 1 (Roja Exterior Izquierda)
                            (setq dx (- (car v3) (car v2)))
                            (setq dy (- (cadr v3) (cadr v2)))
                            (if (not (zerop dy))
                              (progn
                                (setq t_val (/ (- (cadr v4) (cadr v3)) dy))
                                (setq x_end (+ (car v3) (* t_val dx)))
                                (command "._pline" "_NON" (list (car v1) y_ext) "_NON" v1 "_NON" v2 "_NON" v3 "_NON" (list x_end (cadr v4)) "")
                                (command "._chprop" (entlast) "" "_C" "1" "")
                              )
                            )
                            
                            ;; 2. LINEA 2 (Roja Exterior Derecha)
                            (command "._pline" "_NON" v8 "_NON" v7 "_NON" v6 "_NON" v5 "_NON" v4 "_NON" (list (car v4) y_ext) "")
                            (command "._chprop" (entlast) "" "_C" "1" "")
                            
                            ;; 3. MAGENTAS (Horizontales hacia abajo partiendo en V8)
                            (setq y_curr (cadr v8))
                            (while (>= y_curr (cadr v7))
                              (setq ray_start (list (- (car v2) 2.0) y_curr 0.0))
                              (setq ray_end (list (+ (car v8) 2.0) y_curr 0.0))
                              (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                              (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                              (if int_pts
                                (progn
                                  (setq min_x (car int_pts) k 3)
                                  (while (< k (length int_pts))
                                    (setq min_x (min min_x (nth k int_pts)))
                                    (setq k (+ k 3))
                                  )
                                  (command "._pline" "_NON" (list min_x y_curr) "_NON" (list (+ (car v8) 0.80) y_curr) "")
                                  (command "._chprop" (entlast) "" "_C" "6" "")
                                )
                              )
                              (vla-delete ray_obj)
                              (setq y_curr (- y_curr 0.20))
                            )
                            
                            ;; 4. VERDES G1 (Izquierda a Derecha)
                            (setq x_curr (+ (car v1) 0.20))
                            (while (< x_curr (car v3))
                              (setq ray_start (list x_curr (+ y_ext 1.0) 0.0))
                              (setq ray_end (list x_curr (- (cadr v4) 1.0) 0.0))
                              (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                              (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                              (if int_pts
                                (progn
                                  (setq min_y (cadr int_pts) k 4)
                                  (while (< k (length int_pts))
                                    (setq min_y (min min_y (nth k int_pts)))
                                    (setq k (+ k 3))
                                  )
                                  (command "._pline" "_NON" (list x_curr y_ext) "_NON" (list x_curr min_y) "")
                                  (command "._chprop" (entlast) "" "_C" "3" "")
                                )
                              )
                              (vla-delete ray_obj)
                              (setq x_curr (+ x_curr 0.20))
                            )
                            
                            ;; 5. VERDES G2 (Derecha a Izquierda, partiendo en V9)
                            (setq x_curr (car v9))
                            (while (>= x_curr (car v10))
                              (setq ray_start (list x_curr (+ (cadr v8) 1.0) 0.0))
                              (setq ray_end (list x_curr (- (cadr v4) 1.0) 0.0))
                              (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                              (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                              (if int_pts
                                (progn
                                  (setq min_y (cadr int_pts) k 4)
                                  (while (< k (length int_pts))
                                    (setq min_y (min min_y (nth k int_pts)))
                                    (setq k (+ k 3))
                                  )
                                  (command "._pline" "_NON" (list x_curr (cadr v8)) "_NON" (list x_curr min_y) "")
                                  (command "._chprop" (entlast) "" "_C" "3" "")
                                )
                              )
                              (vla-delete ray_obj)
                              (setq x_curr (- x_curr 0.20))
                            )
                            
                            (vla-delete offset_obj)
                            (princ "\\n[OK] Enfierradura inyectada y auditada (Extremo Izquierdo).")
                          )

                          ;; ========================================================
                          ;; ALGORITMO EXTREMO DERECHO (Nuevo)
                          ;; ========================================================
                          ((= "{tipo_cuadrante}" "EXT_DER")
                            (setq pts_by_x (vl-sort pts '(lambda (a b) (< (car a) (car b)))))
                            (setq left_pts (list (nth 0 pts_by_x) (nth 1 pts_by_x)))
                            (setq right_pts (list (nth 8 pts_by_x) (nth 9 pts_by_x)))
                            (setq mid_pts (list (nth 2 pts_by_x) (nth 3 pts_by_x) (nth 4 pts_by_x) (nth 5 pts_by_x) (nth 6 pts_by_x) (nth 7 pts_by_x)))
                            
                            (if (> (cadr (car left_pts)) (cadr (cadr left_pts)))
                              (setq v4 (car left_pts) v5 (cadr left_pts))
                              (setq v4 (cadr left_pts) v5 (car left_pts)))
                              
                            (if (> (cadr (car right_pts)) (cadr (cadr right_pts)))
                              (setq v1 (car right_pts) v10 (cadr right_pts))
                              (setq v1 (cadr right_pts) v10 (car right_pts)))
                              
                            (setq mid_by_y (vl-sort mid_pts '(lambda (a b) (> (cadr a) (cadr b)))))
                            (setq highest_two (list (nth 0 mid_by_y) (nth 1 mid_by_y)))
                            
                            (if (> (car (car highest_two)) (car (cadr highest_two)))
                              (setq v2 (car highest_two) v3 (cadr highest_two))
                              (setq v2 (cadr highest_two) v3 (car highest_two)))
                              
                            (setq lowest_four (list (nth 2 mid_by_y) (nth 3 mid_by_y) (nth 4 mid_by_y) (nth 5 mid_by_y)))
                            (setq lowest_by_x (vl-sort lowest_four '(lambda (a b) (< (car a) (car b)))))
                            (setq v6 (nth 0 lowest_by_x) v7 (nth 1 lowest_by_x) v8 (nth 2 lowest_by_x) v9 (nth 3 lowest_by_x))

                            (setq y_ext (+ (cadr v1) 0.18))
                            
                            ;; 1. LINEA 1 (Exterior Derecha)
                            (setq dx (- (car v9) (car v10)))
                            (setq dy (- (cadr v9) (cadr v10)))
                            (if (not (zerop dy))
                              (progn
                                (setq t_val (/ (- (cadr v8) (cadr v9)) dy))
                                (setq x_end (+ (car v9) (* t_val dx)))
                                (command "._pline" "_NON" (list (car v1) y_ext) "_NON" v1 "_NON" v10 "_NON" v9 "_NON" (list x_end (cadr v8)) "")
                                (command "._chprop" (entlast) "" "_C" "1" "")
                              )
                            )
                            
                            ;; 2. LINEA 2 (Alma y Fondo)
                            (command "._pline" "_NON" (list (car v4) y_ext) "_NON" v4 "_NON" v5 "_NON" v6 "_NON" v7 "_NON" v8 "_NON" (list (car v8) y_ext) "")
                            (command "._chprop" (entlast) "" "_C" "1" "")
                            
                            ;; 3. MAGENTAS (Hacia la Izquierda, partiendo en V4)
                            (setq y_curr (cadr v4))
                            (while (>= y_curr (cadr v5))
                              (setq ray_start (list (+ (car v1) 2.0) y_curr 0.0))
                              (setq ray_end (list (- (car v4) 2.0) y_curr 0.0))
                              (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                              (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                              (if int_pts
                                (progn
                                  (setq max_x (car int_pts) k 3)
                                  (while (< k (length int_pts))
                                    (setq max_x (max max_x (nth k int_pts)))
                                    (setq k (+ k 3))
                                  )
                                  (command "._pline" "_NON" (list (- (car v4) 0.80) y_curr) "_NON" (list max_x y_curr) "")
                                  (command "._chprop" (entlast) "" "_C" "6" "")
                                )
                              )
                              (vla-delete ray_obj)
                              (setq y_curr (- y_curr 0.20))
                            )
                            
                            ;; 4. VERDES G1 (Top Flat, Derecha a Izquierda)
                            (setq x_curr (- (car v1) 0.20))
                            (while (> x_curr (car v2))
                              (setq ray_start (list x_curr (+ y_ext 1.0) 0.0))
                              (setq ray_end (list x_curr (- (cadr v8) 1.0) 0.0))
                              (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                              (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                              (if int_pts
                                (progn
                                  (setq min_y (cadr int_pts) k 4)
                                  (while (< k (length int_pts))
                                    (setq min_y (min min_y (nth k int_pts)))
                                    (setq k (+ k 3))
                                  )
                                  (command "._pline" "_NON" (list x_curr y_ext) "_NON" (list x_curr min_y) "")
                                  (command "._chprop" (entlast) "" "_C" "3" "")
                                )
                              )
                              (vla-delete ray_obj)
                              (setq x_curr (- x_curr 0.20))
                            )
                            
                            ;; 5. VERDES G2 (Inner Step, Izquierda a Derecha)
                            (setq x_curr (car v3))
                            (while (<= x_curr (car v2))
                              (setq ray_start (list x_curr (+ (cadr v4) 1.0) 0.0))
                              (setq ray_end (list x_curr (- (cadr v5) 1.0) 0.0))
                              (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                              (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                              (if int_pts
                                (progn
                                  (setq min_y (cadr int_pts) k 4)
                                  (while (< k (length int_pts))
                                    (setq min_y (min min_y (nth k int_pts)))
                                    (setq k (+ k 3))
                                  )
                                  (command "._pline" "_NON" (list x_curr (cadr v4)) "_NON" (list x_curr min_y) "")
                                  (command "._chprop" (entlast) "" "_C" "3" "")
                                )
                              )
                              (vla-delete ray_obj)
                              (setq x_curr (+ x_curr 0.20))
                            )
                            
                            (vla-delete offset_obj)
                            (princ "\\n[OK] Enfierradura inyectada y auditada (Extremo Derecho).")
                          )
                          
                          (t (alert "Modulo de Cuadrante Intermedio en desarrollo."))
                        )
                        (alert "Fallo de Topologia: La polilinea debe tener exactamente 10 vertices para este cuadrante.\\nUse BOUNDARY o revise su dibujo.")
                      )
                    )
                    (alert "Fallo al generar jaula interior.")
                  )
                )
                (alert "Fallo de Geometria: La polilinea seleccionada NO esta cerrada.")
              )
            )
            (princ "\\n[X] No se selecciono nada.")
          )
          (setvar "OSMODE" old_osnap)
          (princ)
        )"""

        with open(ruta_temp, 'w', encoding='utf-8') as f:
            f.write(lisp_code)

        self.parent_app.cancelar_comando_vivo = False
        ruta_lisp = ruta_temp.replace("\\", "\\\\")
        threading.Thread(target=self.parent_app._hilo_comando_en_vivo, args=(
            f'(load "{ruta_lisp}") (c:SINCAL-TRAVESANO)\n',), daemon=True).start()

    def generar_vista_cad(self, tipo_vista):
        try:
            r_inf, r_sup, r_lat = float(self.ent_rec_inf.get()) / 100.0, float(
                self.ent_rec_sup.get()) / 100.0, float(self.ent_rec_lat.get()) / 100.0
            phi_inf, esp_inf = float(self.ent_phi_inf.get(
            )) / 1000.0, float(self.ent_espac_inf.get()) / 100.0
            phi_sup, esp_sup = float(self.ent_phi_sup.get(
            )) / 1000.0, float(self.ent_espac_sup.get()) / 100.0
            phi_lat, esp_lat = float(self.ent_phi_lat.get(
            )) / 1000.0, float(self.ent_espac_lat.get()) / 100.0

            traslapes = {12: 0.80, 16: 1.10, 18: 1.20, 22: 1.50,
                         25: 1.70, 28: 1.90, 32: 2.20, 36: 2.50}
            t_lap_inf = traslapes.get(int(self.ent_phi_inf.get()), 1.50)
            t_lap_sup = traslapes.get(int(self.ent_phi_sup.get()), 1.50)
        except ValueError:
            return messagebox.showerror("Error", "Entradas numéricas inválidas.")

        try:
            ruta_temp = os.path.join(
                RUTA_LOCAL_APP, f"Estribo_{tipo_vista}.lsp")

            lisp_safe_header = f"""(setvar "CMDECHO" 0) (setq old_att (getvar "ATTREQ") old_fillet (getvar "FILLETRAD")) (setvar "ATTREQ" 0)
              (if (not (tblsearch "LAYER" "FIERROS")) (command "._layer" "_M" "FIERROS" "_C" "5" "" "") (command "._layer" "_T" "FIERROS" "_ON" "FIERROS" "_S" "FIERROS" "" "._layer" "_C" "5" "FIERROS" ""))"""
            lisp_safe_footer = """(setvar "ATTREQ" old_att) (setvar "FILLETRAD" old_fillet) (princ)"""

            if tipo_vista == "FRONTAL":
                lisp_code = f"""(defun c:SINCAL-DIBUJAR (/ p1 p2 X_left X_right Y_bot Y_top cv_xl cv_xr cv_yb cv_yt cx_l cx_r cy_b cy_t rad_b rad_t arr_x_start arr_x_end arr_y_b arr_y_t arr_xl arr_xr arr_y_start arr_y_end len_u_bot len_u_top pti_b pbi_b pbd_b ptd_b x_split_b pt_s1_b pt_s2_start_b pbd_b_up ptd_b_up pbi_t pti_t ptd_t pbd_t x_split_t pt_s1_t pt_s2_start_t pti_t_dn pbi_t_dn draw-circles-with-dim old_att old_fillet c_ent L_base_u H_found min_hook raw_tot rnd_tot diff_to_add dyn_gancho is_split mk_u_str mk_lat_str)
                  {lisp_safe_header}
                  (defun draw-circles-with-dim (pt1 pt2 esp phi_m phi_str offset_x offset_y marca_str / dist ang current_dist pto c_ent num_spaces exact_pt2 qty text_override pt_dim old_osnap)
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
                        (setq num_spaces (fix (+ (/ dist esp) 0.005)))
                        (setq exact_pt2 (polar pt1 ang (* num_spaces esp)))
                        (if (> (- dist (* num_spaces esp)) 0.005)
                          (progn
                            (command "._circle" "_NON" pt2 (/ phi_m 2.0))
                            (setq c_ent (entlast))
                            (command "._-hatch" "_P" "ANSI31" "1.6" "0" "_S" c_ent "" "")
                            (setq exact_pt2 pt2)
                            (setq qty (+ num_spaces 2))
                          )
                          (setq qty (+ num_spaces 1))
                        )
                        (setq text_override (strcat marca_str " " (itoa qty) " %%c" phi_str))
                        (setq pt_dim (list (+ (/ (+ (car pt1) (car exact_pt2)) 2.0) offset_x) (+ (/ (+ (cadr pt1) (cadr exact_pt2)) 2.0) offset_y) 0.0))
                        
                        (if (tblsearch "DIMSTYLE" "GSG_COTAS") (command "._-dimstyle" "_R" "GSG_COTAS"))
                        (setq old_osnap (getvar "OSMODE")) (setvar "OSMODE" 0)
                        (command "_.DIMALIGNED" "_NON" pt1 "_NON" exact_pt2 "_T" text_override "_NON" pt_dim)
                        (setvar "OSMODE" old_osnap)
                      )
                    )
                  )
                  
                  (setq p1 (getpoint "\\n[SINCAL] Clic esquina INFERIOR-IZQUIERDA (Hormigon): "))
                  (if p1
                    (progn 
                      (setq p2 (getcorner p1 "\\n[SINCAL] Clic esquina SUPERIOR-DERECHA (Hormigon): ")) 
                      (if p2 
                        (progn
                          (setq X_left (min (car p1) (car p2)) X_right (max (car p1) (car p2)))
                          (setq Y_bot (min (cadr p1) (cadr p2)) Y_top (max (cadr p1) (cadr p2)))
                          (setq cv_xl (+ X_left {r_lat})) (setq cv_xr (- X_right {r_lat}))
                          (setq cv_yb (+ Y_bot {r_inf})) (setq cv_yt (- Y_top {r_sup}))
                          (setq cy_b cv_yb) (setq cy_t cv_yt)
                          (setq cx_l (+ cv_xl {phi_lat})) (setq cx_r (- cv_xr {phi_lat}))
                          (setq rad_b (* 3.0 {phi_inf})) (setq rad_t (* 3.0 {phi_sup}))
                          
                          (setq L_base_u (- cx_r cx_l))
                          (setq H_found (- Y_top Y_bot))
                          (setq min_hook (* H_found 0.6666667))
                          (setq raw_tot (+ L_base_u (* 2.0 min_hook)))
                          (setq rnd_tot (* (fix (+ (/ raw_tot 0.10) 0.9999)) 0.10))
                          (if (and (> rnd_tot 12.0) (<= raw_tot 12.0)) (setq rnd_tot 12.0))
                          (setq diff_to_add (- rnd_tot raw_tot))
                          (setq dyn_gancho (+ min_hook (/ diff_to_add 2.0)))
                          
                          (setq is_split (> rnd_tot 12.0))
                          (setq mk_u_str (if is_split "(1)(2)" "(1)"))
                          (setq mk_lat_str "(3)")
                          
                          (setq arr_x_start (+ cx_l rad_b)) (setq arr_x_end (- cx_r rad_b))
                          (setq arr_y_b (+ cy_b (/ {phi_inf} 2.0)))
                          (draw-circles-with-dim (list arr_x_start arr_y_b 0.0) (list arr_x_end arr_y_b 0.0) {esp_inf} {phi_inf} "{self.ent_phi_inf.get()}" 0.0 -0.50 mk_u_str)
                          
                          (setq arr_y_t (- cy_t (/ {phi_sup} 2.0)))
                          (draw-circles-with-dim (list arr_x_start arr_y_t 0.0) (list arr_x_end arr_y_t 0.0) {esp_sup} {phi_sup} "{self.ent_phi_sup.get()}" 0.0 0.50 mk_u_str)
                          
                          (setq arr_xl (+ cv_xl (/ {phi_lat} 2.0))) (setq arr_xr (- cv_xr (/ {phi_lat} 2.0)))
                          (setq arr_y_start (+ cy_b rad_b)) (setq arr_y_end (- cy_t rad_t))
                          
                          (draw-circles-with-dim (list arr_xl arr_y_start 0.0) (list arr_xl arr_y_end 0.0) {esp_lat} {phi_lat} "{self.ent_phi_lat.get()}" -0.50 0.0 mk_lat_str)
                          (draw-circles-with-dim (list arr_xr arr_y_start 0.0) (list arr_xr arr_y_end 0.0) {esp_lat} {phi_lat} "{self.ent_phi_lat.get()}" 0.50 0.0 mk_lat_str)
                          
                          (setq len_u_bot (+ (* 2.0 dyn_gancho) (- cx_r cx_l)))
                          (setq pti_b (list cx_l (+ cy_b dyn_gancho))) (setq pbi_b (list cx_l cy_b)) (setq pbd_b (list cx_r cy_b)) (setq ptd_b (list cx_r (+ cy_b dyn_gancho)))
                          (setvar "FILLETRAD" rad_b)
                          (if (<= len_u_bot 12.0)
                            (progn (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" pbd_b "_NON" ptd_b "") (command "._fillet" "P" (entlast)))
                            (progn (setq x_split_b (+ cx_l (- 12.0 dyn_gancho))) (setq pt_s1_b (list x_split_b cy_b)) (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" pt_s1_b "") (command "._fillet" "P" (entlast)) (setq pt_s2_start_b (list (- x_split_b {t_lap_inf}) cy_b)) (command "._pline" "_NON" pt_s2_start_b "_NON" pbd_b "_NON" ptd_b "") (command "._fillet" "P" (entlast))))
                          
                          (setq len_u_top (+ (* 2.0 dyn_gancho) (- cx_r cx_l)))
                          (setq cy_t_estricto (- cy_t {phi_sup}))
                          (setq pbi_t (list cx_l (- cy_t_estricto dyn_gancho))) (setq pti_t (list cx_l cy_t_estricto)) (setq ptd_t (list cx_r cy_t_estricto)) (setq pbd_t (list cx_r (- cy_t_estricto dyn_gancho)))
                          (setvar "FILLETRAD" rad_t)
                          (if (<= len_u_top 12.0)
                            (progn (command "._pline" "_NON" pbi_t "_NON" pti_t "_NON" ptd_t "_NON" pbd_t "") (command "._fillet" "P" (entlast)))
                            (progn (setq x_split_t (- cx_r (- 12.0 dyn_gancho))) (setq pt_s1_t (list x_split_t cy_t_estricto)) (command "._pline" "_NON" pbd_t "_NON" ptd_t "_NON" pt_s1_t "") (command "._fillet" "P" (entlast)) (setq pt_s2_start_t (list (+ x_split_t {t_lap_sup}) cy_t_estricto)) (setq pti_t_dn (list cx_l cy_t_estricto)) (setq pbi_t_dn (list cx_l (- cy_t_estricto dyn_gancho))) (command "._pline" "_NON" pt_s2_start_t "_NON" pti_t_dn "_NON" pbi_t_dn "") (command "._fillet" "P" (entlast))))
                          (princ "\\n[SINCAL] Vista Frontal inyectada con numeración automatizada.")
                        )
                      )
                    )
                  )
                  {lisp_safe_footer}
                )"""

            elif tipo_vista in ["SEC_A", "SEC_B", "SEC_C"]:
                lisp_code = f"""(defun c:SINCAL-DIBUJAR (/ p1 p2 X_left X_right Y_bot Y_top cx_l cx_r cy_b cy_t rad_b rad_t arr_x_start arr_x_end arr_y_start arr_y_end y_bot_perim y_top_perim x_left_perim x_right_perim pti_b pbi_b pbd_b ptd_b len_u_bot x_split_b pt_s2_start_b pbi_t pti_t ptd_t pbd_t len_u_top x_split_t pt_s1_t pt_s2_start_t pti_t_dn pbi_t_dn pt_dim_inf pt_dim_sup pt_dim_lat_izq pt_dim_lat_der draw-circles-with-dim old_att old_fillet c_ent L_base_u H_found min_hook raw_tot rnd_tot diff_to_add dyn_gancho is_split mk_u_str mk_lat_str)
                  {lisp_safe_header}
                  
                  (defun draw-circles-with-dim (pt1 pt2 esp phi_m phi_str offset_x offset_y marca_str / dist ang current_dist pto c_ent num_spaces exact_pt2 qty text_override pt_dim old_osnap)
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
                        (setq num_spaces (fix (+ (/ dist esp) 0.005)))
                        (setq exact_pt2 (polar pt1 ang (* num_spaces esp)))
                        (if (> (- dist (* num_spaces esp)) 0.005)
                          (progn
                            (command "._circle" "_NON" pt2 (/ phi_m 2.0))
                            (setq c_ent (entlast))
                            (command "._-hatch" "_P" "ANSI31" "1.6" "0" "_S" c_ent "" "")
                            (setq exact_pt2 pt2)
                            (setq qty (+ num_spaces 2))
                          )
                          (setq qty (+ num_spaces 1))
                        )
                        (setq text_override (strcat marca_str " " (itoa qty) " %%c" phi_str))
                        (setq pt_dim (list (+ (/ (+ (car pt1) (car exact_pt2)) 2.0) offset_x) (+ (/ (+ (cadr pt1) (cadr exact_pt2)) 2.0) offset_y) 0.0))
                        
                        (if (tblsearch "DIMSTYLE" "GSG_COTAS") (command "._-dimstyle" "_R" "GSG_COTAS"))
                        (setq old_osnap (getvar "OSMODE")) (setvar "OSMODE" 0)
                        (command "_.DIMALIGNED" "_NON" pt1 "_NON" exact_pt2 "_T" text_override "_NON" pt_dim)
                        (setvar "OSMODE" old_osnap)
                      )
                    )
                  )

                  (setq p1 (getpoint "\\n[SINCAL] Clic esquina INFERIOR-IZQUIERDA (Zapata {tipo_vista}): "))
                  (if p1
                    (progn 
                      (setq p2 (getcorner p1 "\\n[SINCAL] Clic esquina SUPERIOR-DERECHA (Zapata {tipo_vista}): ")) 
                      (if p2 
                        (progn
                          (setq X_left (min (car p1) (car p2)) X_right (max (car p1) (car p2)))
                          (setq Y_bot (min (cadr p1) (cadr p2)) Y_top (max (cadr p1) (cadr p2)))
                          (setq cy_b (+ Y_bot {r_inf} (/ {phi_inf} 2.0))) (setq cy_t (- Y_top {r_sup} (/ {phi_sup} 2.0)))
                          (setq cx_l (+ X_left {r_lat} (/ {phi_lat} 2.0))) (setq cx_r (- X_right {r_lat} (/ {phi_lat} 2.0)))
                          (setq rad_b (* 3.0 {phi_inf})) (setq rad_t (* 3.0 {phi_sup}))
                          
                          (setq y_bot_perim (+ cy_b (/ {phi_inf} 2.0))) (setq y_top_perim (+ cy_t (/ {phi_sup} 2.0)))
                          (setq x_left_perim (- cx_l (/ {phi_lat} 2.0))) (setq x_right_perim (+ cx_r (/ {phi_lat} 2.0)))
                          
                          (setq L_base_u (- x_right_perim x_left_perim))
                          (setq H_found (- Y_top Y_bot))
                          (setq min_hook (* H_found 0.6666667))
                          (setq raw_tot (+ L_base_u (* 2.0 min_hook)))
                          (setq rnd_tot (* (fix (+ (/ raw_tot 0.10) 0.9999)) 0.10))
                          (if (and (> rnd_tot 12.0) (<= raw_tot 12.0)) (setq rnd_tot 12.0))
                          (setq diff_to_add (- rnd_tot raw_tot))
                          (setq dyn_gancho (+ min_hook (/ diff_to_add 2.0)))
                          
                          (setq is_split (> rnd_tot 12.0))
                          (setq mk_u_str (if is_split "(1)(2)" "(1)"))
                          (setq mk_lat_str "(3)")

                          (setq arr_x_start (+ cx_l rad_b)) (setq arr_x_end (- cx_r rad_b))
                          
                          """
                if tipo_vista == "SEC_B":
                    lisp_code += f"""
                          (draw-circles-with-dim (list arr_x_end cy_b 0.0) (list arr_x_start cy_b 0.0) {esp_inf} {phi_inf} "{self.ent_phi_inf.get()}" 0.0 -0.50 mk_u_str)
                          (draw-circles-with-dim (list arr_x_end cy_t 0.0) (list arr_x_start cy_t 0.0) {esp_sup} {phi_sup} "{self.ent_phi_sup.get()}" 0.0 0.50 mk_u_str)
                    """
                else:
                    lisp_code += f"""
                          (draw-circles-with-dim (list arr_x_start cy_b 0.0) (list arr_x_end cy_b 0.0) {esp_inf} {phi_inf} "{self.ent_phi_inf.get()}" 0.0 -0.50 mk_u_str)
                          (draw-circles-with-dim (list arr_x_start cy_t 0.0) (list arr_x_end cy_t 0.0) {esp_sup} {phi_sup} "{self.ent_phi_sup.get()}" 0.0 0.50 mk_u_str)
                    """

                lisp_code += f"""
                          (setq arr_y_start (+ cy_b rad_b)) (setq arr_y_end (- cy_t rad_t))
                          (draw-circles-with-dim (list cx_l arr_y_start 0.0) (list cx_l arr_y_end 0.0) {esp_lat} {phi_lat} "{self.ent_phi_lat.get()}" -0.50 0.0 mk_lat_str)
                          (draw-circles-with-dim (list cx_r arr_y_start 0.0) (list cx_r arr_y_end 0.0) {esp_lat} {phi_lat} "{self.ent_phi_lat.get()}" 0.50 0.0 mk_lat_str)
                          
                          (setq len_u_bot (+ (* 2.0 dyn_gancho) (- x_right_perim x_left_perim)))
                          (setq pti_b (list x_left_perim (+ y_bot_perim dyn_gancho))) (setq pbi_b (list x_left_perim y_bot_perim)) (setq pbd_b (list x_right_perim y_bot_perim)) (setq ptd_b (list x_right_perim (+ y_bot_perim dyn_gancho)))
                          (setvar "FILLETRAD" rad_b)
                """

                if tipo_vista == "SEC_B":
                    lisp_code += f"""
                          (if (<= len_u_bot 12.0)
                            (progn (command "._pline" "_NON" ptd_b "_NON" pbd_b "_NON" pbi_b "_NON" pti_b "") (command "._fillet" "P" (entlast)))
                            (progn 
                              (setq x_split_b (- x_right_perim (- 12.0 dyn_gancho))) 
                              (command "._pline" "_NON" ptd_b "_NON" pbd_b "_NON" (list x_split_b y_bot_perim) "") 
                              (command "._fillet" "P" (entlast)) 
                              (setq pt_s2_start_b (list (+ x_split_b {t_lap_inf}) y_bot_perim)) 
                              (command "._pline" "_NON" pt_s2_start_b "_NON" pbi_b "_NON" pti_b "") 
                              (command "._fillet" "P" (entlast))))
                          
                          (setq len_u_top (+ (* 2.0 dyn_gancho) (- x_right_perim x_left_perim)))
                          (setq pbi_t (list x_left_perim (- y_top_perim dyn_gancho))) (setq pti_t (list x_left_perim y_top_perim)) (setq ptd_t (list x_right_perim y_top_perim)) (setq pbd_t (list x_right_perim (- y_top_perim dyn_gancho)))
                          (setvar "FILLETRAD" rad_t)
                          (if (<= len_u_top 12.0)
                            (progn (command "._pline" "_NON" pbi_t "_NON" pti_t "_NON" ptd_t "_NON" pbd_t "") (command "._fillet" "P" (entlast)))
                            (progn 
                              (setq x_split_t (+ x_left_perim (- 12.0 dyn_gancho))) 
                              (command "._pline" "_NON" pbi_t "_NON" pti_t "_NON" (list x_split_t y_top_perim) "") 
                              (command "._fillet" "P" (entlast)) 
                              (setq pt_s2_start_t (list (- x_split_t {t_lap_sup}) y_top_perim)) 
                              (command "._pline" "_NON" pt_s2_start_t "_NON" ptd_t "_NON" pbd_t "") 
                              (command "._fillet" "P" (entlast))))
                    """
                else:
                    lisp_code += f"""
                          (if (<= len_u_bot 12.0)
                            (progn (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" pbd_b "_NON" ptd_b "") (command "._fillet" "P" (entlast)))
                            (progn (setq x_split_b (+ x_left_perim (- 12.0 dyn_gancho))) (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" (list x_split_b y_bot_perim) "") (command "._fillet" "P" (entlast)) (setq pt_s2_start_b (list (- x_split_b {t_lap_inf}) y_bot_perim)) (command "._pline" "_NON" pt_s2_start_b "_NON" pbd_b "_NON" ptd_b "") (command "._fillet" "P" (entlast))))
                          
                          (setq len_u_top (+ (* 2.0 dyn_gancho) (- x_right_perim x_left_perim)))
                          (setq pbi_t (list x_left_perim (- y_top_perim dyn_gancho))) (setq pti_t (list x_left_perim y_top_perim)) (setq ptd_t (list x_right_perim y_top_perim)) (setq pbd_t (list x_right_perim (- y_top_perim dyn_gancho)))
                          (setvar "FILLETRAD" rad_t)
                          (if (<= len_u_top 12.0)
                            (progn (command "._pline" "_NON" pbi_t "_NON" pti_t "_NON" ptd_t "_NON" pbd_t "") (command "._fillet" "P" (entlast)))
                            (progn (setq x_split_t (- x_right_perim (- 12.0 dyn_gancho))) (command "._pline" "_NON" pbd_t "_NON" ptd_t "_NON" (list x_split_t y_top_perim) "") (command "._fillet" "P" (entlast)) (setq pt_s2_start_t (list (+ x_split_t {t_lap_sup}) y_top_perim)) (command "._pline" "_NON" pt_s2_start_t "_NON" pti_t "_NON" pbi_t "") (command "._fillet" "P" (entlast))))
                    """
                lisp_code += f"""
                          (princ "\\n[SINCAL] Zapata inyectada con numeración automatizada.")
                        )
                      )
                    )
                  )
                  {lisp_safe_footer}
                )"""

            with open(ruta_temp, 'w', encoding='utf-8') as f:
                f.write(lisp_code)

            self.parent_app.cancelar_comando_vivo = False
            ruta_lisp = ruta_temp.replace("\\", "\\\\")
            threading.Thread(target=self.parent_app._hilo_comando_en_vivo, args=(
                f'(load "{ruta_lisp}") (c:SINCAL-DIBUJAR)\n',), daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error de Ejecución",
                                 f"Fallo al inyectar código LISP:\n{e}")

    def generar_despiece_cad(self, tipo_vista):
        try:
            alto_cm = float(self.ent_z_alto.get())
            rec_lat_cm = float(self.ent_rec_lat.get())
            phi_val = int(self.ent_phi_inf.get())
            espac_cm = float(self.ent_espac_inf.get())
            phi_m = phi_val / 1000.0

            if tipo_vista == "FRONTAL":
                base_cm = float(self.ent_z_largo.get())
                prof_cm = float(self.ent_z_ancho.get())
            else:
                base_cm = float(self.ent_z_ancho.get())
                prof_cm = float(self.ent_z_largo.get())

            qty = math.ceil(prof_cm / espac_cm) + 1
            B = base_cm - (2 * rec_lat_cm)
            H_min = alto_cm * 0.6666667
            L_raw = B + 2 * H_min

            traslapes = {12: 80, 16: 110, 18: 120, 22: 150,
                         25: 170, 28: 190, 32: 220, 36: 250}
            splice_cm = traslapes.get(phi_val, 150)

            partes = []
            if L_raw <= 1200:
                L_rnd = math.ceil(L_raw / 10.0) * 10.0
                diff = L_rnd - L_raw
                H_dyn = H_min + (diff / 2.0)
                partes.append({"marca": "1", "tipo": "unica", "Horiz": round(
                    B), "H_dyn": round(H_dyn), "L_tot": int(L_rnd)})
            else:
                L2_raw = B - 1200 + splice_cm + (2 * H_min)
                L2_rnd = math.ceil(L2_raw / 10.0) * 10.0
                diff = L2_rnd - L2_raw
                H_dyn = H_min + (diff / 2.0)
                Horiz1 = 1200 - H_dyn
                Horiz2 = B - Horiz1 + splice_cm

                partes.append({"marca": "1", "tipo": "izq", "Horiz": round(
                    Horiz2), "H_dyn": round(H_dyn), "L_tot": int(L2_rnd)})
                partes.append({"marca": "2", "tipo": "der", "Horiz": round(
                    Horiz1), "H_dyn": round(H_dyn), "L_tot": 1200})

        except ValueError:
            return messagebox.showerror("Error", "Entradas numéricas inválidas en dimensiones.")

        ruta_temp = os.path.join(RUTA_LOCAL_APP, f"Despiece_{tipo_vista}.lsp")

        lisp_code = f"""(defun c:SINCAL-DESPIECE (/ pt old_osnap txt_height rad_b p1 p2 p3 p4 p5 p6 p_dim_splice_1 p_dim_splice_2)
          (setq old_osnap (getvar "OSMODE"))
          (setvar "CMDECHO" 0) (setvar "OSMODE" 0)
          
          (if (not (tblsearch "LAYER" "FIERROS")) (command "._layer" "_M" "FIERROS" "_C" "5" "" ""))
          (setvar "CLAYER" "FIERROS")
          
          (if (tblsearch "DIMSTYLE" "GSG_ARM-COTAS") (command "._-dimstyle" "_R" "GSG_ARM-COTAS"))
          (if (tblsearch "STYLE" "RomanD") (setvar "TEXTSTYLE" "RomanD"))
          
          (defun draw-text (pt_txt txt_str align)
            (setq txt_height (cdr (assoc 40 (tblsearch "STYLE" (getvar "TEXTSTYLE")))))
            (if (= txt_height 0.0)
              (command "._TEXT" "_J" align "_NON" pt_txt "2.5" "0" txt_str)
              (command "._TEXT" "_J" align "_NON" pt_txt "0" txt_str)
            )
            (command "._chprop" (entlast) "" "_C" "3" "")
          )
          
          (setq rad_b (* 3.0 {phi_m}))
          (setvar "FILLETRAD" rad_b)

          (setq pt (getpoint "\\n[SINCAL] Clic en pantalla para insertar el Despiece ({tipo_vista}): "))
          (if pt
            (progn
        """

        if len(partes) == 1:
            p = partes[0]
            lisp_code += f"""
              (setq p1 (list (car pt) (- (cadr pt) {p['H_dyn']/100.0})))
              (setq p2 pt)
              (setq p3 (list (+ (car pt) {p['Horiz']/100.0}) (cadr pt)))
              (setq p4 (list (car p3) (- (cadr p3) {p['H_dyn']/100.0})))
              
              (command "._pline" "_NON" p1 "_NON" p2 "_NON" p3 "_NON" p4 "")
              (command "._fillet" "P" (entlast))
              
              (command "_.DIMALIGNED" "_NON" p1 "_NON" p2 "_T" "{p['H_dyn']}" "_NON" (polar p1 pi 0.15))
              (command "_.DIMALIGNED" "_NON" p2 "_NON" p3 "_T" "{p['Horiz']}" "_NON" (polar p2 (/ pi 2) 0.15))
              (command "_.DIMALIGNED" "_NON" p3 "_NON" p4 "_T" "{p['H_dyn']}" "_NON" (polar p3 0 0.15))
              
              (draw-text (polar p2 (/ pi 2) 0.35) "({p['marca']}) {qty} %%c{phi_val} @{int(espac_cm)} L= {p['L_tot']}" "_BC")
            """
        else:
            p_izq = partes[0]
            p_der = partes[1]
            lisp_code += f"""
              ;; --- FIERRO IZQUIERDO ---
              (setq p1 (list (car pt) (- (cadr pt) {p_izq['H_dyn']/100.0})))
              (setq p2 pt)
              (setq p3 (list (+ (car pt) {p_izq['Horiz']/100.0}) (cadr pt)))
              
              (command "._pline" "_NON" p1 "_NON" p2 "_NON" p3 "")
              (command "._fillet" "P" (entlast))
              
              (command "_.DIMALIGNED" "_NON" p1 "_NON" p2 "_T" "{p_izq['H_dyn']}" "_NON" (polar p1 pi 0.15))
              (command "_.DIMALIGNED" "_NON" p2 "_NON" p3 "_T" "{p_izq['Horiz']}" "_NON" (polar p2 (/ pi 2) 0.15))
              
              (draw-text (list (+ (car p2) (/ {p_izq['Horiz']/100.0} 2)) (+ (cadr p2) 0.35)) "({p_izq['marca']}) {qty} %%c{phi_val} @{int(espac_cm)} L= {p_izq['L_tot']}" "_BC")

              ;; --- FIERRO DERECHO ---
              (setq p4 (list (- (car p3) {splice_cm/100.0}) (- (cadr p3) 0.20)))
              (setq p5 (list (+ (car p4) {p_der['Horiz']/100.0}) (cadr p4)))
              (setq p6 (list (car p5) (- (cadr p5) {p_der['H_dyn']/100.0})))
              
              (command "._pline" "_NON" p4 "_NON" p5 "_NON" p6 "")
              (command "._fillet" "P" (entlast))
              
              (command "_.DIMALIGNED" "_NON" p4 "_NON" p5 "_T" "{p_der['Horiz']}" "_NON" (polar p4 (* pi 1.5) 0.15))
              (command "_.DIMALIGNED" "_NON" p5 "_NON" p6 "_T" "{p_der['H_dyn']}" "_NON" (polar p5 0 0.15))
              
              (draw-text (list (+ (car p4) (/ {p_der['Horiz']/100.0} 2)) (- (cadr p4) 0.35)) "({p_der['marca']}) {qty} %%c{phi_val} @{int(espac_cm)} L= {p_der['L_tot']}" "_TC")

              ;; --- COTA DE TRASLAPE ---
              (if (tblsearch "DIMSTYLE" "GSG_COTAS") (command "._-dimstyle" "_R" "GSG_COTAS"))
              (setq p_dim_splice_1 (list (car p4) (cadr p2)))
              (setq p_dim_splice_2 p3)
              (command "_.DIMALIGNED" "_NON" p_dim_splice_1 "_NON" p_dim_splice_2 "_T" "<>\\\\XALTERNADO" "_NON" (list (/ (+ (car p_dim_splice_1) (car p_dim_splice_2)) 2) (+ (cadr p2) 0.50)))
            """

        lisp_code += """
            )
          )
          (setvar "OSMODE" old_osnap)
          (princ)
        )
        """

        with open(ruta_temp, 'w', encoding='utf-8') as f:
            f.write(lisp_code)

        self.parent_app.cancelar_comando_vivo = False
        ruta_lisp = ruta_temp.replace("\\", "\\\\")
        threading.Thread(target=self.parent_app._hilo_comando_en_vivo, args=(
            f'(load "{ruta_lisp}") (c:SINCAL-DESPIECE)\n',), daemon=True).start()

    def cargar_json_bim(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Archivo JSON del Proyecto", filetypes=[("JSON Files", "*.json")])
        if not ruta:
            return
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            e_data = datos.get("estribos", {})
            for ent, key in [(self.ent_z_largo, "dado_muro_frontal_largo_entrada"), (self.ent_z_ancho, "dado_muro_frontal_ancho_entrada"), (self.ent_z_alto, "dado_muro_frontal_espesor_entrada")]:
                ent.delete(0, 'end')
                ent.insert(0, str(e_data.get(key, 0) / 10.0))

            nombre_archivo = os.path.basename(ruta)
            self.lbl_json_status.configure(
                text=f"Archivo: {nombre_archivo}", text_color="#007FFF")
            self.parent_app.log_r(f"[*] JSON cargado: {nombre_archivo}")
            messagebox.showinfo(
                "BIM", "Datos mapeados exitosamente en centímetros.")
        except Exception as e:
            messagebox.showerror("Error JSON", f"Fallo al leer archivo:\n{e}")
