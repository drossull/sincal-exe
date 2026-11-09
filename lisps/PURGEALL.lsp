(defun SPG:Command (args)
  (apply 'command args)
  ;; A script can keep bit 4 active; only bit 1 means a native command is
  ;; still waiting for input. Do not feed the next cleanup step into it.
  (if (= 1 (logand (getvar "CMDACTIVE") 1))
    (progn
      (command)
      (princ (strcat "\n[SINCAL] PURGEALL detenido: " (car args)
        " no termino. Revise las opciones admitidas por el motor CAD."))
      (quit))))

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
    (SPG:Command '("_.-PURGE" "_All" "*" "_No"))
    
    ;; AutoCAD uses Regapps; ZWCAD uses Regapp. _R works in both engines.
    (SPG:Command '("_.-PURGE" "_R" "*" "_No"))
  )

  ;; El CAD protege la escala actual y las referenciadas por objetos.
  ;; Delete * elimina solo las no utilizadas; Reset recrearia escalas.
  (SPG:Command '("_.-SCALELISTEDIT" "_Delete" "*" "_Exit"))

  ;; Conserva la configuracion original, tambien si falla o se cancela.
  (setvar "CMDECHO" old-cmdecho)

  ;; Mensaje final para avisar que terminó
  (princ "\n--- PURGEALL completado con éxito ---")
  
  ;; (princ) al final asegura que el comando termine limpiamente sin devolver "nil"
  (princ)
)
