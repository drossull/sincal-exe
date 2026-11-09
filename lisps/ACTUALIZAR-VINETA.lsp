;;; ACTUALIZAR-VINETA -- reactivar Fields DWGPROPS de la revision actual.
;;; ZWCAD: solo tabla de seis columnas del bloque seleccionado. No guarda.
;;; Recuperacion de la sesion: algunos DWG restablecen Disable al guardar/reabrir.
(vl-load-com)

(defun SRF:Fail (message) (setq SRF:failure message) (exit))
(defun SRF:Code (data)
  (vl-remove-if-not '(lambda (pair) (member (car pair) '(2 3))) data))
(defun SRF:Expression (data / result pair)
  (setq result "")
  (foreach pair (SRF:Code data) (setq result (strcat result (cdr pair))))
  result)
(defun SRF:Property (data / text prefix end)
  (setq text (SRF:Expression data) prefix "\\AcVar CustomDP.")
  (if (and (= "AcVar" (cdr (assoc 1 data)))
           (= 0 (vl-string-search prefix text)))
    (progn
      (setq text (substr text (1+ (strlen prefix))) end 1)
      (while (and (<= end (strlen text))
                  (not (member (substr text end 1) '(" " "\t" "\\"))))
        (setq end (1+ end)))
      (if (> end 1) (substr text 1 (1- end))))))

(defun SRF:Walk (field depth / data pair key children records)
  (if (or (> depth 16) (member field SRF:visited))
    (SRF:Fail "Arbol de Fields circular o demasiado profundo."))
  (setq SRF:visited (cons field SRF:visited) data (entget field))
  (if (not (= "FIELD" (cdr (assoc 0 data))))
    (SRF:Fail "Referencia de FIELD no valida."))
  (foreach pair data
    (if (= 360 (car pair))
      (setq children T records (append records (SRF:Walk (cdr pair) (1+ depth))))))
  (cond
    ((setq key (SRF:Property data)) (setq SRF:keys (cons key SRF:keys)))
    ((and children (= "_text" (cdr (assoc 1 data)))))
    (T (setq SRF:eligible nil)))
  (cons data records))

(defun SRF:Cell (doc table column / id field result SRF:visited SRF:keys SRF:eligible)
  (setq id (vl-catch-all-apply 'vla-GetFieldId (list table 0 column)))
  (if (and (not (vl-catch-all-error-p id)) id (not (equal id 0)))
    (progn
      (setq field (vla-ObjectIDToObject doc id) SRF:eligible T
            result (SRF:Walk (vlax-vla-object->ename field) 0))
      (if (and SRF:eligible SRF:keys) (list result SRF:keys)))))

(defun SRF:TableP (doc table / cell)
  (and (= "AcDbTable" (vla-get-ObjectName table))
       (= 6 (vla-get-Columns table)) (> (vla-get-Rows table) 1)
       (setq cell (SRF:Cell doc table 0))
       (member "REVISION" (mapcar 'strcase (cadr cell)))))

(defun SRF:Patch (data option / seen result pair section)
  ;; ZWCAD duplicates the FIELD expression if group 2/3 is passed to entmod.
  ;; Omit code groups entirely. The FIRST 91 is EvaluationOption. Keep the
  ;; named round-trip record consistent; this does not guarantee persistence.
  ;; Other 91 groups are not evaluation options and must remain intact.
  (foreach pair data
    (cond ((= 6 (car pair)) (setq section (cdr pair)))
          ((= 7 (car pair)) (setq section nil)))
    (if (not (member (car pair) '(2 3)))
      (setq result (cons
        (if (and (= 91 (car pair))
                 (or (not seen) (equal section "ACAD_ROUNDTRIP_2008_FIELD_EVALOPTION")))
          (progn (setq seen T) (cons 91 option)) pair) result))))
  (if (not seen) (SRF:Fail "El FIELD no expone su opcion de evaluacion."))
  (reverse result))

(defun SRF:Prepare (doc table / column cell data key value summary result)
  (if (not (wcmatch (strcase (getvar "PROGRAM")) "*ZW*"))
    (SRF:Fail "Esta reparacion esta validada solamente en ZWCAD."))
  (if (not (SRF:TableP doc table))
    (SRF:Fail "Se requiere una tabla de seis columnas con FIELD Revision en la primera celda."))
  (setq summary (vla-get-SummaryInfo doc) column 0)
  (repeat 6
    (if (setq cell (SRF:Cell doc table column))
      (progn
        (foreach key (cadr cell)
          (setq result (vl-catch-all-apply 'vla-GetCustomByKey (list summary key 'value)))
          (if (vl-catch-all-error-p result)
            (SRF:Fail (strcat "No existe la propiedad DWGPROPS: " key))))
        (foreach data (car cell)
          (if (not (assoc (cdr (assoc -1 data)) SRF:snapshots))
            (progn
              (if (not (assoc 91 data)) (SRF:Fail "FIELD sin opcion de evaluacion."))
              (setq SRF:snapshots (cons (cons (cdr (assoc -1 data)) data) SRF:snapshots)))))))
    (setq column (1+ column))))

(defun SRF:Apply (doc table / saved data changed patched option)
  (foreach saved SRF:snapshots
    (setq data (cdr saved) option (cdr (assoc 91 data))
          patched (SRF:Patch data (if (= option 0) 63 option)))
    (if (not (equal patched (vl-remove-if '(lambda (pair) (member (car pair) '(2 3))) data)))
      (progn
        ;; Capture before attempting the write, so a partial failure is restored.
        (setq SRF:modified (cons saved SRF:modified))
        (if (not (entmod patched))
          (SRF:Fail "ZWCAD rechazo la activacion de un FIELD."))
        (setq changed (1+ (if changed changed 0))))))
  (foreach saved SRF:snapshots
    (if (not (equal (SRF:Code (cdr saved)) (SRF:Code (entget (car saved)))))
      (SRF:Fail "El codigo de un FIELD cambio inesperadamente; se revierte.")))
  (vla-Regen doc 1)
  (foreach saved SRF:snapshots
    (if (not (equal (SRF:Code (cdr saved)) (SRF:Code (entget (car saved)))))
      (SRF:Fail "La regeneracion altero el codigo de un FIELD; se revierte.")))
  (if changed changed 0))

(defun SRF:Restore (/ saved result ok)
  (setq ok T)
  (foreach saved SRF:modified
    (setq result (vl-catch-all-apply 'entmod
      (list (vl-remove-if '(lambda (pair) (member (car pair) '(2 3))) (cdr saved)))))
    (if (or (vl-catch-all-error-p result) (not result)
            (not (equal (SRF:Code (cdr saved)) (SRF:Code (entget (car saved))))))
      (setq ok nil)))
  ok)

(defun SRF:RepairTable (doc table / SRF:failure SRF:snapshots SRF:modified result undo restored)
  ;; Public helper for native regression tests: returns an explicit result alist.
  (setq result (vl-catch-all-apply 'SRF:Prepare (list doc table)))
  (if (not (vl-catch-all-error-p result))
    (progn
      (if (and (= 1 (logand 1 (getvar "UNDOCTL")))
               (= 0 (logand 8 (getvar "UNDOCTL"))))
        (progn (vla-StartUndoMark doc) (setq undo T)))
      (setq result (vl-catch-all-apply 'SRF:Apply (list doc table)))))
  (if (vl-catch-all-error-p result)
    (progn
      (setq restored (SRF:Restore))
      (if undo (vla-EndUndoMark doc))
      (list (cons 'ok nil)
        (cons 'message (strcat (if SRF:failure SRF:failure (vl-catch-all-error-message result))
          (if restored " Sin cambios de opciones pendientes."
            " No se pudo completar la restauracion; usa U antes de continuar.")))))
    (progn
      (if undo (vla-EndUndoMark doc))
      (list (cons 'ok T) (cons 'changed result)))))

(defun SRF:SelectedTable (doc entity / ref name block obj tables)
  (if (not (= "INSERT" (cdr (assoc 0 (entget entity)))))
    (SRF:Fail "Selecciona la insercion del bloque de vineta."))
  (setq ref (vlax-ename->vla-object entity)
        name (if (vlax-property-available-p ref 'EffectiveName)
               (vla-get-EffectiveName ref) (vla-get-Name ref)))
  (if (not (wcmatch (strcase name) "VI?ETA*,VINETA*"))
    (SRF:Fail "El bloque seleccionado no tiene prefijo VINETA / VI?ETA."))
  (setq block (vla-Item (vla-get-Blocks doc) (vla-get-Name ref)))
  (if (= :vlax-true (vla-get-IsXRef block)) (SRF:Fail "No se modifican referencias externas."))
  ;; Enumerate only the selected insertion's actual definition, never all DWG blocks.
  (vlax-for obj block
    (if (SRF:TableP doc obj) (setq tables (cons obj tables))))
  (if (/= 1 (length tables))
    (SRF:Fail "No hay una unica tabla de revisiones compatible dentro de esta insercion."))
  (car tables))

(defun c:ACTUALIZAR-VINETA (/ doc selection table result SRF:failure)
  (if (not (wcmatch (strcase (getvar "PROGRAM")) "*ZW*"))
    (princ "\nACTUALIZAR-VINETA: disponible para ZWCAD; AutoCAD pendiente de validacion.")
    (if (setq selection (entsel "\nSelecciona el bloque de vineta: "))
      (progn
        (setq doc (vla-get-ActiveDocument (vlax-get-acad-object))
              table (vl-catch-all-apply 'SRF:SelectedTable (list doc (car selection))))
        (if (vl-catch-all-error-p table)
          (princ (strcat "\nACTUALIZAR-VINETA: "
            (if SRF:failure SRF:failure (vl-catch-all-error-message table))))
          (progn
            (setq result (SRF:RepairTable doc table))
            (princ (strcat "\nACTUALIZAR-VINETA: "
              (if (cdr (assoc 'ok result))
                (strcat (itoa (cdr (assoc 'changed result)))
                  " Fields reactivados. Revisa la revision actual; guarda si corresponde. U permite deshacer.")
                (cdr (assoc 'message result))))))))))
  (princ))
(princ)
