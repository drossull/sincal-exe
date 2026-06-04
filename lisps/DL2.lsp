;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; Rutina AutoLISP: DeleteLayout2
; Nombre del Comando: DL2
; Descripción: Elimina las pestañas "Layout2" y "A1" sin cambiar de vista.
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

(defun c:DL2 (/ acadObj doc layouts currentTab targets target layoutObj)
  (vl-load-com)

  ; Obtener objetos principales
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadObj))
  (setq layouts (vla-get-Layouts doc))
  (setq currentTab (getvar "CTAB"))

  ; --- CONFIGURACIÓN ---
  ; Lista de pestañas que la rutina intentará eliminar
  (setq targets '("Layout2" "A1"))

  ; Bucle para evaluar cada pestaña en la lista
  (foreach target targets
    ; Intentar capturar la pestaña actual
    (if (not (vl-catch-all-error-p (setq layoutObj (vl-catch-all-apply 'vla-Item (list layouts target)))))
      (progn
        ; Verificar si el usuario está actualmente DENTRO de la pestaña a borrar
        (if (= (strcase currentTab) (strcase target))
          (princ (strcat "\nXX Error: No se puede eliminar '" target "' porque estás actualmente en él. Cambia a otra pestaña e intenta de nuevo."))
          ; Si no está en esa pestaña, proceder a borrarla
          (if (not (vl-catch-all-error-p (vl-catch-all-apply 'vla-delete (list layoutObj))))
            (princ (strcat "\n>> '" target "' fue eliminado con éxito."))
            (princ (strcat "\nXX Ocurrió un error inesperado al intentar eliminar '" target "'."))
          )
        )
      )
      ; Mensaje si la pestaña no existe en el dibujo
      (princ (strcat "\n-- '" target "' no existe en este dibujo."))
    )
  )
  
  (princ) ; Salida limpia
)

(princ "\nComando cargado. Escribe DL2 para eliminar Layout2 y A1.")
(princ)