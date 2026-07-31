(defun c:DUP (/ ss)
  ;; Verifica si ya hay elementos seleccionados antes de ejecutar el comando
  (setq ss (cadr (ssgetfirst)))
  
  ;; Si no hay selección previa, pide al usuario que seleccione
  (if (not ss)
    (setq ss (ssget))
  )

  ;; Si hay una selección válida, ejecuta la copia
  (if ss
    (progn
      ;; Usa el comando COPY con coordenadas 0,0,0 como base y destino
      ;; "_non" evita que el OSNAP (referencias a objetos) interfiera
      (command "_.COPY" ss "" "_non" '(0 0 0) "_non" '(0 0 0))
      (princ (strcat "\n¡Éxito! Se han duplicado " (itoa (sslength ss)) " elemento(s) en el mismo sitio."))
    )
    (princ "\nCancelado: No se seleccionó ningún elemento.")
  )
  (princ) ; Cierra el comando limpiamente sin devolver "nil"
)

;; Función alias para que funcione también escribiendo DUPLICAR
(defun c:DUPLICAR ()
  (c:DUP)
)

;; Mensaje que aparece en la consola al cargar el LISP
(princ "\nRutina cargada. Escribe DUP o DUPLICAR para copiar en el mismo sitio.")
(princ)