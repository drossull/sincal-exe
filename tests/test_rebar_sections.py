"""Analytic cuts of actual straight and bulged bar pieces, without CAD."""
from types import SimpleNamespace
import math

import pytest

from sincal.cad.rebar_sections import intersect_bar_plane, SectionSegment


def piece(points, bulges=None, *, u=(1, 0, 0), v=(0, 0, 1)):
    return SimpleNamespace(vertices_m=tuple(points),
                           bulges=tuple(bulges or [0] * len(points)),
                           axis_u=u, axis_v=v)


def test_straight_crossing_uses_plane_normal_and_keeps_elevation():
    bar = piece(((-2, -1, .5), (4, 2, 1.5)))
    hit = intersect_bar_plane(bar, (1, -1), 0)
    assert hit.points_m[0] == pytest.approx((0, 0, 5 / 6))
    assert not hit.contained_segments
    # Scaling the plane equation must not change its location or tolerance.
    assert intersect_bar_plane(bar, (3, -3), 0) == hit


def test_parallel_external_segment_has_no_section_symbol():
    bar = piece(((2, -1, .5), (2, 1, .5)))
    hit = intersect_bar_plane(bar, (1, 0), 1)
    assert hit.points_m == hit.contained_segments == ()


def test_joint_hit_is_returned_only_once():
    bar = piece(((-1, 0, 0), (0, 0, 1), (1, 0, 0)))
    hit = intersect_bar_plane(bar, (1, 0), 0)
    assert hit.points_m == ((0, 0, 1),)


@pytest.mark.parametrize("sign", (1, -1))
def test_positive_and_negative_quarter_arcs_have_exact_interior_root(sign):
    # Circle in X-Z: radius one, centre zero. Reversing traversal reverses bulge.
    points = ((1, 0, 0), (0, 0, 1))
    if sign < 0:
        points = tuple(reversed(points))
    bar = piece(points, (sign * math.tan(math.pi / 8), 0))
    hit = intersect_bar_plane(bar, (1, 0), .6)
    assert len(hit.points_m) == 1
    assert hit.points_m[0] == pytest.approx((.6, 0, .8), abs=1e-12)
    assert not hit.contained_segments


def test_arc_tangency_is_not_duplicated_and_nearby_external_plane_has_no_hit():
    bar = piece(((0, 0, -1), (0, 0, 1)), (1, 0))
    hit = intersect_bar_plane(bar, (1, 0), 1)
    assert len(hit.points_m) == 1
    assert hit.points_m[0] == pytest.approx((1, 0, 0), abs=1e-12)
    assert intersect_bar_plane(bar, (1, 0), 1.00000001).points_m == ()


def test_plane_can_cross_the_same_arc_twice():
    bar = piece(((0, 0, -1), (0, 0, 1)), (1, 0))
    hit = intersect_bar_plane(bar, (1, 0), .6)
    assert len(hit.points_m) == 2
    for actual, expected in zip(sorted(hit.points_m, key=lambda p: p[2]), ((.6, 0, -.8), (.6, 0, .8))):
        assert actual == pytest.approx(expected, abs=1e-12)


def test_arc_roots_outside_the_actual_sweep_are_rejected():
    bar = piece(((1, 0, 0), (0, 0, 1)), (math.tan(math.pi / 8), 0))
    assert intersect_bar_plane(bar, (1, 0), -.6).points_m == ()


def test_whole_bar_in_plane_returns_original_segments_and_bulges():
    bulge = math.tan(math.pi / 8)
    points = ((1, 0, -1), (1, 0, 0), (0, 0, 1), (-1, 0, 1))
    bar = piece(points, (0, bulge, 0, 0))
    hit = intersect_bar_plane(bar, (0, 1), 0)
    assert hit.points_m == ()
    assert hit.contained_segments == (
        SectionSegment(points[0], points[1]),
        SectionSegment(points[1], points[2], bulge),
        SectionSegment(points[2], points[3]),
    )


def test_join_with_contained_segment_does_not_add_a_circle_to_its_endpoint():
    bar = piece(((-1, 0, 0), (0, 0, 0), (0, 0, 1)))
    hit = intersect_bar_plane(bar, (1, 0), 0)
    assert hit.points_m == ()
    assert hit.contained_segments == (SectionSegment((0, 0, 0), (0, 0, 1)),)


def test_oblique_bar_plane_uses_its_actual_oriented_axes():
    theta = math.radians(-12)
    u = (math.sin(theta), math.cos(theta), 0)
    origin = (2, -3, 4)
    def world(x, z):
        return tuple(origin[i] + x * u[i] + z * (i == 2) for i in range(3))
    bar = piece((world(1, 0), world(0, 1)), (math.tan(math.pi / 8), 0), u=u)
    station = u[0] * origin[0] + u[1] * origin[1] + .6
    hit = intersect_bar_plane(bar, u[:2], station)
    assert len(hit.points_m) == 1
    assert hit.points_m[0] == pytest.approx(world(.6, .8), abs=1e-12)


def test_lap_pieces_keep_independent_hits_even_on_the_same_axis():
    first = piece(((-1, 0, .5), (.5, 0, .5)))
    second = piece(((-.5, 0, .5), (1, 0, .5)))
    assert intersect_bar_plane(first, (1, 0), 0).points_m == ((0, 0, .5),)
    assert intersect_bar_plane(second, (1, 0), 0).points_m == ((0, 0, .5),)


@pytest.mark.parametrize("level,sign", (("superior", -1), ("inferior", 1)))
def test_actual_footing_bend_is_cut_at_exact_circle_height(level, sign):
    from sincal.rebar.assembly import build_footing_assembly
    from sincal.web.rebar import defaults, domain

    assembly = build_footing_assembly(*domain(defaults()))
    assert assembly.is_valid
    bar = min((bar for bar in assembly.bars if bar.key == "mesh_y" and bar.level == level),
              key=lambda bar: abs(bar.coordinate_m))
    radius = bar.bend_radius_cm / 100
    main_end = bar.main_end_m
    # Halfway in horizontal coordinate between the straight tangent and leg.
    station = main_end[1] + radius / 2
    expected_z = main_end[2] + sign * (radius - math.sqrt(radius * radius - (radius / 2) ** 2))
    hit = intersect_bar_plane(bar, (0, 1), station)
    assert len(hit.points_m) == 1
    assert hit.points_m[0] == pytest.approx((bar.coordinate_m, station, expected_z), abs=1e-12)
    assert not hit.contained_segments


@pytest.mark.parametrize("normal,station,tolerance", (((0, 0), 0, 1e-9),
                                                    ((math.nan, 1), 0, 1e-9),
                                                    ((1, 0), math.inf, 1e-9),
                                                    ((1, 0), 0, 0)))
def test_invalid_planes_are_rejected(normal, station, tolerance):
    with pytest.raises(ValueError):
        intersect_bar_plane(piece(((0, 0, 0), (1, 0, 0))), normal, station, tolerance=tolerance)
