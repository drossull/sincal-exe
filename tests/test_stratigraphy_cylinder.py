import copy
import math

import pytest

from sincal.cad.stratigraphy import build_stratigraphy_lisp, output_mode_value, stratigraphy_scene
from sincal.cad.stratigraphy_cylinder import cylinder_scene, published_uscs
from sincal.stratigraphy import VsBand
from test_stratigraphy import report
from test_stratigraphy_cdi_scene import fixture_hole
from test_stratigraphy_octay import PAGES
from sincal.stratigraphy_octay import parse_individual_report


@pytest.mark.parametrize('factory', [lambda: report().boreholes[0],
                                   lambda: parse_individual_report(PAGES).boreholes[0], fixture_hole])
def test_mode_is_additive_leaves_full_output_and_source_unchanged(factory):
    hole = factory()
    before = copy.deepcopy(hole)
    assert stratigraphy_scene(hole, True) == stratigraphy_scene(hole, True, output_mode='full')
    a = stratigraphy_scene(hole, False, output_mode='isometric-cylinder')
    b = stratigraphy_scene(hole, True, output_mode='isometric-cylinder')
    assert a == b  # Documentary table checkbox never adds other content to the cylinder.
    assert a['format'] == hole.drawing_format
    assert a['output_mode'] == 'isometric-cylinder'
    assert all(i['color'] in (1, 3, 8) for i in a['items'])
    assert not any(i['kind'] in ('circle', 'triangle') for i in a['items'])
    assert hole == before


@pytest.mark.parametrize('scale', [5, 10, 20])
def test_true_depths_curve_extents_and_closed_native_boundaries(scale):
    hole = fixture_hole()
    hole.vs_bands = [VsBand('0', '30', '600', '700', 9, 'Arreglo', 8)]
    scene = stratigraphy_scene(hole, annotation_scale=scale, output_mode='isometric-cylinder')
    assert scene['depth'] == 5  # Not drilling's 6 m, and not the independent Vs depth.
    assert scene['depth_scale'] == scale
    hatches = [i for i in scene['items'] if i['kind'] == 'hatch']
    bands = [i for i in hatches if len(i['boundary']) == 4]
    assert len(bands) == 2
    for band, row in zip(bands, hole.horizons):
        upper, right, lower, left = band['boundary']
        assert upper['start'] == math.pi and upper['end'] == 0
        assert lower['start'] == 0 and lower['end'] == math.pi
        assert (upper['point'][1]-scene['depth_origin'])/scale == pytest.approx(float(row.start))
        assert (lower['point'][1]-scene['depth_origin'])/scale == pytest.approx(float(row.end))
        assert band['bounds'][3] == lower['point'][1]+lower['ry']
        assert band['bounds'][2]-band['bounds'][0] == 14

        def endpoints(item):
            if item['kind'] == 'line':
                return item['points']
            return [[item['point'][0]+item['rx']*math.cos(t),
                     item['point'][1]+item['ry']*math.sin(t)] for t in (item['start'], item['end'])]

        for current, following in zip(band['boundary'], band['boundary'][1:]+band['boundary'][:1]):
            assert endpoints(current)[1] == pytest.approx(endpoints(following)[0])
    assert all(i['height'] == 2.5 for i in scene['items'] if i['kind'] == 'text')
    assert max(i['bounds'][3] for i in hatches) < scene['viewbox'][3]


def test_gap_and_zero_length_records_are_never_filled_or_extrapolated():
    hole = fixture_hole()
    hole.horizons[1].start = '3'
    # Direct scene check: the public entry point still rejects discontinuous data.
    scene = cylinder_scene(hole, 5)
    bands = [i for i in scene['items'] if i['kind'] == 'hatch' and len(i['boundary']) == 4]
    assert [i['boundary'][0]['point'][1] for i in bands] == [14, 29]
    assert [i['boundary'][2]['point'][1] for i in bands] == [24, 39]
    assert len([i for i in scene['items'] if i['kind'] == 'hatch' and len(i['boundary']) == 1]) == 2
    with pytest.raises(ValueError):
        stratigraphy_scene(hole, output_mode='isometric-cylinder')
    legacy = report().boreholes[0]  # Includes one refused zero-length drilling row.
    scene = stratigraphy_scene(legacy, output_mode='isometric-cylinder')
    assert len([i for i in scene['items'] if i['kind'] == 'hatch' and len(i['boundary']) == 4]) == 5


@pytest.mark.parametrize('description,expected', [
    ('Grava, clasificación USCS: GP', 'GP'),
    ('Arena. USCS: SP - SM.', 'SP-SM'),
    ('Arena. SUCS: (SW)', 'SW'),
    ('GP, grava según descripción del operador', ''),
    ('Clasificación USCS: GP o GM', ''),
    ('USCS: GP/GC', ''),
    ('USCS: GP posible', ''),
    ('USCS: no determinada', ''),
    ('USCS: GP. USCS: GM.', ''),
])
def test_only_unambiguous_explicit_classification_is_labelled(description, expected):
    assert published_uscs(description) == expected


def test_labels_do_not_include_other_panels_or_company_and_do_not_overlap():
    hole = fixture_hole()
    hole.horizons[0].description = 'Arena. USCS: SP'
    hole.horizons[1].description = 'Grava. USCS: GP-GM'
    scene = stratigraphy_scene(hole, annotation_scale=.1, output_mode='isometric-cylinder')
    labels = [i for i in scene['items'] if i['kind'] == 'text']
    texts = '\n'.join(i['text'] for i in labels)
    assert 'SP' in texts and 'GP-GM' in texts
    assert not any(s in texts for s in ('NSPT', 'RECUPER', 'EMPRESA', 'NO COMPANY', 'VS =', 'PÁG.'))
    for anchor in ('left', 'right'):
        selected = [i for i in labels if i['anchor'] == anchor]
        assert all(b['point'][1]-a['point'][1] >= 4 for a, b in zip(selected, selected[1:]))


@pytest.mark.parametrize('value', [None, True, False, 0, {}, [], 'FULL', 'isometric', ''])
def test_invalid_mode_is_not_coerced_to_default(value):
    with pytest.raises(ValueError):
        output_mode_value(value)
    with pytest.raises(ValueError):
        stratigraphy_scene(fixture_hole(), output_mode=value)


def test_lisp_uses_exact_ellipses_and_shared_hatch_cleanup_and_guards():
    hole = fixture_hole()
    hole.reviewed = True
    hole.reviewed_format = hole.drawing_format
    source = build_stratigraphy_lisp(hole, 'master.dwg', True, 5, '1:200 (m)',
                                   output_mode='isometric-cylinder')
    assert 'vla-AddEllipse' in source and 'vla-put-StartParameter' in source
    assert 'vla-put-EndParameter' in source
    assert '(se:hatch nil nil "AR-SAND" (list' in source
    assert '(foreach boundary boundaries (vla-Delete boundary)' in source
    assert '(vla-AppendOuterLoop hatch objects)' in source
    assert 'vla-CopyObjects' in source and 'RomanD' in source
    assert "(member (type setpropertyvalue) '(SUBR USUBR EXRXSUBR))" in source
    assert "(if has-property (setq result (vl-catch-all-apply 'setpropertyvalue" in source
    assert '(if (or (not has-property) (vl-catch-all-error-p result))' in source
    assert '(vl-cmdf "_.ANNOUPDATE" ent "")' in source
    assert '(regapp "AcadAnnotative")' in source
    assert source.count('      (se:scale)') == 2
    assert '(getvar "CANNOSCALEVALUE") 5 ' in source
    assert '(* k 2.5)' in source and 'vla-EndUndoMark' in source
    assert not any(s in source for s in ('NO COMPANY IN CAD', 'secret@example.test', 'QSAVE', 'NSPT'))
