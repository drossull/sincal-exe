"""Generador CAD de vistas de zapata a partir de contornos confirmados."""
from __future__ import annotations

import math
from functools import partial
from dataclasses import dataclass, replace

from sincal.cad.rebar_marks import build_marks_support
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.plan import mesh_y_parallel_to_skew




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


def _point(point, scale=1.0):
    return f"(list {_fmt(point[0] * scale)} {_fmt(point[1] * scale)} 0.0)"


def _unit(a, b):
    length = math.dist(a, b)
    return ((b[0] - a[0]) / length, (b[1] - a[1]) / length)


def _at(point, vector, distance):
    return point[0] + vector[0] * distance, point[1] + vector[1] * distance


def _polyline_command(vertices, bulges, layer, tag, *, scale=1.0):
    """Emit the shared physical shape, without asking CAD to invent fillets."""
    data = ['(cons 0 "LWPOLYLINE")', '(cons 100 "AcDbEntity")',
            f'(cons 8 "{layer}")', '(cons 100 "AcDbPolyline")',
            f'(cons 90 {len(vertices)})', '(cons 70 0)']
    for point, bulge in zip(vertices, bulges):
        data.append(f'(cons 10 (list {_fmt(point[0] * scale)} {_fmt(point[1] * scale)}))')
        if abs(bulge) > 1e-12:
            data.append(f'(cons 42 {_fmt(bulge)})')
    return f'(progn (setq e (entmakex (list {" ".join(data)}))) (sincal:tag e "{tag}"))'


@dataclass(frozen=True)
class ProjectedFootingBar:
    source_id: str
    placement_id: str
    key: str
    mark: str
    level: str
    diameter_mm: float
    kind: str
    vertices_m: tuple[tuple[float, float], ...]
    bulges: tuple[float, ...]
    lap_segments_m: tuple[tuple[tuple[float, float], tuple[float, float]], ...] = ()


def _project(point, view, horizontal_origin=0.0):
    return (point[0], point[1]) if view == "FF" else (
        (point[0] if view == "FR" else point[1])-horizontal_origin, point[2])


def _simplify_open(points):
    """Remove only coincident/collinear points, preserving actual reversals."""
    result = []
    for point in points:
        if result and math.dist(result[-1], point) < 1e-10:
            continue
        while len(result) >= 2:
            a, b = result[-2:]
            if (abs(_cross(a, b, point)) > 1e-10 or
                    (b[0]-a[0])*(point[0]-b[0]) + (b[1]-a[1])*(point[1]-b[1]) < -1e-12):
                break
            result.pop()
        result.append(tuple(point))
    return tuple(result)


def _project_piece(bar, view, horizontal_origin=0.0):
    u, v = _project(bar.axis_u, view), _project(bar.axis_v, view)
    determinant = u[0]*v[1] - u[1]*v[0]
    if math.isclose(abs(determinant), 1.0, abs_tol=1e-9):
        vertices = tuple(_project(point, view, horizontal_origin) for point in bar.vertices_m)
        bulges = tuple(value * (1 if determinant > 0 else -1) for value in bar.bulges)
    else:
        # A projected circular arc is not generally circular. Preserve its
        # sampled projection instead of giving it a false radius in CAD.
        vertices = _simplify_open(_project(point, view, horizontal_origin) for point in bar.points_m)
        bulges = tuple(0.0 for _ in vertices)
    return ProjectedFootingBar(bar.id, bar.placement_id, bar.key, bar.mark,
                              bar.level, bar.diameter_mm, "polyline", vertices, bulges,
                              tuple(tuple(_project(point, view, horizontal_origin) for point in pair)
                                    for pair in getattr(bar, "lap_segments_m", ())))


def _main_section(bar, view, station=0.0, horizontal_origin=0.0):
    """Intersect the actual main piece at the longitudinal representative's cut."""
    a, b = bar.main_start_m, bar.main_end_m
    coordinate = 1 if view == "FR" else 0
    denominator = b[coordinate] - a[coordinate]
    if abs(denominator) < 1e-12:
        return None
    fraction = (station-a[coordinate]) / denominator
    if fraction < -1e-9 or fraction > 1 + 1e-9:
        return None
    point = tuple(a[i] + fraction * (b[i]-a[i]) for i in range(3))
    return ProjectedFootingBar(bar.id, bar.placement_id, bar.key, bar.mark,
                              bar.level, bar.diameter_mm, "circle", (_project(point, view, horizontal_origin),), (0.0,))


def _vertical_section(assembly, normal, station, horizontal, origin=0.0):
    """Intersect physical straights/arcs; preserve curves contained in-plane."""
    from sincal.cad.rebar_sections import intersect_bar_plane
    def point_in_view(point):
        return horizontal[0] * point[0] + horizontal[1] * point[1] - origin, point[2]

    result = []
    for bar in assembly.bars:
        section = intersect_bar_plane(bar, normal, station)
        for point in section.points_m:
            result.append(ProjectedFootingBar(
                bar.id, bar.placement_id, bar.key, bar.mark, bar.level,
                bar.diameter_mm, "circle", (point_in_view(point),), (0.0,)))
        determinant = ((horizontal[0] * bar.axis_u[0] + horizontal[1] * bar.axis_u[1]) * bar.axis_v[2]
                       - (horizontal[0] * bar.axis_v[0] + horizontal[1] * bar.axis_v[1]) * bar.axis_u[2])
        chains = []
        for segment in section.contained_segments:
            vertices = (point_in_view(segment.start_m), point_in_view(segment.end_m))
            if math.dist(*vertices) < 1e-10:
                continue
            bulge = segment.bulge * (1 if determinant >= 0 else -1)
            if chains and math.dist(chains[-1][0][-1], vertices[0]) < 1e-9:
                chains[-1][0].append(vertices[1])
                chains[-1][1][-1] = bulge
                chains[-1][1].append(0.0)
            else:
                chains.append(([vertices[0], vertices[1]], [bulge, 0.0]))
        for vertices, bulges in chains:
            result.append(ProjectedFootingBar(
                bar.id, bar.placement_id, bar.key, bar.mark, bar.level,
                bar.diameter_mm, "polyline", tuple(vertices), tuple(bulges)))
    return tuple(result)


def _reference_station(assembly, key):
    reference_bars = getattr(assembly, "reference_bars", ()) or assembly.bars
    references = [bar for bar in reference_bars if bar.key == key and bar.level == "superior"]
    references = references or [bar for bar in reference_bars if bar.key == key]
    return min(references, key=lambda bar: abs(bar.coordinate_m)).coordinate_m if references else 0.0


def _skew_side_section(assembly):
    """Cut at the original station, parallel to the real skewed lateral face.

    A parallel Y bar keeps its true bends; an oblique bar becomes its actual
    intersections. The reference width L/cos(skew) never stretches steel.
    """
    angle = math.radians(assembly.skew_degrees)
    sine, cosine = math.sin(angle), math.cos(angle)
    station_x = _reference_station(assembly, "mesh_y")
    return _vertical_section(assembly, (cosine, -sine), station_x*cosine,
                             (sine, cosine), station_x*sine)


def _uses_plane_section(skew, view):
    return abs(skew) > 1e-9 and (view in ("BB", "CC") or
        (view in ("FR", "AA") and mesh_y_parallel_to_skew(skew)))


def project_footing_assembly(assembly, view):
    """Return view representations of the same bars used by the schedule.

    Elevations retain the established central longitudinal representative and
    real cross sections. Skewed B–B/C–C cut parallel to the lateral face at
    the existing central station, until separate cutting stations are supplied.
    E–E (internal FF) displays upper meshes,
    one X placement and one level of each lateral face, without recounting steel.
    """
    if view not in ("FR", "AA", "BB", "CC", "FF"):
        raise ZapataCadError("La vista no corresponde a la zapata.")
    if view in ("BB", "CC") and abs(getattr(assembly, "skew_degrees", 0.0)) > 1e-9:
        return _skew_side_section(assembly)
    skew = getattr(assembly, "skew_degrees", 0.0)
    if _uses_plane_section(skew, view):
        station = _reference_station(assembly, "mesh_x" if view == "FR" else "mesh_y")
        if view == "FR":
            return _vertical_section(assembly, (0., 1.), station, (1., 0.),
                                     math.tan(math.radians(skew))*station)
        return _vertical_section(assembly, (1., 0.), station, (0., 1.))
    bars = assembly.bars
    reference_bars = getattr(assembly, "reference_bars", ()) or bars
    # Elevations use one common section origin, not a per-bar correction.
    # FR's skewed section centre is x = tan(skew)*Y. Cutting transverse
    # pieces at that same Y and translating the entire view keeps the nominal
    # rectangular reference valid without stretching or shifting any bar alone.
    reference_key = "mesh_x" if view == "FR" else "mesh_y"
    references = [bar for bar in reference_bars if bar.key == reference_key and bar.level == "superior"]
    references = references or [bar for bar in reference_bars if bar.key == reference_key]
    station = min(references, key=lambda bar: abs(bar.coordinate_m)).coordinate_m if references else 0.0
    horizontal_origin = math.tan(math.radians(getattr(assembly, "skew_degrees", 0.0)))*station if view == "FR" else 0.0
    longitudinal = {"mesh_x"} if view == "FR" else {"mesh_y", "suple"}
    transverse = {"mesh_y", "suple", "lateral_y"} if view == "FR" else {"mesh_x", "lateral_x"}
    selected = set()
    grouped = {}
    for bar in reference_bars:
        grouped.setdefault((bar.key, bar.level), {}).setdefault(bar.placement_id, []).append(bar)
    for (key, level), placements in grouped.items():
        if view == "FF":
            if level == "inferior":
                continue
            if key in ("mesh_y", "suple"):
                selected.update(placements)
            elif key == "mesh_x":
                chosen = min(placements.values(), key=lambda group: abs(group[0].coordinate_m))
                selected.add(chosen[0].placement_id)
            else:
                coordinates = [group[0].coordinate_m for group in placements.values()]
                centre = (min(coordinates) + max(coordinates)) / 2
                coordinate = min(coordinates, key=lambda value: abs(value-centre))
                selected.update(name for name, group in placements.items()
                                if math.isclose(group[0].coordinate_m, coordinate, abs_tol=1e-9))
        elif key in longitudinal:
            target_station = station if key == reference_key else 0.0
            chosen = min(placements.values(), key=lambda group: abs(group[0].coordinate_m-target_station))
            selected.add(chosen[0].placement_id)
    projected = []
    for bar in bars:
        if bar.placement_id in selected:
            projection = _project_piece(bar, view, horizontal_origin)
            if len(projection.vertices_m) >= 2:
                projected.append(projection)
        elif view != "FF" and bar.key in transverse:
            projection = _main_section(bar, view, station, horizontal_origin)
            if projection is not None:
                projected.append(projection)
    return tuple(projected)


def _circle_command(point, diameter, tag, *, scale=1.0):
    layer = f"fi{int(diameter)}"
    radius_m = diameter / 2000.0
    return (f'(progn (setq e (entmakex (list (cons 0 "CIRCLE") (cons 8 "{layer}") '
            f'(cons 10 {_point(point, scale)}) (cons 40 {_fmt(radius_m * scale)})))) '
            f'(sincal:tag e "{tag}"))')


def _bc_representative_drawing(assembly, view, geometry, cover):
    """Conventional longitudinal symbols, linked to existing physical pieces.

    Only B/C's drawing may extend a straight segment. The calculation, cutting
    schedule, bar geometry and physical section remain untouched.
    """
    physical = project_footing_assembly(assembly, view)
    references = getattr(assembly, "reference_bars", ()) or assembly.bars
    surviving = {bar.id for bar in assembly.bars}
    cosine = math.cos(math.radians(geometry.esviaje_grados))
    if cosine <= 0 or not math.isclose(geometry.esviaje_grados,
                                       getattr(assembly, "skew_degrees", 0.), abs_tol=1e-9):
        raise ZapataCadError("El esviaje de la referencia B/C no coincide con el cálculo.")
    lateral = max((bar.diameter_mm/1000 for bar in references if bar.key == "lateral_x"), default=0.)
    grouped = {}
    for bar in references:
        if bar.key in ("mesh_y", "suple"):
            grouped.setdefault((bar.key, bar.level), {}).setdefault(bar.placement_id, []).append(bar)
    representatives = []
    for (key, level), placements in grouped.items():
        target_station = _reference_station(assembly, "mesh_y") if key == "mesh_y" else 0.
        run = min(placements.values(), key=lambda bars: abs(bars[0].coordinate_m-target_station))
        source = run[0]
        def abscissa(point):
            return sum(value*axis for value, axis in zip(point, source.axis_u))
        all_x = [abscissa(point) for bar in run for point in bar.vertices_m]
        left, right = min(all_x), max(all_x)
        half_width = (geometry.largo_m/2-cover.lateral_m-source.diameter_mm/2000-lateral)/cosine
        shift_left, shift_right = -half_width-left, half_width-right
        extension = shift_right-shift_left
        if half_width <= 0 or extension < -1e-8:
            raise ZapataCadError("El recubrimiento no permite representar el fierro longitudinal de B/C.")
        # Read the original run even after deletions. A missing piece must not
        # relocate the symbol or move its surviving mate. Existing parallel
        # spliced runs already have the right span and require no adaptation.
        if abs(extension) <= 1e-8:
            # The parallel physical run already has the correct span. Keep its
            # whole shape rigid; do not perturb a lap through roundoff noise.
            shift_right = shift_left
            split = math.inf
        else:
            if len(run) != 1 or source.piece_role != "completa":
                raise ZapataCadError("Este recorrido empalmado no admite la representación B/C sin alterar sus traslapos.")
            start, end = sorted((abscissa(source.main_start_m), abscissa(source.main_end_m)))
            if end-start <= 1e-9:
                raise ZapataCadError("No hay un tramo recto para representar B/C sin deformar sus dobleces.")
            split = (start+end)/2

        def point_in_view(point):
            x = abscissa(point)
            return x+(shift_left if x < split else shift_right), point[2]

        for bar in run:
            if bar.id not in surviving:
                continue
            # Arcs always travel as rigid packs with their hooks. No affine
            # scaling, new splice, new mark or new manufactured length is used.
            for first, last, bulge in zip(bar.vertices_m, bar.vertices_m[1:], bar.bulges):
                if abs(bulge) > 1e-12 and (abscissa(first) < split) != (abscissa(last) < split):
                    raise ZapataCadError("La representación B/C no puede extenderse dentro de un doblez.")
            sign = 1 if bar.axis_v[2] >= 0 else -1
            representatives.append(ProjectedFootingBar(
                bar.id, bar.placement_id, bar.key, bar.mark, bar.level, bar.diameter_mm,
                "polyline", tuple(map(point_in_view, bar.vertices_m)),
                tuple(value*sign for value in bar.bulges),
                tuple(tuple(map(point_in_view, pair)) for pair in bar.lap_segments_m)))
    return tuple(piece for piece in physical if piece.key not in ("mesh_y", "suple")) + tuple(representatives)


def footing_drawing_projection(assembly, view, *, geometry=None, cover=None):
    """Apply the agreed thin-line contact convention to CAD elevations only.

    The physical projection remains available separately: section circles
    have their real diameter, but touch the longitudinal *line*, which has no
    model width in CAD. Never feed these presentation centres back into the
    assembly, schedule, detail or isometric model.

    With explicit dimensions and cover, B/C additionally shows the requested
    conventional longitudinal Y/suple run between the covered side limits.
    Its drawing length is never returned to the calculation or the schedule.
    FR retains the complete central X representative: its parallel contacting
    lap mate can sit just outside the mathematical cutting plane. Both pieces
    are projected rigidly; the separate physical section stays unchanged.
    """
    if view in ("BB", "CC") and (geometry is None) != (cover is None):
        raise ZapataCadError("La representación B/C requiere dimensiones y recubrimientos juntos.")
    skew = getattr(assembly, "skew_degrees", 0.0)
    conventional = view in ("BB", "CC") and geometry is not None and cover is not None and abs(skew) > 1e-9
    def drawing(source):
        if conventional:
            return _bc_representative_drawing(source, view, geometry, cover)
        physical = project_footing_assembly(source, view)
        if view != "FR" or not _uses_plane_section(skew, view):
            return physical
        references = getattr(source, "reference_bars", ()) or source.bars
        station = _reference_station(source, "mesh_x")
        placements = {}
        for bar in references:
            if bar.key == "mesh_x":
                placements.setdefault(bar.level, {}).setdefault(bar.placement_id, bar)
        selected = {min(runs.values(), key=lambda bar: abs(bar.coordinate_m-station)).placement_id
                    for runs in placements.values()}
        origin = math.tan(math.radians(skew))*station
        representatives = tuple(_project_piece(bar, "FR", origin) for bar in source.bars
                                if bar.placement_id in selected)
        return tuple(piece for piece in physical if piece.key != "mesh_x")+representatives
    projected = drawing(assembly)
    if view == "FF" or (view in ("BB", "CC") and abs(skew) > 1e-9
                        and not mesh_y_parallel_to_skew(skew) and not conventional):
        # A true skewed section has no assumed longitudinal Y line. Moving its
        # intersections towards a projected bar outside the plane would fake
        # contact and could displace them by centimetres, not half a diameter.
        return projected
    line_key = "mesh_x" if view == "FR" else "mesh_y"
    mesh_key = "mesh_y" if view == "FR" else "mesh_x"
    # Keep the established drafting anchors when a representative is deleted;
    # never move surviving circles or select a replacement bar to hide the gap.
    reference_bars = getattr(assembly, "reference_bars", ())
    anchors = (drawing(replace(assembly, bars=reference_bars))
               if reference_bars and len(reference_bars) != len(assembly.bars) else projected)
    lines = [piece for piece in anchors if piece.key == line_key and piece.kind == "polyline"]
    horizontals, legs = {}, []
    for piece in lines:
        for a, b, bulge in zip(piece.vertices_m, piece.vertices_m[1:], piece.bulges):
            if abs(bulge) > 1e-10 or math.dist(a, b) < 1e-10:
                continue
            if abs(a[1] - b[1]) < 1e-10:
                horizontals.setdefault(piece.level, []).extend((a, b))
            elif abs(a[0] - b[0]) < 1e-10:
                legs.append(a[0])
    # Move the suple by the same amount as its supporting transverse mesh.
    # Snapping both to the main line would collapse their two physical layers.
    mesh_shifts = {}
    for piece in anchors:
        if piece.kind == "circle" and piece.key == mesh_key and piece.level in horizontals:
            line_z = horizontals[piece.level][0][1]
            z = piece.vertices_m[0][1]
            mesh_shifts[piece.level] = line_z + math.copysign(piece.diameter_mm / 2000, z - line_z) - z
    result = []
    for piece in projected:
        if piece.kind != "circle":
            result.append(piece)
            continue
        x, z = piece.vertices_m[0]
        if piece.key == mesh_key or (view == "FR" and piece.key == "suple"):
            z += mesh_shifts.get(piece.level, 0.0)
        elif piece.key.startswith("lateral") and legs:
            leg_x = min(legs, key=lambda value: abs(value - x))
            x = leg_x + math.copysign(piece.diameter_mm / 2000, x - leg_x)
        result.append(replace(piece, vertices_m=((x, z),)))
    return tuple(result)


def _dimension_command(first, last, text_point, layer, tag, *, scale=1.0):
    return (
        f'(sincal:marked-dim {_point(first, scale)} {_point(last, scale)} {_point(text_point, scale)} '
        f'"{layer}" "{tag}")'
    )


def _mark_command(anchor, landing, mark, state, layer, tag, *, scale=1.0):
    return (
        f'(sincal:linked-mark {_point(anchor, scale)} {_point(landing, scale)} '
        f'"{mark}" "{state}" "{layer}" "{tag}")'
    )


def _rule_map(rules):
    return {rule.key: rule for rule in rules if rule.enabled}


def build_zapata_lisp(view, candidate, geometry, cover, rules, abutment_key, master_path="",
                      *, drawing_units_per_m=1.0):
    """Emit CAD geometry in drawing units; all input lengths remain metres.

    Scaling is applied only to newly emitted coordinates and radii. The source
    moldaje is never selected, transformed, renamed or otherwise changed.
    """
    if (isinstance(drawing_units_per_m, bool)
            or not isinstance(drawing_units_per_m, (int, float))
            or not math.isfinite(drawing_units_per_m)
            or drawing_units_per_m not in (1, 100, 1000)):
        raise ZapataCadError("Selecciona unidades de dibujo en metros, centímetros o milímetros.")
    polyline_command = partial(_polyline_command, scale=drawing_units_per_m)
    circle_command = partial(_circle_command, scale=drawing_units_per_m)
    dimension_command = partial(_dimension_command, scale=drawing_units_per_m)
    mark_command = partial(_mark_command, scale=drawing_units_per_m)
    if view == "DD":
        raise ZapataCadError("DD corresponde a muros y alas; no genera armadura de zapata.")
    if view not in ("FR", "AA", "BB", "CC", "FF"):
        raise ZapataCadError(f"La vista {view} no corresponde a una vista de zapata vigente.")
    if len(candidate.vertices) < 3:
        raise ZapataCadError("Vuelve a seleccionar la referencia de la zapata para obtener sus vértices.")
    active = _rule_map(rules)
    if "mesh_x" not in active or "mesh_y" not in active:
        raise ZapataCadError("Las mallas 1–2 y 3 deben estar activas.")
    points = _simplify(candidate.vertices)
    minx, maxx = min(p[0] for p in points), max(p[0] for p in points)
    miny, maxy = min(p[1] for p in points), max(p[1] for p in points)
    tag = f"{abutment_key.upper()}_{view}_ZAP"
    commands = []
    diameters = sorted({int(rule.diameter_mm) for rule in active.values()})
    assembly = build_footing_assembly(geometry, cover, rules)
    schedule = assembly.schedule
    if not schedule.is_valid:
        detail = "; ".join(issue.message for issue in schedule.issues if issue.severity == "error")
        raise ZapataCadError(detail or "La armadura no superó la validación.")
    def presentation(rule, side):
        # Table B is the total for the entire footing. A single face must not
        # display that total as its own quantity; keep the native no-count state.
        state = "SIN_CANTIDAD"
        if rule.key == "suple":
            return state + "_SUP_SUPLE"
        if rule.key in ("mesh_x", "mesh_y"):
            state += "_SUP" if view == "FF" or side == "top" else "_INF"
        return state

    # The selected reference contributes translation only. Hooks, radii and
    # piece identities come from the assembly. B/C's representative straight
    # span uses canonical dimensions/cover; its drawn length is never a cut
    # length or quantity. Circles use the agreed thin-line contact convention.
    centre = ((minx + maxx) / 2.0, (miny + maxy) / 2.0)
    translation = centre if view == "FF" else (centre[0], miny)
    annotations = {}
    for projected in footing_drawing_projection(assembly, view, geometry=geometry, cover=cover):
        vertices = tuple((point[0] + translation[0], point[1] + translation[1])
                         for point in projected.vertices_m)
        layer = f"fi{int(projected.diameter_mm)}"
        if projected.kind == "circle":
            commands.append(circle_command(vertices[0], projected.diameter_mm, tag))
        else:
            commands.append(polyline_command(vertices, projected.bulges, layer, tag))
            # Keep the physical lap pieces in the view, but dimension their
            # overlap only in the detail/splice preview, not on the footing.
        if projected.key.startswith("lateral"):
            if view == "FF" and projected.key == "lateral_x":
                side = "bottom" if sum(point[1] for point in vertices)/len(vertices) < centre[1] else "top"
            else:
                side = "left" if sum(point[0] for point in vertices)/len(vertices) < centre[0] else "right"
        else:
            side = "bottom" if projected.level == "inferior" else "top"
        band = None
        if _uses_plane_section(geometry.esviaje_grados, view) and projected.kind == "circle":
            # Bent bars can cross the skewed plane at different heights. Do
            # not join those isolated intersections with a diagonal pitch dim.
            band = round(vertices[0][0 if projected.key.startswith("lateral") else 1], 8)
        annotations.setdefault((projected.key, projected.level, projected.mark,
                                projected.kind, side, band), []).extend(vertices)

    for (key, level, mark, kind, side, band), vertices in annotations.items():
        rule = active[key]
        layer = f"fi{int(rule.diameter_mm)}"
        lane = 1 if key == "suple" else 0
        if kind == "circle":
            ordered = sorted(set(vertices), key=lambda point: (point[1], point[0])
                             if key.startswith("lateral") else (point[0], point[1]))
            first, last = ordered[0], ordered[-1]
            if len(ordered) > 1:
                location = ((minx - ANNOTATION_OFFSET_M if side == "left" else maxx + ANNOTATION_OFFSET_M),
                            (first[1]+last[1])/2) if key.startswith("lateral") else (
                                (first[0]+last[0])/2,
                                maxy + ANNOTATION_OFFSET_M + lane*.20 if side == "top" else miny - ANNOTATION_OFFSET_M-lane*.20)
                commands.append(dimension_command(first, last, location, layer, tag))
            anchor = ordered[len(ordered)//2]
        else:
            anchor = vertices[len(vertices)//2]
        outward = {"top": (0, 1), "bottom": (0, -1), "left": (-1, 0), "right": (1, 0)}[side]
        landing = _at(anchor, outward, LEADER_DOGLEG_M + lane * .18)
        landing = (landing[0] + .30, landing[1]) if side in ("top", "bottom") else (landing[0], landing[1] + .30)
        commands.append(mark_command(anchor, landing, mark, presentation(rule, side), layer, tag))

    layers = "\n    ".join(f'(sincal:layer "fi{diameter}")' for diameter in diameters)
    body = "\n    ".join(commands)
    marks_support = build_marks_support(schedule, rules, abutment_key,
                                       drawing_units_per_m=drawing_units_per_m)
    master_lisp = master_path.replace("\\", "\\\\").replace('"', '\\"')
    return f'''(vl-load-com)
{marks_support}
(defun sincal:layer (name / layer)
  (if (not (tblsearch "LAYER" name)) (command "_.-LAYER" "_M" name "_C" "5" name "_LT" "Continuous" name ""))
  (setq layer (vla-Item (vla-get-Layers doc) name))
  (if (= :vlax-true (vla-get-Lock layer)) (srb:fail "La capa de armaduras esta bloqueada.")))
(defun sincal:tag (ent value / data) (regapp "SINCAL_REBAR") (setq data (entget ent)) (entmod (append data (list (list -3 (list "SINCAL_REBAR" (cons 1000 value)))))) ent)
(defun sincal:delete-old (value / ss i ent xd)
  (if (setq ss (ssget "_X" '((-3 ("SINCAL_REBAR")))))
    (progn
      (setq i 0)
      (repeat (sslength ss)
        (setq ent (ssname ss i) xd (assoc -3 (entget ent '("SINCAL_REBAR"))))
        (if (and xd (equal value (cdr (assoc 1000 (cdadr xd)))))
          (progn
            (if (SCM:Locked (vlax-ename->vla-object ent)) (srb:fail "La vista anterior contiene armaduras bloqueadas."))
            (if (not (entdel ent)) (srb:fail "No se pudo reemplazar una armadura de la vista anterior."))))
        (setq i (1+ i))))))
(defun sincal:item (collection name / result)
  (setq result (vl-catch-all-apply 'vla-Item (list collection name)))
  (if (vl-catch-all-error-p result) nil result))
(defun sincal:styles-ready (database)
  (sincal:item (vla-get-DimStyles database) "GSG_COTAS"))
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
(defun sincal:import-annotation-styles (acad doc master / dbx opened ok)
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
                  (setq ok nil)))))
          (vl-catch-all-apply 'vlax-release-object (list dbx))))))
  (and ok (sincal:styles-ready doc)))
(defun sincal:ensure-annotation-styles (acad doc master)
  (or (sincal:styles-ready doc)
      (sincal:import-annotation-styles acad doc master)))
(defun sincal:marked-dim (p1 p2 location layer tag / obj)
  (setq obj (vla-AddDimAligned ms (vlax-3d-point p1) (vlax-3d-point p2)
                                (vlax-3d-point location)))
  (vla-put-StyleName obj "GSG_COTAS")
  (vla-put-Layer obj layer)
  (sincal:tag (vlax-vla-object->ename obj) tag)
  obj)
(defun sincal:label-box (obj / lo hi)
  (vla-GetBoundingBox obj 'lo 'hi)
  (list (vlax-safearray->list lo) (vlax-safearray->list hi)))
(defun sincal:boxes-overlap (a b / pad)
  (setq pad {_fmt(0.05 * drawing_units_per_m)})
  (and (< (- (caar a) pad) (caadr b)) (> (+ (caadr a) pad) (caar b))
       (< (- (cadar a) pad) (cadadr b)) (> (+ (cadadr a) pad) (cadar b))))
(defun sincal:place-label (obj arrow landing / box conflict old dx dy step count)
  ;; Compare only labels emitted by this view. Native extents account for the
  ;; actual text and annotation scale; never scan existing drawing objects.
  (setq dx (- (car landing) (car arrow)) dy (- (cadr landing) (cadr arrow)) count 0)
  (setq box (sincal:label-box obj) conflict T)
  (while conflict
    (setq conflict nil)
    (foreach old sincal:label-boxes
      (if (sincal:boxes-overlap box old) (setq conflict T)))
    (if conflict
      (progn
        (if (>= count 100) (srb:fail "No se pudo separar las marcas de esta vista."))
        (setq step (if (> (abs dx) (abs dy))
                     (list (* (if (< dx 0) -1.0 1.0) (+ (- (caadr box) (caar box)) {_fmt(0.10 * drawing_units_per_m)})) 0.0 0.0)
                     (list 0.0 (* (if (< dy 0) -1.0 1.0) (+ (- (cadadr box) (cadar box)) {_fmt(0.10 * drawing_units_per_m)})) 0.0)))
        (vla-Move obj (vlax-3d-point '(0 0 0)) (vlax-3d-point step))
        (setq box (sincal:label-box obj) count (1+ count)))))
  (setq sincal:label-boxes (cons box sincal:label-boxes))
  (vlax-safearray->list (vlax-variant-value (vla-get-InsertionPoint obj))))
(defun sincal:linked-mark (arrow landing mark state layer tag / label)
  ;; Native annotative definitions expect paper height, exactly like MARCA-SC.
  (setq label (srb:label landing mark state nil nil nil layer tag 2.5))
  ;; Layout occurs after the batch field evaluation. Field-code placeholders
  ;; must not determine the extents or cause a regeneration for every label.
  (setq sincal:view-labels (cons (list label arrow landing layer tag) sincal:view-labels)))
(defun sincal:place-mark (label arrow landing layer tag / points obj)
  (setq landing (sincal:place-label (vlax-ename->vla-object label) arrow landing))
  (setq points (vlax-make-safearray vlax-vbDouble '(0 . 5)))
  (vlax-safearray-fill points
    (list (car arrow) (cadr arrow) 0.0 (car landing) (cadr landing) 0.0))
  (setq obj (vla-AddLeader ms points (vlax-ename->vla-object label) 0))
  (vla-put-StyleName obj "GSG_COTAS")
  (vla-put-Layer obj layer)
  (sincal:tag (vlax-vla-object->ename obj) tag))
(defun sincal:generate-view (/ acad doc ms e b sincal:label-boxes sincal:view-labels entry)
  (setq acad (vlax-get-acad-object) doc (vla-get-ActiveDocument acad) ms (vla-get-ModelSpace doc))
  (srb:prepare)
  (if (sincal:ensure-annotation-styles acad doc "{master_lisp}")
    (progn
    (srb:sync-table)
    {layers}
    (sincal:delete-old "{tag}")
    {body}
    (srb:finish)
    (foreach entry (reverse sincal:view-labels) (apply 'sincal:place-mark entry))
    (vla-Regen doc 1)
    (setq *SINCAL_LIVE_RESULT* (list T "Vista {view} de zapata generada. Moldaje preservado."))
    (princ "\\n[SINCAL] Vista {view} generada con cotas y llamadas. Moldaje preservado."))
    (progn
      (setq *SINCAL_LIVE_RESULT* (list nil (strcat "SINCAL no pudo importar GSG_COTAS. "
                     "Verifique el master DWG y vuelva a generar; no se modifico la vista.")))
      (princ (strcat "\\n[SINCAL] " (cadr *SINCAL_LIVE_RESULT*)))))
  (princ))
(defun c:SINCAL-ZAPATA-GENERAR ()
  (srb:run 'sincal:generate-view))
'''
