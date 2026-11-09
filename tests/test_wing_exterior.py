"""A wing bracket is one exact piece; no wing distribution is inferred."""
from dataclasses import FrozenInstanceError
import math

import pytest

from sincal.rebar.detail import detail_dimension_metadata, polyline_developed_length_m, polyline_render_points
from sincal.rebar.model import DIAMETROS_DISPONIBLES_MM
from sincal.rebar.wing_exterior import make_bracket, make_bracket_path


def bracket(**changes):
    values = dict(start_m=(0., 0., 0.), end_m=(3., 0., 0.), inward=(0., 1., 0.),
                  diameter_mm=22, hook_start_cm=40., hook_end_cm=60.,
                  identity="entrada:ala_izq:exterior:0", key="wing_exterior_vertical",
                  mark="7", label="Exterior ala izquierda", spacing_cm=20.)
    values.update(changes)
    return make_bracket(**values)


def assert_points(actual, expected):
    assert len(actual) == len(expected)
    for point, reference in zip(actual, expected):
        assert point == pytest.approx(reference, abs=1e-12)


def test_bracket_exact_hooks_two_bends_and_developed_cut():
    bar = bracket()
    radius = .066
    expected = ((0, .4+radius, 0), (0, radius, 0), (radius, 0, 0),
                (3-radius, 0, 0), (3, radius, 0), (3, .6+radius, 0))
    assert_points(bar.vertices_m, expected)
    assert bar.bulges == pytest.approx((0, math.tan(math.pi/8), 0, math.tan(math.pi/8), 0, 0))
    assert math.dist(*bar.vertices_m[:2]) == pytest.approx(.4)
    assert math.dist(*bar.vertices_m[-2:]) == pytest.approx(.6)
    for index in (1, 3):
        chord = math.dist(*bar.vertices_m[index:index+2])
        recovered_radius = chord/(2*math.sin(2*math.atan(abs(bar.bulges[index]))))
        assert recovered_radius == pytest.approx(radius)
    developed = (.4+.6+3-2*radius+math.pi*radius)*100
    assert bar.developed_length_cm == pytest.approx(developed)
    assert bar.length_cm == math.ceil(developed)
    assert bar.length_cm > bar.developed_length_cm
    assert bar.bend_radius_cm == 6.6
    assert bar.main_start_m == pytest.approx((radius, 0, 0))
    assert bar.main_end_m == pytest.approx((3-radius, 0, 0))
    assert polyline_developed_length_m(bar)*100 == pytest.approx(developed)
    assert polyline_developed_length_m(bar.detail)*100 == pytest.approx(developed)
    assert bar.detail.quantity == 1
    assert bar.detail.total_cm == bar.length_cm
    assert bar.detail.layer == "fi22"
    assert bar.detail.partials_cm == (40, bar.length_cm-100, 60)
    assert sum(bar.detail.partials_cm) == bar.length_cm
    assert bar.detail.length_variants == ()
    assert bar.piece_role == "completa"
    assert [bend["bend_degrees"] for bend in detail_dimension_metadata(bar.detail)["bends"]] == [90, 90]
    assert len(bar.points_m) > len(bar.vertices_m)


def test_arbitrary_3d_orientation_preserves_local_detail_and_true_lengths():
    origin = (5., -2., 8.)
    u = (1/3, 2/3, 2/3)
    v = (-2/math.sqrt(5), 1/math.sqrt(5), 0.)
    end = tuple(coordinate+3*direction for coordinate, direction in zip(origin, u))
    bar = bracket(start_m=origin, end_m=end, inward=v)
    planar = bracket()
    assert bar.axis_u == pytest.approx(u)
    assert bar.axis_v == pytest.approx(v)
    assert_points(bar.detail.vertices_m, planar.detail.vertices_m)
    assert bar.bulges == planar.bulges

    def lift(point):
        return tuple(o+point[0]*a+point[1]*b for o, a, b in zip(origin, u, v))

    assert_points(bar.vertices_m, tuple(lift(point) for point in bar.detail.vertices_m))
    assert_points(bar.points_m, tuple(lift(point) for point in polyline_render_points(bar.detail)))
    assert polyline_developed_length_m(bar) == pytest.approx(polyline_developed_length_m(planar))
    assert bar.developed_length_cm == pytest.approx(planar.developed_length_cm)
    assert bar.length_cm == planar.length_cm
    # Both tips lie inward from their theoretical main-leg corners by hook+R.
    assert math.dist(bar.vertices_m[0], origin) == pytest.approx(.466)
    assert math.dist(bar.vertices_m[-1], end) == pytest.approx(.666)


@pytest.mark.parametrize("diameter", DIAMETROS_DISPONIBLES_MM)
def test_supported_diameters_use_radius_three_diameters(diameter):
    bar = bracket(diameter_mm=diameter, hook_start_cm=32.25, hook_end_cm=47.8)
    assert bar.bend_radius_cm == pytest.approx(3*diameter/10)
    assert math.dist(*bar.vertices_m[:2])*100 == pytest.approx(32.25)
    assert math.dist(*bar.vertices_m[-2:])*100 == pytest.approx(47.8)
    assert bar.detail.partials_cm[0] == 33
    assert bar.detail.partials_cm[-1] == 48
    assert sum(bar.detail.partials_cm) == bar.length_cm
    assert bar.developed_length_cm == pytest.approx(polyline_developed_length_m(bar)*100)


def test_inward_can_reverse_without_changing_lengths_or_flat_detail():
    first, mirrored = bracket(), bracket(inward=(0., -1., 0.))
    assert_points(mirrored.vertices_m, [(x, -y, z) for x, y, z in first.vertices_m])
    assert first.detail == mirrored.detail
    assert first.length_cm == mirrored.length_cm
    assert first.signature != mirrored.signature


def test_signature_is_bound_to_geometry_and_family_not_display_metadata():
    original = bracket()
    changed_labels = bracket(identity="different-id", mark="99", label="Otro rótulo", spacing_cm=10.)
    assert original.signature == changed_labels.signature
    assert len(original.signature) == 64
    for changes in (dict(diameter_mm=16), dict(hook_start_cm=41), dict(hook_end_cm=61),
                    dict(end_m=(3.1, 0, 0)), dict(key="wing_exterior_horizontal"),
                    dict(start_m=(1, 0, 0), end_m=(4, 0, 0))):
        assert bracket(**changes).signature != original.signature


def test_inputs_are_not_mutated_and_result_is_immutable():
    start, end, inward = [0., 0., 0.], [3., 0., 0.], [0., 1., 0.]
    saved = (start[:], end[:], inward[:])
    bar = bracket(start_m=start, end_m=end, inward=inward)
    assert (start, end, inward) == saved
    start[0], end[0], inward[1] = 100, 100, 100
    assert bar.start_m == (0., 0., 0.)
    assert bar.end_m == (3., 0., 0.)
    assert bar.axis_v == (0., 1., 0.)
    with pytest.raises(FrozenInstanceError):
        bar.mark = "8"
    with pytest.raises(FrozenInstanceError):
        bar.detail.total_cm = 20


@pytest.mark.parametrize("field", ("start_m", "end_m", "inward"))
@pytest.mark.parametrize("invalid", ((0, 0), (0, 0, 0, 0), None, "0,0,0",
                                   (True, 0, 0), (math.nan, 0, 0), (0, math.inf, 0)))
def test_bad_vectors_are_rejected(field, invalid):
    with pytest.raises(ValueError):
        bracket(**{field: invalid})


@pytest.mark.parametrize("field", ("diameter_mm", "hook_start_cm", "hook_end_cm", "spacing_cm"))
@pytest.mark.parametrize("invalid", (None, True, "22", math.nan, math.inf, -math.inf, 0, -1))
def test_bad_numbers_are_rejected(field, invalid):
    with pytest.raises(ValueError):
        bracket(**{field: invalid})


@pytest.mark.parametrize("field", ("identity", "key", "mark", "label"))
@pytest.mark.parametrize("invalid", (None, 2, "", " "))
def test_identifiers_are_explicit_nonempty_text(field, invalid):
    with pytest.raises(ValueError):
        bracket(**{field: invalid})


@pytest.mark.parametrize("vector", ((0, 0, 0), (0, 2, 0), (1, 0, 0),
                                  (1/math.sqrt(2), 1/math.sqrt(2), 0)))
def test_inward_must_be_unit_and_perpendicular(vector):
    with pytest.raises(ValueError):
        bracket(inward=vector)


def test_span_must_be_strictly_larger_than_two_radii():
    for span in (0, .1, .132):
        with pytest.raises(ValueError, match="dos radios"):
            bracket(end_m=(span, 0, 0))
    bar = bracket(end_m=(.132001, 0, 0))
    assert math.dist(bar.main_start_m, bar.main_end_m) == pytest.approx(.000001)


def test_unsupported_diameter_is_not_silently_changed():
    with pytest.raises(ValueError, match="diámetro"):
        bracket(diameter_mm=20)


def test_commercial_limit_includes_two_hooks_and_arc_lengths():
    radius = .066
    max_span = 12-.4-.6-(math.pi-2)*radius
    bar = bracket(end_m=(max_span, 0, 0))
    assert bar.length_cm == 1200
    assert bar.developed_length_cm == pytest.approx(1200)
    with pytest.raises(ValueError, match="supera 12 m"):
        bracket(end_m=(max_span+.001, 0, 0))
    for changes in (dict(hook_start_cm=1e308), dict(hook_end_cm=1e308), dict(end_m=(1e308, 0, 0))):
        with pytest.raises(ValueError, match="supera 12 m"):
            bracket(**changes)


def bracket_path(**changes):
    values = dict(main_points_m=((0., 0., 0.), (2., 0., 0.), (3., 1., 0.)),
                  hook_start_direction=(0., 1., 0.),
                  hook_end_direction=(-1/math.sqrt(2), 1/math.sqrt(2), 0.),
                  diameter_mm=22, hook_start_cm=40, hook_end_cm=60,
                  identity="wing:left:horizontal_main:0", key="wing_left_horizontal_main",
                  mark="8", label="Exterior horizontal", spacing_cm=20)
    values.update(changes)
    return make_bracket_path(**values)


def test_two_point_path_delegates_to_existing_bracket():
    first = bracket()
    routed = make_bracket_path((first.start_m, first.end_m), first.axis_v, first.axis_v,
                               first.diameter_mm, first.hook_start_cm, first.hook_end_cm,
                               identity=first.id, key=first.key, mark=first.mark,
                               label=first.label, spacing_cm=first.spacing_cm)
    assert routed == first
    assert routed.signature == first.signature


@pytest.mark.parametrize("sign", (1, -1))
def test_path_keeps_true_interior_angle_and_each_radius(sign):
    end_direction = (-sign/math.sqrt(2), 1/math.sqrt(2), 0.)
    bar = bracket_path(main_points_m=((0, 0, 0), (2, 0, 0), (3, sign, 0)),
                       hook_end_direction=end_direction)
    radius = .066
    tangent = radius*math.tan(math.pi/8)
    expected_cm = (1+2+math.sqrt(2)-2*radius-2*tangent+radius*(math.pi+math.pi/4))*100
    assert bar.developed_length_cm == pytest.approx(expected_cm)
    assert polyline_developed_length_m(bar)*100 == pytest.approx(expected_cm)
    assert polyline_developed_length_m(bar.detail)*100 == pytest.approx(expected_cm)
    assert bar.length_cm == math.ceil(expected_cm)
    assert math.dist(*bar.vertices_m[:2]) == pytest.approx(.4)
    assert math.dist(*bar.vertices_m[-2:]) == pytest.approx(.6)
    assert [bend["bend_degrees"] for bend in detail_dimension_metadata(bar.detail)["bends"]] == [90, 45, 90]
    assert len(bar.detail.partials_cm) == 4
    assert sum(bar.detail.partials_cm) == bar.length_cm
    assert bar.detail.partials_cm[0] == 40
    assert bar.detail.partials_cm[-1] == 60
    curved = [(index, bulge) for index, bulge in enumerate(bar.bulges) if bulge]
    assert len(curved) == 3
    for index, bulge in curved:
        chord = math.dist(*bar.vertices_m[index:index+2])
        assert chord/(2*math.sin(2*math.atan(abs(bulge)))) == pytest.approx(radius)
    assert bar.bulges[curved[1][0]] == pytest.approx(sign*math.tan(math.pi/16))
    assert bar.main_start_m == pytest.approx((radius, 0, 0))
    assert bar.main_end_m == pytest.approx((3-radius/math.sqrt(2), sign*(1-radius/math.sqrt(2)), 0))


def test_path_rotates_into_arbitrary_plane_without_changing_detail():
    base = bracket_path()
    offset = (5, -2, 8)
    u, v = (1/3, 2/3, 2/3), (-2/math.sqrt(5), 1/math.sqrt(5), 0.)

    def lift(point):
        return tuple(o+point[0]*a+point[1]*b for o, a, b in zip(offset, u, v))

    end_direction = tuple((-a+b)/math.sqrt(2) for a, b in zip(u, v))
    rotated = bracket_path(main_points_m=tuple(lift(point) for point in ((0, 0), (2, 0), (3, 1))),
                           hook_start_direction=v, hook_end_direction=end_direction)
    assert_points(rotated.vertices_m, tuple(lift(point) for point in base.detail.vertices_m))
    # Sampling may use one extra chord when a rotated sweep rounds just above
    # a 5-degree boundary; the exact arcs and their lengths remain unchanged.
    assert_points(rotated.points_m, tuple(lift(point) for point in polyline_render_points(rotated.detail)))
    assert_points(rotated.detail.vertices_m, base.detail.vertices_m)
    assert rotated.bulges == pytest.approx(base.bulges)
    assert rotated.developed_length_cm == pytest.approx(base.developed_length_cm)


def test_variable_first_main_segment_keeps_fixed_frontal_partial():
    first = bracket_path()
    longer = bracket_path(main_points_m=((0, 0, 0), (4, 0, 0), (5, 1, 0)))
    assert longer.detail.partials_cm[0] == first.detail.partials_cm[0]
    assert longer.detail.partials_cm[2:] == first.detail.partials_cm[2:]
    assert longer.detail.partials_cm[1]-first.detail.partials_cm[1] == 200
    assert longer.developed_length_cm-first.developed_length_cm == pytest.approx(200)


def test_path_can_turn_opposite_endpoint_hook_explicitly():
    bar = bracket_path(main_points_m=((0, 0, 0), (3, 0, 0)), hook_end_direction=(0, -1, 0))
    assert bar.vertices_m[-1] == pytest.approx((3, -.666, 0))
    assert [bulge for bulge in bar.bulges if bulge] == pytest.approx([math.tan(math.pi/8), -math.tan(math.pi/8)])
    assert polyline_developed_length_m(bar)*100 == pytest.approx(bar.developed_length_cm)


@pytest.mark.parametrize("changes", [
    {"main_points_m": ()}, {"main_points_m": ((0, 0, 0),)},
    {"main_points_m": ((0, 0, 0), (0, 0, 0), (3, 1, 0))},
    {"main_points_m": ((0, 0, 0), (2, 0, 0), (3, 1, 1))},
    {"hook_start_direction": (0, 0, 1)},
    {"hook_end_direction": (0, 0, 1)},
    {"hook_end_direction": (1/math.sqrt(2), 1/math.sqrt(2), 0)},
    {"hook_end_direction": (0, 2, 0)},
    {"main_points_m": ((0, 0, 0), (2, 0, 0), (1, 0, 0)), "hook_end_direction": (0, 1, 0)},
    {"main_points_m": ((0, 0, 0), (.05, 0, 0), (1.05, 1, 0))},
    {"main_points_m": ((0, 0, 0), (2, 0, 0), (2.05, .05, 0))},
    {"main_points_m": ((0, 0, 0), (math.nan, 0, 0), (3, 1, 0))},
    {"diameter_mm": 20}, {"hook_start_cm": -1}, {"hook_end_cm": 0},
    {"spacing_cm": math.nan}, {"mark": ""}, {"identity": None},
])
def test_invalid_path_rejects_without_routing_or_stretching(changes):
    with pytest.raises(ValueError):
        bracket_path(**changes)


def test_path_maximum_includes_real_turn_and_both_hooks():
    base = bracket_path()
    extra = (1200-base.developed_length_cm)/100
    points = ((0, 0, 0), (2+extra, 0, 0), (3+extra, 1, 0))
    full = bracket_path(main_points_m=points)
    assert full.length_cm == 1200
    assert full.developed_length_cm == pytest.approx(1200)
    with pytest.raises(ValueError, match="supera 12 m"):
        bracket_path(main_points_m=((0, 0, 0), (2+extra+.001, 0, 0), (3+extra+.001, 1, 0)))


def test_path_input_lists_are_not_mutated_or_retained():
    points = [[0, 0, 0], [2, 0, 0], [3, 1, 0]]
    start, end = [0, 1, 0], [-1/math.sqrt(2), 1/math.sqrt(2), 0]
    copy = [point[:] for point in points]
    bar = bracket_path(main_points_m=points, hook_start_direction=start, hook_end_direction=end)
    assert points == copy
    points[1][0] = start[1] = end[0] = 99
    assert bar.detail.partial_segments_m[1][1] == (2, 0)


@pytest.mark.parametrize("angle", (-12, -5, 5, 12, 90))
def test_real_wing_turns_keep_their_exact_angles_and_fit_boundary(angle):
    turn = math.radians(angle)
    radius = .066
    tangent = radius*math.tan(abs(turn)/2)
    first_span = radius+tangent
    main = ((0, 0, 0), (first_span, 0, 0),
            (first_span+math.cos(turn), math.sin(turn), 0))
    bar = bracket_path(main_points_m=main, hook_end_direction=(-math.sin(turn), math.cos(turn), 0))
    assert [bend["bend_degrees"] for bend in detail_dimension_metadata(bar.detail)["bends"]] == [90, abs(angle), 90]
    assert polyline_developed_length_m(bar)*100 == pytest.approx(bar.developed_length_cm)
    # The first main straight vanishes exactly when its two tangent lengths
    # consume its span. A genuine shortage must not be repaired silently.
    assert math.dist(bar.vertices_m[2], bar.vertices_m[3]) == pytest.approx(0, abs=1e-12)
    short = ((0, 0, 0), (first_span-.001, 0, 0),
             (first_span-.001+math.cos(turn), math.sin(turn), 0))
    with pytest.raises(ValueError, match="radios de doblez"):
        bracket_path(main_points_m=short, hook_end_direction=(-math.sin(turn), math.cos(turn), 0))


def test_actual_path_series_summarizes_as_one_variable_wing_partial():
    from types import SimpleNamespace
    from sincal.rebar.wing_schedule import summarize_wing_bars

    first = bracket_path()
    longer = bracket_path(main_points_m=((0, 0, 0), (4, 0, 0), (5, 1, 0)),
                           identity="wing:left:horizontal_main:1")
    rule = SimpleNamespace(key=first.key, mark=first.mark, label=first.label,
                           diameter_mm=first.diameter_mm, spacing_cm=first.spacing_cm,
                           continuation_mark="", removed_pieces=())
    result = summarize_wing_bars((first, longer), (rule,), "left")
    assert result["schedule"].is_valid, result["schedule"].issues
    mark, detail = result["schedule"].marks[0], result["details"][0]
    assert mark.quantity == 2
    assert mark.total_length_cm == first.length_cm+longer.length_cm
    assert len(mark.length_variants) == 2
    assert detail.variable_partial_index == 1
    assert detail.vertices_m == longer.detail.vertices_m
    assert detail.partials_cm[2:] == first.detail.partials_cm[2:]


def test_vertical_inner_bar_can_have_bottom_and_top_hooks_on_opposite_sides():
    bar = bracket_path(main_points_m=((.3, .7, .05), (.3, .7, 4)),
                       hook_start_direction=(1, 0, 0), hook_end_direction=(-1, 0, 0),
                       diameter_mm=16, hook_start_cm=40, hook_end_cm=40,
                       identity="wing:left:inner_vertical_main:0", key="wing_left_inner_vertical_main")
    radius = .048
    assert bar.vertices_m[0] == pytest.approx((.3+.4+radius, .7, .05))
    assert bar.vertices_m[-1] == pytest.approx((.3-.4-radius, .7, 4))
    assert bar.main_start_m == pytest.approx((.3, .7, .05+radius))
    assert bar.main_end_m == pytest.approx((.3, .7, 4-radius))
    assert math.dist(*bar.vertices_m[:2]) == pytest.approx(.4)
    assert math.dist(*bar.vertices_m[-2:]) == pytest.approx(.4)
    assert [bulge for bulge in bar.bulges if bulge] == pytest.approx([math.tan(math.pi/8), -math.tan(math.pi/8)])
    assert polyline_developed_length_m(bar)*100 == pytest.approx((3.95+.8+(math.pi-2)*radius)*100)
    assert sum(bar.detail.partials_cm) == bar.length_cm


@pytest.mark.parametrize("angle", (-5, 5))
def test_horizontal_inner_route_keeps_opposed_hook_directions_and_real_join(angle):
    turn = math.radians(angle)
    end_direction = (-math.sin(turn), math.cos(turn), 0)
    last = (2+math.cos(turn), math.sin(turn), 0)
    bar = bracket_path(main_points_m=((0, 0, 0), (2, 0, 0), last),
                       hook_start_direction=(0, -1, 0), hook_end_direction=end_direction,
                       identity="wing:left:inner_horizontal_main:0", key="wing_left_inner_horizontal_main")
    assert bar.vertices_m[0] == pytest.approx((0, -.466, 0))
    assert bar.vertices_m[-1] == pytest.approx(tuple(p+.666*direction for p, direction in zip(last, end_direction)))
    assert [bend["bend_degrees"] for bend in detail_dimension_metadata(bar.detail)["bends"]] == [90, abs(angle), 90]
    assert math.dist(*bar.vertices_m[:2]) == pytest.approx(.4)
    assert math.dist(*bar.vertices_m[-2:]) == pytest.approx(.6)
    assert polyline_developed_length_m(bar)*100 == pytest.approx(bar.developed_length_cm)
    assert sum(bar.detail.partials_cm) == bar.length_cm
