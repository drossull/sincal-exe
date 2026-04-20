(vl-load-com)

(defun c:RC-CAPAS ( / doc layers count col-obj method r g b aci new-aci)
  (princ "\nRevisando los colores de todas las capas...")
  
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq layers (vla-get-Layers doc))
  (setq count 0)

  (vlax-for lay layers
    (setq col-obj (vla-get-TrueColor lay))
    (setq method (vla-get-ColorMethod col-obj))
    (setq new-aci nil)

    (cond
      ;; MÉTODO 194: Colores RGB (True Color)
      ((= method 194) 
        (setq r (vla-get-Red col-obj)
              g (vla-get-Green col-obj)
              b (vla-get-Blue col-obj))

        (cond
          ((and (= r 255) (= g 0) (= b 0))     (setq new-aci 1)) ; Rojo
          ((and (= r 255) (= g 255) (= b 0))   (setq new-aci 2)) ; Amarillo (Corregido)
          ((and (= r 0) (= g 255) (= b 0))     (setq new-aci 3)) ; Verde
          ((and (= r 0) (= g 255) (= b 255))   (setq new-aci 4)) ; Cyan
          ((and (= r 0) (= g 0) (= b 255))     (setq new-aci 5)) ; Azul
          ((and (= r 255) (= g 0) (= b 255))   (setq new-aci 6)) ; Magenta
          ((and (= r 255) (= g 255) (= b 255)) (setq new-aci 7)) ; Blanco
        )
      )
      
      ;; MÉTODO 195: Colores clásicos (Index Color)
      ((= method 195) 
        (setq aci (vla-get-ColorIndex col-obj))
        (if (= aci 252) (setq new-aci 8)) ; 252 a 8
      )
    )

    ;; Si encontró una coincidencia, actualiza la capa
    (if new-aci
      (progn
        (if (not (vl-catch-all-error-p (vl-catch-all-apply 'vla-put-color (list lay new-aci))))
          (setq count (1+ count))
        )
      )
    )
  )

  (vla-Regen doc 0)
  (princ (strcat "\n¡Exito! Se corrigieron los colores de " (itoa count) " capas."))
  (princ)
)
(princ "\nComando 'RC-CAPAS' actualizado con todos los colores. Escribe RC-CAPAS para ejecutar.")
(princ)