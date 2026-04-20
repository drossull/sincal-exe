;;; ==========================================================================
;;; COMANDO: RMLAY (Rename Layout)
;;; DESCRIPCIÓN: 
;;;   Renombra la pestaña de presentación (Layout) en la que te encuentras
;;;   actualmente de forma rápida.
;;;
;;; INSTRUCCIONES DE USO:
;;;   1. Sitúese en la pestaña del Layout que desea cambiar.
;;;   2. Escriba el comando RMLAY y presione Enter.
;;;   3. Escriba el nuevo nombre (puede usar espacios).
;;;   4. Presione Enter para finalizar.
;;;
;;; NOTA TÉCNICA:
;;;   El comando detecta el nombre actual automáticamente, por lo que no
;;;   necesita seleccionarlo ni escribir el nombre antiguo.
;;; ==========================================================================

(defun c:RMLAY (/ doc lay-actual lay-nuevo)
  (vl-load-com) ; Carga funciones Visual LISP

  ; 1. Obtener el nombre del layout actual automáticamente
  (setq lay-actual (getvar "ctab"))

  ; 2. Pedir al usuario el nuevo nombre
  ;    (getstring T ...) permite escribir nombres con ESPACIOS.
  (setq lay-nuevo (getstring T (strcat "\nRenombrar layout <" lay-actual "> a: ")))

  ; 3. Validaciones antes de ejecutar
  (cond
    ; Caso A: El usuario no escribió nada (dio Enter vacío)
    ((= lay-nuevo "")
     (princ "\n[Cancelado] No se ingresó ningún nombre.")
    )
    
    ; Caso B: El nombre nuevo es igual al actual
    ((= (strcase lay-nuevo) (strcase lay-actual))
     (princ "\n[Aviso] El nombre nuevo es igual al actual. Sin cambios.")
    )

    ; Caso C: Proceder al cambio
    (T
     (if (vl-cmdf "_.-LAYOUT" "_RENAME" lay-actual lay-nuevo)
       (princ (strcat "\n[Exito] Layout renombrado a: " lay-nuevo))
       (princ "\n[Error] El nombre ingresado no es válido o ya existe.")
     )
    )
  )
  
  (princ) ; Sale limpiamente
)

;;; Mensaje de carga
(princ "\nComando RMLAY cargado. Escribe RMLAY para cambiar el nombre de la pestaña.")
(princ)