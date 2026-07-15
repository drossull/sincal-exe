;;; =========================================================================
;;; COMANDO: VRAP (Versión Multiselección Centrada)
;;; Selecciona múltiples recuadros en el Model y los envía al Layout
;;; generándolos como viewports centrados y escalados automáticamente.
;;; =========================================================================
(defun c:VRAP (/ pt1 pt2 lst_areas idx area pA pB dx dy lim_min lim_max 
                    paper_w paper_h max_vp_w max_vp_h scale_factor vp_w vp_h 
                    offset ctr vp_p1 vp_p2 origOsmode origCmdecho)
  (vl-load-com)
  
  (setq origOsmode (getvar "OSMODE"))
  (setq origCmdecho (getvar "CMDECHO"))
  (setvar "CMDECHO" 0)

  ;; 1. Forzar ir al Model Space para iniciar la selección masiva
  (if (= (getvar "TILEMODE") 0)
    (setvar "TILEMODE" 1)
  )

  (princ "\n--- MÓDULO SINCAL: MULTI-SELECCIÓN EN MODEL ---")
  (princ "\nSeleccione las ventanas de los detalles. Al finalizar, presione ENTER sin seleccionar nada.")
  
  (setq lst_areas nil)
  (setq pt1 T)

  ;; 2. Bucle de captura en Model Space
  (while pt1
    (setq pt1 (getpoint (strcat "\n[" (itoa (1+ (length lst_areas))) "] Esquina de recuadro (o ENTER para procesar): ")))
    (if pt1
      (progn
        (setq pt2 (getcorner pt1 " -> Esquina opuesta: "))
        (if pt2
          (progn
            ;; Guardamos la pareja de puntos en nuestra lista
            (setq lst_areas (cons (list pt1 pt2) lst_areas))
            (princ (strcat "\n[SINCAL] Detalle " (itoa (length lst_areas)) " registrado con éxito."))
          )
          (setq pt1 nil) ; Si cancela el segundo punto, detenemos
        )
      )
    )
  )

  ;; 3. Procesamiento masivo en el Layout
  (if (and lst_areas (> (length lst_areas) 0))
    (progn
      ;; Volteamos la lista para que se creen en el mismo orden en que se seleccionaron
      (setq lst_areas (reverse lst_areas))
      
      ;; Cambiar al Layout activo
      (setvar "TILEMODE" 0)
      
      ;; Forzar estar en el Paper Space puro (no dentro de otro viewport)
      (command "_.PSPACE")
      
      (setq idx 0)
      (setvar "OSMODE" 0) ; Apagamos snaps para que no se alteren las coordenadas en papel

      (foreach area lst_areas
        (setq pA (car area))
        (setq pB (cadr area))
        
        ;; Medidas del recuadro del Model
        (setq dx (abs (- (car pB) (car pA))))
        (setq dy (abs (- (cadr pB) (cadr pA))))
        
        (if (and (> dx 0) (> dy 0))
          (progn
            ;; Obtener límites de la lámina actual (Paper Space)
            (setq lim_min (getvar "LIMMIN")
                  lim_max (getvar "LIMMAX")
                  paper_w (- (car lim_max) (car lim_min))
                  paper_h (- (cadr lim_max) (cadr lim_min))
            )
            
            ;; Fallback por si los límites no están inicializados
            (if (or (<= paper_w 1.0) (<= paper_h 1.0))
              (setq max_vp_w 200.0 max_vp_h 150.0)
              (setq max_vp_w (* paper_w 0.40) ; Ajustamos al 40% del ancho de la lámina
                    max_vp_h (* paper_h 0.40) ; Ajustamos al 40% del alto de la lámina
              )
            )
            
            ;; Factor de escala para que el Viewport mantenga la proporción del Model
            (setq scale_factor (min (/ max_vp_w dx) (/ max_vp_h dy))
                  vp_w (* dx scale_factor)
                  vp_h (* dy scale_factor)
            )
            
            ;; Aplicamos desfase diagonal (cascada de 10mm) para que no se tapen perfectamente
            (setq offset (* idx 10.0))
            
            ;; Centro geométrico de la lámina + desfase
            (setq ctr (list (+ (* 0.5 (+ (car lim_min) (car lim_max))) offset)
                            (+ (* 0.5 (+ (cadr lim_min) (cadr lim_max))) offset)
                            0.0)
            )
            
            ;; Coordenadas finales de las esquinas del Viewport en papel
            (setq vp_p1 (list (- (car ctr) (* 0.5 vp_w)) (- (cadr ctr) (* 0.5 vp_h)) 0.0)
                  vp_p2 (list (+ (car ctr) (* 0.5 vp_w)) (+ (cadr ctr) (* 0.5 vp_h)) 0.0)
            )
            
            ;; Crear Viewport en el Layout
            (command "_.MVIEW" "_non" vp_p1 "_non" vp_p2)
            
            ;; Entrar al Viewport recién creado, encuadrar el detalle y salir
            (command "_.MSPACE")
            (command "_.ZOOM" "_W" "_non" pA "_non" pB)
            (command "_.PSPACE")
            
            (setq idx (1+ idx))
          )
        )
      )
      
      (princ (strcat "\n[SINCAL] Proceso terminado. Se enviaron " (itoa idx) " viewports centrados al Layout."))
    )
    (princ "\n[!] No se seleccionó ningún área para enviar.")
  )

  ;; 4. Restaurar el entorno original del usuario
  (setvar "OSMODE" origOsmode)
  (setvar "CMDECHO" origCmdecho)
  (princ)
)