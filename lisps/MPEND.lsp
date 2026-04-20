(vl-load-com)
(defun c:MPEND ( / sel slope_str slope_val i ent obj verts pt1 pt2 current_angle target_rad final_target rot_angle)
  ;; 1. Capturar MULTILEADERS previamente seleccionados (PickFirst)
  (setq sel (ssget "_I" '((0 . "MULTILEADER"))))
  
  ;; 2. Si no hay selección previa, pedirla al usuario
  (if (not sel)
    (progn
      (prompt "\nSelecciona el(los) Multileader(s) a inclinar: ")
      (setq sel (ssget '((0 . "MULTILEADER"))))
    )
  )

  ;; 3. Procesar la selección
  (if sel
    (progn
      (setq slope_str (getstring "\nIngresa la pendiente en porcentaje (ej: 2, 2.5 o -2): "))
      
      (if (/= slope_str "")
        (progn
          ;; Limpiar el texto por si el usuario escribe "2%" en lugar de "2"
          (setq slope_val (atof (vl-string-right-trim "% " slope_str)))
          
          ;; Convertir porcentaje a radianes: atan(pendiente/100)
          (setq target_rad (atan (/ slope_val 100.0)))
          
          (setq i 0)
          (while (< i (sslength sel))
            (setq ent (ssname sel i))
            (setq obj (vlax-ename->vla-object ent))
            
            ;; Extraer los vértices de la flecha (con manejo de errores por si no tiene directriz)
            (setq verts (vl-catch-all-apply 'vlax-invoke (list obj 'GetLeaderLineVertices 0)))
            
            (if (and (not (vl-catch-all-error-p verts)) (>= (length verts) 6))
              (progn
                ;; pt1 es la punta de la flecha, pt2 es el siguiente vértice
                (setq pt1 (list (nth 0 verts) (nth 1 verts) (nth 2 verts)))
                (setq pt2 (list (nth 3 verts) (nth 4 verts) (nth 5 verts)))
                
                ;; Ángulo actual de la flecha
                (setq current_angle (angle pt1 pt2))
                
                ;; Ajuste: Si la flecha apunta hacia la izquierda (entre 90 y 270 grados), 
                ;; sumamos 180 grados (pi) para que no se voltee.
                (setq final_target target_rad)
                (if (and (> current_angle (/ pi 2.0)) (< current_angle (* 1.5 pi)))
                  (setq final_target (+ pi target_rad))
                )
                
                ;; Calcular cuánto hay que rotar (Diferencia entre objetivo y actual)
                (setq rot_angle (- final_target current_angle))
                
                ;; Rotar el objeto desde la punta de la flecha (pt1)
                (vla-Rotate obj (vlax-3D-point pt1) rot_angle)
              )
            )
            (setq i (1+ i))
          )
          (prompt "\n¡Listo! Multileader(s) alineado(s) a la pendiente ingresada.")
        )
        (prompt "\nOperación cancelada: No se ingresó ningún valor.")
      )
    )
    (prompt "\nOperación cancelada: No se seleccionó ningún Multileader.")
  )
  
  ;; Limpiar los grips de selección visual
  (sssetfirst nil nil)
  (princ)
)