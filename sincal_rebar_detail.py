"""Modelo geométrico de despiece para las armaduras de zapata."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

from sincal_rebar_model import automatic_hook_cm, lap_length_cm


DETAIL_GROUP_ORDER = ("G12", "G3", "G3A", "G45", "G6")
DETAIL_GROUP_KEYS = {
    "G12": "mesh_x",
    "G3": "mesh_y",
    "G3A": "suple",
    "G45": "lateral_x",
    "G6": "lateral_y",
}


@dataclass(frozen=True)
class DetailPiece:
    mark: str
    key: str
    diameter_mm: int
    quantity: int
    spacing_cm: float
    total_cm: int
    layer: str
    vertices_m: tuple[tuple[float, float], ...]
    bulges: tuple[float, ...]
    partials_cm: tuple[int, ...]
    partial_segments_m: tuple[tuple[tuple[float, float], tuple[float, float]], ...]
    main_start_x_m: float
    main_end_x_m: float


@dataclass(frozen=True)
class DetailGroup:
    group_id: str
    pieces: tuple[DetailPiece, ...]
    offsets_m: tuple[tuple[float, float], ...]
    laps_m: tuple[tuple[float, float, float], ...]
    fingerprint: str


def _signed_turn(incoming, outgoing):
    return math.atan2(
        incoming[0] * outgoing[1] - incoming[1] * outgoing[0],
        incoming[0] * outgoing[0] + incoming[1] * outgoing[1],
    )


def _unit(vector):
    length = math.hypot(*vector)
    return vector[0] / length, vector[1] / length


def _fillet_polyline(raw_points, radius_m):
    """Convierte vértices teóricos en tangencias y bulges de una LWPOLYLINE."""
    if len(raw_points) <= 2 or radius_m <= 0:
        return tuple(raw_points), tuple(0.0 for _ in raw_points)
    vertices = [raw_points[0]]
    bulges = [0.0]
    for index in range(1, len(raw_points) - 1):
        previous, corner, following = raw_points[index - 1:index + 2]
        toward_previous = _unit((previous[0] - corner[0], previous[1] - corner[1]))
        toward_following = _unit((following[0] - corner[0], following[1] - corner[1]))
        incoming = (-toward_previous[0], -toward_previous[1])
        outgoing = toward_following
        turn = _signed_turn(incoming, outgoing)
        tangent = radius_m * math.tan(abs(turn) / 2.0)
        tangent_in = (
            corner[0] + toward_previous[0] * tangent,
            corner[1] + toward_previous[1] * tangent,
        )
        tangent_out = (
            corner[0] + toward_following[0] * tangent,
            corner[1] + toward_following[1] * tangent,
        )
        vertices.append(tangent_in)
        bulges.append(math.tan(turn / 4.0))
        vertices.append(tangent_out)
        bulges.append(0.0)
    vertices.append(raw_points[-1])
    bulges.append(0.0)
    return tuple(vertices), tuple(bulges)


def _piece_bend_sweeps(mark, skew_degrees):
    skew = math.radians(max(-45.0, min(45.0, skew_degrees)))
    left = math.pi / 2.0 + skew
    right = math.pi / 2.0 - skew
    if mark.hook_count == 2:
        return left, right
    if mark.hook_count == 1 and mark.piece_role == "terminal":
        return (right,)
    if mark.hook_count == 1:
        return (left,)
    return ()


def _effective_partials(total_cm, hook_cm, radius_cm, sweeps):
    """Parciales enteros cuya suma coincide exactamente con el largo desarrollado."""
    arcs = tuple(radius_cm * sweep for sweep in sweeps)
    hook_partials = tuple(math.ceil(hook_cm + arc / 2.0 - 1e-9) for arc in arcs)
    main = int(total_cm) - sum(hook_partials)
    if main <= 0:
        raise ValueError("El largo total no permite distribuir ganchos y tramo principal.")
    if len(hook_partials) == 2:
        return (hook_partials[0], main, hook_partials[1]), arcs
    if len(hook_partials) == 1:
        return (hook_partials[0], main), arcs
    return (int(total_cm),), arcs


def _build_piece(mark, rule, height_cm, skew_degrees):
    total_cm = int(math.ceil(mark.unit_length_cm - 1e-9))
    radius_cm = float(mark.bend_radius_cm)
    hook_cm = rule.hook_cm or automatic_hook_cm(height_cm)
    sweeps = _piece_bend_sweeps(mark, skew_degrees)
    partials, arcs = _effective_partials(total_cm, hook_cm, radius_cm, sweeps)
    radius_m = radius_cm / 100.0
    skew = math.radians(max(-45.0, min(45.0, skew_degrees)))
    hook_vector = (math.sin(skew), -math.cos(skew))

    if mark.hook_count == 0:
        raw = ((0.0, 0.0), (total_cm / 100.0, 0.0))
        main_start, main_end = 0.0, total_cm / 100.0
        segment_partials = partials
    elif mark.hook_count == 1 and mark.piece_role == "terminal":
        arc = arcs[0]
        hook_tangent = (partials[0] - arc / 2.0) / 100.0
        main_tangent = (partials[1] - arc / 2.0) / 100.0
        tangent_distance = radius_m * math.tan(sweeps[0] / 2.0)
        corner = (main_tangent + tangent_distance, 0.0)
        endpoint = (
            corner[0] + hook_vector[0] * (hook_tangent + tangent_distance),
            hook_vector[1] * (hook_tangent + tangent_distance),
        )
        raw = ((0.0, 0.0), corner, endpoint)
        main_start, main_end = 0.0, corner[0]
        segment_partials = (partials[1], partials[0])
    elif mark.hook_count == 1:
        arc = arcs[0]
        hook_tangent = (partials[0] - arc / 2.0) / 100.0
        main_tangent = (partials[1] - arc / 2.0) / 100.0
        tangent_distance = radius_m * math.tan(sweeps[0] / 2.0)
        corner = (0.0, 0.0)
        endpoint = (
            hook_vector[0] * (hook_tangent + tangent_distance),
            hook_vector[1] * (hook_tangent + tangent_distance),
        )
        raw = (endpoint, corner, (main_tangent + tangent_distance, 0.0))
        main_start, main_end = 0.0, main_tangent + tangent_distance
        segment_partials = partials
    else:
        left_arc, right_arc = arcs
        left_hook = (partials[0] - left_arc / 2.0) / 100.0
        main_tangent = (partials[1] - (left_arc + right_arc) / 2.0) / 100.0
        right_hook = (partials[2] - right_arc / 2.0) / 100.0
        left_tangent = radius_m * math.tan(sweeps[0] / 2.0)
        right_tangent = radius_m * math.tan(sweeps[1] / 2.0)
        left_corner = (0.0, 0.0)
        right_corner = (main_tangent + left_tangent + right_tangent, 0.0)
        left_endpoint = (
            left_corner[0] + hook_vector[0] * (left_hook + left_tangent),
            left_corner[1] + hook_vector[1] * (left_hook + left_tangent),
        )
        right_endpoint = (
            right_corner[0] + hook_vector[0] * (right_hook + right_tangent),
            right_corner[1] + hook_vector[1] * (right_hook + right_tangent),
        )
        raw = (left_endpoint, left_corner, right_corner, right_endpoint)
        main_start, main_end = left_corner[0], right_corner[0]
        segment_partials = partials

    vertices, bulges = _fillet_polyline(raw, radius_m)
    segments = tuple(zip(raw, raw[1:]))
    return DetailPiece(
        mark=mark.mark,
        key=mark.key,
        diameter_mm=int(mark.diameter_mm),
        quantity=mark.quantity,
        spacing_cm=rule.spacing_cm,
        total_cm=total_cm,
        layer=f"fi{int(mark.diameter_mm)}",
        vertices_m=vertices,
        bulges=bulges,
        partials_cm=tuple(int(value) for value in segment_partials),
        partial_segments_m=segments,
        main_start_x_m=main_start,
        main_end_x_m=main_end,
    )


def _group_fingerprint(group_id, pieces, offsets, laps):
    payload = {
        "group": group_id,
        "pieces": [
            {
                "mark": piece.mark, "diameter": piece.diameter_mm,
                "quantity": piece.quantity, "spacing": piece.spacing_cm,
                "total": piece.total_cm, "vertices": piece.vertices_m,
                "bulges": piece.bulges, "partials": piece.partials_cm,
            }
            for piece in pieces
        ],
        "offsets": offsets,
        "laps": laps,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def build_detail_groups(schedule, rules, geometry):
    """Agrupa marcas físicas en cinco detalles estables y actualizables."""
    rules_by_key = {rule.key: rule for rule in rules if rule.enabled}
    marks_by_key = {}
    for mark in schedule.marks:
        marks_by_key.setdefault(mark.key, []).append(mark)
    result = []
    for group_id in DETAIL_GROUP_ORDER:
        key = DETAIL_GROUP_KEYS[group_id]
        marks = marks_by_key.get(key, ())
        rule = rules_by_key.get(key)
        if not marks or not rule:
            continue
        pieces = tuple(
            _build_piece(mark, rule, geometry.alto_m * 100.0, geometry.esviaje_grados)
            for mark in marks
        )
        offsets = []
        laps = []
        current_main_end = None
        for index, piece in enumerate(pieces):
            y = -0.005 * index
            if index == 0 or current_main_end is None:
                x = 0.0
            else:
                overlap = lap_length_cm(piece.diameter_mm) / 100.0
                x = current_main_end - overlap - piece.main_start_x_m
                laps.append((current_main_end - overlap, current_main_end, y - 0.28 - 0.16 * (index - 1)))
            offsets.append((x, y))
            current_main_end = x + piece.main_end_x_m
        fingerprint = _group_fingerprint(group_id, pieces, tuple(offsets), tuple(laps))
        result.append(DetailGroup(group_id, pieces, tuple(offsets), tuple(laps), fingerprint))
    return tuple(result)


def polyline_developed_length_m(piece):
    """Longitud de comprobación de la LWPOLYLINE con bulges."""
    total = 0.0
    for index in range(len(piece.vertices_m) - 1):
        first, last = piece.vertices_m[index:index + 2]
        chord = math.dist(first, last)
        bulge = piece.bulges[index]
        if abs(bulge) < 1e-12:
            total += chord
        else:
            sweep = 4.0 * math.atan(abs(bulge))
            radius = chord / (2.0 * math.sin(sweep / 2.0))
            total += radius * sweep
    return total
