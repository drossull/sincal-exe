"""Y follows the lateral face below ten degrees; every CAD view cuts that steel."""
from copy import deepcopy
from dataclasses import replace
import math

import pytest

from sincal.cad.moldajes import MoldajeContext
from sincal.cad.zapata_views import (build_zapata_lisp, footing_drawing_projection,
                                     project_footing_assembly)
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import Cover, RemovedPiece, ZapataGeometry, default_zapata_rules
from sincal.web.rebar import reference_candidate


def case(skew):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 200, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    rules = tuple(replace(rule, enabled=True) for rule in default_zapata_rules())
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    return geometry, cover, rules, assembly


def station(assembly, key):
    return min((bar for bar in assembly.reference_bars
                if bar.key == key and bar.level == "superior"),
               key=lambda bar: abs(bar.coordinate_m)).coordinate_m


@pytest.mark.parametrize("skew", (-9, 9))
@pytest.mark.parametrize("view", ("FR", "AA"))
def test_perpendicular_views_intersect_inclined_y_at_its_real_position(view, skew):
    _, _, _, assembly = case(skew)
    original = deepcopy(assembly)
    projected = project_footing_assembly(assembly, view)
    plane_axis = 1 if view == "FR" else 0
    plane = station(assembly, "mesh_x" if view == "FR" else "mesh_y")
    shift = math.tan(math.radians(skew))*plane if view == "FR" else 0
    expected = []
    for bar in assembly.bars:
        if bar.key != "mesh_y":
            continue
        a, b = bar.main_start_m, bar.main_end_m
        assert abs(b[0]-a[0]) > .01  # Real inclined steel, not an orthogonal fixture.
        t = (plane-a[plane_axis])/(b[plane_axis]-a[plane_axis])
        if not 0 <= t <= 1:
            continue
        point = tuple(first+t*(last-first) for first, last in zip(a, b))
        wanted = (point[0 if view == "FR" else 1]-shift, point[2])
        assert any(piece.source_id == bar.id and piece.kind == "circle"
                   and piece.vertices_m[0] == pytest.approx(wanted) for piece in projected)
        expected.append(bar.id)
    assert expected
    assert not any(piece.key == "mesh_y" and piece.kind == "polyline" for piece in projected)
    if view == "AA":
        # There is no longitudinal Y line in this perpendicular plane. Do not
        # move its isolated intersections to an invented U-shaped projection.
        assert footing_drawing_projection(assembly, view) == projected
    assert assembly == original


@pytest.mark.parametrize("skew", (-9, 9))
@pytest.mark.parametrize("view", ("BB", "CC"))
def test_side_views_preserve_full_parallel_y_hooks_radii_and_developed_lengths(view, skew):
    _, _, _, assembly = case(skew)
    sine, cosine = math.sin(math.radians(skew)), math.cos(math.radians(skew))
    intercept = station(assembly, "mesh_y")
    pieces = project_footing_assembly(assembly, view)
    by_id = {bar.id: bar for bar in assembly.bars}
    longitudinal = [piece for piece in pieces if piece.key == "mesh_y"]
    assert longitudinal and all(piece.kind == "polyline" for piece in longitudinal)
    assert {piece.source_id for piece in longitudinal} == {
        bar.id for bar in assembly.bars if bar.key == "mesh_y"
        and math.isclose(bar.coordinate_m, intercept, abs_tol=1e-9)}
    for piece in longitudinal:
        bar = by_id[piece.source_id]
        assert len(piece.vertices_m) == len(bar.vertices_m)
        for actual, (x, y, z) in zip(piece.vertices_m, bar.vertices_m):
            assert actual == pytest.approx((sine*x+cosine*y-intercept*sine, z))
        developed = 0
        radii = []
        for first, last, bulge in zip(piece.vertices_m, piece.vertices_m[1:], piece.bulges):
            chord = math.dist(first, last)
            if abs(bulge) < 1e-12:
                developed += chord
            else:
                angle = 4*math.atan(abs(bulge))
                radius = chord/(2*math.sin(angle/2))
                radii.append(radius)
                developed += radius*angle
        assert radii
        assert radii == pytest.approx([3*bar.diameter_mm/1000]*len(radii))
        assert developed*100 == pytest.approx(bar.developed_length_cm)
    assert any(piece.key == "mesh_x" and piece.kind == "circle" for piece in pieces)


@pytest.mark.parametrize("skew", (-9, 9))
@pytest.mark.parametrize("view", ("FR", "BB", "CC"))
def test_thin_line_contact_only_changes_circle_presentation_where_line_exists(view, skew):
    _, _, _, assembly = case(skew)
    physical = project_footing_assembly(assembly, view)
    drawing = footing_drawing_projection(assembly, view)
    line_key, cross_key = ("mesh_x", "mesh_y") if view == "FR" else ("mesh_y", "mesh_x")
    heights = {piece.level: first[1] for piece in physical
               if piece.key == line_key and piece.kind == "polyline"
               for first, last, bulge in zip(piece.vertices_m, piece.vertices_m[1:], piece.bulges)
               if abs(bulge) < 1e-12 and abs(first[1]-last[1]) < 1e-10}
    assert heights
    # FR's complete representative can additionally include the contacting
    # continuation beside the exact plane; compare surviving physical hits by
    # identity, not their position in the drawing sequence.
    after_by_source = {}
    for piece in drawing:
        after_by_source.setdefault((piece.source_id,piece.kind),[]).append(piece)
    for before in physical:
        after = after_by_source[(before.source_id,before.kind)].pop(0)
        if before.kind == "polyline":
            assert before == after
        elif before.key == cross_key:
            assert after.vertices_m[0][0] == before.vertices_m[0][0]
            assert abs(after.vertices_m[0][1]-heights[after.level]) == pytest.approx(after.diameter_mm/2000)


@pytest.mark.parametrize("skew", (-9, 9))
@pytest.mark.parametrize("view", ("FR", "AA", "BB", "CC", "FF"))
def test_removing_a_reference_run_never_changes_station_or_substitutes_neighbour(view, skew):
    geometry, cover, rules, assembly = case(skew)
    key = "mesh_x" if view in ("FR", "FF") else "mesh_y"
    chosen = min((bar for bar in assembly.bars if bar.key == key and bar.level == "superior"),
                 key=lambda bar: abs(bar.coordinate_m))
    removed = [bar for bar in assembly.bars if bar.placement_id == chosen.placement_id]
    ids = {bar.id for bar in removed}
    rules = tuple(replace(rule, removed_pieces=tuple(RemovedPiece(bar.id, bar.signature) for bar in removed))
                  if rule.key == key else rule for rule in rules)
    after = build_footing_assembly(geometry, cover, rules)
    assert after.is_valid
    for projector in (project_footing_assembly, footing_drawing_projection):
        assert projector(after, view) == tuple(piece for piece in projector(assembly, view)
                                             if piece.source_id not in ids)


@pytest.mark.parametrize("view", ("BB", "CC"))
@pytest.mark.parametrize("skew", (-9, 9))
def test_small_skew_side_reference_uses_l_over_cos_without_scaling_steel(view, skew):
    geometry, cover, rules, assembly = case(skew)
    width = geometry.largo_m/math.cos(math.radians(skew))
    candidate = reference_candidate(((0, 2), (width, 2), (width, 0), (0, 0)), 1,
                                    MoldajeContext("abutment.footing", "entrada", view), geometry, {})
    assert candidate.area_m2 == pytest.approx(width*2)
    before = deepcopy(assembly)
    lisp = build_zapata_lisp(view, candidate, geometry, cover, rules, "entrada")
    assert '(cons 42 ' in lisp
    assert assembly == before
    with pytest.raises(ValueError, match=f"cálculo de {view}"):
        reference_candidate(((0, 2), (geometry.largo_m, 2), (geometry.largo_m, 0), (0, 0)), 1,
                            MoldajeContext("abutment.footing", "entrada", view), geometry, {})


@pytest.mark.parametrize("skew", (-10, 10))
def test_ten_degree_direction_switch_retains_perpendicular_y_in_aa(skew):
    _, _, _, assembly = case(skew)
    assert any(piece.key == "mesh_y" and piece.kind == "polyline"
               for piece in project_footing_assembly(assembly, "AA"))
    assert not any(piece.key == "mesh_y" and piece.kind == "polyline"
                   for piece in project_footing_assembly(assembly, "BB"))
