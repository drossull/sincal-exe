"""A wing schedule counts physical survivors once and keeps its own marks."""
from dataclasses import replace
import math
from types import SimpleNamespace

import pytest

from sincal.rebar.detail import detail_dimension_metadata, polyline_developed_length_m
from sincal.rebar.model import DENSIDAD_ACERO_KG_M3, RemovedPiece
from sincal.rebar.wing_exterior import make_bracket, make_single_hook, make_open_path
from sincal.rebar.wing_schedule import summarize_wing_bars


def rule(side="left", group="vertical_main", mark="7", **changes):
    values = dict(key=f"wing_{side}_{group}", mark=mark, label="Malla exterior vertical",
                  diameter_mm=22, spacing_cm=20, continuation_mark="", removed_pieces=())
    values.update(changes)
    return SimpleNamespace(**values)


def bars_for(lengths=(3, 3), *, side="left", group="vertical_main", mark="7", **changes):
    bars = []
    for index, span in enumerate(lengths):
        values = dict(start_m=(0, 0, index), end_m=(span, 0, index), inward=(0, 1, 0),
                      diameter_mm=22, hook_start_cm=40, hook_end_cm=60,
                      identity=f"wing:{side}:{group}:{index}", key=f"wing_{side}_{group}",
                      mark=mark, label="Malla exterior vertical", spacing_cm=20)
        values.update(changes)
        bars.append(make_bracket(**values))
    return tuple(bars)


def test_equal_lengths_are_one_mark_without_counting_each_view_again():
    bars = bars_for((3, 3, 3))
    result = summarize_wing_bars(bars, [rule()], "left")
    schedule, details = result["schedule"], result["details"]
    assert schedule.is_valid
    assert len(schedule.marks) == len(details) == 1
    mark, detail = schedule.marks[0], details[0]
    assert mark.element == "Ala izquierda"
    assert mark.location == rule().label
    assert mark.views == ("BB", "DD", "EE")
    assert mark.quantity == 3
    assert mark.unit_length_cm == bars[0].length_cm
    assert mark.total_length_cm == 3*bars[0].length_cm
    assert mark.hook_count == 2
    assert mark.bend_radius_cm == 6.6
    assert mark.piece_role == "completa"
    assert mark.length_variants == detail.length_variants == ()
    assert detail.variable_partial_index is None
    assert detail.quantity == 3
    assert detail.vertices_m == bars[0].detail.vertices_m
    assert schedule.total_kg == pytest.approx(mark.total_length_cm/100*math.pi*(.022/2)**2*DENSIDAD_ACERO_KG_M3)


def test_variable_series_sums_each_real_cut_and_only_middle_partial_varies():
    bars = bars_for((2, 3.25, 2, 3.25, 4.5))
    result = summarize_wing_bars(iter(bars), iter([rule()]), "left")
    mark, detail = result["schedule"].marks[0], result["details"][0]
    assert mark.quantity == detail.quantity == 5
    assert [(item.length_cm, item.quantity) for item in mark.length_variants] == [
        (bars[0].length_cm, 2), (bars[1].length_cm, 2), (bars[-1].length_cm, 1)]
    assert mark.total_length_cm == sum(bar.length_cm for bar in bars)
    assert mark.total_length_cm < mark.quantity*mark.unit_length_cm
    assert mark.unit_length_cm == detail.total_cm == bars[-1].length_cm
    assert detail.length_variants == mark.length_variants
    assert detail.variable_partial_index == 1
    assert detail.vertices_m == bars[-1].detail.vertices_m
    assert polyline_developed_length_m(detail)*100 == pytest.approx(bars[-1].developed_length_cm)
    dimensions = detail_dimension_metadata(detail)["partial_ranges_cm"]
    assert dimensions == [{"min_cm": 40, "max_cm": 40},
                          {"min_cm": bars[0].length_cm-100, "max_cm": bars[-1].length_cm-100},
                          {"min_cm": 60, "max_cm": 60}]
    assert mark.shape_data["vertices_m"] == detail.vertices_m


def test_distinct_actual_lengths_with_same_cut_stay_one_nonvariable_cut():
    bars = bars_for((3, 3.001))
    result = summarize_wing_bars(bars, [rule()], "left")
    assert result["schedule"].marks[0].length_variants == ()
    assert result["details"][0].developed_length_cm == bars[-1].developed_length_cm


def test_families_keep_their_marks_and_input_rule_order():
    first = bars_for((3, 4))
    second = bars_for((2, 2, 2), group="horizontal_main", mark="8", diameter_mm=16)
    rules = [rule(group="horizontal_main", mark="8", diameter_mm=16, label="Exterior horizontal"), rule()]
    result = summarize_wing_bars(first+second, rules, "left")
    assert result["schedule"].is_valid
    assert [(mark.mark, mark.quantity, mark.diameter_mm) for mark in result["schedule"].marks] == [("8", 3, 16), ("7", 2, 22)]
    assert [detail.mark for detail in result["details"]] == ["8", "7"]
    assert result["schedule"].marks[0].location == "Exterior horizontal"


def test_right_wing_has_independent_element_and_views():
    result = summarize_wing_bars(bars_for(side="right"), [rule(side="right")], "right")
    assert result["schedule"].is_valid
    mark = result["schedule"].marks[0]
    assert mark.element == "Ala derecha"
    assert mark.views == ("CC", "DD", "EE")
    assert mark.quantity == 2


def test_removal_uses_only_survivors_and_keeps_unrelated_mark():
    original = bars_for((2, 3, 4))
    other = bars_for((2,), group="horizontal_main", mark="8")
    removed = (RemovedPiece(original[-1].id, original[-1].signature),)
    result = summarize_wing_bars(original[:-1]+other, [rule(removed_pieces=removed), rule(group="horizontal_main", mark="8")], "left")
    mark = result["schedule"].marks[0]
    assert mark.mark == "7"
    assert mark.quantity == 2
    assert mark.total_length_cm == sum(bar.length_cm for bar in original[:-1])
    assert result["details"][0].vertices_m == original[-2].detail.vertices_m
    assert result["schedule"].marks[1].mark == "8"
    assert original[-1].id == "wing:left:vertical_main:2"


def test_all_removed_is_valid_empty_without_placeholder_or_renumbering():
    original = bars_for()
    rules = [rule(removed_pieces=tuple(RemovedPiece(bar.id, bar.signature) for bar in original))]
    result = summarize_wing_bars((), rules, "left")
    assert result["schedule"].is_valid
    assert result["schedule"].marks == ()
    assert result["schedule"].total_kg == 0
    assert result["details"] == ()
    assert rules[0].mark == "7"


@pytest.mark.parametrize("bars,rules,side", [
    (bars_for(), [rule(), rule()], "left"),
    (bars_for(), [rule(), rule(group="horizontal_main")], "left"),
    (bars_for(mark="7A"), [rule(mark="7A"), rule(group="horizontal_main", mark="7a")], "left"),
    (bars_for()+bars_for(side="right"), [rule()], "left"),
    (bars_for(), [rule(side="right")], "left"),
    (bars_for(), [], "left"),
    (bars_for()+bars_for(), [rule()], "left"),
    (bars_for(mark="8"), [rule()], "left"),
    (bars_for(diameter_mm=16), [rule()], "left"),
    (bars_for(spacing_cm=25), [rule()], "left"),
    (bars_for(), [rule(continuation_mark="8")], "left"),
    (bars_for(), [rule(key="mesh_y")], "left"),
    (bars_for(), [rule(mark="MARCA")], "left"),
    (bars_for(), [rule(diameter_mm=20)], "left"),
    (bars_for(), [rule(spacing_cm=0)], "left"),
])
def test_conflicts_return_no_partial_schedule_or_details(bars, rules, side):
    result = summarize_wing_bars(bars, rules, side)
    assert not result["schedule"].is_valid
    assert result["schedule"].marks == ()
    assert result["details"] == ()


def test_variable_hooks_cannot_be_mislabelled_as_variable_main_only():
    bars = bars_for((2, 3))
    different = bars_for((3,), hook_start_cm=41, identity=bars[1].id)[0]
    result = summarize_wing_bars((bars[0], different), [rule()], "left")
    assert not result["schedule"].is_valid
    assert "ganchos diferentes" in result["schedule"].issues[0].message


def test_mislabelled_id_group_is_not_combined_with_another_family():
    bar = replace(bars_for()[0], id="wing:left:horizontal_main:0")
    result = summarize_wing_bars([bar], [rule()], "left")
    assert not result["schedule"].is_valid


def with_four_partials(bar):
    """Split the existing straight main leg without changing its geometry."""
    raw = ((0, .466), (0, 0), (1, 0), (bar.end_m[0], 0), (bar.end_m[0], .666))
    detail = replace(bar.detail, partials_cm=(40, 100, bar.length_cm-200, 60),
                     partial_segments_m=tuple(zip(raw, raw[1:])))
    return replace(bar, detail=detail)


def test_more_than_three_compatible_partials_keep_complete_shape_and_variable_index():
    bars = tuple(with_four_partials(bar) for bar in bars_for((2, 3)))
    result = summarize_wing_bars(bars, [rule()], "left")
    assert result["schedule"].is_valid
    detail = result["details"][0]
    assert detail.variable_partial_index == 2
    assert detail.partial_segments_m == bars[-1].detail.partial_segments_m
    assert detail.vertices_m == bars[-1].detail.vertices_m
    assert len(result["schedule"].marks[0].shape_data["raw_m"]) == 5
    ranges = detail_dimension_metadata(detail)["partial_ranges_cm"]
    assert ranges[2] == {"min_cm": bars[0].length_cm-200, "max_cm": bars[-1].length_cm-200}


def test_multiple_variable_partials_require_their_own_detail_definition():
    bars = tuple(with_four_partials(bar) for bar in bars_for((2, 3)))
    last = replace(bars[-1], detail=replace(bars[-1].detail, partials_cm=(40, 120, bars[-1].length_cm-220, 60)))
    result = summarize_wing_bars((bars[0], last), [rule()], "left")
    assert not result["schedule"].is_valid
    assert any("más de una parcial" in issue.message for issue in result["schedule"].issues)


def test_distinct_bend_shapes_cannot_share_a_single_representative():
    first, last = bars_for((2, 3))
    last = replace(last, detail=replace(last.detail, bulges=(0, .2, 0, .4, 0, 0)))
    result = summarize_wing_bars((first, last), [rule()], "left")
    assert not result["schedule"].is_valid
    assert any("ángulos" in issue.message for issue in result["schedule"].issues)


def test_side_is_explicit():
    with pytest.raises(ValueError, match="lado"):
        summarize_wing_bars((), (), "izquierda")


@pytest.mark.parametrize("side", ("left", "right"))
@pytest.mark.parametrize("group", ("inner_vertical_main", "inner_vertical_extension",
                                  "inner_horizontal_main", "inner_horizontal_upper"))
def test_interior_families_keep_their_own_marks_variable_totals_and_labels(side, group):
    bars = bars_for((2, 3, 2), side=side, group=group, mark="27")
    configuration = rule(side=side, group=group, mark="27", label="Malla interior del ala")
    result = summarize_wing_bars(bars, (configuration,), side)
    assert result["schedule"].is_valid, result["schedule"].issues
    mark, detail = result["schedule"].marks[0], result["details"][0]
    assert mark.key == configuration.key
    assert mark.mark == detail.mark == "27"
    assert mark.quantity == detail.quantity == 3
    assert mark.location == "Malla interior del ala"
    assert set(mark.projection_notes.values()) == {"armadura interior"}
    assert mark.views == (("BB", "DD", "EE") if side == "left" else ("CC", "DD", "EE"))
    assert mark.total_length_cm == sum(bar.length_cm for bar in bars)
    assert [(item.length_cm, item.quantity) for item in mark.length_variants] == [(bars[0].length_cm, 2), (bars[1].length_cm, 1)]
    assert detail.variable_partial_index == 1


def test_both_meshes_summarize_together_without_combining_equal_length_pieces():
    outside = bars_for((2, 3), mark="7")
    inside = bars_for((2, 3), group="inner_vertical_main", mark="27")
    rules = (rule(), rule(group="inner_vertical_main", mark="27", label="Vertical interior"))
    result = summarize_wing_bars(outside+inside, rules, "left")
    assert result["schedule"].is_valid
    marks = result["schedule"].marks
    assert [(mark.key, mark.mark, mark.quantity) for mark in marks] == [
        ("wing_left_vertical_main", "7", 2), ("wing_left_inner_vertical_main", "27", 2)]
    assert set(marks[0].projection_notes.values()) == {"armadura exterior"}
    assert set(marks[1].projection_notes.values()) == {"armadura interior"}
    assert [detail.mark for detail in result["details"]] == ["7", "27"]
    assert result["schedule"].total_kg == pytest.approx(2*marks[0].kg_steel)


@pytest.mark.parametrize("inside_mark", ("7A", "7a"))
def test_interior_and_exterior_cannot_reuse_a_mark_even_with_identical_geometry(inside_mark):
    outside = bars_for(mark="7A")
    inside = bars_for(group="inner_vertical_main", mark=inside_mark)
    result = summarize_wing_bars(outside+inside, (rule(mark="7A"), rule(group="inner_vertical_main", mark=inside_mark)), "left")
    assert not result["schedule"].is_valid
    assert result["schedule"].marks == result["details"] == ()
    assert any("duplicada" in issue.message for issue in result["schedule"].issues)


def test_removing_all_interior_survivors_preserves_exterior_exactly():
    outside = bars_for((2, 3))
    inside = bars_for((2, 3), group="inner_vertical_main", mark="27")
    inside_rule = rule(group="inner_vertical_main", mark="27",
                       removed_pieces=tuple(RemovedPiece(bar.id, bar.signature) for bar in inside))
    standalone = summarize_wing_bars(outside, (rule(),), "left")
    combined = summarize_wing_bars(outside, (rule(), inside_rule), "left")
    assert combined == standalone


def test_interior_identity_cannot_be_relabelled_as_exterior_family():
    interior = bars_for(group="inner_vertical_main", mark="27")[0]
    forged = replace(interior, key="wing_left_vertical_main")
    result = summarize_wing_bars((forged,), (rule(mark="27"),), "left")
    assert not result["schedule"].is_valid
    assert result["schedule"].marks == ()


def supplement_bars(totals=(300, 600), *, side="left", interior=False, mark="77"):
    group = ("inner_" if interior else "")+"vertical_supplement"
    radius, hook = .066, .4
    result = []
    for index, total in enumerate(totals):
        span = total/100-hook-(math.pi/2-1)*radius
        result.append(make_single_hook(
            (.2*index, 0, 0), (.2*index, 0, span), (0, 1, 0), 22, hook*100,
            identity=f"wing:{side}:{group}:{index}", key=f"wing_{side}_{group}",
            mark=mark, label="Suple vertical", spacing_cm=20))
    return tuple(result)


@pytest.mark.parametrize("side", ("left", "right"))
@pytest.mark.parametrize("interior", (False, True))
def test_single_hook_supplement_has_one_own_mark_real_variable_totals_and_no_top_hook(side, interior):
    bars = supplement_bars((300, 300, 600), side=side, interior=interior)
    group = ("inner_" if interior else "")+"vertical_supplement"
    result = summarize_wing_bars(bars, (rule(side=side, group=group, mark="77", label="Suple vertical"),), side)
    assert result["schedule"].is_valid, result["schedule"].issues
    mark, detail = result["schedule"].marks[0], result["details"][0]
    assert mark.mark == "77"
    assert mark.quantity == detail.quantity == 3
    assert mark.total_length_cm == 1200
    assert mark.unit_length_cm == detail.total_cm == 600
    assert mark.hook_count == mark.shape_data["hook_count"] == 1
    assert [(variant.length_cm, variant.quantity) for variant in mark.length_variants] == [(300, 2), (600, 1)]
    assert mark.kg_steel == pytest.approx(12*math.pi*(.022/2)**2*DENSIDAD_ACERO_KG_M3)
    assert detail.partials_cm == (40, 560)
    assert detail.variable_partial_index == 1
    assert len(detail.partial_segments_m) == 2
    assert len(mark.shape_data["raw_m"]) == 3
    assert len(detail_dimension_metadata(detail)["bends"]) == 1
    assert sum(abs(bulge) > 1e-10 for bulge in detail.bulges) == 1
    assert polyline_developed_length_m(detail)*100 == pytest.approx(600)
    assert detail.vertices_m == bars[-1].detail.vertices_m
    assert all(bar.hook_end_cm == 0 and bar.main_end_m == bar.end_m for bar in bars)
    assert set(mark.projection_notes.values()) == {"armadura interior" if interior else "armadura exterior"}


def test_supplement_and_regular_brackets_do_not_merge_or_duplicate_view_counts():
    brackets = bars_for((2, 3))
    supplements = supplement_bars((300, 600))
    rules = (rule(), rule(group="vertical_supplement", mark="77", label="Suple vertical"))
    result = summarize_wing_bars(brackets+supplements, rules, "left")
    assert result["schedule"].is_valid
    assert [(mark.mark, mark.quantity, mark.hook_count) for mark in result["schedule"].marks] == [("7", 2, 2), ("77", 2, 1)]
    assert sum(mark.total_length_cm for mark in result["schedule"].marks) == sum(bar.length_cm for bar in brackets+supplements)
    assert [len(detail.partials_cm) for detail in result["details"]] == [3, 2]
    removed = supplements[0]
    rules[1].removed_pieces = (RemovedPiece(removed.id, removed.signature),)
    reduced = summarize_wing_bars(brackets+supplements[1:], rules, "left")
    assert reduced["schedule"].marks[0] == result["schedule"].marks[0]
    assert reduced["schedule"].marks[1].mark == "77"
    assert reduced["schedule"].marks[1].quantity == 1
    assert reduced["schedule"].marks[1].total_length_cm == 600
    assert reduced["details"][1].partials_cm == (40, 560)


def test_supplement_requires_its_own_mark_in_the_shared_wing_schedule():
    brackets = bars_for(mark="7")
    supplements = supplement_bars(mark="7")
    result = summarize_wing_bars(brackets+supplements, (rule(), rule(group="vertical_supplement", mark="7")), "left")
    assert not result["schedule"].is_valid
    assert any("duplicada" in issue.message for issue in result["schedule"].issues)
    assert result["schedule"].marks == result["details"] == ()


def test_one_and_two_hook_shapes_cannot_share_supplement_mark():
    supplement = supplement_bars((300,))[0]
    bracket = bars_for((3,), group="vertical_supplement", mark="77", identity="wing:left:vertical_supplement:999")[0]
    result = summarize_wing_bars((supplement, bracket), (rule(group="vertical_supplement", mark="77"),), "left")
    assert not result["schedule"].is_valid
    assert any("ganchos diferentes" in issue.message or "formas" in issue.message for issue in result["schedule"].issues)
    assert result["details"] == ()


def test_edge_constant_total_keeps_each_partial_range_without_claiming_variable_total():
    bars = tuple(make_open_path(((0,0,0),(first,0,0),(first,3-first,0)),22,
        identity=f'wing:left:edge:{index}',key='wing_left_edge',mark='61',label='Armadura de canto',spacing_cm=20)
        for index,first in enumerate((2.,1.5)))
    result = summarize_wing_bars(bars,(rule(group='edge',mark='61',label='Armadura de canto'),),'left')
    assert result['schedule'].is_valid, result['schedule'].issues
    mark, detail = result['schedule'].marks[0], result['details'][0]
    assert mark.hook_count == 0
    assert mark.length_variants == ()
    assert detail.variable_partial_index is None
    assert mark.total_length_cm == 2*bars[0].length_cm
    assert result['detail_partial_ranges']['wing_left_edge'] == [
        {'min_cm':min(values),'max_cm':max(values)} for values in zip(*(bar.detail.partials_cm for bar in bars))]
    assert all(item['min_cm'] < item['max_cm'] for item in result['detail_partial_ranges']['wing_left_edge'])
    assert set(mark.projection_notes.values()) == {'armadura de canto'}


def test_edge_partial_ranges_do_not_allow_different_bend_angles():
    bars = tuple(make_open_path(((0,0,0),(first,0,0),(first,3-first,0)),22,
        identity=f'wing:left:edge:{index}',key='wing_left_edge',mark='61',label='Armadura de canto',spacing_cm=20)
        for index,first in enumerate((2.,1.5)))
    changed = replace(bars[1],detail=replace(bars[1].detail,bulges=tuple(value/2 for value in bars[1].bulges)))
    result = summarize_wing_bars((bars[0],changed),(rule(group='edge',mark='61'),),'left')
    assert not result['schedule'].is_valid
    assert result['detail_partial_ranges'] == {}
