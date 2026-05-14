(defun c:PURGEALL ()
  ;; Desactiva el eco de los comandos para que el proceso sea invisible y no ensucie la consola
  (setvar "CMDECHO" 0)

  (princ "\nIniciando limpieza profunda, por favor espera...")

  ;; Ejecutamos la limpieza 3 veces para atrapar elementos anidados
  (repeat 3
    ;; "A" = All (Todo), "*" = Todos los nombres, "N" = No verificar (Sin cuadros de diálogo)
    (command "_-PURGE" "A" "*" "N")
    
    ;; "R" = Regapps (Aplicaciones registradas)
    (command "_-PURGE" "R" "*" "N")
  )

  ;; Restaura el eco de los comandos a su estado normal
  (setvar "CMDECHO" 1)

  ;; Mensaje final para avisar que terminó
  (princ "\n--- PURGEALL completado con éxito ---")
  
  ;; (princ) al final asegura que el comando termine limpiamente sin devolver "nil"
  (princ)
)