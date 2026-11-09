"""Interior and exterior reinforcement share a wing without sharing pieces."""
from copy import deepcopy
import math

import pytest

from sincal.rebar.model import DENSIDAD_ACERO_KG_M3
from sincal.web.abutment_scene import build_scene
from sincal.web.server import Store
from sincal.web.wing_exterior import from_project, preview, validate_draft
from sincal.web.wing_geometry import extract_geometry
from test_wing_exterior_integration import configured_extension, assert_counts, assert_valid


def configured_both(side="left", instance="entrada", rotation=0, skew=-12):
    project, abutment, state = configured_extension(side, instance, skew=skew, rotation=rotation)
    state["interior"] = {
        "enabled": True, "parameters_initialized": True,
        "vertical": deepcopy(state["vertical"]), "horizontal": deepcopy(state["horizontal"]),
        "removed_pieces": [],
    }
    state["interior"]["vertical"].update(mark_main="21", mark_extension="22")
    state["interior"]["horizontal"].update(mark_main="23", mark_upper="24")
    return project, abutment, state


def face_bars(result, mesh):
    return [bar for bar in result["bars"] if ("_inner_" in bar["key"]) == (mesh == "interior")]


def hook_direction(bar, end=False):
    tip, tangent = (bar["vertices"][-1], bar["vertices"][-2]) if end else bar["vertices"][:2]
    delta = tuple(a-b for a, b in zip(tip, tangent))
    length = math.hypot(*delta)
    return tuple(value/length for value in delta)


@pytest.mark.parametrize("side", ("left", "right"))
@pytest.mark.parametrize("instance", ("entrada", "salida"))
@pytest.mark.parametrize("rotation", (-5, 0, 5))
def test_interior_real_hook_directions_quantities_and_scene(side, instance, rotation):
    project, abutment, state = configured_both(side, instance, rotation=rotation)
    before = deepcopy((project, abutment))
    result = preview(project, instance, side, state, abutment)
    assert_valid(result)
    assert_counts(result)
    interior, exterior = face_bars(result, "interior"), face_bars(result, "exterior")
    assert interior and exterior
    assert {bar["id"] for bar in interior}.isdisjoint(bar["id"] for bar in exterior)
    assert {bar["mark"] for bar in interior}.isdisjoint(bar["mark"] for bar in exterior)
    metadata = extract_geometry(project, instance, side, abutment)
    inward = metadata["frame"]["inward"]
    outward = tuple(-value for value in inward)
    front_inward = metadata["frame"]["front_inward"]
    for bar in interior:
        group = bar["key"].removeprefix(f"wing_{side}_inner_")
        if group == "vertical_main":
            expected_start, expected_end = inward, outward
        elif group == "vertical_extension":
            expected_start = expected_end = outward
        else:
            expected_start, expected_end = outward, front_inward
        assert hook_direction(bar) == pytest.approx(expected_start)
        assert hook_direction(bar, True) == pytest.approx(expected_end)
        assert math.dist(*bar["vertices"][:2]) == pytest.approx(.4)
        assert math.dist(*bar["vertices"][-2:]) == pytest.approx(.4)
    assert all(set(mark["projection_notes"].values()) == {"armadura interior"}
               for mark in result["marks"] if "_inner_" in mark["key"])
    scene = build_scene(project, instance, abutment, use_state_geometry=True)
    assert [bar for bar in scene["bars"] if bar["element_key"] == f"abutment.{side}_wing"] == result["bars"]
    assert (project, abutment) == before


def test_legacy_state_without_interior_keeps_previous_exterior_and_ids():
    project, abutment, state = configured_extension()
    baseline = preview(project, "entrada", "left", state, abutment)
    state.pop("interior", None)
    validate_draft(state)
    legacy = preview(project, "entrada", "left", state, abutment)
    assert_valid(legacy)
    for field in ("bars", "marks", "details", "total_kg", "removed_bars"):
        assert legacy[field] == baseline[field]


def test_legacy_interior_without_initialized_flag_still_validates():
    project, abutment, state = configured_both()
    initial = preview(project, "entrada", "left", state, abutment)
    del state["interior"]["parameters_initialized"]
    validate_draft(state)
    assert preview(project, "entrada", "left", state, abutment) == initial


def test_interior_variable_piece_removal_changes_only_its_counts_weight_and_detail():
    project, abutment, state = configured_both()
    initial = preview(project, "entrada", "left", state, abutment)
    assert_valid(initial)
    selected = max((bar for bar in face_bars(initial, "interior") if bar["key"].endswith("vertical_extension")),
                   key=lambda bar: bar["length_cm"])
    state["interior"]["removed_pieces"].append({key: selected[key] for key in ("id", "signature")})
    reduced = preview(project, "entrada", "left", state, abutment)
    assert_valid(reduced)
    assert_counts(reduced)
    assert face_bars(reduced, "exterior") == face_bars(initial, "exterior")
    assert {bar["id"] for bar in reduced["bars"]} == {bar["id"] for bar in initial["bars"]}-{selected["id"]}
    assert initial["total_kg"]-reduced["total_kg"] == pytest.approx(
        selected["length_cm"]/100*math.pi*(selected["diameter_mm"]/2000)**2*DENSIDAD_ACERO_KG_M3)
    assert any(record["id"] == selected["id"] and record["status"] == "removed" for record in reduced["removed_bars"])
    state["interior"]["removed_pieces"].clear()
    assert preview(project, "entrada", "left", state, abutment) == initial


@pytest.mark.parametrize("invalid_mesh", ("interior", "exterior"))
def test_invalid_active_mesh_retains_the_other_mesh_without_claiming_full_validity(invalid_mesh):
    project, abutment, state = configured_both()
    initial = preview(project, "entrada", "left", state, abutment)
    assert_valid(initial)
    failed = state["interior"] if invalid_mesh == "interior" else state
    failed["horizontal"]["hook_ala_cm"] = 200
    result = preview(project, "entrada", "left", state, abutment)
    assert not result["valid"]
    other = "exterior" if invalid_mesh == "interior" else "interior"
    assert result["bars"] == face_bars(initial, other)
    assert_counts(result)


def test_incomplete_enabled_interior_does_not_hide_valid_exterior():
    project, abutment, state = configured_extension()
    initial = preview(project, "entrada", "left", state, abutment)
    state["interior"]["enabled"] = True
    assert state["interior"]["vertical"]["diameter_mm"] is None
    result = preview(project, "entrada", "left", state, abutment)
    assert not result["valid"]
    assert result["bars"] == initial["bars"]
    assert result["marks"] == initial["marks"]
    assert result["details"] == initial["details"]
    assert result["total_kg"] == initial["total_kg"]


@pytest.mark.parametrize("cause", ("duplicate_mark", "unconfirmed_geometry", "wrong_order"))
def test_global_block_clears_all_mesh_quantities_and_geometry(cause):
    project, abutment, state = configured_both()
    if cause == "duplicate_mark":
        state["interior"]["vertical"]["mark_main"] = state["vertical"]["mark_main"]
    elif cause == "unconfirmed_geometry":
        state["geometry_confirmed"] = False
    else:
        state["outer_family"] = "horizontal"
    result = preview(project, "entrada", "left", state, abutment)
    assert not result["valid"]
    assert result["bars"] == result["marks"] == result["details"] == []
    assert result["total_kg"] == 0


def test_disabled_interior_keeps_its_mark_reservation_but_does_not_count_steel():
    project, abutment, state = configured_both()
    initial = preview(project, "entrada", "left", state, abutment)
    assert_valid(initial)
    state["interior"]["enabled"] = False
    disabled = preview(project, "entrada", "left", state, abutment)
    assert_valid(disabled)
    assert disabled["bars"] == face_bars(initial, "exterior")
    state["vertical"]["mark_main"] = state["interior"]["vertical"]["mark_main"]
    conflict = preview(project, "entrada", "left", state, abutment)
    assert not conflict["valid"]
    assert not conflict["bars"]
    assert any("reservadas" in issue["message"] for issue in conflict["issues"])


def test_opposed_straight_layer_collision_blocks_even_the_otherwise_valid_exterior():
    project, abutment, state = configured_both(skew=0)
    state["geometry"]["thickness_cm"] = 18
    for mesh in (state, state["interior"]):
        mesh["vertical"].update(hook_bottom_cm=1, hook_top_cm=1)
        mesh["horizontal"].update(hook_ala_cm=1, hook_join_cm=1)
    state["interior"]["vertical"]["diameter_mm"] = 36
    state["interior"]["horizontal"]["diameter_mm"] = 36
    state["interior"]["enabled"] = False
    exterior_alone = preview(project, "entrada", "left", state, abutment)
    assert_valid(exterior_alone)
    assert exterior_alone["bars"]
    state["interior"]["enabled"] = True
    result = preview(project, "entrada", "left", state, abutment)
    assert not result["valid"]
    assert any("capas rectas" in issue["message"] and "superponen" in issue["message"] for issue in result["issues"])
    assert result["bars"] == result["marks"] == result["details"] == []
    assert result["total_kg"] == 0


@pytest.mark.parametrize("owner", ("manual_footing", "other_wing_disabled_interior"))
def test_interior_mark_conflict_with_other_element_is_global(owner):
    project, abutment, state = configured_both()
    assert_valid(preview(project, "entrada", "left", state, abutment))
    if owner == "manual_footing":
        abutment["rules"][0]["automatic"] = False
        taken_mark = abutment["rules"][0]["mark"]
    else:
        other = deepcopy(state)
        other["geometry"] = from_project(project, "entrada", "right", abutment)["state"]["geometry"]
        other["vertical"].update(mark_main="31", mark_extension="32")
        other["horizontal"].update(mark_main="33", mark_upper="34")
        other["interior"]["vertical"].update(mark_main="41", mark_extension="42")
        other["interior"]["horizontal"].update(mark_main="43", mark_upper="44")
        other["interior"]["enabled"] = False
        abutment["wings"]["right"] = other
        taken_mark = "41"
    state["interior"]["vertical"]["mark_main"] = taken_mark
    result = preview(project, "entrada", "left", state, abutment)
    assert not result["valid"]
    assert any("reservadas" in issue["message"] for issue in result["issues"])
    assert result["bars"] == result["marks"] == result["details"] == []
    assert result["total_kg"] == 0


def test_exterior_identity_in_interior_removal_cannot_delete_the_other_mesh():
    project, abutment, state = configured_both()
    initial = preview(project, "entrada", "left", state, abutment)
    assert_valid(initial)
    wrong_target = face_bars(initial, "exterior")[0]
    state["interior"]["removed_pieces"].append({key: wrong_target[key] for key in ("id", "signature")})
    result = preview(project, "entrada", "left", state, abutment)
    assert not result["valid"]
    assert result["bars"] == face_bars(initial, "exterior")
    assert any(record["id"] == wrong_target["id"] and record["status"] == "unresolved" for record in result["removed_bars"])


def test_saved_interior_and_exterior_removals_restore_independently(tmp_path):
    project, abutment, state = configured_both()
    original_json = deepcopy(project)
    initial = preview(project, "entrada", "left", state, abutment)
    assert_valid(initial)
    interior = face_bars(initial, "interior")[0]
    exterior = face_bars(initial, "exterior")[0]
    state["interior"]["removed_pieces"].append({key: interior[key] for key in ("id", "signature")})
    state["removed_pieces"].append({key: exterior[key] for key in ("id", "signature")})
    reduced = preview(project, "entrada", "left", state, abutment)
    assert_valid(reduced)
    payload = {"data": project, "identification": {"ot": "G-TEST", "revision": "A", "structure_name": "Dos mallas del ala"},
               "rebar": {"entrada": abutment}}
    store = Store(tmp_path/"inner-wing.db")
    saved = store.get(store.save(payload)["id"])
    restored_abutment = saved["rebar"]["entrada"]
    restored = restored_abutment["wings"]["left"]
    assert restored["interior"]["parameters_initialized"] is True
    assert restored["interior"]["removed_pieces"] == state["interior"]["removed_pieces"]
    assert restored["removed_pieces"] == state["removed_pieces"]
    assert preview(saved["data"], "entrada", "left", restored, restored_abutment) == reduced
    restored["interior"]["removed_pieces"].clear()
    partial = preview(saved["data"], "entrada", "left", restored, restored_abutment)
    assert interior["id"] in {bar["id"] for bar in partial["bars"]}
    assert exterior["id"] not in {bar["id"] for bar in partial["bars"]}
    assert saved["data"] == project == original_json
