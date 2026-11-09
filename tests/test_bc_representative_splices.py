"""Existing lap pieces remain rigid in the B/C drawing convention."""
from dataclasses import replace
import math

import pytest

from sincal.cad.zapata_views import (ZapataCadError, footing_drawing_projection,
                                     project_footing_assembly)
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import Cover, RemovedPiece, ZapataGeometry, default_zapata_rules


def case(skew=9):
    geometry = ZapataGeometry.from_centimetres(1500, 1159.6, 150, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    rules = tuple(replace(rule, continuation_mark="30", terminal_mark="31") if rule.key == "mesh_y"
                  else replace(rule, enabled=False) if rule.key == "lateral_y" else rule
                  for rule in default_zapata_rules())
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    return geometry, cover, rules, assembly


@pytest.mark.parametrize("view", ("BB", "CC"))
@pytest.mark.parametrize("skew", (-9, 9))
def test_parallel_spliced_y_needs_no_scaling_of_pieces_or_overlaps(view, skew):
    geometry, cover, _, assembly = case(skew)
    physical = [piece for piece in project_footing_assembly(assembly, view) if piece.key == "mesh_y"]
    drawing = [piece for piece in footing_drawing_projection(assembly, view, geometry=geometry, cover=cover)
               if piece.key == "mesh_y"]
    # The exact plane meets the first lane only. B/C's explicitly authorized
    # longitudinal convention still represents both physical lap pieces.
    assert len(physical) == 2 and len(drawing) == 4
    by_id = {piece.source_id: piece for piece in physical}
    source = {bar.id: bar for bar in assembly.bars}
    for after in drawing:
        bar = source[after.source_id]
        sign = 1 if bar.axis_v[2] >= 0 else -1
        assert after.bulges == tuple(value*sign for value in bar.bulges)
        for a,b,wa,wb in zip(after.vertices_m,after.vertices_m[1:],bar.vertices_m,bar.vertices_m[1:]):
            assert math.dist(a,b) == pytest.approx(math.dist(wa,wb))
        if after.source_id in by_id:
            before = by_id[after.source_id]
            for actual, expected in zip(after.vertices_m, before.vertices_m):
                assert actual == pytest.approx(expected)
        if after.lap_segments_m:
            (first, last), = after.lap_segments_m
            assert last[0]-first[0] == pytest.approx(1.5)


@pytest.mark.parametrize("role", ("inicial", "terminal"))
def test_deleting_representative_lap_piece_preserves_remaining_symbol(role):
    geometry, cover, rules, assembly = case()
    before = footing_drawing_projection(assembly, "BB", geometry=geometry, cover=cover)
    represented = {piece.source_id for piece in before if piece.key == "mesh_y"}
    chosen = next(bar for bar in assembly.bars if bar.id in represented and bar.piece_role == role)
    rules = tuple(replace(rule, removed_pieces=(RemovedPiece(chosen.id, chosen.signature),))
                  if rule.key == chosen.key else rule for rule in rules)
    after = build_footing_assembly(geometry, cover, rules)
    assert after.is_valid
    assert footing_drawing_projection(after, "BB", geometry=geometry, cover=cover) == tuple(
        piece for piece in before if piece.source_id != chosen.id)


def test_an_exceptional_spliced_run_that_would_need_extension_is_rejected():
    geometry, cover, _, assembly = case()
    with pytest.raises(ZapataCadError, match="empalmado.*traslapos"):
        footing_drawing_projection(assembly, "BB", geometry=replace(geometry, largo_m=geometry.largo_m+1), cover=cover)


def test_zero_skew_drawing_stays_exactly_as_before_and_requires_paired_parameters():
    geometry, cover, _, assembly = case(0)
    for view in ("FR", "AA", "BB", "CC", "FF"):
        assert footing_drawing_projection(assembly, view, geometry=geometry, cover=cover) == footing_drawing_projection(assembly, view)
    with pytest.raises(ZapataCadError, match="dimensiones y recubrimientos"):
        footing_drawing_projection(assembly, "BB", geometry=geometry)
