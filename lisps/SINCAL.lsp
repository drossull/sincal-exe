(defun c:SINCAL (/ rutaArchivo cmdecho_inicial attreq_inicial last_ent ent ss_del)
  (vl-load-com)

  ;; --- RUTA DINÁMICA ---
  ;; Obtiene automáticamente el AppData del usuario actual (funciona en cualquier PC)
  (setq rutaArchivo (strcat (getenv "APPDATA") "\\Estandar SINCAL\\masters\\FORMATOS ANOTATIVOS ACAD_2025.dwg"))

  ;; Guardar variables del sistema actuales
  (setq cmdecho_inicial (getvar "CMDECHO"))
  (setq attreq_inicial (getvar "ATTREQ"))
  
  ;; Silenciar comandos y diálogos
  (setvar "CMDECHO" 0)
  (setvar "ATTREQ" 0)

  (princ "\n[SINCAL] Ejecutando: Importando estandares...")

  ;; Verificar si el archivo maestro existe
  (if (findfile rutaArchivo)
    (progn
      ;; 1. Capturamos la última entidad dibujada antes de insertar
      (setq last_ent (entlast))

      ;; 2. Insertamos el archivo con un asterisco (*) para explotarlo al entrar.
      ;; Esto transfiere limpiamente todos los estilos, capas y sub-bloques a la raíz.
      (command "._-insert" (strcat "*" rutaArchivo) "_NON" '(0 0 0) 1 0)

      ;; 3. Recolectamos la basura geométrica que cayó en el Model Space
      (setq ss_del (ssadd))
      (setq ent (if last_ent (entnext last_ent) (entnext)))
      (while ent
        (if (and (entget ent) (not (wcmatch (cdr (assoc 0 (entget ent))) "VERTEX,SEQEND")))
          (ssadd ent ss_del)
        )
        (setq ent (entnext ent))
      )

      ;; 4. Borramos la geometría física, dejando intacta la memoria (bloques, estilos)
      (if (> (sslength ss_del) 0) (command "._erase" ss_del ""))

      (princ "\n[SINCAL] EXITO: Estilos, bloques y capas importados correctamente.")
    )
    ;; Error si no lo encuentra
    (alert (strcat "ERROR SINCAL:\nNo se encuentra el archivo maestro en:\n" rutaArchivo "\n\nAsegurese de haber actualizado la Suite."))
  )

  ;; Restaurar variables
  (setvar "ATTREQ" attreq_inicial)
  (setvar "CMDECHO" cmdecho_inicial)
  (princ)
)