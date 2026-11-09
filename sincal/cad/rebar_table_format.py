"""In-place format migration for the generator's original generic tables.

Only an exact owned legacy signature is eligible. The table object, data rows
and their identities remain unchanged, so native fields keep their targets.
"""

TABLE_FORMAT_SUPPORT = r'''
(defun srb:template-managed-p (table / data)
  (setq data (assoc -3 (entget (vlax-vla-object->ename table) '("SINCAL_REBAR_TABLE_FORMAT_V1"))))
  (and data (equal (cdr (assoc 1000 (cdadr data))) "TABLA-FIERROS")))
(defun srb:tag-table-template (table)
  (regapp "SINCAL_REBAR_TABLE_FORMAT_V1")
  (if (not (entmod (append (entget (vlax-vla-object->ename table))
        (list (list -3 (list "SINCAL_REBAR_TABLE_FORMAT_V1" '(1000 . "TABLA-FIERROS")))))))
    (srb:fail "No se pudo registrar el formato de la tabla de armaduras.")))
(defun srb:legacy-table-p (table / column headers match)
  (setq headers '("MARCA" "CANTIDAD" "DIAMETRO" "SEPARACION") column 0
        match (and (equal (srb:owner table) srb:scope)
                   (= (vla-get-Columns table) 4)
                   (>= (vla-get-Rows table) 3)
                   (equal (vla-GetText table 0 0) (strcat "ARMADURAS " srb:scope))))
  (foreach header headers
    (if (not (equal (vla-GetText table 1 column) header)) (setq match nil))
    (setq column (1+ column)))
  match)
(defun srb:copy-cell-format (source target sr tr column / edge margin)
  ;; The other cells of the merged title have no independent cell properties.
  (if (or (> tr 0) (= column 0))
    (progn
      (vla-SetCellTextStyle target tr column (vla-GetCellTextStyle source sr column))
      (vla-SetCellTextHeight target tr column (vla-GetCellTextHeight source sr column))
      (vla-SetCellAlignment target tr column (vla-GetCellAlignment source sr column))
      (vla-SetCellContentColor target tr column (vla-GetCellContentColor source sr column))
      (vla-SetCellBackgroundColorNone target tr column (vla-GetCellBackgroundColorNone source sr column))
      (if (= (vla-GetCellBackgroundColorNone source sr column) :vlax-false)
        (vla-SetCellBackgroundColor target tr column (vla-GetCellBackgroundColor source sr column)))
      (foreach margin '(1 2 4 8 16 32)
        (vla-SetMargin target tr column margin (vla-GetMargin source sr column margin)))
      (foreach edge '(1 2 4 8)
        (vla-SetCellGridLineWeight target tr column edge (vla-GetCellGridLineWeight source sr column edge))
        (vla-SetCellGridColor target tr column edge (vla-GetCellGridColor source sr column edge))
        (vla-SetCellGridVisibility target tr column edge (vla-GetCellGridVisibility source sr column edge))))))
(defun srb:apply-table-format (table model / row column sr)
  (vla-put-StyleName table (vla-get-StyleName model))
  (vla-put-Layer table (vla-get-Layer model))
  (vla-put-TrueColor table (vla-get-TrueColor model))
  (vla-put-Lineweight table (vla-get-Lineweight model))
  (vla-put-Linetype table (vla-get-Linetype model))
  (vla-put-HorzCellMargin table (vla-get-HorzCellMargin model))
  (vla-put-VertCellMargin table (vla-get-VertCellMargin model))
  ;; Text replacement resets content formatting in AutoCAD. Do this first.
  (vla-SetText table 0 0 (strcat "ARMADURA ESTRIBO " (if (= srb:scope "ESTRIBO_ENTRADA") "ENTRADA" "SALIDA")))
  (setq column 0)
  (repeat 4
    (vla-SetText table 1 column (vla-GetText model 1 column))
    (setq column (1+ column)))
  (setq row 0)
  (repeat (vla-get-Rows table)
    (setq sr (min row 2) column 0)
    (repeat 4
      (srb:copy-cell-format model table sr row column)
      (setq column (1+ column)))
    (setq row (1+ row)))
  ;; All data values stay put; reset sizes only after content/margins are fixed.
  (setq column 0)
  (repeat 4
    (vla-SetColumnWidth table column (vla-GetColumnWidth model column))
    (setq column (1+ column)))
  (setq row 0)
  (repeat (vla-get-Rows table)
    (vla-SetRowHeight table row (vla-GetRowHeight model (min row 2)))
    (setq row (1+ row)))
  (vla-Update table))
(defun srb:restore-generated-format (table / model ratio result)
  (if (or srb:created-table (srb:legacy-table-p table)
          (and (equal (srb:owner table) srb:scope)
               (srb:template-managed-p table)))
    (progn
      (setq ratio (getvar "CANNOSCALEVALUE"))
      (if (not (and (numberp ratio) (> ratio 0.0))) (srb:fail "La escala anotativa no es valida."))
      ;; Read the untouched prototype: clearing its sample text would itself
      ;; discard content overrides, so it cannot serve as the format source.
      (setq model (srb:copy-table-template))
      (vla-ScaleEntity model (vlax-3d-point '(0.0 0.0 0.0)) (/ 10.0 ratio))
      (setq result (vl-catch-all-apply 'srb:apply-table-format (list table model)))
      (vla-Delete model)
      (if (vl-catch-all-error-p result)
        (srb:fail (strcat "No se pudo aplicar el formato del master: " (vl-catch-all-error-message result))))
      (srb:tag-table-template table)))
  table)
'''
