"""B/C drafting conventions cannot become fabricated steel or quantities."""
from collections import Counter
from copy import deepcopy
import math
import re
from unittest.mock import patch

import pytest

from sincal.cad.moldajes import MoldajeCandidate
from sincal.cad.rebar_marks import build_marks_support
from sincal.cad.zapata_detail import build_zapata_detail_lisp
from sincal.cad.zapata_views import (
    build_zapata_lisp, footing_drawing_projection, project_footing_assembly,
)
from sincal.rebar.assembly import build_footing_assembly
from sincal.web.abutment_scene_rebar import build_footing_bars
from sincal.web.rebar import defaults, domain, preview


def case(skew):
    state = defaults()
    state["geometry"]["esviaje_grados"] = skew
    state["rules"][2]["enabled"] = True
    return state


def reference(geometry):
    width = geometry.largo_m / math.cos(math.radians(geometry.esviaje_grados))
    x, y, height = 13.25, -12.75, geometry.alto_m
    return MoldajeCandidate("Zapata", "REFERENCE", "OK", 4, width * height,
                           ((x, y), (x + width, y), (x + width, y + height), (x, y + height)))


def physical_snapshot(state):
    geometry, cover, rules = domain(state)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    return {
        "assembly": assembly,
        "scene": build_footing_bars(state),
        "web": preview(state),
        "detail_source": build_zapata_detail_lisp(assembly.schedule, rules, geometry, "entrada", ""),
        "other_views": {view: footing_drawing_projection(assembly, view) for view in ("FR", "AA", "FF")},
    }


def assert_physical_y_quantities(snapshot, skew):
    assembly, scene, web = snapshot["assembly"], snapshot["scene"], snapshot["web"]
    assert scene["valid"], scene["issues"]
    assert web["valid"], web["issues"]
    for family in ("mesh_y", "suple"):
        bars = [bar for bar in assembly.bars if bar.key == family]
        scene_bars = [bar for bar in scene["bars"] if bar["key"] == family]
        mark = next(mark for mark in web["marks"] if mark["key"] == family)
        counts = Counter(bar.length_cm for bar in bars)
        assert mark["quantity"] == len(bars) == len(scene_bars)
        assert mark["total_length_cm"] == sum(bar.length_cm for bar in bars)
        assert mark["kg"] == pytest.approx(mark["total_length_cm"] / 100 * math.pi * (mark["diameter_mm"] / 2000) ** 2 * 7850)
        assert {bar.id: bar.signature for bar in bars} == {bar["id"]: bar["signature"] for bar in scene_bars}
        if abs(skew) >= 10:
            assert len(counts) > 1
            assert {item["length_cm"]: item["quantity"] for item in mark["length_variants"]} == counts
            assert mark["total_length_cm"] < mark["quantity"] * mark["unit_length_cm"]
            # These physical perpendicular bars keep both hooks at one X,
            # regardless of the full-width longitudinal convention in B/C.
            for bar in bars:
                assert bar.vertices_m[0][0] == pytest.approx(bar.vertices_m[-1][0])
        else:
            assert len(counts) == 1 and not mark["length_variants"]


@pytest.mark.parametrize("skew", [-9, 9, -10, 10, -12, 12])
@pytest.mark.parametrize("view", ["BB", "CC"])
def test_bc_source_generation_preserves_assembly_table_details_scene_and_other_views(skew, view):
    state = case(skew)
    initial_state = deepcopy(state)
    geometry, cover, rules = domain(state)
    before = physical_snapshot(state)
    assembly = before["assembly"]
    original = deepcopy(assembly)
    assert_physical_y_quantities(before, skew)
    for units in (1, 1000):
        # Also return the exact already-built object to catch a CAD adapter
        # mutating its argument instead of merely creating presentation data.
        with patch("sincal.cad.zapata_views.build_footing_assembly", return_value=assembly):
            source = build_zapata_lisp(view, reference(geometry), geometry, cover, rules, "entrada",
                                       drawing_units_per_m=units)
        support = build_marks_support(original.schedule, rules, "entrada", drawing_units_per_m=units)
        assert support in source
        assert f"ENTRADA_{view}_ZAP" in source
        assert assembly == original
        assert state == initial_state
    after = physical_snapshot(state)
    assert after == before
    assert_physical_y_quantities(after, skew)


@pytest.mark.parametrize("skew", [-9, 9, -10, 10, -12, 12])
def test_bc_generation_respects_a_deleted_representative_and_never_recreates_it(skew):
    state = case(skew)
    whole = build_footing_assembly(*domain(state))
    chosen = min((bar for bar in whole.bars if bar.key == "mesh_y" and bar.level == "superior"),
                 key=lambda bar: abs(bar.coordinate_m))
    record = {"id": chosen.id, "signature": chosen.signature}
    state["rules"][1]["removed_pieces"] = [record]
    original_state = deepcopy(state)
    geometry, cover, rules = domain(state)
    before = physical_snapshot(state)
    assembly = before["assembly"]
    assert chosen.id not in {bar.id for bar in assembly.bars}
    assert chosen in assembly.reference_bars
    for view in ("BB", "CC"):
        source = build_zapata_lisp(view, reference(geometry), geometry, cover, rules, "entrada")
        assert build_marks_support(assembly.schedule, rules, "entrada") in source
        drawing = footing_drawing_projection(assembly, view, geometry=geometry, cover=cover)
        assert chosen.id not in {piece.source_id for piece in drawing}
        # Do not promote a different top Y bar to conceal the deliberate gap.
        assert not any(piece.key == "mesh_y" and piece.level == "superior" for piece in drawing)
        assert chosen.id not in {piece.source_id for piece in project_footing_assembly(assembly, view)}
    after = physical_snapshot(state)
    assert after == before
    assert state == original_state
    assert state["rules"][1]["removed_pieces"] == [record]
    assert after["scene"]["removed_bars"][0]["status"] == "removed"
    assert {bar.id: bar.signature for bar in after["assembly"].bars} == {
        bar.id: bar.signature for bar in whole.bars if bar.id != chosen.id}
    old = next(mark for mark in whole.schedule.marks if mark.mark == chosen.mark)
    new = next(mark for mark in after["assembly"].schedule.marks if mark.mark == chosen.mark)
    assert new.quantity == old.quantity - 1
    assert new.total_length_cm == old.total_length_cm - chosen.length_cm
    assert_physical_y_quantities(after, skew)


@pytest.mark.parametrize("skew", [-9, 9, -10, 10, -12, 12])
@pytest.mark.parametrize("view", ["BB", "CC"])
def test_conventional_bc_representative_reaches_covered_sides_with_true_hooks_and_radii(skew, view):
    state = case(skew)
    geometry, cover, rules = domain(state)
    assembly = build_footing_assembly(geometry, cover, rules)
    physical = project_footing_assembly(assembly, view)
    shown = footing_drawing_projection(assembly, view, geometry=geometry, cover=cover)
    y_lines = [piece for piece in shown if piece.key in ("mesh_y", "suple")]
    assert {(piece.key, piece.level) for piece in y_lines} == {
        ("mesh_y", "superior"), ("mesh_y", "inferior"), ("suple", "superior")}
    assert len(y_lines) == 3
    assert all(piece.kind == "polyline" for piece in y_lines)
    other_identities = lambda pieces: Counter((piece.source_id, piece.key, piece.level, piece.mark, piece.kind)
                                             for piece in pieces if piece.key not in ("mesh_y", "suple"))
    assert other_identities(shown) == other_identities(physical)
    by_id = {bar.id: bar for bar in assembly.bars}
    lateral_diameter_m = next(rule.diameter_mm / 1000 for rule in rules if rule.key == "lateral_x")
    for piece in y_lines:
        source = by_id[piece.source_id]
        assert piece.mark == source.mark and piece.diameter_mm == source.diameter_mm
        # Mirroring the lower bar's plane reverses the arc's signed bulge.
        # Checking only the radius magnitude misses hooks curling outward.
        assert piece.bulges == pytest.approx(tuple(value * source.axis_v[2] for value in source.bulges))
        rule = next(rule for rule in rules if rule.key == piece.key)
        cosine = math.cos(math.radians(skew))
        half_span = (geometry.largo_m / 2 - cover.lateral_m - rule.diameter_mm / 2000 - lateral_diameter_m) / cosine
        assert min(x for x, _ in piece.vertices_m) == pytest.approx(-half_span)
        assert max(x for x, _ in piece.vertices_m) == pytest.approx(half_span)
        # A drafting-only wider straight must not scale either hook or radius.
        assert math.dist(piece.vertices_m[0], piece.vertices_m[1]) == pytest.approx(
            math.dist(source.vertices_m[0], source.vertices_m[1]))
        assert math.dist(piece.vertices_m[-2], piece.vertices_m[-1]) == pytest.approx(
            math.dist(source.vertices_m[-2], source.vertices_m[-1]))
        arcs = 0
        for first, last, bulge in zip(piece.vertices_m, piece.vertices_m[1:], piece.bulges):
            if abs(bulge) < 1e-10:
                continue
            sweep = 4 * math.atan(abs(bulge))
            assert sweep == pytest.approx(math.pi / 2)
            assert math.dist(first, last) / (2 * math.sin(sweep / 2)) == pytest.approx(3 * rule.diameter_mm / 1000)
            arcs += 1
        assert arcs == 2
    if abs(skew) >= 10:
        assert all(piece.kind == "circle" for piece in physical if piece.key in ("mesh_y", "suple"))
    assert any(piece.key == "mesh_x" and piece.kind == "circle" for piece in shown)
    assert_physical_y_quantities(physical_snapshot(state), skew)


@pytest.mark.parametrize("skew", [-9, 9, -10, 10, -12, 12])
@pytest.mark.parametrize("view", ["BB", "CC"])
def test_bc_source_uses_contextual_drawing_geometry_and_keeps_native_table(skew, view):
    state = case(skew)
    geometry, cover, rules = domain(state)
    assembly = build_footing_assembly(geometry, cover, rules)
    candidate = reference(geometry)
    projected = footing_drawing_projection(assembly, view, geometry=geometry, cover=cover)
    expected = [piece for piece in projected if piece.kind == "polyline"]
    centre_x = (min(x for x, _ in candidate.vertices) + max(x for x, _ in candidate.vertices)) / 2
    bottom_y = min(y for _, y in candidate.vertices)
    for units in (1, 1000):
        source = build_zapata_lisp(view, candidate, geometry, cover, rules, "entrada", drawing_units_per_m=units)
        commands = [line for line in source.splitlines() if '(cons 0 "LWPOLYLINE")' in line]
        assert len(commands) == len(expected)
        for command, piece in zip(commands, expected):
            emitted = [tuple(map(float, point)) for point in re.findall(
                r'\(cons 10 \(list (-?[\d.]+) (-?[\d.]+)\)\)', command)]
            assert len(emitted) == len(piece.vertices_m)
            for actual, point in zip(emitted, piece.vertices_m):
                assert actual == pytest.approx(((point[0] + centre_x) * units, (point[1] + bottom_y) * units), abs=1e-8)
        assert build_marks_support(assembly.schedule, rules, "entrada", drawing_units_per_m=units) in source
