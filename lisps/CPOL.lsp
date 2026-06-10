(defun c:CPOL ( / ptCenter ptEnd ptOpposite ang dist oldOsMode )
  ;; Guardar configuración actual de referencias a objetos (OSNAP)
  (setq oldOsMode (getvar "OSMODE"))
  
  ;; Pedir el punto central
  (if (setq ptCenter (getpoint "\nSelecciona el punto central: "))
    (progn
      ;; Pedir el extremo (muestra una línea elástica desde el centro)
      (if (setq ptEnd (getpoint ptCenter "\nSelecciona el punto final: "))
        (progn
          ;; Calcular distancia y ángulo
          (setq dist (distance ptCenter ptEnd))
          (setq ang (angle ptCenter ptEnd))
          
          ;; Calcular el punto opuesto sumando Pi (180 grados) al ángulo
          (setq ptOpposite (polar ptCenter (+ ang pi) dist))
          
          ;; Desactivar OSNAP temporalmente para que no interfiera al dibujar
          (setvar "OSMODE" 0)
          
          ;; Dibujar la polilínea desde el punto opuesto hasta el punto final
          (command "_.PLINE" ptOpposite ptCenter ptEnd "")
          
          ;; Restaurar OSNAP
          (setvar "OSMODE" oldOsMode)
        )
        (princ "\nComando cancelado: No se seleccionó un punto final.")
      )
    )
    (princ "\nComando cancelado: No se seleccionó un punto central.")
  )
  (princ "\n¡Polilínea central dibujada!")
  (princ)
)

(princ "\nComando cargado exitosamente. Escribe CPOL para usarlo.")
(princ)