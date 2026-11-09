from copy import deepcopy

import pytest

from sincal.web.abutment_scene import build_scene
from sincal.web.rebar import from_project as footing_states, validate_draft as validate_abutment
from sincal.web.wing_exterior import from_project, preview, validate_draft
from test_web_abutment_scene import example


def configured(side='left', instance='entrada', extension=False):
    project = example()
    project['estribos'][f'espesor_muro_ala_{instance}'] = 1000
    if extension:
        project['estribos'].update({f'incluir_aletas_estribo_{instance}': True,
                                   f'largo_aleta_{instance}': 2000,
                                   f'alto_minimo_aleta_{instance}': 1000,
                                   f'alto_maximo_aleta_{instance}': 4000})
    abutment = footing_states(project)[instance]
    state = from_project(project, instance, side, abutment)['state']
    # Legacy mesh-only fixture; edge/supplement integration has its own tests.
    state.pop('edge_rebar', None)
    state['geometry_confirmed'] = True
    state['cover'] = dict.fromkeys(state['cover'], 5.)
    state['vertical'].update(diameter_mm=16, spacing_cm=20, mark_main='11', mark_extension='12')
    state['horizontal'].update(diameter_mm=12, spacing_cm=20, hook_join_cm=40,
                               mark_main='13', mark_upper='14')
    state.update(outer_family='vertical', horizontal_start='wall')
    abutment['wings'] = {side: state}
    return project, abutment, state


def test_import_keeps_unknown_steel_empty_and_does_not_modify_project():
    project = example(); before = deepcopy(project)
    state = from_project(project, 'entrada', 'left')['state']
    assert project == before
    assert set(state['cover'].values()) == {None}
    assert state['vertical']['diameter_mm'] is None
    assert state['horizontal']['hook_join_cm'] == 40
    assert state['vertical']['hook_bottom_cm'] == state['vertical']['hook_top_cm'] == 40
    assert state['horizontal']['hook_ala_cm'] == 40
    assert state['interior']['horizontal']['hook_join_cm'] == 40
    assert [group['hook_cm'] for group in state['supplements'].values()] == [40, 40]
    assert state['geometry_confirmed'] is False


def test_unfinished_draft_can_be_saved_but_has_no_steel():
    project = example(); abutment = footing_states(project)['entrada']
    state = from_project(project, 'entrada', 'left', abutment)['state']
    state['horizontal']['hook_join_cm'] = None
    state['interior']['horizontal']['hook_join_cm'] = 0
    state['supplements']['front']['hook_cm'] = 55
    state['supplements']['back']['hook_cm'] = None
    abutment['wings'] = {'left': state}
    validate_abutment(abutment)
    normalized = from_project(project, 'entrada', 'left', abutment)['normalized_state']
    assert normalized == state
    result = preview(project, 'entrada', 'left', state, abutment)
    assert not result['valid'] and not result['bars']


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('instance', ['entrada', 'salida'])
def test_actual_preview_scene_and_detail_share_quantities_and_geometry(side, instance):
    project, abutment, state = configured(side, instance)
    before = deepcopy((project, abutment))
    result = preview(project, instance, side, state, abutment)
    assert result['valid'], result['issues']
    assert sum(mark['quantity'] for mark in result['marks']) == len(result['bars'])
    assert sum(mark['total_length_cm'] for mark in result['marks']) == sum(bar['length_cm'] for bar in result['bars'])
    scene = build_scene(project, instance, abutment, use_state_geometry=True)
    assert [bar for bar in scene['bars'] if bar['element_key'] == f'abutment.{side}_wing'] == result['bars']
    assert (project, abutment) == before
    for detail in result['details']:
        assert detail['quantity'] == next(mark['quantity'] for mark in result['marks'] if mark['mark'] == detail['mark'])
        assert detail['developed_length_cm'] == pytest.approx(detail['measured_cm'])


def test_verticals_enter_footing_and_horizontal_groups_end_in_different_walls():
    project, abutment, state = configured()
    result = preview(project, 'entrada', 'left', state, abutment)
    assert result['valid'], result['issues']
    verticals = [bar for bar in result['bars'] if bar['key'].endswith('vertical_main')]
    assert min(p[2] for bar in verticals for p in bar['points']) == pytest.approx(.075+.016/2)
    assert {mark['mark'] for mark in result['marks']} == {'11', '13', '14'}
    assert all(bar['length_cm'] <= 1200 for bar in result['bars'])
    assert all(bar['bend_radius_cm'] == pytest.approx(3*bar['diameter_mm']/10) for bar in result['bars'])


def test_one_deleted_wing_piece_updates_only_its_quantity_and_restores():
    project, abutment, state = configured()
    initial = preview(project, 'entrada', 'left', state, abutment)
    selected = initial['bars'][3]
    state['removed_pieces'].append({key: selected[key] for key in ('id', 'signature')})
    validate_abutment(abutment)
    reduced = preview(project, 'entrada', 'left', state, abutment)
    assert reduced['valid'], reduced['issues']
    assert {bar['id'] for bar in reduced['bars']} == {bar['id'] for bar in initial['bars']} - {selected['id']}
    assert sum(mark['total_length_cm'] for mark in initial['marks']) - sum(mark['total_length_cm'] for mark in reduced['marks']) == selected['length_cm']
    state['vertical']['spacing_cm'] = 23
    stale = preview(project, 'entrada', 'left', state, abutment)
    assert not stale['valid'] and not stale['bars']
    state['removed_pieces'] = []
    state['vertical']['spacing_cm'] = 20
    assert preview(project, 'entrada', 'left', state, abutment)['bars'] == initial['bars']


def test_reused_footing_mark_is_rejected_before_cad():
    project, abutment, state = configured()
    state['vertical']['mark_main'] = abutment['rules'][0]['mark']
    result = preview(project, 'entrada', 'left', state, abutment)
    assert not result['valid'] and not result['bars']
    assert any('reservadas' in issue['message'] for issue in result['issues'])


def test_geometry_must_be_reviewed_and_overlong_hooks_are_not_shortened():
    project, abutment, state = configured()
    state['geometry_confirmed'] = False
    assert not preview(project, 'entrada', 'left', state, abutment)['valid']
    state['geometry_confirmed'] = True
    state['horizontal']['hook_ala_cm'] = 120
    result = preview(project, 'entrada', 'left', state, abutment)
    assert not result['valid'] and not result['bars']
    assert state['horizontal']['hook_ala_cm'] == 120
    assert any('no cabe' in issue['message'] for issue in result['issues'])


@pytest.mark.parametrize('bad', [True, float('nan'), float('inf'), '5'])
def test_malformed_engineering_values_are_not_saved(bad):
    _, _, state = configured()
    state['cover']['outside_cm'] = bad
    with pytest.raises(ValueError):
        validate_draft(state)
