"""Physical placement requested for the footing, independent of CAD styling."""
from dataclasses import replace
import math

import pytest

from sincal.cad.zapata_views import project_footing_assembly
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import Cover, ZapataGeometry, default_zapata_rules


SKEWS = (0, -12, 12, -30, 30)


def assembly_case(skew=0, *, origin="inicio", mixed_diameters=False,
                  lateral_x=True, lateral_y=True):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    diameters = {"mesh_x": 22, "mesh_y": 16, "lateral_x": 12, "lateral_y": 18}
    enabled = {"lateral_x": lateral_x, "lateral_y": lateral_y}
    rules = tuple(replace(rule, origin=origin,
                          diameter_mm=diameters.get(rule.key, rule.diameter_mm)
                          if mixed_diameters else rule.diameter_mm,
                          enabled=enabled.get(rule.key, rule.enabled))
                  for rule in default_zapata_rules())
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    return geometry, cover, {rule.key: rule for rule in rules}, assembly


def representative(assembly, key, level="superior"):
    candidates = [bar for bar in assembly.bars if bar.key == key and bar.level == level
                  and bar.piece_role in ("completa", "inicial")]
    return min(candidates, key=lambda bar: abs(bar.coordinate_m))


def first_vertical_leg(bar):
    """Read an actual straight leg rather than the theoretical sharp corner."""
    for a, b, bulge in zip(bar.vertices_m, bar.vertices_m[1:], bar.bulges):
        if (abs(bulge) < 1e-10 and math.dist(a[:2], b[:2]) < 1e-10
                and abs(a[2] - b[2]) > 1e-10):
            return a, b
    raise AssertionError(f"No vertical hook in {bar.id}")


def face_distance(point, key, geometry):
    """Normal axis-to-formwork distance for the face carrying this lateral."""
    x, y, _ = point
    if key == "lateral_x":
        return geometry.largo_m / 2 - abs(y)
    slope = math.tan(math.radians(geometry.esviaje_grados))
    return (geometry.ancho_m / 2 - abs(x - slope * y)) / math.hypot(1, slope)


@pytest.mark.parametrize("skew", SKEWS)
@pytest.mark.parametrize("mixed_diameters", (False, True))
def test_laterals_are_outside_mesh_hooks_with_real_cover_and_surface_contact(skew, mixed_diameters):
    geometry, cover, rules, assembly = assembly_case(skew, mixed_diameters=mixed_diameters)
    for lateral_key, mesh_key in (("lateral_y", "mesh_x"), ("lateral_x", "mesh_y")):
        mesh = representative(assembly, mesh_key)
        mesh_radius = mesh.diameter_mm / 2000
        lateral_radius = rules[lateral_key].diameter_mm / 2000
        leg, _ = first_vertical_leg(mesh)
        leg_distance = face_distance(leg, lateral_key, geometry)
        # The outer lateral occupies one full diameter before the mesh leg.
        assert leg_distance == pytest.approx(cover.lateral_m + 2 * lateral_radius + mesh_radius)
        laterals = [bar for bar in assembly.bars if bar.key == lateral_key]
        assert laterals
        for lateral in laterals:
            for point in (lateral.main_start_m, lateral.main_end_m):
                lateral_distance = face_distance(point, lateral_key, geometry)
                assert lateral_distance - lateral_radius == pytest.approx(cover.lateral_m)
                assert leg_distance - lateral_distance == pytest.approx(mesh_radius + lateral_radius)
            # Their bends and hooks must also remain inside the real skewed faces.
            for point in lateral.points_m:
                for face in ("lateral_x", "lateral_y"):
                    assert face_distance(point, face, geometry) >= cover.lateral_m + lateral_radius - 1e-9


@pytest.mark.parametrize("skew", SKEWS)
@pytest.mark.parametrize("lateral_x,lateral_y", ((False, False), (False, True), (True, False), (True, True)))
def test_disabling_a_lateral_only_removes_its_own_mesh_hook_clearance(skew, lateral_x, lateral_y):
    geometry, cover, rules, assembly = assembly_case(
        skew, mixed_diameters=True, lateral_x=lateral_x, lateral_y=lateral_y)
    for lateral_key, mesh_key, enabled in (("lateral_y", "mesh_x", lateral_y),
                                           ("lateral_x", "mesh_y", lateral_x)):
        mesh = representative(assembly, mesh_key)
        leg, _ = first_vertical_leg(mesh)
        occupied = rules[lateral_key].diameter_mm / 1000 if enabled else 0
        assert face_distance(leg, lateral_key, geometry) == pytest.approx(
            cover.lateral_m + occupied + mesh.diameter_mm / 2000)
        assert any(bar.key == lateral_key for bar in assembly.bars) == enabled


@pytest.mark.parametrize("origin", ("inicio", "final"))
@pytest.mark.parametrize("mixed_diameters", (False, True))
def test_rectangular_transverse_distribution_reaches_both_reference_bend_tangencies(origin, mixed_diameters):
    _, _, _, assembly = assembly_case(origin=origin, mixed_diameters=mixed_diameters)
    source = {bar.id: bar for bar in assembly.bars}
    for view, line_key, circle_key, coordinate in (("FR", "mesh_x", "mesh_y", 0),
                                                   ("AA", "mesh_y", "mesh_x", 1)):
        projected = project_footing_assembly(assembly, view)
        line = [source[piece.source_id] for piece in projected
                if piece.key == line_key and piece.level == "superior"]
        circles = [piece.vertices_m[0][0] for piece in projected
                   if piece.kind == "circle" and piece.key == circle_key and piece.level == "superior"]
        assert line and circles
        assert min(circles) == pytest.approx(min(bar.main_start_m[coordinate] for bar in line))
        assert max(circles) == pytest.approx(max(bar.main_end_m[coordinate] for bar in line))


@pytest.mark.parametrize("skew", SKEWS)
@pytest.mark.parametrize("mixed_diameters", (False, True))
def test_fr_and_aa_keep_the_same_physical_mesh_layer_order(skew, mixed_diameters):
    geometry, cover, _, assembly = assembly_case(skew, mixed_diameters=mixed_diameters)
    x = representative(assembly, "mesh_x")
    y = representative(assembly, "mesh_y")
    contact = (x.diameter_mm + y.diameter_mm) / 2000
    assert x.main_start_m[2] - y.main_start_m[2] == pytest.approx(contact)
    assert geometry.alto_m - x.main_start_m[2] - x.diameter_mm / 2000 == pytest.approx(cover.superior_m)
    for level, sign in (("superior", 1), ("inferior", -1)):
        for view, line_key, circle_key, circle_side in (("FR", "mesh_x", "mesh_y", -sign),
                                                        ("AA", "mesh_y", "mesh_x", sign)):
            line_height = representative(assembly, line_key, level).main_start_m[2]
            circles = [piece for piece in project_footing_assembly(assembly, view)
                       if piece.kind == "circle" and piece.key == circle_key and piece.level == level]
            assert circles
            for circle in circles:
                assert circle.vertices_m[0][1] - line_height == pytest.approx(circle_side * contact)


@pytest.mark.parametrize("skew", SKEWS)
@pytest.mark.parametrize("origin", ("inicio", "final"))
def test_lateral_distribution_reaches_both_mesh_vertical_tangencies_and_keeps_spacing(skew, origin):
    _, _, rules, assembly = assembly_case(skew, origin=origin, mixed_diameters=True)
    for lateral_key, mesh_key in (("lateral_y", "mesh_x"), ("lateral_x", "mesh_y")):
        upper_leg = first_vertical_leg(representative(assembly, mesh_key, "superior"))
        lower_leg = first_vertical_leg(representative(assembly, mesh_key, "inferior"))
        upper = max(point[2] for point in upper_leg)
        lower = min(point[2] for point in lower_leg)
        heights = sorted({bar.coordinate_m for bar in assembly.bars if bar.key == lateral_key},
                         reverse=origin == "inicio")
        assert heights
        assert heights[0] == pytest.approx(upper if origin == "inicio" else lower)
        spacing = rules[lateral_key].spacing_cm / 100
        for index, height in enumerate(heights):
            assert lower - 1e-9 <= height <= upper + 1e-9
            if index < len(heights) - 2:
                expected = heights[0] + (-1 if origin == "inicio" else 1) * index * spacing
                assert height == pytest.approx(expected)
        gaps = [abs(b - a) for a, b in zip(heights, heights[1:])]
        assert all(gap <= spacing + 1e-9 for gap in gaps)
        assert all(gap >= rules[lateral_key].diameter_mm / 1000 - 1e-9 for gap in gaps)
        assert heights[-1] == pytest.approx(lower if origin == "inicio" else upper)


@pytest.mark.parametrize("skew", (-30, -12, 12, 30))
@pytest.mark.parametrize("origin", ("inicio", "final"))
def test_skew_y_mesh_still_covers_both_wedges_with_bend_feasible_end_chords(skew, origin):
    geometry, cover, rules, assembly = assembly_case(skew, origin=origin, mixed_diameters=True)
    bars = [bar for bar in assembly.bars if bar.key == "mesh_y" and bar.level == "superior"]
    bars.sort(key=lambda bar: bar.coordinate_m)
    radius = rules["mesh_y"].diameter_mm / 2000
    bend = 6 * radius
    slope = math.tan(math.radians(skew))
    half_width = geometry.ancho_m / 2 - (
        cover.lateral_m + radius + rules["lateral_y"].diameter_mm / 1000) * math.hypot(1, slope)
    half_depth = geometry.largo_m / 2 - (
        cover.lateral_m + radius + rules["lateral_x"].diameter_mm / 1000)
    limit = half_width + abs(slope) * (half_depth - 2 * bend)
    assert bars[0].coordinate_m < -geometry.ancho_m / 2
    assert bars[-1].coordinate_m > geometry.ancho_m / 2
    assert bars[0].coordinate_m == pytest.approx(-limit)
    assert bars[-1].coordinate_m == pytest.approx(limit)
    # Both limiting chords have two real bends meeting at a common tangent.
    for endpoint in (bars[0], bars[-1]):
        assert math.dist(endpoint.main_start_m, endpoint.main_end_m) == pytest.approx(0, abs=1e-8)
    for first, last in zip(bars, bars[1:]):
        assert last.coordinate_m - first.coordinate_m <= rules["mesh_y"].spacing_cm / 100 + 1e-9


def test_rectangular_fr_left_lateral_circle_is_between_the_leg_and_concrete():
    geometry, cover, rules, assembly = assembly_case(mixed_diameters=True)
    projected = project_footing_assembly(assembly, "FR")
    circles = [piece for piece in projected if piece.kind == "circle" and piece.key == "lateral_y"]
    left = min(piece.vertices_m[0][0] for piece in circles)
    concrete = -geometry.ancho_m / 2
    lateral_radius = rules["lateral_y"].diameter_mm / 2000
    mesh_radius = rules["mesh_x"].diameter_mm / 2000
    mesh_leg, _ = first_vertical_leg(representative(assembly, "mesh_x"))
    assert left - concrete == pytest.approx(cover.lateral_m + lateral_radius)
    assert mesh_leg[0] - concrete == pytest.approx(cover.lateral_m + 2 * lateral_radius + mesh_radius)
    assert concrete < left < mesh_leg[0]
