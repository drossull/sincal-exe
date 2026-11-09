"""Physical corner concrete follows the source dimensions, not a screen symbol."""
from copy import deepcopy
import math

import pytest

from sincal.web.abutment_scene import build_scene
from sincal.web.rebar import from_project
from tests.test_web_abutment_scene import example, find


@pytest.mark.parametrize('instance', ['entrada', 'salida'])
@pytest.mark.parametrize('skew,rotation', [(0, 0), (-12, 0), (12, 15), (-12, -15)])
def test_inner_chamfers_follow_both_faces_without_moving_existing_concrete(instance, skew, rotation):
    data=example()
    data['parametros_generales']['angulo_esviaje_puente']=skew
    for side in ('izq','der'):
        data['estribos'][f'rotacion_muro_ala_{instance}_{side}']=rotation
    baseline=build_scene(data,instance)
    data['estribos'].update(incluir_chaflanes_estribos=True,chaflan_estribos_medida=250)
    before=deepcopy(data)
    actual=build_scene(data,instance)
    assert data==before
    assert [e['key'] for e in actual['elements']]==[e['key'] for e in baseline['elements']]
    for side, direction in [('left',1),('right',-1)]:
        wing=find(actual,side+'_wing')
        assert wing['meshes'][:-1]==find(baseline,side+'_wing')['meshes']
        triangle=wing['chamfer']['footprint_m']
        corner,back,along=triangle
        source=actual['wing_geometry'][side]
        assert corner==pytest.approx(source['main_footprint_m'][1])
        assert math.dist(corner,back)==pytest.approx(.25)
        assert math.dist(corner,along)==pytest.approx(.25)
        angle=math.radians(skew)
        assert back==pytest.approx([corner[0]+direction*.25*math.cos(angle),
                                    corner[1]+direction*.25*math.sin(angle)])
        axis=source['frame']['axis_u']
        assert along==pytest.approx([corner[i]+.25*axis[i] for i in range(2)])
        mesh=wing['meshes'][-1]
        assert mesh['part']=='wing_back_chamfer' and len(mesh['vertices'])==6
        assert {p[2] for p in mesh['vertices'][:3]}=={1.5}
        assert all(p[2]>1.5 for p in mesh['vertices'][3:])
    for element in baseline['elements']:
        if element['key'] not in ('abutment.left_wing','abutment.right_wing'):
            assert element==next(e for e in actual['elements'] if e['key']==element['key'])


def test_chamfers_do_not_change_steel_and_are_rebuilt_from_the_json_measure():
    data=example();state=from_project(data)['entrada']
    # Exercise the path that rebuilds wing meshes after editing parameters.
    profile=build_scene(data,'entrada')['wing_geometry']['left']
    state['wings']={'left':{'geometry':dict(profile['geometry']), 'geometry_confirmed':True}}
    baseline=build_scene(data,'entrada',state,use_state_geometry=True)
    data['estribos'].update(incluir_chaflanes_estribos=True,chaflan_estribos_medida=300)
    old_state=deepcopy(state)
    actual=build_scene(data,'entrada',state,use_state_geometry=True)
    assert state==old_state and actual['bars']==baseline['bars']
    for side in ('left','right'):
        wing=find(actual,side+'_wing')
        assert wing['chamfer']['measure_m']==.3
        assert wing['meshes'][-1]['part']=='wing_back_chamfer'
        assert wing['meshes'][:-1]==find(baseline,side+'_wing')['meshes']


@pytest.mark.parametrize('measure',[None,0,-250,True,float('nan')])
def test_missing_or_invalid_measure_is_not_invented(measure):
    data=example()
    data['estribos'].update(incluir_chaflanes_estribos=True,chaflan_estribos_medida=measure)
    scene=build_scene(data,'entrada')
    assert any('chaflan_estribos_medida' in s for s in scene['issues'])
    assert not any('chamfer' in e for e in scene['elements'])
