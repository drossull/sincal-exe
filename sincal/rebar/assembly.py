"""One geometric source for the footing schedule, details, CAD and viewer.

Coordinates are in the local CAD frame, in metres. Each bar is one physical
piece; lapped pieces touch side by side. Cut labels are rounded up to centimetres,
but that rounding never stretches the geometry beyond the concrete cover.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from types import SimpleNamespace

from .model import (RebarMark, RebarLengthVariant, ZapataSchedule, ValidationIssue,
                    automatic_hook_cm, bend_radius_cm, lap_length_cm,
                    distribution_positions_cm, parse_removed_pieces, _VIEW_NOTES)
from .plan import footing_mesh_axes, mesh_y_parallel_to_skew
from .splices import physical_laps


@dataclass(frozen=True)
class FootingBar:
    id: str
    key: str
    mark: str
    label: str
    diameter_mm: float
    level: str
    piece_role: str
    placement_id: str
    coordinate_m: float
    origin_m: tuple
    axis_u: tuple
    axis_v: tuple
    vertices_m: tuple
    bulges: tuple
    points_m: tuple
    main_start_m: tuple
    main_end_m: tuple
    length_cm: float
    developed_length_cm: float
    bend_radius_cm: float
    lap_length_cm: float
    lap_segments_m: tuple = ()

    @property
    def signature(self):
        """Stable physical identity; changing a mark never revives removed steel.

        Positions and bend-plane axes are included so an index reused after a
        distribution edit cannot accidentally remove a different piece. The
        numerical normalization only removes sub-picometre arithmetic noise.
        """
        def numbers(values):
            return tuple(0.0 if abs(value) < 1e-12 else round(float(value), 12)
                         for value in values)

        physical = {
            "version": 1, "key": self.key, "level": self.level,
            "role": self.piece_role, "diameter_mm": float(self.diameter_mm),
            "vertices_m": tuple(numbers(point) for point in self.vertices_m),
            "bulges": numbers(self.bulges),
            "axis_u": numbers(self.axis_u), "axis_v": numbers(self.axis_v),
        }
        payload = json.dumps(physical, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FootingAssembly:
    bars: tuple
    schedule: ZapataSchedule
    skew_degrees: float = 0.0
    reference_bars: tuple = ()

    @property
    def is_valid(self):
        return self.schedule.is_valid


def _length(a, b, bulge):
    chord = math.dist(a, b)
    if abs(bulge) < 1e-12:
        return chord
    angle = 4 * math.atan(abs(bulge))
    return chord * angle / (2 * math.sin(angle / 2))


def _slice(vertices, bulges, start, end):
    """Cut only on straight portions, retaining the exact original arcs."""
    out, bends, distance = [], [], 0.0
    for a, b, bulge in zip(vertices, vertices[1:], bulges):
        length = _length(a, b, bulge)
        lo, hi = max(start, distance), min(end, distance + length)
        if hi > lo + 1e-10:
            if abs(bulge) > 1e-12:
                if lo > distance + 1e-8 or hi < distance + length - 1e-8:
                    raise ValueError("El empalme invade un doblez; revisa el largo y los ganchos.")
                p, q = a, b
            else:
                p = tuple(x + (y - x) * (lo - distance) / length for x, y in zip(a, b))
                q = tuple(x + (y - x) * (hi - distance) / length for x, y in zip(a, b))
            if not out:
                out.append(p)
            bends.append(bulge)
            out.append(q)
        distance += length
    return tuple(out), tuple(bends + [0.0])


def _raw_vertices(vertices, bulges):
    """Recover theoretical corners for dimensions, without changing the arcs."""
    raw = [vertices[0]]
    for i, bulge in enumerate(bulges[:-1]):
        if abs(bulge) < 1e-12:
            if i + 1 == len(vertices) - 1:
                raw.append(vertices[i + 1])
            continue
        a, b = vertices[i:i + 2]
        sweep = 4 * math.atan(bulge)
        chord = math.dist(a, b)
        radius = chord / (2 * math.sin(abs(sweep) / 2))
        heading = math.atan2(b[1] - a[1], b[0] - a[0]) - sweep / 2
        tangent = radius * math.tan(abs(sweep) / 2)
        raw.append((a[0] + tangent * math.cos(heading), a[1] + tangent * math.sin(heading)))
    if raw[-1] != vertices[-1]:
        raw.append(vertices[-1])
    return tuple(raw)


def build_footing_assembly(geometry, cover, rules):
    # Imports are lazy: detail supports legacy stand-alone pieces as well.
    from .detail import _fillet_polyline, polyline_render_points

    rules = tuple(rules)
    issues = list(geometry.validate()) + list(cover.validate(geometry))
    for rule in rules:
        issues.extend(rule.validate())
    active = {rule.key: rule for rule in rules if rule.enabled}
    if any(i.severity == "error" for i in issues):
        return FootingAssembly((), ZapataSchedule((), tuple(issues)))
    angle = math.radians(geometry.esviaje_grados)
    slope, sec = math.tan(angle), 1 / math.cos(angle)
    variable_y = abs(angle) > 1e-9 and not mesh_y_parallel_to_skew(geometry.esviaje_grados)
    mx, my = active.get("mesh_x"), active.get("mesh_y")
    lx, ly = active.get("lateral_x"), active.get("lateral_y")
    # Lateral bars lie between the vertical mesh hooks and the formwork.
    # Keep their outer surfaces at the cover and move the hooks inward by
    # the exterior bar's diameter: surfaces touch without axis overlap.
    side_insets = (ly.diameter_mm / 1000 if ly else 0.0,
                   lx.diameter_mm / 1000 if lx else 0.0)
    reference = mx or my or next(iter(active.values()), None)
    if reference is None:
        return FootingAssembly((), ZapataSchedule((), tuple(issues)))
    rx = (mx or reference).diameter_mm / 2000
    ry = (my or reference).diameter_mm / 2000
    low_x = cover.inferior_m + rx
    high_x = geometry.alto_m - cover.superior_m - rx
    low_y, high_y = low_x + rx + ry, high_x - rx - ry
    bars, shape_by_id = [], {}

    def world(p, origin, u, v):
        return tuple(origin[i] + p[0] * u[i] + p[1] * v[i] for i in range(3))

    def add_run(rule, origin, u, v, span, level, coordinate, placement, skew=0.0,
                neighbour_origins=()):
        radius = bend_radius_cm(rule.diameter_mm) / 100
        hook = (rule.hook_cm or automatic_hook_cm(geometry.alto_m * 100)) / 100
        left, right = math.pi / 2 + skew, math.pi / 2 - skew
        tl, tr = radius * math.tan(left / 2), radius * math.tan(right / 2)
        if span < tl + tr - 1e-9:
            raise ValueError("El tramo no permite alojar sus dos radios de doblez.")
        hv = (math.sin(skew), -math.cos(skew))
        raw = ((hv[0] * (hook + tl), hv[1] * (hook + tl)), (0., 0.),
               (span, 0.), (span + hv[0] * (hook + tr), hv[1] * (hook + tr)))
        vertices, bulges = _fillet_polyline(raw, radius)
        lengths = [_length(a, b, bulge) for a, b, bulge in zip(vertices, vertices[1:], bulges)]
        total = sum(lengths)
        main_from, main_to = hook + radius * left, total - hook - radius * right
        variable = rule.key in ("mesh_y", "suple") and variable_y
        if total > 12 + 1e-9 and (variable or not rule.continuation_mark):
            reason = "la serie variable no tiene un reparto de empalmes definido" if variable else "no tiene marca de continuación"
            raise ValueError(f"desarrolla {math.ceil(total * 100 - 1e-9)} cm y requiere empalme; {reason}.")
        lap = lap_length_cm(rule.diameter_mm) / 100 if total > 12 + 1e-9 else 0.
        intervals, start = [], 0.
        while True:
            manual_first = not intervals and lap > 0 and rule.first_piece_cm > 0
            end = rule.first_piece_cm / 100 if manual_first else min(total, start + 12)
            if manual_first and (end - lap < main_from - 1e-9 or end > main_to + 1e-9):
                raise ValueError("El largo del primer fierro sitúa el empalme fuera del tramo recto; ajusta su largo sin invadir los dobleces.")
            if not manual_first and end < total - 1e-9:
                # A commercial piece may end at the last straight tangency,
                # but never inside the terminal hook or its bend.
                end = min(end, main_to)
            if end <= start + 1e-9:
                raise ValueError("No hay tramo recto suficiente para repartir las piezas y sus empalmes.")
            intervals.append((start, end))
            if end >= total - 1e-9:
                break
            if end - lap < main_from - 1e-9 or end > main_to + 1e-9:
                raise ValueError("No hay tramo recto suficiente para el traslapo reglado.")
            start = end - lap
        count = len(intervals)
        inset = cover.lateral_m + rule.diameter_mm / 2000

        def covered(points):
            return all(abs(y) <= geometry.largo_m / 2 - inset + 1e-8
                and abs(x-slope*y) <= geometry.ancho_m / 2 - inset*sec + 1e-8
                and cover.inferior_m+rule.diameter_mm/2000-1e-8 <= z
                <= geometry.alto_m-cover.superior_m-rule.diameter_mm/2000+1e-8
                for x,y,z in points)

        normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        diameter = rule.diameter_mm/1000
        shift = (0.,0.,0.)
        sliced = [_slice(vertices,bulges,start,end) for start,end in intervals]
        if count > 1:
            centre = (0.,0.,geometry.alto_m/2)
            preferred = 1 if sum((c-o)*n for c,o,n in zip(centre,origin,normal)) >= 0 else -1
            lane_coordinate = sum(o*n for o,n in zip(origin,normal))
            for sign in (preferred,-preferred):
                candidate = tuple(sign*diameter*n for n in normal)
                candidate_origin = tuple(o+d for o,d in zip(origin,candidate))
                # Do not consume another run's actual distribution lane.
                if any(abs(lane_coordinate+sign*diameter-sum(o*n for o,n in zip(other,normal)))
                       < diameter-1e-8 for other in neighbour_origins):
                    continue
                shifted_points = [tuple(world(p,candidate_origin,u,v)
                    for p in polyline_render_points(SimpleNamespace(vertices_m=pts,bulges=bends)))
                    for index,(pts,bends) in enumerate(sliced) if index%2]
                if not all(covered(points) for points in shifted_points):
                    continue
                # Adjacent already-placed continuation lanes may also compete
                # for room. Check parallel main segments, not only mouldage.
                collision = False
                for index,(pts,bends) in enumerate(sliced):
                    if not index%2:
                        continue
                    main = [(a,b) for a,b,bend in zip(pts,pts[1:],bends)
                            if abs(bend)<1e-12 and abs(a[1])<1e-9 and abs(b[1])<1e-9]
                    if not main:
                        continue
                    a,b = max(main,key=lambda pair:math.dist(*pair))
                    first,last = world(a,candidate_origin,u,v),world(b,candidate_origin,u,v)
                    length = math.dist(first,last)
                    for other in bars:
                        if other.key != rule.key or abs(abs(sum(x*y for x,y in zip(u,other.axis_u)))-1)>1e-8:
                            continue
                        params = [sum((p-a)*d for p,a,d in zip(point,first,u))
                                  for point in (other.main_start_m,other.main_end_m)]
                        if min(length,max(params))-max(0.,min(params)) <= 1e-8:
                            continue
                        perpendicular = tuple(p-a-params[0]*d for p,a,d in
                            zip(other.main_start_m,first,u))
                        if math.hypot(*perpendicular) < (rule.diameter_mm+other.diameter_mm)/2000-1e-8:
                            collision = True
                            break
                    if collision:
                        break
                if not collision:
                    shift = candidate
                    break
            else:
                raise ValueError('No caben las barras empalmadas lado a lado respetando recubrimientos y separación; revisa el reparto.')
        for index, (start, end) in enumerate(intervals):
            role = "completa" if count == 1 else "inicial" if index == 0 else "terminal" if index == count - 1 else "intermedia"
            mark = (rule.mark if index == 0 else rule.continuation_mark if count == 2 or index < count - 1
                    else rule.terminal_mark or rule.continuation_mark + "A")
            pts, bends = sliced[index]
            piece_offset = shift if index%2 else (0.,0.,0.)
            piece_origin = tuple(o+d for o,d in zip(origin,piece_offset))
            sampled = polyline_render_points(SimpleNamespace(vertices_m=pts, bulges=bends))
            points = tuple(world(p, piece_origin, u, v) for p in sampled)
            # Validate surfaces, including every sampled bend, not only corners.
            for x, y, z in points:
                if (abs(y) > geometry.largo_m / 2 - inset + 1e-8 or
                    abs(x - slope * y) > geometry.ancho_m / 2 - inset * sec + 1e-8 or
                    z < cover.inferior_m + rule.diameter_mm / 2000 - 1e-8 or
                    z > geometry.alto_m - cover.superior_m - rule.diameter_mm / 2000 + 1e-8):
                    raise ValueError("Un gancho o tramo invade el recubrimiento; revisa dimensiones y largo de gancho.")
            # Main tangencies are the horizontal segment in the local bar plane.
            horizontal = [(a, b) for a, b, bend in zip(pts, pts[1:], bends)
                          if abs(bend) < 1e-12 and abs(a[1]) < 1e-9 and abs(b[1]) < 1e-9]
            a, b = max(horizontal, key=lambda pair: math.dist(*pair)) if horizontal else ((tl, 0.), (tl, 0.))
            main_a, main_b = world(a, piece_origin, u, v), world(b, piece_origin, u, v)
            cut = float(math.ceil((end - start) * 100 - 1e-8))
            hooks = (index == 0) + (index == count - 1)
            nominal = int(math.ceil(hook * 100 - 1e-9))
            partials = ((nominal, int(cut) - 2 * nominal, nominal) if hooks == 2 else
                        (nominal, int(cut) - nominal) if index == 0 else
                        (int(cut) - nominal, nominal) if hooks == 1 else (int(cut),))
            lap_segments = ()
            if index:
                overlap_end = world((a[0] + lap, 0.), piece_origin, u, v)
                lap_segments = ((main_a, overlap_end),)
            identity = f"{placement}:{index}"
            bars.append(FootingBar(identity, rule.key, mark, rule.label, rule.diameter_mm,
                                  level, role, placement, coordinate, piece_origin, u, v,
                                  tuple(world(p, piece_origin, u, v) for p in pts), bends, points,
                                  main_a, main_b, cut, (end - start) * 100,
                                  bend_radius_cm(rule.diameter_mm), lap * 100, lap_segments))
            shape_by_id[identity] = {"vertices_m": pts, "bulges": bends, "raw_m": _raw_vertices(pts, bends),
                                    "main_start_x_m": a[0], "main_end_x_m": b[0],
                                    "developed_length_cm": (end - start) * 100,
                                    "splice_lane_index": index%2 if count>1 else 0,
                                    "splice_axis_offset_m": piece_offset,
                                    "cut_length_cm": cut, "partials_cm": partials, "hook_count": hooks}

    for rule in rules:
        if not rule.enabled:
            continue
        first_bar = len(bars)
        try:
            if rule.key in ("mesh_x", "mesh_y", "suple"):
                ref = (my or rule) if rule.key in ("mesh_x", "suple") else (mx or rule)
                axes = footing_mesh_axes(geometry, cover, rule, ref, side_insets_m=side_insets)
                if len(axes) > 12000:
                    raise ValueError("La distribución supera 12.000 ejes; revisa dimensiones y separación.")
                if rule.key == "mesh_x":
                    levels = (("superior", high_x), ("inferior", low_x))
                elif rule.key == "mesh_y":
                    levels = (("superior", high_y), ("inferior", low_y))
                else:
                    levels = (("superior", high_y - ry - rule.diameter_mm / 2000),)
                for i, axis in enumerate(axes):
                    for level, z in levels:
                        a, b = axis.start_m, axis.end_m
                        u = ((b[0] - a[0]) / axis.length_m, (b[1] - a[1]) / axis.length_m, 0.)
                        add_run(rule, (*a, z), u, (0., 0., 1. if level == "superior" else -1.),
                                axis.length_m, level, axis.coordinate_m, f"{rule.key}:{level}:{i}",
                                neighbour_origins=tuple((*other.start_m,z) for j,other in enumerate(axes) if j!=i))
            elif rule.key in ("lateral_x", "lateral_y"):
                r = rule.diameter_mm / 2000
                hx = geometry.ancho_m / 2 - (cover.lateral_m + r) * sec
                hy = geometry.largo_m / 2 - (cover.lateral_m + r)
                if hx <= 0 or hy <= 0:
                    raise ValueError("No queda contorno útil para los laterales.")
                mesh = (mx if rule.key == "lateral_y" else my) or reference
                low, high = (low_x, high_x) if rule.key == "lateral_y" else (low_y, high_y)
                lower = low + bend_radius_cm(mesh.diameter_mm) / 100
                upper = high - bend_radius_cm(mesh.diameter_mm) / 100
                if upper < lower:
                    raise ValueError("No queda altura útil para distribuir los laterales.")
                positions = distribution_positions_cm((upper - lower) * 100, rule.spacing_cm, rule.origin,
                                                      include_endpoints=True,
                                                      minimum_spacing_cm=rule.diameter_mm / 10)
                for i, position in enumerate(positions):
                    # In an elevation, Inicio begins at the upper bend's
                    # vertical tangency and descends; Final reverses the range.
                    z = upper - position / 100
                    for side in (-1, 1):
                        if rule.key == "lateral_x":
                            y = side * hy
                            origin = (side * hx + slope * y, y, z)
                            u, v, span = (-float(side), 0., 0.), (0., float(side), 0.), 2 * hx
                        else:
                            y = side * hy
                            origin = (side * hx + slope * y, y, z)
                            u = (-side * math.sin(angle), -side * math.cos(angle), 0.)
                            v = (side * math.cos(angle), -side * math.sin(angle), 0.)
                            span = 2 * hy * sec
                        add_run(rule, origin, u, v, span, "lateral", z,
                                f"{rule.key}:{side}:{i}", angle,
                                neighbour_origins=tuple((origin[0],origin[1],upper-other/100)
                                                       for j,other in enumerate(positions) if j!=i))
            else:
                raise ValueError("La familia no tiene geometría de zapata definida.")
        except (ValueError, OverflowError) as error:
            del bars[first_bar:]
            issues.append(ValidationIssue("error", f"{rule.label}: {error}"))

    # Apply deliberate omissions only after generating the real pieces. This
    # leaves the remaining runs, splice partners, coordinates and IDs intact.
    # The same filtered collection feeds quantities, detail, CAD and viewer.
    reference_bars = tuple(bars)
    mark_order = {rule.key: tuple(dict.fromkeys(bar.mark for bar in bars if bar.key == rule.key))
                  for rule in rules}
    removed_ids = set()
    by_id = {bar.id: bar for bar in bars}
    for rule in rules:
        if not rule.enabled or not rule.removed_pieces:
            continue
        stale = 0
        for removed in parse_removed_pieces(rule.removed_pieces, rule.key):
            bar = by_id.get(removed.id)
            if bar is None or bar.key != rule.key or bar.signature != removed.signature:
                stale += 1
            else:
                removed_ids.add(bar.id)
        if stale:
            issues.append(ValidationIssue("error", (
                f"{rule.label}: {stale} fierro(s) eliminado(s) ya no coinciden con el cálculo. "
                "Restaura esas eliminaciones y vuelve a seleccionar los fierros; "
                "no se eliminaron otras piezas en su lugar."
            )))
    bars = [bar for bar in bars if bar.id not in removed_ids]

    marks = []
    for rule in rules:
        family = [bar for bar in bars if bar.key == rule.key]
        roles_by_name = {}
        for bar in family:
            roles_by_name.setdefault(bar.mark.upper(), set()).add(bar.piece_role)
        for name, roles in roles_by_name.items():
            if len(roles) > 1:
                issues.append(ValidationIssue("error", f"Marca duplicada '{name}': piezas iniciales, intermedias y terminales requieren marcas distintas."))
        active_names = {bar.mark for bar in family}
        names = [name for name in mark_order[rule.key] if name in active_names]
        for name in names:
            pieces = [bar for bar in family if bar.mark == name]
            longest = max(pieces, key=lambda b: b.developed_length_cm)
            lengths = Counter(bar.length_cm for bar in pieces)
            variable = rule.key in ("mesh_y", "suple") and variable_y
            variants = tuple(RebarLengthVariant(length, count) for length, count in sorted(lengths.items())) if variable else ()
            shape = shape_by_id[longest.id]
            notes = dict(_VIEW_NOTES[rule.key])
            if abs(angle) > 1e-9:
                if not variable_y and rule.key in ("mesh_y", "suple"):
                    notes["AA"] = "sección oblicua de la malla longitudinal"
                for view in ("BB", "CC"):
                    if view in notes:
                        notes[view] = ("longitud real paralela a la cara lateral"
                                       if not variable_y and rule.key in ("mesh_y", "suple")
                                       else "sección oblicua paralela a la cara lateral")
            marks.append(RebarMark(rule.key, name, "Zapata", rule.label, rule.diameter_mm,
                                   len(pieces), longest.length_cm, sum(b.length_cm for b in pieces),
                                   tuple(notes), notes, shape["hook_count"], longest.bend_radius_cm,
                                   longest.piece_role, variants, shape))
    seen = set()
    for mark in marks:
        if mark.mark.upper() in seen:
            issues.append(ValidationIssue("error", f"Marca duplicada '{mark.mark}': cada pieza debe tener una marca única en la tabla."))
        seen.add(mark.mark.upper())
    splice_laps = None
    if any(rule.removed_pieces for rule in rules):
        ranges = {rule.key: set() for rule in rules}
        remaining_by_id = {bar.id: bar for bar in bars}
        for lap in physical_laps(bars):
            bar = remaining_by_id[lap.piece_id]
            local_x = lambda point: sum((p-o)*u for p, o, u in zip(point, bar.origin_m, bar.axis_u))
            ranges[bar.key].add(tuple(round(local_x(point), 12) for point in (lap.start_m, lap.end_m)))
        splice_laps = {key: tuple(sorted(values)) for key, values in ranges.items()}
    schedule = ZapataSchedule(tuple(marks), tuple(issues), splice_laps)
    return FootingAssembly(tuple(bars) if schedule.is_valid else (), schedule,
                           geometry.esviaje_grados, reference_bars)
