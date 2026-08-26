"""Generador CAD de vistas de zapata a partir de contornos confirmados."""
from __future__ import annotations

import math

from sincal.rebar.model import (
    LARGO_COMERCIAL_CM,
    automatic_hook_cm,
    bend_radius_cm,
    build_zapata_schedule,
    distribution_positions_cm,
    lap_length_cm,
)


EE_LAP_GRAPHIC_OFFSET_M = 0.005
ANNOTATION_OFFSET_M = 0.25
LEADER_DOGLEG_M = 0.45


class ZapataCadError(ValueError):
    pass


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def _area(points):
    return sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points))) / 2


def _simplify(points):
    points = list(points)
    changed = True
    while changed and len(points) > 3:
        changed = False
        for i in range(len(points)):
            if abs(_cross(points[i - 1], points[i], points[(i + 1) % len(points)])) < 1e-9:
                points.pop(i)
                changed = True
                break
    return tuple(points)


def _line_intersection(a, b, c, d):
    ab = (b[0] - a[0], b[1] - a[1])
    cd = (d[0] - c[0], d[1] - c[1])
    den = ab[0] * cd[1] - ab[1] * cd[0]
    if abs(den) < 1e-12:
        raise ZapataCadError("El moldaje contiene lados paralelos degenerados.")
    t = ((c[0] - a[0]) * cd[1] - (c[1] - a[1]) * cd[0]) / den
    return a[0] + t * ab[0], a[1] + t * ab[1]


def inward_offset(points, distance):
    """Offset convexo independiente de la cantidad de vértices."""
    points = _simplify(points)
    if len(points) < 3:
        raise ZapataCadError("El moldaje no contiene suficientes vértices útiles.")
    orientation = 1 if _area(points) > 0 else -1
    signs = []
    for i in range(len(points)):
        turn = _cross(points[i - 1], points[i], points[(i + 1) % len(points)])
        if abs(turn) > 1e-9:
            signs.append(1 if turn > 0 else -1)
    if signs and any(sign != signs[0] for sign in signs):
        raise ZapataCadError("La primera etapa admite moldajes convexos; el contorno confirmado es cóncavo.")
    shifted = []
    for i, start in enumerate(points):
        end = points[(i + 1) % len(points)]
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length < 1e-12:
            raise ZapataCadError("El moldaje contiene vértices coincidentes.")
        normal = (-dy / length * orientation, dx / length * orientation)
        shifted.append(((start[0] + normal[0] * distance, start[1] + normal[1] * distance),
                        (end[0] + normal[0] * distance, end[1] + normal[1] * distance)))
    result = []
    for i in range(len(shifted)):
        result.append(_line_intersection(*shifted[i - 1], *shifted[i]))
    return tuple(result)


def _axis_intersections(points, coordinate, horizontal):
    values = []
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        av, bv = (a[1], b[1]) if horizontal else (a[0], b[0])
        if coordinate < min(av, bv) - 1e-9 or coordinate > max(av, bv) + 1e-9 or abs(av - bv) < 1e-12:
            continue
        t = (coordinate - av) / (bv - av)
        if -1e-9 <= t <= 1 + 1e-9:
            point = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            if not any(math.dist(point, old) < 1e-8 for old in values):
                values.append(point)
    values.sort(key=lambda p: p[0] if horizontal else p[1])
    if len(values) < 2:
        return None, None
    return values[0], values[-1]


def _fmt(value):
    return f"{value:.9f}".rstrip("0").rstrip(".")


def _point(point):
    return f"(list {_fmt(point[0])} {_fmt(point[1])} 0.0)"


def _unit(a, b):
    length = math.dist(a, b)
    return ((b[0] - a[0]) / length, (b[1] - a[1]) / length)


def _at(point, vector, distance):
    return point[0] + vector[0] * distance, point[1] + vector[1] * distance


def _path_command(points, layer, radius, tag):
    args = " ".join(f'"_NON" {_point(point)}' for point in points)
    fillet = f'(command "_.FILLET" "_R" {_fmt(radius)} "_.FILLET" "_P" e)' if len(points) > 2 and radius > 0 else ""
    return f'(progn (setvar "CLAYER" "{layer}") (command "_.PLINE" {args} "") (setq e (entlast)) {fillet} (sincal:tag e "{tag}"))'


def _circle_command(point, diameter, tag):
    layer = f"fi{int(diameter)}"
    radius_m = diameter / 2000.0
    return (f'(progn (setq e (entmakex (list (cons 0 "CIRCLE") (cons 8 "{layer}") '
            f'(cons 10 {_point(point)}) (cons 40 {_fmt(radius_m)})))) '
            f'(sincal:tag e "{tag}"))')


def _dimension_command(first, last, text_point, entries, layer, tag):
    lisp_entries = " ".join(
        f'(list "{mark}" "{description}{" +" if index < len(entries) - 1 else ""}")'
        for index, (mark, description) in enumerate(entries)
    )
    return (
        f'(sincal:marked-dim {_point(first)} {_point(last)} {_point(text_point)} '
        f'(list {lisp_entries}) "{layer}" "{tag}")'
    )


def _mleader_command(anchor, landing, text, layer, tag):
    return (
        f'(sincal:mleader {_point(anchor)} {_point(landing)} '
        f'"{text}" "{layer}" "{tag}")'
    )


def _rule_map(rules):
    return {rule.key: rule for rule in rules if rule.enabled}


def build_zapata_lisp(view, candidate, geometry, cover, rules, abutment_key, master_path=""):
    """Crea un AutoLISP autocontenido; no modifica el moldaje confirmado."""
    if view == "DD":
        raise ZapataCadError("DD corresponde a muros y alas; no genera armadura de zapata.")
    if len(candidate.vertices) < 3:
        raise ZapataCadError("Vuelve a detectar el moldaje para obtener sus vértices topológicos.")
    active = _rule_map(rules)
    if "mesh_x" not in active or "mesh_y" not in active:
        raise ZapataCadError("Las mallas 1–2 y 3 deben estar activas.")
    points = _simplify(candidate.vertices)
    minx, maxx = min(p[0] for p in points), max(p[0] for p in points)
    miny, maxy = min(p[1] for p in points), max(p[1] for p in points)
    mx, my = active["mesh_x"], active["mesh_y"]
    hook_m = max(1.0, math.ceil((geometry.alto_m * 50.0) / 10.0) / 10.0)
    tag = f"{abutment_key.upper()}_{view}_ZAP"
    commands = []
    diameters = sorted({int(rule.diameter_mm) for rule in active.values()})
    schedule = build_zapata_schedule(geometry, cover, rules)
    if not schedule.is_valid:
        detail = "; ".join(issue.message for issue in schedule.issues if issue.severity == "error")
        raise ZapataCadError(detail or "La armadura no superó la validación.")
    marks_by_key = {}
    for mark in schedule.marks:
        marks_by_key.setdefault(mark.key, []).append(mark)

    def mark_labels(rule):
        """Una llamada por marca/pieza; nunca combina dos marcas en un MLeader."""
        return tuple(mark.mark for mark in marks_by_key.get(rule.key, ()))

    def distribution_entries(rule, visible_count):
        """Bloque MARK y descripción por cada marca de la distribución visible."""
        entries = []
        group_marks = marks_by_key.get(rule.key, ())
        base_quantity = group_marks[0].quantity if group_marks else 1
        for mark in group_marks:
            piece_factor = mark.quantity / base_quantity
            quantity = max(1, round(visible_count * piece_factor))
            entries.append((
                mark.mark,
                f"{quantity}%%c{int(mark.diameter_mm)} @{rule.spacing_cm:g}",
            ))
        return tuple(entries)

    def group_leaders(rule, start, end, side, lane=0):
        labels = mark_labels(rule)
        if not labels:
            return
        vector = _unit(start, end)
        outward = {
            "top": (0.0, 1.0), "bottom": (0.0, -1.0),
            "left": (-1.0, 0.0), "right": (1.0, 0.0),
        }[side]
        midpoint = _at(start, vector, math.dist(start, end) / 2.0)
        for index, label in enumerate(labels):
            along = (index - (len(labels) - 1) / 2.0) * 0.45
            anchor = _at(midpoint, vector, along)
            landing = _at(anchor, outward, LEADER_DOGLEG_M + lane * 0.18)
            landing = _at(landing, vector, 0.30 if index % 2 == 0 else -0.30)
            commands.append(_mleader_command(
                anchor, landing, f"({label})", f"fi{int(rule.diameter_mm)}", tag))

    def inset(rule):
        return cover.lateral_m + rule.diameter_mm / 2000.0

    def horizontal_u(rule, y, upward, annotation_side, lane=0):
        inner = inward_offset(points, inset(rule))
        a, b = _axis_intersections(inner, y, True)
        if a is None:
            raise ZapataCadError("No fue posible intersectar el moldaje en el nivel de la malla.")
        dy = hook_m if upward else -hook_m
        commands.append(_path_command(((a[0], a[1] + dy), a, b, (b[0], b[1] + dy)),
                                      f"fi{int(rule.diameter_mm)}", bend_radius_cm(rule.diameter_mm) / 100, tag))
        group_leaders(rule, a, b, annotation_side, lane)

    def vertical_u(rule, x, rightward, annotation_side, lane=0):
        inner = inward_offset(points, inset(rule))
        a, b = _axis_intersections(inner, x, False)
        if a is None:
            raise ZapataCadError("No fue posible intersectar el moldaje en el nivel de la malla.")
        dx = hook_m if rightward else -hook_m
        commands.append(_path_command(((a[0] + dx, a[1]), a, b, (b[0] + dx, b[1])),
                                      f"fi{int(rule.diameter_mm)}", bend_radius_cm(rule.diameter_mm) / 100, tag))
        group_leaders(rule, a, b, annotation_side, lane)

    def horizontal_chords(rule):
        inner = inward_offset(points, inset(rule))
        lo, hi = min(p[1] for p in inner), max(p[1] for p in inner)
        positions = distribution_positions_cm((hi - lo) * 100, rule.spacing_cm, rule.origin)
        representative = None
        for value in positions:
            a, b = _axis_intersections(inner, lo + value / 100, True)
            if a is not None:
                commands.append(_path_command((a, b), f"fi{int(rule.diameter_mm)}", 0, tag))
                if representative is None or abs(value - positions[len(positions) // 2]) < 1e-9:
                    representative = (a, b)
        if representative:
            group_leaders(rule, representative[0], representative[1], "bottom")

    def vertical_chords(rule, offset=0.0, lane=0):
        inner = inward_offset(points, inset(rule))
        lo, hi = min(p[0] for p in inner), max(p[0] for p in inner)
        positions = distribution_positions_cm((hi - lo) * 100, rule.spacing_cm, rule.origin)
        representative = None
        middle = positions[len(positions) // 2] if positions else None
        for value in positions:
            x = min(hi, lo + value / 100 + offset)
            a, b = _axis_intersections(inner, x, False)
            if a is not None:
                commands.append(_path_command((a, b), f"fi{int(rule.diameter_mm)}", 0, tag))
                if representative is None or value == middle:
                    representative = (a, b)
        if representative:
            group_leaders(rule, representative[0], representative[1], "right", lane)

    def row_blocks(rule, y, start, end, dimension_side, lane=0):
        positions = distribution_positions_cm((end - start) * 100, rule.spacing_cm, rule.origin)
        centres = tuple((start + value / 100, y) for value in positions)
        commands.extend(_circle_command(point, rule.diameter_mm, tag) for point in centres)
        entries = distribution_entries(rule, len(centres))
        layer = f"fi{int(rule.diameter_mm)}"
        if len(centres) >= 2:
            dim_y = (maxy + ANNOTATION_OFFSET_M + lane * 0.20
                     if dimension_side == "top"
                     else miny - ANNOTATION_OFFSET_M - lane * 0.20)
            commands.append(_dimension_command(
                centres[0], centres[-1], ((centres[0][0] + centres[-1][0]) / 2.0, dim_y),
                entries, layer, tag,
            ))
        elif centres:
            outward = 1 if dimension_side == "top" else -1
            landing = (centres[0][0] + LEADER_DOGLEG_M,
                       centres[0][1] + outward * (ANNOTATION_OFFSET_M + lane * 0.20))
            text = " + ".join(f"({mark}) {description}" for mark, description in entries)
            commands.append(_mleader_command(centres[0], landing, text, layer, tag))

    def column_blocks(rule, x, levels, dimension_side, lane=0):
        centres = tuple((x, bottom_y + value / 100) for value in levels)
        commands.extend(_circle_command(point, rule.diameter_mm, tag) for point in centres)
        entries = distribution_entries(rule, len(centres))
        layer = f"fi{int(rule.diameter_mm)}"
        if len(centres) >= 2:
            dim_x = (minx - ANNOTATION_OFFSET_M - lane * 0.20
                     if dimension_side == "left"
                     else maxx + ANNOTATION_OFFSET_M + lane * 0.20)
            commands.append(_dimension_command(
                centres[0], centres[-1], (dim_x, (centres[0][1] + centres[-1][1]) / 2.0),
                entries, layer, tag,
            ))
        elif centres:
            outward = -1 if dimension_side == "left" else 1
            landing = (centres[0][0] + outward * (ANNOTATION_OFFSET_M + lane * 0.20),
                       centres[0][1] + LEADER_DOGLEG_M)
            text = " + ".join(f"({mark}) {description}" for mark, description in entries)
            commands.append(_mleader_command(centres[0], landing, text, layer, tag))

    def ee_mesh_x_pair(rule):
        """Una representación 1–2; la barra corta se desplaza 5 mm hacia Y-."""
        inner = inward_offset(points, inset(rule))
        y = (min(p[1] for p in inner) + max(p[1] for p in inner)) / 2.0
        a, b = _axis_intersections(inner, y, True)
        if a is None:
            raise ZapataCadError("No fue posible ubicar el par 1–2 en EE.")
        radius_m = bend_radius_cm(rule.diameter_mm) / 100.0
        left = (a[0] + radius_m, y)
        right = (b[0] - radius_m, y)
        straight_cm = max(0.0, (right[0] - left[0]) * 100.0)
        hook_cm = rule.hook_cm or automatic_hook_cm(geometry.alto_m * 100.0)
        arc_cm = math.pi * bend_radius_cm(rule.diameter_mm) / 2.0
        developed_cm = straight_cm + 2.0 * (hook_cm + arc_cm)
        layer = f"fi{int(rule.diameter_mm)}"
        if developed_cm <= LARGO_COMERCIAL_CM:
            commands.append(_path_command((left, right), layer, 0, tag))
            group_leaders(rule, left, right, "bottom")
            return
        first_straight_m = (LARGO_COMERCIAL_CM - hook_cm - arc_cm) / 100.0
        lap_cm = lap_length_cm(rule.diameter_mm)
        terminal_cm = developed_cm - LARGO_COMERCIAL_CM + lap_cm
        second_straight_m = (terminal_cm - hook_cm - arc_cm) / 100.0
        first_end = (min(right[0], left[0] + first_straight_m), y)
        short_y = y - EE_LAP_GRAPHIC_OFFSET_M
        second_start = (max(left[0], right[0] - second_straight_m), short_y)
        second_end = (right[0], short_y)
        commands.append(_path_command((left, first_end), layer, 0, tag))
        commands.append(_path_command((second_start, second_end), layer, 0, tag))
        labels = mark_labels(rule)
        if labels:
            group_leaders_for_segments = (
                (labels[0], left, first_end, 0),
                (labels[-1], second_start, second_end, 1),
            )
            for label, segment_start, segment_end, lane in group_leaders_for_segments:
                vector = _unit(segment_start, segment_end)
                anchor = _at(segment_start, vector, math.dist(segment_start, segment_end) * 0.55)
                landing = (anchor[0] + LEADER_DOGLEG_M, anchor[1] - ANNOTATION_OFFSET_M - lane * 0.18)
                commands.append(_mleader_command(anchor, landing, f"({label})", layer, tag))

    top_y = maxy - cover.superior_m - mx.diameter_mm / 2000
    bottom_y = miny + cover.inferior_m + mx.diameter_mm / 2000
    left_x = minx + cover.lateral_m + my.diameter_mm / 2000
    right_x = maxx - cover.lateral_m - my.diameter_mm / 2000

    if view == "FR":
        horizontal_u(mx, top_y, False, "top")
        horizontal_u(mx, bottom_y, True, "bottom")
        row_blocks(my, top_y - my.diameter_mm / 2000, left_x, right_x, "top")
        row_blocks(my, bottom_y + my.diameter_mm / 2000, left_x, right_x, "bottom")
    elif view in ("AA", "BB", "CC"):
        horizontal_u(my, top_y - mx.diameter_mm / 1000, False, "top")
        horizontal_u(my, bottom_y + mx.diameter_mm / 1000, True, "bottom")
        row_blocks(mx, top_y, left_x, right_x, "top")
        row_blocks(mx, bottom_y, left_x, right_x, "bottom")

    if view in ("FR", "AA", "BB", "CC") and "suple" in active:
        suple = active["suple"]
        if view == "FR":
            row_blocks(suple, top_y - suple.diameter_mm / 2000,
                       left_x + (my.diameter_mm + suple.diameter_mm) / 2000, right_x,
                       "top", 1)
        else:
            horizontal_u(
                suple, top_y - (mx.diameter_mm + suple.diameter_mm) / 1000,
                False, "top", 1)

    if view in ("AA", "BB", "CC") and "lateral_x" in active:
        lx = active["lateral_x"]
        levels = distribution_positions_cm((top_y - bottom_y) * 100, lx.spacing_cm, lx.origin)
        column_blocks(lx, left_x, levels, "left")
        column_blocks(lx, right_x, levels, "right")

    if view == "FR" and "lateral_y" in active:
        ly = active["lateral_y"]
        levels = distribution_positions_cm((top_y - bottom_y) * 100, ly.spacing_cm, ly.origin)
        column_blocks(ly, left_x, levels, "left")
        column_blocks(ly, right_x, levels, "right")

    if view == "EE":
        ee_mesh_x_pair(mx)
        vertical_chords(my)
        if "suple" in active:
            suple = active["suple"]
            vertical_chords(suple, (my.diameter_mm + suple.diameter_mm) / 2000, 1)
        for key in ("lateral_x", "lateral_y"):
            if key not in active:
                continue
            rule = active[key]
            inner = inward_offset(points, inset(rule))
            for i, a in enumerate(inner):
                b = inner[(i + 1) % len(inner)]
                is_x = abs(b[0] - a[0]) >= abs(b[1] - a[1])
                if (key == "lateral_x") != is_x:
                    continue
                prev, nxt = inner[i - 1], inner[(i + 2) % len(inner)]
                p0 = _at(a, _unit(a, prev), min(hook_m, math.dist(a, prev) * 0.8))
                p3 = _at(b, _unit(b, nxt), min(hook_m, math.dist(b, nxt) * 0.8))
                commands.append(_path_command((p0, a, b, p3), f"fi{int(rule.diameter_mm)}",
                                              bend_radius_cm(rule.diameter_mm) / 100, tag))
                side = "top" if (a[1] + b[1]) / 2.0 >= (miny + maxy) / 2.0 else "bottom"
                group_leaders(rule, a, b, side)

    layers = "\n    ".join(f'(sincal:layer "fi{diameter}")' for diameter in diameters)
    body = "\n    ".join(commands)
    master_lisp = master_path.replace("\\", "\\\\").replace('"', '\\"')
    return f'''(vl-load-com)
(defun sincal:layer (name) (if (not (tblsearch "LAYER" name)) (command "_.-LAYER" "_M" name "_C" "5" name "_LT" "Continuous" name "")))
(defun sincal:tag (ent value / data) (regapp "SINCAL_REBAR") (setq data (entget ent)) (entmod (append data (list (list -3 (list "SINCAL_REBAR" (cons 1000 value)))))) ent)
(defun sincal:delete-old (value / ss i ent xd) (if (setq ss (ssget "_X" '((-3 ("SINCAL_REBAR"))))) (progn (setq i 0) (repeat (sslength ss) (setq ent (ssname ss i) xd (assoc -3 (entget ent '("SINCAL_REBAR")))) (if (and xd (vl-string-search value (vl-princ-to-string xd))) (entdel ent)) (setq i (1+ i))))))
(defun sincal:item (collection name / result)
  (setq result (vl-catch-all-apply 'vla-Item (list collection name)))
  (if (vl-catch-all-error-p result) nil result))
(defun sincal:mleader-dict (database)
  (sincal:item (vla-get-Dictionaries database) "ACAD_MLEADERSTYLE"))
(defun sincal:styles-ready (database / mldict)
  (and (sincal:item (vla-get-DimStyles database) "GSG_COTAS")
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
(defun sincal:import-annotation-styles (acad doc master / dbx opened source-ml target-ml ok)
  (setq ok T)
  (if (or (= master "") (not (findfile master)))
    (setq ok nil)
    (progn
      (setq dbx (sincal:get-dbx acad))
      (if (not dbx)
        (setq ok nil)
        (progn
          (setq opened (vl-catch-all-apply 'vla-Open (list dbx master)))
          (if (vl-catch-all-error-p opened)
            (setq ok nil)
            (progn
              (if (not (sincal:item (vla-get-DimStyles doc) "GSG_COTAS"))
                (if (not (sincal:copy-style dbx (vla-get-DimStyles dbx)
                                             (vla-get-DimStyles doc) "GSG_COTAS"))
                  (setq ok nil)))
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
  (and ok (sincal:styles-ready doc)))
(defun sincal:ensure-annotation-styles (acad doc master)
  (or (sincal:styles-ready doc)
      (sincal:import-annotation-styles acad doc master)))
(defun sincal:set-mark (block value / attributes attribute)
  (if (= (vla-get-HasAttributes block) :vlax-true)
    (progn
      (setq attributes (vlax-invoke block 'GetAttributes))
      (foreach attribute attributes
        (if (= (strcase (vla-get-TagString attribute)) "MARCA")
          (vla-put-TextString attribute value))))))
(defun sincal:add-mark (point value layer rotation tag / block)
  (setq block (vla-InsertBlock ms (vlax-3d-point point) "MARK" 1.0 1.0 1.0 rotation))
  (vla-put-Layer block layer)
  (sincal:set-mark block value)
  (sincal:tag (vlax-vla-object->ename block) tag)
  block)
(defun sincal:add-mtext (point text layer rotation width tag / obj)
  (setq obj (vla-AddMText ms (vlax-3d-point point) width text))
  (vla-put-StyleName obj "RomanD")
  (vla-put-Height obj 0.0025)
  (vla-put-Rotation obj rotation)
  (vla-put-AttachmentPoint obj 4)
  (vl-catch-all-apply 'vla-put-BackgroundFill (list obj :vlax-true))
  (vla-put-Layer obj layer)
  (sincal:tag (vlax-vla-object->ename obj) tag)
  obj)
(defun sincal:annotation-scale (/ value)
  (setq value (vl-catch-all-apply 'getvar (list "CANNOSCALEVALUE")))
  (if (or (vl-catch-all-error-p value) (not (numberp value)) (<= value 0.0))
    1.0
    (max 1.0 value)))
(defun sincal:marked-dim (p1 p2 location entries layer tag / obj angle scale unit total cursor item mark description width mark-point text-point)
  (setq obj (vla-AddDimAligned ms (vlax-3d-point p1) (vlax-3d-point p2)
                                (vlax-3d-point location)))
  (vla-put-StyleName obj "GSG_COTAS")
  (vla-put-TextOverride obj " ")
  (vla-put-Layer obj layer)
  (sincal:tag (vlax-vla-object->ename obj) tag)
  (setq angle (angle p1 p2)
        scale (sincal:annotation-scale)
        unit (* 0.0025 scale)
        total 0.0)
  (foreach item entries
    (setq total (+ total (* unit (+ 2.2 (* 0.62 (strlen (cadr item))) 1.1)))))
  (setq cursor (polar location (+ angle pi) (/ total 2.0)))
  (foreach item entries
    (setq mark (car item) description (cadr item)
          mark-point cursor
          text-point (polar cursor angle (* unit 1.8))
          width (* unit (+ 1.0 (* 0.70 (strlen description)))))
    (sincal:add-mark mark-point mark layer angle tag)
    (sincal:add-mtext text-point description layer angle width tag)
    (setq cursor (polar cursor angle (+ (* unit 2.2) width (* unit 1.1)))))
  obj)
(defun sincal:mleader (arrow landing text layer tag / points obj)
  (setq points (vlax-make-safearray vlax-vbDouble '(0 . 5)))
  (vlax-safearray-fill points
    (list (car arrow) (cadr arrow) 0.0 (car landing) (cadr landing) 0.0))
  (setq obj (vla-AddMLeader ms points 0))
  (vla-put-StyleName obj "GSG_MLEADER")
  (vla-put-TextString obj text)
  (vla-put-Layer obj layer)
  (sincal:tag (vlax-vla-object->ename obj) tag))
(defun c:SINCAL-ZAPATA-GENERAR (/ acad doc ms e b)
  (setq acad (vlax-get-acad-object) doc (vla-get-ActiveDocument acad) ms (vla-get-ModelSpace doc))
  (if (sincal:ensure-annotation-styles acad doc "{master_lisp}")
    (progn
    {layers}
    (sincal:delete-old "{tag}")
    {body}
    (vla-Regen doc 1)
    (princ "\\n[SINCAL] Vista {view} generada con cotas y llamadas. Moldaje preservado."))
    (alert (strcat "SINCAL no pudo importar GSG_COTAS, GSG_MLEADER, RomanD y MARK.\\n"
                   "Verifique el master DWG y vuelva a generar; no se modifico la vista.")))
  (princ))
'''
