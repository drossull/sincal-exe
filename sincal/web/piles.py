"""Editable pile configuration and zone preview; no reinforcement fabrication."""
from collections.abc import Mapping
from copy import deepcopy
import math

from sincal.rebar.model import bend_radius_cm


ZONE_KEYS = ("lower", "middle", "upper")
ZONE_LABELS = {"lower": "inferior", "middle": "medio", "upper": "superior"}
FIELDS = {
    "geometry": ("diameter_cm", "length_cm", "footing_height_cm"),
    "cover": ("lateral_cm", "inferior_cm"),
    "longitudinal": ("diameter_mm", "spacing_cm", "hook_cm"),
    "ties": ("diameter_mm", "hook_90_cm", "hook_45_cm", "overrun_cm"),
}
LABELS = {
    "geometry.diameter_cm": "Diámetro del pilote",
    "geometry.length_cm": "Largo del pilote",
    "geometry.footing_height_cm": "Espesor de la zapata",
    "cover.lateral_cm": "Recubrimiento lateral",
    "cover.inferior_cm": "Recubrimiento inferior",
    "longitudinal.diameter_mm": "Diámetro longitudinal",
    "longitudinal.spacing_cm": "Separación longitudinal sobre la circunferencia",
    "longitudinal.hook_cm": "Pata recta del gancho inferior",
    "ties.diameter_mm": "Diámetro del estribo circular",
    "ties.hook_90_cm": "Pata recta del gancho de 90° del estribo",
    "ties.hook_45_cm": "Pata recta del gancho de 45° del estribo",
    "ties.overrun_cm": "Extensión después de la vuelta completa",
    "confinement_cm": "Penetración dentro de la zapata",
}


def defaults():
    """Hook lengths start editable; other unknown engineering inputs stay empty."""
    state = {
        **{group: dict.fromkeys(fields) for group, fields in FIELDS.items()},
        "confinement_cm": None,
        "zones": [{"key": key, "from_cm": None, "to_cm": None, "spacing_cm": None}
                  for key in ZONE_KEYS],
    }
    state["longitudinal"]["hook_cm"] = 40.
    state["ties"].update(hook_90_cm=15., hook_45_cm=25.)
    return state


def _draft_number(value, field):
    if value is None:
        return
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or abs(value) > 10_000_000):
        raise ValueError(f"{field}: ingresa un número finito o deja el campo vacío.")


def validate_draft(state):
    """Save unfinished or cross-field-invalid edits; reject malformed payloads."""
    if not isinstance(state, Mapping):
        raise ValueError("La configuración del pilote debe ser un objeto.")
    if set(state) != {*FIELDS, "confinement_cm", "zones"}:
        raise ValueError("Campos de configuración del pilote no válidos.")
    for group, fields in FIELDS.items():
        values = state[group]
        if not isinstance(values, Mapping) or set(values) != set(fields):
            raise ValueError(f"Campos de {group} del pilote no válidos.")
        for field in fields:
            _draft_number(values[field], f"{group}.{field}")
    _draft_number(state["confinement_cm"], "confinement_cm")
    zones = state["zones"]
    if not isinstance(zones, list) or len(zones) != len(ZONE_KEYS):
        raise ValueError("Define los tres tramos del pilote: inferior, medio y superior.")
    for expected, zone in zip(ZONE_KEYS, zones):
        if (not isinstance(zone, Mapping)
                or set(zone) != {"key", "from_cm", "to_cm", "spacing_cm"}
                or zone["key"] != expected):
            raise ValueError("Los tramos del pilote no tienen el formato u orden esperado.")
        for field in ("from_cm", "to_cm", "spacing_cm"):
            _draft_number(zone[field], f"zones.{expected}.{field}")


def from_project(data, instance_key):
    """Import only known pile geometry keys, whose source units are millimetres."""
    if not isinstance(data, Mapping):
        raise ValueError("El proyecto debe ser un objeto JSON.")
    if instance_key not in ("entrada", "salida"):
        raise ValueError("Selecciona el estribo de entrada o de salida.")
    source = data.get("estribos", {})
    if not isinstance(source, Mapping):
        raise ValueError("El bloque estribos debe ser un objeto JSON.")
    state = defaults()
    for target, source_key in (
        ("diameter_cm", f"pilotes_dado_estribo_{instance_key}_diametro"),
        ("length_cm", f"pilotes_dado_estribo_{instance_key}_largo"),
        ("footing_height_cm", f"dado_muro_frontal_espesor_{instance_key}"),
    ):
        value = source.get(source_key)
        _draft_number(value, source_key)
        if value is not None:
            state["geometry"][target] = value / 10.0
    # Stored geometry is commonly present even when the optional pile is off.
    present = source.get(f"incluir_pilotes_dado_estribo_{instance_key}") is True
    return {"present": present, "state": state}


def preview(state):
    """Preview explicit zones measured upwards from the concrete pile bottom.

    This intentionally returns no steel quantities, cut lengths, marks, or CAD
    geometry. Zone endpoints do not decide whether an extra tie belongs there.
    """
    validate_draft(state)
    issues = []

    def issue(field, message, severity="error"):
        issues.append({"field": field, "message": message, "severity": severity})

    def positive(value, field, *, allow_zero=False):
        label = LABELS.get(field, field)
        if value is None:
            issue(field, f"Completa {label.lower()}.")
            return False
        if value < 0 or (value == 0 and not allow_zero):
            relation = "mayor o igual a cero" if allow_zero else "mayor que cero"
            issue(field, f"{label}: debe ser {relation}.")
            return False
        return True

    usable = {}
    for group, fields in FIELDS.items():
        for field in fields:
            path = f"{group}.{field}"
            usable[path] = positive(state[group][field], path, allow_zero=group == "cover")
    usable["confinement_cm"] = positive(state["confinement_cm"], "confinement_cm", allow_zero=True)
    geometry, cover = state["geometry"], state["cover"]
    if usable["cover.lateral_cm"] and usable["geometry.diameter_cm"]:
        if 2 * cover["lateral_cm"] >= geometry["diameter_cm"]:
            issue("cover.lateral_cm", "El recubrimiento lateral no deja espacio dentro del pilote.")
    if usable["cover.inferior_cm"] and usable["geometry.length_cm"]:
        if cover["inferior_cm"] >= geometry["length_cm"]:
            issue("cover.inferior_cm", "El recubrimiento inferior alcanza o supera el largo del pilote.")
    if usable["confinement_cm"] and usable["geometry.footing_height_cm"]:
        if state["confinement_cm"] > geometry["footing_height_cm"]:
            issue("confinement_cm", "La penetración supera el espesor de la zapata.")

    first_tie_height_cm = None
    if all(usable[field] for field in (
            "cover.inferior_cm", "longitudinal.diameter_mm", "geometry.length_cm")):
        diameter = state["longitudinal"]["diameter_mm"]
        # The first circular tie is at the tangent where the vertical bar
        # begins its bottom 90-degree bend. The straight hook leg is horizontal
        # and does not change this height. Cover is to the bar's outer surface.
        height = cover["inferior_cm"] + diameter / 20.0 + bend_radius_cm(diameter)
        if height >= geometry["length_cm"]:
            issue("first_tie_height_cm", "El inicio del doblez inferior alcanza o supera el largo del pilote.")
        else:
            first_tie_height_cm = height

    top = (geometry["length_cm"] + state["confinement_cm"]
           if usable["geometry.length_cm"] and usable["confinement_cm"] else None)
    candidates = []
    for zone in state["zones"]:
        key = zone["key"]
        # Ignore an old/manual lower-zone start while retaining the saved draft.
        effective = {**zone, "from_cm": first_tie_height_cm} if key == "lower" else zone
        start, end, spacing = (effective[field] for field in ("from_cm", "to_cm", "spacing_cm"))
        complete = True
        for field, value in (("from_cm", start), ("to_cm", end), ("spacing_cm", spacing)):
            if value is None:
                if key == "lower" and field == "from_cm":
                    issue("zones.lower.from_cm", "El inicio del tramo inferior depende del recubrimiento inferior, diámetro longitudinal y largo válidos.")
                else:
                    issue(f"zones.{key}.{field}", f"Completa el tramo {ZONE_LABELS[key]}: falta "
                          + {"from_cm": "inicio", "to_cm": "fin", "spacing_cm": "separación"}[field] + ".")
                complete = False
        if not complete:
            continue
        if start < 0 or end <= start or spacing <= 0:
            issue(f"zones.{key}", f"Tramo {ZONE_LABELS[key]}: usa inicio no negativo, fin mayor al inicio y separación positiva.")
            continue
        if top is None or first_tie_height_cm is None:
            continue
        if start < first_tie_height_cm - 1e-9:
            issue(f"zones.{key}", f"El tramo {ZONE_LABELS[key]} comienza por debajo del primer estribo ({first_tie_height_cm:g} cm desde el fondo).")
            continue
        if end > top + 1e-9:
            issue(f"zones.{key}", f"El tramo {ZONE_LABELS[key]} supera el extremo de la penetración en la zapata ({top:g} cm desde el fondo).")
            continue
        candidates.append(deepcopy(effective))

    excluded = set()
    for index, zone in enumerate(candidates):
        for other in candidates[index + 1:]:
            if min(zone["to_cm"], other["to_cm"]) - max(zone["from_cm"], other["from_cm"]) > 1e-9:
                issue("zones", f"Los tramos {ZONE_LABELS[zone['key']]} y {ZONE_LABELS[other['key']]} se superponen.")
                excluded.update((zone["key"], other["key"]))
            elif zone["from_cm"] > other["from_cm"]:
                issue("zones", "Los tramos inferior, medio y superior deben quedar ordenados desde el fondo hacia arriba.")
                excluded.update((zone["key"], other["key"]))
    zones = [zone for zone in candidates if zone["key"] not in excluded]
    if len(zones) == len(ZONE_KEYS):
        for before, after in zip(zones, zones[1:]):
            if after["from_cm"] > before["to_cm"] + 1e-9:
                issue("zones", f"Hay un tramo sin separación definida entre {before['to_cm']:g} y {after['from_cm']:g} cm desde el fondo.", "warning")
    return {
        "valid": not any(item["severity"] == "error" for item in issues),
        "configuration_only": True,
        "calculation_available": False,
        "message": "Vista previa de configuración. El cálculo, despiece e inserción de pilotes aún no están disponibles.",
        "issues": issues,
        "geometry": deepcopy(geometry),
        "confinement_cm": state["confinement_cm"],
        "first_tie_height_cm": first_tie_height_cm,
        "zones": zones,
    }
