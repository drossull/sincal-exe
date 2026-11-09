"""Quantities and fabrication details from the surviving bars of one wing.

This adapter does not distribute, regenerate or filter steel. The caller has
already validated and applied any ``removed_pieces`` against the physical bars.
Each bar counts once, regardless of how many drawing views show its mark.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
import math
import re

from .model import (DIAMETROS_DISPONIBLES_MM, RebarLengthVariant, RebarMark,
                    ValidationIssue, ZapataSchedule)


_GROUPS = (r"(?:(?:inner_)?(?:vertical_main|vertical_extension|vertical_supplement|horizontal_main|horizontal_upper)"
           r"|inner_supplement_front|inner_supplement_back|edge)")
_KEY = re.compile(rf"wing_(left|right)_({_GROUPS})")
_IDENTITY = re.compile(rf"wing:(left|right):({_GROUPS}):[0-9]{{1,6}}")
_MARK = re.compile(r"[0-9]+[A-Z]*", re.IGNORECASE | re.ASCII)


def _positive_number(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value > 0)


def summarize_wing_bars(bars, rules, side):
    """Return ``{schedule: ZapataSchedule, details: tuple[DetailPiece, ...]}``.

    ``side`` is ``left`` or ``right``. Rule and bar keys follow
    ``wing_<side>_<group>``; IDs are ``wing:<side>:<group>:<index>``.
    An ``inner_`` group prefix selects the interior mesh; legacy group names
    keep the exterior mesh. Marks are unique across both sets of families.
    Each current family has one mark for complete pieces with fixed hooks and
    at most one variable straight partial. Supplements retain one lower hook.
    Invalid associations return an empty, invalid schedule rather than silently
    combining incompatible pieces. Empty survivors are a valid empty schedule.
    """
    if side not in ("left", "right"):
        raise ValueError("El lado del ala debe ser 'left' o 'right'.")
    bars, rules = tuple(bars), tuple(rules)
    issues, by_key, marks_seen = [], {}, {}

    def error(message):
        issues.append(ValidationIssue("error", message))

    for rule in rules:
        key = getattr(rule, "key", None)
        match = _KEY.fullmatch(key) if isinstance(key, str) else None
        if not match or match[1] != side:
            error(f"La familia '{key}' no corresponde al ala {side}.")
            continue
        if key in by_key:
            error(f"La familia '{key}' está repetida.")
            continue
        by_key[key] = rule
        mark = getattr(rule, "mark", None)
        if not isinstance(mark, str) or not _MARK.fullmatch(mark):
            error(f"Marca inválida para la familia '{key}'.")
        elif mark.upper() in marks_seen:
            error(f"Marca duplicada '{mark}': cada familia del ala requiere su propia marca.")
        else:
            marks_seen[mark.upper()] = key
        if not isinstance(getattr(rule, "label", None), str) or not rule.label.strip():
            error(f"La familia '{key}' necesita un rótulo.")
        diameter, spacing = getattr(rule, "diameter_mm", None), getattr(rule, "spacing_cm", None)
        if not _positive_number(diameter) or diameter not in DIAMETROS_DISPONIBLES_MM:
            error(f"Diámetro inválido para la familia '{key}'.")
        if not _positive_number(spacing):
            error(f"Separación inválida para la familia '{key}'.")
        if getattr(rule, "continuation_mark", ""):
            error(f"La familia '{key}' aún no tiene reparto de empalmes definido.")

    grouped, seen_ids = defaultdict(list), set()
    for bar in bars:
        identity = _IDENTITY.fullmatch(bar.id)
        if not identity or identity[1] != side or bar.key != f"wing_{side}_{identity[2]}":
            error(f"El fierro '{bar.id}' no corresponde a su ala y familia.")
            continue
        if bar.id in seen_ids:
            error(f"El fierro '{bar.id}' figura más de una vez.")
            continue
        seen_ids.add(bar.id)
        rule = by_key.get(bar.key)
        if rule is None:
            error(f"El fierro '{bar.id}' no tiene una regla de su familia.")
            continue
        if (not isinstance(rule.mark, str) or bar.mark.upper() != rule.mark.upper()
                or bar.diameter_mm != rule.diameter_mm or bar.spacing_cm != rule.spacing_cm
                or bar.piece_role != "completa"):
            error(f"El fierro '{bar.id}' no coincide con la marca, diámetro o separación de su familia.")
            continue
        grouped[(bar.key, rule.mark)].append(bar)

    variable_indexes, partial_ranges = {}, {}
    for (key, mark), pieces in grouped.items():
        first = pieces[0]
        if any(not math.isclose(bar.hook_start_cm, first.hook_start_cm, abs_tol=1e-9, rel_tol=0)
               or not math.isclose(bar.hook_end_cm, first.hook_end_cm, abs_tol=1e-9, rel_tol=0)
               for bar in pieces[1:]):
            error(f"La marca '{mark}' de '{key}' mezcla ganchos diferentes; sólo su tramo central puede ser variable.")
        if any(len(bar.detail.partials_cm) != len(first.detail.partials_cm)
               or len(bar.detail.bulges) != len(first.detail.bulges)
               or any(not math.isclose(a, b, abs_tol=1e-9, rel_tol=0)
                      for a, b in zip(bar.detail.bulges, first.detail.bulges))
               for bar in pieces[1:]):
            error(f"La marca '{mark}' mezcla formas o ángulos de doblez incompatibles.")
            continue
        changed_partials = [index for index, values in enumerate(zip(*(bar.detail.partials_cm for bar in pieces)))
                            if len(set(values)) > 1]
        fixed_edge = (key.endswith('_edge') and len({bar.length_cm for bar in pieces}) == 1
                      and max(bar.developed_length_cm for bar in pieces)-min(bar.developed_length_cm for bar in pieces) < 1e-7)
        if fixed_edge and changed_partials:
            partial_ranges[key] = [{'min_cm': min(values), 'max_cm': max(values)}
                                   for values in zip(*(bar.detail.partials_cm for bar in pieces))]
        elif len(changed_partials) > 1:
            error(f"La marca '{mark}' tiene más de una parcial variable; falta definir su despiece.")
        elif len({bar.length_cm for bar in pieces}) > 1:
            if len(changed_partials) != 1:
                error(f"No se identifica la parcial variable de la marca '{mark}'.")
            else:
                variable_indexes[(key, mark)] = changed_partials[0]
    if issues:
        return {"schedule": ZapataSchedule((), tuple(issues)), "details": (), "detail_partial_ranges": {}}

    element = "Ala izquierda" if side == "left" else "Ala derecha"
    views = ("BB", "DD", "EE") if side == "left" else ("CC", "DD", "EE")
    marks, details = [], []
    for rule in rules:
        pieces = grouped.get((rule.key, rule.mark), ())
        if not pieces:
            continue
        longest = max(pieces, key=lambda bar: (bar.length_cm, bar.developed_length_cm, bar.id))
        counts = Counter(bar.length_cm for bar in pieces)
        variants = (tuple(RebarLengthVariant(length, count) for length, count in sorted(counts.items()))
                    if len(counts) > 1 else ())
        detail = replace(longest.detail, mark=rule.mark, quantity=len(pieces),
                         length_variants=variants,
                         variable_partial_index=variable_indexes.get((rule.key, rule.mark)) if variants else None)
        # Preserve the representative's exact local geometry and nominal cut.
        # Variable totals below always sum the individual manufactured pieces.
        raw = tuple(segment[0] for segment in detail.partial_segments_m) + (detail.partial_segments_m[-1][1],)
        hook_count = sum(length > 0 for length in (longest.hook_start_cm, longest.hook_end_cm))
        shape = {"vertices_m": detail.vertices_m, "bulges": detail.bulges, "raw_m": raw,
                 "main_start_x_m": detail.main_start_x_m, "main_end_x_m": detail.main_end_x_m,
                 "developed_length_cm": detail.developed_length_cm,
                 "cut_length_cm": detail.total_cm, "partials_cm": detail.partials_cm, "hook_count": hook_count}
        mesh_label = "interior" if rule.key.startswith(f"wing_{side}_inner_") else "exterior"
        view_note = 'armadura de canto' if rule.key.endswith('_edge') else f'armadura {mesh_label}'
        marks.append(RebarMark(
            rule.key, rule.mark, element, rule.label, rule.diameter_mm, len(pieces),
            longest.length_cm, sum(bar.length_cm for bar in pieces), views,
            {view: view_note for view in views}, hook_count=hook_count,
            bend_radius_cm=longest.bend_radius_cm, piece_role="completa",
            length_variants=variants, shape_data=shape))
        details.append(detail)
    return {"schedule": ZapataSchedule(tuple(marks), ()), "details": tuple(details),
            "detail_partial_ranges": partial_ranges}
