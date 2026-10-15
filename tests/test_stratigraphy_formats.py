import copy
from unittest.mock import Mock

import pytest

from sincal.stratigraphy import StratigraphyReport, read_report
from sincal.stratigraphy_octay import parse_individual_report, match_sample_descriptions
from sincal.cad.stratigraphy import stratigraphy_scene, build_stratigraphy_lisp
from sincal.web.services import Services
from test_stratigraphy_octay import PAGES
from test_stratigraphy import PAGES as VISAN


def test_format_is_detected_by_content_not_filename(tmp_path):
    for filename,pages,expected in [('Puerto Octay.txt',VISAN,'visan-summary-v1'),
                                    ('VISAN.txt',PAGES,'octay-intervals-v1')]:
        path=tmp_path/filename;path.write_text('\f'.join(pages),encoding='utf8')
        report=read_report(path)
        checks=Services.describe_stratigraphy(report)['checks'][0]
        assert checks['format']['id']==expected==checks['scene']['format']
    path.write_text('Sondaje S-07. Puerto Octay.',encoding='utf8')
    with pytest.raises(ValueError,match='No se reconocieron'): read_report(path)


def test_octay_interval_bars_separate_recovery_and_no_invented_refusal():
    report=parse_individual_report(PAGES);hole=report.boreholes[0]
    before=copy.deepcopy(report.to_dict());scene=stratigraphy_scene(hole)
    bars=[i for i in scene['items'] if i.get('series')=='nspt']
    assert len(bars)==1
    a,b=bars[0]['points']
    assert a[0]==b[0]==pytest.approx(38+80*.84)
    assert a[1]==pytest.approx(27+1.8*scene['depth_scale'])
    assert b[1]==pytest.approx(27+2.25*scene['depth_scale'])
    assert bars[0]['color']==5 and not any(i['kind']=='circle' for i in scene['items'])
    refusal=next(i for i in scene['items'] if i.get('series')=='refusal')
    assert refusal['points'][0][1]==refusal['points'][1][1]  # zero-length rejection stays zero
    assert refusal['points'][0][0]>118  # not a numeric N
    assert all(p[0]>=280 for i in scene['items'] if i.get('series')=='recovery' for p in i['points'])
    assert report.to_dict()==before
    assert all(i['height']==2.5 and i['color']==3 for i in scene['items'] if i['kind']=='text')


def cells(index,start,end,method='HQ3',values=None,description='Arena fina'):
    return [method,start,end,*(values or ['','','','']),str(index),'75','71%',description,None]


def test_descriptions_match_verified_cells_not_extraction_order():
    hole=parse_individual_report(PAGES).boreholes[0]
    row=cells(1,'0,00','1,05',description='Arena\nfina color gris')
    match_sample_descriptions(hole,3,[cells(999,'0','1'),row])
    assert hole.samples[0].description=='Arena fina color gris'
    scene=stratigraphy_scene(hole)
    assert any('ARENA FINA COLOR GRIS' in i.get('text','') for i in scene['items'])
    # Duplicate matches, changed depths or extra columns cannot silently misalign text.
    for rows in [[row,row],[cells(1,'0,00','1,06')],[row+['Otra columna']]]:
        other=parse_individual_report(PAGES).boreholes[0]
        match_sample_descriptions(other,3,rows)
        assert other.samples[0].description==''
        assert any('ambigua' in w for w in other.warnings)


def test_txt_descriptions_and_legacy_json_require_new_format_review(tmp_path):
    pages=[p.replace('1 75 71%','1 75 71% Arena fina color gris') for p in PAGES]
    report=parse_individual_report(pages);hole=report.boreholes[0]
    assert hole.samples[0].description=='Arena fina color gris'
    hole.reviewed=True
    legacy=report.to_dict();legacy['boreholes'][0].pop('reviewed_format')
    for s in legacy['boreholes'][0]['samples']:s.pop('description')
    loaded=StratigraphyReport.from_dict(legacy).boreholes[0]
    assert not loaded.ready_to_insert
    assert any('reconocimiento antiguo' in w for w in loaded.audit())
    with pytest.raises(ValueError,match='Coteja'):build_stratigraphy_lisp(loaded,'master.dwg')
    service=Services(tmp_path/'state');service.cad=Mock()
    try:
        with pytest.raises(ValueError,match='Coteja'):
            service.stratigraphy_insert(Mock(),{'report':legacy,'key':loaded.key})
        service.cad.assert_not_called()
    finally:service.jobs.close()
    hole.reviewed_format=hole.drawing_format
    assert hole.ready_to_insert
    lisp=build_stratigraphy_lisp(hole,'master.dwg')
    assert 'ARENA FINA COLOR GRIS' in lisp and '(* k 2.5)' in lisp
    assert 'vla-AddCircle' not in lisp and 'QSAVE' not in lisp


def test_long_sample_labels_do_not_overlap_and_format_cannot_be_overridden():
    report=parse_individual_report(PAGES)
    for sample in report.boreholes[0].samples:sample.description='Arena fina con gravas. '*12
    data=report.to_dict();data['boreholes'][0]['drawing_format']='visan-summary-v1'
    hole=StratigraphyReport.from_dict(data).boreholes[0]
    assert hole.drawing_format=='octay-intervals-v1'
    scene=stratigraphy_scene(hole)
    labels=[i for i in scene['items'] if 'sample' in i]
    for a,b in zip(labels,labels[1:]):
        assert a['point'][1]+2*len(a['text'].splitlines()) < b['point'][1]-2*len(b['text'].splitlines())
    assert max(i['point'][1] for i in labels)<scene['viewbox'][3]
