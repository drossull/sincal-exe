"""Web adapter; engineering rules remain in the existing domain model."""
from dataclasses import asdict, replace
from copy import deepcopy
from collections.abc import Mapping
import math

from sincal.rebar.catalog import BRIDGE_REBAR_CATALOG, ContourPolicy
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


def assistant_catalog(data):
    """Serialize the immutable bridge catalog for the web assistant.

    Optional elements are deliberately included even when they are absent from
    the project.  The UI can therefore explain that they do not apply instead
    of silently hiding part of the bridge hierarchy.
    """
    if not isinstance(data, Mapping):
        raise ValueError("El proyecto de armaduras debe ser un objeto JSON.")
    structures = []
    for structure in BRIDGE_REBAR_CATALOG.structures:
        instances = []
        for instance in BRIDGE_REBAR_CATALOG.resolve_instances(structure.key, data):
            elements = []
            for element in BRIDGE_REBAR_CATALOG.elements_for(structure.key):
                elements.append({
                    "key": element.key,
                    "label": element.label,
                    "folder_path": list(element.folder_path),
                    "optional": element.optional,
                    "presence": element.presence.kind.value,
                    "present": element.presence.resolve(data, instance.key),
                    "definition_pending": element.definition_pending,
                    "layers": [{
                        "view": layer.view,
                        "layer": layer.layer,
                        "contour": layer.contour.value,
                        "detail": layer.detail,
                    } for layer in element.layers],
                    "recipes": [recipe.value for recipe in element.recipes],
                })
            instances.append({
                "key": instance.key,
                "label": instance.label,
                "source_index": instance.source_index,
                "elements": elements,
            })
        structures.append({
            "key": structure.key,
            "label": structure.label,
            "folder": structure.folder,
            "instances": instances,
        })
    return {"structures": structures}


def resolve_assistant_element(data, structure_key, instance_key, element_key, *, require_present=True):
    """Resolve one unambiguous catalog context supplied by the web client."""
    if not isinstance(data, Mapping):
        raise ValueError("El proyecto de armaduras debe ser un objeto JSON.")
    if not all(isinstance(value, str) and value.strip()
               for value in (structure_key, instance_key, element_key)):
        raise ValueError("Selecciona una estructura, instancia y elemento válidos.")
    try:
        structure = BRIDGE_REBAR_CATALOG.structure(structure_key)
        element = BRIDGE_REBAR_CATALOG.element(element_key)
    except KeyError as error:
        raise ValueError("El elemento estructural no pertenece al catálogo vigente.") from error
    if element.structure_key != structure.key:
        raise ValueError("El elemento no pertenece a la estructura seleccionada.")
    matches = tuple(
        instance for instance in BRIDGE_REBAR_CATALOG.resolve_instances(structure.key, data)
        if instance.key == instance_key
    )
    if not matches:
        raise ValueError("La instancia no existe en el JSON del proyecto.")
    if len(matches) != 1:
        raise ValueError("La instancia es ambigua en el JSON; usa nombres únicos.")
    present = element.presence.resolve(data, instance_key)
    if require_present and not present:
        raise ValueError("El elemento opcional no está presente en esta instancia.")
    return structure, matches[0], element


def summarize_element_detection(element, detection, *, selection="unknown"):
    """Return a JSON-ready assessment for one explicitly selected element."""
    assignments = {}
    assigned_candidates = {}
    missing_layers = []
    ambiguous_layers = []
    curved_layers = []
    usable_by_layer = {}
    for layer_view in element.layers:
        allow_open = layer_view.contour in (ContourPolicy.OPEN, ContourPolicy.EITHER)
        allow_closed = layer_view.contour in (ContourPolicy.CLOSED, ContourPolicy.EITHER)
        candidates = tuple(
            candidate for candidate in detection.for_layer(layer_view.layer)
            if not (candidate.closed is True and not allow_closed)
            and candidate.is_usable(allow_open=allow_open, allow_arcs=True)
        )
        usable_by_layer[layer_view.layer] = candidates
        if not candidates:
            missing_layers.append(layer_view.layer)
        elif len(candidates) > 1:
            ambiguous_layers.append(layer_view.layer)
        else:
            assignments[layer_view.layer] = candidates[0].handle
            assigned_candidates[layer_view.layer] = candidates[0]
            if candidates[0].has_arcs:
                curved_layers.append(layer_view.layer)

    candidates = []
    for candidate in detection.candidates:
        item = asdict(candidate)
        item["vertices"] = [list(point) for point in candidate.vertices]
        item["bulges"] = list(candidate.bulges)
        item["label"] = candidate.label
        item["usable"] = candidate in usable_by_layer.get(candidate.layer, ())
        candidates.append(item)

    trusted_detection = selection == "ok" and detection.uses_metres
    detection_complete = (
        trusted_detection
        and bool(element.layers)
        and len(assigned_candidates) == len(element.layers)
    )
    generation_ready = (
        detection_complete
        and element.key == "abutment.footing"
        and all(candidate.is_valid for candidate in assigned_candidates.values())
    )
    if not trusted_detection:
        assignments = {}

    if selection == "cancelled":
        message = "Selección cancelada; no se cambió ninguna asignación."
    elif selection != "ok":
        message = "No se pudo confirmar la selección de moldajes en CAD."
    elif not detection.uses_metres:
        message = "Corrige INSUNITS a 6 (metros) antes de generar armaduras."
    elif missing_layers or ambiguous_layers:
        message = "La selección requiere revisión antes de generar armaduras."
    elif curved_layers:
        message = "Moldajes completos; revisa las vistas con arcos antes de generar."
    elif generation_ready:
        message = "La zapata tiene todos sus moldajes cerrados y está lista para generar."
    elif element.key == "abutment.footing" and detection_complete:
        message = "Moldajes completos, pero la zapata requiere contornos cerrados para generar."
    elif detection_complete:
        message = "Moldajes completos; la receta de armadura aún está pendiente de aprobación."
    else:
        message = f"{len(assignments)} vista(s) asignadas al elemento."
    return {
        "message": message,
        "selection": selection,
        "uses_metres": detection.uses_metres,
        "insunits": detection.insunits,
        "candidates": candidates,
        "assignments": assignments,
        "detection_complete": detection_complete,
        "generation_ready": generation_ready,
        "missing_layers": missing_layers,
        "ambiguous_layers": ambiguous_layers,
        "curved_layers": curved_layers,
    }
