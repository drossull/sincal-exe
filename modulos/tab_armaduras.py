import json
import math
import os
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from sincal_runtime import ruta_recurso, ruta_runtime

RUTA_TEMPORAL = ruta_runtime()


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

        # GENERACIÓN DE VISTAS Y DESPIECES
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

        ctk.CTkLabel(frame_params, text="Longitud fierros viga (cm):", font=fuente_normal).grid(
            row=3, column=0, sticky="w", padx=5, pady=5)
        self.ent_viga_largo = ctk.CTkEntry(
            frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_viga_largo.grid(row=3, column=1, padx=5, pady=5)
        self.ent_viga_largo.insert(0, "200")

        ctk.CTkLabel(frame_params, text="Cantidad de travesaños:", font=fuente_normal).grid(
            row=3, column=2, sticky="w", padx=20, pady=5)
        self.ent_t_cantidad = ctk.CTkEntry(
            frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_cantidad.grid(row=3, column=3, padx=5, pady=5)
        self.ent_t_cantidad.insert(0, "1")

        # --- II. HERRAMIENTAS DE GENERACIÓN ---
        frame_botones_t = ctk.CTkFrame(tab_trav_main, fg_color="transparent")
        frame_botones_t.pack(fill="x", padx=10, pady=15)

        ctk.CTkLabel(frame_botones_t, text="II. SELECCIÓN DE CUADRANTE (AutoCAD):", font=fuente_subtitulo,
                     text_color="#007FFF").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        def crear_btn_cuadrante(parent, texto, comando_gen, comando_desp, fila, col, colspan=1, is_viga=False):
            frm = ctk.CTkFrame(parent, fg_color="transparent")
            frm.grid(row=fila, column=col, columnspan=colspan,
                     padx=5, pady=5, sticky="ew")

            hover_c = "#FFBF00" if is_viga else "#007FFF"
            text_c = "#1E1E1E" if is_viga else "#DCE4EE"

            btn_gen = ctk.CTkButton(frm, text=texto, font=fuente_normal, fg_color="#444444",
                                    hover_color=hover_c, text_color=text_c, corner_radius=0, command=comando_gen)
            btn_gen.pack(side="left", expand=True, fill="x")

            btn_desp = ctk.CTkButton(frm, text="D", font=fuente_subtitulo, corner_radius=0, width=30,
                                     fg_color="#007FFF", hover_color="#0066CC", text_color="#FFFFFF",
                                     command=comando_desp)
            btn_desp.pack(side="right", padx=(2, 0))
            return frm

        crear_btn_cuadrante(frame_botones_t, "1. Extremo Izquierdo",
                            lambda: self.generar_travesano_cad("EXT_IZQ"),
                            lambda: self.generar_despiece_travesano_cad("EXT_IZQ"), 1, 0)

        crear_btn_cuadrante(frame_botones_t, "2. Extremo Derecho",
                            lambda: self.generar_travesano_cad("EXT_DER"),
                            lambda: self.generar_despiece_travesano_cad("EXT_DER"), 1, 1)

        crear_btn_cuadrante(frame_botones_t, "3. Cuadrante sobre Tope",
                            lambda: self.generar_travesano_cad("INT_TOPE"),
                            lambda: self.generar_despiece_travesano_cad("INT_TOPE"), 2, 0)

        crear_btn_cuadrante(frame_botones_t, "4. Cuadrante Macizo",
                            lambda: self.generar_travesano_cad("INT_MACIZO"),
                            lambda: self.generar_despiece_travesano_cad("INT_MACIZO"), 2, 1)

        crear_btn_cuadrante(frame_botones_t, "5. Cuadrante Viga",
                            lambda: self.generar_travesano_cad("INT_VIGA"),
                            lambda: self.generar_despiece_travesano_cad("INT_VIGA"), 3, 0, colspan=2, is_viga=True)

        frame_botones_t.grid_columnconfigure(0, weight=1)
        frame_botones_t.grid_columnconfigure(1, weight=1)

    def mostrar_ayuda_travesano(self):
        visor = ctk.CTkToplevel(self)
        visor.title("SINCAL - Ayuda Cuadrantes de Travesaño")
        visor.geometry("900x350")
        visor.transient(self)

        ruta_img = ruta_recurso("mapas", "ayuda_travesano.png")

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

    def generar_travesano_cad(self, tipo_cuadrante):
        try:
            recub = float(self.ent_t_rec.get())
            espesor = float(self.ent_t_espesor.get())
            esviaje = float(self.ent_t_esviaje.get())
            phi_ext = int(self.ent_t_phi_ext.get())
            phi_horiz = int(self.ent_t_phi_horiz.get())
            phi_estr = int(self.ent_t_phi_estr.get())
            largo_viga = float(self.ent_viga_largo.get())
        except ValueError:
            return messagebox.showerror("Error", "Por favor, ingresa solo valores numéricos válidos en los parámetros del travesaño.")

        ruta_temp = os.path.join(
            RUTA_TEMPORAL, f"Travesano_{tipo_cuadrante}.lsp")
        ruta_lisp = ruta_temp.replace("\\", "\\\\")

        lisp_code = f"""(defun c:SINCAL-TRAVESANO (/ ent obj old_osnap recub_m offset_obj offset_res coords i pts pts_by_x left_pts right_pts mid_pts mid_by_y lowest_two highest_two middle_two v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15 v16 y_ext dx dy t_val x_end y_curr x_curr ray_start ray_end ray_obj int_pts min_x max_x min_y k lowest_four lowest_by_x right_bot pts_by_y pair1 pair2 pair3 pair4 pair5 pair6 bot4 y_max_L y_max_R raw_len rnd_len ext x_start x_end dist_sacado num_spaces step_sacado i_sac m_top ang_top perp_top x1_off y1_off m_horiz offset_h y_L y_R y_limit pt_start pt_end real_y_L real_y_R dx_67 dy_67 m_cyan_L y_mid_L x_start_L y_start_L dx_1011 dy_1011 m_cyan_R y_mid_R x_end_R y_end_R x_mid len_viga half_l y_min pad_g3 first_x_g1 last_x_g1 first_x_g2 last_x_g2 first_x_g3 last_x_g3 y_dim_global raw_pts p1 p2 p3 a_val left_by_y right_by_y)
          (vl-load-com)
          (setvar "CMDECHO" 0)
          (setq old_osnap (getvar "OSMODE"))
          (setvar "OSMODE" 0)
          
          (if (not (tblsearch "LAYER" "FIERROS")) (command "._layer" "_M" "FIERROS" "_C" "5" "" ""))
          (setvar "CLAYER" "FIERROS")
          
          (if (not (tblsearch "DIMSTYLE" "GSG_COTAS")) (command "._-dimstyle" "_R" "GSG_COTAS"))

          (princ "\\n[SINCAL] Cuadrante: {tipo_cuadrante} | Extrayendo geometria...")
          (setq ent (car (entsel "\\nSeleccione la polilinea cerrada del cuadrante: ")))
          
          (if ent
            (progn
              (setq *SINCAL_TRAV_HANDLE* (cdr (assoc 5 (entget ent))))
              (setq obj (vlax-ename->vla-object ent))
              (if (= (vla-get-Closed obj) :vlax-true)
                (progn
                  (setq recub_m (/ {recub} 100.0))
                  
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
                      
                      ;; LECTURA CON LAVADO COLINEAL SEGURO (Evita colapsos de AutoCAD)
                      (setq coords (vlax-safearray->list (vlax-variant-value (vla-get-Coordinates offset_obj))))
                      (setq raw_pts nil i 0)
                      (while (< i (length coords))
                        (setq raw_pts (append raw_pts (list (list (nth i coords) (nth (1+ i) coords)))))
                        (setq i (+ i 2))
                      )
                      
                      (setq pts (list (car raw_pts)))
                      (setq i 1)
                      (while (< i (1- (length raw_pts)))
                        (setq p1 (last pts) p2 (nth i raw_pts) p3 (nth (1+ i) raw_pts))
                        (if (and (> (distance p1 p2) 0.005) (> (distance p2 p3) 0.005))
                          (progn
                            (setq a_val (abs (- (angle p1 p2) (angle p2 p3))))
                            (if (> a_val pi) (setq a_val (- (* 2.0 pi) a_val)))
                            (if (not (or (< a_val 0.005) (> a_val (- pi 0.005))))
                              (setq pts (append pts (list p2)))
                            )
                          )
                        )
                        (setq i (1+ i))
                      )
                      (if (> (length raw_pts) 1) (setq pts (append pts (list (last raw_pts)))))
                      
                      (cond
                        ;; ========================================================
                        ;; ALGORITMO EXTREMO IZQUIERDO
                        ;; ========================================================
                        ((= "{tipo_cuadrante}" "EXT_IZQ")
                          (setq pts_by_x (vl-sort pts '(lambda (a b) (< (car a) (car b)))))
                          (setq left_pts (list (nth 0 pts_by_x) (nth 1 pts_by_x)))
                          (setq right_pts (list (nth (- (length pts) 2) pts_by_x) (nth (- (length pts) 1) pts_by_x)))
                          (setq mid_pts nil i 2)
                          (while (< i (- (length pts) 2))
                            (setq mid_pts (append mid_pts (list (nth i pts_by_x))))
                            (setq i (1+ i))
                          )
                          
                          (if (> (cadr (car left_pts)) (cadr (cadr left_pts))) (setq v1 (car left_pts) v2 (cadr left_pts)) (setq v1 (cadr left_pts) v2 (car left_pts)))
                          (if (> (cadr (car right_pts)) (cadr (cadr right_pts))) (setq v8 (car right_pts) v7 (cadr right_pts)) (setq v8 (cadr right_pts) v7 (car right_pts)))
                          
                          (setq mid_by_y (vl-sort mid_pts '(lambda (a b) (< (cadr a) (cadr b)))))
                          (setq lowest_two (list (nth 0 mid_by_y) (nth 1 mid_by_y)))
                          (setq highest_two (list (nth (- (length mid_by_y) 2) mid_by_y) (nth (- (length mid_by_y) 1) mid_by_y)))
                          (setq middle_two (list (nth 2 mid_by_y) (nth 3 mid_by_y)))
                          
                          (if (< (car (car lowest_two)) (car (cadr lowest_two))) (setq v4 (car lowest_two) v5 (cadr lowest_two)) (setq v4 (cadr lowest_two) v5 (car lowest_two)))
                          (if (< (car (car highest_two)) (car (cadr highest_two))) (setq v10 (car highest_two) v9 (cadr highest_two)) (setq v10 (cadr highest_two) v9 (car highest_two)))
                          (if (< (car (car middle_two)) (car (cadr middle_two))) (setq v3 (car middle_two) v6 (cadr middle_two)) (setq v3 (cadr middle_two) v6 (car middle_two)))

                          (setq m_top (/ (- (cadr v10) (cadr v1)) (- (car v10) (car v1))))
                          (setq ang_top (atan m_top))
                          (setq perp_top (+ ang_top (/ pi 2.0)))
                          (setq x1_off (+ (car v1) (* 0.18 (cos perp_top))))
                          (setq y1_off (+ (cadr v1) (* 0.18 (sin perp_top))))
                          (defun get-y-losa (x_target / ) (+ y1_off (* m_top (- x_target x1_off))))
                          
                          (setq y_ext (get-y-losa (car v1)))
                          (setq y_dim_global (+ y_ext 0.15))
                          
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
                          
                          ;; AQUI: Sube el fierro exterior hasta la cota Y de v8
                          (command "._pline" "_NON" (list (car v8) (get-y-losa (car v8))) "_NON" v8 "_NON" v7 "_NON" v6 "_NON" v5 "_NON" v4 "_NON" (list (car v4) (cadr v8)) "")
                          (command "._chprop" (entlast) "" "_C" "1" "")
                          
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
                                (command "._pline" "_NON" (list min_x y_curr) "_NON" (list (+ (car v8) 1.00) y_curr) "")
                                (command "._chprop" (entlast) "" "_C" "6" "")
                              )
                            )
                            (vla-delete ray_obj)
                            (setq y_curr (- y_curr 0.20))
                          )
                          
                          (setq first_x_g1 nil last_x_g1 nil)
                          (setq x_curr (+ (car v1) 0.20))
                          (while (< x_curr (car v3))
                            (if (not first_x_g1) (setq first_x_g1 x_curr))
                            (setq last_x_g1 x_curr)
                            (setq ray_start (list x_curr (+ (get-y-losa x_curr) 1.0) 0.0))
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
                                (command "._pline" "_NON" (list x_curr (get-y-losa x_curr)) "_NON" (list x_curr min_y) "")
                                (command "._chprop" (entlast) "" "_C" "3" "")
                              )
                            )
                            (vla-delete ray_obj)
                            (setq x_curr (+ x_curr 0.20))
                          )
                          
                          (if first_x_g1
                            (command "_.DIMALIGNED" "_NON" (list first_x_g1 (get-y-losa first_x_g1)) "_NON" (list last_x_g1 (get-y-losa last_x_g1)) "_T" (strcat "(3) %%c" (itoa {phi_estr}) " @20") "_NON" (list (/ (+ first_x_g1 last_x_g1) 2.0) y_dim_global))
                          )
                          
                          (setq first_x_g3 nil last_x_g3 nil)
                          (setq x_curr (car v9))
                          (while (>= x_curr (car v10))
                            (if (not first_x_g3) (setq first_x_g3 x_curr))
                            (setq last_x_g3 x_curr)
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
                          
                          (if first_x_g3
                            (command "_.DIMALIGNED" "_NON" (list last_x_g3 (cadr v8)) "_NON" (list first_x_g3 (cadr v8)) "_T" (strcat "(5) %%c" (itoa {phi_estr}) " @20") "_NON" (list (/ (+ first_x_g3 last_x_g3) 2.0) y_dim_global))
                          )
                          
                          (vla-delete offset_obj)
                          (princ "\\n[OK] Enfierradura inyectada y acotada (Extremo Izquierdo).")
                        )

                        ;; ========================================================
                        ;; ALGORITMO EXTREMO DERECHO
                        ;; ========================================================
                        ((= "{tipo_cuadrante}" "EXT_DER")
                          (setq pts_by_x (vl-sort pts '(lambda (a b) (< (car a) (car b)))))
                          (setq left_pts (list (nth 0 pts_by_x) (nth 1 pts_by_x)))
                          (setq right_pts (list (nth (- (length pts) 2) pts_by_x) (nth (- (length pts) 1) pts_by_x)))
                          (setq mid_pts nil i 2)
                          (while (< i (- (length pts) 2))
                            (setq mid_pts (append mid_pts (list (nth i pts_by_x))))
                            (setq i (1+ i))
                          )
                          
                          (if (> (cadr (car left_pts)) (cadr (cadr left_pts))) (setq v4 (car left_pts) v5 (cadr left_pts)) (setq v4 (cadr left_pts) v5 (car left_pts)))
                          (if (> (cadr (car right_pts)) (cadr (cadr right_pts))) (setq v1 (car right_pts) v10 (cadr right_pts)) (setq v1 (cadr right_pts) v10 (car right_pts)))
                          
                          (setq mid_by_y (vl-sort mid_pts '(lambda (a b) (> (cadr a) (cadr b)))))
                          (setq highest_two (list (nth 0 mid_by_y) (nth 1 mid_by_y)))
                          (if (> (car (car highest_two)) (car (cadr highest_two))) (setq v2 (car highest_two) v3 (cadr highest_two)) (setq v2 (cadr highest_two) v3 (car highest_two)))
                          (setq lowest_four nil i 2)
                          (while (< i (length mid_by_y)) (setq lowest_four (append lowest_four (list (nth i mid_by_y)))) (setq i (1+ i)))
                          (setq lowest_by_x (vl-sort lowest_four '(lambda (a b) (< (car a) (car b)))))
                          (setq v6 (nth 0 lowest_by_x) v7 (nth 1 lowest_by_x))
                          (setq right_bot (list (nth (- (length lowest_by_x) 2) lowest_by_x) (nth (- (length lowest_by_x) 1) lowest_by_x)))
                          (if (> (cadr (car right_bot)) (cadr (cadr right_bot))) (setq v9 (car right_bot) v8 (cadr right_bot)) (setq v9 (cadr right_bot) v8 (car right_bot)))

                          (setq m_top (/ (- (cadr v1) (cadr v2)) (- (car v1) (car v2))))
                          (setq ang_top (atan m_top)) (setq perp_top (+ ang_top (/ pi 2.0)))
                          (setq x1_off (+ (car v2) (* 0.18 (cos perp_top)))) (setq y1_off (+ (cadr v2) (* 0.18 (sin perp_top))))
                          (defun get-y-losa (x_target / ) (+ y1_off (* m_top (- x_target x1_off))))
                          
                          (setq y_ext (get-y-losa (car v1)))
                          (setq y_dim_global (+ y_ext 0.15))
                          
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
                          
                          ;; AQUI: Sube el fierro exterior hasta la cota Y de v4
                          (command "._pline" "_NON" (list (car v4) (get-y-losa (car v4))) "_NON" v4 "_NON" v5 "_NON" v6 "_NON" v7 "_NON" v8 "_NON" (list (car v8) (cadr v4)) "")
                          (command "._chprop" (entlast) "" "_C" "1" "")
                          
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
                                (command "._pline" "_NON" (list (- (car v4) 1.00) y_curr) "_NON" (list max_x y_curr) "")
                                (command "._chprop" (entlast) "" "_C" "6" "")
                              )
                            )
                            (vla-delete ray_obj)
                            (setq y_curr (- y_curr 0.20))
                          )
                          
                          (setq first_x_g1 nil last_x_g1 nil)
                          (setq x_curr (- (car v1) 0.20))
                          (while (> x_curr (car v2))
                            (if (not first_x_g1) (setq first_x_g1 x_curr))
                            (setq last_x_g1 x_curr)
                            (setq ray_start (list x_curr (+ (get-y-losa x_curr) 1.0) 0.0))
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
                                (command "._pline" "_NON" (list x_curr (get-y-losa x_curr)) "_NON" (list x_curr min_y) "")
                                (command "._chprop" (entlast) "" "_C" "3" "")
                              )
                            )
                            (vla-delete ray_obj)
                            (setq x_curr (- x_curr 0.20))
                          )
                          
                          (if first_x_g1
                            (command "_.DIMALIGNED" "_NON" (list last_x_g1 (get-y-losa last_x_g1)) "_NON" (list first_x_g1 (get-y-losa first_x_g1)) "_T" (strcat "(3) %%c" (itoa {phi_estr}) " @20") "_NON" (list (/ (+ first_x_g1 last_x_g1) 2.0) y_dim_global))
                          )
                          
                          (setq first_x_g3 nil last_x_g3 nil)
                          (setq x_curr (car v3))
                          (while (<= x_curr (car v2))
                            (if (not first_x_g3) (setq first_x_g3 x_curr))
                            (setq last_x_g3 x_curr)
                            (setq ray_start (list x_curr (+ (cadr v4) 1.0) 0.0))
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
                                (command "._pline" "_NON" (list x_curr (cadr v4)) "_NON" (list x_curr min_y) "")
                                (command "._chprop" (entlast) "" "_C" "3" "")
                              )
                            )
                            (vla-delete ray_obj)
                            (setq x_curr (+ x_curr 0.20))
                          )
                          
                          (if first_x_g3
                            (command "_.DIMALIGNED" "_NON" (list first_x_g3 (cadr v4)) "_NON" (list last_x_g3 (cadr v4)) "_T" (strcat "(5) %%c" (itoa {phi_estr}) " @20") "_NON" (list (/ (+ first_x_g3 last_x_g3) 2.0) y_dim_global))
                          )
                          
                          (vla-delete offset_obj)
                          (princ "\\n[OK] Enfierradura inyectada y auditada (Extremo Derecho).")
                        )

                        ;; ========================================================
                        ;; ALGORITMO CUADRANTE TOPE
                        ;; ========================================================
                        ((= "{tipo_cuadrante}" "INT_TOPE")
                          (setq pts_by_y (vl-sort pts '(lambda (a b) (> (cadr a) (cadr b)))))
                          
                          (setq pair1 (vl-sort (list (nth 0 pts_by_y) (nth 1 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v1 (car pair1) v16 (cadr pair1))
                          (setq pair2 (vl-sort (list (nth 2 pts_by_y) (nth 3 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v2 (car pair2) v15 (cadr pair2))
                          (setq pair3 (vl-sort (list (nth 4 pts_by_y) (nth 5 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v3 (car pair3) v14 (cadr pair3))
                          (setq pair4 (vl-sort (list (nth 6 pts_by_y) (nth 7 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v8 (car pair4) v9 (cadr pair4))
                          (setq pair5 (vl-sort (list (nth 8 pts_by_y) (nth 9 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v4 (car pair5) v13 (cadr pair5))
                          (setq pair6 (vl-sort (list (nth 10 pts_by_y) (nth 11 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v5 (car pair6) v12 (cadr pair6))
                          
                          (setq bot4 nil i 12)
                          (while (< i (length pts_by_y)) (setq bot4 (append bot4 (list (nth i pts_by_y)))) (setq i (1+ i)))
                          (setq bot4 (vl-sort bot4 '(lambda (a b) (< (car a) (car b)))))
                          (setq v6 (nth 0 bot4) v7 (nth 1 bot4) v10 (nth 2 bot4) v11 (nth 3 bot4))

                          (setq m_top (/ (- (cadr v16) (cadr v1)) (- (car v16) (car v1))))
                          (setq ang_top (atan m_top)) (setq perp_top (+ ang_top (/ pi 2.0)))
                          (setq x1_off (+ (car v1) (* 0.18 (cos perp_top)))) (setq y1_off (+ (cadr v1) (* 0.18 (sin perp_top))))
                          (defun get-y-losa (x_target / ) (+ y1_off (* m_top (- x_target x1_off))))

                          (setq dist_sacado (- (car v9) (car v8)))

                          (command "._pline" "_NON" v3 "_NON" v4 "_NON" v5 "_NON" v6 "_NON" v7 "_NON" (list (car v7) (get-y-losa (car v7))) "")
                          (command "._chprop" (entlast) "" "_C" "1" "")

                          (setq raw_len (+ dist_sacado 1.40))
                          (setq rnd_len (* (fix (+ (/ raw_len 0.10) 0.5)) 0.10))
                          (setq ext (/ (- rnd_len dist_sacado) 2.0))
                          (command "._pline" "_NON" (list (- (car v8) ext) (cadr v8)) "_NON" (list (+ (car v9) ext) (cadr v9)) "")
                          (command "._chprop" (entlast) "" "_C" "1" "")

                          (command "._pline" "_NON" v14 "_NON" v13 "_NON" v12 "_NON" v11 "_NON" v10 "_NON" (list (car v10) (get-y-losa (car v10))) "")
                          (command "._chprop" (entlast) "" "_C" "1" "")

                          (setq g1_min_h 9999.0 g1_max_h -9999.0 g1_qty 0)
                          (setq x_curr (car v2))
                          (while (<= x_curr (car v8))
                            (setq ray_start (list x_curr (+ (cadr v1) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v6) 1.0) 0.0))
                            (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                            (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                            (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v3) min_y)) (setq g1_min_h (min g1_min_h h) g1_max_h (max g1_max_h h) g1_qty (1+ g1_qty))
                             (command "._pline" "_NON" (list x_curr (cadr v3)) "_NON" (list x_curr min_y) "")
                             (command "._chprop" (entlast) "" "_C" "3" "")
                             ))
                            (vla-delete ray_obj) (setq x_curr (+ x_curr 0.20))
                          )
                          
                          (setq g2_min_h 9999.0 g2_max_h -9999.0 g2_qty 0)
                          (setq x_curr (car v15))
                          (while (>= x_curr (car v9))
                            (setq ray_start (list x_curr (+ (cadr v16) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v11) 1.0) 0.0))
                            (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                            (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                            (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v14) min_y)) (setq g2_min_h (min g2_min_h h) g2_max_h (max g2_max_h h) g2_qty (1+ g2_qty))
                             (command "._pline" "_NON" (list x_curr (cadr v14)) "_NON" (list x_curr min_y) "")
                             (command "._chprop" (entlast) "" "_C" "3" "")
                             ))
                            (vla-delete ray_obj) (setq x_curr (- x_curr 0.20))
                          )

                          (setq g3_min_h 9999.0 g3_max_h -9999.0 g3_qty 0)
                          (setq num_spaces (fix (/ dist_sacado 0.20))) (setq pad_g3 (/ (- dist_sacado (* num_spaces 0.20)) 2.0))
                          (setq i_sac 0)
                          (while (<= i_sac num_spaces)
                            (setq x_curr (+ (car v8) pad_g3 (* i_sac 0.20)))
                            (setq ray_start (list x_curr (+ (cadr v1) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v8) 1.0) 0.0))
                            (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                            (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                            (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (get-y-losa x_curr) min_y)) (setq g3_min_h (min g3_min_h h) g3_max_h (max g3_max_h h) g3_qty (1+ g3_qty))
                             (command "._pline" "_NON" (list x_curr (get-y-losa x_curr)) "_NON" (list x_curr min_y) "")
                             (command "._chprop" (entlast) "" "_C" "3" "")
                             ))
                            (vla-delete ray_obj) (setq i_sac (1+ i_sac))
                          )

                          (setq m_horiz (/ (- (cadr v14) (cadr v3)) (- (car v14) (car v3))))
                          (setq offset_h 0.20 y_L (- (cadr v3) offset_h) y_R (- (cadr v14) offset_h) y_limit (+ (max (cadr v8) (cadr v9)) 0.20))
                          (setq g_gri_min_l 9999.0 g_gri_max_l -9999.0 g_gri_qty 1) 
                          (setq g_gri_min_l (distance v3 v14) g_gri_max_l (distance v3 v14))
                          (while (>= (min y_L y_R) y_limit)
                            (setq ray_start (list (- (car v3) 1.0) (- y_L (* m_horiz 1.0)) 0.0)) (setq ray_end (list (+ (car v14) 1.0) (+ y_R (* m_horiz 1.0)) 0.0))
                            (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                            (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                            (if int_pts (progn (setq min_x (car int_pts) max_x min_x k 3) (while (< k (length int_pts)) (setq min_x (min min_x (nth k int_pts))) (setq max_x (max max_x (nth k int_pts))) (setq k (+ k 3)))
                             (setq real_y_L (+ y_L (* m_horiz (- min_x (car v3))))) (setq real_y_R (+ y_L (* m_horiz (- max_x (car v3)))))
                             (setq len_line (distance (list min_x real_y_L) (list max_x real_y_R)))
                             (setq g_gri_min_l (min g_gri_min_l len_line) g_gri_max_l (max g_gri_max_l len_line) g_gri_qty (1+ g_gri_qty))
                             (command "._pline" "_NON" (list min_x real_y_L) "_NON" (list max_x real_y_R) "")
                             (command "._chprop" (entlast) "" "_C" "8" "")
                             ))
                            (vla-delete ray_obj) (setq offset_h (+ offset_h 0.20)) (setq y_L (- (cadr v3) offset_h)) (setq y_R (- (cadr v14) offset_h))
                          )
                          
                          (setq dx_67 (- (car v7) (car v6))) (setq dy_67 (- (cadr v7) (cadr v6))) (if (= dx_67 0.0) (setq m_cyan_L 0.0) (setq m_cyan_L (/ dy_67 dx_67)))
                          (setq y_mid_L (/ (+ (cadr v8) (cadr v7)) 2.0)) (setq x_start_L (car v5)) (setq y_start_L (+ y_mid_L (* m_cyan_L (- x_start_L (car v8)))))
                          (command "._pline" "_NON" (list x_start_L y_start_L) "_NON" (list (car v8) y_mid_L) "")
                          (command "._chprop" (entlast) "" "_C" "4" "")

                          (setq dx_1011 (- (car v11) (car v10))) (setq dy_1011 (- (cadr v11) (cadr v10))) (if (= dx_1011 0.0) (setq m_cyan_R 0.0) (setq m_cyan_R (/ dy_1011 dx_1011)))
                          (setq y_mid_R (/ (+ (cadr v9) (cadr v10)) 2.0)) (setq x_end_R (car v12)) (setq y_end_R (+ y_mid_R (* m_cyan_R (- x_end_R (car v9)))))
                          (command "._pline" "_NON" (list (car v9) y_mid_R) "_NON" (list x_end_R y_end_R) "")
                          (command "._chprop" (entlast) "" "_C" "4" "")

                          (vla-delete offset_obj)
                          (princ "\\n[OK] Cuadrante de Tope inyectado.")
                        )

                        ;; ========================================================
                        ;; ALGORITMO CUADRANTE MACIZO
                        ;; ========================================================
                        ((= "{tipo_cuadrante}" "INT_MACIZO")
                          (setq pts_by_x (vl-sort pts '(lambda (a b) (< (car a) (car b)))))
                          (setq left_pts nil right_pts nil i 0)
                          (while (< i 6) (setq left_pts (append left_pts (list (nth i pts_by_x)))) (setq i (1+ i)))
                          (setq i 6)
                          (while (< i 12) (setq right_pts (append right_pts (list (nth i pts_by_x)))) (setq i (1+ i)))
                          
                          (setq left_by_y (vl-sort left_pts '(lambda (a b) (> (cadr a) (cadr b)))))
                          (setq right_by_y (vl-sort right_pts '(lambda (a b) (> (cadr a) (cadr b)))))
                          
                          (setq v1 (nth 0 left_by_y) v2 (nth 1 left_by_y) v3 (nth 2 left_by_y) v4 (nth 3 left_by_y) v5 (nth 4 left_by_y) v6 (nth 5 left_by_y))
                          (setq v12 (nth 0 right_by_y) v11 (nth 1 right_by_y) v10 (nth 2 right_by_y) v9 (nth 3 right_by_y) v8 (nth 4 right_by_y) v7 (nth 5 right_by_y))

                          ;; AQUI: Dibuja desde v3 hasta v10 exactamente
                          (command "._pline" "_NON" v3 "_NON" v4 "_NON" v5 "_NON" v6 "_NON" v7 "_NON" v8 "_NON" v9 "_NON" v10 "")
                          (command "._chprop" (entlast) "" "_C" "1" "")

                          (setq m_top (/ (- (cadr v12) (cadr v1)) (- (car v12) (car v1))))
                          (setq ang_top (atan m_top)) (setq perp_top (+ ang_top (/ pi 2.0)))
                          (setq x1_off (+ (car v1) (* 0.18 (cos perp_top)))) (setq y1_off (+ (cadr v1) (* 0.18 (sin perp_top))))
                          (defun get-y-losa (x_target / ) (+ y1_off (* m_top (- x_target x1_off))))

                          (setq g1_min_h 9999.0 g1_max_h -9999.0 g1_qty 0)
                          (setq x_curr (car v2))
                          (while (<= x_curr (car v1))
                            (setq ray_start (list x_curr (+ (cadr v3) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v6) 1.0) 0.0))
                            (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                            (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                            (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v3) min_y)) (setq g1_min_h (min g1_min_h h) g1_max_h (max g1_max_h h) g1_qty (1+ g1_qty))
                             (command "._pline" "_NON" (list x_curr (cadr v3)) "_NON" (list x_curr min_y) "")
                             (command "._chprop" (entlast) "" "_C" "3" "")
                             ))
                            (vla-delete ray_obj) (setq x_curr (+ x_curr 0.20))
                          )
                          
                          (setq g2_min_h 9999.0 g2_max_h -9999.0 g2_qty 0)
                          (setq x_curr (car v11))
                          (while (>= x_curr (car v12))
                            (setq ray_start (list x_curr (+ (cadr v10) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v7) 1.0) 0.0))
                            (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                            (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                            (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v10) min_y)) (setq g2_min_h (min g2_min_h h) g2_max_h (max g2_max_h h) g2_qty (1+ g2_qty))
                             (command "._pline" "_NON" (list x_curr (cadr v10)) "_NON" (list x_curr min_y) "")
                             (command "._chprop" (entlast) "" "_C" "3" "")
                             ))
                            (vla-delete ray_obj) (setq x_curr (- x_curr 0.20))
                          )

                          (setq g3_min_h 9999.0 g3_max_h -9999.0 g3_qty 0)
                          (setq dist_sacado (- (car v12) (car v1))) (setq num_spaces (fix (/ dist_sacado 0.20))) (setq pad_g3 (/ (- dist_sacado (* num_spaces 0.20)) 2.0))
                          (setq i_sac 0)
                          (while (<= i_sac num_spaces)
                            (setq x_curr (+ (car v1) pad_g3 (* i_sac 0.20)))
                            (setq ray_start (list x_curr (+ (cadr v1) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v6) 1.0) 0.0))
                            (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                            (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                            (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (get-y-losa x_curr) min_y)) (setq g3_min_h (min g3_min_h h) g3_max_h (max g3_max_h h) g3_qty (1+ g3_qty))
                             (command "._pline" "_NON" (list x_curr (get-y-losa x_curr)) "_NON" (list x_curr min_y) "")
                             (command "._chprop" (entlast) "" "_C" "3" "")
                             ))
                            (vla-delete ray_obj) (setq i_sac (1+ i_sac))
                          )

                          (setq m_horiz (/ (- (cadr v10) (cadr v3)) (- (car v10) (car v3))))
                          (setq offset_h 0.20 y_L (- (cadr v3) offset_h) y_R (- (cadr v10) offset_h) y_limit (max (cadr v4) (cadr v9)))
                          (setq g_gri_min_l 9999.0 g_gri_max_l -9999.0 g_gri_qty 1) 
                          (setq g_gri_min_l (distance v3 v10) g_gri_max_l (distance v3 v10))
                          (while (>= (min y_L y_R) y_limit)
                            (setq ray_start (list (- (car v3) 1.0) (- y_L (* m_horiz 1.0)) 0.0)) (setq ray_end (list (+ (car v10) 1.0) (+ y_R (* m_horiz 1.0)) 0.0))
                            (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                            (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                            (if int_pts (progn (setq min_x (car int_pts) max_x min_x k 3) (while (< k (length int_pts)) (setq min_x (min min_x (nth k int_pts))) (setq max_x (max max_x (nth k int_pts))) (setq k (+ k 3)))
                             (setq real_y_L (+ y_L (* m_horiz (- min_x (car v3))))) (setq real_y_R (+ y_L (* m_horiz (- max_x (car v3)))))
                             (setq len_line (distance (list min_x real_y_L) (list max_x real_y_R)))
                             (setq g_gri_min_l (min g_gri_min_l len_line) g_gri_max_l (max g_gri_max_l len_line) g_gri_qty (1+ g_gri_qty))
                             (command "._pline" "_NON" (list min_x real_y_L) "_NON" (list max_x real_y_R) "")
                             (command "._chprop" (entlast) "" "_C" "8" "")
                             ))
                            (vla-delete ray_obj) (setq offset_h (+ offset_h 0.20)) (setq y_L (- (cadr v3) offset_h)) (setq y_R (- (cadr v10) offset_h))
                          )
                          
                          (vla-delete offset_obj)
                          (princ "\\n[OK] Cuadrante Macizo inyectado.")
                        )

                        ;; ========================================================
                        ;; ALGORITMO CUADRANTE VIGA
                        ;; ========================================================
                        ((= "{tipo_cuadrante}" "INT_VIGA")
                          (setq pts_by_y (vl-sort pts '(lambda (a b) (> (cadr a) (cadr b)))))
                          (setq v1 (nth 0 pts_by_y) v2 (nth 1 pts_by_y) v3 (nth 2 pts_by_y) v4 (nth 3 pts_by_y))
                          (setq len_viga (/ {largo_viga} 100.0))
                          (setq half_l (/ len_viga 2.0))
                          (setq x_mid (/ (+ (car v1) (car v2)) 2.0))
                          (setq y_curr (cadr v1)) (setq y_min (cadr v3))
                          (while (>= y_curr y_min)
                            (command "._pline" "_NON" (list (- x_mid half_l) y_curr) "_NON" (list (+ x_mid half_l) y_curr) "")
                            (command "._chprop" (entlast) "" "_C" "2" "")
                            (setq y_curr (- y_curr 0.20))
                          )
                          (vla-delete offset_obj)
                          (princ "\\n[OK] Cuadrante de Viga inyectado.")
                        )
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

    def generar_despiece_travesano_cad(self, tipo_cuadrante):
        try:
            recub = float(self.ent_t_rec.get())
            espesor = float(self.ent_t_espesor.get())
            esviaje = float(self.ent_t_esviaje.get())
            phi_ext = int(self.ent_t_phi_ext.get())
            phi_horiz = int(self.ent_t_phi_horiz.get())
            phi_estr = int(self.ent_t_phi_estr.get())
            cant_trav = int(self.ent_t_cantidad.get())
            largo_viga = float(self.ent_viga_largo.get())
        except ValueError:
            return messagebox.showerror("Error", "Entradas numéricas inválidas.")

        ruta_temp = os.path.join(
            RUTA_TEMPORAL, f"Despiece_Trav_{tipo_cuadrante}.lsp")

        lisp_code = f"""(defun c:SINCAL-DESPIECE-TRAV (/ ent obj old_osnap recub_m offset_obj offset_res coords i pts pts_by_x left_pts right_pts mid_pts mid_by_y lowest_two highest_two middle_two v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 v11 v12 v13 v14 v15 v16 y_ext dx dy t_val x_end y_curr x_curr ray_start ray_end ray_obj int_pts min_x max_x min_y k ins_pt ins_x ins_y shift_x shift_y pts1 pts2 L1 L2 w_estr g1_min_h g1_max_h g1_qty first_x_g1 last_x_g1 g2_min_l g2_max_l g2_qty g3_min_h g3_max_h g3_qty first_x_g3 last_x_g3 h len_line L3_min L3_max L4_min L4_max L5_min L5_max h_avg l_avg txt_height m_top ang_top perp_top x1_off y1_off pts_by_y pair1 pair2 pair3 pair4 pair5 pair6 bot4 dist_sacado num_spaces step_sacado pad_g3 i_sac m_horiz offset_h y_L y_R y_limit real_y_L real_y_R m_cyan_L y_mid_L x_start_L y_start_L m_cyan_R y_mid_R x_end_R y_end_R len_viga half_l x_mid y_min ang_hk_L ang_hk_R l_min l_max spa hk1 hk2 rad text_str p_dim_w p_dim_h p_dim_hk g_gri_min_l g_gri_max_l g_gri_qty len_cyan_L len_cyan_R g_qty dim_off p1 p2 p3 raw_pts raw_list pA_raw pB_raw pC_raw a_val center_tl p_start1 p_end1 p_start2 p_end2 p_90 p_180 left_by_y right_by_y)
          (vl-load-com)
          (setvar "CMDECHO" 0)
          (setq old_osnap (getvar "OSMODE"))
          (setvar "OSMODE" 0)
          
          (setq ent nil)
          (if (boundp '*SINCAL_TRAV_HANDLE*)
            (setq ent (handent *SINCAL_TRAV_HANDLE*))
          )
          
          (if (or (not ent) (not (entget ent)))
            (progn 
              (alert "Error: El cuadrante en memoria no coincide o fue borrado. Por favor vuelve a hacer clic en Generar cuadrante antes de pedir el despiece.")
              (exit)
            )
          )
          
          (if (not (tblsearch "DIMSTYLE" "GSG_ARM-COTAS"))
            (command "._-dimstyle" "_R" "GSG_COTAS")
            (command "._-dimstyle" "_R" "GSG_ARM-COTAS")
          )
          
          (setq obj (vlax-ename->vla-object ent))
          (setq recub_m (/ {recub} 100.0))
          (setq w_estr (- (/ {espesor} 100.0) (* 2.0 recub_m)))
          
          ;; Helpers
          (defun deg2rad (deg) (* pi (/ deg 180.0)))
          
          (defun draw-text (pt_txt txt_str align / txt_height)
            (setq txt_height (cdr (assoc 40 (tblsearch "STYLE" (getvar "TEXTSTYLE")))))
            (if (= txt_height 0.0)
              (command "._TEXT" "_J" align "_NON" pt_txt "2.5" "0" txt_str)
              (command "._TEXT" "_J" align "_NON" pt_txt "0" txt_str)
            )
            (command "._chprop" (entlast) "" "_C" "3" "")
          )
          
          (defun draw-custom-bar (ins_p pts_list phi_m phi_val mark qty / new_pts x0 y0 p_trans L_tot i pA pB p_dim ang text_str dim_off raw_list pA_raw pB_raw pC_raw a_val)
            (command "._-dimstyle" "_R" "GSG_ARM-COTAS")
            (setvar "FILLETRAD" (* 3.0 phi_m))
            
            ;; LAVADO COLINEAL INTERNO PARA DIBUJO (Mata fragmentaciones y cotas 0 en el despiece)
            (setq raw_list (list (car pts_list)))
            (setq i 1)
            (while (< i (1- (length pts_list)))
              (setq pA_raw (last raw_list) pB_raw (nth i pts_list) pC_raw (nth (1+ i) pts_list))
              (if (and (> (distance pA_raw pB_raw) 0.005) (> (distance pB_raw pC_raw) 0.005))
                (progn
                  (setq a_val (abs (- (angle pA_raw pB_raw) (angle pB_raw pC_raw))))
                  (if (> a_val pi) (setq a_val (- (* 2.0 pi) a_val)))
                  (if (not (or (< a_val 0.005) (> a_val (- pi 0.005))))
                    (setq raw_list (append raw_list (list pB_raw)))
                  )
                )
              )
              (setq i (1+ i))
            )
            (if (> (length pts_list) 1) (setq raw_list (append raw_list (list (last pts_list)))))

            (setq new_pts nil L_tot 0.0)
            (setq x0 (car (car raw_list)) y0 (cadr (car raw_list)))
            (foreach p raw_list
              (setq p_trans (list (+ (car ins_p) (- (car p) x0)) (+ (cadr ins_p) (- (cadr p) y0))))
              (setq new_pts (append new_pts (list p_trans)))
            )
            (command "._pline") (foreach p new_pts (command "_NON" p)) (command "")
            (command "._fillet" "P" (entlast))
            (command "._chprop" (entlast) "" "_C" "5" "")
            
            (setq dim_off 0.3)
            (setq i 0)
            (while (< i (1- (length new_pts)))
              (setq pA (nth i new_pts) pB (nth (1+ i) new_pts))
              (setq L_tot (+ L_tot (distance pA pB)))
              (setq ang (angle pA pB))
              (setq p_dim (polar (list (/ (+ (car pA) (car pB)) 2.0) (/ (+ (cadr pA) (cadr pB)) 2.0)) (+ ang (/ pi 2.0)) dim_off))
              (if (> (distance pA pB) 0.05)
                (command "_.DIMALIGNED" "_NON" pA "_NON" pB "_T" (rtos (* (distance pA pB) 100) 2 0) "_NON" p_dim)
              )
              (setq i (1+ i))
            )
            (setq text_str (strcat "(" mark ") " (itoa qty) " %%c" (itoa phi_val) " L= " (rtos (* L_tot 100) 2 0)))
            (draw-text (list (+ (car ins_p) 0.5) (- (cadr ins_p) 1.2)) text_str "_TL")
          )

          (defun draw-stirrup (ins_p w h phi_m phi_val mark qty l_mi l_ma spa / pA pB pC pD rad text_str L_min L_max dim_off center_tl p_start1 p_end1 p_start2 p_end2 p_90 p_180)
            (command "._-dimstyle" "_R" "GSG_ARM-COTAS")
            (setq rad (* 3.0 phi_m))
            
            ;; Puntos de las esquinas exteriores
            (setq pA (list (car ins_p) (+ (cadr ins_p) h)))       ;; Arriba-Izq
            (setq pB (list (car ins_p) (cadr ins_p)))             ;; Abajo-Izq
            (setq pC (list (+ (car ins_p) w) (cadr ins_p)))       ;; Abajo-Der
            (setq pD (list (+ (car ins_p) w) (+ (cadr ins_p) h))) ;; Arriba-Der

            ;; 1. Dibujar el rectangulo con fillet (Dibuja arco de 90 a 180 grados)
            (setvar "FILLETRAD" rad)
            (command "._rectang" "_F" rad "_NON" pB "_NON" pD)
            (command "._chprop" (entlast) "" "_C" "5" "")

            ;; 2. Rellenar el GAP proyectando el arco
            (setq center_tl (list (+ (car ins_p) rad) (- (+ (cadr ins_p) h) rad)))
            
            ;; Puntos diametrales a 45 y 225 grados
            (setq p_start1 (polar center_tl (deg2rad 45) rad))
            (setq p_start2 (polar center_tl (deg2rad 225) rad))
            (setq p_90 (polar center_tl (deg2rad 90) rad))
            (setq p_180 (polar center_tl (deg2rad 180) rad))
            
            ;; DIBUJO DE LOS ARCOS DE RELLENO
            (command "._arc" "_C" "_NON" center_tl "_NON" p_start1 "_NON" p_90)
            (command "._chprop" (entlast) "" "_C" "5" "")
            (command "._arc" "_C" "_NON" center_tl "_NON" p_180 "_NON" p_start2)
            (command "._chprop" (entlast) "" "_C" "5" "")
            
            ;; Trazar las lineas de 15 cm hacia adentro (paralelas a 315 grados)
            (setq p_end1 (polar p_start1 (deg2rad 315) 0.15))
            (setq p_end2 (polar p_start2 (deg2rad 315) 0.15))

            (command "._pline" "_NON" p_start1 "_NON" p_end1 "")
            (command "._chprop" (entlast) "" "_C" "5" "")
            (command "._pline" "_NON" p_start2 "_NON" p_end2 "")
            (command "._chprop" (entlast) "" "_C" "5" "")

            ;; 3. Textos y Cotas
            (setq dim_off 0.3)
            (setq L_min (* (+ (* 2.0 w) (* 2.0 l_mi) 0.30) 100.0))
            (setq L_max (* (+ (* 2.0 w) (* 2.0 l_ma) 0.30) 100.0))

            ;; Texto de marca inferior
            (if (= l_mi l_ma)
              (setq text_str (strcat "(" mark ") " (itoa qty) " %%c" (itoa phi_val) " @" (rtos (* spa 100) 2 0) " L= " (rtos L_min 2 0)))
              (setq text_str (strcat "(" mark ") " (itoa qty) " %%c" (itoa phi_val) " @" (rtos (* spa 100) 2 0) " L= VAR. " (rtos L_min 2 0) " - " (rtos L_max 2 0)))
            )
            (draw-text (list (+ (car ins_p) (/ w 2.0)) (- (cadr ins_p) 1.2)) text_str "_TC")
            
            ;; Texto g= 15 cm
            (draw-text (list (+ (car center_tl) 0.15) (+ (cadr center_tl) 0.05)) "g= 15 cm" "_ML")

            ;; Cota Inferior (Ancho) - Verde
            (command "_.DIMALIGNED" "_NON" pB "_NON" pC "_T" (rtos (* w 100) 2 0) "_NON" (list (+ (car ins_p) (/ w 2.0)) (- (cadr ins_p) dim_off)))
            
            ;; Cota Superior (Ancho) - Verde
            (command "_.DIMALIGNED" "_NON" pA "_NON" pD "_T" (rtos (* w 100) 2 0) "_NON" (list (+ (car ins_p) (/ w 2.0)) (+ (cadr ins_p) h dim_off)))
            
            ;; Cota Izquierda (Alto - Verde - Variable o fija)
            (if (= l_mi l_ma)
              (command "_.DIMALIGNED" "_NON" pA "_NON" pB "_T" (rtos (* l_mi 100) 2 0) "_NON" (list (- (car ins_p) dim_off) (+ (cadr ins_p) (/ h 2.0))))
              (command "_.DIMALIGNED" "_NON" pA "_NON" pB "_T" (strcat "VAR. " (rtos (* l_mi 100) 2 0) "-" (rtos (* l_ma 100) 2 0)) "_NON" (list (- (car ins_p) (* dim_off 2.5)) (+ (cadr ins_p) (/ h 2.0))))
            )
          )

          (defun draw-l-bar (ins_p l_bar hk_len ang_deg phi_m phi_val mark qty l_mi l_ma spa is_right / pA pB pC rad text_str L_min L_max dim_off)
            (command "._-dimstyle" "_R" "GSG_ARM-COTAS")
            (setvar "FILLETRAD" (* 3.0 phi_m))
            (if is_right
              (progn
                (setq pA (list (car ins_p) (cadr ins_p)))
                (setq pB (list (+ (car ins_p) l_bar) (cadr ins_p)))
                (setq pC (polar pB (deg2rad (- 180.0 ang_deg)) hk_len))
              )
              (progn
                (setq pB (list (car ins_p) (cadr ins_p)))
                (setq pC (list (+ (car ins_p) l_bar) (cadr ins_p)))
                (setq pA (polar pB (deg2rad ang_deg) hk_len))
              )
            )
            (command "._pline" "_NON" pA "_NON" pB "_NON" pC "")
            (command "._fillet" "P" (entlast))
            (command "._chprop" (entlast) "" "_C" "5" "")
            (setq L_min (* (+ l_mi hk_len) 100.0) L_max (* (+ l_ma hk_len) 100.0))
            (if (= l_mi l_ma)
              (setq text_str (strcat "(" mark ") " (itoa qty) " %%c" (itoa phi_val) " @" (rtos (* spa 100) 2 0) " L= " (rtos L_min 2 0)))
              (setq text_str (strcat "(" mark ") " (itoa qty) " %%c" (itoa phi_val) " @" (rtos (* spa 100) 2 0) " L= VAR. " (rtos L_min 2 0) " - " (rtos L_max 2 0)))
            )
            (setq dim_off 0.3)
            (draw-text (list (+ (car ins_p) (/ l_bar 2.0)) (- (cadr ins_p) 1.2)) text_str "_TC")
            
            (if (= l_mi l_ma)
              (command "_.DIMALIGNED" "_NON" (if is_right pA pB) "_NON" (if is_right pB pC) "_T" (rtos (* l_mi 100) 2 0) "_NON" (list (+ (car ins_p) (/ l_bar 2.0)) (+ (cadr ins_p) dim_off)))
              (command "_.DIMALIGNED" "_NON" (if is_right pA pB) "_NON" (if is_right pB pC) "_T" (strcat "VAR. " (rtos (* l_mi 100) 2 0) "-" (rtos (* l_ma 100) 2 0)) "_NON" (list (+ (car ins_p) (/ l_bar 2.0)) (+ (cadr ins_p) dim_off)))
            )
            (command "_.DIMALIGNED" "_NON" (if is_right pB pA) "_NON" (if is_right pC pB) "_T" (rtos (* hk_len 100) 2 0) "_NON" (polar (if is_right pB pA) (deg2rad (if is_right (+ (- 180.0 ang_deg) 90.0) (+ ang_deg 90.0))) dim_off))
            
            (if (not (= ang_deg 90.0))
              (progn
                (command "._-dimstyle" "_R" "GSG_COTAS")
                (if is_right
                  (command "_.DIMANGULAR" "" "_NON" pB "_NON" pA "_NON" pC "_NON" (polar pB (deg2rad (- 180.0 (/ ang_deg 2.0))) 1.5))
                  (command "_.DIMANGULAR" "" "_NON" pB "_NON" pC "_NON" pA "_NON" (polar pB (deg2rad (/ ang_deg 2.0)) 1.5))
                )
                (command "._-dimstyle" "_R" "GSG_ARM-COTAS")
              )
            )
          )

          (defun draw-str-bar (ins_p l_bar phi_m phi_val mark qty l_mi l_ma spa / pA pB text_str L_min L_max dim_off)
            (command "._-dimstyle" "_R" "GSG_ARM-COTAS")
            (setq pA (list (car ins_p) (cadr ins_p)) pB (list (+ (car ins_p) l_bar) (cadr ins_p)))
            (command "._pline" "_NON" pA "_NON" pB "")
            (command "._chprop" (entlast) "" "_C" "5" "")
            (setq L_min (* l_mi 100.0) L_max (* l_ma 100.0))
            (if (= l_mi l_ma)
              (setq text_str (strcat "(" mark ") " (itoa qty) " %%c" (itoa phi_val) " L= " (rtos L_min 2 0)))
              (setq text_str (strcat "(" mark ") " (itoa qty) " %%c" (itoa phi_val) " @" (rtos (* spa 100) 2 0) " L= VAR. " (rtos L_min 2 0) " - " (rtos L_max 2 0)))
            )
            (if (> spa 0.0)
              (if (= l_mi l_ma)
                (setq text_str (strcat "(" mark ") " (itoa qty) " %%c" (itoa phi_val) " @" (rtos (* spa 100) 2 0) " L= " (rtos L_min 2 0)))
              )
            )
            (setq dim_off 0.3)
            (draw-text (list (+ (car ins_p) (/ l_bar 2.0)) (- (cadr ins_p) 1.2)) text_str "_TC")
            (if (= l_mi l_ma)
              (command "_.DIMALIGNED" "_NON" pA "_NON" pB "_T" (rtos (* l_mi 100) 2 0) "_NON" (list (+ (car ins_p) (/ l_bar 2.0)) (+ (cadr ins_p) dim_off)))
              (command "_.DIMALIGNED" "_NON" pA "_NON" pB "_T" (strcat "VAR. " (rtos (* l_mi 100) 2 0) "-" (rtos (* l_ma 100) 2 0)) "_NON" (list (+ (car ins_p) (/ l_bar 2.0)) (+ (cadr ins_p) dim_off)))
            )
          )

          ;; --- EXTRACCION DE GEOMETRIA ---
          (setq offset_res (vl-catch-all-apply 'vla-offset (list obj (- recub_m))))
          (if (not (vl-catch-all-error-p offset_res))
            (setq offset_obj (car (vlax-safearray->list (vlax-variant-value offset_res))))
            (progn
              (setq offset_res (vl-catch-all-apply 'vla-offset (list obj recub_m)))
              (if (not (vl-catch-all-error-p offset_res)) (setq offset_obj (car (vlax-safearray->list (vlax-variant-value offset_res)))))
            )
          )
          
          (if offset_obj
            (progn
              (if (> (vla-get-Area offset_obj) (vla-get-Area obj)) (progn (vla-delete offset_obj) (setq offset_obj (car (vlax-safearray->list (vlax-variant-value (vla-offset obj recub_m)))))))
              
              ;; LECTURA PURA INTACTA
              (setq coords (vlax-safearray->list (vlax-variant-value (vla-get-Coordinates offset_obj))))
              (setq pts nil i 0)
              (while (< i (length coords))
                (setq pts (append pts (list (list (nth i coords) (nth (1+ i) coords)))))
                (setq i (+ i 2))
              )
              
              (cond
                ;; ============================ EXT_IZQ ============================
                ((= "{tipo_cuadrante}" "EXT_IZQ")
                  (setq pts_by_x (vl-sort pts '(lambda (a b) (< (car a) (car b)))))
                  (setq left_pts (list (nth 0 pts_by_x) (nth 1 pts_by_x)))
                  (setq right_pts (list (nth (- (length pts) 2) pts_by_x) (nth (- (length pts) 1) pts_by_x)))
                  (setq mid_pts nil i 2)
                  (while (< i (- (length pts) 2))
                    (setq mid_pts (append mid_pts (list (nth i pts_by_x))))
                    (setq i (1+ i))
                  )
                  
                  (if (> (cadr (car left_pts)) (cadr (cadr left_pts))) (setq v1 (car left_pts) v2 (cadr left_pts)) (setq v1 (cadr left_pts) v2 (car left_pts)))
                  (if (> (cadr (car right_pts)) (cadr (cadr right_pts))) (setq v8 (car right_pts) v7 (cadr right_pts)) (setq v8 (cadr right_pts) v7 (car right_pts)))
                  
                  (setq mid_by_y (vl-sort mid_pts '(lambda (a b) (< (cadr a) (cadr b)))))
                  (setq lowest_two (list (nth 0 mid_by_y) (nth 1 mid_by_y)))
                  (setq highest_two (list (nth (- (length mid_by_y) 2) mid_by_y) (nth (- (length mid_by_y) 1) mid_by_y)))
                  (setq middle_two (list (nth 2 mid_by_y) (nth 3 mid_by_y)))
                  
                  (if (< (car (car lowest_two)) (car (cadr lowest_two))) (setq v4 (car lowest_two) v5 (cadr lowest_two)) (setq v4 (cadr lowest_two) v5 (car lowest_two)))
                  (if (< (car (car highest_two)) (car (cadr highest_two))) (setq v10 (car highest_two) v9 (cadr highest_two)) (setq v10 (cadr highest_two) v9 (car highest_two)))
                  (if (< (car (car middle_two)) (car (cadr middle_two))) (setq v3 (car middle_two) v6 (cadr middle_two)) (setq v3 (cadr middle_two) v6 (car middle_two)))

                  (setq m_top (/ (- (cadr v10) (cadr v1)) (- (car v10) (car v1))))
                  (setq ang_top (atan m_top)) (setq perp_top (+ ang_top (/ pi 2.0)))
                  (setq x1_off (+ (car v1) (* 0.18 (cos perp_top)))) (setq y1_off (+ (cadr v1) (* 0.18 (sin perp_top))))
                  (defun get-y-losa (x_target / ) (+ y1_off (* m_top (- x_target x1_off))))
                  (setq y_ext (get-y-losa (car v1)))
                  (setq t_val (/ (- (cadr v4) (cadr v3)) (- (cadr v3) (cadr v2))))
                  (setq x_end (+ (car v3) (* t_val (- (car v3) (car v2)))))

                  (setq g1_min_h 9999.0 g1_max_h -9999.0 g1_qty 0)
                  (setq x_curr (+ (car v1) 0.20))
                  (while (< x_curr (car v3))
                    (setq ray_start (list x_curr (+ (get-y-losa x_curr) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v4) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts
                      (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (get-y-losa x_curr) min_y))
                             (setq g1_min_h (min g1_min_h h) g1_max_h (max g1_max_h h) g1_qty (1+ g1_qty))))
                    (vla-delete ray_obj) (setq x_curr (+ x_curr 0.20))
                  )
                  
                  (setq g3_min_h 9999.0 g3_max_h -9999.0 g3_qty 0)
                  (setq x_curr (car v9))
                  (while (>= x_curr (car v10))
                    (setq ray_start (list x_curr (+ (cadr v8) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v4) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts
                      (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v8) min_y))
                             (setq g3_min_h (min g3_min_h h) g3_max_h (max g3_max_h h) g3_qty (1+ g3_qty))))
                    (vla-delete ray_obj) (setq x_curr (- x_curr 0.20))
                  )

                  (setq g2_min_l 9999.0 g2_max_l -9999.0 g2_qty 0)
                  (setq y_curr (cadr v8))
                  (while (>= y_curr (cadr v7))
                    (setq ray_start (list (- (car v2) 2.0) y_curr 0.0)) (setq ray_end (list (+ (car v8) 2.0) y_curr 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts
                      (progn (setq min_x (car int_pts) k 3) (while (< k (length int_pts)) (setq min_x (min min_x (nth k int_pts))) (setq k (+ k 3)))
                             (setq len_line (- (+ (car v8) 1.00) min_x))
                             (setq g2_min_l (min g2_min_l len_line) g2_max_l (max g2_max_l len_line) g2_qty (1+ g2_qty))))
                    (vla-delete ray_obj) (setq y_curr (- y_curr 0.20))
                  )
                  
                  (vla-delete offset_obj)

                  (setvar "OSMODE" old_osnap)
                  (setq ins_pt (getpoint "\\n[SINCAL] Clic para insertar tabla de despiece: "))
                  (setvar "OSMODE" 0)
                  (if ins_pt
                    (progn
                      (setq ins_x (car ins_pt) ins_y (cadr ins_pt))
                      (setq pts1 (list (list (car v1) y_ext) v1 v2 v3 (list x_end (cadr v4))))
                      (draw-custom-bar ins_pt pts1 (/ {phi_ext} 1000.0) {phi_ext} "1" (* 2 {cant_trav}))
                      
                      (setq ins_y (- ins_y 4.0))
                      ;; AQUI: Proyeccion completa para Extremo Izquierdo (Sube hasta Y de vertice 8)
                      (setq pts2 (list (list (car v8) (get-y-losa (car v8))) v8 v7 v6 v5 v4 (list (car v4) (cadr v8))))
                      (draw-custom-bar (list ins_x ins_y 0.0) pts2 (/ {phi_ext} 1000.0) {phi_ext} "2" (* 2 {cant_trav}))
                      
                      (setq ins_y (- ins_y 4.0))
                      (if (> g1_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g1_min_h g1_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "3" (* g1_qty {cant_trav}) g1_min_h g1_max_h 0.20))
                      
                      (setq ins_y (- ins_y (+ (/ (+ g1_min_h g1_max_h) 2.0) 3.0)))
                      (if (> g2_qty 0)
                        (if (= {esviaje} 0.0)
                          (draw-l-bar (list ins_x ins_y 0.0) (/ (+ g2_min_l g2_max_l) 2.0) w_estr 90.0 (/ {phi_horiz} 1000.0) {phi_horiz} "4" (* (* g2_qty 2) {cant_trav}) g2_min_l g2_max_l 0.20 nil)
                          (progn
                            (draw-l-bar (list ins_x ins_y 0.0) (/ (+ g2_min_l g2_max_l) 2.0) w_estr (- 90.0 {esviaje}) (/ {phi_horiz} 1000.0) {phi_horiz} "4" (* g2_qty {cant_trav}) g2_min_l g2_max_l 0.20 nil)
                            (setq ins_y (- ins_y 2.0))
                            (draw-l-bar (list ins_x ins_y 0.0) (/ (+ g2_min_l g2_max_l) 2.0) w_estr (+ 90.0 {esviaje}) (/ {phi_horiz} 1000.0) {phi_horiz} "4A" (* g2_qty {cant_trav}) g2_min_l g2_max_l 0.20 nil)
                          )
                        )
                      )
                      
                      (setq ins_y (- ins_y 4.0))
                      (if (> g3_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g3_min_h g3_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "5" (* g3_qty {cant_trav}) g3_min_h g3_max_h 0.20))
                      (princ "\\n[OK] Despiece generado.")
                    )
                  )
                )

                ;; ============================ EXT_DER ============================
                ((= "{tipo_cuadrante}" "EXT_DER")
                  (setq pts_by_x (vl-sort pts '(lambda (a b) (< (car a) (car b)))))
                  (setq left_pts (list (nth 0 pts_by_x) (nth 1 pts_by_x)))
                  (setq right_pts (list (nth (- (length pts) 2) pts_by_x) (nth (- (length pts) 1) pts_by_x)))
                  (setq mid_pts nil i 2)
                  (while (< i (- (length pts) 2))
                    (setq mid_pts (append mid_pts (list (nth i pts_by_x))))
                    (setq i (1+ i))
                  )
                  
                  (if (> (cadr (car left_pts)) (cadr (cadr left_pts))) (setq v4 (car left_pts) v5 (cadr left_pts)) (setq v4 (cadr left_pts) v5 (car left_pts)))
                  (if (> (cadr (car right_pts)) (cadr (cadr right_pts))) (setq v1 (car right_pts) v10 (cadr right_pts)) (setq v1 (cadr right_pts) v10 (car right_pts)))
                  
                  (setq mid_by_y (vl-sort mid_pts '(lambda (a b) (> (cadr a) (cadr b)))))
                  (setq highest_two (list (nth 0 mid_by_y) (nth 1 mid_by_y)))
                  (if (> (car (car highest_two)) (car (cadr highest_two))) (setq v2 (car highest_two) v3 (cadr highest_two)) (setq v2 (cadr highest_two) v3 (car highest_two)))
                  (setq lowest_four nil i 2)
                  (while (< i (length mid_by_y)) (setq lowest_four (append lowest_four (list (nth i mid_by_y)))) (setq i (1+ i)))
                  (setq lowest_by_x (vl-sort lowest_four '(lambda (a b) (< (car a) (car b)))))
                  (setq v6 (nth 0 lowest_by_x) v7 (nth 1 lowest_by_x))
                  (setq right_bot (list (nth (- (length lowest_by_x) 2) lowest_by_x) (nth (- (length lowest_by_x) 1) lowest_by_x)))
                  (if (> (cadr (car right_bot)) (cadr (cadr right_bot))) (setq v9 (car right_bot) v8 (cadr right_bot)) (setq v9 (cadr right_bot) v8 (car right_bot)))

                  (setq m_top (/ (- (cadr v1) (cadr v2)) (- (car v1) (car v2))))
                  (setq ang_top (atan m_top)) (setq perp_top (+ ang_top (/ pi 2.0)))
                  (setq x1_off (+ (car v2) (* 0.18 (cos perp_top)))) (setq y1_off (+ (cadr v2) (* 0.18 (sin perp_top))))
                  (defun get-y-losa (x_target / ) (+ y1_off (* m_top (- x_target x1_off))))
                  (setq y_ext (get-y-losa (car v1)))
                  (setq t_val (/ (- (cadr v8) (cadr v9)) (- (cadr v9) (cadr v10))))
                  (setq x_end (+ (car v9) (* t_val (- (car v9) (car v10)))))

                  (setq g1_min_h 9999.0 g1_max_h -9999.0 g1_qty 0)
                  (setq x_curr (- (car v1) 0.20))
                  (while (> x_curr (car v2))
                    (setq ray_start (list x_curr (+ (get-y-losa x_curr) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v8) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts
                      (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (get-y-losa x_curr) min_y))
                             (setq g1_min_h (min g1_min_h h) g1_max_h (max g1_max_h h) g1_qty (1+ g1_qty))))
                    (vla-delete ray_obj) (setq x_curr (- x_curr 0.20))
                  )
                  
                  (setq g3_min_h 9999.0 g3_max_h -9999.0 g3_qty 0)
                  (setq x_curr (car v3))
                  (while (<= x_curr (car v2))
                    (setq ray_start (list x_curr (+ (cadr v4) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v8) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts
                      (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v4) min_y))
                             (setq g3_min_h (min g3_min_h h) g3_max_h (max g3_max_h h) g3_qty (1+ g3_qty))))
                    (vla-delete ray_obj) (setq x_curr (+ x_curr 0.20))
                  )

                  (setq g2_min_l 9999.0 g2_max_l -9999.0 g2_qty 0)
                  (setq y_curr (cadr v4))
                  (while (>= y_curr (cadr v5))
                    (setq ray_start (list (+ (car v1) 2.0) y_curr 0.0)) (setq ray_end (list (- (car v4) 2.0) y_curr 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts
                      (progn (setq max_x (car int_pts) k 3) (while (< k (length int_pts)) (setq max_x (max max_x (nth k int_pts))) (setq k (+ k 3)))
                             (setq len_line (- max_x (- (car v4) 1.00)))
                             (setq g2_min_l (min g2_min_l len_line) g2_max_l (max g2_max_l len_line) g2_qty (1+ g2_qty))))
                    (vla-delete ray_obj) (setq y_curr (- y_curr 0.20))
                  )
                  
                  (vla-delete offset_obj)

                  (setvar "OSMODE" old_osnap)
                  (setq ins_pt (getpoint "\\n[SINCAL] Clic para insertar tabla de despiece: "))
                  (setvar "OSMODE" 0)
                  (if ins_pt
                    (progn
                      (setq ins_x (car ins_pt) ins_y (cadr ins_pt))
                      (setq pts1 (list (list (car v1) y_ext) v1 v10 v9 (list x_end (cadr v8))))
                      (draw-custom-bar ins_pt pts1 (/ {phi_ext} 1000.0) {phi_ext} "1" (* 2 {cant_trav}))
                      
                      (setq ins_y (- ins_y 4.0))
                      ;; AQUI: Proyeccion completa para Extremo Derecho (Sube hasta Y de vertice 4)
                      (setq pts2 (list (list (car v4) (get-y-losa (car v4))) v4 v5 v6 v7 v8 (list (car v8) (cadr v4))))
                      (draw-custom-bar (list ins_x ins_y 0.0) pts2 (/ {phi_ext} 1000.0) {phi_ext} "2" (* 2 {cant_trav}))
                      
                      (setq ins_y (- ins_y 4.0))
                      (if (> g1_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g1_min_h g1_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "3" (* g1_qty {cant_trav}) g1_min_h g1_max_h 0.20))
                      
                      (setq ins_y (- ins_y (+ (/ (+ g1_min_h g1_max_h) 2.0) 3.0)))
                      (if (> g2_qty 0)
                        (if (= {esviaje} 0.0)
                          (draw-l-bar (list ins_x ins_y 0.0) (/ (+ g2_min_l g2_max_l) 2.0) w_estr 90.0 (/ {phi_horiz} 1000.0) {phi_horiz} "4" (* (* g2_qty 2) {cant_trav}) g2_min_l g2_max_l 0.20 t)
                          (progn
                            (draw-l-bar (list ins_x ins_y 0.0) (/ (+ g2_min_l g2_max_l) 2.0) w_estr (- 90.0 {esviaje}) (/ {phi_horiz} 1000.0) {phi_horiz} "4" (* g2_qty {cant_trav}) g2_min_l g2_max_l 0.20 t)
                            (setq ins_y (- ins_y 2.0))
                            (draw-l-bar (list ins_x ins_y 0.0) (/ (+ g2_min_l g2_max_l) 2.0) w_estr (+ 90.0 {esviaje}) (/ {phi_horiz} 1000.0) {phi_horiz} "4A" (* g2_qty {cant_trav}) g2_min_l g2_max_l 0.20 t)
                          )
                        )
                      )
                      
                      (setq ins_y (- ins_y 4.0))
                      (if (> g3_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g3_min_h g3_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "5" (* g3_qty {cant_trav}) g3_min_h g3_max_h 0.20))
                      (princ "\\n[OK] Despiece generado.")
                    )
                  )
                )

                ;; ============================ INT_TOPE ============================
                ((= "{tipo_cuadrante}" "INT_TOPE")
                  (setq pts_by_y (vl-sort pts '(lambda (a b) (> (cadr a) (cadr b)))))
                  
                  (setq pair1 (vl-sort (list (nth 0 pts_by_y) (nth 1 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v1 (car pair1) v16 (cadr pair1))
                  (setq pair2 (vl-sort (list (nth 2 pts_by_y) (nth 3 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v2 (car pair2) v15 (cadr pair2))
                  (setq pair3 (vl-sort (list (nth 4 pts_by_y) (nth 5 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v3 (car pair3) v14 (cadr pair3))
                  (setq pair4 (vl-sort (list (nth 6 pts_by_y) (nth 7 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v8 (car pair4) v9 (cadr pair4))
                  (setq pair5 (vl-sort (list (nth 8 pts_by_y) (nth 9 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v4 (car pair5) v13 (cadr pair5))
                  (setq pair6 (vl-sort (list (nth 10 pts_by_y) (nth 11 pts_by_y)) '(lambda (a b) (< (car a) (car b))))) (setq v5 (car pair6) v12 (cadr pair6))
                  
                  (setq bot4 nil i 12)
                  (while (< i (length pts_by_y)) (setq bot4 (append bot4 (list (nth i pts_by_y)))) (setq i (1+ i)))
                  (setq bot4 (vl-sort bot4 '(lambda (a b) (< (car a) (car b)))))
                  (setq v6 (nth 0 bot4) v7 (nth 1 bot4) v10 (nth 2 bot4) v11 (nth 3 bot4))

                  (setq m_top (/ (- (cadr v16) (cadr v1)) (- (car v16) (car v1))))
                  (setq ang_top (atan m_top)) (setq perp_top (+ ang_top (/ pi 2.0)))
                  (setq x1_off (+ (car v1) (* 0.18 (cos perp_top)))) (setq y1_off (+ (cadr v1) (* 0.18 (sin perp_top))))
                  (defun get-y-losa (x_target / ) (+ y1_off (* m_top (- x_target x1_off))))

                  (setq dist_sacado (- (car v9) (car v8)))

                  ;; G1 (Left)
                  (setq g1_min_h 9999.0 g1_max_h -9999.0 g1_qty 0)
                  (setq x_curr (car v2))
                  (while (<= x_curr (car v8))
                    (setq ray_start (list x_curr (+ (cadr v1) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v6) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v3) min_y)) (setq g1_min_h (min g1_min_h h) g1_max_h (max g1_max_h h) g1_qty (1+ g1_qty))))
                    (vla-delete ray_obj) (setq x_curr (+ x_curr 0.20))
                  )
                  
                  ;; G2 (Right)
                  (setq g2_min_h 9999.0 g2_max_h -9999.0 g2_qty 0)
                  (setq x_curr (car v15))
                  (while (>= x_curr (car v9))
                    (setq ray_start (list x_curr (+ (cadr v16) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v11) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v14) min_y)) (setq g2_min_h (min g2_min_h h) g2_max_h (max g2_max_h h) g2_qty (1+ g2_qty))))
                    (vla-delete ray_obj) (setq x_curr (- x_curr 0.20))
                  )

                  ;; G3 (Center)
                  (setq g3_min_h 9999.0 g3_max_h -9999.0 g3_qty 0)
                  (setq num_spaces (fix (/ dist_sacado 0.20))) (setq pad_g3 (/ (- dist_sacado (* num_spaces 0.20)) 2.0))
                  (setq i_sac 0)
                  (while (<= i_sac num_spaces)
                    (setq x_curr (+ (car v8) pad_g3 (* i_sac 0.20)))
                    (setq ray_start (list x_curr (+ (cadr v1) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v8) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (get-y-losa x_curr) min_y)) (setq g3_min_h (min g3_min_h h) g3_max_h (max g3_max_h h) g3_qty (1+ g3_qty))))
                    (vla-delete ray_obj) (setq i_sac (1+ i_sac))
                  )

                  ;; Grises
                  (setq m_horiz (/ (- (cadr v14) (cadr v3)) (- (car v14) (car v3))))
                  (setq offset_h 0.20 y_L (- (cadr v3) offset_h) y_R (- (cadr v14) offset_h) y_limit (+ (max (cadr v8) (cadr v9)) 0.20))
                  (setq g_gri_min_l 9999.0 g_gri_max_l -9999.0 g_gri_qty 1) 
                  (setq g_gri_min_l (distance v3 v14) g_gri_max_l (distance v3 v14))
                  (while (>= (min y_L y_R) y_limit)
                    (setq ray_start (list (- (car v3) 1.0) (- y_L (* m_horiz 1.0)) 0.0)) (setq ray_end (list (+ (car v14) 1.0) (+ y_R (* m_horiz 1.0)) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts (progn (setq min_x (car int_pts) max_x min_x k 3) (while (< k (length int_pts)) (setq min_x (min min_x (nth k int_pts))) (setq max_x (max max_x (nth k int_pts))) (setq k (+ k 3)))
                             (setq real_y_L (+ y_L (* m_horiz (- min_x (car v3))))) (setq real_y_R (+ y_L (* m_horiz (- max_x (car v3)))))
                             (setq len_line (distance (list min_x real_y_L) (list max_x real_y_R)))
                             (setq g_gri_min_l (min g_gri_min_l len_line) g_gri_max_l (max g_gri_max_l len_line) g_gri_qty (1+ g_gri_qty))))
                    (vla-delete ray_obj) (setq offset_h (+ offset_h 0.20)) (setq y_L (- (cadr v3) offset_h)) (setq y_R (- (cadr v14) offset_h))
                  )
                  
                  (vla-delete offset_obj)

                  (setvar "OSMODE" old_osnap)
                  (setq ins_pt (getpoint "\\n[SINCAL] Clic para insertar tabla de despiece: "))
                  (setvar "OSMODE" 0)
                  (if ins_pt
                    (progn
                      (setq ins_x (car ins_pt) ins_y (cadr ins_pt))
                      (setq pts1 (list v3 v4 v5 v6 v7 (list (car v7) (get-y-losa (car v7)))))
                      (draw-custom-bar ins_pt pts1 (/ {phi_ext} 1000.0) {phi_ext} "1" (* 2 {cant_trav}))
                      
                      (setq ins_y (- ins_y 4.0))
                      (setq raw_len (+ dist_sacado 1.40)) (setq rnd_len (* (fix (+ (/ raw_len 0.10) 0.5)) 0.10)) (setq ext (/ (- rnd_len dist_sacado) 2.0))
                      (setq pts2 (list (list (- (car v8) ext) (cadr v8)) (list (+ (car v9) ext) (cadr v9))))
                      (draw-custom-bar (list ins_x ins_y 0.0) pts2 (/ {phi_ext} 1000.0) {phi_ext} "2" (* 2 {cant_trav}))
                      
                      (setq ins_y (- ins_y 3.0))
                      (setq pts3 (list v14 v13 v12 v11 v10 (list (car v10) (get-y-losa (car v10)))))
                      (draw-custom-bar (list ins_x ins_y 0.0) pts3 (/ {phi_ext} 1000.0) {phi_ext} "3" (* 2 {cant_trav}))
                      
                      (setq ins_y (- ins_y 4.0))
                      (if (> g1_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g1_min_h g1_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "4" (* g1_qty {cant_trav}) g1_min_h g1_max_h 0.20))
                      
                      (setq ins_y (- ins_y (+ (/ (+ g2_min_h g2_max_h) 2.0) 3.0)))
                      (if (> g2_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g2_min_h g2_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "5" (* g2_qty {cant_trav}) g2_min_h g2_max_h 0.20))
                      
                      (setq ins_y (- ins_y (+ (/ (+ g3_min_h g3_max_h) 2.0) 3.0)))
                      (if (> g3_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g3_min_h g3_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "6" (* g3_qty {cant_trav}) g3_min_h g3_max_h 0.20))

                      (setq ins_y (- ins_y (+ (/ (+ g3_min_h g3_max_h) 2.0) 3.0)))
                      (draw-str-bar (list ins_x ins_y 0.0) (/ (+ g_gri_min_l g_gri_max_l) 2.0) (/ {phi_horiz} 1000.0) {phi_horiz} "7" (* (* g_gri_qty 2) {cant_trav}) g_gri_min_l g_gri_max_l 0.0)

                      (princ "\\n[OK] Despiece generado.")
                    )
                  )
                )

                ;; ============================ INT_MACIZO ============================
                ((= "{tipo_cuadrante}" "INT_MACIZO")
                  (setq pts_by_x (vl-sort pts '(lambda (a b) (< (car a) (car b)))))
                  (setq left_pts nil right_pts nil i 0)
                  (while (< i 6) (setq left_pts (append left_pts (list (nth i pts_by_x)))) (setq i (1+ i)))
                  (setq i 6)
                  (while (< i 12) (setq right_pts (append right_pts (list (nth i pts_by_x)))) (setq i (1+ i)))
                  
                  (setq left_by_y (vl-sort left_pts '(lambda (a b) (> (cadr a) (cadr b)))))
                  (setq right_by_y (vl-sort right_pts '(lambda (a b) (> (cadr a) (cadr b)))))
                  
                  (setq v1 (nth 0 left_by_y) v2 (nth 1 left_by_y) v3 (nth 2 left_by_y) v4 (nth 3 left_by_y) v5 (nth 4 left_by_y) v6 (nth 5 left_by_y))
                  (setq v12 (nth 0 right_by_y) v11 (nth 1 right_by_y) v10 (nth 2 right_by_y) v9 (nth 3 right_by_y) v8 (nth 4 right_by_y) v7 (nth 5 right_by_y))

                  (setq m_top (/ (- (cadr v12) (cadr v1)) (- (car v12) (car v1))))
                  (setq ang_top (atan m_top)) (setq perp_top (+ ang_top (/ pi 2.0)))
                  (setq x1_off (+ (car v1) (* 0.18 (cos perp_top)))) (setq y1_off (+ (cadr v1) (* 0.18 (sin perp_top))))
                  (defun get-y-losa (x_target / ) (+ y1_off (* m_top (- x_target x1_off))))

                  (setq g1_min_h 9999.0 g1_max_h -9999.0 g1_qty 0)
                  (setq x_curr (car v2))
                  (while (<= x_curr (car v1))
                    (setq ray_start (list x_curr (+ (cadr v3) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v6) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v3) min_y)) (setq g1_min_h (min g1_min_h h) g1_max_h (max g1_max_h h) g1_qty (1+ g1_qty))))
                    (vla-delete ray_obj) (setq x_curr (+ x_curr 0.20))
                  )
                  
                  (setq g2_min_h 9999.0 g2_max_h -9999.0 g2_qty 0)
                  (setq x_curr (car v11))
                  (while (>= x_curr (car v12))
                    (setq ray_start (list x_curr (+ (cadr v10) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v7) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (cadr v10) min_y)) (setq g2_min_h (min g2_min_h h) g2_max_h (max g2_max_h h) g2_qty (1+ g2_qty))))
                    (vla-delete ray_obj) (setq x_curr (- x_curr 0.20))
                  )

                  (setq g3_min_h 9999.0 g3_max_h -9999.0 g3_qty 0)
                  (setq dist_sacado (- (car v12) (car v1))) (setq num_spaces (fix (/ dist_sacado 0.20))) (setq pad_g3 (/ (- dist_sacado (* num_spaces 0.20)) 2.0))
                  (setq i_sac 0)
                  (while (<= i_sac num_spaces)
                    (setq x_curr (+ (car v1) pad_g3 (* i_sac 0.20)))
                    (setq ray_start (list x_curr (+ (cadr v1) 1.0) 0.0)) (setq ray_end (list x_curr (- (cadr v6) 1.0) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts (progn (setq min_y (cadr int_pts) k 4) (while (< k (length int_pts)) (setq min_y (min min_y (nth k int_pts))) (setq k (+ k 3)))
                             (setq h (- (get-y-losa x_curr) min_y)) (setq g3_min_h (min g3_min_h h) g3_max_h (max g3_max_h h) g3_qty (1+ g3_qty))))
                    (vla-delete ray_obj) (setq i_sac (1+ i_sac))
                  )

                  (setq m_horiz (/ (- (cadr v10) (cadr v3)) (- (car v10) (car v3))))
                  (setq offset_h 0.20 y_L (- (cadr v3) offset_h) y_R (- (cadr v10) offset_h) y_limit (max (cadr v4) (cadr v9)))
                  (setq g_gri_min_l 9999.0 g_gri_max_l -9999.0 g_gri_qty 1) 
                  (setq g_gri_min_l (distance v3 v10) g_gri_max_l (distance v3 v10))
                  (while (>= (min y_L y_R) y_limit)
                    (setq ray_start (list (- (car v3) 1.0) (- y_L (* m_horiz 1.0)) 0.0)) (setq ray_end (list (+ (car v10) 1.0) (+ y_R (* m_horiz 1.0)) 0.0))
                    (setq ray_obj (vlax-ename->vla-object (entmakex (list '(0 . "LINE") (cons 10 ray_start) (cons 11 ray_end)))))
                    (setq int_pts (vlax-invoke ray_obj 'IntersectWith offset_obj acExtendNone))
                    (if int_pts (progn (setq min_x (car int_pts) max_x min_x k 3) (while (< k (length int_pts)) (setq min_x (min min_x (nth k int_pts))) (setq max_x (max max_x (nth k int_pts))) (setq k (+ k 3)))
                             (setq real_y_L (+ y_L (* m_horiz (- min_x (car v3))))) (setq real_y_R (+ y_L (* m_horiz (- max_x (car v3)))))
                             (setq len_line (distance (list min_x real_y_L) (list max_x real_y_R)))
                             (setq g_gri_min_l (min g_gri_min_l len_line) g_gri_max_l (max g_gri_max_l len_line) g_gri_qty (1+ g_gri_qty))))
                    (vla-delete ray_obj) (setq offset_h (+ offset_h 0.20)) (setq y_L (- (cadr v3) offset_h)) (setq y_R (- (cadr v10) offset_h))
                  )
                  
                  (vla-delete offset_obj)

                  (setvar "OSMODE" old_osnap)
                  (setq ins_pt (getpoint "\\n[SINCAL] Clic para insertar tabla de despiece: "))
                  (setvar "OSMODE" 0)
                  (if ins_pt
                    (progn
                      (setq ins_x (car ins_pt) ins_y (cadr ins_pt))
                      ;; AQUI: Restaurada la linea perfecta v3 a v10 SIN DIAGONAL.
                      (setq pts1 (list (list (car v1) (get-y-losa (car v1))) v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 (list (car v12) (get-y-losa (car v12)))))
                      (draw-custom-bar ins_pt pts1 (/ {phi_ext} 1000.0) {phi_ext} "1" (* 2 {cant_trav}))
                      
                      (setq ins_y (- ins_y 4.0))
                      (if (> g1_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g1_min_h g1_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "2" (* g1_qty {cant_trav}) g1_min_h g1_max_h 0.20))
                      
                      (setq ins_y (- ins_y (+ (/ (+ g2_min_h g2_max_h) 2.0) 3.0)))
                      (if (> g2_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g2_min_h g2_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "3" (* g2_qty {cant_trav}) g2_min_h g2_max_h 0.20))
                      
                      (setq ins_y (- ins_y (+ (/ (+ g3_min_h g3_max_h) 2.0) 3.0)))
                      (if (> g3_qty 0) (draw-stirrup (list ins_x ins_y 0.0) w_estr (/ (+ g3_min_h g3_max_h) 2.0) (/ {phi_estr} 1000.0) {phi_estr} "4" (* g3_qty {cant_trav}) g3_min_h g3_max_h 0.20))

                      (setq ins_y (- ins_y (+ (/ (+ g3_min_h g3_max_h) 2.0) 3.0)))
                      (draw-str-bar (list ins_x ins_y 0.0) (/ (+ g_gri_min_l g_gri_max_l) 2.0) (/ {phi_horiz} 1000.0) {phi_horiz} "5" (* (* g_gri_qty 2) {cant_trav}) g_gri_min_l g_gri_max_l 0.0)

                      (princ "\\n[OK] Despiece generado.")
                    )
                  )
                )

                ;; ========================================================
                ;; ALGORITMO CUADRANTE VIGA
                ;; ========================================================
                ((= "{tipo_cuadrante}" "INT_VIGA")
                  (setq pts_by_y (vl-sort pts '(lambda (a b) (> (cadr a) (cadr b)))))
                  (setq v1 (nth 0 pts_by_y) v2 (nth 1 pts_by_y) v3 (nth 2 pts_by_y) v4 (nth 3 pts_by_y))
                  (setq len_viga (/ {largo_viga} 100.0))
                  (setq half_l (/ len_viga 2.0))
                  (setq x_mid (/ (+ (car v1) (car v2)) 2.0))
                  (setq y_curr (cadr v1)) (setq y_min (cadr v3))
                  (setq g_qty 0)
                  (while (>= y_curr y_min) (setq g_qty (1+ g_qty)) (setq y_curr (- y_curr 0.20)))
                  (vla-delete offset_obj)

                  (setvar "OSMODE" old_osnap)
                  (setq ins_pt (getpoint "\\n[SINCAL] Clic para insertar tabla de despiece: "))
                  (setvar "OSMODE" 0)
                  (if ins_pt
                    (progn
                      (draw-str-bar ins_pt len_viga (/ {phi_horiz} 1000.0) {phi_horiz} "1" (* (* g_qty 2) {cant_trav}) len_viga len_viga 0.20)
                      (princ "\\n[OK] Despiece generado.")
                    )
                  )
                )

              )
            )
            (alert "Fallo interno al procesar el recubrimiento de la polilinea.")
          )
          (setvar "OSMODE" old_osnap)
          (princ)
        )"""

        with open(ruta_temp, 'w', encoding='utf-8') as f:
            f.write(lisp_code)

        self.parent_app.cancelar_comando_vivo = False
        ruta_lisp = ruta_temp.replace("\\", "\\\\")
        threading.Thread(target=self.parent_app._hilo_comando_en_vivo, args=(
            f'(load "{ruta_lisp}") (c:SINCAL-DESPIECE-TRAV)\n',), daemon=True).start()

    def cargar_json_bim(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Archivo JSON del Proyecto", filetypes=[("JSON Files", "*.json")])
        if not ruta:
            return
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)

            e_data = datos.get("estribos", {})
            for ent, key in [(self.ent_z_largo, "dado_muro_frontal_largo_entrada"),
                             (self.ent_z_ancho, "dado_muro_frontal_ancho_entrada"),
                             (self.ent_z_alto, "dado_muro_frontal_espesor_entrada")]:
                if key in e_data:
                    ent.delete(0, 'end')
                    ent.insert(0, str(e_data.get(key, 0) / 10.0))

            if "elementos_comunes" in datos and "travesanos" in datos["elementos_comunes"]:
                espesor_mm = datos["elementos_comunes"]["travesanos"].get(
                    "espesor_travesano")
                if espesor_mm is not None:
                    self.ent_t_espesor.delete(0, 'end')
                    self.ent_t_espesor.insert(0, str(espesor_mm / 10.0))

            if "parametros_generales" in datos:
                esviaje = datos["parametros_generales"].get(
                    "angulo_esviaje_puente")
                if esviaje is not None:
                    self.ent_t_esviaje.delete(0, 'end')
                    self.ent_t_esviaje.insert(0, str(esviaje))

            nombre_archivo = os.path.basename(ruta)
            self.lbl_json_status.configure(
                text=f"Archivo: {nombre_archivo}", text_color="#007FFF")
            self.parent_app.log_r(f"[*] JSON cargado: {nombre_archivo}")
            messagebox.showinfo(
                "BIM", "Datos mapeados exitosamente en centímetros y grados.")
        except Exception as e:
            messagebox.showerror("Error JSON", f"Fallo al leer archivo:\n{e}")
