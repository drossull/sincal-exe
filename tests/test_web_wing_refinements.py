from copy import deepcopy

import pytest

from sincal.web.abutment_scene import build_scene
from sincal.web.server import Store
from sincal.web.wing_exterior import preview, validate_draft
from test_wing_mesh_geometry import configured
from test_wing_exterior_integration import assert_counts


def configured_edge():
    project, abutment, state, _ = configured()
    state['edge_rebar'] = {'quantity': 3, 'diameter_mm': 16, 'top_hook_enabled': True,
                           'top_hook_cm': 20., 'total_cm': 650., 'min_extension_cm': 100.,
                           'mark': '51', 'removed_pieces': []}
    abutment['wings'] = {'left': state}
    return project, abutment, state


def test_canto_shares_scene_counts_and_exact_total_without_rounding():
    project, abutment, state = configured_edge()
    original = deepcopy((project, abutment))
    result = preview(project, 'entrada', 'left', state, abutment)
    assert result['valid'], result['issues']
    edge = [bar for bar in result['bars'] if bar['key'].endswith('_edge')]
    assert len(edge) == 3
    assert all(bar['developed_length_cm'] == pytest.approx(650.) for bar in edge)
    assert all(item['extension_cm'] >= 100 for item in result['edge_extensions_cm'])
    mark = next(item for item in result['marks'] if item['mark'] == '51')
    assert mark['quantity'] == 3 and mark['total_length_cm'] == 1950
    detail = next(item for item in result['details'] if item['mark'] == '51')
    assert not detail['length_variants']
    assert sum(item['min_cm'] != item['max_cm'] for item in detail['partial_ranges_cm']) >= 2
    scene = build_scene(project, 'entrada', abutment, use_state_geometry=True)
    assert [bar for bar in scene['bars'] if bar['element_key'] == 'abutment.left_wing'] == result['bars']
    assert (project, abutment) == original


def test_one_canto_removal_updates_only_its_mark_and_persists(tmp_path):
    project, abutment, state = configured_edge()
    initial = preview(project, 'entrada', 'left', state, abutment)
    selected = next(bar for bar in initial['bars'] if bar['key'].endswith('_edge'))
    state['edge_rebar']['removed_pieces'] = [{key: selected[key] for key in ('id', 'signature')}]
    validate_draft(state)
    reduced = preview(project, 'entrada', 'left', state, abutment)
    assert reduced['valid'], reduced['issues']
    assert len(reduced['bars']) == len(initial['bars'])-1
    assert len(reduced['edge_extensions_cm']) == 2
    assert [m for m in reduced['marks'] if m['mark'] != '51'] == [m for m in initial['marks'] if m['mark'] != '51']
    payload = {'data': project, 'identification': {'ot': 'G-TEST', 'revision': 'A', 'structure_name': 'Canto'},
               'rebar': {'entrada': abutment}}
    store = Store(tmp_path/'edge.db')
    saved = store.get(store.save(payload)['id'])
    restored = saved['rebar']['entrada']
    assert preview(saved['data'], 'entrada', 'left', restored['wings']['left'], restored) == reduced


@pytest.mark.parametrize('blocked', ['mark', 'geometry'])
def test_global_invalidity_does_not_leave_edge_extensions_visible(blocked):
    project, abutment, state = configured_edge()
    if blocked == 'mark':
        state['edge_rebar']['mark'] = state['vertical']['mark_main']
    else:
        state['geometry_confirmed'] = False
    result = preview(project, 'entrada', 'left', state, abutment)
    assert not result['valid']
    assert result['bars'] == result['marks'] == result['details'] == result['edge_extensions_cm'] == []
    assert result['total_kg'] == 0


def test_insufficient_canto_total_is_not_silently_extended():
    project, abutment, state = configured_edge()
    state['edge_rebar']['total_cm'] = 600.
    result = preview(project, 'entrada', 'left', state, abutment)
    assert not result['valid']
    assert any('prolongación' in issue['message'] and issue['severity'] == 'error' for issue in result['issues'])
    assert not any(bar['key'].endswith('_edge') for bar in result['bars'])
    assert state['edge_rebar']['total_cm'] == 600.


def configured_all_families():
    project, abutment, state = configured_edge()
    state['interior'] = {'enabled': True, 'parameters_initialized': True,
                         'vertical': deepcopy(state['vertical']),
                         'horizontal': deepcopy(state['horizontal']), 'removed_pieces': []}
    state['interior']['vertical'].update(mark_main='21', mark_extension='22')
    state['interior']['horizontal'].update(mark_main='23', mark_upper='24')
    state['edge_rebar']['mark'] = '53'
    state['supplements'] = {
        'front': {'enabled': True, 'range_height_cm': 80., 'diameter_mm': 12,
                  'spacing_cm': 20., 'hook_cm': 40., 'straight_cm': 300.,
                  'mark': '51', 'removed_pieces': []},
        'back': {'enabled': True, 'diameter_mm': 12, 'spacing_cm': 20.,
                 'hook_cm': 40., 'straight_cm': 300., 'mark': '52', 'removed_pieces': []},
    }
    return project, abutment, state


def test_combined_meshes_supplements_and_canto_share_quantities_scene_and_saved_bajas(tmp_path):
    project, abutment, state = configured_all_families()
    initial = preview(project, 'entrada', 'left', state, abutment)
    assert initial['valid'], initial['issues']
    assert_counts(initial)
    assert {'51', '52', '53'} <= {mark['mark'] for mark in initial['marks']}
    selected = next(bar for bar in initial['bars'] if bar['key'].endswith('_inner_supplement_front'))
    state['supplements']['front']['removed_pieces'] = [{key: selected[key] for key in ('id', 'signature')}]
    validate_draft(state)
    reduced = preview(project, 'entrada', 'left', state, abutment)
    assert reduced['valid'], reduced['issues']
    assert_counts(reduced)
    assert len(reduced['bars']) == len(initial['bars'])-1
    assert [mark for mark in reduced['marks'] if mark['mark'] != '51'] == [
        mark for mark in initial['marks'] if mark['mark'] != '51']
    scene = build_scene(project, 'entrada', abutment, use_state_geometry=True)
    assert [bar for bar in scene['bars'] if bar['element_key'] == 'abutment.left_wing'] == reduced['bars']
    store = Store(tmp_path/'all-wing-families.db')
    payload = {'data': project, 'identification': {'ot': 'G-TEST', 'revision': 'A', 'structure_name': 'Ala'},
               'rebar': {'entrada': abutment}}
    restored = store.get(store.save(payload)['id'])
    restored_abutment = restored['rebar']['entrada']
    assert preview(restored['data'], 'entrada', 'left', restored_abutment['wings']['left'], restored_abutment) == reduced


def test_supplement_marks_remain_unique_against_edge_and_interior_mesh():
    project, abutment, state = configured_all_families()
    state['supplements']['front']['mark'] = state['edge_rebar']['mark']
    result = preview(project, 'entrada', 'left', state, abutment)
    assert not result['valid']
    assert result['bars'] == result['marks'] == result['details'] == []
    assert result['edge_extensions_cm'] == []
