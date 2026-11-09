from copy import deepcopy

import pytest

from sincal.web.server import Store
from sincal.web.wing_exterior import from_project, normalize_draft, preview, validate_draft
from test_web_wing_exterior import configured


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('instance', ['entrada', 'salida'])
def test_profile_preserves_footing_reference_and_current_dimensions(side, instance):
    project, abutment, state = configured(side, instance, extension=True)
    view = from_project(project, instance, side, abutment)['range_preview']
    assert view['reference'] == 'footing_top' and view['extension_enabled']
    geometry = state['geometry']
    assert [geometry['main_length_cm'], 0.] in view['profile_cm']
    state['geometry']['top_tip_cm'] += 10
    changed = preview(project, instance, side, state, abutment)['range_preview']
    assert [geometry['main_length_cm']+geometry['extension_length_cm'],
            geometry['top_tip_cm']] in changed['profile_cm']


def test_old_free_ranges_are_retained_but_not_applied_to_new_groups():
    project, abutment, state = configured()
    old = {name: dict(enabled=True, start_cm=80., end_cm=160., diameter_mm=16, spacing_cm=20.)
           for name in ('axilla', 'upper')}
    state['supplements'] = deepcopy(old)
    before = deepcopy(state)
    validate_draft(state)
    converted = from_project(project, 'entrada', 'left', abutment)['normalized_state']
    assert state == before
    assert converted['supplements_legacy'] == old
    assert converted['supplements']['front']['range_height_cm'] is None
    assert converted['supplements']['front']['enabled'] is True
    assert converted['supplements']['back']['diameter_mm'] == 16
    assert converted['edge_rebar']['total_cm'] is None
    assert converted['edge_rebar']['min_extension_cm'] == 100
    assert normalize_draft(converted, add_controls=True) == converted


def test_legacy_mesh_only_preview_is_unchanged():
    project, abutment, state = configured()
    baseline = preview(project, 'entrada', 'left', state, abutment)
    del state['supplements']
    validate_draft(state)
    assert preview(project, 'entrada', 'left', state, abutment) == baseline


def test_new_group_and_edge_parameters_roundtrip_without_mutating_project(tmp_path):
    project, abutment, state = configured(extension=True)
    original = deepcopy(project)
    state.update(normalize_draft(state, add_controls=True))
    state['supplements']['front'].update(enabled=True, range_height_cm=250., diameter_mm=16,
                                         spacing_cm=20., hook_cm=40., straight_cm=180., mark='31')
    state['edge_rebar'].update(quantity=3, diameter_mm=16, total_cm=600., mark='33')
    payload = {'data': project, 'identification': {'ot': 'G-TEST', 'revision': 'A',
               'structure_name': 'Refuerzos de ala'}, 'rebar': {'entrada': abutment}}
    store = Store(tmp_path/'wing-supplements.db')
    saved = store.get(store.save(payload)['id'])
    assert saved['rebar']['entrada']['wings']['left'] == state
    assert saved['data'] == project == original


@pytest.mark.parametrize('bad', [True, float('inf'), float('nan'), '20'])
def test_values_require_finite_numbers(bad):
    _, _, state = configured()
    state['supplements']['front']['spacing_cm'] = bad
    with pytest.raises(ValueError):
        validate_draft(state)


@pytest.mark.parametrize('bad', [None, {}, {'front': {}}, {'axilla': True, 'upper': None}])
def test_malformed_groups_are_not_saved(bad):
    _, _, state = configured()
    state['supplements'] = bad
    with pytest.raises(ValueError):
        validate_draft(state)


def test_fractional_edge_quantity_is_rejected_before_save():
    _, _, state = configured()
    state = normalize_draft(state, add_controls=True)
    state['edge_rebar']['quantity'] = 3.5
    with pytest.raises(ValueError, match='entera'):
        validate_draft(state)
