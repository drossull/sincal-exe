"""Lap dimensions belong to the despiece/preview, never to footing views."""
from dataclasses import replace
from unittest.mock import patch

import pytest

from sincal.cad.moldajes import MoldajeCandidate
from sincal.cad.zapata_detail import build_zapata_detail_lisp
from sincal.cad.zapata_views import build_zapata_lisp, project_footing_assembly
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.detail import build_detail_groups
from sincal.web.rebar import defaults, domain, preview


def footing():
    geometry, cover, rules = domain(defaults())
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    candidate = MoldajeCandidate(
        'ZAP', 'reference', 'OK', 4, geometry.ancho_m * geometry.alto_m,
        ((0, 0), (geometry.ancho_m, 0),
         (geometry.ancho_m, geometry.alto_m), (0, geometry.alto_m)),
    )
    return geometry, cover, rules, assembly, candidate


@pytest.mark.parametrize('view', ['FR', 'AA', 'BB', 'CC', 'FF'])  # E–E uses FF internally.
def test_view_geometry_and_annotations_ignore_lap_dimension_metadata(view):
    geometry, cover, rules, assembly, candidate = footing()
    projected = project_footing_assembly(assembly, view)
    # Add explicit overlap metadata to every projected polyline, including
    # sections whose default visible longitudinal family happens to be whole.
    with_laps = tuple(replace(piece, lap_segments_m=(((1.0, 0.8), (2.5, 0.8)),))
                      if piece.kind != 'circle' else piece for piece in projected)
    without_laps = tuple(replace(piece, lap_segments_m=()) for piece in projected)
    assert any(piece.lap_segments_m for piece in with_laps)
    with patch('sincal.cad.zapata_views.project_footing_assembly', return_value=with_laps):
        source = build_zapata_lisp(view, candidate, geometry, cover, rules, 'entrada')
    with patch('sincal.cad.zapata_views.project_footing_assembly', return_value=without_laps):
        without = build_zapata_lisp(view, candidate, geometry, cover, rules, 'entrada')
    assert source == without
    assert source.count('(cons 0 "LWPOLYLINE")') == sum(piece.kind != 'circle' for piece in projected)
    assert source.count('(cons 0 "CIRCLE")') == sum(piece.kind == 'circle' for piece in projected)
    distribution_dimensions = [line for line in source.splitlines()
                               if line.strip().startswith('(sincal:marked-dim ')]
    if view != 'FF':
        assert distribution_dimensions, 'Cross-section distribution dimensions remain visible.'
    else:
        assert distribution_dimensions == []


def test_actual_laps_remain_in_shared_geometry_despiece_and_preview():
    geometry, cover, rules, assembly, _ = footing()
    actual_laps = [bar for bar in assembly.bars if bar.lap_segments_m]
    assert actual_laps
    assert any(piece.lap_segments_m for piece in project_footing_assembly(assembly, 'FR'))
    groups = build_detail_groups(assembly.schedule, rules, geometry)
    number_of_dimensions = sum(len(group.laps_m) for group in groups)
    assert number_of_dimensions > 0
    detail = build_zapata_detail_lisp(assembly.schedule, rules, geometry, 'entrada', '')
    assert sum(line.strip().startswith('(sincal:lap-dim ') for line in detail.splitlines()) == number_of_dimensions
    web_preview = preview(defaults())
    assert web_preview['valid']
    assert any(piece['lap_segments_m'] for group in web_preview['splice_groups'] for piece in group['pieces'])
