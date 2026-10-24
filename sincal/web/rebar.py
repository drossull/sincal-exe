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
                    "calculation_available": element.key == "abutment.footing",
                    "views": list(dict.fromkeys(
                        "EE" if element.key == "abutment.footing" and item.view == "FF" else item.view
                        for item in element.layers)),
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


def reference_sequence(data, instance_key, view, *, geometry=None):
    """Select two corners for rectangles and three for a skewed footing plan."""
    from sincal.rebar.model import VISTAS_ZAPATA
    view = "FF" if view == "EE" else view
    if view not in VISTAS_ZAPATA:
        raise ValueError("Selecciona una vista de zapata válida.")
    resolve_assistant_element(data, "abutment", instance_key, "abutment.footing")
    elements = BRIDGE_REBAR_CATALOG.elements_for("abutment")
    order = ("abutment.footing", "abutment.pile")
    ordered = sorted(elements, key=lambda item: order.index(item.key) if item.key in order else 2)
    orientation = data.get("estribos", {}).get(f"orientacion_dado_estribo_{instance_key}", "rectangular")
    skew = (geometry.esviaje_grados if geometry is not None else
            float(data.get("parametros_generales", {}).get("angulo_esviaje_puente", 0)))
    skewed_plan = view == "FF" and orientation == "romboide" and abs(skew) > 1e-9
    return [{"key": item.key, "label": item.label,
             "reference_mode": "parallelogram" if skewed_plan and item.key == "abutment.footing" else "rectangle"}
            for item in ordered
            if item.presence.resolve(data, instance_key)
            and any(layer.view == view for layer in item.layers)]


def drawing_units_per_m(expected, choice="auto"):
    """Never infer units from dimensions or silently relabel a millimetre DWG."""
    declared = (expected or {}).get("active", {}).get("insunits")
    declared_scales = {4: 1000.0, 5: 100.0, 6: 1.0}
    choices = {"mm": 1000.0, "cm": 100.0, "m": 1.0}
    if not isinstance(choice, str):
        raise ValueError("Unidad de dibujo no válida; elige mm, cm o m.")
    if choice == "auto":
        if declared not in declared_scales:
            raise ValueError("El dibujo no declara una unidad compatible. Elige mm, cm o m antes de enviar la vista.")
        return declared_scales[declared]
    if choice not in choices:
        raise ValueError("Unidad de dibujo no válida; elige mm, cm o m.")
    # An explicit choice interprets the coordinates, never changes INSUNITS.
    # Some Proyecto Puentes exports declare metres but contain millimetres.
    return choices[choice]


def reference_candidate(vertices, factor, context, geometry, project, *, reference_mode="rectangle"):
    """Validate a measured reference; never infer a skewed plan from its box.

    Parallelogram vertices are upper-left, upper-right, lower-right, lower-left.
    The three selected corners determine the fourth before this validation.
    The current drawing recipe requires the upper edge to remain horizontal.
    """
    from sincal.cad.moldajes import MoldajeCandidate
    if reference_mode not in ("rectangle", "parallelogram"):
        raise ValueError("Tipo de referencia de zapata no válido.")
    if (isinstance(factor, bool) or not isinstance(factor, (int, float))
            or not math.isfinite(factor) or factor <= 0):
        raise ValueError("La unidad de la referencia no es válida.")
    try:
        raw_points = tuple(tuple(float(v) for v in p) for p in vertices)
    except (TypeError, ValueError) as error:
        raise ValueError("La referencia de zapata no es válida.") from error
    if (len(raw_points) != 4 or any(len(p) not in (2, 3) for p in raw_points)
            or not all(math.isfinite(v) for p in raw_points for v in p)):
        raise ValueError("La referencia de zapata debe contener cuatro vértices válidos.")
    if any(len(p) == 3 and abs(p[2] / factor) > 1e-7 for p in raw_points):
        raise ValueError("La referencia de zapata debe estar en el plano XY con Z = 0.")
    points = tuple((p[0] / factor, p[1] / factor) for p in raw_points)
    orientation = project.get("estribos", {}).get(
        f"orientacion_dado_estribo_{context.instance}", "rectangular")
    if context.view == "FF" and orientation not in ("rectangular", "romboide"):
        raise ValueError("El JSON debe indicar si la zapata en planta es rectangular o romboide.")
    if reference_mode == "parallelogram":
        if context.view != "FF":
            raise ValueError("La referencia de tres esquinas corresponde a la planta de zapata.")
        if orientation != "romboide":
            raise ValueError("La referencia es romboide, pero el JSON define una zapata rectangular.")
        p1, p2, p3, p4 = points
        upper = (p2[0] - p1[0], p2[1] - p1[1])
        base = math.hypot(*upper)
        if base <= 1e-7:
            raise ValueError("Las dos esquinas superiores de la zapata no pueden coincidir.")
        closing = (p1[0] + p3[0] - p2[0], p1[1] + p3[1] - p2[1])
        if math.dist(p4, closing) > 1e-7:
            raise ValueError("Los vértices no forman el paralelogramo definido por las tres esquinas.")
        unit = (upper[0] / base, upper[1] / base)
        down = (p3[0] - p2[0], p3[1] - p2[1])
        depth = down[0] * unit[1] - down[1] * unit[0]
        if depth <= 1e-7:
            raise ValueError("Selecciona las esquinas consecutivas: superior izquierda, superior derecha e inferior derecha.")
        # delta is the upper edge's signed horizontal displacement from the
        # lower edge. Its sign must agree with the JSON's skew convention.
        delta = -(down[0] * unit[0] + down[1] * unit[1])
        measured_skew = math.degrees(math.atan2(delta, depth))
        wanted_delta = geometry.largo_m * math.tan(math.radians(geometry.esviaje_grados))
        measurements = ((base, geometry.ancho_m), (depth, geometry.largo_m),
                        (delta, wanted_delta))
        if any(abs(actual - wanted) > max(0.01, abs(wanted) * 0.005)
               for actual, wanted in measurements):
            raise ValueError(
                f"La planta seleccionada tiene base {base:.3f} m, profundidad perpendicular "
                f"{depth:.3f} m y esviaje {measured_skew:.3f}°, pero el cálculo requiere "
                f"{geometry.ancho_m:.3f} m, {geometry.largo_m:.3f} m y "
                f"{geometry.esviaje_grados:.3f}°. Revisa los puntos, la unidad o el JSON. "
                "No se insertaron armaduras.")
        if upper[0] <= 0 or abs(upper[1]) > 1e-7:
            raise ValueError(
                "La planta está girada. Esta versión requiere la base superior horizontal, "
                "de izquierda a derecha; no se deformaron ni insertaron armaduras.")
        contour = (p4, p3, p2, p1)
        return MoldajeCandidate("", "", "OK", 4, base * depth,
                                contour, True, False, (), context)
    if (context.view == "FF" and orientation == "romboide"
            and abs(geometry.esviaje_grados) > 1e-9):
        raise ValueError("La planta esviada requiere tres esquinas consecutivas; no puede definirse por dos puntos de un rectángulo.")
    minx, maxx = min(p[0] for p in points), max(p[0] for p in points)
    miny, maxy = min(p[1] for p in points), max(p[1] for p in points)
    width, height = maxx - minx, maxy - miny
    delta = 0.0
    if context.view == "FR":
        wanted_width, wanted_height = geometry.ancho_m, geometry.alto_m
    elif context.view in ("AA", "BB", "CC"):
        wanted_width, wanted_height = geometry.largo_m, geometry.alto_m
    elif context.view == "FF":
        if orientation == "romboide":
            delta = geometry.largo_m * math.tan(math.radians(geometry.esviaje_grados))
        wanted_width, wanted_height = geometry.ancho_m + abs(delta), geometry.largo_m
    else:
        raise ValueError("Vista de referencia no válida.")
    if any(abs(actual - wanted) > max(0.01, wanted * 0.005)
           for actual, wanted in ((width, wanted_width), (height, wanted_height))):
        raise ValueError(
            f"El rectángulo mide {width:.3f} × {height:.3f} m, pero el cálculo de {context.view} "
            f"requiere {wanted_width:.3f} × {wanted_height:.3f} m. "
            "Revisa la unidad elegida, los puntos o las dimensiones del cálculo. No se insertaron armaduras.")
    # Anchor the exact calculated dimensions at the selected lower-left corner.
    startx = minx + max(0.0, -delta)
    base = wanted_width - abs(delta)
    contour = ((startx, miny), (startx + base, miny),
               (startx + base + delta, miny + wanted_height),
               (startx + delta, miny + wanted_height))
    return MoldajeCandidate("", "", "OK", 4, base * wanted_height,
                            contour, True, False, (), context)


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
