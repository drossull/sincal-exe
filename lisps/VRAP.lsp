;;; =========================================================================
;;; COMANDO: VRAP (Versión Tamaño Fijo en Layout)
;;; 1. Selecciona múltiples áreas en el Model.
;;; 2. Pide dibujar UN rectángulo en el Layout.
;;; 3. Genera todos los viewports con ese tamaño exacto en cascada.
;;; =========================================================================
(defun c:VRAP (/ pt1 pt2 lst_areas idx area pA pB vp_p1 vp_p2 offset paper_p1 paper_p2 origOsmode origCmdecho)
  (vl-load-com)
  
  (setq origOsmode (getvar "OSMODE"))
  (setq origCmdecho (getvar "CMDECHO"))
  (setvar "CMDECHO" 0)

  ;; 1. Forzar ir al Model Space
  (if (= (getvar "TILEMODE") 0)
    (setvar "TILEMODE" 1)
  )

  (princ "\n--- MÓDULO SINCAL: MULTI-SELECCIÓN EN MODEL ---")
  (princ "\nSeleccione los recuadros de los detalles. Al finalizar, presione ENTER o Espacio en blanco.")
  
  (setq lst_areas nil)
  (setq pt1 T)

  ;; 2. Bucle de captura de coordenadas en el Model
  (while pt1
    (setq pt1 (getpoint (strcat "\n[" (itoa (1+ (length lst_areas))) "] Esquina del recuadro (o ENTER para ir al Layout): ")))
    (if pt1
      (progn
        (setq pt2 (getcorner pt1 " -> Esquina opuesta: "))
        (if pt2
          (progn
            (setq lst_areas (cons (list pt1 pt2) lst_areas))
            (princ (strcat "\n[SINCAL] Detalle " (itoa (length lst_areas)) " registrado."))
          )
          (setq pt1 nil) ; Detener si se cancela
        )
      )
    )
  )

  ;; 3. Viaje al Layout y Definición de Tamaño Físico
  (if (and lst_areas (> (length lst_areas) 0))
    (progn
      (setq lst_areas (reverse lst_areas))
      
      (setvar "TILEMODE" 0)
      (command "_.PSPACE")
      
      (princ "\n--- SINCAL: CREACIÓN EN EL LAYOUT ---")
      (setq vp_p1 (getpoint "\nEspecifique la PRIMERA esquina del tamaño de sus Viewports: "))
      
      (if vp_p1
        (setq vp_p2 (getcorner vp_p1 "\nEspecifique la ESQUINA OPUESTA (Define el tamaño para todos): "))
      )

      (if (and vp_p1 vp_p2)
        (progn
          (setvar "OSMODE" 0)
          (setq idx 0)
          
          ;; 4. Bucle generador de Viewports
          (foreach area lst_areas
            (setq pA (car area))
            (setq pB (cadr area))
            
            ;; Desfase de cascada (15 unidades en X y -15 en Y por cada viewport adicional)
            (setq offset (* idx 15.0))
            (setq paper_p1 (list (+ (car vp_p1) offset) (- (cadr vp_p1) offset) 0.0))
            (setq paper_p2 (list (+ (car vp_p2) offset) (- (cadr vp_p2) offset) 0.0))
            
            ;; Crea el viewport físico
            (command "_.MVIEW" "_non" paper_p1 "_non" paper_p2)
            
            ;; Entra, hace Zoom Window forzado y sale
            (command "_.MSPACE")
            (command "_.ZOOM" "_W" "_non" pA "_non" pB)
            (command "_.PSPACE")
            
            (setq idx (1+ idx))
          )
          (princ (strcat "\n[SINCAL] ¡Éxito! Se generaron " (itoa idx) " viewports del mismo tamaño."))
        )
        (princ "\n[!] Operación cancelada: No se definió el tamaño del Viewport.")
      )
    )
    (princ "\n[!] No se seleccionó ningún área en el Model.")
  )

  ;; 5. Restaurar variables
  (setvar "OSMODE" origOsmode)
  (setvar "CMDECHO" origCmdecho)
  (princ)
)