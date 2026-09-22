;;; LAYORIGIN - Restablece el origen interno de la imagen del papel.
;;; Solo actua sobre la presentacion actual cuando What to plot = Layout.
;;; No mueve entidades, no cambia escala/papel/PC3 y no guarda el DWG.
;;; Los grupos DXF 148/149 no son el Plot offset (46/47) del dialogo.

(defun sincal:paper-origin-zero-p (data)
  (and (assoc 148 data) (assoc 149 data)
       (equal (cdr (assoc 148 data)) 0.0 1e-9)
       (equal (cdr (assoc 149 data)) 0.0 1e-9)))

(defun c:LAYORIGIN (/ *error* layout-dict layout-ent old-data new-data
                       x y undo-open edited)
  (defun *error* (msg)
    (if edited (entmod old-data))
    (if undo-open (command-s "_.UNDO" "_End"))
    (if msg (princ (strcat "\n[SINCAL] LAYORIGIN: " msg)))
    (princ))

  (cond
    ((= (getvar "TILEMODE") 1)
     (princ "\n[SINCAL] Activa una presentacion para ejecutar LAYORIGIN."))
    ((not (setq layout-dict (dictsearch (namedobjdict) "ACAD_LAYOUT")))
     (princ "\n[SINCAL] No se encontro el diccionario de presentaciones."))
    ((not (setq old-data
                (dictsearch (cdr (assoc -1 layout-dict)) (getvar "CTAB"))))
     (princ "\n[SINCAL] No se pudo leer la presentacion actual."))
    ((/= (cdr (assoc 74 old-data)) 5)
     (princ "\n[SINCAL] Selecciona What to plot = Layout antes de usar LAYORIGIN."))
    ((not (and (assoc 148 old-data) (assoc 149 old-data)))
     (princ "\n[SINCAL] Este CAD no expone el origen interno del papel. Sin cambios."))
    ((sincal:paper-origin-zero-p old-data)
     (princ "\n[SINCAL] El origen interno del papel ya esta en 0,0. Sin cambios."))
    (T
     (setq layout-ent (cdr (assoc -1 old-data))
           old-data (entget layout-ent)
           x (cdr (assoc 148 old-data))
           y (cdr (assoc 149 old-data))
           new-data (subst '(148 . 0.0) (assoc 148 old-data) old-data)
           new-data (subst '(149 . 0.0) (assoc 149 new-data) new-data))
     ;; Agrupa la correccion y la regeneracion en un solo Deshacer.
     (if (and (/= (logand (getvar "UNDOCTL") 1) 0)
              (= (logand (getvar "UNDOCTL") 8) 0))
       (progn (command "_.UNDO" "_Begin") (setq undo-open T)))
     (if (entmod new-data)
       (progn
         (setq edited T)
         (command "_.REGENALL")
         (if (and (sincal:paper-origin-zero-p (entget layout-ent))
                  (= (cdr (assoc 74 (entget layout-ent))) 5))
           (progn
             (if undo-open (command "_.UNDO" "_End"))
             (setq undo-open nil edited nil)
             (princ (strcat "\n[SINCAL] Layout " (getvar "CTAB")
                            ": origen interno (" (rtos x 2 4) ", " (rtos y 2 4)
                            ") restablecido a (0,0). What to plot sigue en Layout."
                            "\nRevisa la vista previa y guarda el DWG si el resultado es correcto.")))
           (*error* "El CAD no conservo la correccion; se restauro la configuracion anterior.")))
       (*error* "El CAD rechazo el cambio del origen interno."))))
  (princ))

(princ "\nLAYORIGIN cargado. Restablece el origen interno del papel del layout actual.")
(princ)
