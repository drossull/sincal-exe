(vl-load-com) ; Carga las funciones visuales necesarias para las polilíneas

(defun c:PND ( / ss ent tipo p1 p2 dx dy pct msg)
  ;; 1. Revisa si ya hay algo seleccionado antes de ejecutar el comando (Pickfirst)
  (setq ss (cadr (ssgetfirst)))
  
  (if ss
    ;; Si hay selección previa, tomamos el primer objeto
    (setq ent (ssname ss 0))
    ;; Si no, le pedimos al usuario que seleccione uno
    (setq ent (car (entsel "\nSelecciona una linea o polilinea: ")))
  )
  
  (if ent
    (progn
      ;; Verificamos que sea una línea o polilínea
      (setq tipo (cdr (assoc 0 (entget ent))))
      (if (wcmatch tipo "LINE,*POLYLINE")
        (progn
          ;; Extraemos el punto inicial absoluto y final absoluto de la figura
          (setq p1 (vlax-curve-getStartPoint ent))
          (setq p2 (vlax-curve-getEndPoint ent))
          
          ;; Calculamos la diferencia en X e Y
          (setq dx (abs (- (car p2) (car p1))))
          (setq dy (abs (- (cadr p2) (cadr p1))))
          
          ;; Evitamos la división por cero
          (if (> dx 0.000001)
            (progn
              (setq pct (* (/ dy dx) 100.0))
              ;; Preparamos el mensaje y lo mostramos en una ventana emergente
              (setq msg (strcat "La pendiente es: " (rtos pct 2 2) "%"))
              (alert msg)
            )
            (alert "La línea es completamente vertical (pendiente infinita).")
          )
        )
        ;; Mensaje de error si seleccionó un círculo, texto, etc.
        (alert "Error: Por favor, selecciona solo una línea o polilínea.")
      )
    )
    (princ "\nComando cancelado: No se seleccionó ningún objeto.")
  )
  
  ;; Limpiamos la selección para no interferir con tus siguientes comandos
  (sssetfirst nil nil)
  (princ)
)