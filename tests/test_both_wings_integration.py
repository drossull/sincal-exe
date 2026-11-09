"""Both wings retain independent steel, marks and edits in one abutment."""
from copy import deepcopy

import pytest

from sincal.web.abutment_scene import build_scene
from sincal.web.server import Store
from sincal.web.wing_exterior import from_project, preview
from test_web_wing_refinements import configured_all_families
from test_wing_exterior_integration import assert_counts
from test_wing_mesh_geometry import configured


def both_wings(instance):
    project, abutment, _, _ = configured(instance=instance)
    _, _, template = configured_all_families()
    abutment['wings'] = {}
    for side, offset in (('left', 0), ('right', 100)):
        state = deepcopy(template)
        state['geometry'] = from_project(project, instance, side, abutment)['state']['geometry']
        for mesh in (state, state['interior']):
            for group in ('vertical', 'horizontal'):
                for field, value in mesh[group].items():
                    if field.startswith('mark_') and value:
                        mesh[group][field] = str(int(value)+offset)
        for owner in (state['edge_rebar'], *state['supplements'].values()):
            owner['mark'] = str(int(owner['mark'])+offset)
        abutment['wings'][side] = state
    return project, abutment


def results(project, instance, abutment):
    calculated = {side: preview(project, instance, side, state, abutment)
                  for side, state in abutment['wings'].items()}
    for result in calculated.values():
        assert result['valid'], result['issues']
        assert_counts(result)
    return calculated


def assert_scene(project, instance, abutment, calculated):
    scene = build_scene(project, instance, abutment, use_state_geometry=True)
    for side, result in calculated.items():
        element = f'abutment.{side}_wing'
        assert [bar for bar in scene['bars'] if bar['element_key'] == element] == result['bars']
        assert [bar for bar in scene.get('removed_bars', [])
                if bar['id'].startswith(f'wing:{side}:')] == result['removed_bars']


@pytest.mark.parametrize('instance', ('entrada', 'salida'))
def test_both_complete_wings_share_scene_without_merging_marks_or_geometry(instance):
    project, abutment = both_wings(instance)
    original = deepcopy((project, abutment))
    calculated = results(project, instance, abutment)
    left, right = calculated['left'], calculated['right']
    assert {bar['id'] for bar in left['bars']}.isdisjoint(bar['id'] for bar in right['bars'])
    assert {mark['mark'] for mark in left['marks']}.isdisjoint(mark['mark'] for mark in right['marks'])
    groups = {'vertical_main', 'vertical_extension', 'horizontal_main', 'horizontal_upper',
              'inner_vertical_main', 'inner_vertical_extension', 'inner_horizontal_main',
              'inner_horizontal_upper', 'inner_supplement_front', 'inner_supplement_back', 'edge'}
    for side, result in calculated.items():
        assert {bar['key'].removeprefix(f'wing_{side}_') for bar in result['bars']} == groups
        assert all(mark['views'] == (('BB', 'DD', 'EE') if side == 'left' else ('CC', 'DD', 'EE'))
                   for mark in result['marks'])
    assert_scene(project, instance, abutment, calculated)
    assert (project, abutment) == original


@pytest.mark.parametrize('instance', ('entrada', 'salida'))
@pytest.mark.parametrize('group,owner_path', (
    ('vertical_main', ()),
    ('inner_vertical_main', ('interior',)),
    ('inner_supplement_front', ('supplements', 'front')),
    ('inner_supplement_back', ('supplements', 'back')),
    ('edge', ('edge_rebar',)),
))
def test_right_piece_removal_persists_and_restores_without_changing_left(
        tmp_path, instance, group, owner_path):
    project, abutment = both_wings(instance)
    original_json = deepcopy(project)
    original_left = deepcopy(abutment['wings']['left'])
    initial = results(project, instance, abutment)
    selected = next(bar for bar in initial['right']['bars'] if bar['key'] == f'wing_right_{group}')
    owner = abutment['wings']['right']
    for key in owner_path:
        owner = owner[key]
    owner['removed_pieces'] = [{key: selected[key] for key in ('id', 'signature')}]
    reduced = results(project, instance, abutment)
    assert reduced['left'] == initial['left']
    assert reduced['right']['bars'] == [bar for bar in initial['right']['bars'] if bar['id'] != selected['id']]
    assert reduced['right']['total_kg'] < initial['right']['total_kg']
    assert [mark for mark in reduced['right']['marks'] if mark['mark'] != selected['mark']] == [
        mark for mark in initial['right']['marks'] if mark['mark'] != selected['mark']]
    assert_scene(project, instance, abutment, reduced)

    payload = {'data': project, 'identification': {
        'ot': 'G-TEST', 'revision': 'A', 'structure_name': 'Ambas alas'},
        'rebar': {instance: abutment}}
    store = Store(tmp_path/'both-wings.db')
    saved = store.get(store.save(payload)['id'])
    restored = saved['rebar'][instance]
    assert restored['wings']['left'] == original_left
    assert results(saved['data'], instance, restored) == reduced
    assert_scene(saved['data'], instance, restored, reduced)

    owner = restored['wings']['right']
    for key in owner_path:
        owner = owner[key]
    owner['removed_pieces'].clear()
    assert results(saved['data'], instance, restored) == initial
    assert_scene(saved['data'], instance, restored, initial)
    assert saved['data'] == project == original_json
