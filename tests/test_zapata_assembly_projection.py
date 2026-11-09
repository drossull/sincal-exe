"""CAD projection regressions independent of the physical model builder."""
import math
from types import SimpleNamespace

import pytest

from sincal.cad.zapata_views import project_footing_assembly


def curved_bar(*, key="mesh_x", level="inferior", theta=0.0, mirror=False):
    radius = .066
    u = (math.cos(theta), math.sin(theta), 0.0)
    v = (0.0, 0.0, -1.0 if mirror else 1.0)
    def lift(point):
        x, y = point
        return tuple(x*u[i] + y*v[i] for i in range(3))
    vertices = ((0,1+radius),(0,radius),(radius,0),
                (2-radius,0),(2,radius),(2,1+radius))
    samples = [vertices[0], vertices[1]]
    for angle in range(185,271,5):
        angle = math.radians(angle)
        samples.append((radius + radius*math.cos(angle), radius+radius*math.sin(angle)))
    samples.append(vertices[3])
    for angle in range(275,361,5):
        angle = math.radians(angle)
        samples.append((2-radius+radius*math.cos(angle), radius+radius*math.sin(angle)))
    samples.append(vertices[-1])
    return SimpleNamespace(id="mesh:bottom:0:0",placement_id="mesh:bottom:0",key=key,
        mark="1",level=level,diameter_mm=22,coordinate_m=0,axis_u=u,axis_v=v,
        vertices_m=tuple(map(lift,vertices)),bulges=(0,math.tan(math.pi/8),0,math.tan(math.pi/8),0,0),
        points_m=tuple(map(lift,samples)),main_start_m=lift(vertices[2]),
        main_end_m=lift(vertices[3]),lap_segments_m=((lift((.5,0)),lift((1.5,0))),))


def test_parallel_view_preserves_real_arc_radius_and_mirrors_bulges():
    for mirror in (False,True):
        bar=curved_bar(mirror=mirror)
        piece,=project_footing_assembly(SimpleNamespace(bars=(bar,)),"FR")
        assert piece.source_id==bar.id and piece.mark==bar.mark
        expected_sign=-1 if mirror else 1
        for a,b,bulge in zip(piece.vertices_m,piece.vertices_m[1:],piece.bulges):
            if abs(bulge)>1e-9:
                assert bulge*expected_sign>0
                radius=math.dist(a,b)/(2*math.sin(2*math.atan(abs(bulge))))
                assert radius==pytest.approx(.066)
        assert piece.lap_segments_m==(((.5,0),(1.5,0)),)


def test_plan_flattens_vertical_hooks_without_inventing_a_plan_radius():
    bar=curved_bar(level="superior")
    piece,=project_footing_assembly(SimpleNamespace(bars=(bar,)),"FF")
    assert piece.vertices_m==((0.0,0.0),(2.0,0.0))
    assert not any(piece.bulges)


def test_oblique_projection_is_sampled_not_given_a_false_circular_radius():
    bar=curved_bar(theta=math.radians(30))
    piece,=project_footing_assembly(SimpleNamespace(bars=(bar,)),"FR")
    assert len(piece.vertices_m)>len(bar.vertices_m)
    assert not any(piece.bulges)
    assert piece.vertices_m[0]==pytest.approx((0,1.066))
    assert piece.vertices_m[-1]==pytest.approx((2*math.cos(math.radians(30)),1.066))


def section_bar(mark,start,end):
    return SimpleNamespace(id=f"y:{mark}",placement_id=f"y:{mark}",key="mesh_y",mark=mark,
        level="superior",diameter_mm=22,coordinate_m=2,
        main_start_m=(2,start,1.417),main_end_m=(2,end,1.417))


def test_transverse_circles_are_intersections_of_each_real_lap_piece():
    bars=(section_bar("3",-3,-1),section_bar("3A",-1,3),section_bar("3B",-.5,.5))
    result=project_footing_assembly(SimpleNamespace(bars=bars),"FR")
    assert [piece.mark for piece in result]==["3A","3B"]
    assert all(piece.kind=="circle" for piece in result)
    assert all(piece.vertices_m==((2.0,1.417),) for piece in result)
    # Two coincident axes remain two physical pieces in a lap, not one bar
    # or one circle whose quantity has been silently recomputed.
    assert len({piece.source_id for piece in result})==2


@pytest.mark.parametrize("skew", [-30, 30])
def test_skew_fr_uses_one_representative_station_and_common_section_origin(skew):
    from sincal.web.rebar import defaults, domain
    from sincal.rebar.assembly import build_footing_assembly

    state=defaults()
    state["geometry"]["esviaje_grados"]=skew
    for rule in state["rules"]:
        if rule["key"] in ("mesh_x", "mesh_y"):
            rule["spacing_cm"]=150
    geometry,cover,rules=domain(state)
    assembly=build_footing_assembly(geometry,cover,rules)
    assert assembly.is_valid, assembly.schedule.issues
    station=min((bar.coordinate_m for bar in assembly.bars if bar.key=="mesh_x"),key=abs)
    assert abs(station)>.5  # Deliberately exposes the old zero-station mismatch.
    shift=math.tan(math.radians(skew))*station
    projected=project_footing_assembly(assembly,"FR")
    source={bar.id:bar for bar in assembly.bars}
    expected_sections={}
    for bar in assembly.bars:
        if bar.key not in ("mesh_y", "suple", "lateral_y"):
            continue
        a,b=bar.main_start_m,bar.main_end_m
        if abs(b[1]-a[1])<1e-12:
            continue
        t=(station-a[1])/(b[1]-a[1])
        if 0<=t<=1:
            expected_sections[bar.id]=(a[0]+t*(b[0]-a[0])-shift,a[2]+t*(b[2]-a[2]))
    sections=[piece for piece in projected if piece.kind=="circle"]
    assert {piece.source_id for piece in sections}==set(expected_sections)
    for piece in sections:
        assert piece.vertices_m[0]==pytest.approx(expected_sections[piece.source_id])
    mesh=[piece for piece in projected if piece.key=="mesh_x"]
    assert mesh
    for piece in mesh:
        bar=source[piece.source_id]
        assert bar.coordinate_m==station
        for actual, point in zip(piece.vertices_m,bar.vertices_m):
            assert actual==pytest.approx((point[0]-shift,point[2]))
    # Independently check the selected rectangular section's real side cover.
    sec=1/math.cos(math.radians(skew))
    for piece in projected:
        inset=cover.lateral_m+piece.diameter_mm/2000
        for x,z in piece.vertices_m:
            assert abs(x)<=geometry.ancho_m/2-inset*sec+1e-9
            assert z>=cover.inferior_m+piece.diameter_mm/2000-1e-9
            assert z<=geometry.alto_m-cover.superior_m-piece.diameter_mm/2000+1e-9


@pytest.mark.parametrize("view", ["AA"])
def test_sections_intersect_transverse_bars_at_the_chosen_y_family_station(view):
    from sincal.web.rebar import defaults, domain
    from sincal.rebar.assembly import build_footing_assembly

    state=defaults()
    state["geometry"]["esviaje_grados"]=-30
    state["rules"][1]["spacing_cm"]=150
    assembly=build_footing_assembly(*domain(state))
    assert assembly.is_valid
    station=min((bar.coordinate_m for bar in assembly.bars if bar.key=="mesh_y"),key=abs)
    assert abs(station)>.05
    expected={}
    for bar in assembly.bars:
        if bar.key not in ("mesh_x", "lateral_x"):
            continue
        a,b=bar.main_start_m,bar.main_end_m
        if abs(b[0]-a[0])<1e-12:
            continue
        t=(station-a[0])/(b[0]-a[0])
        if 0<=t<=1:
            expected[bar.id]=(a[1]+t*(b[1]-a[1]),a[2]+t*(b[2]-a[2]))
    projected=project_footing_assembly(assembly,view)
    sections=[piece for piece in projected if piece.kind=="circle"]
    assert {piece.source_id for piece in sections}==set(expected)
    for piece in sections:
        assert piece.vertices_m[0]==pytest.approx(expected[piece.source_id])
