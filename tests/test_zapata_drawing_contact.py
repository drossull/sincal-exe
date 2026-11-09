"""CAD thin-line contact is a presentation convention, not a physical move."""
from copy import deepcopy
from dataclasses import replace
import math
import re

import pytest

from sincal.cad.moldajes import MoldajeCandidate
from sincal.cad.zapata_views import (
    build_zapata_lisp, footing_drawing_projection, project_footing_assembly,
)
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import Cover, RemovedPiece, ZapataGeometry, default_zapata_rules


def footing(skew=0, origin="inicio"):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    diameters = {"mesh_x": 22, "mesh_y": 16, "suple": 12,
                 "lateral_x": 12, "lateral_y": 18}
    rules = tuple(replace(rule, diameter_mm=diameters[rule.key],
                          origin=origin, enabled=True)
                  for rule in default_zapata_rules())
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    return geometry, cover, rules, assembly


@pytest.mark.parametrize("view", ("FR", "AA", "BB", "CC"))
@pytest.mark.parametrize("skew,origin", ((0, "inicio"), (0, "final"),
                                        (-12, "inicio"), (12, "final")))
def test_sections_touch_thin_lines_without_changing_physical_bars(view, skew, origin):
    _, _, _, assembly = footing(skew, origin)
    original = deepcopy(assembly)
    physical = project_footing_assembly(assembly, view)
    drawing = footing_drawing_projection(assembly, view)
    source = {bar.id: bar for bar in assembly.bars}
    assert [piece.source_id for piece in drawing] == [piece.source_id for piece in physical]
    assert len(drawing) == len(physical)
    if view in ("BB", "CC") and skew:
        # The oblique cut intersects both meshes. There is no longitudinal Y
        # line in this plane to which its circles may be artificially snapped.
        assert drawing == physical
        assert assembly == original
        return

    line_key = "mesh_x" if view == "FR" else "mesh_y"
    mesh_key = "mesh_y" if view == "FR" else "mesh_x"
    line_bars = [source[piece.source_id] for piece in physical
                 if piece.kind == "polyline" and piece.key == line_key]
    heights = {bar.level: bar.main_start_m[2] for bar in line_bars}
    # Read straight vertical legs from the unchanged drawing of the main bar.
    leg_positions = {a[0] for piece in physical
                     if piece.kind == "polyline" and piece.key == line_key
                     for a, b, bulge in zip(piece.vertices_m, piece.vertices_m[1:], piece.bulges)
                     if abs(bulge) < 1e-10 and abs(a[0] - b[0]) < 1e-10
                     and abs(a[1] - b[1]) > 1e-10}
    assert leg_positions
    mesh_shifts = {}
    for before, after in zip(physical, drawing):
        # Geometry of the actual line, hooks, arcs and lap pieces is untouched.
        if before.kind == "polyline":
            assert after == before
            continue
        assert replace(after, vertices_m=before.vertices_m) == before
        x, z = after.vertices_m[0]
        old_x, old_z = before.vertices_m[0]
        radius = after.diameter_mm / 2000
        if after.key == mesh_key:
            height = heights[after.level]
            assert abs(z - height) == pytest.approx(radius)
            assert (z - height) * (old_z - height) > 0
            assert x == old_x
            mesh_shifts[after.level] = z - old_z
        elif after.key.startswith("lateral"):
            leg = min(leg_positions, key=lambda value: abs(value - old_x))
            assert abs(x - leg) == pytest.approx(radius)
            assert (x - leg) * (old_x - leg) > 0
            assert z == old_z

    if view == "FR":
        suples = [(before, after) for before, after in zip(physical, drawing)
                  if before.key == "suple"]
        assert suples
        for before, after in suples:
            assert after.vertices_m[0][0] == before.vertices_m[0][0]
            assert after.vertices_m[0][1] - before.vertices_m[0][1] == pytest.approx(
                mesh_shifts["superior"])
            mesh_z = next(piece.vertices_m[0][1] for piece in drawing
                          if piece.key == mesh_key and piece.level == "superior")
            # The suple remains a distinct layer below Y, never collapsed onto X.
            assert mesh_z - after.vertices_m[0][1] == pytest.approx((16 + 12) / 2000)

    assert assembly == original
    assert project_footing_assembly(assembly, view) == physical
    assert footing_drawing_projection(assembly, "FF") == project_footing_assembly(assembly, "FF")


@pytest.mark.parametrize("skew,origin", ((0, "inicio"), (-12, "inicio"), (12, "final")))
def test_removing_upper_y_mesh_does_not_move_surviving_suples(skew, origin):
    geometry, cover, rules, assembly = footing(skew, origin)
    removed = tuple(bar for bar in assembly.bars
                    if bar.key == "mesh_y" and bar.level == "superior")
    removed_ids = {bar.id for bar in removed}
    revised_rules = tuple(
        replace(rule, removed_pieces=tuple(RemovedPiece(bar.id, bar.signature) for bar in removed))
        if rule.key == "mesh_y" else rule for rule in rules)
    revised = build_footing_assembly(geometry, cover, revised_rules)
    assert revised.is_valid, revised.schedule.issues
    prior = footing_drawing_projection(assembly, "FR")
    assert any(piece.key == "suple" for piece in prior)
    assert footing_drawing_projection(revised, "FR") == tuple(
        piece for piece in prior if piece.source_id not in removed_ids)


NUMBER = r"(-?\d+(?:\.\d+)?)"
POINT = re.compile(r"\(list " + NUMBER + " " + NUMBER + r" 0\.0\)")


def points_in(line):
    return [tuple(map(float, pair)) for pair in POINT.findall(line)]


def has_point(points, target):
    return any(point == pytest.approx(target, abs=1e-7) for point in points)


@pytest.mark.parametrize("view", ("FR", "AA"))
@pytest.mark.parametrize("units", (1, 100, 1000))
def test_lisp_circles_dimensions_and_mark_leaders_share_presented_centres(view, units):
    geometry, cover, rules, assembly = footing(-12, "final")
    width = geometry.ancho_m if view == "FR" else geometry.largo_m
    # A nonzero reference origin also checks translation before unit conversion.
    left, bottom = 2.3, 4.7
    candidate = MoldajeCandidate("reference", "REF", "OK", 4, width * geometry.alto_m,
                                 ((left, bottom), (left + width, bottom),
                                  (left + width, bottom + geometry.alto_m),
                                  (left, bottom + geometry.alto_m)))
    drawing = footing_drawing_projection(assembly, view)
    circles = [piece for piece in drawing if piece.kind == "circle"]
    expected = [((piece.vertices_m[0][0] + left + width / 2) * units,
                 (piece.vertices_m[0][1] + bottom) * units) for piece in circles]
    source = build_zapata_lisp(view, candidate, geometry, cover, rules, "entrada",
                              drawing_units_per_m=units)
    circle_lines = [line for line in source.splitlines() if '(cons 0 "CIRCLE")' in line]
    assert len(circle_lines) == len(circles)
    for line, point, piece in zip(circle_lines, expected, circles):
        actual, = points_in(line)
        assert actual == pytest.approx(point, abs=1e-7)
        radius = float(re.search(r"\(cons 40 " + NUMBER + r"\)", line).group(1))
        assert radius == pytest.approx(piece.diameter_mm / 2000 * units)

    dimensions = [line for line in source.splitlines()
                  if line.strip().startswith("(sincal:marked-dim ")]
    assert dimensions
    for line in dimensions:
        first, last, _ = points_in(line)
        assert has_point(expected, first) and has_point(expected, last)
        assert math.dist(first, last) > 0
        assert first[0] == pytest.approx(last[0]) or first[1] == pytest.approx(last[1])

    points_by_mark = {}
    for piece, point in zip(circles, expected):
        points_by_mark.setdefault(piece.mark, []).append(point)
    leaders = [line for line in source.splitlines()
               if line.strip().startswith("(sincal:linked-mark ")]
    matched = set()
    for line in leaders:
        mark = re.findall(r'"([^\"]*)"', line)[0]
        if mark in points_by_mark:
            assert has_point(points_by_mark[mark], points_in(line)[0])
            matched.add(mark)
    assert matched == set(points_by_mark)
