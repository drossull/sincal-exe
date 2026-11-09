"""A single-hook primitive has one real bend and no assumed total length."""
from dataclasses import FrozenInstanceError
import math

import pytest

from sincal.rebar.detail import detail_dimension_metadata, polyline_developed_length_m, polyline_render_points
from sincal.rebar.model import DIAMETROS_DISPONIBLES_MM
from sincal.rebar.wing_exterior import make_single_hook


def single(**changes):
    values = dict(start_m=(0., 0., 0.), end_m=(0., 0., 3.), inward=(1., 0., 0.),
                  diameter_mm=16, hook_start_cm=40., identity='wing:left:supplement:0',
                  key='wing_left_supplement', mark='31', label='Suple de prueba', spacing_cm=20.)
    values.update(changes)
    return make_single_hook(**values)


def assert_points(actual, expected):
    assert len(actual) == len(expected)
    for a,b in zip(actual, expected):
        assert a == pytest.approx(b, abs=1e-12)


def test_one_hook_one_bend_and_real_straight_tip():
    bar = single()
    radius = .048
    assert_points(bar.vertices_m, ((.4+radius,0,0), (radius,0,0), (0,0,radius), (0,0,3)))
    assert bar.bulges == pytest.approx((0, math.tan(math.pi/8), 0, 0))
    assert math.dist(*bar.vertices_m[:2]) == pytest.approx(.4)
    assert math.dist(*bar.vertices_m[-2:]) == pytest.approx(3-radius)
    assert bar.main_start_m == pytest.approx((0,0,radius))
    assert bar.main_end_m == bar.end_m == bar.vertices_m[-1] == bar.points_m[-1] == (0,0,3)
    assert bar.hook_start_cm == 40 and bar.hook_end_cm == 0
    assert bar.bend_radius_cm == pytest.approx(4.8)
    expected = (.4+3-radius+math.pi*radius/2)*100
    assert bar.developed_length_cm == pytest.approx(expected)
    assert polyline_developed_length_m(bar)*100 == pytest.approx(expected)
    assert polyline_developed_length_m(bar.detail)*100 == pytest.approx(expected)
    assert bar.length_cm == bar.detail.total_cm == math.ceil(expected)
    assert bar.detail.partials_cm == (40, bar.length_cm-40)
    assert len(bar.detail.partial_segments_m) == 2
    assert bar.detail.partial_segments_m[-1][-1] == (3., 0.)
    assert bar.detail.main_start_x_m == radius
    assert bar.detail.main_end_x_m == 3
    assert bar.detail.quantity == 1 and bar.detail.length_variants == ()
    metadata = detail_dimension_metadata(bar.detail)
    assert [bend['bend_degrees'] for bend in metadata['bends']] == [90]


@pytest.mark.parametrize('diameter', DIAMETROS_DISPONIBLES_MM)
def test_all_supported_diameters_and_fractional_hook_keep_true_dimensions(diameter):
    bar = single(diameter_mm=diameter, hook_start_cm=32.25)
    radius = 3*diameter/1000
    chord = math.dist(bar.vertices_m[1],bar.vertices_m[2])
    assert chord/(2*math.sin(math.pi/4)) == pytest.approx(radius)
    assert math.dist(bar.vertices_m[0],bar.vertices_m[1])*100 == pytest.approx(32.25)
    assert bar.main_start_m[2] == pytest.approx(radius)
    assert bar.main_end_m[2] == 3
    assert bar.detail.partials_cm[0] == 33
    assert sum(bar.detail.partials_cm) == bar.length_cm
    assert bar.developed_length_cm == pytest.approx(polyline_developed_length_m(bar)*100)


def test_arbitrary_3d_orientation_and_mirrored_hook_do_not_change_flat_detail():
    origin = (5.,-2.,8.)
    axis = (1/3,2/3,2/3)
    inward = (-2/math.sqrt(5),1/math.sqrt(5),0.)
    end = tuple(zero+3*direction for zero,direction in zip(origin,axis))
    bar = single(start_m=origin,end_m=end,inward=inward)
    plain = single()
    assert_points(bar.detail.vertices_m,plain.detail.vertices_m)
    assert bar.length_cm == plain.length_cm
    assert bar.main_end_m == bar.vertices_m[-1] == end
    lifted = [tuple(zero+point[0]*u+point[1]*v for zero,u,v in zip(origin,axis,inward))
              for point in polyline_render_points(bar.detail)]
    assert_points(bar.points_m,lifted)
    mirrored = single(inward=(-1.,0.,0.))
    assert_points(mirrored.vertices_m,[(-x,y,z) for x,y,z in plain.vertices_m])
    assert mirrored.detail == plain.detail
    assert mirrored.signature != plain.signature


def test_signature_and_immutable_result_are_consistent_with_other_wing_pieces():
    start, end, direction = [0.,0.,0.],[0.,0.,3.],[1.,0.,0.]
    bar = single(start_m=start,end_m=end,inward=direction)
    start[0] = end[0] = direction[0] = 10
    assert bar.start_m == (0.,0.,0.) and bar.end_m == (0.,0.,3.)
    assert bar.signature == single(identity='new-id',mark='99',label='Otro nombre',spacing_cm=10).signature
    assert bar.signature != single(hook_start_cm=41).signature
    assert bar.signature != single(end_m=(0.,0.,3.1)).signature
    assert bar.signature != single(key='other-family').signature
    with pytest.raises(FrozenInstanceError):
        bar.hook_end_cm = 40


def test_commercial_limit_counts_the_initial_hook_arc_and_all_main_straight():
    radius = .048
    max_span = 12-.4-(math.pi/2-1)*radius
    exact = single(end_m=(0.,0.,max_span))
    assert exact.length_cm == 1200
    assert exact.developed_length_cm == pytest.approx(1200)
    assert exact.main_end_m == (0.,0.,max_span)
    with pytest.raises(ValueError, match='supera 12 m'):
        single(end_m=(0.,0.,max_span+.001))
    with pytest.raises(ValueError, match='supera 12 m'):
        single(hook_start_cm=1e308)
    with pytest.raises(ValueError, match='supera 12 m'):
        single(end_m=(0.,0.,1e308))


def test_tip_is_not_moved_to_a_commercial_multiple_or_rounded_dimension():
    bar = single(end_m=(0.,0.,3.12345),hook_start_cm=40.125)
    assert bar.end_m == bar.main_end_m == bar.points_m[-1] == (0.,0.,3.12345)
    assert bar.length_cm != 300 and bar.length_cm != 600
    assert bar.length_cm != pytest.approx(bar.developed_length_cm)


@pytest.mark.parametrize('span',[0., .02, .048])
def test_main_straight_requires_room_beyond_the_single_bend(span):
    with pytest.raises(ValueError,match='un radio'):
        single(end_m=(0.,0.,span))
    minimal = single(end_m=(0.,0.,.048001))
    assert math.dist(minimal.main_start_m,minimal.main_end_m) == pytest.approx(.000001)


@pytest.mark.parametrize('changes',[
    {'start_m':(0,0)}, {'end_m':(0,math.nan,0)}, {'inward':(True,0,0)},
    {'inward':(0,0,0)}, {'inward':(2,0,0)}, {'inward':(0,0,1)},
    {'inward':(1/math.sqrt(2),0,1/math.sqrt(2))},
    {'diameter_mm':20}, {'diameter_mm':None}, {'diameter_mm':True},
    {'hook_start_cm':0}, {'hook_start_cm':-40}, {'hook_start_cm':math.inf},
    {'hook_start_cm':'40'}, {'spacing_cm':0}, {'spacing_cm':math.nan},
    {'identity':''}, {'key':None}, {'mark':False}, {'label':' '},
])
def test_invalid_geometry_or_metadata_is_rejected_without_fallback(changes):
    with pytest.raises(ValueError):
        single(**changes)
