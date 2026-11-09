"""Nominal wing formwork uses one reusable exterior profile, never CAD."""
from copy import deepcopy
import math

import pytest

from sincal.web.abutment_scene import build_scene
from sincal.web.rebar import from_project
from sincal.web.wing_geometry import GEOMETRY_FIELDS, build_wing_profile, extract_geometry
from tests.test_web_abutment_scene import example, find


def project(extension=True, skew=-12, rotation=0):
    data = example()
    data["parametros_generales"]["angulo_esviaje_puente"] = skew
    for instance in ("entrada", "salida"):
        data["estribos"].update({
            f"incluir_aletas_estribo_{instance}": extension,
            f"largo_aleta_{instance}": 3000,
            f"alto_minimo_aleta_{instance}": 1000,
            f"alto_maximo_aleta_{instance}": 2500,
            f"espesor_aleta_{instance}": 999,  # Only applies to transparent abutments.
            f"rotacion_muro_ala_{instance}_izq": rotation,
            f"rotacion_muro_ala_{instance}_der": rotation,
        })
    return data


@pytest.mark.parametrize("instance", ("entrada", "salida"))
@pytest.mark.parametrize("side", ("left", "right"))
@pytest.mark.parametrize("skew,rotation", ((0, 0), (-12, 0), (12, 15), (-12, -15)))
def test_extension_reaches_real_footing_edge_with_zero_lower_step(instance, side, skew, rotation):
    data = project(skew=skew, rotation=rotation)
    before = deepcopy(data)
    scene = build_scene(data, instance)
    profile = scene["wing_geometry"][side]
    geometry = profile["geometry"]
    assert set(geometry) == set(GEOMETRY_FIELDS)
    assert profile["quality"] == "nominal" and not profile["geometry_confirmed"]
    assert profile["extension_enabled"]
    assert geometry["extension_length_cm"] == 300
    assert geometry["tip_height_cm"] == 100
    assert profile["source"]["alto_maximo_aleta_cm"] == 250
    assert any("alto máximo" in issue for issue in profile["issues"])
    assert data == before
    assert profile == extract_geometry(data, instance, side)
    assert len(profile["main_profile_m"]) == len(profile["extension_profile_m"]) == 4
    extension = profile["extension_profile_m"]
    assert extension[0] == (geometry["main_length_cm"]/100, 0)
    assert extension[1][1] == pytest.approx((geometry["top_tip_cm"]-geometry["tip_height_cm"])/100)
    theta = math.radians(skew)
    edge_s = (-1 if instance == "entrada" else 1) * 7.5/(2*math.cos(theta))
    # Both corners of the diagonal's starting edge are on the actual footing
    # side and exactly at the concrete top, including with rotated wings.
    for x, y in profile["extension_footprint_m"][:2]:
        assert y-x*math.tan(theta) == pytest.approx(edge_s)
    extension_mesh = profile["meshes"][1]
    for index in (0, 4):
        assert extension_mesh["vertices"][index][2] == pytest.approx(1.5)
    assert extension_mesh["vertices"][1][2] == pytest.approx(extension_mesh["vertices"][5][2])
    assert extension_mesh["vertices"][6][2]-extension_mesh["vertices"][2][2] == pytest.approx(
        profile["inner_top_tip_delta_cm"]/100)
    mouldage = find(scene, "left_wing" if side == "left" else "right_wing")
    assert mouldage["meshes"] == profile["meshes"]
    assert profile["front_available_width_cm"] > geometry["thickness_cm"]
    assert profile["frame"]["front_inward"] == (1 if side == "left" else -1, 0, 0)


@pytest.mark.parametrize("side", ("left", "right"))
def test_without_extension_keeps_original_y_constant_end_and_has_no_fake_tip(side):
    data = project(extension=False)
    profile = extract_geometry(data, "entrada", side)
    assert not profile["extension_enabled"]
    assert profile["geometry"]["extension_length_cm"] == 0
    assert profile["extension_profile_m"] == profile["extension_footprint_m"] == ()
    assert len(profile["meshes"]) == 1
    assert profile["main_footprint_m"][2][1] == pytest.approx(profile["main_footprint_m"][3][1])
    assert not any("alto máximo" in issue for issue in profile["issues"])
    assert profile["geometry"]["main_length_cm"] == pytest.approx(
        profile["source"]["largo_muro_ala_efectivo_cm"])


@pytest.mark.parametrize("side", ("left", "right"))
def test_thickness_is_perpendicular_to_rotated_faces_and_front_has_its_own_axis(side):
    profile = extract_geometry(project(rotation=15), "entrada", side)
    theta, rho = map(math.radians, (-12, 15))
    expected = 50*abs(math.cos(rho)+math.tan(theta)*math.sin(rho))
    assert profile["geometry"]["thickness_cm"] == pytest.approx(expected)
    axis, inward = profile["frame"]["axis_u"], profile["frame"]["inward"]
    assert sum(a*b for a,b in zip(axis, inward)) == pytest.approx(0)
    assert profile["frame"]["front_axis_u"] == (0, -1, 0)
    assert abs(axis[0]) > .1
    origin = profile["frame"]["origin_m"]
    for (u,z), point in zip(profile["exterior_profile_m"], profile["exterior_vertices_m"]):
        if u < 0:
            assert point[0] == pytest.approx(origin[0])
        else:
            assert point[0] == pytest.approx(origin[0]+u*axis[0])


def test_manual_profile_edits_are_local_and_do_not_replace_source_or_global_walls():
    data = project()
    original = deepcopy(data)
    scene = build_scene(data, "entrada")
    metadata = scene["wing_geometry"]["left"]
    saved = deepcopy(metadata)
    changes = {"top_join_cm": metadata["geometry"]["top_join_cm"]+15,
               "top_edge_cm": metadata["geometry"]["top_edge_cm"]+25,
               "top_tip_cm": 300, "tip_height_cm": 90, "thickness_cm": 60}
    revised = build_wing_profile(metadata, changes)
    assert metadata == saved and data == original
    assert revised["geometry_edited"]
    assert revised["extension_profile_m"][1][1] == pytest.approx(2.1)
    assert revised["main_profile_m"][-1][1] == pytest.approx(changes["top_join_cm"]/100)
    assert any("frontal o espaldar" in issue for issue in revised["issues"])
    assert revised["source"] == metadata["source"]
    after = build_scene(data, "entrada")
    assert find(after, "front_wall") == find(scene, "front_wall")
    assert find(after, "back_wall") == find(scene, "back_wall")


def test_geometry_uses_draft_footing_dimensions_without_mutating_state_or_json():
    data = project()
    state = from_project(data)["entrada"]
    state["geometry"].update(largo_cm=850, alto_cm=180)
    saved = deepcopy(state), deepcopy(data)
    draft = extract_geometry(data, "entrada", "left", state)
    assert draft["geometry_edited"]
    assert draft["frame"]["origin_m"][2] == pytest.approx(1.8)
    theta = math.radians(-12)
    for x,y in draft["extension_footprint_m"][:2]:
        assert y-x*math.tan(theta) == pytest.approx(-8.5/(2*math.cos(theta)))
    assert (state,data) == saved


def test_height_compatibility_warning_is_recomputed_after_editing_the_tip():
    metadata = extract_geometry(project(), "entrada", "left")
    assert any("alto máximo" in issue for issue in metadata["issues"])
    revised = build_wing_profile(metadata, {"top_tip_cm": metadata["source"]["alto_maximo_aleta_cm"]})
    assert not any("alto máximo" in issue for issue in revised["issues"])
    assert metadata["source"]["alto_maximo_aleta_cm"] == 250


@pytest.mark.parametrize("missing", ("alto_minimo_aleta_entrada", "alto_maximo_aleta_entrada", "largo_aleta_entrada"))
def test_missing_extension_dimension_does_not_fabricate_geometry(missing):
    data = project()
    del data["estribos"][missing]
    scene = build_scene(data, "entrada")
    assert not scene.get("wing_geometry")
    assert any(missing in issue for issue in scene["issues"])
    with pytest.raises(ValueError, match=missing):
        extract_geometry(data, "entrada", "left")


@pytest.mark.parametrize("changes", ({"tip_height_cm": 0}, {"tip_height_cm": 10000},
                                     {"top_join_cm": float("nan")}, {"thickness_cm": True},
                                     {"back_thickness_cm": 10000}, {"main_length_cm": 0}))
def test_invalid_confirmed_measurements_are_not_silently_corrected(changes):
    metadata = extract_geometry(project(), "entrada", "left")
    with pytest.raises(ValueError):
        build_wing_profile(metadata, changes)


def test_legacy_side_aliases_map_to_standard_public_names():
    data = project()
    scene = build_scene(data, "entrada")
    assert set(scene["wing_geometry"]) == {"left", "right"}
    assert extract_geometry(data, "entrada", "izq") == scene["wing_geometry"]["left"]
    assert extract_geometry(data, "entrada", "der") == scene["wing_geometry"]["right"]
