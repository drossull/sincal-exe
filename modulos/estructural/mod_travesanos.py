import os
import threading
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image

RUTA_LOCAL_APP = os.path.join(os.getenv('APPDATA'), "Estandar SINCAL")

class ModTravesanos(ctk.CTkFrame):
    def __init__(self, master, parent_app, **kwargs):
        super().__init__(master, **kwargs)
        self.parent_app = parent_app
        self.setup_ui()

    def setup_ui(self):
        fuente_subtitulo = ("Consolas", 18, "bold")
        fuente_normal = ("Consolas", 12)

        self.tab_sub_travesanos = ctk.CTkTabview(self, fg_color="#1E1E1E", segmented_button_selected_color="#005BBF")
        self.tab_sub_travesanos.pack(fill="both", expand=True)
        self.tab_sub_travesanos._segmented_button.configure(font=fuente_normal)

        tab_trav_main = self.tab_sub_travesanos.add("Configuración y Generación")

        frame_params = ctk.CTkFrame(tab_trav_main, fg_color="transparent")
        frame_params.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_params, text="I. PARÁMETROS GLOBALES:", font=fuente_subtitulo, text_color="#007FFF").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        btn_ayuda = ctk.CTkButton(frame_params, text="❓ Abrir ayuda", font=fuente_normal, width=100, fg_color="#333333", hover_color="#555555", corner_radius=0, border_width=1, border_color="#555555", command=self.mostrar_ayuda_travesano)
        btn_ayuda.grid(row=0, column=4, columnspan=2, sticky="e", padx=5, pady=(0, 10))

        ctk.CTkLabel(frame_params, text="Recubrimiento general (cm):", font=fuente_normal).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.ent_t_rec = ctk.CTkEntry(frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_rec.grid(row=1, column=1, padx=5, pady=5)
        self.ent_t_rec.insert(0, "2.5")

        ctk.CTkLabel(frame_params, text="Espesor del travesaño (cm):", font=fuente_normal).grid(row=1, column=2, sticky="w", padx=20, pady=5)
        self.ent_t_espesor = ctk.CTkEntry(frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_espesor.grid(row=1, column=3, padx=5, pady=5)
        self.ent_t_espesor.insert(0, "25")

        ctk.CTkLabel(frame_params, text="Ángulo de esviaje (°):", font=fuente_normal).grid(row=1, column=4, sticky="w", padx=20, pady=5)
        self.ent_t_esviaje = ctk.CTkEntry(frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_esviaje.grid(row=1, column=5, padx=5, pady=5)
        self.ent_t_esviaje.insert(0, "0")

        ctk.CTkLabel(frame_params, text="Ø Fierros externos (mm):", font=fuente_normal).grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.ent_t_phi_ext = ctk.CTkEntry(frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_phi_ext.grid(row=2, column=1, padx=5, pady=5)
        self.ent_t_phi_ext.insert(0, "22")

        ctk.CTkLabel(frame_params, text="Ø Fierros horizontales (mm):", font=fuente_normal).grid(row=2, column=2, sticky="w", padx=20, pady=5)
        self.ent_t_phi_horiz = ctk.CTkEntry(frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_phi_horiz.grid(row=2, column=3, padx=5, pady=5)
        self.ent_t_phi_horiz.insert(0, "12")

        ctk.CTkLabel(frame_params, text="Ø Estribos (mm):", font=fuente_normal).grid(row=2, column=4, sticky="w", padx=20, pady=5)
        self.ent_t_phi_estr = ctk.CTkEntry(frame_params, font=fuente_normal, width=60, corner_radius=0)
        self.ent_t_phi_estr.grid(row=2, column=5, padx=5, pady=5)
        self.ent_t_phi_estr.insert(0, "12")

        frame_botones_t = ctk.CTkFrame(tab_trav_main, fg_color="transparent")
        frame_botones_t.pack(fill="x", padx=10, pady=15)

        ctk.CTkLabel(frame_botones_t, text="II. SELECCIÓN DE CUADRANTE (AutoCAD):", font=fuente_subtitulo, text_color="#007FFF").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        btn_ext_izq = ctk.CTkButton(frame_botones_t, text="1. Extremo Izquierdo", font=fuente_normal, fg_color="#444444", hover_color="#007FFF", corner_radius=0, command=lambda: self.generar_travesano_cad("EXT_IZQ"))
        btn_ext_izq.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        btn_ext_der = ctk.CTkButton(frame_botones_t, text="2. Extremo Derecho", font=fuente_normal, fg_color="#444444", hover_color="#007FFF", corner_radius=0, command=lambda: self.generar_travesano_cad("EXT_DER"))
        btn_ext_der.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        btn_tope = ctk.CTkButton(frame_botones_t, text="3. Cuadrante sobre Tope", font=fuente_normal, fg_color="#444444", hover_color="#007FFF", corner_radius=0, command=lambda: self.generar_travesano_cad("INT_TOPE"))
        btn_tope.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        btn_macizo = ctk.CTkButton(frame_botones_t, text="4. Cuadrante Macizo", font=fuente_normal, fg_color="#444444", hover_color="#007FFF", corner_radius=0, command=lambda: self.generar_travesano_cad("INT_MACIZO"))
        btn_macizo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        frame_botones_t.grid_columnconfigure(0, weight=1)
        frame_botones_t.grid_columnconfigure(1, weight=1)

    def mostrar_ayuda_travesano(self):
        visor = ctk.CTkToplevel(self)
        visor.title("SINCAL - Ayuda Cuadrantes de Travesaño")
        visor.geometry("900x350")
        visor.transient(self)

        ruta_img = os.path.join(RUTA_LOCAL_APP, "mapas", "ayuda_travesano.png")
        if not os.path.exists(ruta_img):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ruta_img = os.path.abspath(os.path.join(base_dir, "mapas", "ayuda_travesano.png"))

        if os.path.exists(ruta_img):
            try:
                img = Image.open(ruta_img)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(850, 300))
                lbl_img = ctk.CTkLabel(visor, image=ctk_img, text="")
                lbl_img.pack(fill="both", expand=True, padx=10, pady=10)
            except Exception as e:
                ctk.CTkLabel(visor, text=f"Error cargando imagen:\n{e}").pack(pady=20)
        else:
            ctk.CTkLabel(visor, text=f"No se encontró la imagen de ayuda en:\n{ruta_img}\n\nPor favor, guarda el DXF como 'ayuda_travesano.png' en la carpeta 'mapas'.").pack(pady=20)

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

        ruta_temp = os.path.join(RUTA_LOCAL_APP, f"Travesano_{tipo_cuadrante}.lsp")
        ruta_lisp = ruta_temp.replace("\\", "\\\\")

        lisp_code = f"""(defun c:SINCAL-TRAVESANO (/ ent obj old_osnap recub_m offset_obj coords i pts pts_by_x left_pts right_pts mid_pts mid_by_y lowest_two highest_two middle_two v1 v2 v3 v4 v5 v6 v7 v8 v9 v10 y_ext dx dy t_val x_end y_curr x_curr ray_start ray_end ray_obj int_pts min_x max_x min_y k lowest_four lowest_by_x)
          (vl-load-com)
          (setvar "CMDECHO" 0)
          (setq old_osnap (getvar "OSMODE"))
          (setvar "OSMODE" 0)
          
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
                  
                  (setq offset_obj (car (vlax-safearray->list (vlax-variant-value (vla-offset obj (- recub_m))))))
                  (if (> (vla-get-Area offset_obj) (vla-get-Area obj))
                    (progn
                      (vla-delete offset_obj)
                      (setq offset_obj (car (vlax-safearray->list (vlax-variant-value (vla-offset obj recub_m)))))
                    )
                  )
                  
                  (setq coords (vlax-safearray->list (vlax-variant-value (vla-get-Coordinates offset_obj))))
                  (setq pts nil i 0)
                  (while (< i (length coords))
                    (setq pts (append pts (list (list (nth i coords) (nth (1+ i) coords)))))
                    (setq i (+ i 2))
                  )
                  
                  (if (= (length pts) 10)
                    (cond
                      ;; ========================================================
                      ;; ALGORITMO EXTREMO IZQUIERDO (Original Exacto)
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
                        
                        (command "._pline" "_NON" v8 "_NON" v7 "_NON" v6 "_NON" v5 "_NON" v4 "_NON" (list (car v4) y_ext) "")
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
                              (command "._pline" "_NON" (list min_x y_curr) "_NON" (list (+ (car v8) 0.80) y_curr) "")
                              (command "._chprop" (entlast) "" "_C" "6" "")
                            )
                          )
                          (vla-delete ray_obj)
                          (setq y_curr (- y_curr 0.20))
                        )
                        
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
                        
                        ;; LINEA 1
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
                        
                        ;; LINEA 2
                        (command "._pline" "_NON" v3 "_NON" v4 "_NON" v5 "_NON" v6 "_NON" v7 "_NON" v8 "_NON" v9 "_NON" (list (car v9) y_ext) "")
                        (command "._chprop" (entlast) "" "_C" "1" "")
                        
                        ;; MAGENTAS
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
                        
                        ;; VERDES G1
                        (setq x_curr (- (car v1) 0.20))
                        (while (> x_curr (car v9))
                          (setq ray_start (list x_curr (+ y_ext 1.0) 0.0))
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
                              (command "._pline" "_NON" (list x_curr y_ext) "_NON" (list x_curr min_y) "")
                              (command "._chprop" (entlast) "" "_C" "3" "")
                            )
                          )
                          (vla-delete ray_obj)
                          (setq x_curr (- x_curr 0.20))
                        )
                        
                        ;; VERDES G2
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
                    (alert "Fallo de Topologia: La polilinea debe tener exactamente 10 vertices para los cuadrantes extremos.\\nUse BOUNDARY o revise su dibujo.")
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
        threading.Thread(target=self.parent_app._hilo_comando_en_vivo, args=(f'(load "{ruta_lisp}") (c:SINCAL-TRAVESANO)\n',), daemon=True).start()