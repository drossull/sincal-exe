"""Real exterior-wing previews, shared scene quantities and saved projects."""
from collections import Counter
from copy import deepcopy
import json
import math

import pytest

from sincal.rebar.model import DENSIDAD_ACERO_KG_M3
from sincal.web.abutment_scene import build_scene
from sincal.web.rebar import from_project as footing_states
from sincal.web.server import Store
from sincal.web.wing_exterior import from_project, preview
from sincal.web.wing_geometry import build_wing_profile, extract_geometry
from test_web_wing_exterior import configured


def configured_extension(side="left", instance="entrada", skew=-12, rotation=0):
    project, _, original = configured(side, instance, extension=True)
    project["parametros_generales"]["angulo_esviaje_puente"] = skew
    json_side = "izq" if side == "left" else "der"
    project["estribos"][f"rotacion_muro_ala_{instance}_{json_side}"] = rotation
    abutment = footing_states(project)[instance]
    state = deepcopy(original)
    state["geometry"] = from_project(project, instance, side, abutment)["state"]["geometry"]
    abutment["wings"] = {side: state}
    return project, abutment, state


def assert_valid(result):
    assert result["valid"], result["issues"]


def assert_counts(result):
    counts = Counter(bar["mark"] for bar in result["bars"])
    assert counts == {mark["mark"]: mark["quantity"] for mark in result["marks"]}
    assert counts == {detail["mark"]: detail["quantity"] for detail in result["details"]}
    assert sum(mark["total_length_cm"] for mark in result["marks"]) == sum(bar["length_cm"] for bar in result["bars"])
    expected_kg = sum(bar["length_cm"]/100*math.pi*(bar["diameter_mm"]/2000)**2*DENSIDAD_ACERO_KG_M3
                      for bar in result["bars"])
    assert result["total_kg"] == pytest.approx(expected_kg)
    for mark in result["marks"]:
        family = [bar for bar in result["bars"] if bar["mark"] == mark["mark"]]
        detail = next(detail for detail in result["details"] if detail["mark"] == mark["mark"])
        lengths = Counter(bar["length_cm"] for bar in family)
        assert mark["total_length_cm"] == sum(length*count for length, count in lengths.items())
        assert mark["unit_length_cm"] == max(lengths)
        assert detail["total_cm"] == max(lengths)
        assert detail["developed_length_cm"] == pytest.approx(max(bar["developed_length_cm"] for bar in family))
        assert detail["length_variants"] == mark["length_variants"]
        if mark["length_variants"]:
            assert {item["length_cm"]: item["quantity"] for item in mark["length_variants"]} == lengths


@pytest.mark.parametrize("side", ("left", "right"))
@pytest.mark.parametrize("instance", ("entrada", "salida"))
@pytest.mark.parametrize("skew", (-12, 12))
def test_active_extension_with_explicit_zero_rotation_keeps_source_and_scene_counts(side, instance, skew):
    project, abutment, state = configured_extension(side, instance, skew)
    before = deepcopy((project, abutment))
    metadata = extract_geometry(project, instance, side, abutment)
    assert metadata["extension_enabled"] is True
    assert metadata["source"]["rotation_degrees"] == 0
    assert metadata["source"]["skew_degrees"] == skew
    result = preview(project, instance, side, state, abutment)
    assert_valid(result)
    assert_counts(result)
    assert any(bar["key"].endswith("vertical_extension") for bar in result["bars"])
    scene = build_scene(project, instance, abutment, use_state_geometry=True)
    assert [bar for bar in scene["bars"] if bar["element_key"] == f"abutment.{side}_wing"] == result["bars"]
    assert all(mark["views"] == (("BB", "DD", "EE") if side == "left" else ("CC", "DD", "EE"))
               for mark in result["marks"])
    assert (project, abutment) == before


def inside_plane(vertices, indices):
    first, second, third = (vertices[index] for index in indices)
    a, b = ([end-start for start, end in zip(first, point)] for point in (second, third))
    normal = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    size = math.hypot(*normal)
    normal = tuple(value/size for value in normal)
    centre = tuple(sum(point[axis] for point in vertices)/len(vertices) for axis in range(3))
    if sum(n*(c-p) for n, c, p in zip(normal, centre, first)) < 0:
        normal = tuple(-value for value in normal)
    return lambda point: sum(n*(value-base) for n, value, base in zip(normal, point, first))


@pytest.mark.parametrize("side", ("left", "right"))
def test_short_extension_verticals_stop_at_real_diagonal_while_main_ones_anchor_in_footing(side):
    project, abutment, state = configured_extension(side)
    result = preview(project, "entrada", side, state, abutment)
    assert_valid(result)
    metadata = extract_geometry(project, "entrada", side, abutment)
    profile = build_wing_profile(metadata, state["geometry"])
    diagonal = inside_plane(profile["meshes"][1]["vertices"], (0, 1, 5))
    required = state["cover"]["diagonal_cm"]/100+state["vertical"]["diameter_mm"]/2000
    extension = [bar for bar in result["bars"] if bar["key"].endswith("vertical_extension")]
    main = [bar for bar in result["bars"] if bar["key"].endswith("vertical_main")]
    assert extension and main
    for bar in extension:
        # A rounded corner may sit farther inside than its theoretical corner;
        # the whole actual hook must nevertheless clear the diagonal plane.
        assert min(map(diagonal, bar["points"])) >= required-1e-8
        assert min(point[2] for point in bar["points"]) > profile["frame"]["origin_m"][2]
    expected_lower = abutment["cover"]["inferior_cm"]/100+state["vertical"]["diameter_mm"]/2000
    assert all(min(point[2] for point in bar["points"]) == pytest.approx(expected_lower) for bar in main)
    assert max(bar["length_cm"] for bar in extension) < max(bar["length_cm"] for bar in main)


def test_free_ala_hook_remains_40_cm_and_frontal_hook_is_independent():
    project, abutment, state = configured_extension()
    state["horizontal"]["hook_join_cm"] = 25
    initial = preview(project, "entrada", "left", state, abutment)
    assert_valid(initial)
    for bar in initial["bars"]:
        assert math.dist(*bar["vertices"][:2]) == pytest.approx(.4)
        assert math.dist(*bar["vertices"][-2:]) == pytest.approx(.25 if "horizontal" in bar["key"] else .4)
    state["horizontal"]["hook_join_cm"] = 55
    edited = preview(project, "entrada", "left", state, abutment)
    assert_valid(edited)
    assert_counts(edited)
    original = {bar["id"]: bar for bar in initial["bars"]}
    for bar in edited["bars"]:
        if "vertical" in bar["key"]:
            assert bar == original[bar["id"]]
        else:
            # The skewed free frontal face can also move the theoretical
            # corner to keep the longer hook covered; its main leg is exact.
            assert bar["signature"] != original[bar["id"]]["signature"]
            assert math.dist(*bar["vertices"][:2]) == pytest.approx(.4)
            assert math.dist(*bar["vertices"][-2:]) == pytest.approx(.55)


@pytest.mark.parametrize("side", ("left", "right"))
@pytest.mark.parametrize("instance", ("entrada", "salida"))
@pytest.mark.parametrize("rotation", (-5, 5))
def test_rotated_wing_horizontal_follows_both_faces_with_true_join_bend(side, instance, rotation):
    project, abutment, state = configured_extension(side, instance, rotation=rotation)
    before = deepcopy((project, abutment))
    result = preview(project, instance, side, state, abutment)
    assert_valid(result)
    assert_counts(result)
    metadata = extract_geometry(project, instance, side, abutment)
    assert metadata["source"]["rotation_degrees"] == rotation
    origin, inward = metadata["frame"]["origin_m"], metadata["frame"]["inward"]

    def depth(point):
        return sum((value-base)*direction for value, base, direction in zip(point, origin, inward))

    dv, dh = state["vertical"]["diameter_mm"]/1000, state["horizontal"]["diameter_mm"]/1000
    vertical_depth = state["cover"]["outside_cm"]/100+dv/2
    horizontal_depth = vertical_depth+dv/2+dh/2
    verticals = [bar for bar in result["bars"] if "vertical" in bar["key"]]
    horizontals = [bar for bar in result["bars"] if "horizontal" in bar["key"]]
    assert verticals and horizontals
    assert all(depth(bar["main_start"]) == pytest.approx(vertical_depth) for bar in verticals)
    for bar in horizontals:
        assert depth(bar["main_start"]) == pytest.approx(horizontal_depth)
        assert min(point[2] for point in bar["points"]) >= origin[2]
        angles = [math.degrees(4*math.atan(abs(bulge))) for bulge in bar["bulges"] if abs(bulge) > 1e-10]
        assert angles == pytest.approx([90, abs(rotation), 90])
        assert math.dist(*bar["vertices"][:2]) == pytest.approx(.4)
        assert math.dist(*bar["vertices"][-2:]) == pytest.approx(state["horizontal"]["hook_join_cm"]/100)
        assert all(point[2] == pytest.approx(bar["points"][0][2]) for point in bar["points"])
    scene = build_scene(project, instance, abutment, use_state_geometry=True)
    assert [bar for bar in scene["bars"] if bar["element_key"] == f"abutment.{side}_wing"] == result["bars"]
    assert (project, abutment) == before


def test_variable_piece_removal_updates_lengths_mass_and_only_that_wing():
    project, abutment, state = configured_extension()
    other = deepcopy(state)
    other["geometry"] = from_project(project, "entrada", "right", abutment)["state"]["geometry"]
    other["vertical"].update(mark_main="31", mark_extension="32")
    other["horizontal"].update(mark_main="33", mark_upper="34")
    abutment["wings"]["right"] = other
    initial = preview(project, "entrada", "left", state, abutment)
    assert_valid(initial)
    scene_before = build_scene(project, "entrada", abutment, use_state_geometry=True)
    chosen = max((bar for bar in initial["bars"] if bar["key"].endswith("vertical_extension")), key=lambda bar: bar["length_cm"])
    state["removed_pieces"].append({key: chosen[key] for key in ("id", "signature")})
    reduced = preview(project, "entrada", "left", state, abutment)
    assert_valid(reduced)
    assert_counts(reduced)
    assert {bar["id"] for bar in reduced["bars"]} == {bar["id"] for bar in initial["bars"]}-{chosen["id"]}
    assert initial["total_kg"]-reduced["total_kg"] == pytest.approx(chosen["length_cm"]/100*math.pi*(chosen["diameter_mm"]/2000)**2*DENSIDAD_ACERO_KG_M3)
    assert reduced["removed_bars"][0]["status"] == "removed"
    assert any(mark["length_variants"] for mark in reduced["marks"] if mark["mark"] == chosen["mark"])
    scene_after = build_scene(project, "entrada", abutment, use_state_geometry=True)
    assert [bar for bar in scene_after["bars"] if bar["element_key"] != "abutment.left_wing"] == [bar for bar in scene_before["bars"] if bar["element_key"] != "abutment.left_wing"]
    state["removed_pieces"].clear()
    assert preview(project, "entrada", "left", state, abutment)["bars"] == initial["bars"]


@pytest.mark.parametrize("reservation", ("other_wing", "manual_footing"))
def test_reserved_marks_include_other_wing_and_nonautomatic_footing(reservation):
    project, abutment, state = configured_extension()
    if reservation == "other_wing":
        other = deepcopy(state)
        other["geometry_confirmed"] = False
        abutment["wings"]["right"] = other
    else:
        abutment["rules"][0]["automatic"] = False
        state["vertical"]["mark_main"] = abutment["rules"][0]["mark"]
    result = preview(project, "entrada", "left", state, abutment)
    assert not result["valid"]
    assert result["bars"] == []
    assert any("reservadas" in issue["message"] for issue in result["issues"])


def test_nominal_unconfirmed_geometry_never_adds_wing_steel_to_scene():
    project, abutment, state = configured_extension()
    state["geometry_confirmed"] = False
    result = preview(project, "entrada", "left", state, abutment)
    assert not result["valid"]
    assert result["bars"] == []
    scene = build_scene(project, "entrada", abutment, use_state_geometry=True)
    assert not any(bar["element_key"] == "abutment.left_wing" for bar in scene["bars"])
    element = next(element for element in scene["elements"] if element["key"] == "abutment.left_wing")
    assert element["quality"] == "schematic"


def test_saved_project_restores_wing_edits_and_removal_without_changing_json_or_other_instance(tmp_path):
    project, abutment, state = configured_extension()
    original_json = deepcopy(project)
    original_preview = preview(project, "entrada", "left", state, abutment)
    assert_valid(original_preview)
    selected = next(bar for bar in original_preview["bars"] if bar["key"].endswith("vertical_extension"))
    state["removed_pieces"].append({key: selected[key] for key in ("id", "signature")})
    reduced = preview(project, "entrada", "left", state, abutment)
    exit_state = footing_states(project)["salida"]
    exit_wing = from_project(project, "salida", "left", exit_state)["state"]
    exit_state["wings"] = {"left": exit_wing}
    payload = {"data": project, "identification": {"ot": "G-TEST", "revision": "A", "structure_name": "Ala de prueba"},
               "rebar": {"entrada": abutment, "salida": exit_state}}
    store = Store(tmp_path/"wing-sessions.db")
    identity = store.save(payload)["id"]
    saved = store.get(identity)
    assert saved == json.loads(json.dumps(payload))
    assert saved["data"] == project == original_json
    restored_abutment = saved["rebar"]["entrada"]
    restored_state = restored_abutment["wings"]["left"]
    assert preview(saved["data"], "entrada", "left", restored_state, restored_abutment) == reduced
    assert saved["rebar"]["salida"] == exit_state
    assert saved["rebar"]["salida"]["wings"]["left"]["removed_pieces"] == []
    store.recover("wing-preview", saved)
    assert store.recover()["payload"] == saved
    restored_state["removed_pieces"] = []
    assert preview(saved["data"], "entrada", "left", restored_state, restored_abutment)["bars"] == original_preview["bars"]
    assert project == original_json
