"""Wing-wall bars, without distribution or reinforcement assumptions.

The caller supplies explicit corners or endpoints in metres, already placed
at the required covers. Hook inputs are straight lengths after their curves.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

from .detail import DetailPiece, _fillet_polyline, polyline_render_points
from .model import DIAMETROS_DISPONIBLES_MM, LARGO_COMERCIAL_CM, bend_radius_cm


@dataclass(frozen=True)
class WingBar:
    id: str
    key: str
    mark: str
    label: str
    diameter_mm: float
    spacing_cm: float
    hook_start_cm: float
    hook_end_cm: float
    start_m: tuple[float, float, float]
    end_m: tuple[float, float, float]
    axis_u: tuple[float, float, float]
    axis_v: tuple[float, float, float]
    vertices_m: tuple[tuple[float, float, float], ...]
    bulges: tuple[float, ...]
    points_m: tuple[tuple[float, float, float], ...]
    main_start_m: tuple[float, float, float]
    main_end_m: tuple[float, float, float]
    length_cm: int
    developed_length_cm: float
    bend_radius_cm: float
    detail: DetailPiece
    piece_role: str = "completa"

    @property
    def signature(self) -> str:
        """Bind edits to physical geometry, independent of mark and caption."""
        def numbers(values):
            return tuple(0.0 if abs(value) < 1e-12 else round(float(value), 12)
                         for value in values)
        physical = {
            "version": "wing-bracket-v1", "key": self.key,
            "diameter_mm": self.diameter_mm,
            "vertices_m": tuple(numbers(point) for point in self.vertices_m),
            "bulges": numbers(self.bulges),
            "axis_u": numbers(self.axis_u), "axis_v": numbers(self.axis_v),
        }
        return hashlib.sha256(json.dumps(physical, sort_keys=True, separators=(",", ":"),
                                         allow_nan=False).encode("utf-8")).hexdigest()


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}: ingresa un número finito.")
    return float(value)


def _point(value, label):
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError(f"{label}: se requieren tres coordenadas.")
    return tuple(_number(item, label) for item in value)


def make_bracket(start_m, end_m, inward, diameter_mm, hook_start_cm, hook_end_cm,
                 *, identity, key, mark, label, spacing_cm):
    """Return one immutable 3D bracket and its exact flat ``DetailPiece``.

    The three theoretical straight legs have two 90-degree bends of radius
    3Ø. Only cut labels round up to centimetres; geometry is never lengthened.
    No covers, distribution, splice, mark numbering or direction are inferred.
    """
    start, end = _point(start_m, "Inicio"), _point(end_m, "Final")
    inside = _point(inward, "Dirección hacia el interior")
    diameter = _number(diameter_mm, "Diámetro")
    hooks = (_number(hook_start_cm, "Gancho inicial"), _number(hook_end_cm, "Gancho final"))
    spacing = _number(spacing_cm, "Separación")
    if diameter not in DIAMETROS_DISPONIBLES_MM:
        raise ValueError("El diámetro debe pertenecer a la lista de fierros disponible.")
    if min(hooks) <= 0 or spacing <= 0:
        raise ValueError("Los ganchos y la separación deben ser mayores que cero.")
    for value, name in ((identity, "Identificador"), (key, "Familia"), (mark, "Marca"), (label, "Rótulo")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name}: se requiere un texto no vacío.")
    span = math.dist(start, end)
    radius_cm = bend_radius_cm(diameter)
    radius = radius_cm/100
    if not math.isfinite(span) or span <= 2*radius:
        raise ValueError("El tramo principal debe ser mayor que dos radios de doblez.")
    if span > LARGO_COMERCIAL_CM/100 or max(hooks) > LARGO_COMERCIAL_CM:
        raise ValueError("El corchete supera 12 m; su reparto de empalmes no está definido.")
    axis_u = tuple((last-first)/span for first, last in zip(start, end))
    norm = math.hypot(*inside)
    if not math.isclose(norm, 1., rel_tol=0., abs_tol=1e-9):
        raise ValueError("La dirección hacia el interior debe ser un vector unitario.")
    dot = sum(u*v for u, v in zip(axis_u, inside))
    if abs(dot) > 1e-9:
        raise ValueError("La dirección hacia el interior debe ser perpendicular al tramo principal.")
    # Remove only accepted floating-point noise so lifting to 3D is an exact
    # orthonormal transform, without changing the supplied hook direction.
    perpendicular = tuple(value-dot*u for value, u in zip(inside, axis_u))
    norm = math.hypot(*perpendicular)
    axis_v = tuple(value/norm for value in perpendicular)
    hook_start, hook_end = (value/100 for value in hooks)
    raw = ((0., hook_start+radius), (0., 0.), (span, 0.), (span, hook_end+radius))
    vertices, bulges = _fillet_polyline(raw, radius)
    developed_cm = math.fsum((hook_start, hook_end, span-2*radius, math.pi*radius))*100
    # The epsilon only removes sub-nanometre floating-point noise at an exact
    # centimetre or commercial limit; it is not an engineering tolerance.
    cut_cm = math.ceil(developed_cm-1e-9)
    if developed_cm > LARGO_COMERCIAL_CM+1e-9 or cut_cm > LARGO_COMERCIAL_CM:
        raise ValueError("El corchete supera 12 m; su reparto de empalmes no está definido.")
    first_partial, last_partial = (math.ceil(value-1e-9) for value in hooks)
    detail = DetailPiece(
        mark=mark, key=key, diameter_mm=int(diameter), quantity=1,
        spacing_cm=spacing, total_cm=cut_cm, layer=f"fi{int(diameter)}",
        vertices_m=vertices, bulges=bulges,
        partials_cm=(first_partial, cut_cm-first_partial-last_partial, last_partial),
        partial_segments_m=tuple(zip(raw, raw[1:])),
        main_start_x_m=radius, main_end_x_m=span-radius,
        developed_length_cm=developed_cm,
    )

    def world(point):
        return tuple(origin+point[0]*u+point[1]*v for origin, u, v in zip(start, axis_u, axis_v))

    return WingBar(identity, key, mark, label, diameter, spacing, *hooks, start, end,
                   axis_u, axis_v, tuple(map(world, vertices)), bulges,
                   tuple(map(world, polyline_render_points(detail))),
                   world((radius, 0.)), world((span-radius, 0.)),
                   cut_cm, developed_cm, radius_cm, detail)


def make_single_hook(start_m, end_m, inward, diameter_mm, hook_start_cm,
                     *, identity, key, mark, label, spacing_cm):
    """Return one L bar with an initial 90° hook and a straight free end.

    ``start_m`` is the theoretical corner, while ``end_m`` is the actual
    free tip. The supplied hook is its straight length after the bend. The
    caller owns positioning, covers and distribution; this function neither
    assumes a total length nor inserts a second hook or a splice.
    """
    start, end = _point(start_m, "Inicio"), _point(end_m, "Final")
    inside = _point(inward, "Dirección del gancho")
    diameter = _number(diameter_mm, "Diámetro")
    hook_cm = _number(hook_start_cm, "Gancho inicial")
    spacing = _number(spacing_cm, "Separación")
    if diameter not in DIAMETROS_DISPONIBLES_MM:
        raise ValueError("El diámetro debe pertenecer a la lista de fierros disponible.")
    if hook_cm <= 0 or spacing <= 0:
        raise ValueError("El gancho y la separación deben ser mayores que cero.")
    for value, name in ((identity, "Identificador"), (key, "Familia"), (mark, "Marca"), (label, "Rótulo")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name}: se requiere un texto no vacío.")
    span = math.dist(start, end)
    radius_cm = bend_radius_cm(diameter)
    radius = radius_cm/100
    if not math.isfinite(span) or span <= radius:
        raise ValueError("El tramo principal debe ser mayor que un radio de doblez.")
    if span > LARGO_COMERCIAL_CM/100 or hook_cm > LARGO_COMERCIAL_CM:
        raise ValueError("El fierro con un gancho supera 12 m; su reparto de empalmes no está definido.")
    axis_u = tuple((last-first)/span for first, last in zip(start, end))
    norm = math.hypot(*inside)
    if not math.isclose(norm, 1., rel_tol=0., abs_tol=1e-9):
        raise ValueError("La dirección del gancho debe ser un vector unitario.")
    dot = sum(u*v for u, v in zip(axis_u, inside))
    if abs(dot) > 1e-9:
        raise ValueError("La dirección del gancho debe ser perpendicular al tramo principal.")
    perpendicular = tuple(value-dot*u for value, u in zip(inside, axis_u))
    norm = math.hypot(*perpendicular)
    axis_v = tuple(value/norm for value in perpendicular)
    hook = hook_cm/100
    raw = ((0., hook+radius), (0., 0.), (span, 0.))
    vertices, bulges = _fillet_polyline(raw, radius)
    developed_cm = math.fsum((hook, span-radius, math.pi*radius/2))*100
    cut_cm = math.ceil(developed_cm-1e-9)
    if developed_cm > LARGO_COMERCIAL_CM+1e-9 or cut_cm > LARGO_COMERCIAL_CM:
        raise ValueError("El fierro con un gancho supera 12 m; su reparto de empalmes no está definido.")
    hook_partial = math.ceil(hook_cm-1e-9)
    detail = DetailPiece(
        mark=mark, key=key, diameter_mm=int(diameter), quantity=1,
        spacing_cm=spacing, total_cm=cut_cm, layer=f"fi{int(diameter)}",
        vertices_m=vertices, bulges=bulges,
        partials_cm=(hook_partial, cut_cm-hook_partial),
        partial_segments_m=tuple(zip(raw, raw[1:])),
        main_start_x_m=radius, main_end_x_m=span,
        developed_length_cm=developed_cm,
    )

    def world(point):
        if point == (span, 0.):
            return end
        return tuple(origin+point[0]*u+point[1]*v for origin, u, v in zip(start, axis_u, axis_v))

    return WingBar(identity, key, mark, label, diameter, spacing, hook_cm, 0., start, end,
                   axis_u, axis_v, tuple(map(world, vertices)), bulges,
                   tuple(map(world, polyline_render_points(detail))),
                   world((radius, 0.)), end,
                   cut_cm, developed_cm, radius_cm, detail)


def make_single_hook_path(main_points_m, hook_start_direction, diameter_mm, hook_start_cm,
                          *, identity, key, mark, label, spacing_cm):
    """Fillet an explicit coplanar route with one initial hook and a free tip.

    All main points are theoretical corners except the last, which is the
    actual straight free end. Directions, placement, covers and quantity are
    supplied by the caller. Every bend retains its real angle and radius 3Ø.
    """
    if not isinstance(main_points_m, (list, tuple)) or len(main_points_m) < 2:
        raise ValueError("El recorrido principal necesita al menos dos puntos.")
    main = tuple(_point(point, "Punto del recorrido") for point in main_points_m)
    direction = _point(hook_start_direction, "Dirección del gancho inicial")
    if len(main) == 2:
        return make_single_hook(*main, direction, diameter_mm, hook_start_cm,
                                identity=identity, key=key, mark=mark, label=label, spacing_cm=spacing_cm)
    vectors = tuple(tuple(b-a for a,b in zip(first,last)) for first,last in zip(main,main[1:]))
    lengths = tuple(math.hypot(*vector) for vector in vectors)
    if any(not math.isfinite(length) or length <= 0 for length in lengths):
        raise ValueError("Los segmentos principales deben tener longitud finita mayor que cero.")
    axis_u = tuple(value/lengths[0] for value in vectors[0])
    if not math.isclose(math.hypot(*direction), 1., rel_tol=0, abs_tol=1e-9):
        raise ValueError("La dirección del gancho debe ser un vector unitario.")
    noise = sum(a*b for a,b in zip(axis_u,direction))
    if abs(noise) > 1e-9:
        raise ValueError("El gancho debe ser perpendicular al segmento inicial.")
    diameter = _number(diameter_mm, "Diámetro")
    hook_cm = _number(hook_start_cm, "Gancho inicial")
    spacing = _number(spacing_cm, "Separación")
    if diameter not in DIAMETROS_DISPONIBLES_MM:
        raise ValueError("El diámetro debe pertenecer a la lista de fierros disponible.")
    if hook_cm <= 0 or spacing <= 0:
        raise ValueError("El gancho y la separación deben ser mayores que cero.")
    for value,name in ((identity,"Identificador"),(key,"Familia"),(mark,"Marca"),(label,"Rótulo")):
        if not isinstance(value,str) or not value.strip():
            raise ValueError(f"{name}: se requiere un texto no vacío.")
    if hook_cm > LARGO_COMERCIAL_CM:
        raise ValueError("El fierro con un gancho supera 12 m; su reparto de empalmes no está definido.")
    radius_cm = bend_radius_cm(diameter)
    radius = radius_cm/100
    origin = main[0]
    perpendicular = tuple(value-noise*u for value,u in zip(direction,axis_u))
    norm = math.hypot(*perpendicular)
    axis_v = tuple(value/norm for value in perpendicular)
    normal = (axis_u[1]*axis_v[2]-axis_u[2]*axis_v[1],
              axis_u[2]*axis_v[0]-axis_u[0]*axis_v[2],
              axis_u[0]*axis_v[1]-axis_u[1]*axis_v[0])
    offsets = tuple(tuple(value-zero for value,zero in zip(point,origin)) for point in main)
    if any(abs(sum(a*b for a,b in zip(offset,normal))) > 1e-9 for offset in offsets):
        raise ValueError("El recorrido y su gancho deben pertenecer a un mismo plano.")
    planar = tuple((sum(a*b for a,b in zip(offset,axis_u)), sum(a*b for a,b in zip(offset,axis_v)))
                   for offset in offsets)
    raw = ((0.,hook_cm/100+radius),*planar)
    raw_lengths = tuple(math.dist(first,last) for first,last in zip(raw,raw[1:]))
    turns, tangents = [], [0.]
    for first,corner,last in zip(raw,raw[1:],raw[2:]):
        incoming = tuple(b-a for a,b in zip(first,corner))
        outgoing = tuple(b-a for a,b in zip(corner,last))
        length_in, length_out = math.hypot(*incoming),math.hypot(*outgoing)
        incoming = tuple(value/length_in for value in incoming)
        outgoing = tuple(value/length_out for value in outgoing)
        turn = math.atan2(incoming[0]*outgoing[1]-incoming[1]*outgoing[0],
                          incoming[0]*outgoing[0]+incoming[1]*outgoing[1])
        if math.pi-abs(turn) <= 1e-9:
            raise ValueError("El recorrido no puede invertir su dirección en un doblez de 180°.")
        turns.append(abs(turn))
        tangents.append(radius*math.tan(abs(turn)/2))
    tangents.append(0.)
    straight = tuple(length-before-after for length,before,after in zip(raw_lengths,tangents,tangents[1:]))
    if any(length < -1e-9 for length in straight):
        raise ValueError("Los radios de doblez no caben en uno de los segmentos del recorrido.")
    if any(length < 0 for length in straight):
        raise ValueError("Las tangencias de los dobleces se superponen en un segmento.")
    try:
        developed_cm = math.fsum((*straight,*(radius*turn for turn in turns)))*100
    except OverflowError as error:
        raise ValueError("El fierro con un gancho supera 12 m; su reparto de empalmes no está definido.") from error
    if not math.isfinite(developed_cm) or developed_cm > LARGO_COMERCIAL_CM+1e-9:
        raise ValueError("El fierro con un gancho supera 12 m; su reparto de empalmes no está definido.")
    cut_cm = math.ceil(developed_cm-1e-9)
    vertices,bulges = _fillet_polyline(raw,radius)
    # The initial arc belongs to the first main partial. Each interior arc
    # is shared by its two neighbours; there is no arc at the free tip.
    main_partials = []
    for index in range(1,len(straight)):
        left_arc = radius*turns[index-1]*(1 if index == 1 else .5)
        right_arc = radius*turns[index]/2 if index < len(straight)-1 else 0.
        main_partials.append((straight[index]+left_arc+right_arc)*100)
    components = (hook_cm,*main_partials)
    partials = [math.ceil(hook_cm-1e-9),0]
    partials.extend(math.ceil(math.fsum(components[index:])-1e-9)
                    - math.ceil(math.fsum(components[index+1:])-1e-9)
                    for index in range(2,len(components)))
    partials[1] = cut_cm-partials[0]-sum(partials[2:])
    if min(partials) < 0:
        raise ValueError("El recorrido no permite expresar sus parciales en centímetros enteros.")
    detail = DetailPiece(
        mark=mark,key=key,diameter_mm=int(diameter),quantity=1,spacing_cm=spacing,
        total_cm=cut_cm,layer=f"fi{int(diameter)}",vertices_m=vertices,bulges=bulges,
        partials_cm=tuple(partials),partial_segments_m=tuple(zip(raw,raw[1:])),
        main_start_x_m=radius,main_end_x_m=planar[-1][0],developed_length_cm=developed_cm)

    def world(point):
        if point == planar[-1]:
            return main[-1]
        return tuple(zero+point[0]*u+point[1]*v for zero,u,v in zip(origin,axis_u,axis_v))

    return WingBar(identity,key,mark,label,diameter,spacing,hook_cm,0.,main[0],main[-1],
                   axis_u,axis_v,tuple(map(world,vertices)),bulges,
                   tuple(map(world,polyline_render_points(detail))),world((radius,0.)),main[-1],
                   cut_cm,developed_cm,radius_cm,detail)


def make_bracket_path(main_points_m, hook_start_direction, hook_end_direction,
                      diameter_mm, hook_start_cm, hook_end_cm, *, identity, key,
                      mark, label, spacing_cm):
    """Fillet an explicit coplanar route, with perpendicular endpoint hooks.

    Main points are theoretical corners already placed by the caller. Interior
    turns keep their actual angles and radius 3Ø; no route, cover or splice is
    inferred. ``DetailPiece`` keeps one partial per original straight segment.
    """
    if not isinstance(main_points_m, (list, tuple)) or len(main_points_m) < 2:
        raise ValueError("El recorrido principal necesita al menos dos puntos.")
    main = tuple(_point(point, "Punto del recorrido") for point in main_points_m)
    directions = (_point(hook_start_direction, "Dirección del gancho inicial"),
                  _point(hook_end_direction, "Dirección del gancho final"))
    vectors = tuple(tuple(b-a for a, b in zip(first, last)) for first, last in zip(main, main[1:]))
    lengths = tuple(math.hypot(*vector) for vector in vectors)
    if any(not math.isfinite(length) or length <= 0 for length in lengths):
        raise ValueError("Los segmentos principales deben tener longitud finita mayor que cero.")
    units = tuple(tuple(value/length for value in vector) for vector, length in zip(vectors, lengths))
    for direction, unit in zip(directions, (units[0], units[-1])):
        if not math.isclose(math.hypot(*direction), 1., rel_tol=0, abs_tol=1e-9):
            raise ValueError("Las direcciones de los ganchos deben ser vectores unitarios.")
        if abs(sum(a*b for a, b in zip(direction, unit))) > 1e-9:
            raise ValueError("Cada gancho debe ser perpendicular a su segmento principal.")
    if len(main) == 2 and math.dist(*directions) <= 1e-9:
        return make_bracket(*main, directions[0], diameter_mm, hook_start_cm, hook_end_cm,
                            identity=identity, key=key, mark=mark, label=label, spacing_cm=spacing_cm)

    diameter = _number(diameter_mm, "Diámetro")
    hooks = (_number(hook_start_cm, "Gancho inicial"), _number(hook_end_cm, "Gancho final"))
    spacing = _number(spacing_cm, "Separación")
    if diameter not in DIAMETROS_DISPONIBLES_MM:
        raise ValueError("El diámetro debe pertenecer a la lista de fierros disponible.")
    if min(hooks) <= 0 or spacing <= 0:
        raise ValueError("Los ganchos y la separación deben ser mayores que cero.")
    for value, name in ((identity, "Identificador"), (key, "Familia"), (mark, "Marca"), (label, "Rótulo")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name}: se requiere un texto no vacío.")
    if max(hooks) > LARGO_COMERCIAL_CM:
        raise ValueError("El corchete supera 12 m; su reparto de empalmes no está definido.")
    radius_cm = bend_radius_cm(diameter)
    radius = radius_cm/100
    origin, axis_u = main[0], units[0]
    noise = sum(a*b for a, b in zip(axis_u, directions[0]))
    inward = tuple(value-noise*u for value, u in zip(directions[0], axis_u))
    inward_norm = math.hypot(*inward)
    axis_v = tuple(value/inward_norm for value in inward)
    normal = (axis_u[1]*axis_v[2]-axis_u[2]*axis_v[1],
              axis_u[2]*axis_v[0]-axis_u[0]*axis_v[2],
              axis_u[0]*axis_v[1]-axis_u[1]*axis_v[0])

    def local(vector):
        return (sum(a*b for a, b in zip(vector, axis_u)),
                sum(a*b for a, b in zip(vector, axis_v)))

    offsets = tuple(tuple(value-zero for value, zero in zip(point, origin)) for point in main)
    if (any(abs(sum(a*b for a, b in zip(offset, normal))) > 1e-9 for offset in offsets)
            or abs(sum(a*b for a, b in zip(directions[-1], normal))) > 1e-9):
        raise ValueError("El recorrido y sus ganchos deben pertenecer a un mismo plano.")
    planar = tuple(local(offset) for offset in offsets)
    end_u, end_requested = local(units[-1]), local(directions[-1])
    end_sign = 1 if end_u[0]*end_requested[1]-end_u[1]*end_requested[0] > 0 else -1
    end_normal = (-end_sign*end_u[1], end_sign*end_u[0])
    hook_start, hook_end = (value/100 for value in hooks)
    last = tuple(value+(hook_end+radius)*direction for value, direction in zip(planar[-1], end_normal))
    raw = ((0., hook_start+radius), *planar, last)
    raw_lengths = tuple(math.dist(first, last) for first, last in zip(raw, raw[1:]))
    turns, tangents = [], [0.]
    for first, corner, last in zip(raw, raw[1:], raw[2:]):
        incoming = tuple(b-a for a, b in zip(first, corner))
        outgoing = tuple(b-a for a, b in zip(corner, last))
        incoming_length, outgoing_length = math.hypot(*incoming), math.hypot(*outgoing)
        incoming = tuple(value/incoming_length for value in incoming)
        outgoing = tuple(value/outgoing_length for value in outgoing)
        turn = math.atan2(incoming[0]*outgoing[1]-incoming[1]*outgoing[0],
                          incoming[0]*outgoing[0]+incoming[1]*outgoing[1])
        if math.pi-abs(turn) <= 1e-9:
            raise ValueError("El recorrido no puede invertir su dirección en un doblez de 180°.")
        turns.append(abs(turn))
        tangents.append(radius*math.tan(abs(turn)/2))
    tangents.append(0.)
    straight = tuple(length-before-after for length, before, after in zip(raw_lengths, tangents, tangents[1:]))
    if any(length < -1e-9 for length in straight):
        raise ValueError("Los radios de doblez no caben en uno de los segmentos del recorrido.")
    if any(length < 0 for length in straight):
        # No shortening of a physical segment is used to make a route fit.
        raise ValueError("Las tangencias de los dobleces se superponen en un segmento.")
    try:
        developed_cm = math.fsum((*straight, *(radius*turn for turn in turns)))*100
    except OverflowError as error:
        raise ValueError("El corchete supera 12 m; su reparto de empalmes no está definido.") from error
    if not math.isfinite(developed_cm) or developed_cm > LARGO_COMERCIAL_CM+1e-9:
        raise ValueError("El corchete supera 12 m; su reparto de empalmes no está definido.")
    cut_cm = math.ceil(developed_cm-1e-9)
    vertices, bulges = _fillet_polyline(raw, radius)
    # Endpoint arcs belong to the adjacent main partial; interior arcs are
    # shared between their two main partials. Round labels from the far end,
    # leaving the first main partial to absorb total-cut rounding. Thus a
    # variable wing segment does not change the fixed frontal-wall partial.
    main_partials = []
    for index in range(1, len(straight)-1):
        left_arc = radius*turns[index-1]*(1 if index == 1 else .5)
        right_arc = radius*turns[index]*(1 if index == len(straight)-2 else .5)
        main_partials.append((straight[index]+left_arc+right_arc)*100)
    components = (hooks[0], *main_partials, hooks[1])
    partials = [math.ceil(hooks[0]-1e-9), 0]
    partials.extend(math.ceil(math.fsum(components[index:])-1e-9)
                    - math.ceil(math.fsum(components[index+1:])-1e-9)
                    for index in range(2, len(components)))
    partials[1] = cut_cm-partials[0]-sum(partials[2:])
    if min(partials) < 0:
        raise ValueError("El recorrido no permite expresar sus parciales en centímetros enteros.")
    main_start = (planar[0][0]+radius, planar[0][1])
    main_end = tuple(value-radius*direction for value, direction in zip(planar[-1], end_u))
    detail = DetailPiece(
        mark=mark, key=key, diameter_mm=int(diameter), quantity=1, spacing_cm=spacing,
        total_cm=cut_cm, layer=f"fi{int(diameter)}", vertices_m=vertices, bulges=bulges,
        partials_cm=tuple(partials), partial_segments_m=tuple(zip(raw, raw[1:])),
        main_start_x_m=main_start[0], main_end_x_m=main_end[0], developed_length_cm=developed_cm)

    def world(point):
        return tuple(zero+point[0]*u+point[1]*v for zero, u, v in zip(origin, axis_u, axis_v))

    return WingBar(identity, key, mark, label, diameter, spacing, *hooks, main[0], main[-1],
                   axis_u, axis_v, tuple(map(world, vertices)), bulges,
                   tuple(map(world, polyline_render_points(detail))), world(main_start), world(main_end),
                   cut_cm, developed_cm, radius_cm, detail)


def make_open_path(main_points_m, diameter_mm, *, identity, key, mark, label, spacing_cm):
    """Return an explicit coplanar path with two free, unhooked endpoints.

    Interior points are theoretical corners. Only their bends receive radius
    3Ø; endpoints are never shortened or bent. Each original main segment has
    one developed partial, sharing interior arcs with its neighbouring segment.
    """
    if not isinstance(main_points_m, (list, tuple)) or len(main_points_m) < 2:
        raise ValueError("El recorrido principal necesita al menos dos puntos.")
    main = tuple(_point(point, "Punto del recorrido") for point in main_points_m)
    vectors = tuple(tuple(b-a for a,b in zip(first,last)) for first,last in zip(main,main[1:]))
    lengths = tuple(math.hypot(*vector) for vector in vectors)
    if any(not math.isfinite(length) or length <= 0 for length in lengths):
        raise ValueError("Los segmentos principales deben tener longitud finita mayor que cero.")
    diameter = _number(diameter_mm, "Diámetro")
    spacing = _number(spacing_cm, "Separación")
    if diameter not in DIAMETROS_DISPONIBLES_MM:
        raise ValueError("El diámetro debe pertenecer a la lista de fierros disponible.")
    if spacing <= 0:
        raise ValueError("La separación debe ser mayor que cero.")
    for value,name in ((identity,"Identificador"),(key,"Familia"),(mark,"Marca"),(label,"Rótulo")):
        if not isinstance(value,str) or not value.strip():
            raise ValueError(f"{name}: se requiere un texto no vacío.")
    origin = main[0]
    axis_u = tuple(value/lengths[0] for value in vectors[0])
    offsets = tuple(tuple(value-zero for value,zero in zip(point,origin)) for point in main)
    axis_v = None
    for vector in offsets[2:]:
        along = sum(a*b for a,b in zip(vector,axis_u))
        perpendicular = tuple(value-along*u for value,u in zip(vector,axis_u))
        norm = math.hypot(*perpendicular)
        if norm > 1e-10:
            axis_v = tuple(value/norm for value in perpendicular)
            break
    if axis_v is None:
        # A straight bar has no preferred bend plane. Select a deterministic
        # perpendicular only for its flat detail; its world axis is unchanged.
        index = min(range(3),key=lambda i: abs(axis_u[i]))
        reference = tuple(float(i == index) for i in range(3))
        along = axis_u[index]
        perpendicular = tuple(value-along*u for value,u in zip(reference,axis_u))
        norm = math.hypot(*perpendicular)
        axis_v = tuple(value/norm for value in perpendicular)
    normal = (axis_u[1]*axis_v[2]-axis_u[2]*axis_v[1],
              axis_u[2]*axis_v[0]-axis_u[0]*axis_v[2],
              axis_u[0]*axis_v[1]-axis_u[1]*axis_v[0])
    if any(abs(sum(a*b for a,b in zip(offset,normal))) > 1e-9 for offset in offsets):
        raise ValueError("Todos los puntos del recorrido deben pertenecer a un mismo plano.")
    raw = tuple((sum(a*b for a,b in zip(offset,axis_u)),sum(a*b for a,b in zip(offset,axis_v)))
                for offset in offsets)
    radius_cm = bend_radius_cm(diameter)
    radius = radius_cm/100
    raw_lengths = tuple(math.dist(first,last) for first,last in zip(raw,raw[1:]))
    turns, tangents = [], [0.]
    for first,corner,last in zip(raw,raw[1:],raw[2:]):
        incoming = tuple(b-a for a,b in zip(first,corner))
        outgoing = tuple(b-a for a,b in zip(corner,last))
        length_in,length_out = math.hypot(*incoming),math.hypot(*outgoing)
        incoming = tuple(value/length_in for value in incoming)
        outgoing = tuple(value/length_out for value in outgoing)
        turn = math.atan2(incoming[0]*outgoing[1]-incoming[1]*outgoing[0],
                          incoming[0]*outgoing[0]+incoming[1]*outgoing[1])
        if math.pi-abs(turn) <= 1e-9:
            raise ValueError("El recorrido no puede invertir su dirección en un doblez de 180°.")
        turns.append(abs(turn))
        tangents.append(radius*math.tan(abs(turn)/2))
    tangents.append(0.)
    straight = tuple(length-before-after for length,before,after in zip(raw_lengths,tangents,tangents[1:]))
    if any(length < -1e-9 for length in straight):
        raise ValueError("Los radios de doblez no caben en uno de los segmentos del recorrido.")
    if any(length < 0 for length in straight):
        raise ValueError("Las tangencias de los dobleces se superponen en un segmento.")
    try:
        developed_cm = math.fsum((*straight,*(radius*turn for turn in turns)))*100
    except OverflowError as error:
        raise ValueError("El fierro sin ganchos supera 12 m; su reparto de empalmes no está definido.") from error
    if not math.isfinite(developed_cm) or developed_cm > LARGO_COMERCIAL_CM+1e-9:
        raise ValueError("El fierro sin ganchos supera 12 m; su reparto de empalmes no está definido.")
    cut_cm = math.ceil(developed_cm-1e-9)
    vertices,bulges = _fillet_polyline(raw,radius)
    components = tuple((length+(radius*turns[index-1]/2 if index else 0.)
                         +(radius*turns[index]/2 if index < len(turns) else 0.))*100
                       for index,length in enumerate(straight))
    partials = [0]
    partials.extend(math.ceil(math.fsum(components[index:])-1e-9)
                    - math.ceil(math.fsum(components[index+1:])-1e-9)
                    for index in range(1,len(components)))
    partials[0] = cut_cm-sum(partials[1:])
    if min(partials) < 0:
        raise ValueError("El recorrido no permite expresar sus parciales en centímetros enteros.")
    detail = DetailPiece(
        mark=mark,key=key,diameter_mm=int(diameter),quantity=1,spacing_cm=spacing,
        total_cm=cut_cm,layer=f"fi{int(diameter)}",vertices_m=vertices,bulges=bulges,
        partials_cm=tuple(partials),partial_segments_m=tuple(zip(raw,raw[1:])),
        main_start_x_m=0.,main_end_x_m=raw[-1][0],developed_length_cm=developed_cm)

    def world(point):
        if point == raw[0]:
            return main[0]
        if point == raw[-1]:
            return main[-1]
        return tuple(zero+point[0]*u+point[1]*v for zero,u,v in zip(origin,axis_u,axis_v))

    return WingBar(identity,key,mark,label,diameter,spacing,0.,0.,main[0],main[-1],
                   axis_u,axis_v,tuple(map(world,vertices)),bulges,
                   tuple(map(world,polyline_render_points(detail))),main[0],main[-1],
                   cut_cm,developed_cm,radius_cm,detail)
