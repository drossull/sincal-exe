"""Editing a lap changes the physical pieces, not only their preview labels."""
from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
import math

import pytest

from sincal.cad.zapata_views import project_footing_assembly
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.detail import build_detail_groups, polyline_developed_length_m
from sincal.web.abutment_scene_rebar import build_footing_bars
from sincal.web.rebar import defaults, domain, preview, validate_draft


def grouped(assembly):
    groups = defaultdict(list)
    for bar in assembly.bars:
        groups[bar.placement_id].append(bar)
    return groups


@pytest.mark.parametrize("skew", [0, -12, 12])
def test_first_length_repositions_the_lap_without_changing_envelope_or_lap_length(skew):
    state = defaults()
    state["geometry"]["esviaje_grados"] = skew
    original = build_footing_assembly(*domain(state))
    state["rules"][0]["first_piece_cm"] = 900
    state["rules"][3]["first_piece_cm"] = 700
    geometry, cover, rules = domain(state)
    edited = build_footing_assembly(geometry, cover, rules)
    assert edited.is_valid, edited.schedule.issues
    before = grouped(original)
    for key, run in grouped(edited).items():
        assert run[0].vertices_m[0] == pytest.approx(before[key][0].vertices_m[0])
        assert run[-1].vertices_m[-1] == pytest.approx(before[key][-1].vertices_m[-1])
        assert run[0].main_start_m == pytest.approx(before[key][0].main_start_m)
        assert run[-1].main_end_m == pytest.approx(before[key][-1].main_end_m)
        if run[0].key not in ("mesh_x", "lateral_x"):
            assert run == before[key]
            continue
        assert run[0].developed_length_cm == pytest.approx(900 if run[0].key == "mesh_x" else 700)
        assert all(bar.length_cm <= 1200 for bar in run)
        for first, second in zip(run, run[1:]):
            assert math.dist(first.origin_m,second.origin_m) == pytest.approx(first.diameter_mm/1000)
            assert sum((a-b)*u for a,b,u in zip(first.main_end_m,second.main_start_m,first.axis_u))*100 == pytest.approx(first.lap_length_cm)
            assert math.dist(second.lap_segments_m[0][1],first.main_end_m) == pytest.approx(first.diameter_mm/1000)
        # Coverage is unchanged after subtracting the physical overlap of pieces.
        def net_length(bars):
            return sum(bar.developed_length_cm for bar in bars) - sum(bar.lap_length_cm for bar in bars[1:])
        assert net_length(run) == pytest.approx(net_length(before[key]))
    marks = {mark.mark: mark for mark in edited.schedule.marks}
    for group in build_detail_groups(edited.schedule, rules, geometry):
        for piece in group.pieces:
            actual = next(bar for bar in edited.bars if bar.mark == piece.mark)
            assert polyline_developed_length_m(piece) * 100 == pytest.approx(
                marks[piece.mark].shape_data["developed_length_cm"])
            if piece.mark in ("1", "4"):
                assert piece.total_cm == actual.length_cm
    projected = project_footing_assembly(edited, "FR")
    prior = {piece.source_id: piece for piece in project_footing_assembly(original, "FR")}
    first = next(piece for piece in projected if piece.mark == "1" and piece.kind == "polyline")
    assert first.vertices_m[-1] != prior[first.source_id].vertices_m[-1]
    continuation = next(piece for piece in projected if piece.mark == "2" and piece.kind == "polyline")
    assert math.dist(*continuation.lap_segments_m[0]) * 100 == pytest.approx(150)
    scene = build_footing_bars(state)
    assert scene["valid"]
    assert all(bar["developed_length_cm"] == pytest.approx(900)
               for bar in scene["bars"] if bar["mark"] == "1")


def test_shorter_first_piece_can_require_an_additional_commercial_piece():
    state = defaults()
    state["geometry"]["ancho_cm"] = 1500
    original = build_footing_assembly(*domain(state))
    state["rules"][0]["first_piece_cm"] = 500
    edited = build_footing_assembly(*domain(state))
    assert edited.is_valid, edited.schedule.issues
    before = grouped(original)["mesh_x:superior:0"]
    after = grouped(edited)["mesh_x:superior:0"]
    assert len(before) == 2 and len(after) == 3
    assert [bar.mark for bar in after] == ["1", "2", "2A"]
    assert [bar.piece_role for bar in after] == ["inicial", "intermedia", "terminal"]
    assert after[0].developed_length_cm == pytest.approx(500)
    assert after[1].developed_length_cm == pytest.approx(1200)
    assert after[-1].length_cm <= 1200
    for first, second in zip(after, after[1:]):
        assert sum((a-b)*u for a,b,u in zip(first.main_end_m,second.main_start_m,first.axis_u))*100 == pytest.approx(150)


@pytest.mark.parametrize("width,length", [(1159.6, 200), (1050, 1200), (1159.6, 100)])
def test_manual_length_does_not_silently_clamp_or_cut_into_hook(width, length):
    state = defaults()
    state["geometry"]["ancho_cm"] = width
    state["rules"][0]["first_piece_cm"] = length
    result = preview(state)
    assert not result["valid"]
    assert any("primer fierro" in issue["message"] for issue in result["issues"])
    assert result["details"] == result["splice_groups"] == []


def test_manual_setting_does_not_create_an_unneeded_lap():
    state = defaults()
    state["geometry"]["ancho_cm"] = 800
    original = build_footing_assembly(*domain(state))
    state["rules"][0]["first_piece_cm"] = 500
    edited = build_footing_assembly(*domain(state))
    assert edited == original
    assert not preview(state)["splice_groups"]


@pytest.mark.parametrize("value", [None, True, "900", float("nan"), float("inf"), -1, 1201])
def test_manual_length_is_validated_at_the_web_and_model_boundaries(value):
    state = defaults()
    state["rules"][0]["first_piece_cm"] = value
    with pytest.raises(ValueError, match="first_piece_cm"):
        domain(state)
    geometry, cover, rules = domain(defaults())
    rules[0] = replace(rules[0], first_piece_cm=value)
    assert not build_footing_assembly(geometry, cover, rules).is_valid


def test_manual_length_is_not_accepted_for_a_family_without_a_splice_recipe():
    state = defaults()
    state["rules"][1]["first_piece_cm"] = 500
    result = preview(state)
    assert not result["valid"]
    assert any("reparto de empalmes" in issue["message"] for issue in result["issues"])


def test_old_drafts_default_to_auto_and_unfinished_fields_can_be_saved_unchanged():
    current = defaults()
    old = deepcopy(current)
    for rule in old["rules"]:
        del rule["first_piece_cm"]
    assert preview(old) == preview(current)
    unfinished = deepcopy(current)
    unfinished["rules"][0]["first_piece_cm"] = None
    validate_draft(unfinished)
    assert unfinished["rules"][0]["first_piece_cm"] is None


def test_splice_preview_is_the_same_physical_run_without_display_offsets(monkeypatch):
    from sincal.web import rebar
    state = defaults()
    state["geometry"]["esviaje_grados"] = -12
    state["rules"][0]["first_piece_cm"] = 900
    assembly = build_footing_assembly(*domain(state))
    calls = []
    def build_once(*args):
        calls.append(args)
        return assembly
    monkeypatch.setattr(rebar, "build_footing_assembly", build_once)
    result = preview(state)
    assert len(calls) == 1
    assert {group["key"] for group in result["splice_groups"]} == {"mesh_x", "lateral_x"}
    for group in result["splice_groups"]:
        run = grouped(assembly)[group["placement_id"]]
        for piece, bar in zip(group["pieces"], run):
            assert piece["id"] == bar.id and piece["mark"] == bar.mark
            assert piece["bulges"] == bar.bulges
            for local, world in zip(piece["points_m"], bar.points_m):
                rebuilt = tuple(group["frame_origin_m"][i] + sum(local[j]*group["frame_axes"][j][i]
                                for j in range(3)) for i in range(3))
                assert rebuilt == pytest.approx(world)
        assert group["main_start_m"] == group["pieces"][0]["main_start_m"]
        assert group["main_end_m"] == group["pieces"][-1]["main_end_m"]
        for first, second in zip(group["pieces"], group["pieces"][1:]):
            assert first["main_end_m"][0] == pytest.approx(second["lap_segments_m"][0][1][0])
            assert math.dist(first["main_end_m"], second["lap_segments_m"][0][1]) == pytest.approx(group["diameter_mm"]/1000)
            assert second["main_start_m"] == pytest.approx(second["lap_segments_m"][0][0])
            assert math.dist(*second["lap_segments_m"][0]) * 100 == pytest.approx(group["lap_cm"])
