(defun c:SINCAL (/ *error* rutaArchivo rutaOverride rutaInstalada rutaLegacy cmdecho_inicial attreq_inicial last_ent ent ss_del)
  (vl-load-com)

  ;; Prioridad: copia sincronizada del usuario, master del instalador y ruta heredada.
  (setq rutaOverride
    (if (getenv "LOCALAPPDATA")
      (strcat (getenv "LOCALAPPDATA") "\\SINCAL\\resources\\masters\\FORMATOS ANOTATIVOS ACAD_2025.dwg")
    )
  )
  (setq rutaInstalada
    (if (getenv "ProgramFiles")
      (strcat (getenv "ProgramFiles") "\\SINCAL\\masters\\FORMATOS ANOTATIVOS ACAD_2025.dwg")
    )
  )
  (setq rutaLegacy
    (if (getenv "APPDATA")
      (strcat (getenv "APPDATA") "\\Estandar SINCAL\\masters\\FORMATOS ANOTATIVOS ACAD_2025.dwg")
    )
  )

  (cond
    ((and rutaOverride (findfile rutaOverride)) (setq rutaArchivo rutaOverride))
    ((and rutaInstalada (findfile rutaInstalada)) (setq rutaArchivo rutaInstalada))
    ((and rutaLegacy (findfile rutaLegacy)) (setq rutaArchivo rutaLegacy))
  )

  ;; Conservar siempre el estado original, incluso si AutoCAD cancela o falla.
  (setq cmdecho_inicial (getvar "CMDECHO"))
  (setq attreq_inicial (getvar "ATTREQ"))
  (defun *error* (mensaje)
    (setvar "ATTREQ" attreq_inicial)
    (setvar "CMDECHO" cmdecho_inicial)
    (if (and mensaje
             (not (wcmatch (strcase mensaje) "*BREAK*,*CANCEL*,*EXIT*")))
      (princ (strcat "\n[X] SINCAL: " mensaje))
    )
    (princ)
  )

  (setvar "CMDECHO" 0)
  (setvar "ATTREQ" 0)
  (princ "\n[SINCAL] Ejecutando: Importando estandares...")

  (if rutaArchivo
    (progn
      ;; Capturar la última entidad antes de insertar y explotar el master.
      (setq last_ent (entlast))
      (command "._-insert" (strcat "*" rutaArchivo) "_NON" '(0 0 0) 1 0)

      ;; Eliminar la geometría insertada conservando bloques, estilos y capas.
      (setq ss_del (ssadd))
      (setq ent (if last_ent (entnext last_ent) (entnext)))
      (while ent
        (if (and (entget ent)
                 (not (wcmatch (cdr (assoc 0 (entget ent))) "VERTEX,SEQEND")))
          (ssadd ent ss_del)
        )
        (setq ent (entnext ent))
      )
      (if (> (sslength ss_del) 0) (command "._erase" ss_del ""))
      (princ (strcat "\n[SINCAL] EXITO: Estandares importados desde " rutaArchivo))
    )
    (alert
      (strcat
        "ERROR SINCAL:\nNo se encontro un master DWG valido.\n\n"
        "Abra SINCAL Suite y use 'Actualizar recursos CAD', o reinstale la aplicacion."
      )
    )
  )

  (setvar "ATTREQ" attreq_inicial)
  (setvar "CMDECHO" cmdecho_inicial)
  (princ)
)
