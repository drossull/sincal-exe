(defun c:PURGEALL (/ *error* old-cmdecho)
  (setq old-cmdecho (getvar "CMDECHO"))
  (defun *error* (msg)
    (setvar "CMDECHO" old-cmdecho)
    (if msg (princ (strcat "\n[SINCAL] PURGEALL: " msg)))
    (princ))
  ;; Desactiva el eco de los comandos para que el proceso sea invisible y no ensucie la consola
  (setvar "CMDECHO" 0)

  (princ "\nIniciando limpieza profunda, por favor espera...")

  ;; Ejecutamos la limpieza 3 veces para atrapar elementos anidados
  (repeat 3
    ;; "A" = All (Todo), "*" = Todos los nombres, "N" = No verificar (Sin cuadros de diálogo)
    (command "_.-PURGE" "_All" "*" "_No")
    
    ;; "R" = Regapps (Aplicaciones registradas)
    (command "_.-PURGE" "_Regapps" "*" "_No")
  )

  ;; El CAD protege la escala actual y las referenciadas por objetos.
  ;; Delete * elimina solo las no utilizadas; Reset recrearia escalas.
  (command "_.-SCALELISTEDIT" "_Delete" "*" "_Exit")

  ;; Conserva la configuracion original, tambien si falla o se cancela.
  (setvar "CMDECHO" old-cmdecho)

  ;; Mensaje final para avisar que terminó
  (princ "\n--- PURGEALL completado con éxito ---")
  
  ;; (princ) al final asegura que el comando termine limpiamente sin devolver "nil"
  (princ)
)
