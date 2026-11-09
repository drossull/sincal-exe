from collections import Counter
from copy import deepcopy
import math

import pytest

from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import build_zapata_schedule
from sincal.web.abutment_scene_rebar import build_footing_bars
from sincal.web.rebar import defaults, domain


@pytest.mark.parametrize("state", [None, {}, [], {"geometry": {}}, {"rules": None}])
def test_missing_or_incomplete_state_does_not_invent_reinforcement(state):
    result = build_footing_bars(state)
    assert result["bars"] == []
    assert not result["valid"]
    assert result["issues"]


@pytest.mark.parametrize("skew", [0, -12, 12])
def test_all_enabled_families_are_complete_pieces_and_match_the_schedule(skew):
    state = defaults()
    state["geometry"]["esviaje_grados"] = skew
    for rule in state["rules"]:
        rule["enabled"] = True
    result = build_footing_bars(state)
    geometry, cover, rules = domain(state)
    schedule = build_zapata_schedule(geometry, cover, rules)
    assert result["valid"], result["issues"]
    assert result["representation"] == "physical_pieces"
    assert {bar["key"] for bar in result["bars"]} == {
        "mesh_x", "mesh_y", "suple", "lateral_x", "lateral_y"}
    assert {bar["element_key"] for bar in result["bars"]} == {"abutment.footing"}
    assert len({bar["id"] for bar in result["bars"]}) == len(result["bars"])
    counts = Counter(bar["mark"] for bar in result["bars"])
    assert counts == {mark.mark: mark.quantity for mark in schedule.marks}
    for mark in schedule.marks:
        pieces = [bar for bar in result["bars"] if bar["mark"] == mark.mark]
        assert all(bar["marks"] == [mark.mark] for bar in pieces)
        assert sum(bar["length_cm"] for bar in pieces) == pytest.approx(mark.total_length_cm)
        if mark.length_variants:
            assert Counter(bar["length_cm"] for bar in pieces) == {
                variant.length_cm: variant.quantity for variant in mark.length_variants}
    assert "ganchos" in result["note"] and "empalmes" in result["note"]
    assert not any("pendiente" in issue for issue in result["issues"])


def test_real_bends_use_three_diameters_and_cut_rounding_never_stretches_the_shape():
    result = build_footing_bars(defaults())
    assert result["valid"], result["issues"]
    for bar in result["bars"]:
        curve_count = 0
        for index, bulge in enumerate(bar["bulges"][:-1]):
            if abs(bulge) < 1e-12:
                continue
            curve_count += 1
            chord = math.dist(bar["vertices"][index], bar["vertices"][index + 1])
            sweep = 4 * math.atan(abs(bulge))
            radius_m = chord / (2 * math.sin(sweep / 2))
            assert radius_m == pytest.approx(3 * bar["diameter_mm"] / 1000)
        expected = 2 if bar["piece_role"] == "completa" else 0 if bar["piece_role"] == "intermedia" else 1
        assert curve_count == expected
        if curve_count:
            assert len(bar["points"]) > len(bar["vertices"])
        assert 0 <= bar["length_cm"] - bar["developed_length_cm"] < 1 + 1e-8
        assert bar["length_cm"] <= 1200


def test_lap_pieces_keep_their_individual_marks_shapes_and_required_overlap():
    state = defaults()
    # Enough length to require an initial, an intermediate and a terminal piece.
    state["geometry"]["ancho_cm"] = 2600
    result = build_footing_bars(state)
    assert result["valid"], result["issues"]
    family = [bar for bar in result["bars"] if bar["key"] == "mesh_x"]
    placement = [bar for bar in family if bar["placement_id"] == family[0]["placement_id"]]
    assert {bar["piece_role"] for bar in placement} == {"inicial", "intermedia", "terminal"}
    assert len({bar["mark"] for bar in placement}) == 3
    assert all(bar["lap_cm"] == 150 for bar in placement)
    assert all(bar["length_cm"] <= 1200 for bar in placement)
    ordered = sorted(placement, key=lambda bar: bar["main_start"][0])
    for first, second in zip(ordered, ordered[1:]):
        assert (first["main_end"][0] - second["main_start"][0]) * 100 == pytest.approx(150)
        assert math.dist(first["main_start"][1:],second["main_start"][1:]) == pytest.approx(.022)
    overlaps = [segment for bar in placement for segment in bar["lap_segments"]]
    assert len(overlaps) == 2
    for first, last in overlaps:
        assert math.dist(first, last) == pytest.approx(1.5)
        assert first[1:] == pytest.approx(last[1:])
    for owner in placement:
        for segment, contact in zip(owner["lap_segments"], owner["lap_partners"]):
            assert contact["axis_distance_m"] == pytest.approx(.022)
            assert contact["piece_id"] in {bar["id"] for bar in placement}
            for point, partner_point in zip(segment,contact["segment"]):
                assert math.dist(point,partner_point) == pytest.approx(.022)


@pytest.mark.parametrize("skew", [0, -12, 12])
def test_scene_is_only_a_rigid_rotation_of_every_shared_physical_piece(skew):
    state = defaults()
    state["geometry"]["esviaje_grados"] = skew
    for rule in state["rules"]:
        rule["enabled"] = True
    geometry, cover, rules = domain(state)
    assembly = build_footing_assembly(geometry, cover, rules)
    result = build_footing_bars(state)
    assert result["valid"], result["issues"]
    by_id = {bar.id: bar for bar in assembly.bars}
    angle = math.radians(skew)
    for bar in result["bars"]:
        source = by_id[bar["id"]]
        assert len(bar["points"]) == len(source.points_m)
        for point, original in zip(bar["points"], source.points_m):
            x, y, z = original
            assert point == pytest.approx([
                math.cos(angle) * x - math.sin(angle) * y,
                math.sin(angle) * x + math.cos(angle) * y,
                z,
            ])
        assert bar["length_cm"] == source.length_cm
        assert bar["developed_length_cm"] == source.developed_length_cm
        assert len(bar["lap_segments"]) == len(source.lap_segments_m)
        for segment, original_segment in zip(bar["lap_segments"], source.lap_segments_m):
            for point, (x, y, z) in zip(segment, original_segment):
                assert point == pytest.approx([
                    math.cos(angle) * x - math.sin(angle) * y,
                    math.sin(angle) * x + math.cos(angle) * y, z,
                ])


def test_state_is_not_mutated_and_changing_distribution_origin_changes_placements():
    state = defaults()
    before = deepcopy(state)
    first = build_footing_bars(state)
    assert first["valid"], first["issues"]
    assert state == before
    state["rules"][0]["origin"] = "final"
    last = build_footing_bars(state)
    assert last["valid"], last["issues"]
    assert len(first["bars"]) == len(last["bars"])
    # Both boundary bars now remain tied to the exact bend tangencies. The
    # origin moves the short closing interval and the interior distribution.
    assert first["bars"][0]["points"] == last["bars"][0]["points"]
    assert any(a["points"] != b["points"] for a, b in zip(first["bars"], last["bars"]))


def test_different_diameters_do_not_hide_a_mesh_and_disabled_families_stay_absent():
    state = defaults()
    state["rules"][1]["diameter_mm"] = 16
    result = build_footing_bars(state)
    assert result["valid"], result["issues"]
    assert {bar["key"] for bar in result["bars"]} == {"mesh_x", "mesh_y", "lateral_x", "lateral_y"}
    assert all(bar["diameter_mm"] == 16 for bar in result["bars"] if bar["key"] == "mesh_y")
    state["rules"][3]["enabled"] = False
    state["rules"][4]["enabled"] = False
    assert {bar["key"] for bar in build_footing_bars(state)["bars"]} == {"mesh_x", "mesh_y"}
    state["rules"][0]["enabled"] = False
    assert build_footing_bars(state)["bars"] == []


@pytest.mark.parametrize("orientation", ["rectangular", "rectangular_rotado", "unknown"])
def test_unsupported_skew_orientation_is_not_sheared_to_fit(orientation):
    state = defaults()
    state["geometry"]["esviaje_grados"] = 12
    assert build_footing_bars(state, orientation=orientation)["bars"] == []


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), True, -5])
def test_invalid_geometry_omits_bars(value):
    state = defaults()
    state["geometry"]["alto_cm"] = value
    assert build_footing_bars(state)["bars"] == []


@pytest.mark.parametrize("role", ("inicial", "terminal"))
@pytest.mark.parametrize("skew", (0, -12))
def test_removing_splice_partner_removes_only_its_physical_overlap(role, skew):
    state = defaults()
    state["geometry"]["esviaje_grados"] = skew
    assembly = build_footing_assembly(*domain(state))
    assert assembly.is_valid, assembly.schedule.issues
    chosen = next(bar for bar in assembly.bars if bar.key == "mesh_x" and bar.piece_role == role)
    partner = next(bar for bar in assembly.bars if bar.placement_id == chosen.placement_id and bar.id != chosen.id)
    before = {bar["id"]: bar for bar in build_footing_bars(state)["bars"]}
    assert before[partner.id]["lap_cm"] > 0
    rule = next(rule for rule in state["rules"] if rule["key"] == chosen.key)
    rule["removed_pieces"] = [{"id": chosen.id, "signature": chosen.signature}]
    scene = build_footing_bars(state)
    assert scene["valid"], scene["issues"]
    after = {bar["id"]: bar for bar in scene["bars"]}
    assert chosen.id not in after
    assert after[partner.id]["lap_cm"] == 0
    assert after[partner.id]["lap_segments"] == []
    assert after[partner.id]["lap_partners"] == []
    for key in ("signature", "vertices", "points", "bulges", "length_cm"):
        assert after[partner.id][key] == before[partner.id][key]
    for bar in assembly.bars:
        if bar.placement_id != chosen.placement_id:
            assert after[bar.id] == before[bar.id]
