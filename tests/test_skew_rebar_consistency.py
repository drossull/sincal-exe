"""Independent geometry-to-quantity regressions; no running CAD is required."""
from collections import Counter
from copy import deepcopy
import math
import re

import pytest

from sincal.cad.moldajes import MoldajeCandidate
from sincal.cad.rebar_marks import build_marks_support
from sincal.cad.zapata_views import build_zapata_lisp, project_footing_assembly
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.detail import build_detail_groups
from sincal.rebar.model import build_zapata_schedule
from sincal.web.abutment_scene_rebar import build_footing_bars
from sincal.web.rebar import defaults, domain, preview


def state_for(skew, origin="inicio"):
    # Same footing dimensions as the Aconcagua example, with explicit rules.
    state = defaults()
    state["geometry"]["esviaje_grados"] = skew
    state["rules"][1]["origin"] = origin
    return state


def unrotate(point, degrees):
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = point
    return c*x+s*y, -s*x+c*y, z


def y_axes(state):
    result = build_footing_bars(state)
    assert result["valid"], result["issues"]
    return [bar for bar in result["bars"] if bar["key"] == "mesh_y"]


def full_y_chord(bar, skew):
    """Recover plan corners from physical tangent points and the radius 3Ø."""
    a, b = (unrotate(bar[key], skew) for key in ("main_start", "main_end"))
    radius = 3 * bar["diameter_mm"] / 1000
    first, last = (a[0], a[1]-radius, a[2]), (b[0], b[1]+radius, b[2])
    # A U's vertical hooks have those same plan positions. This independently
    # catches a drift between claimed tangencies and the rendered full shape.
    assert unrotate(bar["vertices"][0], skew)[:2] == pytest.approx(first[:2], abs=1e-8)
    assert unrotate(bar["vertices"][-1], skew)[:2] == pytest.approx(last[:2], abs=1e-8)
    return first, last


def physical_developed_cm(bar):
    total = 0.0
    for a, b, bulge in zip(bar["vertices"], bar["vertices"][1:], bar["bulges"]):
        chord = math.dist(a, b)
        if abs(bulge) < 1e-10:
            total += chord
        else:
            sweep = 4 * math.atan(abs(bulge))
            radius = chord / (2 * math.sin(sweep/2))
            assert radius == pytest.approx(3*bar["diameter_mm"]/1000)
            assert math.degrees(sweep) == pytest.approx(90)
            total += radius*sweep
    return total*100


@pytest.mark.parametrize("skew", [-30, -12, 12, 30])
@pytest.mark.parametrize("origin", ["inicio", "final"])
def test_skew_mesh_covers_both_wedges_and_preserves_real_cover(skew, origin):
    state = state_for(skew, origin)
    before = deepcopy(state)
    axes = y_axes(state)
    geometry, cover, rules = domain(state)
    rule = next(rule for rule in rules if rule.key == "mesh_y")
    width, length = geometry.ancho_m, geometry.largo_m
    tangent = math.tan(math.radians(skew))
    axis_cover = cover.lateral_m + rule.diameter_mm/2000
    # Independent support function of the offset parallelogram. This does not
    # call the plan generator or its inward-offset helper.
    support = width/2 - axis_cover*math.sqrt(1+tangent*tangent)
    support += (length/2-axis_cover)*abs(tangent)
    x_positions = []
    for bar in axes:
        a, b = full_y_chord(bar, skew)
        assert a[0] == pytest.approx(b[0], abs=1e-9)
        assert a[1] < b[1]
        for x, y, z in (unrotate(point, skew) for point in bar["points"]):
            distance_to_end = length/2-abs(y)
            distance_to_side = (width/2-abs(x-y*tangent))/math.sqrt(1+tangent*tangent)
            assert distance_to_end >= axis_cover-1e-9
            assert distance_to_side >= axis_cover-1e-9
            assert z >= cover.inferior_m + rule.diameter_mm/2000 - 1e-9
            assert z <= geometry.alto_m-cover.superior_m-rule.diameter_mm/2000+1e-9
        if bar["level"] == "superior":
            x_positions.append(a[0])
    x_positions.sort()
    assert x_positions[0] < -width/2
    assert x_positions[-1] > width/2
    assert x_positions[0] - (-support) <= rule.spacing_cm/100+1e-9
    assert support - x_positions[-1] <= rule.spacing_cm/100+1e-9
    assert max(b-a for a, b in zip(x_positions, x_positions[1:])) <= rule.spacing_cm/100+1e-9
    assert state == before


@pytest.mark.parametrize("skew", [-30, -12, 12, 30])
def test_same_mark_totals_match_every_drawn_variable_length(skew):
    state = state_for(skew)
    geometry, cover, rules = domain(state)
    schedule = build_zapata_schedule(geometry, cover, rules)
    assert schedule.is_valid, schedule.issues
    family = [mark for mark in schedule.marks if mark.key == "mesh_y"]
    assert len(family) == 1
    mark = family[0]
    assert mark.mark == "3"
    axes = y_axes(state)
    assert len(axes) == mark.quantity
    assert Counter(bar["level"] for bar in axes) == {
        "superior": mark.quantity//2, "inferior": mark.quantity//2,
    }
    assert all(bar["marks"] == ["3"] for bar in axes)
    rule = next(rule for rule in rules if rule.key == "mesh_y")
    radius_cm = 3*rule.diameter_mm/10
    hook_cm = rule.hook_cm or max(100, math.ceil((geometry.alto_m*100*.5)/10)*10)
    expected = Counter()
    for bar in axes:
        chord_cm = math.dist(*full_y_chord(bar, skew))*100
        # Developed U: straight chord less both tangency radii, two straight
        # hooks, and two quarter circles. No constant/max-length multiplication.
        developed = chord_cm-2*radius_cm+2*hook_cm+math.pi*radius_cm
        assert physical_developed_cm(bar) == pytest.approx(developed, abs=1e-7)
        assert bar["developed_length_cm"] == pytest.approx(developed, abs=1e-7)
        assert bar["length_cm"] == math.ceil(developed-1e-9)
        expected[float(math.ceil(developed-1e-9))] += 1
    actual = {variant.length_cm: variant.quantity for variant in mark.length_variants}
    assert len(actual) > 2
    assert actual == expected
    assert sum(actual.values()) == mark.quantity
    total_cm = sum(length*count for length, count in expected.items())
    assert mark.total_length_cm == pytest.approx(total_cm)
    assert mark.total_length_cm < mark.unit_length_cm*mark.quantity
    expected_kg = total_cm/100 * math.pi*(mark.diameter_mm/2000)**2 * 7850
    assert mark.kg_steel == pytest.approx(expected_kg)
    payload = preview(state)
    web_mark = next(value for value in payload["marks"] if value["key"] == "mesh_y")
    assert list(web_mark["length_variants"]) == [
        {"length_cm": item.length_cm, "quantity": item.quantity}
        for item in mark.length_variants
    ]
    assert web_mark["kg"] == pytest.approx(expected_kg)


def test_variable_series_uses_one_table_row_and_one_detail_without_false_laps():
    state = state_for(-12)
    geometry, cover, rules = domain(state)
    schedule = build_zapata_schedule(geometry, cover, rules)
    mark = next(mark for mark in schedule.marks if mark.key == "mesh_y")
    support = build_marks_support(schedule, rules, "entrada")
    table_payload = support.split("(defun srb:fail", 1)[0]
    assert table_payload.count('"footing:mesh_y:base"') == 1
    assert table_payload.count(f'"3" {mark.quantity} 22 20)') == 1
    assert '(srb:copy-table-template)' in support
    group = next(group for group in build_detail_groups(schedule, rules, geometry) if group.group_id == "G3")
    assert len(group.pieces) == 1
    assert group.pieces[0].mark == "3"
    assert group.pieces[0].quantity == mark.quantity
    assert group.pieces[0].length_variants == mark.length_variants
    assert group.laps_m == ()


@pytest.mark.parametrize("skew", [-30, -12, 12, 30])
@pytest.mark.parametrize("units", [1, 100, 1000])
def test_ee_translation_does_not_change_axes_or_table_quantities(skew, units):
    state = state_for(skew)
    geometry, cover, rules = domain(state)
    tangent = math.tan(math.radians(skew))
    width, length = geometry.ancho_m, geometry.largo_m
    tx, ty = 123.25, -42.75
    vertices = tuple((tx+x+y*tangent, ty+y) for x, y in (
        (-width/2, -length/2), (width/2, -length/2),
        (width/2, length/2), (-width/2, length/2),
    ))
    candidate = MoldajeCandidate("EE_ZAP", "REFERENCE", "OK", 4, width*length, vertices)
    source = build_zapata_lisp("FF", candidate, geometry, cover, rules, "entrada", drawing_units_per_m=units)
    emitted = []
    for line in source.splitlines():
        if '(cons 0 "LWPOLYLINE")' not in line or '(cons 8 "fi22")' not in line:
            continue
        points = [tuple(map(float, point)) for point in re.findall(
            r'\(cons 10 \(list (-?[\d.]+) (-?[\d.]+)\)\)', line)]
        if len(points) == 2 and abs(points[0][0]-points[1][0]) < 1e-8:
            emitted.append(tuple((x/units-tx, y/units-ty) for x, y in points))
    expected = []
    for bar in y_axes(state):
        if bar["level"] == "superior":
            expected.append(tuple(point[:2] for point in full_y_chord(bar, skew)))
    assert len(emitted) == len(expected)
    assembly = build_footing_assembly(geometry, cover, rules)
    projected = [p for p in project_footing_assembly(assembly, "FF") if p.key == "mesh_y"]
    assert {p.source_id for p in projected} == {bar["id"] for bar in y_axes(state) if bar["level"] == "superior"}
    assert all(p.mark == "3" and not any(p.bulges) for p in projected)
    emitted.sort(key=lambda pair: pair[0][0])
    expected.sort(key=lambda pair: pair[0][0])
    for cad, iso in zip(emitted, expected):
        for cad_point, iso_point in zip(cad, iso):
            assert cad_point == pytest.approx(iso_point, abs=1e-8)
    mark = next(mark for mark in build_zapata_schedule(geometry, cover, rules).marks if mark.key == "mesh_y")
    table_payload = source.split("(defun srb:fail", 1)[0]
    assert table_payload.count(f'"3" {mark.quantity} 22 20)') == 1


@pytest.mark.parametrize("skew", [-12, 12])
def test_enabled_suple_keeps_own_mark_and_upper_only_variable_distribution(skew):
    state = state_for(skew)
    state["rules"][2]["enabled"] = True
    geometry, cover, rules = domain(state)
    schedule = build_zapata_schedule(geometry, cover, rules)
    mark = next(mark for mark in schedule.marks if mark.key == "suple")
    assert mark.mark == "3A" and len(mark.length_variants) > 1
    bars = [bar for bar in build_footing_bars(state)["bars"] if bar["key"] == "suple"]
    assert len(bars) == mark.quantity
    assert {bar["level"] for bar in bars} == {"superior"}
    assert all(bar["marks"] == ["3A"] for bar in bars)
    assert sum(item.quantity for item in mark.length_variants) == len(bars)
    assert mark.total_length_cm == sum(item.quantity*item.length_cm for item in mark.length_variants)
    rule = next(rule for rule in rules if rule.key == "suple")
    minimum_chord = 2*3*rule.diameter_mm/1000
    assert min(math.dist(*full_y_chord(bar, skew)) for bar in bars) >= minimum_chord-1e-9
    for bar in bars:
        assert bar["length_cm"] == math.ceil(physical_developed_cm(bar)-1e-9)
    xs = sorted(unrotate(bar["points"][0], skew)[0] for bar in bars)
    assert len(xs) == len(set(round(x, 8) for x in xs))
    assert max(b-a for a, b in zip(xs, xs[1:])) <= rule.spacing_cm/100+1e-9
    assert xs[0] < -geometry.ancho_m/2 and xs[-1] > geometry.ancho_m/2
    group = next(group for group in build_detail_groups(schedule, rules, geometry) if group.group_id == "G3A")
    assert len(group.pieces) == 1 and group.pieces[0].mark == "3A"
    assert group.pieces[0].length_variants == mark.length_variants
    assert group.laps_m == ()


def test_zero_skew_keeps_the_existing_rectangular_mesh_and_uniform_mark():
    state = state_for(0)
    geometry, cover, rules = domain(state)
    schedule = build_zapata_schedule(geometry, cover, rules)
    mark = next(mark for mark in schedule.marks if mark.key == "mesh_y")
    axes = y_axes(state)
    assert len(axes) == mark.quantity == 116
    assert mark.length_variants == ()
    assert mark.total_length_cm == mark.quantity*mark.unit_length_cm
    upper = sorted((bar for bar in axes if bar["level"] == "superior"), key=lambda bar:bar["points"][0][0])
    mx, my, _, lx, ly = rules
    # Exterior lateral diameter, mesh axis radius, then its bend radius.
    tangent = cover.lateral_m + ly.diameter_mm/1000 + 3.5*mx.diameter_mm/1000
    assert upper[0]["points"][0][0] == pytest.approx(-geometry.ancho_m/2+tangent)
    assert upper[-1]["points"][0][0] == pytest.approx(geometry.ancho_m/2-tangent)
    chord = geometry.largo_m-2*(cover.lateral_m+lx.diameter_mm/1000+my.diameter_mm/2000)
    assert {round(math.dist(*full_y_chord(bar, 0)), 6) for bar in upper} == {round(chord,6)}
    for bar in upper:
        assert physical_developed_cm(bar) == pytest.approx(chord*100 - 2*6.6 + 200 + math.pi*6.6)
