"""Individual deletions persist and reach the shared schedule, scene and CAD.

These checks generate local data/Lisp only. They never contact a running CAD
session or automatically regenerate a previously inserted DWG view.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import json
import math

import pytest

from sincal.cad.rebar_marks import build_marks_support
from sincal.cad.moldajes import MoldajeCandidate
from sincal.cad.zapata_views import build_zapata_lisp, project_footing_assembly
from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import DENSIDAD_ACERO_KG_M3
from sincal.web.abutment_scene_rebar import build_footing_bars
from sincal.web.abutment_scene import build_scene
from sincal.web.rebar import defaults, domain, preview
from sincal.web.server import Store
from tests.test_rebar_marks_cad import lisp_forms


def state_and_assembly(skew=0):
    state = defaults()
    state["geometry"]["esviaje_grados"] = skew
    assembly = build_footing_assembly(*domain(state))
    assert assembly.is_valid, assembly.schedule.issues
    return state, assembly


def remove(state, *bars):
    for bar in bars:
        rule = next(rule for rule in state["rules"] if rule["key"] == bar.key)
        records = list(rule.get("removed_pieces", ()))
        records.append({"id": bar.id, "signature": bar.signature})
        rule["removed_pieces"] = records


def by_mark(result):
    return {mark["mark"]: mark for mark in result["marks"]}


@pytest.mark.parametrize("key,role", (("mesh_x", "inicial"),
                                    ("mesh_x", "terminal"),
                                    ("mesh_y", "completa")))
def test_web_scene_preview_and_detail_remove_only_the_selected_piece(key, role):
    state, assembly = state_and_assembly()
    chosen = next(bar for bar in assembly.bars if bar.key == key and bar.piece_role == role)
    prior = preview(state)
    scene_before = build_footing_bars(state)
    visible = next(bar for bar in scene_before["bars"] if bar["id"] == chosen.id)
    assert visible["signature"] == chosen.signature
    remove(state, chosen)
    saved = deepcopy(state)

    result = preview(state)
    scene = build_footing_bars(state)
    assert result["valid"], result["issues"]
    assert scene["valid"], scene["issues"]
    assert state == saved
    assert {bar["id"] for bar in scene["bars"]} == {bar.id for bar in assembly.bars} - {chosen.id}
    assert Counter(bar["mark"] for bar in scene["bars"]) == {
        mark["mark"]: mark["quantity"] for mark in result["marks"]}
    before, after = by_mark(prior), by_mark(result)
    assert after[chosen.mark]["quantity"] == before[chosen.mark]["quantity"] - 1
    assert after[chosen.mark]["total_length_cm"] == before[chosen.mark]["total_length_cm"] - chosen.length_cm
    weight = chosen.length_cm / 100 * math.pi * (chosen.diameter_mm / 2000) ** 2 * DENSIDAD_ACERO_KG_M3
    assert result["total_kg"] == pytest.approx(prior["total_kg"] - weight)
    for mark, item in after.items():
        if mark != chosen.mark:
            assert item == before[mark]
    detail = next(piece for piece in result["details"] if piece["mark"] == chosen.mark)
    assert detail["quantity"] == after[chosen.mark]["quantity"]
    # An individual lap-piece deletion never deletes its continuation partner.
    partners = [bar.id for bar in assembly.bars if bar.placement_id == chosen.placement_id and bar.id != chosen.id]
    assert set(partners) <= {bar["id"] for bar in scene["bars"]}


def test_variable_series_totals_and_variants_use_surviving_lengths():
    state, assembly = state_and_assembly(-12)
    bars = [bar for bar in assembly.bars if bar.key == "mesh_y"]
    chosen = min(bars, key=lambda bar: bar.length_cm)
    before = preview(state)
    remove(state, chosen)
    after = preview(state)
    assert after["valid"], after["issues"]
    mark = by_mark(after)[chosen.mark]
    expected = Counter(bar.length_cm for bar in bars if bar.id != chosen.id)
    assert {variant["length_cm"]: variant["quantity"] for variant in mark["length_variants"]} == expected
    assert mark["quantity"] == len(bars) - 1
    assert mark["total_length_cm"] == sum(length * count for length, count in expected.items())
    assert mark["total_length_cm"] == by_mark(before)[chosen.mark]["total_length_cm"] - chosen.length_cm
    detail = next(piece for piece in after["details"] if piece["mark"] == chosen.mark)
    assert detail["length_variants"] == mark["length_variants"]


def test_deleting_last_piece_of_a_mark_removes_its_row_without_renumbering_others():
    state, assembly = state_and_assembly()
    chosen_mark = "1"
    remove(state, *(bar for bar in assembly.bars if bar.mark == chosen_mark))
    geometry, cover, rules = domain(state)
    remaining = build_footing_assembly(geometry, cover, rules)
    result = preview(state)
    assert result["valid"], result["issues"]
    assert {item["mark"] for item in result["marks"]} == {mark.mark for mark in assembly.schedule.marks} - {chosen_mark}
    assert chosen_mark not in {piece["mark"] for piece in result["details"]}
    source = build_marks_support(remaining.schedule, rules, "entrada")
    rows = source.split("(defun srb:fail", 1)[0]
    assert '"footing:mesh_x:base"' not in rows
    assert '"footing:mesh_x:continuation"' in rows
    for mark in remaining.schedule.marks:
        spacing = next(rule.spacing_cm for rule in rules if rule.key == mark.key)
        assert rows.count(f'"{mark.mark}" {mark.quantity} {mark.diameter_mm:g} {spacing:g})') == 1
    # The CAD synchronization remains scoped to owned element rows.
    assert "(srb:our-row srb:table-object row)" in source
    assert "(not (srb:preserved srb:table-object row))" in source


def test_saved_project_and_recovery_keep_removals_per_abutment(tmp_path):
    state, assembly = state_and_assembly(-12)
    chosen = next(bar for bar in assembly.bars if bar.key == "mesh_y")
    remove(state, chosen)
    # JSON transport matches the browser, including the new optional records.
    state = json.loads(json.dumps(state))
    original_data = {"estribos": {"tipo_estribo_entrada": "muro_lleno"}}
    payload = {"data": original_data, "identification": {
        "ot": "T", "revision": "A", "structure_name": "Puente de prueba"},
        "rebar": {"entrada": state, "salida": defaults()}}
    store = Store(tmp_path / "sessions.db")
    saved = store.save(payload)
    restored = store.get(saved["id"])
    assert restored == json.loads(json.dumps(payload))
    assert restored["data"] == original_data
    assert chosen.id not in {bar["id"] for bar in build_footing_bars(restored["rebar"]["entrada"])["bars"]}
    assert not any(rule.get("removed_pieces") for rule in restored["rebar"]["salida"]["rules"])
    assert preview(restored["rebar"]["salida"]) == preview(defaults())
    store.recover("fixture", restored)
    assert store.recover()["payload"] == restored
    next(rule for rule in restored["rebar"]["entrada"]["rules"] if rule["key"] == chosen.key)["removed_pieces"] = []
    assert chosen.id in {bar["id"] for bar in build_footing_bars(restored["rebar"]["entrada"])["bars"]}


def test_full_isometric_scene_keeps_removed_metadata_and_does_not_modify_json():
    state, assembly = state_and_assembly(-12)
    chosen = next(bar for bar in assembly.bars if bar.key == "mesh_y")
    remove(state, chosen)
    data = {"estribos": {"tipo_estribo_entrada": "muro_lleno"}}
    saved_data, saved_state = deepcopy(data), deepcopy(state)
    scene = build_scene(data, "entrada", state, use_state_geometry=True)
    assert {bar["id"] for bar in scene["bars"]} == {bar.id for bar in assembly.bars} - {chosen.id}
    assert {bar["id"] for bar in scene["removed_bars"]} == {chosen.id}
    assert scene["removed_bars"][0]["signature"] == chosen.signature
    assert data == saved_data
    assert state == saved_state


@pytest.mark.parametrize("skew", (0, -12))
def test_all_deleted_is_a_valid_zero_quantity_and_explicit_cad_cleanup(skew):
    state, before = state_and_assembly(skew)
    remove(state, *before.bars)
    geometry, cover, rules = domain(state)
    assembly = build_footing_assembly(geometry, cover, rules)
    result = preview(state)
    scene = build_footing_bars(state)
    assert assembly.is_valid, assembly.schedule.issues
    assert result["valid"], result["issues"]
    assert scene["valid"], scene["issues"]
    assert result["marks"] == result["details"] == result["splice_groups"] == []
    assert result["total_kg"] == 0
    assert not scene["bars"]
    assert {bar["id"] for bar in scene["removed_bars"]} == {bar.id for bar in before.bars}
    source = build_marks_support(assembly.schedule, rules, "entrada")
    assert "srb:rows '()" in source.split("(defun srb:fail", 1)[0]
    # An explicit regeneration still targets the old view so stale objects can
    # be removed; zero quantities do not create false zero-count mark rows.
    candidate = MoldajeCandidate("explicit_reference", "REF", "OK", 4, 1,
                                ((0, 0), (1, 0), (1, 1), (0, 1)))
    for view in ("FR", "AA", "BB", "CC", "FF"):
        assert project_footing_assembly(assembly, view) == ()
        cad = build_zapata_lisp(view, candidate, geometry, cover, rules, "entrada")
        assert f'(sincal:delete-old "ENTRADA_{view}_ZAP")' in cad
        assert '(cons 0 "CIRCLE")' not in cad
        assert '(cons 0 "LWPOLYLINE")' not in cad
        assert "(srb:sync-table)" in cad


def test_empty_cad_table_retains_a_fresh_data_row_and_requires_explicit_removals():
    state, before = state_and_assembly()
    geometry, cover, original_rules = domain(state)
    # A caller cannot turn a missing calculation into an instruction to erase
    # every managed row simply by passing an empty otherwise valid schedule.
    with pytest.raises(ValueError, match="No hay marcas calculadas"):
        build_marks_support(replace(before.schedule, marks=()), original_rules, "entrada")
    remove(state, *before.bars)
    geometry, cover, rules = domain(state)
    assembly = build_footing_assembly(geometry, cover, rules)
    source = build_marks_support(assembly.schedule, rules, "entrada")
    forms = lisp_forms(source)
    sync = next(form for form in forms if form.startswith("(defun srb:sync-table "))
    clear = next(form for form in forms if form.startswith("(defun srb:clear-last-owned-row "))
    reset = next(form for form in forms if form.startswith("(defun srb:reset-template-row "))
    # MARCA-SC recognizes tables with a title, header and at least one data
    # row. The last owned row becomes blank, with no deleted row's identity.
    assert "(if (= (vla-get-Rows srb:table-object) 3)" in sync
    assert "(srb:clear-last-owned-row srb:table-object)" in sync
    assert "(srb:our-row srb:table-object row)" in sync
    assert "(not (srb:preserved srb:table-object row))" in sync
    assert "(SCM:RowID table 2)" in clear
    assert '(srb:custom table 2 "SINCAL_REBAR_PIECE_V1")' in clear
    assert '(srb:put-custom table 2 "SINCAL_REBAR_OWNER_V1" srb:scope)' in clear
    assert '(srb:put-custom table 2 "SINCAL_REBAR_ELEMENT_V1" srb:element)' in clear
    assert "(vla-DeleteRows table 2 1)" in reset
    assert "(vla-InsertRows table 2 (vla-GetRowHeight model 2) 1)" in reset
    assert "vla-SetCustomData" not in reset


@pytest.mark.parametrize("view,skew", (("FR", 0), ("AA", 0), ("BB", -12), ("CC", 12), ("FF", 0)))
def test_cad_does_not_replace_a_removed_central_representative_or_move_the_cut(view, skew):
    state, assembly = state_and_assembly(skew)
    key = "mesh_x" if view in ("FR", "FF") else "mesh_y"
    central = min((bar for bar in assembly.bars if bar.key == key and bar.level == "superior"),
                  key=lambda bar: abs(bar.coordinate_m))
    # Repeated individual deletions may remove all pieces of this one run.
    chosen = [bar for bar in assembly.bars if bar.placement_id == central.placement_id]
    removed_ids = {bar.id for bar in chosen}
    prior = project_footing_assembly(assembly, view)
    remove(state, *chosen)
    after = build_footing_assembly(*domain(state))
    assert after.is_valid, after.schedule.issues
    projected = project_footing_assembly(after, view)
    assert not removed_ids & {piece.source_id for piece in projected}
    # A representative drawing/cut must stay at its original station. A new
    # neighbour is not a replacement for the manufactured piece we removed.
    assert projected == tuple(piece for piece in prior if piece.source_id not in removed_ids)


def test_stale_removal_is_preserved_for_recovery_but_not_used_for_valid_cad():
    state, assembly = state_and_assembly()
    chosen = next(bar for bar in assembly.bars if bar.key == "mesh_x")
    remove(state, chosen)
    record = deepcopy(state["rules"][0]["removed_pieces"])
    state["geometry"]["alto_cm"] += 10
    result = preview(state)
    assert not result["valid"]
    assert any(issue["severity"] == "error" for issue in result["issues"])
    assert state["rules"][0]["removed_pieces"] == record
    assert result["details"] == []
    scene = build_footing_bars(state)
    assert not scene["valid"]
    assert scene["bars"] == []
    assert scene["removed_bars"][0]["id"] == chosen.id
    assert scene["removed_bars"][0]["status"] == "unresolved"
