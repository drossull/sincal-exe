;;; ==========================================================================
;;; NOMBRE DEL COMANDO: BV (Bloquear Viewports)
;;;
;;; DESCRIPCIÓN:
;;;   Esta rutina "pone el candado" automáticamente a todas las ventanas 
;;;   gráficas (Viewports) de la presentación (Layout) actual.
;;;
;;;   Es muy útil para evitar mover la escala o el encuadre por accidente
;;;   cuando entras a trabajar dentro de una ventana.
;;;
;;; INSTRUCCIONES DE USO:
;;;   1. Cargue este archivo con el comando CUI.
;;;   2. Vaya a la pestaña del Layout (Presentación) que quiere proteger.
;;;   3. Escriba BV y presione Enter.
;;;
;;; NOTAS IMPORTANTES:
;;;   - Este comando NO funciona en la pestaña "Model" (Espacio Modelo).
;;;     Debe estar en una hoja de presentación.
;;;   - Solo afecta al Layout que tenga abierto en ese momento.
;;; ==========================================================================

(defun c:BV (/ ss i ent obj nCount layoutName)
  (vl-load-com) ; Cargar funciones Visual LISP

  ; Obtener nombre del layout actual
  (setq layoutName (getvar "ctab"))

  ; 1. Verificar que NO estamos en el Model Space
  (if (= layoutName "Model")
    (alert "El comando BV solo funciona en un Layout (Presentación).")
    
    ; 2. Si estamos en un Layout, proceder
    (progn
      (princ "\nBloqueando viewports...")
      
      ; Crear selección de todos los Viewports del layout actual
      ; Excluyendo el Viewport ID 1 (que es la hoja de papel misma)
      (setq ss (ssget "_X" (list 
                            '(0 . "VIEWPORT") 
                            (cons 410 layoutName)
                            '(-4 . "<NOT") '(69 . 1) '(-4 . "NOT>")
                          )))

      (if ss
        (progn
          (setq i 0)
          (setq nCount 0)
          
          ; Iterar sobre cada viewport encontrado
          (repeat (sslength ss)
            (setq ent (ssname ss i))
            (setq obj (vlax-ename->vla-object ent))
            
            ; Bloquear la vista (Display Locked = YES)
            ; Usamos vl-catch-all-apply para evitar errores si alguno ya estaba bloqueado
            (if (not (vl-catch-all-error-p 
                       (vl-catch-all-apply 'vla-put-DisplayLocked (list obj :vlax-true))))
                (setq nCount (1+ nCount))
            )
            (setq i (1+ i))
          )
          (princ (strcat "\nListo: " (itoa nCount) " viewports bloqueados en " layoutName "."))
        )
        (princ "\nNo se encontraron viewports para bloquear en este layout.")
      )
    )
  )
  (princ) ; Salida silenciosa
)

;;; Mensaje de confirmación al cargar
(princ "\nComando BV cargado. Escriba BV en un Layout para bloquear sus ventanas.")
(princ)