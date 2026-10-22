import copy
import json

import pytest

from sincal.cad.stratigraphy_cdi import cdi_scene
from sincal.cad.stratigraphy import build_stratigraphy_lisp, stratigraphy_scene
from sincal.stratigraphy import Borehole, DrillingRecord, Horizon, Spt


def fixture_hole():
    def test(index, start, end, nspt, original):
        return Spt(index=index, start=start, end=end, nspt=nspt,
                   sample_number=original, sample_length='45', tool='Cuchara',
                   mechanism='Caída libre', n1='10', n2='20', n3='30',
                   driven='', recovered='', recovered_unit='cm', page=5)

    def drilling(start, end, recovery):
        return DrillingRecord(start=start, end=end, drilled='1,50', recovered='1,20',
                              recovery=recovery, pressure='150', page=4)

    return Borehole(key='S-2-test', name='S-2',
                           horizons=[Horizon(1, '0', '2', '', 'Arena fina', 2, 'arena'),
                                     Horizon(2, '2', '5', '', 'Grava con arena', 2, 'grava')],
                           drilling_records=[drilling('0', '1.5', '80'),
                                             drilling('1.5', '3', '60'),
                                             drilling('4', '6', '50')],
                           tests=[test(1, '1', '1.45', '50', '7'),
                                  test(2, '2.5', '2.5', 'R', '9'),
                                  test(3, '4', '4.45', '110', '9')],
                           study_info={'company': 'NO COMPANY IN CAD', 'email': 'secret@example.test'})


def test_cdi_independent_spt_intervals_and_refusal_outside_grid():
    hole = fixture_hole()
    scene = cdi_scene(hole)
    assert scene['format'] == 'cdi-spt-v1'
    assert scene['nspt_max'] == 110
    bars = [i for i in scene['items'] if i.get('series') == 'nspt']
    assert len(bars) == 2 and [i['test'] for i in bars] == [1, 3]
    assert all(i['color'] == 5 for i in bars)
    assert bars[0]['points'] == [[42 + 80 * 50 / 110, 37], [42 + 80 * 50 / 110, 41.5]]
    assert bars[1]['points'] == [[122, 67], [122, 71.5]]
    markers = [i for i in scene['items'] if i.get('series') == 'nspt-marker']
    assert len(markers) == 4 and all(i['color'] == 1 for i in markers)
    refusals = [i for i in scene['items'] if i.get('series') == 'refusal']
    assert len(refusals) == 1 and refusals[0]['points'] == [[128, 52], [130, 52]]
    assert refusals[0]['color'] == 1
    assert not any(i.get('test') == 2 for i in bars + markers)


def test_cdi_recovery_does_not_bridge_gap_or_extend_horizons():
    scene = cdi_scene(fixture_hole())
    recovery = [i for i in scene['items'] if i.get('series') == 'recovery']
    assert len(recovery) == 4  # Three measured intervals, one contiguous step.
    horizontal = [i for i in recovery if i['points'][0][1] == i['points'][1][1]]
    assert len(horizontal) == 1 and horizontal[0]['points'][0][1] == 42
    assert scene['depth'] == 6
    hatches = [i for i in scene['items'] if i['kind'] == 'hatch' and 'horizon' in i]
    assert max(i['bounds'][3] for i in hatches) == 77  # Soil stops at 5 m, not 6 m.
    assert all(i['color'] == 1 for i in scene['items'] if i.get('series') == 'strata')
    assert all(i['color'] == 8 for i in scene['items'] if i['kind'] == 'hatch')


@pytest.mark.parametrize('scale', [5, 20])
def test_cdi_real_depths_and_paper_text_height(scale):
    scene = cdi_scene(fixture_hole(), annotation_scale=scale)
    assert scene['depth_scale'] == scene['annotation_scale'] == scale
    assert scene['depth_origin'] == 27
    bars = [i for i in scene['items'] if i.get('series') == 'nspt']
    assert (bars[0]['points'][1][1] - bars[0]['points'][0][1]) / scale == pytest.approx(.45)
    labels = [i for i in scene['items'] if i['kind'] == 'text']
    assert all(i['height'] == 2.5 and i['color'] == 3 for i in labels)


def test_cdi_documentary_tables_no_company_or_false_recovered_sample():
    hole = fixture_hole()
    before = copy.deepcopy(hole)
    scene = cdi_scene(hole, include_table=True)
    labels = [i['text'] for i in scene['items'] if i['kind'] == 'text']
    assert 'LONG. cm'.upper() in labels
    assert 'PRESIÓN PSI' in labels
    assert '150' in labels and '1,20' in labels and '45' in labels
    assert labels.count('9') == 2  # Original duplicate sample labels are not renumbered.
    assert 'R' in labels and '110' in labels
    combined = json.dumps(scene)
    assert 'NO COMPANY IN CAD' not in combined and 'secret@example.test' not in combined
    assert not any('HINC.' in label or 'REC. cm' in label for label in labels)
    assert vars(hole) == vars(before)


def test_cdi_scene_dispatch_and_lisp_use_shared_geometry_without_metadata():
    hole = fixture_hole()
    assert not hole.errors()
    assert stratigraphy_scene(hole, True) == cdi_scene(hole, True)
    hole.reviewed = True
    hole.reviewed_format = hole.drawing_format
    source = build_stratigraphy_lisp(hole, 'master.dwg', True, 5, '1:200 (m)')
    assert 'RomanD' in source and '(* k 2.5)' in source
    assert 'vla-AddCircle' in source and 'vla-CopyObjects' in source
    assert 'NO COMPANY IN CAD' not in source and 'secret@example.test' not in source
    assert 'QSAVE' not in source and 'vla-Save' not in source
    assert '(getvar "CANNOSCALEVALUE") 5 ' in source


def test_cdi_long_horizon_descriptions_have_non_overlapping_labels():
    hole = fixture_hole()
    for horizon in hole.horizons:
        horizon.description = 'Arena fina con grava, color gris. ' * 20
    scene = cdi_scene(hole)
    labels = [i for i in scene['items'] if i['kind'] == 'text' and 'horizon' in i]
    for a, b in zip(labels, labels[1:]):
        assert a['point'][1] + 2 * len(a['text'].splitlines()) < b['point'][1] - 2 * len(b['text'].splitlines())
    assert max(i['point'][1] for i in labels) < scene['viewbox'][3]
