"""The angle selects actual longitudinal steel direction, not a CAD stretch."""
from collections import defaultdict
from dataclasses import replace
import math

import pytest

from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import (
    Cover, ZapataGeometry, bend_radius_cm, default_zapata_rules, lap_length_cm,
)
from sincal.rebar.plan import footing_mesh_axes, mesh_y_parallel_to_skew


def inputs(skew, origin="inicio", mixed=False, length=750):
    geometry = ZapataGeometry.from_centimetres(length, 1159.6, 150, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    diameters = {"mesh_x": 22, "mesh_y": 16, "suple": 12,
                 "lateral_x": 12, "lateral_y": 18}
    rules = tuple(replace(rule, origin=origin, enabled=True,
                          diameter_mm=diameters[rule.key] if mixed else rule.diameter_mm)
                  for rule in default_zapata_rules())
    return geometry, cover, rules


@pytest.mark.parametrize("angle,parallel", ((0, True), (-9, True), (9, True),
                                           (-9.99999, True), (9.99999, True),
                                           (-10, False), (10, False), (-12, False), (12, False)))
def test_orientation_uses_absolute_unrounded_angle(angle, parallel):
    assert mesh_y_parallel_to_skew(angle) is parallel


@pytest.mark.parametrize("skew", (-9, 9))
@pytest.mark.parametrize("origin", ("inicio", "final"))
@pytest.mark.parametrize("mixed", (False, True))
def test_parallel_meshes_have_constant_real_lengths_bends_and_cover(skew, origin, mixed):
    geometry, cover, rules = inputs(skew, origin, mixed)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    angle = math.radians(skew)
    direction = (math.sin(angle), math.cos(angle), 0)
    by_key = defaultdict(list)
    for bar in assembly.bars:
        by_key[bar.key].append(bar)
        if bar.key not in ("mesh_y", "suple"):
            continue
        assert bar.axis_u == pytest.approx(direction)
        assert bar.axis_v == (0, 0, 1 if bar.level == "superior" else -1)
        assert bar.piece_role == "completa"
        assert bar.bend_radius_cm == pytest.approx(3 * bar.diameter_mm / 10)
        for first, last, bulge in zip(bar.vertices_m, bar.vertices_m[1:], bar.bulges):
            if abs(bulge) < 1e-12:
                continue
            sweep = abs(4 * math.atan(bulge))
            assert sweep == pytest.approx(math.pi / 2)
            assert math.dist(first, last) / (2 * math.sin(sweep / 2)) == pytest.approx(
                3 * bar.diameter_mm / 1000)
        axis_cover = cover.lateral_m + bar.diameter_mm / 2000
        for x, y, z in bar.points_m:
            assert geometry.largo_m / 2 - abs(y) >= axis_cover - 1e-8
            distance_side = (geometry.ancho_m / 2 - abs(x - math.tan(angle) * y)) * math.cos(angle)
            assert distance_side >= axis_cover - 1e-8
            assert z >= cover.inferior_m + bar.diameter_mm / 2000 - 1e-8
            assert geometry.alto_m - z >= cover.superior_m + bar.diameter_mm / 2000 - 1e-8
    for key in ("mesh_y", "suple"):
        assert len({round(bar.developed_length_cm, 7) for bar in by_key[key]}) == 1
        mark = next(mark for mark in assembly.schedule.marks if mark.key == key)
        assert not mark.length_variants
        assert mark.quantity == len(by_key[key])
        assert mark.total_length_cm == sum(bar.length_cm for bar in by_key[key])
        assert "oblicua" in mark.projection_notes["AA"]
        assert "longitud real" in mark.projection_notes["BB"]
        assert "longitud real" in mark.projection_notes["CC"]


@pytest.mark.parametrize("skew", (-9, 9))
@pytest.mark.parametrize("origin", ("inicio", "final"))
def test_parallel_grid_covers_both_sides_and_meets_real_tangencies(skew, origin):
    geometry, cover, rules = inputs(skew, origin, True)
    mx, my, _, lx, ly = rules
    insets = (ly.diameter_mm / 1000, lx.diameter_mm / 1000)
    xaxes = footing_mesh_axes(geometry, cover, mx, my, side_insets_m=insets)
    yaxes = footing_mesh_axes(geometry, cover, my, mx, side_insets_m=insets)
    angle = math.radians(skew)
    slope, cosine = math.tan(angle), math.cos(angle)
    rx = bend_radius_cm(mx.diameter_mm) / 100
    ry = bend_radius_cm(my.diameter_mm) / 100
    central = min(xaxes, key=lambda axis: abs(axis.coordinate_m))
    # FR intersects the physical inclined steel at both horizontal tangencies.
    at_fr = lambda axis: axis.coordinate_m + slope * central.coordinate_m
    assert at_fr(yaxes[0]) == pytest.approx(central.start_m[0] + rx)
    assert at_fr(yaxes[-1]) == pytest.approx(central.end_m[0] - rx)
    # The first/last X also meet Y's real, projected bend tangencies.
    assert xaxes[0].coordinate_m == pytest.approx(yaxes[0].start_m[1] + ry * cosine)
    assert xaxes[-1].coordinate_m == pytest.approx(yaxes[0].end_m[1] - ry * cosine)
    for axis in yaxes:
        for x, y in (axis.start_m, axis.end_m):
            assert x - slope * y == pytest.approx(axis.coordinate_m)
        assert axis.length_m == pytest.approx(
            (geometry.largo_m - 2 * (cover.lateral_m + my.diameter_mm / 2000 + insets[1])) / cosine)
    # @ remains the transverse intercept pitch; only the closing residue varies.
    for axes, rule in ((xaxes, mx), (yaxes, my)):
        gaps = [right.coordinate_m - left.coordinate_m for left, right in zip(axes, axes[1:])]
        assert max(gaps) == pytest.approx(rule.spacing_cm / 100)
        assert max(gaps) <= rule.spacing_cm / 100 + 1e-9
        assert len({round(axis.coordinate_m, 8) for axis in axes}) == len(axes)
    for first, last in zip(yaxes, yaxes[1:]):
        assert (last.coordinate_m - first.coordinate_m) * cosine >= my.diameter_mm / 1000 - 1e-9
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    xbar = min((bar for bar in assembly.bars if bar.key == "mesh_x" and bar.level == "superior"),
               key=lambda bar: abs(bar.coordinate_m))
    ybar = next(bar for bar in assembly.bars if bar.key == "mesh_y" and bar.level == "superior")
    assert xbar.main_start_m[2] - ybar.main_start_m[2] == pytest.approx(
        (mx.diameter_mm + my.diameter_mm) / 2000)


@pytest.mark.parametrize("skew", (-10, 10, -12, 12))
def test_larger_angles_keep_perpendicular_wedges_and_variable_marks(skew):
    geometry, cover, rules = inputs(skew)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    for key in ("mesh_y", "suple"):
        bars = [bar for bar in assembly.bars if bar.key == key]
        assert all(bar.axis_u == (0, 1, 0) for bar in bars)
        mark = next(mark for mark in assembly.schedule.marks if mark.key == key)
        assert len(mark.length_variants) > 1
        assert "oblicua" in mark.projection_notes["BB"]


@pytest.mark.parametrize("skew", (-9, 9))
@pytest.mark.parametrize("first_length", (0, 900))
def test_constant_longitudinal_mesh_can_use_defined_splices(skew, first_length):
    geometry, cover, original_rules = inputs(skew, length=1500)
    rules = tuple(replace(rule, continuation_mark="8", terminal_mark="9", first_piece_cm=first_length)
                  if rule.key == "mesh_y" else replace(rule, enabled=rule.key == "mesh_x")
                  for rule in original_rules)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    runs = defaultdict(list)
    for bar in assembly.bars:
        if bar.key == "mesh_y":
            runs[bar.placement_id].append(bar)
    assert runs
    for first, last in runs.values():
        assert first.piece_role == "inicial" and last.piece_role == "terminal"
        assert first.developed_length_cm == pytest.approx(first_length or 1200)
        assert first.length_cm <= 1200 and last.length_cm <= 1200
        assert first.axis_u == last.axis_u
        delta = tuple(a-b for a,b in zip(first.main_end_m,last.main_start_m))
        overlap = sum(value*direction for value,direction in zip(delta,first.axis_u))
        assert overlap*100 == pytest.approx(lap_length_cm(first.diameter_mm))
        assert math.hypot(*(value-overlap*direction for value,direction in zip(delta,first.axis_u))) == pytest.approx(
            (first.diameter_mm+last.diameter_mm)/2000)
        assert math.dist(*last.lap_segments_m[0]) * 100 == pytest.approx(lap_length_cm(first.diameter_mm))
    marks = [mark for mark in assembly.schedule.marks if mark.key == "mesh_y"]
    assert {mark.mark for mark in marks} == {"3", "8"}
    assert all(not mark.length_variants for mark in marks)


def test_parallel_mesh_rejects_missing_continuation_instead_of_inventing_one():
    geometry, cover, rules = inputs(9, length=1500)
    rules = tuple(replace(rule, enabled=rule.key in ("mesh_x", "mesh_y")) for rule in rules)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert not assembly.is_valid
    assert any("no tiene marca de continuación" in issue.message for issue in assembly.schedule.issues)
    assert not any("serie variable" in issue.message for issue in assembly.schedule.issues)
