"""Explicit routes without endpoint hooks preserve exact physical endpoints."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import math

import pytest

from sincal.rebar.detail import detail_dimension_metadata, polyline_developed_length_m, polyline_render_points
from sincal.rebar.model import DIAMETROS_DISPONIBLES_MM
from sincal.rebar.wing_exterior import make_open_path


def path(**changes):
    values = dict(main_points_m=((0.,0.,3.),(0.,0.,2.),(2.,0.,0.),(2.7,0.,-.7)),
                  diameter_mm=16,identity='wing:left:edge:0',key='wing_left_edge',
                  mark='51',label='Borde explícito',spacing_cm=20.)
    values.update(changes)
    return make_open_path(**values)


def assert_points(actual,expected):
    assert len(actual) == len(expected)
    for a,b in zip(actual,expected):
        assert a == pytest.approx(b,abs=1e-12)


def test_vertical_diagonal_and_collinear_extension_have_only_one_bend():
    bar = path()
    radius = .048
    expected = (1+2.7*math.sqrt(2)-2*radius*math.tan(math.pi/8)+radius*math.pi/4)*100
    assert bar.hook_start_cm == bar.hook_end_cm == 0
    assert bar.start_m == bar.main_start_m == bar.vertices_m[0] == bar.points_m[0] == (0,0,3)
    assert bar.end_m == bar.main_end_m == bar.vertices_m[-1] == bar.points_m[-1] == (2.7,0,-.7)
    assert bar.developed_length_cm == pytest.approx(expected)
    assert polyline_developed_length_m(bar)*100 == pytest.approx(expected)
    assert polyline_developed_length_m(bar.detail)*100 == pytest.approx(expected)
    assert bar.length_cm == math.ceil(expected)
    assert len(bar.detail.partials_cm) == len(bar.detail.partial_segments_m) == 3
    assert sum(bar.detail.partials_cm) == bar.length_cm
    assert bar.detail.partials_cm[-1] == math.ceil(.7*math.sqrt(2)*100)
    assert bar.detail.quantity == 1 and bar.detail.length_variants == ()
    assert [bend['bend_degrees'] for bend in detail_dimension_metadata(bar.detail)['bends']] == [45]


@pytest.mark.parametrize('points',[
    ((0.,0.,0.),(3.,0.,0.)),
    ((5.,-2.,8.),(6.,0.,10.)),
    ((0.,0.,0.),(0.,0.,1.),(0.,0.,3.)),
])
def test_straight_paths_have_no_bend_and_do_not_lose_endpoint_lengths(points):
    bar = path(main_points_m=points)
    assert all(abs(b)<1e-12 for b in bar.bulges)
    assert not detail_dimension_metadata(bar.detail)['bends']
    expected = sum(math.dist(a,b) for a,b in zip(points,points[1:]))*100
    assert bar.developed_length_cm == pytest.approx(expected)
    assert bar.length_cm == math.ceil(expected-1e-9)
    assert bar.main_start_m == points[0]
    assert bar.main_end_m == points[-1]
    assert sum(bar.detail.partials_cm) == bar.length_cm


@pytest.mark.parametrize('diameter',DIAMETROS_DISPONIBLES_MM)
@pytest.mark.parametrize('angle',[-80,-30,30,80])
def test_all_diameters_and_turns_keep_three_diameter_arcs(diameter,angle):
    radians = math.radians(angle)
    points = ((0.,0.,0.),(2.,0.,0.),(2+math.cos(radians),math.sin(radians),0.))
    bar = path(main_points_m=points,diameter_mm=diameter)
    radius = 3*diameter/1000
    expected = (3-2*radius*math.tan(abs(radians)/2)+radius*abs(radians))*100
    assert bar.developed_length_cm == pytest.approx(expected)
    assert polyline_developed_length_m(bar)*100 == pytest.approx(expected)
    bends = [(i,b) for i,b in enumerate(bar.bulges) if abs(b)>1e-12]
    assert len(bends) == 1
    i,bulge = bends[0]
    chord = math.dist(bar.vertices_m[i],bar.vertices_m[i+1])
    assert chord/(2*math.sin(2*math.atan(abs(bulge)))) == pytest.approx(radius)
    assert bar.main_start_m == points[0] and bar.main_end_m == points[-1]


def test_arcs_are_shared_once_between_partial_segments():
    bar = path(main_points_m=((0.,0.,0.),(1.,0.,0.),(1.,2.,0.),(4.,2.,0.)))
    radius = .048
    expected = (6-4*radius+math.pi*radius)*100
    assert bar.developed_length_cm == pytest.approx(expected)
    assert bar.length_cm == math.ceil(expected)
    components = ((1-radius+math.pi*radius/4)*100,
                  (2-2*radius+math.pi*radius/2)*100,
                  (3-radius+math.pi*radius/4)*100)
    assert bar.detail.partials_cm[-1] == math.ceil(components[-1])
    assert bar.detail.partials_cm[1] == math.ceil(sum(components[1:]))-math.ceil(components[-1])
    assert sum(bar.detail.partials_cm) == bar.length_cm
    assert [bend['bend_degrees'] for bend in detail_dimension_metadata(bar.detail)['bends']] == [90,90]


def test_arbitrary_3d_orientation_lifts_the_same_flat_geometry():
    origin = (5.,-2.,8.)
    u = (1/3,2/3,2/3)
    v = (-2/math.sqrt(5),1/math.sqrt(5),0.)
    local = ((0.,0.),(2.,0.),(3.,1.),(4.,1.))
    def lift(p):
        return tuple(zero+p[0]*a+p[1]*b for zero,a,b in zip(origin,u,v))
    main = tuple(map(lift,local))
    bar = path(main_points_m=main)
    planar = path(main_points_m=tuple((x,y,0.) for x,y in local))
    assert_points(bar.detail.vertices_m,planar.detail.vertices_m)
    assert_points(bar.points_m,tuple(map(lift,polyline_render_points(bar.detail))))
    assert bar.length_cm == planar.length_cm
    assert bar.developed_length_cm == pytest.approx(planar.developed_length_cm)
    assert bar.main_start_m == main[0] and bar.main_end_m == main[-1]


def test_exact_limit_and_rounding_never_change_real_endpoints():
    straight = path(main_points_m=((0.,0.,0.),(12.,0.,0.)))
    assert straight.length_cm == straight.developed_length_cm == 1200
    radius = .048
    first = 12-1-radius*(math.pi/2-2)
    main = ((0.,0.,0.),(first,0.,0.),(first,1.,0.))
    curved = path(main_points_m=main)
    assert curved.length_cm == 1200
    assert curved.developed_length_cm == pytest.approx(1200)
    assert curved.main_end_m == main[-1]
    with pytest.raises(ValueError,match='supera 12 m'):
        path(main_points_m=((0.,0.,0.),(first+.001,0.,0.),(first+.001,1.,0.)))
    fractional = path(main_points_m=((0.,0.,0.),(3.12345,0.,0.)))
    assert fractional.main_end_m == (3.12345,0.,0.)
    assert fractional.length_cm == 313
    assert fractional.developed_length_cm == pytest.approx(312.345)


def test_physical_signature_and_immutability_do_not_depend_on_display_labels():
    main = [[0.,0.,0.],[2.,0.,0.],[3.,1.,0.]]
    before = deepcopy(main)
    bar = path(main_points_m=main)
    assert main == before
    main[-1][0] = 9
    assert bar.end_m == (3.,1.,0.)
    assert path(main_points_m=before,mark='99',identity='new',label='Otro',spacing_cm=10).signature == bar.signature
    assert path(main_points_m=before,diameter_mm=22).signature != bar.signature
    assert path(main_points_m=before,key='another_family').signature != bar.signature
    assert path(main_points_m=main).signature != bar.signature
    with pytest.raises(FrozenInstanceError):
        bar.hook_start_cm = 40


def test_nonplanar_reversed_and_overlapping_bends_are_rejected():
    with pytest.raises(ValueError,match='mismo plano'):
        path(main_points_m=((0.,0.,0.),(2.,0.,0.),(3.,1.,0.),(4.,1.,.01)))
    with pytest.raises(ValueError,match='180'):
        path(main_points_m=((0.,0.,0.),(1.,0.,0.),(0.,0.,0.)))
    for main in (((0.,0.,0.),(.02,0.,0.),(.02,1.,0.)),
                 ((0.,0.,0.),(1.,0.,0.),(1.,.05,0.),(2.,.05,0.))):
        with pytest.raises(ValueError,match='no caben|superponen'):
            path(main_points_m=main)


@pytest.mark.parametrize('changes',[
    {'main_points_m':None},{'main_points_m':[]},{'main_points_m':[(0,0,0)]},
    {'main_points_m':[(0,0,0),(0,0,0)]},{'main_points_m':[(0,0,0),(1,0)]},
    {'main_points_m':[(0,0,0),(math.inf,0,0)]},{'main_points_m':[(0,0,0),(True,0,0)]},
    {'diameter_mm':None},{'diameter_mm':20},{'diameter_mm':True},
    {'spacing_cm':0},{'spacing_cm':math.nan},{'spacing_cm':'20'},
    {'identity':''},{'key':None},{'mark':3},{'label':' '},
])
def test_invalid_input_does_not_acquire_defaults(changes):
    with pytest.raises(ValueError):
        path(**changes)
