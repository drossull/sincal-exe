"""B/C follow the skewed lateral face without changing manufactured bars."""
from copy import deepcopy
from dataclasses import replace
import math

import pytest

from sincal.cad.zapata_views import project_footing_assembly, footing_drawing_projection
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import Cover, ZapataGeometry, default_zapata_rules


def case(skew):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 200, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    rules = tuple(replace(rule, enabled=True) for rule in default_zapata_rules())
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    return geometry, cover, assembly


@pytest.mark.parametrize("view", ("BB", "CC"))
@pytest.mark.parametrize("skew", (-30, -12, 12, 30))
def test_skew_cut_intersects_actual_meshes_in_the_side_parallel_plane(view, skew):
    geometry, cover, assembly = case(skew)
    original = deepcopy(assembly)
    angle = math.radians(skew)
    sine, cosine = math.sin(angle), math.cos(angle)
    station_x = min((bar.coordinate_m for bar in assembly.bars if bar.key == "mesh_y"), key=abs)
    station = station_x * cosine
    origin = station_x * sine
    projected = project_footing_assembly(assembly, view)
    circles = [p for p in projected if p.kind == "circle"]
    assert {p.key for p in circles} >= {"mesh_x", "mesh_y", "suple"}
    # Each main straight-piece intersection is checked independently of the
    # production arc/segment intersection helper. Hooks may add more hits.
    expected_main_count = 0
    for bar in assembly.bars:
        a, b = bar.main_start_m, bar.main_end_m
        qa, qb = cosine * a[0] - sine * a[1], cosine * b[0] - sine * b[1]
        if abs(qb - qa) < 1e-10:
            continue
        t = (station - qa) / (qb - qa)
        if not 0 <= t <= 1:
            continue
        point = tuple(a[i] + t * (b[i] - a[i]) for i in range(3))
        expected = (sine * point[0] + cosine * point[1] - origin, point[2])
        matching = [p for p in circles if p.source_id == bar.id]
        assert any(p.vertices_m[0] == pytest.approx(expected) for p in matching)
        assert expected[0] == pytest.approx(point[1] / cosine)
        expected_main_count += 1
    assert expected_main_count > 20
    by_id = {bar.id: bar for bar in assembly.bars}
    for piece in projected:
        source = by_id[piece.source_id]
        assert piece.diameter_mm == source.diameter_mm
        assert piece.mark == source.mark
        for s, z in piece.vertices_m:
            # The concrete interval is L/cos(theta); steel remains covered.
            assert abs(s) <= geometry.largo_m / (2 * cosine) - cover.lateral_m
            assert cover.inferior_m <= z <= geometry.alto_m - cover.superior_m
    assert not any(p.kind == "polyline" and p.key in ("mesh_y", "suple") for p in projected)
    assert footing_drawing_projection(assembly, view) == projected
    assert assembly == original


@pytest.mark.parametrize("view", ("BB", "CC"))
def test_zero_skew_preserves_existing_aa_representation(view):
    _, _, assembly = case(0)
    assert project_footing_assembly(assembly, view) == project_footing_assembly(assembly, "AA")
    assert footing_drawing_projection(assembly, view) == footing_drawing_projection(assembly, "AA")
