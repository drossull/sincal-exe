"""Physical footing invariants independent of CAD commands and SVG rendering."""
from collections import Counter, defaultdict
from dataclasses import replace
import math

import pytest

from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.detail import build_detail_groups, polyline_developed_length_m
from sincal.rebar.model import Cover, ZapataGeometry, default_zapata_rules, lap_length_cm


def inputs(skew=0, *, width=1159.6, origin="inicio", different_diameters=False, suple=False):
    geometry = ZapataGeometry.from_centimetres(750, width, 150, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    rules = tuple(replace(rule, origin=origin,
                          diameter_mm=16 if different_diameters and rule.key == "mesh_y" else rule.diameter_mm,
                          enabled=True if suple and rule.key == "suple" else rule.enabled)
                  for rule in default_zapata_rules())
    return geometry, cover, rules


def exact_length(bar):
    total = 0
    for first, last, bulge in zip(bar.vertices_m, bar.vertices_m[1:], bar.bulges):
        chord = math.dist(first, last)
        sweep = abs(4 * math.atan(bulge))
        total += chord if not sweep else chord * sweep / (2 * math.sin(sweep / 2))
    return total * 100


@pytest.mark.parametrize("skew", [0, -12, 12, -30, 30])
@pytest.mark.parametrize("origin", ["inicio", "final"])
def test_every_piece_is_counted_once_with_exact_arcs_cuts_and_cover(skew, origin):
    geometry, cover, rules = inputs(skew, origin=origin, different_diameters=True, suple=True)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    assert len({bar.id for bar in assembly.bars}) == len(assembly.bars)
    assert {bar.key for bar in assembly.bars} == {rule.key for rule in rules if rule.enabled}
    by_mark = defaultdict(list)
    slope = math.tan(math.radians(skew))
    for bar in assembly.bars:
        by_mark[bar.mark].append(bar)
        developed = exact_length(bar)
        assert developed == pytest.approx(bar.developed_length_cm, abs=1e-7)
        assert bar.length_cm == math.ceil(developed - 1e-8)
        assert 0 < bar.length_cm <= 1200
        for first, last, bulge in zip(bar.vertices_m, bar.vertices_m[1:], bar.bulges):
            if abs(bulge) < 1e-12:
                continue
            sweep = abs(4 * math.atan(bulge))
            radius = math.dist(first, last) / (2 * math.sin(sweep / 2))
            assert radius == pytest.approx(3 * bar.diameter_mm / 1000, abs=1e-9)
            if bar.key in ("mesh_x", "mesh_y", "suple"):
                assert sweep == pytest.approx(math.pi / 2)
        # Independent half-plane distances to the four actual concrete faces.
        axis_cover = cover.lateral_m + bar.diameter_mm / 2000
        for x, y, z in bar.points_m:
            assert geometry.largo_m / 2 - abs(y) >= axis_cover - 1e-8
            assert (geometry.ancho_m / 2 - abs(x - slope * y)) / math.hypot(1, slope) >= axis_cover - 1e-8
            assert z >= cover.inferior_m + bar.diameter_mm / 2000 - 1e-8
            assert geometry.alto_m - z >= cover.superior_m + bar.diameter_mm / 2000 - 1e-8
    for mark in assembly.schedule.marks:
        bars = by_mark[mark.mark]
        assert len(bars) == mark.quantity
        assert sum(bar.length_cm for bar in bars) == pytest.approx(mark.total_length_cm)
        if mark.length_variants:
            assert Counter(bar.length_cm for bar in bars) == {
                variant.length_cm: variant.quantity for variant in mark.length_variants}


@pytest.mark.parametrize("width", [1159.6, 2300, 3500])
def test_two_three_and_four_piece_runs_keep_real_overlaps_and_commercial_limit(width):
    geometry, cover, rules = inputs(-12, width=width)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    placements = defaultdict(list)
    for bar in assembly.bars:
        placements[bar.placement_id].append(bar)
    found_split = False
    for run in placements.values():
        if len(run) == 1:
            continue
        found_split = True
        assert run[0].piece_role == "inicial"
        assert run[-1].piece_role == "terminal"
        assert all(bar.piece_role == "intermedia" for bar in run[1:-1])
        for first, last in zip(run, run[1:]):
            assert first.axis_u == last.axis_u and first.axis_v == last.axis_v
            overlap = sum((a - b) * direction for a, b, direction in
                          zip(first.main_end_m, last.main_start_m, first.axis_u)) * 100
            assert overlap == pytest.approx(lap_length_cm(first.diameter_mm), abs=1e-7)
            assert last.lap_length_cm == pytest.approx(overlap)
            assert len(last.lap_segments_m) == 1
            assert math.dist(*last.lap_segments_m[0]) * 100 == pytest.approx(overlap)
            assert first.developed_length_cm == pytest.approx(1200)
    assert found_split


@pytest.mark.parametrize("skew", [0, -12, 12])
def test_details_keep_the_exact_representative_piece_from_the_assembly(skew):
    geometry, cover, rules = inputs(skew, suple=True)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    marks = {mark.mark: mark for mark in assembly.schedule.marks}
    for group in build_detail_groups(assembly.schedule, rules, geometry):
        for piece in group.pieces:
            shape = marks[piece.mark].shape_data
            assert piece.vertices_m == shape["vertices_m"]
            assert piece.bulges == shape["bulges"]
            assert piece.partial_segments_m == tuple(zip(shape["raw_m"], shape["raw_m"][1:]))
            assert piece.total_cm == shape["cut_length_cm"]
            assert polyline_developed_length_m(piece) * 100 == pytest.approx(shape["developed_length_cm"])
            assert sum(piece.partials_cm) == piece.total_cm


def test_oversized_hooks_and_undefined_variable_splices_are_not_clipped_or_invented():
    geometry, cover, rules = inputs(-12)
    long_hook = tuple(replace(rule, hook_cm=200) if rule.key == "mesh_x" else rule for rule in rules)
    invalid_hook = build_footing_assembly(geometry, cover, long_hook)
    assert not invalid_hook.is_valid and not invalid_hook.bars
    assert any("recubrimiento" in issue.message for issue in invalid_hook.schedule.issues)
    invalid_splice = build_footing_assembly(replace(geometry, largo_m=15), cover, rules)
    assert not invalid_splice.is_valid and not invalid_splice.bars
    assert any("serie variable" in issue.message for issue in invalid_splice.schedule.issues)


@pytest.mark.parametrize("width", [1010, 1050, 1100])
def test_near_commercial_limit_keeps_the_terminal_hook_whole(width):
    assembly = build_footing_assembly(*inputs(width=width))
    assert assembly.is_valid, assembly.schedule.issues
    run = [bar for bar in assembly.bars if bar.placement_id == "mesh_x:superior:0"]
    assert len(run) == 2
    first, last = run
    assert first.developed_length_cm < 1200
    assert sum((a-b)*u for a,b,u in zip(first.main_end_m,last.main_end_m,first.axis_u)) == pytest.approx(0)
    assert math.dist(first.main_end_m,last.main_end_m) == pytest.approx(first.diameter_mm/1000)
    assert sum((a-b)*u for a,b,u in zip(first.main_end_m,last.main_start_m,first.axis_u))*100 == pytest.approx(150)
    assert math.dist(last.vertices_m[-2], last.vertices_m[-1]) == pytest.approx(1.0)
    assert exact_length(first) == pytest.approx(first.developed_length_cm)
    assert exact_length(last) == pytest.approx(last.developed_length_cm)
