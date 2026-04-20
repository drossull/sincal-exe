;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; Rutina AutoLISP: DeleteLayout2
; Nombre del Comando: DL2
; Descripción: Elimina únicamente la pestaña "Layout2" sin cambiar de vista.
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

(defun c:DL2 (/ acadObj doc layouts layout2Obj currentTab)
  (vl-load-com)

  ; Obtener objetos principales
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadObj))
  (setq layouts (vla-get-Layouts doc))
  (setq currentTab (getvar "CTAB"))

  ; Intentar capturar "Layout2"
  (if (not (vl-catch-all-error-p (setq layout2Obj (vl-catch-all-apply 'vla-Item (list layouts "Layout2")))))
    (progn
      ; Verificar si el usuario está actualmente DENTRO de Layout2
      (if (= (strcase currentTab) "LAYOUT2")
        (princ "\nXX Error: No se puede eliminar 'Layout2' porque estás actualmente en él. Cambia a otra pestaña e intenta de nuevo.")
        ; Si no está en Layout2, proceder a borrarlo
        (if (not (vl-catch-all-error-p (vl-catch-all-apply 'vla-delete (list layout2Obj))))
          (princ "\n>> 'Layout2' fue eliminado con éxito.")
          (princ "\nXX Ocurrió un error inesperado al intentar eliminar 'Layout2'.")
        )
      )
    )
    ; Mensaje si Layout2 no existe en el dibujo
    (princ "\n-- 'Layout2' no existe en este dibujo.")
  )
  
  (princ) ; Salida limpia
)

(princ "\nComando cargado. Escribe DL2 para eliminar Layout2.")
(princ)