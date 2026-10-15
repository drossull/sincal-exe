import copy

import pytest

from sincal.cad.stratigraphy import stratigraphy_scene, build_stratigraphy_lisp
from sincal.stratigraphy import VsBand
from sincal.prospecciones import number
from sincal.stratigraphy_octay import parse_individual_report
from test_stratigraphy import report
from test_stratigraphy_octay import PAGES


@pytest.mark.parametrize('scale', [20, 10, 5, 2, 3.14159])
@pytest.mark.parametrize('octay', [False, True])
def test_real_depths_and_paper_symbols_at_every_annotation_scale(scale, octay):
    hole = parse_individual_report(PAGES).boreholes[0] if octay else report().boreholes[0]
    hole.vs_bands = [VsBand('0','30','608','676',19,'Arreglo',117)]
    original = copy.deepcopy(hole)
    scene = stratigraphy_scene(hole, True, scale)
    assert scene['depth_scale'] == scale and scene['depth'] == 30
    strata = [i for i in scene['items'] if i['kind']=='hatch' and i['bounds'][0]==12]
    rows = [(r,n) for r in hole.strata if number(r.end)>number(r.start) for n in [r.material,*r.inclusions]]
    for item,(row,_) in zip(strata,rows):
        assert (item['bounds'][1]-scene['depth_origin'])/scale == pytest.approx(number(row.start))
        assert (item['bounds'][3]-scene['depth_origin'])/scale == pytest.approx(number(row.end))
        assert item['bounds'][2]-item['bounds'][0] == 14  # paper width is fixed
    assert all(i['height']==2.5 for i in scene['items'] if i['kind']=='text')
    # Vs still reaches 30 m even when the borehole itself is shallower.
    tips = [i['points'][0][1] for i in scene['items'] if i['kind']=='triangle']
    assert (max(tips)-min(tips))/scale == pytest.approx(30)
    if octay:
        bar = next(i for i in scene['items'] if i.get('series')=='nspt')
        assert (bar['points'][1][1]-bar['points'][0][1])/scale == pytest.approx(.45)
        labels = [i for i in scene['items'] if 'sample' in i]
        for a,b in zip(labels,labels[1:]):
            assert a['point'][1]+2*len(a['text'].splitlines()) < b['point'][1]-2*len(b['text'].splitlines())
    assert hole == original


@pytest.mark.parametrize('value', [None, 0, -1, float('nan'), float('inf'), True, 'invalid'])
def test_invalid_scale_is_not_silently_replaced(value):
    hole = report().boreholes[0]
    hole.reviewed = True
    with pytest.raises(ValueError, match='escala'):
        build_stratigraphy_lisp(hole, 'master.dwg', annotation_scale=value)


def test_runtime_checks_scale_before_and_after_point_without_changing_it():
    hole = report().boreholes[0]
    hole.reviewed = True
    source = build_stratigraphy_lisp(hole, 'master.dwg', annotation_scale=5, scale_name='CUSTOM metres')
    assert source.count('      (se:scale)') == 2
    assert source.index('(se:scale)') < source.index('(setq db (se:dbx))')
    assert source.index('(se:scale)', source.index('(setq base (getpoint')) < source.index('(vla-StartUndoMark doc)')
    assert '(getvar "CANNOSCALEVALUE") 5 ' in source
    assert '"CUSTOM metres"' in source
    assert '(setvar "CANNOSCALE' not in source
    assert '"_Add" scale-name' in source
