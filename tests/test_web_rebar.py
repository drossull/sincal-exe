import pytest
from sincal.web.rebar import defaults, domain, preview
from sincal.web.server import Store


def test_geometry_matches_partial_and_total():
    result = preview(defaults())
    assert result['valid']
    assert len(result['marks']) == 6
    for piece in result['details']:
        assert sum(piece['partials_cm']) == piece['total_cm']
        assert piece['measured_cm'] == pytest.approx(piece['developed_length_cm'])
        assert -1e-8 <= piece['total_cm'] - piece['measured_cm'] < 1
    assert result['marks'][0]['bend_radius_cm'] == 6.6


def test_hook_edit_is_not_stale():
    state = defaults()
    before = preview(state)
    state['rules'][0]['hook_cm'] = 110
    after = preview(state)
    assert before['details'][0]['partials_cm'] != after['details'][0]['partials_cm']
    assert 110 in after['details'][0]['partials_cm']


def test_detail_api_exposes_real_bends_and_partial_variable_ranges():
    state = defaults()
    state['geometry']['esviaje_grados'] = -12
    result = preview(state)
    pieces = {piece['mark']: piece for piece in result['details']}
    assert pieces['1']['bends'][0]['bend_degrees'] == 90
    assert not pieces['1']['bends'][0]['skewed']
    assert pieces['4']['bends'][0]['interior_degrees'] == 102
    assert pieces['4']['bends'][0]['skewed']
    assert pieces['5']['bends'][0]['bend_degrees'] == 102
    assert pieces['3']['partial_ranges_cm'] == [
        {'min_cm': 100, 'max_cm': 100},
        {'min_cm': 21, 'max_cm': 743},
        {'min_cm': 100, 'max_cm': 100},
    ]
    assert all(bend['bend_degrees'] == 90 and not bend['skewed']
               for bend in pieces['3']['bends'])
    # Annotations leave the existing totals, piece geometry and quantities intact.
    for piece in result['details']:
        assert sum(item['max_cm'] for item in piece['partial_ranges_cm']) == piece['total_cm']
        assert piece['measured_cm'] == pytest.approx(piece['developed_length_cm'])
        assert -1e-8 <= piece['total_cm'] - piece['measured_cm'] < 1


@pytest.mark.parametrize('value', [None, float('nan'), float('inf'), 0, -1, True])
def test_spacing_guard(value):
    state = defaults()
    state['rules'][0]['spacing_cm'] = value
    with pytest.raises(ValueError):
        preview(state)


def test_invalid_geometry_has_no_detail():
    state = defaults()
    state['cover']['inferior_cm'] = 200
    result = preview(state)
    assert not result['valid']
    assert result['details'] == []


def test_two_abutments_roundtrip(tmp_path):
    state = {'data': {}, 'identification': {'ot':'Test', 'revision':'A', 'structure_name':'Demo'},
             'rebar': {'entrada':defaults(), 'salida':defaults()}}
    state['rebar']['salida']['geometry']['alto_cm'] = 200
    store = Store(tmp_path / 'sessions.db')
    saved = store.save(state)
    restored = store.get(saved['id'])
    assert restored == state
    assert restored['rebar']['entrada']['geometry']['alto_cm'] == 150


def test_saved_legacy_marks_migrate_at_input_boundary():
    state = defaults()
    state['rules'][2].update(mark='3-a', enabled=True)
    state['rules'][0]['terminal_mark'] = '2-A'
    state['rules'][3]['terminal_mark'] = '5-A'
    _, _, rules = domain(state)
    assert rules[2].mark == '3a'
    assert rules[0].terminal_mark == '2A'
    assert rules[3].terminal_mark == '5A'
    result = preview(state)
    assert result['valid']
    assert '3a' in {mark['mark'] for mark in result['marks']}
    assert state['rules'][2]['mark'] == '3-a'  # Input is not mutated.


@pytest.mark.parametrize('mark', ['3-A2', '3--A', '3 A', '3\") (quit)', '3İ'])
def test_legacy_migration_does_not_sanitize_invalid_marks(mark):
    state = defaults()
    state['rules'][0]['mark'] = mark
    result = preview(state)
    assert not result['valid']
    assert not result['details']


def test_legacy_migration_detects_collisions_before_cad():
    state = defaults()
    state['rules'][1]['mark'] = '3a'
    state['rules'][2].update(mark='3-A', enabled=True)
    result = preview(state)
    assert not result['valid']
    assert any('Marca duplicada' in issue['message'] for issue in result['issues'])
    assert not result['details']
