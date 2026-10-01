"""Web adapter; engineering rules remain in the existing domain model."""
from dataclasses import asdict, replace
from copy import deepcopy
import math

from sincal.rebar.model import Cover, ZapataGeometry, default_zapata_rules, build_zapata_schedule
from sincal.rebar.detail import build_detail_groups, polyline_render_points, polyline_developed_length_m


def defaults():
    return {"geometry": {"largo_cm": 750, "ancho_cm": 1159.6, "alto_cm": 150, "esviaje_grados": 0},
            "cover": {"inferior_cm": 7.5, "superior_cm": 5, "lateral_cm": 5},
            "rules": [asdict(rule) for rule in default_zapata_rules()]}


def number(data, key, minimum, maximum):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key}: ingresa un número finito.")
    if not minimum <= value <= maximum:
        raise ValueError(f"{key}: fuera del intervalo permitido ({minimum} a {maximum}).")
    return value


def domain(payload):
    g, c = payload.get("geometry", {}), payload.get("cover", {})
    geometry = ZapataGeometry.from_centimetres(
        *(number(g, key, 1, 10000) for key in ("largo_cm", "ancho_cm", "alto_cm")),
        number(g, "esviaje_grados", -89, 89))
    cover = Cover.from_centimetres(*(number(c, key, 0, 1000) for key in ("inferior_cm", "superior_cm", "lateral_cm")))
    supplied = payload.get("rules")
    base = default_zapata_rules()
    if not isinstance(supplied, list) or len(supplied) != len(base):
        raise ValueError("Se requieren los cinco grupos de zapata.")
    rules = []
    for original, values in zip(base, supplied):
        if not isinstance(values, dict) or values.get("key") != original.key:
            raise ValueError("Grupo de armadura desconocido o fuera de orden.")
        if not isinstance(values.get("enabled"), bool):
            raise ValueError("Activo debe ser booleano.")
        mark = values.get('mark', original.mark)
        if not isinstance(mark, str) or len(mark) > 32:
            raise ValueError('Marca no válida.')
        rules.append(replace(original, mark=mark.strip(), diameter_mm=number(values, "diameter_mm", 12, 36),
            spacing_cm=number(values, "spacing_cm", 1, 1000), hook_cm=number(values, "hook_cm", 0, 1200),
            enabled=values["enabled"], origin=values.get("origin", "inicio")))
    return geometry, cover, rules


def from_project(data):
    output = {}
    for key in ('entrada', 'salida'):
        state = defaults()
        source = data.get('estribos', {})
        for field, original in [('largo_cm', 'largo'), ('ancho_cm', 'ancho'), ('alto_cm', 'espesor')]:
            value = source.get(f'dado_muro_frontal_{original}_{key}')
            state['geometry'][field] = float(value) / 10 if value is not None else None
        state['geometry']['esviaje_grados'] = float(data.get('parametros_generales', {}).get('angulo_esviaje_puente', 0))
        output[key] = state
    return output


def validate_draft(state):
    """Allow unfinished fields in saved work; execution still needs valid numbers."""
    candidate = deepcopy(state)
    base = defaults()
    for group in ('geometry', 'cover'):
        for key, value in base[group].items():
            if candidate[group].get(key) is None:
                candidate[group][key] = value
    for rule, original in zip(candidate['rules'], base['rules']):
        for key in ('diameter_mm', 'spacing_cm', 'hook_cm'):
            if rule.get(key) is None:
                rule[key] = original[key]
    domain(candidate)


def preview(payload):
    geometry, cover, rules = domain(payload)
    schedule = build_zapata_schedule(geometry, cover, rules)
    details = []
    if schedule.is_valid:
        for group in build_detail_groups(schedule, rules, geometry):
            for piece in group.pieces:
                details.append({**asdict(piece), "points_m": polyline_render_points(piece),
                                "measured_cm": polyline_developed_length_m(piece) * 100})
    return {"valid": schedule.is_valid, "issues": [asdict(issue) for issue in schedule.issues],
            "marks": [{**asdict(mark), "kg": mark.kg_steel, 'area_cm2': mark.area_m2 * 10000,
                       'spacing_cm': next(rule.spacing_cm for rule in rules if rule.key == mark.key)} for mark in schedule.marks],
            "total_kg": schedule.total_kg, "details": details}
