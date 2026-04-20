;;; ==========================================================================
;;; COMANDO: W08 (Width 0.8)
;;; DESCRIPCIÓN: Establece el Width Factor de TODOS los estilos de texto a 0.8
;;; ==========================================================================

(defun c:W08 (/ acadObj doc styles count styleObj)
  (vl-load-com) ; Cargar extensiones Visual LISP

  ;; Obtener el objeto de la aplicación y el documento activo
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadObj))
  
  ;; Obtener la colección de estilos de texto
  (setq styles (vla-get-TextStyles doc))
  
  (setq count 0)

  (princ "\nAjustando el factor de ancho (Width) de los estilos...")

  ;; Iterar a través de cada estilo
  (vlax-for styleObj styles
    ;; Cambiar la propiedad Width a 0.8
    ;; Puedes cambiar el 0.8 por otro valor si lo necesitas en el futuro
    (vla-put-Width styleObj 0.8) 
    (setq count (1+ count))
  )

  ;; Regenerar para ver los cambios inmediatos
  (vla-Regen doc acAllViewports)

  ;; Mensaje final
  (princ (strcat "\n¡Hecho! " (itoa count) " estilos de texto ahora tienen un Width Factor de 0.8."))
  (princ)
)