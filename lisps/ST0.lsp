;;; ==========================================================================
;;; COMANDO: ST0 (Style Text 0)
;;; DESCRIPCIÓN: Establece la altura de TODOS los estilos de texto a 0.0
;;; COMPATIBILIDAD: AutoCAD 2000 - 2025
;;; ==========================================================================

(defun c:ST0 (/ acadObj doc styles count styleObj name)
  (vl-load-com) ; Cargar extensiones Visual LISP

  ;; Obtener el objeto de la aplicación y el documento activo
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadObj))
  
  ;; Obtener la colección de estilos de texto
  (setq styles (vla-get-TextStyles doc))
  
  (setq count 0) ; Inicializar contador

  (princ "\nProcesando estilos de texto...")

  ;; Iterar a través de cada estilo en la colección
  (vlax-for styleObj styles
    ;; Establecer la altura a 0.0
    (vla-put-Height styleObj 0.0)
    (setq count (1+ count))
  )

  ;; Regenerar el dibujo para asegurar que los cambios sean visibles
  (vla-Regen doc acAllViewports)

  ;; Mensaje final al usuario
  (princ (strcat "\n¡Listo! Se han actualizado " (itoa count) " estilos de texto con altura 0.0."))
  (princ)
)