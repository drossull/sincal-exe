"""Access slab/corbel geometry matches the reviewed Proyecto Puentes source."""
from copy import deepcopy
import math

import pytest

from sincal.web.abutment_scene import build_scene
from sincal.web.rebar import from_project
from tests.test_web_abutment_scene import example, find, points


def plane(points):
    """Return z(x,y) from a nondegenerate triple, independent of mesh order."""
    a=points[0]
    for b in points[1:]:
        for c in points[2:]:
            u=[b[i]-a[i] for i in range(3)]
            v=[c[i]-a[i] for i in range(3)]
            determinant=u[0]*v[1]-u[1]*v[0]
            if abs(determinant)>1e-10:
                gx=(u[2]*v[1]-u[1]*v[2])/determinant
                gy=(u[0]*v[2]-u[2]*v[0])/determinant
                return lambda x,y:a[2]+gx*(x-a[0])+gy*(y-a[1])
    raise AssertionError('Degenerate section')


def roof(scene,x,y,key='back_wall',upper=True):
    for mesh in find(scene,key)['meshes']:
        vertices=mesh['vertices'];n=len(vertices)//2
        if min(p[0] for p in vertices)-1e-8<=x<=max(p[0] for p in vertices)+1e-8:
            return plane(vertices[n:] if upper else vertices[:n])(x,y)
    raise AssertionError('Outside strip')


@pytest.mark.parametrize('instance', ['entrada','salida'])
def test_legacy_console_is_present_with_provenance_and_source_state_unchanged(instance):
    data=example();state=from_project(data)[instance]
    old_data,old_state=deepcopy(data),deepcopy(state)
    scene=build_scene(data,instance,state)
    console=find(scene,'back_console')
    assert data==old_data and state==old_state
    assert console['parameters_mm']=={
        'consola_losa_acceso_ancho_apoyo':250.,
        'consola_losa_acceso_canto_vertical':250.,
        'consola_losa_acceso_solape_en_muro':50.}
    assert set(console['inherited_fields'])=={
        'incluir_consola_losa_acceso','consola_losa_acceso_ancho_apoyo',
        'consola_losa_acceso_canto_vertical','consola_losa_acceso_solape_en_muro'}
    assert 'por defecto' in console['note']
    assert find(scene,'access_slab')['meshes']
    assert all(b['element_key']=='abutment.footing' for b in scene['bars'])


@pytest.mark.parametrize('instance', ['entrada','salida'])
@pytest.mark.parametrize('skew,rotations', [(0,(0,0)),(-12,(0,0)),(12,(10,-7)),(-12,(-8,15))])
def test_slab_preserves_projected_length_each_wing_rotation_and_vertical_thickness(instance,skew,rotations):
    data=example();data['parametros_generales']['angulo_esviaje_puente']=skew
    for side,rotation in zip(('izq','der'),rotations):
        data['estribos'][f'rotacion_muro_ala_{instance}_{side}']=rotation
    scene=build_scene(data,instance)
    slab=find(scene,'access_slab')
    side_sign=-1 if instance=='entrada' else 1
    reach=3/math.cos(math.radians(skew))
    for side,rotation in zip(('left','right'),rotations):
        # The inner root of the actual wing supplies the starting point;
        # source rotations must be retained separately at both slab sides.
        start=scene['wing_geometry'][side]['main_footprint_m'][1]
        rho=math.radians(rotation)
        end=(start[0]-side_sign*reach*math.sin(rho),
             start[1]+side_sign*reach*math.cos(rho))
        actual_xy=[p[:2] for p in points(slab)]
        assert any(math.dist(p,start)<1e-8 for p in actual_xy)
        assert any(math.dist(p,end)<1e-8 for p in actual_xy)
        assert math.dist(start,end)==pytest.approx(reach)
    for mesh in slab['meshes']:
        vertices=mesh['vertices'];n=len(vertices)//2
        for lower,upper in zip(vertices[:n],vertices[n:]):
            assert lower[:2]==upper[:2]
            assert upper[2]-lower[2]==pytest.approx(.25)


def test_slab_keeps_real_transverse_breaks_and_longitudinal_slope():
    data=example();scene=build_scene(data,'entrada')
    # T34-like fixture: roadway axis at x=-0.823, right pavement edge x=2.677.
    breakpoint=2.677
    factor=math.sqrt(1+.005**2)
    seen=set()
    for mesh in find(scene,'access_slab')['meshes']:
        vertices=mesh['vertices'];n=len(vertices)//2
        top=vertices[n:];xmin=min(p[0] for p in top);xmax=max(p[0] for p in top)
        assert not xmin+1e-8<breakpoint<xmax-1e-8
        x=(xmin+xmax)/2;y=sum(p[1] for p in top)/n
        surface=plane(top)
        desired=-.02*factor if x<breakpoint else -.01*factor
        assert surface(x+.01,y)-surface(x,y)==pytest.approx(desired*.01)
        assert surface(x,y+.01)-surface(x,y)==pytest.approx(.005*.01)
        assert surface(x,y)==pytest.approx(roof(scene,x,y))
        seen.add('pavement' if x<breakpoint else 'sidewalk')
    assert seen=={'pavement','sidewalk'}


@pytest.mark.parametrize('instance,wall_depth',[('entrada',.50125),('salida',.49875)])
def test_console_has_25_cm_free_edge_and_exact_45_degree_soffit(instance,wall_depth):
    scene=build_scene(example(),instance)
    for mesh in find(scene,'back_console')['meshes']:
        vertices=mesh['vertices'];assert len(vertices)==8
        for wall_i,outer_i in ((0,3),(1,2)):
            wall,outer=vertices[wall_i],vertices[outer_i]
            wall_top,outer_top=vertices[wall_i+4],vertices[outer_i+4]
            assert wall[0]==outer[0]
            assert abs(outer[1]-wall[1])==pytest.approx(.25)
            assert outer[2]-wall[2]==pytest.approx(.25)
            assert outer_top[2]-outer[2]==pytest.approx(.25)
            assert wall_top[2]-wall[2]==pytest.approx(wall_depth)
            assert wall_top[2]==pytest.approx(roof(scene,*wall_top[:2])-.25)
            assert outer_top[2]==pytest.approx(roof(scene,*outer_top[:2])-.25)


@pytest.mark.parametrize('instance',['entrada','salida'])
def test_chamfers_end_at_console_soffit_without_changing_plan(instance):
    data=example();data['estribos'].update(incluir_chaflanes_estribos=True,chaflan_estribos_medida=250)
    with_console=build_scene(data,instance)
    data['estribos']['incluir_consola_losa_acceso']=False
    without_console=build_scene(data,instance)
    for side in ('left','right'):
        actual=find(with_console,side+'_wing');previous=find(without_console,side+'_wing')
        assert actual['chamfer']['footprint_m']==previous['chamfer']['footprint_m']
        current=actual['meshes'][-1]['vertices'];old=previous['meshes'][-1]['vertices']
        assert current[:3]==old[:3]
        for now,before in zip(current[3:],old[3:]):
            assert now[:2]==before[:2] and now[2]<before[2]
            assert now[2]==pytest.approx(roof(with_console,*now[:2],key='back_console',upper=False))


def test_explicit_false_and_dimensions_override_inheritance():
    data=example();data['estribos']['incluir_consola_losa_acceso']=False
    scene=build_scene(data,'entrada')
    assert find(scene,'access_slab')
    assert not any(e['key']=='abutment.back_console' for e in scene['elements'])
    data['estribos'].update(incluir_consola_losa_acceso=True,
        consola_losa_acceso_ancho_apoyo=320,consola_losa_acceso_canto_vertical=180,
        consola_losa_acceso_solape_en_muro=70)
    scene=build_scene(data,'entrada');console=find(scene,'back_console')
    assert console['inherited_fields']==[]
    assert console['parameters_mm']['consola_losa_acceso_solape_en_muro']==70
    for mesh in console['meshes']:
        p=mesh['vertices']
        assert abs(p[3][1]-p[0][1])==pytest.approx(.32)
        assert p[7][2]-p[3][2]==pytest.approx(.18)
    data['estribos']['incluir_losas_acceso']=False
    scene=build_scene(data,'entrada')
    assert not any(e['key'] in ('abutment.back_console','abutment.access_slab') for e in scene['elements'])


@pytest.mark.parametrize('value',[None,0,-20,True,float('nan')])
def test_invalid_explicit_console_measure_is_not_silently_defaulted(value):
    data=example();data['estribos']['consola_losa_acceso_ancho_apoyo']=value
    scene=build_scene(data,'entrada')
    assert find(scene,'access_slab')
    assert not any(e['key']=='abutment.back_console' for e in scene['elements'])
    assert any('consola_losa_acceso_ancho_apoyo' in issue for issue in scene['issues'])
