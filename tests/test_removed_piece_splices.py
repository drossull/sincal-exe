"""Removed splice partners cannot create physical overlap in any detail."""
from collections import defaultdict
from types import SimpleNamespace

import pytest

from sincal.cad.zapata_detail import _group_definition
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.detail import build_detail_groups
from sincal.rebar.splices import physical_laps
from sincal.web.rebar import domain, preview
from tests.test_web_bar_removal import state_and_assembly, remove


def detail(state):
    geometry, cover, rules = domain(state)
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    return next(group for group in build_detail_groups(assembly.schedule, rules, geometry)
                if group.group_id == "G12")


@pytest.mark.parametrize("role", ("inicial", "terminal"))
def test_splice_editor_single_survivor_has_no_lap_but_family_detail_keeps_existing_pairs(role):
    state, assembly = state_and_assembly()
    first = next(bar for bar in assembly.bars if bar.key == "mesh_x" and bar.piece_role == "inicial")
    run = [bar for bar in assembly.bars if bar.placement_id == first.placement_id]
    before = preview(state)["splice_groups"][0]
    removed = next(bar for bar in run if bar.piece_role == role)
    survivor = next(bar for bar in run if bar.id != removed.id)
    remove(state, removed)
    group = preview(state)["splice_groups"][0]
    assert group["removed_piece_count"] == 1
    assert group["lap_cm"] == 0
    assert [piece["id"] for piece in group["pieces"]] == [survivor.id]
    assert group["pieces"][0]["lap_segments_m"] == ()
    assert group["main_start_m"] == before["main_start_m"]
    assert group["main_end_m"] == before["main_end_m"]
    original = next(piece for piece in before["pieces"] if piece["id"] == survivor.id)
    for field in ("points_m", "vertices_m", "bulges", "length_cm", "developed_length_cm"):
        assert group["pieces"][0][field] == original[field]
    # The aggregated fabrication detail still describes genuine pairs in all
    # the other runs; deleting one representative is not a family-wide edit.
    assert len(detail(state).laps_m) == 1


@pytest.mark.parametrize("role", ("inicial", "terminal"))
def test_removing_entire_partner_mark_keeps_survivor_coordinates_and_no_detail_lap(role):
    state, assembly = state_and_assembly()
    before = detail(state)
    removed = [bar for bar in assembly.bars if bar.key == "mesh_x" and bar.piece_role == role]
    remove(state, *removed)
    after = detail(state)
    assert len(after.pieces) == 1
    assert after.laps_m == ()
    assert after.offsets_m[0][0] == 0
    original = next(piece for piece in before.pieces if piece.mark == after.pieces[0].mark)
    assert after.pieces[0].vertices_m == original.vertices_m
    assert after.pieces[0].total_cm == original.total_cm
    assert "sincal:lap-dim" not in _group_definition(after, "entrada")[1]


def test_removing_all_middle_pieces_does_not_join_initial_and_terminal():
    state, _ = state_and_assembly()
    state["geometry"]["ancho_cm"] = 2300
    assembly = build_footing_assembly(*domain(state))
    assert assembly.is_valid, assembly.schedule.issues
    before = detail(state)
    removed = [bar for bar in assembly.bars if bar.key == "mesh_x" and bar.piece_role == "intermedia"]
    assert removed
    remove(state, *removed)
    after = detail(state)
    assert [piece.mark for piece in after.pieces] == ["1", "2A"]
    assert after.laps_m == ()
    assert all(offset[0] == 0 for offset in after.offsets_m)
    assert after.pieces[1].main_start_x_m > after.pieces[0].main_end_x_m
    for piece in after.pieces:
        original = next(item for item in before.pieces if item.mark == piece.mark)
        assert piece.vertices_m == original.vertices_m
        assert piece.total_cm == original.total_cm
    group = preview(state)["splice_groups"][0]
    assert group["lap_cm"] == 0
    assert all(not piece["lap_segments_m"] for piece in group["pieces"])
    assert "sincal:lap-dim" not in _group_definition(after, "entrada")[1]


def test_marks_remaining_in_disjoint_runs_do_not_imply_a_physical_splice():
    state, assembly = state_and_assembly()
    runs = defaultdict(list)
    for bar in assembly.bars:
        if bar.key == "mesh_x":
            runs[bar.placement_id].append(bar)
    remove(state, *(pieces[index % 2] for index, pieces in enumerate(runs.values())))
    after = detail(state)
    assert [piece.mark for piece in after.pieces] == ["1", "2"]
    assert all(piece.quantity > 0 for piece in after.pieces)
    assert after.laps_m == ()


def test_physical_lap_is_clipped_to_the_partner_that_remains():
    initial = SimpleNamespace(id="initial", placement_id="run", main_start_m=(0, 0, 0),
                              main_end_m=(1, 0, 0), lap_segments_m=())
    continuation = SimpleNamespace(id="continuation", placement_id="run", main_start_m=(.5, 0, 0),
                                   main_end_m=(2, 0, 0), lap_segments_m=(((.5, 0, 0), (1.5, 0, 0)),))
    lap, = physical_laps((initial, continuation))
    assert lap.piece_id == continuation.id and lap.partner_id == initial.id
    assert lap.start_m == (.5, 0, 0) and lap.end_m == (1, 0, 0)
    assert lap.length_cm == 50
    assert physical_laps((continuation,)) == ()
