"""The footing can close at both tangencies without changing legacy callers."""
from dataclasses import replace

import pytest

from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import Cover, ZapataGeometry, default_zapata_rules, distribution_positions_cm
from sincal.rebar.plan import footing_mesh_axes


@pytest.mark.parametrize("origin", ("inicio", "final"))
def test_explicit_endpoints_close_a_short_residue_without_duplicates(origin):
    positions = distribution_positions_cm(122.1, 20, origin, include_endpoints=True)
    assert positions[0] == 0
    assert positions[-1] == pytest.approx(122.1)
    ordered = positions if origin == "inicio" else tuple(122.1 - p for p in reversed(positions))
    assert ordered[:-1] == pytest.approx((0, 20, 40, 60, 80, 100, 120))
    assert ordered[-1] - ordered[-2] == pytest.approx(2.1)
    assert len(positions) == len(set(positions))


@pytest.mark.parametrize("span,expected", ((0, (0,)), (120, (0, 20, 40, 60, 80, 100, 120))))
def test_exact_endpoint_does_not_duplicate_a_regular_bar(span, expected):
    assert distribution_positions_cm(span, 20, include_endpoints=True) == expected


def test_unspecified_endpoint_option_keeps_existing_ten_centimetre_rule():
    assert distribution_positions_cm(122.1, 20) == (0, 20, 40, 60, 80, 100, 120)
    assert distribution_positions_cm(135, 20) == (0, 20, 40, 60, 80, 100, 120, 135)


@pytest.mark.parametrize("origin", ("inicio", "final"))
@pytest.mark.parametrize("span,diameter,last_gap", ((721.4, 2.2, 10.7), (122.1, 1.6, 2.1),
                                                   (122.1, 2.5, 11.05), (124, 4, 4)))
def test_short_closing_interval_never_overlaps_parallel_bars(origin, span, diameter, last_gap):
    positions = distribution_positions_cm(span, 20, origin, include_endpoints=True,
                                         minimum_spacing_cm=diameter)
    assert positions[0] == 0
    assert positions[-1] == pytest.approx(span)
    ordered = positions if origin == "inicio" else tuple(span - p for p in reversed(positions))
    gaps = [b - a for a, b in zip(ordered, ordered[1:])]
    assert gaps[-1] == pytest.approx(last_gap)
    assert all(diameter - 1e-9 <= gap <= 20 + 1e-9 for gap in gaps)
    assert gaps[:-2] == pytest.approx([20] * len(gaps[:-2]))


@pytest.mark.parametrize("span,spacing,diameter", ((1.4, 20, 2.2), (3, 2.2, 2.2), (20, 1, 2.2)))
def test_insufficient_room_for_both_end_bars_is_explicit(span, spacing, diameter):
    with pytest.raises(ValueError, match="superpon"):
        distribution_positions_cm(span, spacing, include_endpoints=True,
                                  minimum_spacing_cm=diameter)


@pytest.mark.parametrize("origin", ("inicio", "final"))
@pytest.mark.parametrize("diameter", (12, 16, 22, 32))
def test_common_lateral_assembly_closes_both_tangencies_without_parallel_overlap(origin, diameter):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150)
    cover = Cover.from_centimetres(7.5, 5, 5)
    rules = tuple(replace(rule, origin=origin,
                          diameter_mm=diameter if rule.key.startswith("lateral_") else rule.diameter_mm)
                  for rule in default_zapata_rules())
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    for lateral, mesh in (("lateral_x", "mesh_y"), ("lateral_y", "mesh_x")):
        upper = next(bar for bar in assembly.bars if bar.key == mesh and bar.level == "superior")
        lower = next(bar for bar in assembly.bars if bar.key == mesh and bar.level == "inferior")
        heights = sorted({bar.coordinate_m for bar in assembly.bars if bar.key == lateral})
        assert heights[0] == pytest.approx(lower.main_start_m[2] + lower.bend_radius_cm / 100)
        assert heights[-1] == pytest.approx(upper.main_start_m[2] - upper.bend_radius_cm / 100)
        assert all(diameter / 1000 - 1e-9 <= b - a <= .2 + 1e-9
                   for a, b in zip(heights, heights[1:]))


@pytest.mark.parametrize("origin", ("inicio", "final"))
@pytest.mark.parametrize("skew", (0, -12))
def test_suple_applies_existing_offset_before_checking_its_closing_interval(origin, skew):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    _, mesh_y, suple, *_ = default_zapata_rules()
    suple = replace(suple, enabled=True, origin=origin)
    axes = footing_mesh_axes(geometry, cover, suple, mesh_y)
    assert all(suple.diameter_mm / 1000 - 1e-9 <= b.coordinate_m - a.coordinate_m
               <= suple.spacing_cm / 100 + 1e-9 for a, b in zip(axes, axes[1:]))
