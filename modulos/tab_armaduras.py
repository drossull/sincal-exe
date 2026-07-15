import os
import json
import threading
import math
import customtkinter as ctk
from tkinter import messagebox, filedialog

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

        ctk.CTkLabel(frame_top, text="DICCIONARIO DE DATOS (ESTRIBOS)",
                     font=fuente_subtitulo, text_color="#FFBF00").pack(side="left", padx=15, pady=15)

        self.btn_cargar_json = ctk.CTkButton(frame_top, text="📁 Cargar JSON de Proyecto", font=fuente_normal,
                                             fg_color="#444444", hover_color="#555555", corner_radius=0, command=self.cargar_json_bim)
        self.btn_cargar_json.pack(side="right", padx=15, pady=15)
        self.lbl_json_status = ctk.CTkLabel(
            frame_top, text="Archivo: Ninguno", font=fuente_normal, text_color="#888888")
        self.lbl_json_status.pack(side="right", padx=(15, 0), pady=15)

        # --- Tabview Estructural ---
        self.tab_estribo = ctk.CTkTabview(
            self, width=800, height=420, fg_color="#1E1E1E", segmented_button_selected_color="#007FFF")
        self.tab_estribo.pack(padx=20, pady=5, fill="x")
        self.tab_estribo._segmented_button.configure(font=fuente_normal)

        tab_zap = self.tab_estribo.add("Geometría Zapata")
        self.tab_estribo.add("Muros")
        self.tab_estribo.add("Consola y Topes")

        # I. DIMENSIONES GENERALES
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

        # II. RECUBRIMIENTOS
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

        # III. ARMADURA
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

        # --- NUEVA ESTRUCTURA DE BOTONES: VISTA + DESPIECE INTEGRADOS ---
        frame_vistas = ctk.CTkFrame(self, fg_color="transparent")
        frame_vistas.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(frame_vistas, text="GENERACIÓN DE VISTAS Y DESPIECES:",
                     font=fuente_subtitulo, text_color="#FFBF00").pack(anchor="w", pady=(0, 10))

        btn_container = ctk.CTkFrame(frame_vistas, fg_color="transparent")
        btn_container.pack(fill="x")

        vistas = [("1. Vista Frontal", "FRONTAL"), ("2. Sección A-A", "SEC_A"),
                  ("3. Sección B-B", "SEC_B"), ("4. Sección C-C", "SEC_C")]

        for txt, vista in vistas:
            frame_btn = ctk.CTkFrame(btn_container, fg_color="transparent")
            frame_btn.pack(side="left", expand=True, fill="x", padx=2)

            # Botón Principal (80% del ancho)
            btn_v = ctk.CTkButton(frame_btn, text=txt, font=fuente_normal, corner_radius=0, height=40,
                                  fg_color="transparent", border_width=1, border_color="#007FFF", text_color="#CCCCCC",
                                  hover_color="#444444", command=lambda v=vista: self.generar_vista_cad(v))
            btn_v.pack(side="left", expand=True, fill="x")

            # Botón "D" (Despiece) asociado a la misma vista (20% del ancho)
            btn_d = ctk.CTkButton(frame_btn, text="D", font=fuente_subtitulo, corner_radius=0, height=40, width=30,
                                  fg_color="#007FFF", hover_color="#0066CC", text_color="#FFFFFF",
                                  command=lambda v=vista: self.generar_despiece_cad(v))
            btn_d.pack(side="left", padx=(2, 0))

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
                  ;; Acepta parametro marca_str para incluirlo al principio del override
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
                        ;; Formato exacto: (1)(2) 51 Ø22
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
                          
                          ;; CÁLCULO DINÁMICO ADELANTADO PARA EXTRAER LAS MARCAS
                          (setq L_base_u (- cx_r cx_l))
                          (setq H_found (- Y_top Y_bot))
                          (setq min_hook (* H_found 0.6666667))
                          (setq raw_tot (+ L_base_u (* 2.0 min_hook)))
                          (setq rnd_tot (* (fix (+ (/ raw_tot 0.10) 0.9999)) 0.10))
                          (if (and (> rnd_tot 12.0) (<= raw_tot 12.0)) (setq rnd_tot 12.0))
                          (setq diff_to_add (- rnd_tot raw_tot))
                          (setq dyn_gancho (+ min_hook (/ diff_to_add 2.0)))
                          
                          ;; DEFINIR MARCAS INTELIGENTES
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
                          
                          ;; U-BAR INFERIOR
                          (setq len_u_bot (+ (* 2.0 dyn_gancho) (- cx_r cx_l)))
                          (setq pti_b (list cx_l (+ cy_b dyn_gancho))) (setq pbi_b (list cx_l cy_b)) (setq pbd_b (list cx_r cy_b)) (setq ptd_b (list cx_r (+ cy_b dyn_gancho)))
                          (setvar "FILLETRAD" rad_b)
                          (if (<= len_u_bot 12.0)
                            (progn (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" pbd_b "_NON" ptd_b "") (command "._fillet" "P" (entlast)))
                            (progn (setq x_split_b (+ cx_l (- 12.0 dyn_gancho))) (setq pt_s1_b (list x_split_b cy_b)) (command "._pline" "_NON" pti_b "_NON" pbi_b "_NON" pt_s1_b "") (command "._fillet" "P" (entlast)) (setq pt_s2_start_b (list (- x_split_b {t_lap_inf}) cy_b)) (command "._pline" "_NON" pt_s2_start_b "_NON" pbd_b "_NON" ptd_b "") (command "._fillet" "P" (entlast))))
                          
                          ;; U-BAR SUPERIOR
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
                # Generamos lógica compartida con sutiles variaciones para B-B (Mirror)
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
                          
                          ;; CÁLCULO DINÁMICO Y ASIGNACIÓN DE MARCAS
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

    # --- NUEVA LÓGICA DINÁMICA DE DESPIECE DEPENDIENTE DE LA VISTA SELECCIONADA ---
    def generar_despiece_cad(self, tipo_vista):
        try:
            alto_cm = float(self.ent_z_alto.get())
            rec_lat_cm = float(self.ent_rec_lat.get())
            phi_val = int(self.ent_phi_inf.get())
            espac_cm = float(self.ent_espac_inf.get())
            phi_m = phi_val / 1000.0

            # 1. Adaptar geometría base según la vista
            if tipo_vista == "FRONTAL":
                base_cm = float(self.ent_z_largo.get())
                prof_cm = float(self.ent_z_ancho.get())
            else:
                base_cm = float(self.ent_z_ancho.get())
                prof_cm = float(self.ent_z_largo.get())

            import math
            qty = math.ceil(prof_cm / espac_cm) + 1
            B = base_cm - (2 * rec_lat_cm)
            H_min = alto_cm * 0.6666667
            L_raw = B + 2 * H_min

            traslapes = {12: 80, 16: 110, 18: 120, 22: 150,
                         25: 170, 28: 190, 32: 220, 36: 250}
            splice_cm = traslapes.get(phi_val, 150)

            # 2. Generación Inteligente de Marcas Internas
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
