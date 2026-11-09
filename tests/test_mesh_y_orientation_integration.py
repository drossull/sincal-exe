"""Automatic Y direction remains one physical source for scene and detailing.

These integration checks intentionally measure the output geometry rather than
calling the direction helper. No drawing or running CAD is inspected.
"""
from collections import Counter
from copy import deepcopy
import math

import pytest

from sincal.rebar.assembly import build_footing_assembly
from sincal.web.abutment_scene_rebar import build_footing_bars
from sincal.web.rebar import defaults, domain, preview, validate_draft
from sincal.web.server import Store


def state_for(skew, *, suple=False, length_cm=750):
    state = defaults()
    state["geometry"].update(esviaje_grados=skew, largo_cm=length_cm)
    state["rules"][2]["enabled"] = suple
    return state


def unrotate(point, skew):
    c, s = math.cos(math.radians(skew)), math.sin(math.radians(skew))
    x, y, z = point
    return c * x + s * y, -s * x + c * y, z


def measured_length_cm(vertices, bulges):
    result = 0.0
    for a, b, bulge in zip(vertices, vertices[1:], bulges):
        chord = math.dist(a, b)
        sweep = 4 * math.atan(abs(bulge))
        result += chord if sweep < 1e-10 else chord * sweep / (2 * math.sin(sweep / 2))
    return 100 * result


def assert_detail_matches_representative(detail, bars):
    # The representative is the longest real piece of its mark. Transform its
    # vertices into the bar's own plane, not an assumed global Y projection.
    representative = max((bar for bar in bars if bar.mark == detail["mark"]),
                         key=lambda bar: bar.developed_length_cm)
    assert detail["total_cm"] == representative.length_cm
    assert detail["measured_cm"] == pytest.approx(representative.developed_length_cm)
    assert len(detail["vertices_m"]) == len(representative.vertices_m)
    for actual, world in zip(detail["vertices_m"], representative.vertices_m):
        delta = tuple(value - origin for value, origin in zip(world, representative.origin_m))
        local = tuple(sum(a * b for a, b in zip(delta, axis))
                      for axis in (representative.axis_u, representative.axis_v))
        assert actual == pytest.approx(local)
    assert detail["bulges"] == pytest.approx(representative.bulges)


@pytest.mark.parametrize("skew", [0, -9, 9, -10, 10, -12, 12])
@pytest.mark.parametrize("suple", [False, True])
def test_scene_direction_lengths_quantities_and_details_follow_automatic_y_rule(skew, suple):
    state = state_for(skew, suple=suple)
    unchanged = deepcopy(state)
    assembly = build_footing_assembly(*domain(state))
    scene, web = build_footing_bars(state), preview(state)
    assert scene["valid"], scene["issues"]
    assert web["valid"], web["issues"]
    assert assembly.is_valid, assembly.schedule.issues
    assert state == unchanged
    assert {bar["id"]: bar["signature"] for bar in scene["bars"]} == {
        bar.id: bar.signature for bar in assembly.bars}
    families = ("mesh_y", "suple") if suple else ("mesh_y",)
    for family in families:
        bars = [bar for bar in scene["bars"] if bar["key"] == family]
        marks = [mark for mark in web["marks"] if mark["key"] == family]
        assert len(marks) == 1
        mark = marks[0]
        parallel = abs(skew) < 10
        expected = (math.sin(math.radians(skew)), math.cos(math.radians(skew)), 0.0) if parallel else (0.0, 1.0, 0.0)
        for bar in bars:
            # The shortest wedge piece has touching bend tangencies and no
            # straight segment between them. Its equal-length hook endpoints
            # still expose the real plan direction without dividing by zero.
            a, b = (unrotate(bar["vertices"][index], skew) for index in (0, -1))
            length = math.dist(a, b)
            assert tuple((end - start) / length for start, end in zip(a, b)) == pytest.approx(expected)
            assert measured_length_cm(bar["vertices"], bar["bulges"]) == pytest.approx(bar["developed_length_cm"])
            assert bar["length_cm"] <= 1200
            assert 0 <= bar["length_cm"] - bar["developed_length_cm"] < 1 + 1e-8
            assert bar["lap_segments"] == []
        lengths = Counter(bar["length_cm"] for bar in bars)
        if parallel:
            assert len(lengths) == 1
            assert not mark["length_variants"]
        else:
            assert len(lengths) > 1
            assert {item["length_cm"]: item["quantity"] for item in mark["length_variants"]} == lengths
        assert mark["quantity"] == len(bars)
        assert mark["total_length_cm"] == sum(bar["length_cm"] for bar in bars)
        assert mark["kg"] == pytest.approx(mark["total_length_cm"] / 100 * math.pi * (mark["diameter_mm"] / 2000) ** 2 * 7850)
        details = [detail for detail in web["details"] if detail["key"] == family]
        assert len(details) == 1
        assert_detail_matches_representative(details[0], assembly.bars)
        assert all(bend["bend_degrees"] == pytest.approx(90) for bend in details[0]["bends"])
        assert any(item["min_cm"] != item["max_cm"] for item in details[0]["partial_ranges_cm"]) is (not parallel)


@pytest.mark.parametrize("before_skew,after_skew", [(9, 10), (-9, -10), (10, 9), (-10, -9)])
def test_saved_single_piece_removal_cannot_follow_reused_id_across_direction_threshold(tmp_path, before_skew, after_skew):
    state = state_for(before_skew)
    original = build_footing_bars(state)
    assert original["valid"], original["issues"]
    chosen = next(bar for bar in original["bars"] if bar["id"] == "mesh_y:superior:2:0")
    record = {"id": chosen["id"], "signature": chosen["signature"]}
    state["rules"][1]["removed_pieces"] = [record]
    validate_draft(state)
    document = {"data": {}, "identification": {"ot": "Test", "revision": "A", "structure_name": "Umbral"},
                "rebar": {"entrada": state, "salida": state_for(0)}}
    store = Store(tmp_path / "orientation.db")
    restored = store.get(store.save(document)["id"])
    assert restored == document
    edited = restored["rebar"]["entrada"]
    scene = build_footing_bars(edited)
    assert scene["valid"], scene["issues"]
    assert chosen["id"] not in {bar["id"] for bar in scene["bars"]}
    old_quantity = next(mark for mark in preview(state_for(before_skew))["marks"] if mark["key"] == "mesh_y")["quantity"]
    assert next(mark for mark in preview(edited)["marks"] if mark["key"] == "mesh_y")["quantity"] == old_quantity - 1
    edited["geometry"]["esviaje_grados"] = after_skew
    validate_draft(edited)  # An unfinished edit can still be saved for review.
    unresolved_scene, unresolved_web = build_footing_bars(edited), preview(edited)
    assert not unresolved_scene["valid"] and not unresolved_web["valid"]
    assert unresolved_scene["bars"] == []
    assert unresolved_web["details"] == unresolved_web["splice_groups"] == []
    assert unresolved_scene["removed_bars"] == [{**record, "key": "mesh_y", "label": state["rules"][1]["label"], "status": "unresolved"}]
    assert edited["rules"][1]["removed_pieces"] == [record]
    edited["rules"][1]["removed_pieces"] = []
    current = build_footing_bars(edited)
    assert current["valid"], current["issues"]
    reused = next(bar for bar in current["bars"] if bar["id"] == chosen["id"])
    assert reused["signature"] != chosen["signature"]
    assert restored["rebar"]["salida"] == state_for(0)


@pytest.mark.parametrize("skew", [0, -9, 9])
@pytest.mark.parametrize("length_cm,roles", [(1500, {"inicial", "terminal"}), (2600, {"inicial", "intermedia", "terminal"})])
def test_long_constant_y_has_real_splices_and_deleting_one_piece_updates_every_output(skew, length_cm, roles):
    state = state_for(skew, length_cm=length_cm)
    state["rules"][1].update(continuation_mark="8", terminal_mark="9")
    for rule in state["rules"]:
        if rule["key"].startswith("lateral_"):
            rule["enabled"] = False
    assembly = build_footing_assembly(*domain(state))
    scene, web = build_footing_bars(state), preview(state)
    assert scene["valid"], scene["issues"]
    assert web["valid"], web["issues"]
    family = [bar for bar in scene["bars"] if bar["key"] == "mesh_y"]
    assert {bar["piece_role"] for bar in family} == roles
    assert all(bar["length_cm"] <= 1200 for bar in family)
    group = next(group for group in web["splice_groups"] if group["key"] == "mesh_y")
    run = [bar for bar in family if bar["placement_id"] == group["placement_id"]]
    assert len(run) == len(roles)
    assert {piece["id"] for piece in group["pieces"]} == {bar["id"] for bar in run}
    for first, second in zip(run, run[1:]):
        length = math.dist(first["main_start"], first["main_end"])
        axis = tuple((b-a)/length for a,b in zip(first["main_start"], first["main_end"]))
        delta = tuple(a-b for a,b in zip(first["main_end"], second["main_start"]))
        overlap = sum(value*direction for value,direction in zip(delta,axis))
        assert overlap*100 == pytest.approx(group["lap_cm"])
        assert math.hypot(*(value-overlap*direction for value,direction in zip(delta,axis))) == pytest.approx(
            (first["diameter_mm"]+second["diameter_mm"])/2000)
    for mark in (mark for mark in web["marks"] if mark["key"] == "mesh_y"):
        assert not mark["length_variants"]
        assert mark["quantity"] == sum(bar["mark"] == mark["mark"] for bar in family)
    for detail in (detail for detail in web["details"] if detail["key"] == "mesh_y"):
        assert_detail_matches_representative(detail, assembly.bars)
    chosen = run[0]
    state["rules"][1]["removed_pieces"] = [{"id": chosen["id"], "signature": chosen["signature"]}]
    remaining_scene, remaining_web = build_footing_bars(state), preview(state)
    assert remaining_scene["valid"] and remaining_web["valid"]
    assert {bar["id"] for bar in remaining_scene["bars"]} == {bar["id"] for bar in scene["bars"]} - {chosen["id"]}
    remaining_group = next(group for group in remaining_web["splice_groups"] if group["key"] == "mesh_y")
    assert remaining_group["removed_piece_count"] == 1
    assert chosen["id"] not in {piece["id"] for piece in remaining_group["pieces"]}
    assert remaining_group["pieces"][0]["lap_segments_m"] == ()
    if len(roles) == 2:
        assert remaining_group["lap_cm"] == 0
        survivor = next(bar for bar in remaining_scene["bars"] if bar["id"] == run[1]["id"])
        assert survivor["lap_cm"] == 0 and survivor["lap_segments"] == []
    old = next(mark for mark in web["marks"] if mark["mark"] == chosen["mark"])
    new = next(mark for mark in remaining_web["marks"] if mark["mark"] == chosen["mark"])
    assert new["quantity"] == old["quantity"] - 1
    assert new["total_length_cm"] == old["total_length_cm"] - chosen["length_cm"]


@pytest.mark.parametrize("skew", [-9, 9])
def test_long_constant_y_requires_explicit_continuation_mark(skew):
    state = state_for(skew, length_cm=1500)
    for rule in state["rules"]:
        if rule["key"].startswith("lateral_"):
            rule["enabled"] = False
    result = preview(state)
    assert not result["valid"]
    assert any("marca de continuación" in issue["message"] for issue in result["issues"])
    assert result["details"] == result["splice_groups"] == []
