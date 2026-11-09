"""Geometry constraints of the shared mesh plan, independent of CAD."""
from dataclasses import replace
import math

import pytest

from sincal.rebar.model import (
    Cover, ZapataGeometry, bend_radius_cm, build_zapata_schedule,
    default_zapata_rules, distribution_positions_cm,
)
from sincal.rebar.plan import footing_mesh_axes


def test_rectangular_meshes_keep_tangent_distribution_and_fixed_lengths():
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150)
    cover = Cover.from_centimetres(7.5, 5, 5)
    mx, my, *_ = default_zapata_rules()
    for rule, reference, transverse in ((mx, my, 750), (my, mx, 1159.6)):
        tangent = 5 + reference.diameter_mm / 20 + bend_radius_cm(reference.diameter_mm)
        expected = distribution_positions_cm(transverse - 2 * tangent, rule.spacing_cm,
                                             include_endpoints=True,
                                             minimum_spacing_cm=rule.diameter_mm / 10)
        axes = footing_mesh_axes(geometry, cover, rule, reference)
        assert len(axes) == len(expected)
        assert len({round(axis.length_m, 8) for axis in axes}) == 1
    assert all(not mark.length_variants for mark in build_zapata_schedule(geometry, cover, default_zapata_rules()).marks)


@pytest.mark.parametrize('skew', [-30, -12, 12, 30])
def test_shortest_edge_bar_fits_exactly_two_bends_without_zero_length_axis(skew):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    mx, my, *_ = default_zapata_rules()
    axes = footing_mesh_axes(geometry, cover, my, mx)
    radius = bend_radius_cm(my.diameter_mm) / 100
    assert axes[0].length_m == pytest.approx(2 * radius)
    assert all(axis.length_m >= 2 * radius - 1e-9 for axis in axes)
    mark = next(mark for mark in build_zapata_schedule(geometry, cover, default_zapata_rules()).marks if mark.key == 'mesh_y')
    assert mark.length_variants[0].length_cm == math.ceil(200 + math.pi * radius * 100 - 1e-9)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), True, -1])
def test_bad_spacing_is_rejected_before_distribution(value):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, 12)
    cover = Cover.from_centimetres(7.5, 5, 5)
    mx, my, *_ = default_zapata_rules()
    with pytest.raises(ValueError):
        footing_mesh_axes(geometry, cover, replace(my, spacing_cm=value), mx)


def test_unbendable_wedge_does_not_silently_drop_all_end_bars():
    geometry = ZapataGeometry.from_centimetres(20, 20, 150, 45)
    cover = Cover.from_centimetres(5, 5, 5)
    mx, my, *_ = default_zapata_rules()
    with pytest.raises(ValueError, match='dobleces'):
        footing_mesh_axes(geometry, cover, my, mx)


def test_overlength_variable_series_is_rejected_without_inventing_splices():
    geometry = ZapataGeometry.from_centimetres(1500, 1159.6, 150, 12)
    cover = Cover.from_centimetres(7.5, 5, 5)
    schedule = build_zapata_schedule(geometry, cover, default_zapata_rules())
    assert not schedule.is_valid
    assert not any(mark.key == 'mesh_y' for mark in schedule.marks)
    assert any('serie variable' in issue.message and 'empalme' in issue.message for issue in schedule.issues)
