import pytest
from sincal.web.rebar import defaults, preview
from sincal.web.server import Store


def test_geometry_matches_partial_and_total():
    result = preview(defaults())
    assert result['valid']
    assert len(result['marks']) == 6
    for piece in result['details']:
        assert sum(piece['partials_cm']) == piece['total_cm']
        assert piece['measured_cm'] == pytest.approx(piece['total_cm'])
    assert result['marks'][0]['bend_radius_cm'] == 6.6


def test_hook_edit_is_not_stale():
    state = defaults()
    before = preview(state)
    state['rules'][0]['hook_cm'] = 110
    after = preview(state)
    assert before['details'][0]['partials_cm'] != after['details'][0]['partials_cm']
    assert 110 in after['details'][0]['partials_cm']


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
