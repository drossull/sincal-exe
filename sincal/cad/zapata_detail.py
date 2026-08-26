"""Generación AutoLISP del despiece actualizable de una zapata."""
from __future__ import annotations

import math

from sincal.rebar.detail import DETAIL_GROUP_ORDER, build_detail_groups


DETAIL_SLOT_PITCH_M = 3.0


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
    for (first, last), value in zip(piece.partial_segments_m, piece.partials_cm):
        first = _shift(first, offset)
        last = _shift(last, offset)
        location = _dimension_location(first, last, dim_offset)
        commands.append(
            f'(sincal:partial-dim {_point(first)} {_point(last)} {_point(location)} '
            f'"{value}" "{piece.layer}" "{tag}" ss)'
        )
    min_y = min(point[1] + offset[1] for point in piece.vertices_m)
    min_x = min(point[0] + offset[0] for point in piece.vertices_m)
    label_point = (min_x, min_y - 0.42 - index * 0.20)
    description = (
        f"{piece.quantity} %%c{piece.diameter_mm} @{piece.spacing_cm:g} "
        f"L={piece.total_cm}"
    )
    commands.append(
        f'(sincal:detail-label {_point(label_point)} "{piece.mark}" '
        f'"{description}" "{piece.layer}" "{tag}" ss)'
    )
    return commands


def _group_definition(group, abutment_key):
    block_name = f"SINCAL_ZAP_{abutment_key.upper()}_{group.group_id}_{group.fingerprint.upper()}"
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


def _annotation_support(master_path):
    master = _lisp_string(master_path)
    return f'''(defun sincal:item (collection name / result)
  (setq result (vl-catch-all-apply 'vla-Item (list collection name)))
  (if (vl-catch-all-error-p result) nil result))
(defun sincal:mleader-dict (database)
  (sincal:item (vla-get-Dictionaries database) "ACAD_MLEADERSTYLE"))
(defun sincal:detail-ready (database / mldict)
  (and (sincal:item (vla-get-DimStyles database) "GSG_COTAS")
       (sincal:item (vla-get-DimStyles database) "GSG_ARM-COTAS")
       (setq mldict (sincal:mleader-dict database))
       (sincal:item mldict "GSG_MLEADER")
       (sincal:item (vla-get-TextStyles database) "RomanD")
       (sincal:item (vla-get-Blocks database) "MARK")))
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
(defun sincal:import-detail-styles (acad doc / dbx opened source-ml target-ml ok)
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
                    (setq ok nil))))
              (setq source-ml (sincal:mleader-dict dbx)
                    target-ml (sincal:mleader-dict doc))
              (if (and ok (not (sincal:item target-ml "GSG_MLEADER")))
                (if (or (not source-ml)
                        (not (sincal:copy-style dbx source-ml target-ml "GSG_MLEADER")))
                  (setq ok nil)))
              (if (and ok (not (sincal:item (vla-get-TextStyles doc) "RomanD")))
                (if (not (sincal:copy-style dbx (vla-get-TextStyles dbx)
                                             (vla-get-TextStyles doc) "RomanD"))
                  (setq ok nil)))
              (if (and ok (not (sincal:item (vla-get-Blocks doc) "MARK")))
                (if (not (sincal:copy-style dbx (vla-get-Blocks dbx)
                                             (vla-get-Blocks doc) "MARK"))
                  (setq ok nil)))))
          (vl-catch-all-apply 'vlax-release-object (list dbx))))))
  (and ok (sincal:detail-ready doc)))
(defun sincal:ensure-detail-styles (acad doc)
  (or (sincal:detail-ready doc) (sincal:import-detail-styles acad doc)))'''


def build_zapata_detail_lisp(schedule, rules, geometry, abutment_key, master_path):
    """Construye un comando de despiece general con actualización confirmable."""
    groups = build_detail_groups(schedule, rules, geometry)
    group_map = {group.group_id: group for group in groups}
    definitions = []
    desired = []
    for slot, group_id in enumerate(DETAIL_GROUP_ORDER):
        group = group_map.get(group_id)
        prefix = f"SINCAL_DETAIL|{abutment_key.upper()}|{group_id}|"
        if group:
            block_name, definition = _group_definition(group, abutment_key)
            definitions.append(definition)
            exact_tag = f"{prefix}{group.fingerprint}|{slot}"
            label = ", ".join(piece.mark for piece in group.pieces)
            desired.append((group_id, slot, prefix, exact_tag, block_name, label, group.pieces[0].layer))
        else:
            desired.append((group_id, slot, prefix, "", "", group_id, "0"))

    infer_base = []
    planning = []
    for group_id, slot, prefix, exact_tag, block_name, label, layer in desired:
        infer_base.append(
            f'(if (and (not base) (setq old (sincal:find-detail "{prefix}"))) '
            f'(progn (setq ip (cdr (assoc 10 (entget old)))) '
            f'(setq base (list (car ip) (+ (cadr ip) {_fmt(slot * DETAIL_SLOT_PITCH_M)}) 0.0))))'
        )
        planning.append(
            f'(setq plan (sincal:plan-detail "{prefix}" "{exact_tag}" "{block_name}" '
            f'"{label}" "{layer}" base {slot}))\n'
            f'    (if plan (setq plans (cons plan plans)))'
        )

    definitions_text = "\n  ".join(definitions)
    infer_text = "\n    ".join(infer_base)
    planning_text = "\n    ".join(planning)
    support = _annotation_support(master_path)
    return f'''(vl-load-com)
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
(defun sincal:set-mark (block value / attributes attribute)
  (if (= (vla-get-HasAttributes block) :vlax-true)
    (progn
      (setq attributes (vlax-invoke block 'GetAttributes))
      (foreach attribute attributes
        (if (= (strcase (vla-get-TagString attribute)) "MARCA")
          (vla-put-TextString attribute value))))))
(defun sincal:partial-dim (p1 p2 location text layer tag ss / obj ent)
  (setq obj (vla-AddDimAligned ms (vlax-3d-point p1) (vlax-3d-point p2)
                                (vlax-3d-point location)))
  (vla-put-StyleName obj "GSG_ARM-COTAS")
  (vla-put-TextOverride obj text)
  (vla-put-Layer obj layer)
  (setq ent (vlax-vla-object->ename obj))
  (sincal:detail-add ent ss tag))
(defun sincal:lap-dim (p1 p2 location layer tag ss / obj ent)
  (setq obj (vla-AddDimAligned ms (vlax-3d-point p1) (vlax-3d-point p2)
                                (vlax-3d-point location)))
  (vla-put-StyleName obj "GSG_COTAS")
  (vla-put-TextOverride obj "<>\\XALTERNADO")
  (vla-put-Layer obj layer)
  (setq ent (vlax-vla-object->ename obj))
  (sincal:detail-add ent ss tag))
(defun sincal:annotation-scale (/ value)
  (setq value (vl-catch-all-apply 'getvar (list "CANNOSCALEVALUE")))
  (if (or (vl-catch-all-error-p value) (not (numberp value)) (<= value 0.0))
    1.0
    (max 1.0 value)))
(defun sincal:detail-label (point mark description layer tag ss / block text text-point scale unit ent)
  (setq scale (sincal:annotation-scale) unit (* 0.0025 scale))
  (setq block (vla-InsertBlock ms (vlax-3d-point point) "MARK" 1.0 1.0 1.0 0.0))
  (vla-put-Layer block layer)
  (sincal:set-mark block mark)
  (setq ent (vlax-vla-object->ename block))
  (sincal:detail-add ent ss tag)
  (setq text-point (polar point 0.0 (* unit 1.8)))
  (setq text (vla-AddMText ms (vlax-3d-point text-point)
                           (* unit (+ 2.0 (* 0.70 (strlen description)))) description))
  (vla-put-StyleName text "RomanD")
  (vla-put-Height text 0.0025)
  (vla-put-AttachmentPoint text 4)
  (vla-put-Layer text layer)
  (setq ent (vlax-vla-object->ename text))
  (sincal:detail-add ent ss tag))
(defun sincal:plan-detail (prefix exact block-name label layer base slot / old oldtag action point)
  (setq old (sincal:find-detail prefix)
        oldtag (if old (sincal:xdata-value old) nil)
        point (if old (cdr (assoc 10 (entget old)))
                    (list (car base) (- (cadr base) (* slot {DETAIL_SLOT_PITCH_M})) 0.0)))
  (cond
    ((and old (= oldtag exact)) nil)
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
        ((= action "Cancelar") (setq sincal:abort T)))
      (if (= action "Actualizar") (list action old block-name exact layer point) nil))))
(defun sincal:apply-plan (plan / old block-name exact layer point obj)
  (setq old (nth 1 plan) block-name (nth 2 plan) exact (nth 3 plan)
        layer (nth 4 plan) point (nth 5 plan))
  (cond
    ((= block-name "") (if old (entdel old)))
    ((tblsearch "BLOCK" block-name)
      (if old (entdel old))
      (setq obj (vla-InsertBlock ms (vlax-3d-point point) block-name 1.0 1.0 1.0 0.0))
      (vla-put-Layer obj layer)
      (sincal:tag (vlax-vla-object->ename obj) exact))
    (T (alert (strcat "SINCAL no pudo construir el detalle " block-name
                      ". Se conservo la referencia anterior.")))))
(defun c:SINCAL-ZAPATA-DESPIECE (/ acad doc ms ss base old ip plans plan sincal:update-all sincal:abort)
  (setq acad (vlax-get-acad-object) doc (vla-get-ActiveDocument acad)
        ms (vla-get-ModelSpace doc) plans nil sincal:update-all nil sincal:abort nil)
  (if (not (sincal:ensure-detail-styles acad doc))
    (alert "SINCAL no pudo importar MARK, RomanD o los estilos de anotacion. No se modifico el despiece.")
    (progn
      {infer_text}
      (if (not base) (setq base (getpoint "\\nPunto superior izquierdo del despiece de zapata: ")))
      (if base
        (progn
          {planning_text}
          (if sincal:abort
            (princ "\\n[SINCAL] Actualizacion cancelada; no se reemplazo ningun detalle.")
            (progn
              {definitions_text}
              (if sincal:abort
                (princ "\\n[SINCAL] No se crearon bloques; se conservaron los detalles anteriores.")
                (progn
                  (foreach plan (reverse plans) (sincal:apply-plan plan))
                  (vla-Regen doc 1)
                  (princ "\\n[SINCAL] Despiece de zapata revisado y actualizado.")))))))))
  (princ))
'''
