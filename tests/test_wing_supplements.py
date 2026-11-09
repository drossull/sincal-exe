"""Green supplements use real interior stations and exact one-hook paths."""
from copy import deepcopy
import math

import pytest

from sincal.rebar.wing_mesh import build_wing_mesh
from sincal.rebar.wing_supplements import build_wing_supplements
from sincal.web.wing_geometry import extract_geometry, build_wing_profile
from test_wing_interior_integration import configured_both
from test_wing_exterior_integration import assert_counts


def fixture(side='left', rotation=0, skew=0):
    project, abutment, state = configured_both(side, rotation=rotation, skew=skew)
    state['supplements'] = {
        'front': {'enabled': True, 'range_height_cm': 80, 'diameter_mm': 12, 'spacing_cm': 20,
                  'hook_cm': 40, 'straight_cm': 300, 'mark': '51', 'removed_pieces': []},
        'back': {'enabled': True, 'diameter_mm': 12, 'spacing_cm': 20,
                 'hook_cm': 40, 'straight_cm': 300, 'mark': '52', 'removed_pieces': []},
    }
    profile = build_wing_profile(extract_geometry(project, 'entrada', side, abutment), state['geometry'])
    return project, abutment, state, profile


def inner(profile, state, abutment, side='left'):
    values = {**state, **{key: state['interior'][key] for key in ('vertical', 'horizontal', 'removed_pieces')}}
    result = build_wing_mesh(profile, values, abutment, side, mesh='interior')
    assert result['valid'], result['issues']
    return result


def calculate(profile, state, abutment, side='left'):
    return build_wing_supplements(profile, state, abutment, side, inner(profile, state, abutment, side))


@pytest.mark.parametrize('side', ('left', 'right'))
@pytest.mark.parametrize('rotation', (-5, 0, 5))
def test_real_groups_have_independent_marks_one_hook_and_exact_development(side, rotation):
    project, abutment, state, profile = fixture(side, rotation, skew=-12)
    before = deepcopy((project, abutment, state, profile))
    result = calculate(profile, state, abutment, side)
    assert result['valid'], result['issues']
    assert_counts(result)
    assert {mark['mark'] for mark in result['marks']} == {'51', '52'}
    assert all(mark['hook_count'] == 1 for mark in result['marks'])
    for bar in result['bars']:
        assert bar['level'] == 'interior'
        assert bar['key'] in (f'wing_{side}_inner_supplement_front', f'wing_{side}_inner_supplement_back')
        assert bar['developed_length_cm'] == pytest.approx(40+math.pi/2*3.6+300)
        assert math.dist(*bar['vertices'][:2]) == pytest.approx(.4)
        assert bar['main_end'] == bar['vertices'][-1]
        assert sum(abs(bulge)>1e-10 for bulge in bar['bulges']) == (2 if rotation else 1)
        assert bar['lap_cm'] == 0
    if rotation:
        assert set(result['length_labels'].values()) == {'Desarrollo desde el gancho hasta el extremo libre'}
    assert (project, abutment, state, profile) == before


def test_nominal_ranges_share_frontal_crown_and_stations_start_at_main_midpoints():
    _, abutment, state, profile = fixture()
    principal = inner(profile, state, abutment)
    result = build_wing_supplements(profile, state, abutment, 'left', principal)
    assert result['valid'], result['issues']
    crown = profile['geometry']['front_height_cm']
    assert result['supplement_ranges_cm'] == {
        'front': {'start_cm': pytest.approx(crown-80), 'end_cm': pytest.approx(crown)},
        'back': {'start_cm': pytest.approx(crown), 'end_cm': pytest.approx(profile['geometry']['top_join_cm'])}}
    levels = sorted({bar['points'][0][2] for bar in principal['bars'] if '_inner_horizontal_' in bar['key']})
    midpoints = [(a+b)/2 for a,b in zip(levels,levels[1:])]
    origin = profile['frame']['origin_m'][2]
    stations = {}
    for name in ('front', 'back'):
        heights = sorted(bar['points'][0][2] for bar in result['bars'] if bar['key'].endswith('_'+name))
        low = result['supplement_ranges_cm'][name]['start_cm']/100+origin
        assert heights[0] == pytest.approx(next(z for z in midpoints if z>=low-1e-8))
        assert all(b-a == pytest.approx(.2) for a,b in zip(heights,heights[1:]))
        assert all(min(abs(z-base) for base in levels) >= .012-1e-8 for z in heights)
        stations[name] = heights
    assert stations['back'][0]-stations['front'][-1] <= .2+1e-8


def test_union_closes_with_extra_midpoint_without_moving_regular_stations():
    _, abutment, state, profile = fixture()
    state['supplements']['front']['spacing_cm'] = 80
    result = calculate(profile, state, abutment)
    assert result['valid'], result['issues']
    front = sorted(bar['points'][0][2] for bar in result['bars'] if bar['key'].endswith('_front'))
    back = sorted(bar['points'][0][2] for bar in result['bars'] if bar['key'].endswith('_back'))
    assert len(front) == 2  # The ordinary 80 cm progression fits only its first station.
    assert 0 < front[-1]-front[0] < .8
    assert back[0]-front[-1] <= .2+1e-8


def test_incompatible_spacing_rejects_collision_instead_of_shifting_mesh():
    _, abutment, state, profile = fixture()
    state['supplements']['front']['spacing_cm'] = 10
    before = deepcopy(state)
    result = calculate(profile, state, abutment)
    assert not result['valid']
    assert any('choca' in issue['message'] for issue in result['issues'])
    assert result['bars'] == result['marks'] == result['details'] == []
    assert state == before


def test_removing_main_horizontal_preserves_supplement_stations_and_identities():
    _, abutment, state, profile = fixture()
    principal = inner(profile, state, abutment)
    initial = build_wing_supplements(profile, state, abutment, 'left', principal)
    assert initial['valid'], initial['issues']
    chosen = next(bar for bar in principal['bars'] if '_inner_horizontal_' in bar['key'])
    state['interior']['removed_pieces'].append({key: chosen[key] for key in ('id','signature')})
    reduced_main = inner(profile, state, abutment)
    assert chosen['id'] not in {bar['id'] for bar in reduced_main['bars']}
    after = build_wing_supplements(profile, state, abutment, 'left', reduced_main)
    assert after['valid'], after['issues']
    assert after['bars'] == initial['bars']
    assert after['marks'] == initial['marks']


def test_supplement_removal_changes_only_its_group_and_restores():
    _, abutment, state, profile = fixture()
    initial = calculate(profile, state, abutment)
    selected = next(bar for bar in initial['bars'] if bar['key'].endswith('_front'))
    state['supplements']['front']['removed_pieces'].append({key: selected[key] for key in ('id','signature')})
    result = calculate(profile, state, abutment)
    assert result['valid'], result['issues']
    assert_counts(result)
    assert {bar['id'] for bar in result['bars']} == {bar['id'] for bar in initial['bars']}-{selected['id']}
    assert [mark for mark in result['marks'] if mark['key'].endswith('_back')] == [mark for mark in initial['marks'] if mark['key'].endswith('_back')]
    state['supplements']['front']['removed_pieces'].clear()
    assert calculate(profile, state, abutment)['bars'] == initial['bars']


def test_requested_development_cannot_end_inside_join_bend():
    _, abutment, state, profile = fixture(rotation=5)
    initial = calculate(profile, state, abutment)
    assert initial['valid'], initial['issues']
    bar = next(bar for bar in initial['bars'] if bar['key'].endswith('_back'))
    straight = math.dist(bar['vertices'][2],bar['vertices'][3])
    half_arc = bar['bend_radius_cm']/100*math.radians(5)/2
    state['supplements']['back']['straight_cm'] = (straight+half_arc)*100
    result = calculate(profile, state, abutment)
    assert not result['valid']
    assert any('termina dentro' in issue['message'] for issue in result['issues'])


@pytest.mark.parametrize('field,value', [('diameter_mm',None),('diameter_mm',20),('spacing_cm',0),
                                       ('hook_cm',0),('straight_cm',float('nan')),('range_height_cm',500)])
def test_missing_or_incompatible_inputs_fail_without_partial_results(field,value):
    _, abutment, state, profile = fixture()
    state['supplements']['front'][field] = value
    result = calculate(profile,state,abutment)
    assert not result['valid']
    assert result['bars'] == result['marks'] == result['details'] == []


def test_overlong_route_is_not_clipped_to_concrete_or_spliced():
    _, abutment, state, profile = fixture()
    state['supplements']['back']['straight_cm'] = 1000
    result = calculate(profile,state,abutment)
    assert not result['valid']
    assert any('moldaje' in issue['message'] or 'recubrimiento' in issue['message'] for issue in result['issues'])
    assert state['supplements']['back']['straight_cm'] == 1000


def test_disabled_groups_need_no_interior_but_enabled_groups_do():
    _, abutment, state, profile = fixture()
    state['interior']['enabled'] = False
    assert not build_wing_supplements(profile,state,abutment,'left',{'valid':False})['valid']
    for values in state['supplements'].values():
        values['enabled'] = False
    empty = build_wing_supplements(profile,state,abutment,'left',{'valid':False})
    assert empty['valid'] and empty['bars'] == []


def test_enabled_group_requires_a_distinct_mark():
    _, abutment, state, profile = fixture()
    state['supplements']['back']['mark'] = state['supplements']['front']['mark']
    result = calculate(profile,state,abutment)
    assert not result['valid']
    assert any('duplicada' in issue['message'] for issue in result['issues'])
