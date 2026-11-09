"""Canto bars share one entered total and retain real covers and anchorage."""
from copy import deepcopy
import math

import pytest

from sincal.rebar.model import DENSIDAD_ACERO_KG_M3
from sincal.rebar.wing_edge import build_wing_edge
from tests.test_wing_mesh_geometry import configured, dot, inward_plane


def fixture(side='left',instance='entrada',skew=-12,rotation=0,hook=True):
    data,abutment,wing,profile = configured(side,skew,True,rotation,instance)
    abutment['wings'] = {side:wing}
    state = {'quantity':4,'diameter_mm':16,'top_hook_enabled':hook,'top_hook_cm':20,
             'total_cm':650,'min_extension_cm':100,'mark':'51','removed_pieces':[]}
    return data,abutment,profile,state


def local(point,profile):
    frame = profile['frame']
    delta = tuple(value-zero for value,zero in zip(point,frame['origin_m']))
    return dot(delta,frame['axis_u']),dot(delta,frame['inward']),delta[2]


@pytest.mark.parametrize('side',['left','right'])
@pytest.mark.parametrize('instance',['entrada','salida'])
@pytest.mark.parametrize('skew,rotation',[(0,0),(-12,0),(12,0),(-12,5),(12,-5)])
@pytest.mark.parametrize('hook',[False,True])
def test_complete_edge_has_uniform_depths_fixed_total_and_real_concrete(side,instance,skew,rotation,hook):
    data,abutment,profile,state = fixture(side,instance,skew,rotation,hook)
    before = deepcopy((data,abutment,profile,state))
    result = build_wing_edge(profile,state,abutment,side)
    assert result['valid'],result['issues']
    assert (data,abutment,profile,state) == before
    assert len(result['bars']) == state['quantity']
    assert len(result['marks']) == len(result['details']) == 1
    mark,detail = result['marks'][0],result['details'][0]
    assert mark['quantity'] == detail['quantity'] == state['quantity']
    assert mark['unit_length_cm'] == state['total_cm']
    assert mark['total_length_cm'] == state['quantity']*state['total_cm']
    assert mark['length_variants'] == ()
    expected_weight = state['quantity']*state['total_cm']/100*math.pi*(state['diameter_mm']/2000)**2*DENSIDAD_ACERO_KG_M3
    assert result['total_kg'] == pytest.approx(expected_weight)
    assert mark['hook_count'] == int(hook)
    assert len(detail['bends']) == 1+int(hook)
    assert len(detail['partials_cm']) == 3+int(hook)
    extensions = {record['id']:record['extension_cm'] for record in result['edge_extensions_cm']}
    assert min(extensions.values()) >= 100-1e-8
    steel_radius = state['diameter_mm']/2000
    covers = abutment['wings'][side]['cover']
    thickness = profile['geometry']['thickness_cm']/100
    first,last = covers['outside_cm']/100+steel_radius,thickness-covers['inside_cm']/100-steel_radius
    expected_depths = [first+(last-first)*i/(state['quantity']-1) for i in range(state['quantity'])]
    concrete = profile['meshes']+profile['footing_meshes']
    solids = [tuple(inward_plane(item,face) for face in item['faces']) for item in concrete]
    extension_mesh = profile['meshes'][1]
    diagonal = inward_plane(extension_mesh,(0,1,5,4))
    theta = math.radians(skew)
    half_x = abutment['geometry']['ancho_cm']/200*math.cos(theta)
    half_s = abutment['geometry']['largo_cm']/200
    for index,bar in enumerate(result['bars']):
        assert bar['id'] == f'wing:{side}:edge:{index}'
        assert bar['key'] == f'wing_{side}_edge' and bar['level'] == 'edge'
        assert bar['length_cm'] == state['total_cm']
        assert bar['developed_length_cm'] == pytest.approx(state['total_cm'],abs=1e-7)
        assert bar['bend_radius_cm'] == pytest.approx(state['diameter_mm']*.3)
        assert bar['points'][-1] == bar['main_end']
        assert bar['main_end'][2] < profile['frame']['origin_m'][2]
        for point in bar['points']:
            assert local(point,profile)[1] == pytest.approx(expected_depths[index])
            assert any(all(distance(point)>=-1e-8 for distance in faces) for faces in solids), (bar['id'],point)
            if point[2] < profile['frame']['origin_m'][2]:
                clear = abutment['cover']['lateral_cm']/100+steel_radius
                assert half_x-abs(point[0]) >= clear-1e-8
                assert half_s-abs(point[1]*math.cos(theta)-point[0]*math.sin(theta)) >= clear-1e-8
                assert point[2] >= abutment['cover']['inferior_cm']/100+steel_radius-1e-8
        # The real diagonal segment has its requested normal cover. Its
        # continuation remains collinear even after entering the footing.
        assert diagonal(bar['main_end']) == pytest.approx(covers['diagonal_cm']/100+steel_radius,abs=1e-8)
    assert any('penetra en la zapata' in issue['message'] for issue in result['issues'])


def test_partial_variations_are_declared_without_making_the_total_variable():
    _,abutment,profile,state = fixture()
    result = build_wing_edge(profile,state,abutment,'left')
    assert result['valid'],result['issues']
    detail = result['details'][0]
    assert detail['detail_note'] == 'Largo total fijo; las parciales varían entre fierros. Se representa una pieza de la serie.'
    assert sum(r['min_cm'] != r['max_cm'] for r in detail['partial_ranges_cm']) >= 2
    assert detail['total_cm'] == 650 and detail['length_variants'] == ()
    assert max(r['extension_cm'] for r in result['edge_extensions_cm']) > min(r['extension_cm'] for r in result['edge_extensions_cm'])


def test_insufficient_total_does_not_reduce_the_minimum_or_extend_the_geometry():
    _,abutment,profile,state = fixture()
    state['total_cm'] = 600
    before = deepcopy((abutment,profile,state))
    result = build_wing_edge(profile,state,abutment,'left')
    assert not result['valid'] and not result['bars']
    assert any('98.6 cm' in issue['message'] and '100 cm' in issue['message'] for issue in result['issues'])
    assert (abutment,profile,state) == before


def test_entered_nonhundred_total_is_preserved_and_lower_cover_is_not_relaxed():
    _,abutment,profile,state = fixture()
    state['total_cm'] = 643.25
    result = build_wing_edge(profile,state,abutment,'left')
    assert result['valid'],result['issues']
    assert all(bar['developed_length_cm'] == pytest.approx(643.25) for bar in result['bars'])
    assert all(bar['length_cm'] == 644 for bar in result['bars'])
    state['total_cm'] = 800
    invalid = build_wing_edge(profile,state,abutment,'left')
    assert not invalid['valid'] and not invalid['bars']
    assert any('recubrimiento inferior de la zapata' in issue['message'] for issue in invalid['issues'])
    assert state['total_cm'] == 800


def test_hook_is_optional_without_moving_the_diagonal_or_changing_total():
    _,abutment,profile,state = fixture()
    hooked = build_wing_edge(profile,state,abutment,'left')
    state['top_hook_enabled'] = False
    state['top_hook_cm'] = None
    plain = build_wing_edge(profile,state,abutment,'left')
    assert hooked['valid'] and plain['valid']
    assert plain['marks'][0]['hook_count'] == 0
    assert len(plain['details'][0]['bends']) == 1
    assert plain['total_kg'] == hooked['total_kg']
    for original,current in zip(hooked['edge_extensions_cm'],plain['edge_extensions_cm']):
        assert current['extension_cm'] > original['extension_cm']


def test_deleting_one_edge_piece_updates_only_its_real_quantity_and_length():
    _,abutment,profile,state = fixture()
    before = build_wing_edge(profile,state,abutment,'left')
    removed = before['bars'][1]
    state['removed_pieces'] = [{key:removed[key] for key in ('id','signature')}]
    reduced = build_wing_edge(profile,state,abutment,'left')
    assert reduced['valid'],reduced['issues']
    assert {bar['id'] for bar in reduced['bars']} == {bar['id'] for bar in before['bars']}-{removed['id']}
    assert reduced['marks'][0]['quantity'] == 3
    assert before['marks'][0]['total_length_cm']-reduced['marks'][0]['total_length_cm'] == 650
    assert len(reduced['edge_extensions_cm']) == 3
    assert reduced['removed_bars'][0]['status'] == 'removed'
    state['mark'] = '62'
    assert build_wing_edge(profile,state,abutment,'left')['removed_bars'][0]['status'] == 'removed'
    state['quantity'] = 3
    changed = build_wing_edge(profile,state,abutment,'left')
    assert not changed['valid'] and not changed['bars']
    assert changed['removed_bars'][0]['status'] == 'unresolved'
    state['quantity'] = 4
    state['mark'] = '51'
    state['removed_pieces'] = []
    assert build_wing_edge(profile,state,abutment,'left')['bars'] == before['bars']
    state['removed_pieces'] = [{key:bar[key] for key in ('id','signature')} for bar in before['bars']]
    empty = build_wing_edge(profile,state,abutment,'left')
    assert empty['valid'] and not empty['bars'] and not empty['marks']
    assert empty['edge_extensions_cm'] == [] and empty['total_kg'] == 0


def test_absent_extension_does_not_request_edge_parameters_or_generate_a_bar():
    _,abutment,_,profile = configured(extension=False)
    result = build_wing_edge(profile,{},abutment,'left')
    assert result['valid'] and not result['issues'] and not result['bars']


@pytest.mark.parametrize('changes,message',[
    ({'quantity':None},'cantidad'),({'quantity':1},'mínimo 2'),({'quantity':3.5},'entera'),
    ({'quantity':5001},'máximo 5000'),({'quantity':50},'superponer'),
    ({'diameter_mm':None},'diámetro'),({'diameter_mm':20},'diámetro'),
    ({'total_cm':None},'largo total'),({'total_cm':1201},'1200'),
    ({'min_extension_cm':99},'100 cm'),({'min_extension_cm':None},'100 cm'),
    ({'top_hook_enabled':'true'},'gancho superior'),({'top_hook_cm':0},'tramo recto'),
    ({'mark':''},'marca válida'),({'removed_pieces':[{}]},'identidad'),
])
def test_missing_or_invalid_inputs_do_not_acquire_defaults(changes,message):
    _,abutment,profile,state = fixture()
    state.update(changes)
    result = build_wing_edge(profile,state,abutment,'left')
    assert not result['valid'] and not result['bars']
    assert any(message.lower() in issue['message'].lower() for issue in result['issues'])


@pytest.mark.parametrize('source,key',[('wing','outside_cm'),('wing','diagonal_cm'),
                                       ('foundation','inferior_cm'),('foundation','superior_cm')])
def test_missing_cover_is_explicitly_blocked(source,key):
    _,abutment,profile,state = fixture()
    cover = abutment['wings']['left']['cover'] if source=='wing' else abutment['cover']
    cover[key] = None
    result = build_wing_edge(profile,state,abutment,'left')
    assert not result['valid'] and not result['bars']
    assert any('recubrimientos' in issue['message'] for issue in result['issues'])
