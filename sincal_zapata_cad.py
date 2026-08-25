"""Generador CAD de vistas de zapata a partir de contornos confirmados."""
from __future__ import annotations

import math

from sincal_rebar_model import bend_radius_cm, distribution_positions_cm


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


def _block_command(point, diameter, tag):
    layer = f"fi{int(diameter)}"
    return (f'(progn (setq b (vla-InsertBlock ms (vlax-3d-point {_point(point)}) "{layer}" '
            f'0.001 0.001 0.001 0.0)) (vla-put-Layer b "{layer}") '
            f'(sincal:tag (vlax-vla-object->ename b) "{tag}"))')


def _rule_map(rules):
    return {rule.key: rule for rule in rules if rule.enabled}


def build_zapata_lisp(view, candidate, geometry, cover, rules, abutment_key):
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

    def inset(rule):
        return cover.lateral_m + rule.diameter_mm / 2000.0

    def horizontal_u(rule, y, upward):
        inner = inward_offset(points, inset(rule))
        a, b = _axis_intersections(inner, y, True)
        if a is None:
            raise ZapataCadError("No fue posible intersectar el moldaje en el nivel de la malla.")
        dy = hook_m if upward else -hook_m
        commands.append(_path_command(((a[0], a[1] + dy), a, b, (b[0], b[1] + dy)),
                                      f"fi{int(rule.diameter_mm)}", bend_radius_cm(rule.diameter_mm) / 100, tag))

    def vertical_u(rule, x, rightward):
        inner = inward_offset(points, inset(rule))
        a, b = _axis_intersections(inner, x, False)
        if a is None:
            raise ZapataCadError("No fue posible intersectar el moldaje en el nivel de la malla.")
        dx = hook_m if rightward else -hook_m
        commands.append(_path_command(((a[0] + dx, a[1]), a, b, (b[0] + dx, b[1])),
                                      f"fi{int(rule.diameter_mm)}", bend_radius_cm(rule.diameter_mm) / 100, tag))

    def horizontal_chords(rule):
        inner = inward_offset(points, inset(rule))
        lo, hi = min(p[1] for p in inner), max(p[1] for p in inner)
        positions = distribution_positions_cm((hi - lo) * 100, rule.spacing_cm, rule.origin)
        for value in positions:
            a, b = _axis_intersections(inner, lo + value / 100, True)
            if a is not None:
                commands.append(_path_command((a, b), f"fi{int(rule.diameter_mm)}", 0, tag))

    def vertical_chords(rule, offset=0.0):
        inner = inward_offset(points, inset(rule))
        lo, hi = min(p[0] for p in inner), max(p[0] for p in inner)
        positions = distribution_positions_cm((hi - lo) * 100, rule.spacing_cm, rule.origin)
        for value in positions:
            x = min(hi, lo + value / 100 + offset)
            a, b = _axis_intersections(inner, x, False)
            if a is not None:
                commands.append(_path_command((a, b), f"fi{int(rule.diameter_mm)}", 0, tag))

    def row_blocks(rule, y, start, end):
        positions = distribution_positions_cm((end - start) * 100, rule.spacing_cm, rule.origin)
        commands.extend(_block_command((start + value / 100, y), rule.diameter_mm, tag) for value in positions)

    top_y = maxy - cover.superior_m - mx.diameter_mm / 2000
    bottom_y = miny + cover.inferior_m + mx.diameter_mm / 2000
    left_x = minx + cover.lateral_m + my.diameter_mm / 2000
    right_x = maxx - cover.lateral_m - my.diameter_mm / 2000

    if view == "FR":
        horizontal_u(mx, top_y, False)
        horizontal_u(mx, bottom_y, True)
        row_blocks(my, top_y - my.diameter_mm / 2000, left_x, right_x)
        row_blocks(my, bottom_y + my.diameter_mm / 2000, left_x, right_x)
    elif view in ("AA", "BB", "CC"):
        horizontal_u(my, top_y - mx.diameter_mm / 1000, False)
        horizontal_u(my, bottom_y + mx.diameter_mm / 1000, True)
        row_blocks(mx, top_y, left_x, right_x)
        row_blocks(mx, bottom_y, left_x, right_x)

    if view in ("FR", "AA", "BB", "CC") and "suple" in active:
        suple = active["suple"]
        if view == "FR":
            row_blocks(suple, top_y - suple.diameter_mm / 2000,
                       left_x + (my.diameter_mm + suple.diameter_mm) / 2000, right_x)
        else:
            horizontal_u(suple, top_y - (mx.diameter_mm + suple.diameter_mm) / 1000, False)

    if view in ("FR", "AA", "BB", "CC") and "lateral_x" in active:
        lx = active["lateral_x"]
        levels = distribution_positions_cm((top_y - bottom_y) * 100, lx.spacing_cm, lx.origin)
        for value in levels:
            y = bottom_y + value / 100
            if view == "FR":
                inner = inward_offset(points, inset(lx))
                a, b = _axis_intersections(inner, y, True)
                if a is not None:
                    commands.append(_path_command((a, b), f"fi{int(lx.diameter_mm)}", 0, tag))
            else:
                commands.append(_block_command((left_x, y), lx.diameter_mm, tag))
                commands.append(_block_command((right_x, y), lx.diameter_mm, tag))

    if view in ("FR", "BB", "CC") and "lateral_y" in active:
        ly = active["lateral_y"]
        levels = distribution_positions_cm((top_y - bottom_y) * 100, ly.spacing_cm, ly.origin)
        for value in levels:
            y = bottom_y + value / 100
            if view == "FR":
                commands.append(_block_command((left_x, y), ly.diameter_mm, tag))
                commands.append(_block_command((right_x, y), ly.diameter_mm, tag))
            else:
                inner = inward_offset(points, inset(ly))
                a, b = _axis_intersections(inner, y, True)
                if a is not None:
                    commands.append(_path_command((a, b), f"fi{int(ly.diameter_mm)}", 0, tag))

    if view == "EE":
        horizontal_chords(mx)
        vertical_chords(my)
        if "suple" in active:
            suple = active["suple"]
            vertical_chords(suple, (my.diameter_mm + suple.diameter_mm) / 2000)
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

    layers = "\n".join(f'(sincal:layer "fi{diameter}")' for diameter in diameters)
    blocks = sorted({int(rule.diameter_mm) for rule in active.values() if (
        (view == "FR" and rule.key in ("mesh_y", "suple", "lateral_y")) or
        (view in ("AA", "BB", "CC") and rule.key in ("mesh_x", "lateral_x"))
    )})
    checks = " ".join(f'(tblsearch "BLOCK" "fi{diameter}")' for diameter in blocks) or "T"
    body = "\n  ".join(commands)
    return f'''(vl-load-com)
(defun sincal:layer (name) (if (not (tblsearch "LAYER" name)) (command "_.-LAYER" "_M" name "_C" "5" name "_LT" "Continuous" name "")))
(defun sincal:tag (ent value / data) (regapp "SINCAL_REBAR") (setq data (entget ent)) (entmod (append data (list (list -3 (list "SINCAL_REBAR" (cons 1000 value)))))) ent)
(defun sincal:delete-old (value / ss i ent xd) (if (setq ss (ssget "_X" '((-3 ("SINCAL_REBAR"))))) (progn (setq i 0) (repeat (sslength ss) (setq ent (ssname ss i) xd (assoc -3 (entget ent '("SINCAL_REBAR")))) (if (and xd (vl-string-search value (vl-princ-to-string xd))) (entdel ent)) (setq i (1+ i))))))
(defun c:SINCAL-ZAPATA-GENERAR (/ acad doc ms e b) (setq acad (vlax-get-acad-object) doc (vla-get-ActiveDocument acad) ms (vla-get-ModelSpace doc))
  {layers}
  (if (not (and {checks})) (progn (if (fboundp 'c:SINCAL) (c:SINCAL)) ))
  (if (and {checks}) (progn (sincal:delete-old "{tag}")
  {body}
  (vla-Regen doc 1) (princ "\\n[SINCAL] Vista {view} generada. Moldaje preservado."))
  (princ "\\n[SINCAL] Faltan bloques fiXX. Ejecute SINCAL para importar el master.")) (princ))
'''
