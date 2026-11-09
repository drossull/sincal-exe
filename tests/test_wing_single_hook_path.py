"""Explicit coplanar paths have one initial hook and no invented end bend."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import math

import pytest

from sincal.rebar.detail import detail_dimension_metadata, polyline_developed_length_m, polyline_render_points
from sincal.rebar.model import DIAMETROS_DISPONIBLES_MM
from sincal.rebar.wing_exterior import make_single_hook, make_single_hook_path


def path(**changes):
    values = dict(main_points_m=((0.,0.,0.),(2.,0.,0.),(3.,1.,0.)),
                  hook_start_direction=(0.,1.,0.),diameter_mm=16,hook_start_cm=40.,
                  identity='wing:left:explicit_path:0',key='wing_left_explicit_path',
                  mark='41',label='Recorrido explícito',spacing_cm=20.)
    values.update(changes)
    return make_single_hook_path(**values)


def assert_points(actual, expected):
    assert len(actual) == len(expected)
    for a,b in zip(actual,expected):
        assert a == pytest.approx(b,abs=1e-12)


def test_two_points_delegate_to_exact_existing_single_hook():
    options = dict(identity='wing:left:explicit_path:0',key='wing_left_explicit_path',
                   mark='41',label='Recorrido explícito',spacing_cm=20.)
    points = ((1.,2.,3.),(1.,2.,6.))
    direct = make_single_hook(*points,(1.,0.,0.),16,40.,**options)
    routed = make_single_hook_path(points,(1.,0.,0.),16,40.,**options)
    assert direct == routed


def test_initial_and_interior_arcs_are_counted_once_and_final_tip_stays_straight():
    bar = path()
    radius = .048
    tangent = radius*math.tan(math.pi/8)
    expected = (.4+2+math.sqrt(2)-radius-2*tangent+radius*(math.pi/2+math.pi/4))*100
    assert bar.developed_length_cm == pytest.approx(expected)
    assert polyline_developed_length_m(bar)*100 == pytest.approx(expected)
    assert polyline_developed_length_m(bar.detail)*100 == pytest.approx(expected)
    assert bar.length_cm == math.ceil(expected)
    assert bar.hook_start_cm == 40 and bar.hook_end_cm == 0
    assert math.dist(*bar.vertices_m[:2]) == pytest.approx(.4)
    assert bar.main_start_m == pytest.approx((radius,0,0))
    assert bar.main_end_m == bar.end_m == bar.points_m[-1] == bar.vertices_m[-1] == (3,1,0)
    assert bar.bulges[-2:] == (0.,0.)
    assert [bend['bend_degrees'] for bend in detail_dimension_metadata(bar.detail)['bends']] == [90,45]
    assert len(bar.detail.partials_cm) == len(bar.detail.partial_segments_m) == 3
    assert bar.detail.partials_cm[0] == 40
    final_partial = (math.sqrt(2)-tangent+radius*math.pi/8)*100
    assert bar.detail.partials_cm[-1] == math.ceil(final_partial)
    assert sum(bar.detail.partials_cm) == bar.length_cm
    assert bar.detail.partial_segments_m[-1] == ((2.,0.),(3.,1.))


@pytest.mark.parametrize('degrees',[-80,-30,-5,5,30,80])
@pytest.mark.parametrize('diameter',DIAMETROS_DISPONIBLES_MM)
def test_signed_turns_keep_three_diameter_radius_and_correct_developed_length(degrees,diameter):
    angle = math.radians(degrees)
    end = (2+math.cos(angle),math.sin(angle),0.)
    bar = path(main_points_m=((0.,0.,0.),(2.,0.,0.),end),diameter_mm=diameter)
    radius = 3*diameter/1000
    expected = (.4+3-radius-2*radius*math.tan(abs(angle)/2)+radius*(math.pi/2+abs(angle)))*100
    assert bar.developed_length_cm == pytest.approx(expected)
    assert bar.developed_length_cm == pytest.approx(polyline_developed_length_m(bar)*100)
    assert bar.main_end_m == end
    bends = [(i,b) for i,b in enumerate(bar.bulges) if abs(b)>1e-12]
    assert len(bends) == 2
    for i,bulge in bends:
        chord = math.dist(bar.vertices_m[i],bar.vertices_m[i+1])
        assert chord/(2*math.sin(2*math.atan(abs(bulge)))) == pytest.approx(radius)
    assert math.copysign(1,bends[-1][1]) == math.copysign(1,degrees)


def test_multiple_bends_and_collinear_extension_do_not_add_an_end_hook():
    points = ((0.,0.,0.),(1.,0.,0.),(2.,1.,0.),(3.,1.,0.),(4.,1.,0.))
    bar = path(main_points_m=points)
    radius = .048
    expected = (.4+3+math.sqrt(2)-radius-4*radius*math.tan(math.pi/8)
                +radius*(math.pi/2+math.pi/4+math.pi/4))*100
    assert bar.developed_length_cm == pytest.approx(expected)
    assert polyline_developed_length_m(bar)*100 == pytest.approx(expected)
    assert bar.main_end_m == points[-1]
    assert len(bar.detail.partials_cm) == len(points)
    assert sum(bar.detail.partials_cm) == bar.length_cm
    assert len(detail_dimension_metadata(bar.detail)['bends']) == 3


def test_tail_partials_stay_fixed_when_only_initial_main_segment_varies():
    original = path()
    longer = path(main_points_m=((0.,0.,0.),(2.37,0.,0.),(3.37,1.,0.)))
    assert longer.detail.partials_cm[0] == original.detail.partials_cm[0]
    assert longer.detail.partials_cm[2:] == original.detail.partials_cm[2:]
    assert longer.detail.partials_cm[1]-original.detail.partials_cm[1] == 37
    assert longer.length_cm-original.length_cm == 37


def test_arbitrary_3d_frame_and_hook_mirror_preserve_exact_local_geometry():
    origin = (5.,-2.,8.)
    axis = (1/3,2/3,2/3)
    inward = (-2/math.sqrt(5),1/math.sqrt(5),0.)
    planar = path()
    def lift(point):
        return tuple(zero+point[0]*u+point[1]*v for zero,u,v in zip(origin,axis,inward))
    main = tuple(lift(point) for point in ((0,0),(2,0),(3,1)))
    bar = path(main_points_m=main,hook_start_direction=inward)
    assert_points(bar.detail.vertices_m,planar.detail.vertices_m)
    assert_points(bar.points_m,tuple(lift(point) for point in polyline_render_points(bar.detail)))
    assert bar.main_end_m == main[-1]
    assert bar.length_cm == planar.length_cm
    assert bar.developed_length_cm == pytest.approx(planar.developed_length_cm)
    mirrored = path(main_points_m=((0.,0.,0.),(2.,0.,0.),(3.,-1.,0.)),hook_start_direction=(0.,-1.,0.))
    assert_points(mirrored.vertices_m,[(x,-y,z) for x,y,z in planar.vertices_m])
    assert mirrored.detail == planar.detail


def test_limit_includes_one_hook_all_straights_and_all_real_arcs():
    radius = .048
    initial = 12-.4-1-radius*(math.pi/2-1)-radius*(math.pi/4-2*math.tan(math.pi/8))
    final = (initial+math.cos(math.pi/4),math.sin(math.pi/4),0.)
    exact = path(main_points_m=((0.,0.,0.),(initial,0.,0.),final))
    assert exact.length_cm == 1200
    assert exact.developed_length_cm == pytest.approx(1200)
    with pytest.raises(ValueError,match='supera 12 m'):
        path(main_points_m=((0.,0.,0.),(initial+.001,0.,0.),(final[0]+.001,final[1],0.)))
    with pytest.raises(ValueError,match='supera 12 m'):
        path(hook_start_cm=1e308)


def test_result_is_immutable_and_signature_binds_real_path_not_mark():
    main = [[0.,0.,0.],[2.,0.,0.],[3.,1.,0.]]
    direction = [0.,1.,0.]
    before = deepcopy((main,direction))
    bar = path(main_points_m=main,hook_start_direction=direction)
    assert (main,direction) == before
    main[-1][2] = direction[1] = 10
    assert bar.main_end_m == (3.,1.,0.)
    assert path(mark='99',label='Otro',identity='other',spacing_cm=10).signature == bar.signature
    assert path(hook_start_cm=41).signature != bar.signature
    assert path(main_points_m=((0.,0.,0.),(2.,0.,0.),(3.1,1.,0.))).signature != bar.signature
    with pytest.raises(FrozenInstanceError):
        bar.hook_end_cm = 40


@pytest.mark.parametrize('points',[
    ((0.,0.,0.),(2.,0.,0.),(3.,1.,.001)),
    ((0.,0.,0.),(2.,0.,0.),(2.,0.,1.)),
])
def test_nonplanar_route_relative_to_hook_is_not_projected(points):
    with pytest.raises(ValueError,match='mismo plano'):
        path(main_points_m=points)


def test_reversal_and_overlapping_tangencies_are_not_trimmed_to_fit():
    with pytest.raises(ValueError,match='180'):
        path(main_points_m=((0.,0.,0.),(1.,0.,0.),(0.,0.,0.)))
    with pytest.raises(ValueError,match='no caben|superponen'):
        path(main_points_m=((0.,0.,0.),(.05,0.,0.),(.05,1.,0.)))
    with pytest.raises(ValueError,match='no caben|superponen'):
        path(main_points_m=((0.,0.,0.),(1.,0.,0.),(1.,.02,0.)))


@pytest.mark.parametrize('changes',[
    {'main_points_m':None},{'main_points_m':[]},{'main_points_m':[(0,0,0)]},
    {'main_points_m':[(0,0,0),(1,0,0),(1,0,0)]},
    {'main_points_m':[(0,0,0),(1,0,0),(math.inf,1,0)]},
    {'main_points_m':[(0,0,0),(1,0,0),(True,1,0)]},
    {'hook_start_direction':(0,0,0)},{'hook_start_direction':(0,2,0)},
    {'hook_start_direction':(1,0,0)},{'hook_start_direction':(0,math.nan,0)},
    {'diameter_mm':None},{'diameter_mm':20},{'diameter_mm':True},
    {'hook_start_cm':0},{'hook_start_cm':-40},{'hook_start_cm':math.inf},
    {'spacing_cm':0},{'spacing_cm':False},{'identity':''},{'key':None},
    {'mark':23},{'label':' '},
])
def test_invalid_input_is_rejected_without_inference(changes):
    with pytest.raises(ValueError):
        path(**changes)
