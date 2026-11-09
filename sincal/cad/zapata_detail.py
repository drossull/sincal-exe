"""Generación AutoLISP del despiece actualizable de una zapata."""
from __future__ import annotations

import math

from sincal.rebar.detail import DETAIL_GROUP_KEYS, DETAIL_GROUP_ORDER, build_detail_groups
from sincal.cad.rebar_marks import build_marks_support


DETAIL_SLOT_PITCH_M = 3.0
DETAIL_MARK_VERSION = "DE2"


def _fmt(value):
    return f"{value:.9f}".rstrip("0").rstrip(".")


def _point(point):
    return f"(list {_fmt(point[0])} {_fmt(point[1])} 0.0)"


def _shift(point, offset):
    return point[0] + offset[0], point[1] + offset[1]


def _dimension_location(first, last, offset):
    dx, dy = last[0] - first[0], last[1] - first[1]
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        return first
    normal = (-dy / length, dx / length)
    return (
        (first[0] + last[0]) / 2.0 + normal[0] * offset,
        (first[1] + last[1]) / 2.0 + normal[1] * offset,
    )


def _lisp_string(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _polyline_command(piece, offset, tag):
    data = [
        '(cons 0 "LWPOLYLINE")', '(cons 100 "AcDbEntity")',
        f'(cons 8 "{piece.layer}")', '(cons 100 "AcDbPolyline")',
        f'(cons 90 {len(piece.vertices_m)})', '(cons 70 0)',
    ]
    for point, bulge in zip(piece.vertices_m, piece.bulges):
        shifted = _shift(point, offset)
        data.append(f'(cons 10 (list {_fmt(shifted[0])} {_fmt(shifted[1])}))')
        if abs(bulge) > 1e-12:
            data.append(f'(cons 42 {_fmt(bulge)})')
    return f'(sincal:detail-add (entmakex (list {" ".join(data)})) ss "{tag}")'


def _piece_commands(piece, offset, index, tag):
    commands = [_polyline_command(piece, offset, tag)]
    dim_offset = 0.28 if index == 0 else -0.30 - (index - 1) * 0.18
    for partial_index, ((first, last), value) in enumerate(zip(piece.partial_segments_m, piece.partials_cm)):
        first = _shift(first, offset)
        last = _shift(last, offset)
        location = _dimension_location(first, last, dim_offset)
        text = str(value)
        if partial_index == piece.variable_partial_index:
            constant = piece.total_cm - value
            lower = min(variant.length_cm for variant in piece.length_variants) - constant
            upper = max(variant.length_cm for variant in piece.length_variants) - constant
            text = f"VAR. {_fmt(lower)}-{_fmt(upper)}"
        commands.append(
            f'(sincal:partial-dim {_point(first)} {_point(last)} {_point(location)} '
            f'"{text}" "{piece.layer}" "{tag}" ss)'
        )
    if len(piece.length_variants) > 1:
        # Notes describe lengths, never replace the native MARCA-DE. Keep the
        # full list to the right in short columns so adjacent 3 m slots remain
        # clear, even when a skew produces many distinct lengths.
        x = max(point[0] + offset[0] for point in piece.vertices_m) + 0.7
        y = max(point[1] + offset[1] for point in piece.vertices_m) + 0.55
        notes = [((x, y), "SERIE VARIABLE - CANT. x L DESARROLLADO (cm)"),
                 ((x, y - 0.22), "Geometria representativa: largo maximo")]
        for variant_index, variant in enumerate(piece.length_variants):
            column, row = divmod(variant_index, 8)
            notes.append(((x + column * 2.4, y - 0.52 - row * 0.22),
                          f"{variant.quantity} x {_fmt(variant.length_cm)}"))
        for point, text in notes:
            commands.append(
                f'(sincal:series-note {_point(point)} "{_lisp_string(text)}" '
                f'"{piece.layer}" "{tag}" ss)')
    return commands


def _group_definition(group, abutment_key):
    block_name = f"SINCAL_ZAP_{abutment_key.upper()}_{group.group_id}_{DETAIL_MARK_VERSION}_{group.fingerprint.upper()}"
    entity_tag = f"SINCAL_DETAIL_ENTITY|{abutment_key.upper()}|{group.group_id}|{group.fingerprint}"
    commands = []
    for index, (piece, offset) in enumerate(zip(group.pieces, group.offsets_m)):
        commands.extend(_piece_commands(piece, offset, index, entity_tag))
    lap_layer = group.pieces[0].layer
    for lap_start, lap_end, dimension_y in group.laps_m:
        commands.append(
            f'(sincal:lap-dim {_point((lap_start, 0.0))} {_point((lap_end, 0.0))} '
            f'{_point(((lap_start + lap_end) / 2.0, dimension_y))} '
            f'"{lap_layer}" "{entity_tag}" ss)'
        )
    body = "\n      ".join(commands)
    return block_name, f'''(if (and (sincal:planned-block-p plans "{block_name}")
         (not (tblsearch "BLOCK" "{block_name}")))
    (progn
      (setq ss (ssadd))
      {body}
      (if (not (sincal:create-detail-block "{block_name}" ss))
        (setq sincal:abort T))))'''


def _label_recipe(group):
    """Keep linked dynamic references outside the immutable geometry block."""
    records = []
    for index, (piece, offset) in enumerate(zip(group.pieces, group.offsets_m)):
        point = (
            min(p[0] + offset[0] for p in piece.vertices_m),
            min(p[1] + offset[1] for p in piece.vertices_m) - 0.42 - index * 0.20,
        )
        state = "SUP_SUPLE" if piece.key == "suple" else "NORMAL"
        length = str(piece.total_cm)
        if len(piece.length_variants) > 1:
            lower = min(variant.length_cm for variant in piece.length_variants)
            upper = max(variant.length_cm for variant in piece.length_variants)
            # The existing bridge accepts a string in srb:decimal and writes
            # it into the editable native LARGO attribute. No new block type.
            length = f'"VAR. {_fmt(lower)}-{_fmt(upper)} cm"'
        records.append(
            f'(list {_point(point)} "{piece.mark}" "{state}" '
            f'{piece.quantity} {length} "{piece.layer}")'
        )
    return f'(list {" ".join(records)})'


def _annotation_support(master_path):
    master = _lisp_string(master_path)
    return f'''(defun sincal:item (collection name / result)
  (setq result (vl-catch-all-apply 'vla-Item (list collection name)))
  (if (vl-catch-all-error-p result) nil result))
(defun sincal:detail-ready (database)
  (and (sincal:item (vla-get-DimStyles database) "GSG_COTAS")
       (sincal:item (vla-get-DimStyles database) "GSG_ARM-COTAS")))
(defun sincal:get-dbx (acad / major names dbx candidate)
  (setq major (substr (getvar "ACADVER") 1 2)
        names (list (strcat "ObjectDBX.AxDbDocument." major)
                    "ObjectDBX.AxDbDocument"
                    (strcat "ZWCAD.ZcDbDocument." major)
                    "ZWCAD.ZcDbDocument")
        dbx nil)
  (foreach candidate names
    (if (not dbx)
      (progn
        (setq dbx (vl-catch-all-apply 'vla-GetInterfaceObject (list acad candidate)))
        (if (vl-catch-all-error-p dbx) (setq dbx nil)))))
  dbx)
(defun sincal:copy-style (source-db source-collection target-collection name / item objects result)
  (if (setq item (sincal:item source-collection name))
    (progn
      (setq objects (vlax-make-safearray vlax-vbObject '(0 . 0)))
      (vlax-safearray-put-element objects 0 item)
      (setq result (vl-catch-all-apply 'vla-CopyObjects (list source-db objects target-collection)))
      (not (vl-catch-all-error-p result)))))
(defun sincal:import-detail-styles (acad doc / dbx opened name ok)
  (setq ok T)
  (if (not (findfile "{master}"))
    (setq ok nil)
    (progn
      (setq dbx (sincal:get-dbx acad))
      (if (not dbx)
        (setq ok nil)
        (progn
          (setq opened (vl-catch-all-apply 'vla-Open (list dbx "{master}")))
          (if (vl-catch-all-error-p opened)
            (setq ok nil)
            (progn
              (foreach name '("GSG_COTAS" "GSG_ARM-COTAS")
                (if (not (sincal:item (vla-get-DimStyles doc) name))
                  (if (not (sincal:copy-style dbx (vla-get-DimStyles dbx)
                                               (vla-get-DimStyles doc) name))
                    (setq ok nil))))))
          (vl-catch-all-apply 'vlax-release-object (list dbx))))))
  (and ok (sincal:detail-ready doc)))
(defun sincal:ensure-detail-styles (acad doc)
  (or (sincal:detail-ready doc) (sincal:import-detail-styles acad doc)))'''


def build_zapata_detail_lisp(schedule, rules, geometry, abutment_key, master_path,
                            *, drawing_units_per_m=1.0):
    """Keep detail block definitions in metres and place them in drawing units."""
    if (isinstance(drawing_units_per_m, bool)
            or not isinstance(drawing_units_per_m, (int, float))
            or not math.isfinite(drawing_units_per_m)
            or drawing_units_per_m not in (1, 100, 1000)):
        raise ValueError("Selecciona unidades de dibujo en metros, centímetros o milímetros.")
    drawing_scale = _fmt(drawing_units_per_m)
    slot_pitch = _fmt(DETAIL_SLOT_PITCH_M * drawing_units_per_m)
    groups = build_detail_groups(schedule, rules, geometry)
    group_map = {group.group_id: group for group in groups}
    definitions = []
    label_recipes = []
    desired = []
    for slot, group_id in enumerate(DETAIL_GROUP_ORDER):
        group = group_map.get(group_id)
        prefix = f"SINCAL_DETAIL|{abutment_key.upper()}|{group_id}|"
        if group:
            block_name, definition = _group_definition(group, abutment_key)
            definitions.append(definition)
            label_recipes.append(f'((= name "{block_name}") {_label_recipe(group)})')
            exact_tag = f"{prefix}{DETAIL_MARK_VERSION}|{group.fingerprint}|{slot}"
            label = ", ".join(piece.mark for piece in group.pieces)
            desired.append((group_id, slot, prefix, exact_tag, block_name, label, group.pieces[0].layer))
        else:
            desired.append((group_id, slot, prefix, "", "", group_id, "0"))

    infer_base = []
    planning = []
    for group_id, slot, prefix, exact_tag, block_name, label, layer in desired:
        infer_base.append(
            f'(if (and (not base) (setq old (sincal:find-detail "{prefix}"))) '
            f'(progn (setq ip (trans (cdr (assoc 10 (entget old))) old 0)) '
            f'(setq base (list (car ip) (+ (cadr ip) {_fmt(slot * DETAIL_SLOT_PITCH_M * drawing_units_per_m)}) 0.0))))'
        )
        planning.append(
            f'(setq plan (sincal:plan-detail "{prefix}" "{exact_tag}" "{block_name}" '
            f'"{label}" "{layer}" base {slot} "{DETAIL_GROUP_KEYS[group_id]}"))\n'
            f'    (if plan (setq plans (cons plan plans)))'
        )

    definitions_text = "\n  ".join(definitions)
    infer_text = "\n    ".join(infer_base)
    planning_text = "\n    ".join(planning)
    recipes_text = "\n    ".join(label_recipes)
    support = _annotation_support(master_path)
    marks_support = build_marks_support(schedule, rules, abutment_key,
                                        drawing_units_per_m=drawing_units_per_m)
    return f'''(vl-load-com)
{marks_support}
{support}
(defun sincal:tag (ent value / data)
  (regapp "SINCAL_REBAR")
  (setq data (entget ent))
  (entmod (append data (list (list -3 (list "SINCAL_REBAR" (cons 1000 value)))))) ent)
(defun sincal:xdata-value (ent / xd)
  (setq xd (assoc -3 (entget ent '("SINCAL_REBAR"))))
  (if xd (cdr (assoc 1000 (cdr (cadr xd))))))
(defun sincal:starts-with (text prefix)
  (and text (= 0 (vl-string-search prefix text))))
(defun sincal:detail-scale-p (ent / data)
  (setq data (entget ent))
  (and (equal (cdr (assoc 41 data)) {drawing_scale} 0.000000001)
       (equal (cdr (assoc 42 data)) {drawing_scale} 0.000000001)
       (equal (cdr (assoc 43 data)) {drawing_scale} 0.000000001)))
(defun sincal:find-detail (prefix / ss index ent found)
  (setq found nil)
  (if (setq ss (ssget "_X" '((0 . "INSERT") (-3 ("SINCAL_REBAR")))))
    (progn
      (setq index 0)
      (while (and (< index (sslength ss)) (not found))
        (setq ent (ssname ss index))
        (if (sincal:starts-with (sincal:xdata-value ent) prefix) (setq found ent))
        (setq index (1+ index)))))
  found)
(defun sincal:detail-add (ent ss tag)
  (if ent (progn (sincal:tag ent tag) (ssadd ent ss))) ent)
(defun sincal:detail-layer (name / layer)
  (setq layer (sincal:item (vla-get-Layers doc) name))
  (if (not layer) (setq layer (vla-Add (vla-get-Layers doc) name)))
  (if (= :vlax-true (vla-get-Lock layer))
    (srb:fail "La capa de los fierros esta bloqueada.")))
(defun sincal:erase-selection (ss / index ent)
  (setq index 0)
  (repeat (sslength ss)
    (setq ent (ssname ss index))
    (if (entget ent) (entdel ent))
    (setq index (1+ index))))
(defun sincal:planned-block-p (plans name / found plan)
  (setq found nil)
  (foreach plan plans
    (if (= (nth 2 plan) name) (setq found T)))
  found)
(defun sincal:create-detail-block (name ss / count objects index ent block result)
  (if (tblsearch "BLOCK" name)
    T
    (progn
      (setq count (sslength ss))
      (if (= count 0)
        nil
        (progn
          (setq block (vla-Add (vla-get-Blocks doc) (vlax-3d-point (list 0.0 0.0 0.0)) name)
                objects (vlax-make-safearray vlax-vbObject (cons 0 (1- count)))
                index 0)
          (repeat count
            (setq ent (ssname ss index))
            (vlax-safearray-put-element objects index (vlax-ename->vla-object ent))
            (setq index (1+ index)))
          (setq result (vl-catch-all-apply 'vla-CopyObjects (list doc objects block)))
          (if (vl-catch-all-error-p result)
            (progn
              (sincal:erase-selection ss)
              (vl-catch-all-apply 'vla-Delete (list block))
              nil)
            (progn
              (sincal:erase-selection ss)
              T)))))))
(defun sincal:partial-dim (p1 p2 location text layer tag ss / obj ent)
  (setq obj (vla-AddDimAligned ms (vlax-3d-point p1) (vlax-3d-point p2)
                                (vlax-3d-point location)))
  (vla-put-StyleName obj "GSG_ARM-COTAS")
  (vla-put-TextOverride obj text)
  (vla-put-Layer obj layer)
  (setq ent (vlax-vla-object->ename obj))
  (sincal:detail-add ent ss tag))
(defun sincal:series-note (point text layer tag ss / ent)
  (setq ent (entmakex (list '(0 . "TEXT") '(100 . "AcDbEntity")
             (cons 8 layer) '(100 . "AcDbText") (cons 10 point)
             '(40 . 0.12) (cons 1 text) '(7 . "Standard") '(50 . 0.0))))
  (if (not ent) (srb:fail "No se pudo crear el listado de largos variables."))
  (sincal:detail-add ent ss tag))
(defun sincal:lap-dim (p1 p2 location layer tag ss / obj ent)
  (setq obj (vla-AddDimAligned ms (vlax-3d-point p1) (vlax-3d-point p2)
                                (vlax-3d-point location)))
  (vla-put-StyleName obj "GSG_COTAS")
  (vla-put-TextOverride obj "<>\\XALTERNADO")
  (vla-put-Layer obj layer)
  (setq ent (vlax-vla-object->ename obj))
  (sincal:detail-add ent ss tag))
(defun sincal:detail-recipes (name)
  (cond
    {recipes_text}))
;;; Linked native blocks must stay at ModelSpace level, never inside geometry.
;;; Explicit owner handles prevent a copied group from deleting original labels.
(defun sincal:label-owner-p (label owner / xd)
  (and label owner (entget label)
       (setq xd (assoc -3 (entget label '("SINCAL_DETAIL_OWNER"))))
       (= (cdr (assoc 1005 (cdadr xd))) (cdr (assoc 5 (entget owner))))))
(defun sincal:detail-label-refs (owner / dict record pair label refs)
  (if (and owner (setq dict (cdr (assoc 360 (entget owner))))
           (setq record (dictsearch dict "SINCAL_DETAIL_LABELS_V1")))
    (foreach pair record
      (if (= (car pair) 1)
        (progn
          (setq label (handent (cdr pair)))
          (setq refs (append refs (list (if (sincal:label-owner-p label owner) label nil))))))))
  refs)
(defun sincal:store-label-refs (owner labels / dict old data label record)
  (setq dict (vlax-vla-object->ename
               (vla-GetExtensionDictionary (vlax-ename->vla-object owner))))
  (if (setq old (dictsearch dict "SINCAL_DETAIL_LABELS_V1"))
    (progn (dictremove dict "SINCAL_DETAIL_LABELS_V1") (entdel (cdr (assoc -1 old)))))
  (setq data '((0 . "XRECORD") (100 . "AcDbXrecord") (280 . 1)))
  (regapp "SINCAL_DETAIL_OWNER")
  (foreach label labels
    (entmod (append (entget label)
      (list (list -3 (list "SINCAL_DETAIL_OWNER" (cons 1005 (cdr (assoc 5 (entget owner)))))))))
    (setq data (append data (list (cons 1 (cdr (assoc 5 (entget label))))))))
  (setq record (entmakex data))
  (if (not (and record (dictadd dict "SINCAL_DETAIL_LABELS_V1" record)))
    (srb:fail "No se pudo registrar el vinculo entre despiece y marcas.")))
(defun sincal:erase-detail-labels (owner / label)
  (foreach label (sincal:detail-label-refs owner)
    (if label
      (progn (SCM:WritableMark (vlax-ename->vla-object label)) (entdel label)))))
(defun sincal:sync-detail-labels (owner old replace-values / recipes refs index recipe previous point label labels obj attrs)
  (setq recipes (sincal:detail-recipes (cdr (assoc 2 (entget owner))))
        refs (sincal:detail-label-refs (if old old owner)) index 0)
  (foreach recipe recipes
    (setq previous (nth index refs))
    (cond
      ((and previous (not replace-values)) (setq label previous))
      ((and previous
            (= "SINCAL_MARCA_DE_V2" (SCM:UpName (vlax-ename->vla-object previous))))
        ;; Update accepted calculated values in place. Native flip, visibility,
        ;; rotation, position and all annotation contexts stay as the user set them.
        (setq obj (SCM:WritableMark (vlax-ename->vla-object previous)) attrs (SCM:Attrs obj))
        (SCM:PutText (cdr (assoc "CANT_TOTAL" attrs)) (srb:decimal (nth 3 recipe)))
        (SCM:PutText (cdr (assoc "LARGO" attrs)) (strcat "L=" (srb:decimal (nth 4 recipe))))
        (SCM:Bind obj srb:table-object (SCM:RowByMark srb:table-object (nth 1 recipe)))
        (vla-put-Layer obj (nth 5 recipe))
        (sincal:tag previous (strcat "SINCAL_DETAIL_MARK|" (sincal:xdata-value owner)))
        (setq label previous))
      (T
        (if previous (SCM:WritableMark (vlax-ename->vla-object previous)))
        (setq point
          (if previous (trans (cdr (assoc 10 (entget previous))) previous 0)
            (sincal:detail-world-point owner (car recipe))))
        (setq label (srb:label point (nth 1 recipe) (nth 2 recipe) T
          (nth 3 recipe) (nth 4 recipe) (nth 5 recipe)
          (strcat "SINCAL_DETAIL_MARK|" (sincal:xdata-value owner)) 2.5))
        (if (not label) (srb:fail "No se pudo insertar MARCA-DE del despiece."))
        (if previous (entdel previous))))
    (setq labels (append labels (list label)) index (1+ index)))
  (while (< index (length refs))
    (if (setq label (nth index refs))
      (progn (SCM:WritableMark (vlax-ename->vla-object label)) (entdel label)))
    (setq index (1+ index)))
  (sincal:store-label-refs owner labels))
(defun sincal:detail-world-point (owner local / data origin sx sy angle x y)
  (setq data (entget owner) origin (trans (cdr (assoc 10 data)) owner 0)
        sx (cdr (assoc 41 data)) sy (cdr (assoc 42 data)) angle (cdr (assoc 50 data))
        x (* sx (car local)) y (* sy (cadr local)))
  (list (+ (car origin) (- (* x (cos angle)) (* y (sin angle))))
        (+ (cadr origin) (+ (* x (sin angle)) (* y (cos angle)))) (caddr origin)))
(defun sincal:plan-detail (prefix exact block-name label layer base slot rule-key / old oldtag action point)
  (setq old (sincal:find-detail prefix)
        oldtag (if old (sincal:xdata-value old) nil)
        point (if old (trans (cdr (assoc 10 (entget old))) old 0)
                    (list (car base) (- (cadr base) (* slot {slot_pitch})) 0.0)))
  (cond
    ((and old (= oldtag exact) (sincal:detail-scale-p old))
      (setq sincal:unchanged (cons old sincal:unchanged)) nil)
    ((and (not old) (= block-name "")) nil)
    ((and (not old) (/= block-name "")) (list "Actualizar" nil block-name exact layer point))
    (T
      (if sincal:update-all
        (setq action "Actualizar")
        (progn
          (initget "Actualizar Conservar Todas Cancelar")
          (setq action (getkword
            (strcat "\\nSINCAL: cambio detectado en " label
                    " [Actualizar/Conservar/Todas/Cancelar] <Actualizar>: ")))
          (if (not action) (setq action "Actualizar"))))
      (cond
        ((= action "Todas") (setq sincal:update-all T action "Actualizar"))
        ((= action "Conservar") (setq srb:preserve-keys (cons rule-key srb:preserve-keys)))
        ((= action "Cancelar") (setq sincal:abort T)))
      (if (= action "Actualizar") (list action old block-name exact layer point) nil))))
(defun sincal:apply-plan (plan / old block-name exact layer point obj)
  (setq old (nth 1 plan) block-name (nth 2 plan) exact (nth 3 plan)
        layer (nth 4 plan) point (nth 5 plan))
  (if (and old (SCM:Locked (vlax-ename->vla-object old)))
    (srb:fail "La capa del despiece anterior esta bloqueada."))
  (cond
    ((= block-name "")
      (if old (progn (sincal:erase-detail-labels old) (entdel old))))
    ((tblsearch "BLOCK" block-name)
      (setq obj (vla-InsertBlock ms (vlax-3d-point point) block-name {drawing_scale} {drawing_scale} {drawing_scale} 0.0))
      (vla-put-Layer obj layer)
      (if old (vla-put-Rotation obj (cdr (assoc 50 (entget old)))))
      (sincal:tag (vlax-vla-object->ename obj) exact)
      (sincal:sync-detail-labels (vlax-vla-object->ename obj) old T)
      (if old (entdel old)))
    (T
      (srb:fail (strcat "SINCAL no pudo construir el detalle " block-name
                       ". Se conservo la referencia anterior.")))))
(defun sincal:generate-detail (/ acad doc ms ss base old ip plans plan sincal:update-all sincal:abort sincal:unchanged srb:preserve-keys)
  (setq acad (vlax-get-acad-object) doc (vla-get-ActiveDocument acad)
        ms (vla-get-ModelSpace doc) plans nil sincal:update-all nil sincal:abort nil)
  (srb:prepare)
  (if (not (sincal:ensure-detail-styles acad doc))
    (srb:fail "SINCAL no pudo importar los estilos de cotas. No se modifico el despiece."))
  {infer_text}
  (if (not base)
    (progn
      (setq base (getpoint "\\nPunto superior izquierdo del despiece de zapata: "))
      (if base (setq base (trans base 1 0)))))
  (if (not base) (srb:fail "Despiece cancelado; no se indico punto de insercion."))
  {planning_text}
  (if sincal:abort (srb:fail "Actualizacion cancelada; no se reemplazo ningun detalle."))
  ;; Choose Conservar before touching the shared rows or native mark blocks.
  (srb:sync-table)
  (foreach plan plans (sincal:detail-layer (nth 4 plan)))
  {definitions_text}
  (if sincal:abort (srb:fail "No se completaron los bloques; se conservaron los detalles anteriores."))
  (foreach plan (reverse plans) (sincal:apply-plan plan))
  (foreach old sincal:unchanged (sincal:sync-detail-labels old nil nil))
  (srb:finish)
  (setq *SINCAL_LIVE_RESULT* (list T "Despiece de zapata y marcas vinculadas revisados y actualizados.")))
(defun c:SINCAL-ZAPATA-DESPIECE ()
  (srb:run 'sincal:generate-detail)
  (princ))
'''
