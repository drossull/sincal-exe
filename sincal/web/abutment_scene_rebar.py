"""Read-only scene adapter for the shared physical footing reinforcement.

Every rendered item is one manufactured piece, including its real curves and
lap. This adapter never reconstructs a bar from a nominal axis or calculates a
second set of quantities. Coordinates are metres; the assembly's CAD-local
plan is rigidly rotated to match Proyecto Puentes, with the footing bottom at
Z=0. Neither the source state nor the fabrication geometry is modified.
"""
from __future__ import annotations

from collections.abc import Mapping
import math

from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.splices import physical_laps
from sincal.web.rebar import domain


REPRESENTATION_NOTE = (
    "Armadura de zapata: todas las familias activadas, con ganchos, radios de "
    "doblez y empalmes del mismo modelo usado por el despiece y CAD."
)


def _result(bars=(), issues=(), *, valid=False, removed_bars=()):
    return {"bars": list(bars), "issues": list(issues), "valid": valid,
            "removed_bars": list(removed_bars),
            "representation": "physical_pieces", "units": "m", "note": REPRESENTATION_NOTE}


def build_footing_bars(state, *, orientation="romboide"):
    """Expose complete physical pieces from explicitly supplied parameters."""
    if not isinstance(state, Mapping) or not state:
        return _result(issues=["Configura y calcula la zapata para mostrar su armadura."])
    try:
        geometry, cover, rules = domain(state)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        return _result(issues=[f"La armadura de zapata requiere parámetros completos y válidos: {error}"])
    if orientation not in ("romboide", "rectangular", "rectangular_rotado"):
        return _result(issues=["La orientación de la zapata no permite ubicar su armadura."])
    angle = math.radians(geometry.esviaje_grados)
    if orientation != "romboide" and abs(angle) > 1e-9:
        return _result(issues=["La armadura 3D de esta orientación de zapata esviada está pendiente; no se deformaron los fierros."])

    active = {rule.key: rule for rule in rules if rule.enabled}
    if "mesh_x" not in active or "mesh_y" not in active:
        return _result(issues=["Activa ambas mallas de zapata para representar su armadura, como requieren las vistas CAD."])
    try:
        assembly = build_footing_assembly(geometry, cover, rules)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        return _result(issues=[f"La armadura de zapata requiere parámetros completos y válidos: {error}"])
    issues = [issue.message for issue in assembly.schedule.issues]
    originals = {bar.id: bar for bar in assembly.reference_bars}
    removed = []
    for rule in rules:
        for record in rule.removed_pieces:
            bar = originals.get(record.id)
            matched = bar is not None and bar.signature == record.signature
            removed.append({"id": record.id, "signature": record.signature, "key": rule.key,
                            "label": rule.label, "status": "removed" if matched else "unresolved",
                            **({"mark": bar.mark, "piece_role": bar.piece_role, "length_cm": bar.length_cm,
                                "diameter_mm": bar.diameter_mm} if matched else {})})
    if not assembly.is_valid:
        return _result(issues=issues, removed_bars=removed)

    cs, sn = math.cos(angle), math.sin(angle)

    def world(point):
        x, y, z = point
        return [cs * x - sn * y, sn * x + cs * y, z]

    lap_segments, lap_partners, lap_lengths = {}, {}, {}
    for lap in physical_laps(assembly.bars):
        lap_segments.setdefault(lap.piece_id, []).append((lap.start_m, lap.end_m))
        lap_partners.setdefault(lap.piece_id, []).append({
            "piece_id": lap.partner_id, "axis_distance_m": lap.axis_distance_m,
            "segment": [world(lap.partner_start_m), world(lap.partner_end_m)],
        })
        for piece_id in (lap.piece_id, lap.partner_id):
            lap_lengths[piece_id] = max(lap_lengths.get(piece_id, 0), round(lap.length_cm, 10))

    bars = [{
        "id": bar.id, "signature": bar.signature, "key": bar.key, "element_key": "abutment.footing",
        "label": bar.label, "mark": bar.mark, "marks": [bar.mark],
        "diameter_mm": bar.diameter_mm, "level": bar.level,
        "piece_role": bar.piece_role, "placement_id": bar.placement_id,
        "length_cm": bar.length_cm, "developed_length_cm": bar.developed_length_cm,
        "bend_radius_cm": bar.bend_radius_cm, "lap_cm": lap_lengths.get(bar.id, 0),
        "representation": "physical_pieces", "points": [world(point) for point in bar.points_m],
        "vertices": [world(point) for point in bar.vertices_m], "bulges": list(bar.bulges),
        "main_start": world(bar.main_start_m), "main_end": world(bar.main_end_m),
        "lap_segments": [[world(first), world(last)] for first, last in lap_segments.get(bar.id, ())],
        "lap_partners": lap_partners.get(bar.id, []),
    } for bar in assembly.bars]
    return _result(bars, issues, valid=True, removed_bars=removed)
