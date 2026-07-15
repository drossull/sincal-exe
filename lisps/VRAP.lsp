;;; =========================================================================
;;; COMANDO: VRAP (Versión Viewports de Tamaños Independientes)
;;; 1. Selecciona múltiples áreas en el Model de manera secuencial.
;;; 2. En el Layout, pide especificar el tamaño y ubicación de cada Viewport
;;;    uno por uno, en el mismo orden de selección.
;;; =========================================================================
(defun c:VRAP (/ pt1 pt2 lst_areas idx area pA pB vp_p1 vp_p2 origOsmode origCmdecho)
  (vl-load-com)
  
  (setq origOsmode (getvar "OSMODE"))
  (setq origCmdecho (getvar "CMDECHO"))
  (setvar "CMDECHO" 0)

  ;; 1. Forzar ir al Model Space para iniciar la selección
  (if (= (getvar "TILEMODE") 0)
    (setvar "TILEMODE" 1)
  )

  (princ "\n--- MÓDULO SINCAL: MULTI-SELECCIÓN EN MODEL ---")
  (princ "\nSeleccione los recuadros de los detalles. Al finalizar, presione ENTER o Espacio.")
  
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

  ;; 3. Viaje al Layout y creación secuencial personalizada
  (if (and lst_areas (> (length lst_areas) 0))
    (progn
      ;; Volteamos la lista para procesar en el mismo orden de selección
      (setq lst_areas (reverse lst_areas))
      
      (setvar "TILEMODE" 0)
      (command "_.PSPACE")
      
      (princ "\n--- SINCAL: CREACIÓN PERSONALIZADA EN EL LAYOUT ---")
      (setq idx 1)
      
      (foreach area lst_areas
        (setq pA (car area))
        (setq pB (cadr area))
        
        ;; Activamos tus referencias (Snaps) para que puedas apoyarte en el Layout
        (setvar "OSMODE" origOsmode)
        
        (setq vp_p1 (getpoint (strcat "\n[Detalle " (itoa idx) "] Especifique PRIMERA esquina de este Viewport en la lámina: ")))
        (if vp_p1
          (progn
            (setq vp_p2 (getcorner vp_p1 " -> Especifique ESQUINA OPUESTA: "))
            (if vp_p2
              (progn
                ;; Apagamos snaps temporalmente para realizar el Zoom Window de precisión sin interferencias
                (setvar "OSMODE" 0)
                
                ;; Crear viewport físico
                (command "_.MVIEW" "_non" vp_p1 "_non" vp_p2)
                
                ;; Entrar al viewport, encuadrar el detalle exacto del model y salir
                (command "_.MSPACE")
                (command "_.ZOOM" "_W" "_non" pA "_non" pB)
                (command "_.PSPACE")
                
                (setq idx (1+ idx))
              )
              (princ "\n[!] Operación omitida: Falta definir la esquina opuesta.")
            )
          )
          (princ "\n[!] Operación omitida: Detalle cancelado por el usuario.")
        )
      )
      (princ (strcat "\n[SINCAL] ¡Éxito! Se generaron " (itoa (1- idx)) " viewports independientes con sus medidas exactas."))
    )
    (princ "\n[!] No se seleccionó ningún área en el Model.")
  )

  ;; 4. Restaurar variables originales del usuario
  (setvar "OSMODE" origOsmode)
  (setvar "CMDECHO" origCmdecho)
  (princ)
)