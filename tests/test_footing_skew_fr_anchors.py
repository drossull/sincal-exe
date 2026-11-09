"""Only the selected frontal section is anchored; the full skew mesh remains."""
from dataclasses import replace
import math

import pytest

from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import Cover, ZapataGeometry, default_zapata_rules, bend_radius_cm
from sincal.rebar.plan import footing_mesh_axes


def case(skew, origin, mixed):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    diameters = {"mesh_x": 22, "mesh_y": 16, "lateral_x": 12, "lateral_y": 18}
    rules = tuple(replace(rule, origin=origin,
                          diameter_mm=diameters.get(rule.key, rule.diameter_mm) if mixed else rule.diameter_mm)
                  for rule in default_zapata_rules())
    return geometry, cover, rules


@pytest.mark.parametrize("skew", (-30, -12, 12, 30))
@pytest.mark.parametrize("origin", ("inicio", "final"))
@pytest.mark.parametrize("mixed", (False, True))
def test_first_and_last_real_y_in_frontal_section_meet_x_bend_tangencies(skew, origin, mixed):
    geometry, cover, rules = case(skew, origin, mixed)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    reference = min((bar for bar in assembly.bars if bar.key == "mesh_x" and bar.level == "superior"),
                    key=lambda bar: abs(bar.coordinate_m))
    station = reference.coordinate_m
    run = [bar for bar in assembly.bars if bar.placement_id == reference.placement_id]
    left = min(bar.main_start_m[0] for bar in run)
    right = max(bar.main_end_m[0] for bar in run)
    ybars = [bar for bar in assembly.bars if bar.key == "mesh_y" and bar.level == "superior"]
    crossing = [bar for bar in ybars if bar.main_start_m[1] - 1e-9 <= station <= bar.main_end_m[1] + 1e-9]
    assert min(bar.coordinate_m for bar in crossing) == pytest.approx(left)
    assert max(bar.coordinate_m for bar in crossing) == pytest.approx(right)
    # These are real surface contacts in 3D, not moved drawing circles.
    contact = (reference.diameter_mm + rules[1].diameter_mm) / 2000
    for endpoint in (left, right):
        bar = next(bar for bar in crossing if math.isclose(bar.coordinate_m, endpoint, abs_tol=1e-9))
        assert reference.main_start_m[2] - bar.main_start_m[2] == pytest.approx(contact)
    # No exterior Y, including its curved hook or vertical leg, passes through
    # this section outside the two agreed tangencies.
    for bar in ybars:
        if bar.coordinate_m < left - 1e-9 or bar.coordinate_m > right + 1e-9:
            ys = [point[1] for point in bar.vertices_m]
            assert station < min(ys) - 1e-9 or station > max(ys) + 1e-9


@pytest.mark.parametrize("skew", (-30, -12, 12, 30))
@pytest.mark.parametrize("origin", ("inicio", "final"))
def test_wedges_keep_both_global_endpoints_direction_and_maximum_pitch(skew, origin):
    geometry, cover, rules = case(skew, origin, True)
    mx, my, _, lx, ly = rules
    side_insets = (ly.diameter_mm / 1000, lx.diameter_mm / 1000)
    axes = footing_mesh_axes(geometry, cover, my, mx, side_insets_m=side_insets)
    slope = math.tan(math.radians(skew))
    half_width = geometry.ancho_m / 2 - (cover.lateral_m + my.diameter_mm / 2000 + side_insets[0]) * math.hypot(1, slope)
    half_depth = geometry.largo_m / 2 - cover.lateral_m - my.diameter_mm / 2000 - side_insets[1]
    radius = bend_radius_cm(my.diameter_mm) / 100
    limit = half_width + abs(slope) * (half_depth - 2 * radius)
    assert axes[0].coordinate_m == pytest.approx(-limit)
    assert axes[-1].coordinate_m == pytest.approx(limit)
    assert axes[0].length_m == pytest.approx(2 * radius)
    assert axes[-1].length_m == pytest.approx(2 * radius)
    assert len({round(axis.coordinate_m, 9) for axis in axes}) == len(axes)
    for axis in axes:
        assert axis.start_m[0] == axis.end_m[0] == axis.coordinate_m
    for first, last in zip(axes, axes[1:]):
        gap = last.coordinate_m - first.coordinate_m
        assert my.diameter_mm / 1000 - 1e-9 <= gap <= my.spacing_cm / 100 + 1e-9


def test_zero_skew_keeps_existing_rectangular_pitch():
    geometry, cover, rules = case(0, "inicio", False)
    mx, my, _, lx, ly = rules
    axes = footing_mesh_axes(geometry, cover, my, mx,
                             side_insets_m=(ly.diameter_mm / 1000, lx.diameter_mm / 1000))
    expected_start = -geometry.ancho_m / 2 + cover.lateral_m + ly.diameter_mm / 1000 + mx.diameter_mm / 2000 + bend_radius_cm(mx.diameter_mm) / 100
    assert axes[0].coordinate_m == pytest.approx(expected_start)
    assert axes[1].coordinate_m == pytest.approx(expected_start + my.spacing_cm / 100)
    assert axes[-1].coordinate_m == pytest.approx(-expected_start)


def test_too_close_wedge_bar_is_reported_instead_of_moving_or_trimming_it():
    geometry, cover, rules = case(-12, "inicio", False)
    rules = tuple(replace(rule, spacing_cm=5) if rule.key == "mesh_y" else rule for rule in rules)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert not assembly.is_valid
    assert any("fierro de la cuña sobre el doblez" in issue.message for issue in assembly.schedule.issues)
