"""Shared CAD table and native MARCA-SC/MARCA-DE support for reinforcement.

The calculation owns individual table rows, not the drawing or the table style.
Each abutment has an explicit table registration; no moldaje search is involved.
"""

import math
import re

from sincal.runtime import ruta_recurso
from sincal.cad.rebar_table_format import TABLE_FORMAT_SUPPORT


def _quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ') + '"'


def build_marks_support(schedule, rules, abutment_key, *, drawing_units_per_m=1.0,
                        element_key="footing"):
    """Build the transactional bridge to the existing linked-mark commands.

    The table belongs to the whole abutment. Each calculation owns only its
    element's rows; displaying a subset of views never changes the quantities.
    ``srb:preserve-keys`` can be dynamically bound by the detail generator when
    the user chooses to retain an earlier group and its calculated table rows.
    """
    if abutment_key not in ("entrada", "salida"):
        raise ValueError("Estribo no válido para la tabla de marcas.")
    if not isinstance(element_key, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", element_key):
        raise ValueError("Elemento no válido para las filas de la tabla de marcas.")
    if (isinstance(drawing_units_per_m, bool)
            or not isinstance(drawing_units_per_m, (int, float))
            or drawing_units_per_m not in (1, 100, 1000)):
        raise ValueError("Las unidades de dibujo deben ser metros, centímetros o milímetros.")
    if not schedule.is_valid:
        raise ValueError("Corrige el cálculo antes de generar la tabla de marcas.")
    rules_by_key = {rule.key: rule for rule in rules}
    rows, marks, identities = [], set(), set()
    for mark in schedule.marks:
        name = mark.mark.strip()
        if not re.fullmatch(r"[0-9]+[A-Za-z]*", name):
            raise ValueError(f"Marca incompatible con MARCA-SC: {name!r}.")
        if mark.key not in rules_by_key:
            raise ValueError("Falta la regla de separación de una marca.")
        rule = rules_by_key[mark.key]
        # A formerly complete bar becoming the initial lap piece keeps its row
        # identity. The continuation also survives terminal/intermediate changes.
        slot = ("base" if name.upper() == rule.mark.strip().upper()
                else "continuation" if name.upper() == rule.continuation_mark.strip().upper()
                else "terminal")
        identity = f"{element_key}:{mark.key}:{slot}"
        if name.upper() in marks or identity in identities:
            raise ValueError("El cálculo contiene marcas o identidades de pieza duplicadas.")
        spacing = rule.spacing_cm
        if (isinstance(mark.quantity, bool) or mark.quantity <= 0
                or int(mark.quantity) != mark.quantity
                or not all(math.isfinite(v) and v > 0 for v in (mark.diameter_mm, spacing))):
            raise ValueError("Cantidad, diámetro o separación de marca inválidos.")
        marks.add(name.upper())
        identities.add(identity)
        rows.append(f"({_quote(identity)} {_quote(mark.key)} {_quote(name)} "
                    f"{int(mark.quantity)} {mark.diameter_mm:g} {spacing:g})")
    if not rows and not any(rule.removed_pieces for rule in rules_by_key.values()):
        raise ValueError("No hay marcas calculadas para insertar.")
    path = str(ruta_recurso("lisps", "MARCAS-SC.lsp")).replace("\\", "/")
    master = str(ruta_recurso("masters", "FORMATOS ANOTATIVOS ACAD_2025.dwg")).replace("\\", "/")
    return (_SUPPORT.replace("@SCM_PATH@", _quote(path))
            .replace("@MASTER_PATH@", _quote(master))
            .replace("@SCOPE@", _quote(f"ESTRIBO_{abutment_key.upper()}"))
            .replace("@ELEMENT@", _quote(element_key))
            .replace("@ROWS@", "(" + " ".join(rows) + ")")
            .replace("@UNITS@", f"{drawing_units_per_m:g}"))


_SUPPORT = r'''
;;; One table per complete abutment, with independently owned element rows.
;;; B is the TOTAL calculated quantity for a mark, never a visible-view count.
;;; Full DWG copies retain the table and identities; visibility is not an input.
(setq srb:source @SCM_PATH@ srb:master @MASTER_PATH@ srb:scope @SCOPE@ srb:element @ELEMENT@ srb:rows '@ROWS@ srb:units @UNITS@)
(defun srb:fail (message)
  (setq srb:failure message *SINCAL_LIVE_RESULT* (list nil message)) (quit))
(defun srb:load ()
  (if (not (findfile srb:source)) (srb:fail "No se encontro MARCAS-SC.lsp instalado."))
  (load srb:source)
  (if (not (member "SCM:BIND" (atoms-family 1)))
    (srb:fail "No se pudo cargar el sistema de marcas vinculadas.")))
(defun srb:prepare ()
  (SCM:DefinitionNamed "SINCAL_MARCA_SC_V3")
  (SCM:DefinitionNamed "SINCAL_MARCA_DE_V2"))
(defun srb:custom (table row key / value result)
  (setq result (vl-catch-all-apply 'vla-GetCustomData (list table row 0 key 'value)))
  (if (not (vl-catch-all-error-p result))
    (progn (if (= (type value) 'VARIANT) (setq value (vlax-variant-value value)))
      (if (= (type value) 'STR) value))))
(defun srb:put-custom (table row key value)
  (vla-SetCustomData table row 0 key (vlax-make-variant value vlax-vbString)))
(defun srb:owner (table / data)
  (setq data (assoc -3 (entget (vlax-vla-object->ename table) '("SINCAL_REBAR_TABLE_V1"))))
  (if data (cdr (assoc 1000 (cdadr data)))))
(defun srb:register (table / key record en)
  (setq key (strcat "SINCAL_REBAR_TABLE_" srb:scope "_V1"))
  (regapp "SINCAL_REBAR_TABLE_V1")
  (if (not (entmod (append (entget (vlax-vla-object->ename table))
        (list (list -3 (list "SINCAL_REBAR_TABLE_V1" (cons 1000 srb:scope)))))))
    (srb:fail "No se pudo registrar el propietario de la tabla."))
  (setq record (dictsearch (namedobjdict) key))
  (if record
    (progn (dictremove (namedobjdict) key) (entdel (cdr (assoc -1 record)))))
  (setq en (entmakex (list '(0 . "XRECORD") '(100 . "AcDbXrecord") '(280 . 1)
              (cons 1 srb:scope) (cons 340 (vlax-vla-object->ename table)))))
  (if (not (and en (dictadd (namedobjdict) key en)))
    (srb:fail "No se pudo guardar la referencia de tabla.")))
(defun srb:registered (/ record en)
  (setq record (dictsearch (namedobjdict) (strcat "SINCAL_REBAR_TABLE_" srb:scope "_V1")))
  (if (and record (setq en (cdr (assoc 340 record))) (entget en))
    (vlax-ename->vla-object en)))
(defun srb:table-dbx (/ acad major name dbx candidate)
  (setq acad (vlax-get-acad-object) major (substr (getvar "ACADVER") 1 2))
  (foreach name (list (strcat "ObjectDBX.AxDbDocument." major) "ObjectDBX.AxDbDocument"
                      (strcat "ZWCAD.ZcDbDocument." major) "ZWCAD.ZcDbDocument")
    (if (not dbx)
      (progn
        (setq candidate (vl-catch-all-apply 'vla-GetInterfaceObject (list acad name)))
        (if (not (vl-catch-all-error-p candidate)) (setq dbx candidate)))))
  dbx)
(defun srb:copy-table-from-dbx (dbx / block index candidate source objects copied)
  (vla-Open dbx srb:master)
  ;; Only the named prototype block in the master is read, never the target DWG.
  (setq block (vla-Item (vla-get-Blocks dbx) "TABLA-FIERROS") index 0)
  (repeat (vla-get-Count block)
    (setq candidate (vla-Item block index) index (1+ index))
    (if (and (= "AcDbTable" (vla-get-ObjectName candidate)) (SCM:TableP candidate))
      (if source (srb:fail "TABLA-FIERROS contiene mas de una tabla compatible.") (setq source candidate))))
  (if (not source) (srb:fail "TABLA-FIERROS no contiene una tabla compatible de cuatro columnas."))
  (setq objects (vlax-make-safearray vlax-vbObject '(0 . 0)))
  (vlax-safearray-put-element objects 0 source)
  ;; Deep-copy brings the referenced table/text styles and layer. Existing
  ;; named definitions are reused, not overwritten in the destination drawing.
  (setq copied (vla-CopyObjects dbx objects (vla-get-ModelSpace (SCM:Doc))))
  (if (= (type copied) 'VARIANT) (setq copied (vlax-variant-value copied)))
  (car (vlax-safearray->list copied)))
(defun srb:copy-table-template (/ dbx copied failure)
  (if (not (findfile srb:master)) (srb:fail "No se encontro el master de formatos para la tabla de armaduras."))
  (setq dbx (srb:table-dbx))
  (if (not dbx) (srb:fail "No se pudo abrir ObjectDBX para copiar TABLA-FIERROS del master."))
  (setq copied (vl-catch-all-apply 'srb:copy-table-from-dbx (list dbx)))
  (vl-catch-all-apply 'vlax-release-object (list dbx))
  (if (or (vl-catch-all-error-p copied) (not copied))
    (srb:fail "No se pudo copiar TABLA-FIERROS del master. Revise que contenga el ejemplo de tabla de marcas."))
  copied)
(defun srb:reset-template-row (table model / column)
  ;; Delete the old data cell containers completely, including custom IDs.
  ;; InsertRows alone inherits unscaled table-style defaults; restore the
  ;; prototype's explicit cell formats before fixing the row height.
  (vla-DeleteRows table 2 1)
  (vla-InsertRows table 2 (vla-GetRowHeight model 2) 1)
  (setq column 0)
  (repeat 4
    (srb:copy-cell-format model table 2 2 column)
    (setq column (1+ column)))
  (vla-SetRowHeight table 2 (vla-GetRowHeight model 2)))
(defun srb:clear-template-data (table / model result key en)
  ;; A short, temporary copy retains the actual overrides while all example
  ;; data cells and their IDs are deleted. Only the clean table is registered.
  (if (> (vla-get-Rows table) 3) (vla-DeleteRows table 3 (- (vla-get-Rows table) 3)))
  (setq model (vla-Copy table))
  (setq result (vl-catch-all-apply 'srb:reset-template-row (list table model)))
  (vla-Delete model)
  (if (vl-catch-all-error-p result)
    (srb:fail "No se pudo preparar la fila vacia con el formato del master."))
  (if (or (SCM:RowID table 2) (srb:custom table 2 "SINCAL_REBAR_OWNER_V1")
          (srb:custom table 2 "SINCAL_REBAR_PIECE_V1"))
    (srb:fail "No se pudieron limpiar los identificadores de la tabla de ejemplo."))
  (setq en (vlax-vla-object->ename table))
  (foreach key '("SINCAL_REBAR_TABLE_V1" "SINCAL_REBAR_TABLE_FORMAT_V1" "SINCAL_REBAR")
    (if (assoc -3 (entget en (list key)))
      (if (not (entmod (append (entget en) (list (list -3 (list key))))))
        (srb:fail "No se pudo limpiar la referencia de la tabla de ejemplo."))))
  table)
(defun srb:new-table (/ point table ratio origin)
  (setq point (getpoint "\nEsquina superior izquierda de la tabla de marcas: "))
  (if (not point) (srb:fail "Insercion cancelada; no se modificaron las armaduras."))
  ;; The official prototype is drawn at 1:100 M: its ratio is 10 paper/drawing
  ;; units, width 8, rows .5, text .24. Thus 1:75 M scales it by .75, including
  ;; text, margins and borders. Never create through the current table style.
  (setq ratio (getvar "CANNOSCALEVALUE"))
  (if (not (and (numberp ratio) (> ratio 0.0))) (srb:fail "La escala anotativa no es valida."))
  (setq table (srb:clear-template-data (srb:copy-table-template)))
  (vla-SetText table 0 0 (if (= srb:scope "ESTRIBO_ENTRADA") "ARMADURA ESTRIBO ENTRADA" "ARMADURA ESTRIBO SALIDA"))
  (setq origin (vla-get-InsertionPoint table))
  (vla-ScaleEntity table origin (/ 10.0 ratio))
  (vla-Move table origin (vlax-3d-point (trans point 1 0)))
  (vla-RecomputeTableBlock table :vlax-true)
  ;; The first data row is deliberately blank and is claimed only by this scope.
  (srb:put-custom table 2 "SINCAL_REBAR_OWNER_V1" srb:scope)
  (srb:put-custom table 2 "SINCAL_REBAR_ELEMENT_V1" srb:element)
  (setq srb:created-table T)
  table)
(defun srb:table (/ table selected owner)
  (setq srb:adopt-table nil)
  (setq table (srb:registered))
  (if (not table)
    (progn
      (setq selected (entsel "\nSeleccione tabla de marcas de este estribo <Enter: crear tabla>: "))
      (setq table (if selected (vlax-ename->vla-object (car selected)) (srb:new-table)))))
  (if (not (SCM:TableP table))
    (srb:fail "Seleccione una tabla de cuatro columnas: marca, cantidad, diametro y separacion."))
  (if (SCM:Locked table) (srb:fail "La tabla de marcas esta en una capa bloqueada."))
  (if (not (vlax-method-applicable-p table 'SetCustomData))
    (srb:fail "El motor CAD no admite identificadores por fila."))
  (setq owner (srb:owner table))
  (if (and owner (/= owner srb:scope))
    (srb:fail "Esta tabla pertenece a otro estribo. Seleccione la tabla del estribo actual."))
  ;; Only the first explicit selection of an unowned table permits adopting
  ;; existing rows. A later collision in an already-owned table is never taken.
  (setq srb:adopt-table (and selected (not owner)))
  table)
(defun srb:our-row (table row)
  (and (equal srb:scope (srb:custom table row "SINCAL_REBAR_OWNER_V1"))
       (equal srb:element (srb:custom table row "SINCAL_REBAR_ELEMENT_V1"))))
(defun srb:preserved (table row)
  (and (srb:our-row table row) (boundp 'srb:preserve-keys)
       (member (srb:custom table row "SINCAL_REBAR_FAMILY_V1") srb:preserve-keys)))
(defun srb:incoming (/ rows entry)
  (foreach entry srb:rows
    (if (not (and (boundp 'srb:preserve-keys) (member (cadr entry) srb:preserve-keys)))
      (setq rows (cons entry rows))))
  (reverse rows))
(defun srb:owned-row (table identity / row found)
  (setq row 2)
  (while (< row (vla-get-Rows table))
    (if (and (srb:our-row table row)
             (equal identity (srb:custom table row "SINCAL_REBAR_PIECE_V1")))
      (setq found (cons row found)))
    (setq row (1+ row)))
  (if (> (length found) 1) (srb:fail "Identidad de pieza duplicada en la tabla."))
  (car found))
(defun srb:values-match (table row entry / column wanted actual matches)
  (setq column 1 matches T)
  (foreach wanted (cdddr entry)
    (setq actual (distof (SCM:Trim (vla-GetText table row column)) 2))
    (if (not (and actual (equal actual wanted 0.000001))) (setq matches nil))
    (setq column (1+ column)))
  matches)
(defun srb:preflight (table incoming / row marks identities ids mark id owner identity entry changed action)
  ;; Read only the explicitly registered/selected table, before changing any row.
  (setq row 2 srb:adoptions nil)
  (while (< row (vla-get-Rows table))
    (setq mark (SCM:MarkKey (vla-GetText table row 0)) id (SCM:RowID table row)
          owner (srb:custom table row "SINCAL_REBAR_OWNER_V1")
          identity (srb:custom table row "SINCAL_REBAR_PIECE_V1"))
    (if (and (/= mark "") (member mark marks)) (srb:fail "Hay marcas duplicadas en la tabla."))
    (if (/= mark "") (setq marks (cons mark marks)))
    (if (and id (member id ids)) (srb:fail "Hay identificadores de fila duplicados."))
    (if id (setq ids (cons id ids)))
    (if (and owner (/= owner srb:scope)) (srb:fail "La tabla contiene filas de otro estribo."))
    (if (and identity (equal owner srb:scope))
      (progn
        (if (member identity identities) (srb:fail "Hay piezas generadas duplicadas."))
        (setq identities (cons identity identities))))
    (foreach entry incoming
      (if (and (= mark (SCM:MarkKey (nth 2 entry)))
               (not (and (srb:our-row table row) (not (srb:preserved table row)))))
        (if (and srb:adopt-table (not owner))
          (progn
            (setq srb:adoptions (cons (cons row entry) srb:adoptions))
            (if (not (srb:values-match table row entry)) (setq changed T)))
          (srb:fail (strcat "La marca " (nth 2 entry) " ya pertenece a otro elemento o a una fila manual o conservada.")))))
    (setq row (1+ row)))
  (if changed
    (progn
      (initget "Actualizar Cancelar")
      (setq action (getkword "\nLa tabla seleccionada contiene valores distintos del calculo [Actualizar/Cancelar] <Cancelar>: "))
      (if (not (equal action "Actualizar")) (srb:fail "Vinculacion cancelada; se conservo la tabla existente."))))
  T)
(defun srb:adopt-rows (/ adoption row entry)
  (foreach adoption srb:adoptions
    (setq row (car adoption) entry (cdr adoption))
    (srb:put-custom srb:table-object row "SINCAL_REBAR_OWNER_V1" srb:scope)
    (srb:put-custom srb:table-object row "SINCAL_REBAR_ELEMENT_V1" srb:element)
    (srb:put-custom srb:table-object row "SINCAL_REBAR_FAMILY_V1" (cadr entry))
    (srb:put-custom srb:table-object row "SINCAL_REBAR_PIECE_V1" (car entry))
    (SCM:EnsureID srb:table-object row)))
(defun srb:clear-last-owned-row (table / model result)
  ;; Removing every calculated piece must leave a usable empty data row.
  ;; Replace its cell containers, retaining only format and table identity;
  ;; copying text over the old row would retain obsolete MARCA row links.
  (setq model (vla-Copy table))
  (setq result (vl-catch-all-apply 'srb:reset-template-row (list table model)))
  (vla-Delete model)
  (if (vl-catch-all-error-p result)
    (srb:fail "No se pudo preparar la fila vacia al retirar los fierros."))
  (if (or (SCM:RowID table 2) (srb:custom table 2 "SINCAL_REBAR_PIECE_V1"))
    (srb:fail "La fila vacia conserva vinculos de fierros eliminados."))
  (srb:put-custom table 2 "SINCAL_REBAR_OWNER_V1" srb:scope)
  (srb:put-custom table 2 "SINCAL_REBAR_ELEMENT_V1" srb:element))
(defun srb:sync-table (/ incoming row entry target column empty value srb:created-table)
  (setq srb:table-object (srb:table) incoming (srb:incoming))
  (srb:preflight srb:table-object incoming)
  (srb:adopt-rows)
  ;; Delete only obsolete rows of the recalculated element, never other elements
  ;; of the same abutment or rows whose views happen to be hidden in this DWG.
  ;; Work backwards so unrelated rows, styles and stable row IDs remain intact.
  (setq row (1- (vla-get-Rows srb:table-object)))
  (while (>= row 2)
    (if (and (srb:our-row srb:table-object row)
             (not (srb:preserved srb:table-object row))
             (srb:custom srb:table-object row "SINCAL_REBAR_PIECE_V1")
             (not (assoc (srb:custom srb:table-object row "SINCAL_REBAR_PIECE_V1") incoming)))
      (if (= (vla-get-Rows srb:table-object) 3)
        (srb:clear-last-owned-row srb:table-object)
        (vla-DeleteRows srb:table-object row 1)))
    (setq row (1- row)))
  (foreach entry incoming
    (setq target (srb:owned-row srb:table-object (car entry)))
    (if (not target)
      (progn
        (setq row 2 empty nil)
        (while (< row (vla-get-Rows srb:table-object))
          (if (and (srb:our-row srb:table-object row)
                   (not (srb:custom srb:table-object row "SINCAL_REBAR_PIECE_V1"))
                   (= "" (SCM:Trim (vla-GetText srb:table-object row 0)))) (setq empty row))
          (setq row (1+ row)))
        (setq target (if empty empty (vla-get-Rows srb:table-object)))
        (if (not empty) (vla-InsertRows srb:table-object target
                         (vla-GetRowHeight srb:table-object (1- target)) 1))))
    (setq column 0)
    (foreach value (cddr entry)
      (vla-SetText srb:table-object target column
        (if (= (type value) 'STR) value (srb:decimal value)))
      (setq column (1+ column)))
    (srb:put-custom srb:table-object target "SINCAL_REBAR_OWNER_V1" srb:scope)
    (srb:put-custom srb:table-object target "SINCAL_REBAR_ELEMENT_V1" srb:element)
    (srb:put-custom srb:table-object target "SINCAL_REBAR_FAMILY_V1" (cadr entry))
    (srb:put-custom srb:table-object target "SINCAL_REBAR_PIECE_V1" (car entry))
    (SCM:EnsureID srb:table-object target))
  ;; InsertRows and SetText can restore base-style dimensions. Apply the
  ;; untouched master's cell formatting after all data edits, on managed
  ;; tables only; identity, quantities and foreign manual formats stay intact.
  (srb:restore-generated-format srb:table-object)
  (srb:register srb:table-object)
  (vla-Update srb:table-object)
  srb:table-object)
(defun srb:decimal (value / text)
  (if (= (type value) 'STR) value
    (progn (setq text (rtos value 2 6))
      (if (vl-string-search "." text) (setq text (vl-string-right-trim "." (vl-string-right-trim "0" text))))
      text)))
(defun srb:state (obj state / prop allowed found)
  (foreach prop (vlax-invoke obj 'GetDynamicBlockProperties)
    (setq allowed (vlax-get prop 'AllowedValues))
    (if (member state allowed)
      (progn (vlax-put prop 'Value state) (setq found T))))
  (if (not found) (srb:fail (strcat "El bloque de marca no admite el estado " state "."))))
(defun srb:label (point mark state detail quantity length layer tag scale / obj attrs row en layers target)
  (if (not srb:table-object) (srb:fail "La tabla debe sincronizarse antes de insertar marcas."))
  (setq row (SCM:RowByMark srb:table-object mark))
  (setq layers (vla-get-Layers (SCM:Doc)))
  (if (not (tblsearch "LAYER" layer)) (vla-Add layers layer))
  (setq target (vla-item layers layer))
  (if (= :vlax-true (vla-get-Lock target)) (srb:fail "La capa de marcas esta bloqueada."))
  (setq obj (vla-InsertBlock (vla-get-ModelSpace (SCM:Doc)) (vlax-3d-point point)
              (if detail "SINCAL_MARCA_DE_V2" "SINCAL_MARCA_SC_V3") scale scale scale 0.0))
  (vla-put-Layer obj layer)
  (srb:state obj state)
  (if detail
    (progn (setq attrs (SCM:Attrs obj))
      (SCM:PutText (cdr (assoc "CANT_TOTAL" attrs)) (srb:decimal quantity))
      (SCM:PutText (cdr (assoc "LARGO" attrs)) (strcat "L=" (srb:decimal length)))))
  (SCM:Bind obj srb:table-object row)
  (setq en (vlax-vla-object->ename obj))
  (regapp "SINCAL_REBAR")
  (if (not (entmod (append (entget en) (list (list -3 (list "SINCAL_REBAR" (cons 1000 tag)))))))
    (srb:fail "No se pudo identificar la marca insertada."))
  (setq srb:labels (cons obj srb:labels))
  en)
(defun srb:finish (/ obj meta affected)
  ;; One existing marks-system pass repairs fields after row movement, including
  ;; previously inserted views. This is not a moldaje/geometry identification scan.
  (foreach obj (SCM:Managed)
    (setq meta (SCM:Metadata obj))
    (if (and meta (= (car meta) (vla-get-Handle srb:table-object)))
      (progn (SCM:SyncOne obj) (setq affected (cons obj affected)))))
  (if affected (SCM:Evaluate affected))
  (setq SCM:pending nil)
  ;; Enable once after all rows and labels exist, never for individual bars.
  (SCM:EnableAuto))
(defun srb:restore-vars (/ pair)
  (foreach pair srb:variables (vl-catch-all-apply 'setvar (list (car pair) (cdr pair)))))
(defun srb:run (fn / *error* started touched anchor key SCM:busy SCM:defer-auto
                       SCM:changed srb:failure srb:table-object srb:labels srb:preserve-keys
                       srb:adopt-table srb:adoptions srb:variables)
  (setq *SINCAL_LIVE_RESULT* nil SCM:busy T SCM:defer-auto T)
  (setq srb:variables (mapcar '(lambda (name) (cons name (getvar name))) '("CLAYER" "FILLETRAD" "CMDECHO")))
  (defun *error* (message)
    (if started
      (progn (command-s "_.UNDO" "_End") (if touched (command-s "_.U"))))
    (srb:restore-vars)
    (if (member "SCM:ENABLEAUTO" (atoms-family 1))
      (vl-catch-all-apply 'SCM:EnableAuto nil))
    (setq *SINCAL_LIVE_RESULT* (list nil
      (if srb:failure srb:failure (if (and message (not (wcmatch (strcase message) "*CANCEL*,*QUIT*,*BREAK*,*EXIT ABORT*")))
        (strcat "No se insertaron armaduras: " message)
        "Operacion cancelada; se restauraron las armaduras y la tabla."))))
    (princ (strcat "\n[SINCAL] " (cadr *SINCAL_LIVE_RESULT*))) (princ))
  (if (= 0 (logand 1 (getvar "UNDOCTL"))) (srb:fail "Active UNDO antes de insertar armaduras."))
  (srb:load)
  (command "_.UNDO" "_Begin") (setq started T)
  ;; A transient dictionary record gives this undo group a real modification
  ;; even when the first selection is cancelled. U cannot undo an earlier action.
  (setq key "SINCAL_REBAR_TRANSACTION_V1")
  (if (dictsearch (namedobjdict) key) (srb:fail "Ya existe una transaccion de armaduras activa."))
  (setq anchor (entmakex '((0 . "XRECORD") (100 . "AcDbXrecord") (280 . 1) (1 . "temporary"))))
  (if (not anchor) (srb:fail "No se pudo iniciar la transaccion de armaduras."))
  (setq touched T)
  (if (not (dictadd (namedobjdict) key anchor)) (srb:fail "No se pudo iniciar la transaccion de armaduras."))
  (dictremove (namedobjdict) key) (entdel anchor)
  (apply fn nil)
  (if (not (car *SINCAL_LIVE_RESULT*))
    (srb:fail (if (cadr *SINCAL_LIVE_RESULT*) (cadr *SINCAL_LIVE_RESULT*) "No se completo la insercion de armaduras.")))
  (srb:restore-vars)
  (command "_.UNDO" "_End") (setq started nil)
  (princ))
'''

_SUPPORT += TABLE_FORMAT_SUPPORT
