"""Explicit single-piece edits feed every aggregate of the shared assembly."""
from collections import Counter
from dataclasses import asdict, replace
import json

import pytest

from sincal.rebar.assembly import build_footing_assembly
from sincal.rebar.model import (
    Cover, DENSIDAD_ACERO_KG_M3, RemovedPiece, ZapataGeometry,
    default_zapata_rules, parse_removed_pieces,
)


def case(skew=0):
    geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, skew)
    cover = Cover.from_centimetres(7.5, 5, 5)
    rules = default_zapata_rules()
    assembly = build_footing_assembly(geometry, cover, rules)
    assert assembly.is_valid, assembly.schedule.issues
    return geometry, cover, rules, assembly


def omit(rules, *bars):
    return tuple(replace(rule, removed_pieces=tuple(
        RemovedPiece(bar.id, bar.signature) for bar in bars if bar.key == rule.key))
        for rule in rules)


def mark(assembly, name):
    return next(item for item in assembly.schedule.marks if item.mark == name)


def test_removing_one_bar_reduces_only_its_quantity_length_and_weight():
    geometry, cover, rules, before = case()
    removed = next(bar for bar in before.bars if bar.key == "mesh_x" and bar.piece_role == "inicial")
    after = build_footing_assembly(geometry, cover, omit(rules, removed))
    assert after.is_valid, after.schedule.issues
    assert after.reference_bars == before.bars == before.reference_bars
    assert after.bars == tuple(bar for bar in before.bars if bar.id != removed.id)
    assert len(after.bars) == len(before.bars) - 1
    old, new = mark(before, removed.mark), mark(after, removed.mark)
    assert new.quantity == old.quantity - 1
    assert new.total_length_cm == old.total_length_cm - removed.length_cm
    removed_kg = removed.length_cm / 100 * old.area_m2 * DENSIDAD_ACERO_KG_M3
    assert before.schedule.total_kg - after.schedule.total_kg == pytest.approx(removed_kg)
    assert [m for m in after.schedule.marks if m.mark != removed.mark] == [
        m for m in before.schedule.marks if m.mark != removed.mark]
    # The continuation physically overlapping the selected bar stays intact.
    partner = next(bar for bar in before.bars if bar.placement_id == removed.placement_id and bar.id != removed.id)
    assert partner in after.bars


@pytest.mark.parametrize("role", ("inicial", "terminal"))
def test_each_spliced_piece_can_be_removed_without_removing_or_renumbering_partner(role):
    geometry, cover, rules, before = case()
    removed = next(bar for bar in before.bars if bar.key == "mesh_x" and bar.piece_role == role)
    after = build_footing_assembly(geometry, cover, omit(rules, removed))
    assert after.is_valid
    assert {bar.id for bar in after.bars} == {bar.id for bar in before.bars} - {removed.id}
    assert [m.mark for m in after.schedule.marks] == [m.mark for m in before.schedule.marks]


def test_variable_series_removes_exact_variant_and_reselects_longest_detail():
    geometry, cover, rules, before = case(-12)
    candidates = [bar for bar in before.bars if bar.key == "mesh_y"]
    longest_length = max(bar.length_cm for bar in candidates)
    # Remove the entire longest variant to exercise changing the representative
    # detail while retaining a single mark and the actual remaining series.
    removed = [bar for bar in candidates if bar.length_cm == longest_length]
    after = build_footing_assembly(geometry, cover, omit(rules, *removed))
    assert after.is_valid, after.schedule.issues
    old, new = mark(before, "3"), mark(after, "3")
    remaining = [bar for bar in candidates if bar not in removed]
    assert new.quantity == old.quantity - len(removed)
    assert new.total_length_cm == sum(bar.length_cm for bar in remaining)
    assert new.unit_length_cm == max(bar.length_cm for bar in remaining)
    assert new.unit_length_cm < old.unit_length_cm
    assert {item.length_cm: item.quantity for item in new.length_variants} == dict(
        Counter(bar.length_cm for bar in remaining))
    assert new.shape_data["cut_length_cm"] == new.unit_length_cm


def test_removing_last_piece_of_a_mark_drops_only_that_mark():
    geometry, cover, rules, before = case()
    removed = [bar for bar in before.bars if bar.mark == "2"]
    after = build_footing_assembly(geometry, cover, omit(rules, *removed))
    assert after.is_valid
    assert "2" not in {m.mark for m in after.schedule.marks}
    assert {m.mark for m in after.schedule.marks} == {m.mark for m in before.schedule.marks} - {"2"}
    assert after.bars == tuple(bar for bar in before.bars if bar.mark != "2")


def test_removing_all_pieces_has_zero_quantities_without_recreating_or_renumbering():
    geometry, cover, rules, before = case()
    after = build_footing_assembly(geometry, cover, omit(rules, *before.bars))
    assert after.is_valid
    assert after.bars == ()
    assert after.schedule.marks == ()
    assert after.schedule.total_kg == 0
    assert after.reference_bars == before.bars


def test_rename_and_serialization_keep_removal_while_restore_recovers_original():
    geometry, cover, rules, before = case()
    removed = next(bar for bar in before.bars if bar.key == "mesh_x" and bar.piece_role == "inicial")
    edited = omit(rules, removed)
    encoded = json.loads(json.dumps(asdict(edited[0])))
    record = parse_removed_pieces(encoded["removed_pieces"], "mesh_x")
    assert record == edited[0].removed_pieces
    renamed = tuple(replace(rule, mark="101", removed_pieces=record) if rule.key == "mesh_x" else rule
                    for rule in edited)
    after = build_footing_assembly(geometry, cover, renamed)
    assert after.is_valid
    assert removed.id not in {bar.id for bar in after.bars}
    assert mark(after, "101").quantity == mark(before, "1").quantity - 1
    restored = tuple(replace(rule, removed_pieces=()) for rule in edited)
    assert build_footing_assembly(geometry, cover, restored) == before


@pytest.mark.parametrize("edit", ("spacing", "height", "diameter", "first_piece", "missing_id"))
def test_changed_physical_piece_cannot_silently_remove_another_bar(edit):
    geometry, cover, rules, before = case()
    # An interior row moves when the pitch changes; its ID may be reused.
    removed = next(bar for bar in before.bars if bar.id == "mesh_x:superior:2:0")
    changed = list(omit(rules, removed))
    if edit == "spacing":
        changed[0] = replace(changed[0], spacing_cm=25)
    elif edit == "height":
        geometry = replace(geometry, alto_m=2)
    elif edit == "diameter":
        changed[0] = replace(changed[0], diameter_mm=25)
    elif edit == "first_piece":
        changed[0] = replace(changed[0], first_piece_cm=1100)
    else:
        changed[0] = replace(changed[0], removed_pieces=(
            RemovedPiece("mesh_x:superior:99999:0", removed.signature),))
    after = build_footing_assembly(geometry, cover, changed)
    assert not after.is_valid
    assert after.bars == ()
    assert any("ya no coinciden" in issue.message and "Restaura" in issue.message
               for issue in after.schedule.issues)


def test_disabled_family_keeps_pending_removal_and_checks_it_on_reactivation():
    geometry, cover, rules, before = case()
    removed = next(bar for bar in before.bars if bar.key == "lateral_y")
    changed = tuple(replace(rule, enabled=False, spacing_cm=25) if rule.key == "lateral_y" else rule
                    for rule in omit(rules, removed))
    # Changing height makes the removed side bar's geometry stale. A disabled
    # family does not block unrelated active steel and preserves its record.
    geometry = replace(geometry, alto_m=2)
    after = build_footing_assembly(geometry, cover, changed)
    assert after.is_valid, after.schedule.issues
    assert not any(bar.key == "lateral_y" for bar in after.bars)
    assert changed[-1].removed_pieces == (RemovedPiece(removed.id, removed.signature),)
    enabled = tuple(replace(rule, enabled=True) if rule.key == "lateral_y" else rule for rule in changed)
    assert not build_footing_assembly(geometry, cover, enabled).is_valid


@pytest.mark.parametrize("values", (
    None, {}, "mesh_x:superior:0:0", [None],
    [{"id": "mesh_x:superior:0:0"}],
    [{"id": "mesh_x:superior:0:0", "signature": "a" * 64, "extra": 1}],
    [{"id": "lateral_y:1:0:0", "signature": "a" * 64}],
    [{"id": "mesh_x:superior:0", "signature": "a" * 64}],
    [{"id": "mesh_x:superior:-1:0", "signature": "a" * 64}],
    [{"id": "mesh_x:superior:0:0", "signature": "a" * 63}],
    [{"id": "mesh_x:superior:0:0", "signature": "g" * 64}],
    [{"id": "mesh_x:superior:0:0", "signature": None}],
    [{"id": "mesh_x:superior:0:0", "signature": "a" * 64}] * 2,
))
def test_invalid_removal_records_are_rejected(values):
    with pytest.raises(ValueError):
        parse_removed_pieces(values, "mesh_x")


def test_direct_domain_rule_validation_also_rejects_bad_records():
    geometry, cover, rules, _ = case()
    invalid = tuple(replace(rule, removed_pieces=({"id": "bad", "signature": "bad"},))
                    if rule.key == "mesh_x" else rule for rule in rules)
    result = build_footing_assembly(geometry, cover, invalid)
    assert not result.is_valid
    assert result.bars == ()


def test_signature_is_repeatable_and_independent_of_display_mark_and_label():
    _, _, _, assembly = case(-12)
    bar = assembly.bars[0]
    assert len(bar.signature) == 64
    assert bar.signature == replace(bar, mark="999", label="Otro rótulo").signature
    assert bar.signature == replace(bar, diameter_mm=float(bar.diameter_mm)).signature
    assert bar.signature != replace(bar, diameter_mm=bar.diameter_mm + 1).signature
    moved = tuple((x + .001, y, z) for x, y, z in bar.vertices_m)
    assert bar.signature != replace(bar, vertices_m=moved).signature
