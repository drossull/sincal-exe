import copy
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from sincal.stratigraphy import (Borehole, Interval, Spt, VsBand, StratigraphyReport,
                                 material, parse_pages, read_report)
from sincal.cad.stratigraphy import stratigraphy_scene, build_stratigraphy_lisp, drawing_label, mtext_label
from sincal.prospecciones_ocr import ImportCancelled
from sincal.web.services import Services


PAGES = ['3.1.- SONDAJE S-40', '''Tabla Nº 3: De la Perforación
Recuperado % de
Desde (m) Hasta (m) Perforado (m) Recuperado
0,00 1,05 1,05 0,60 57 Gravas T.M. 2", con arena.
1,05 1,50 0,45 0,25 56 SPT Nº 1: Arenas con gravas.
1,50 2,50 1,00 0,65 65 Gravas con bolón 5".
2,50 2,50 0,00 0,00 0 SPT Nº 2: Rechazo en N1.
2,50 3,50 1,00 0,75 75 Pasada de hormigón y acero.
ESTRATIGRAFIA DEL SONDAJE (SEGÚN EL OPERADOR)
PROFUNDIDAD Descripción de suelo según Operador''', '''Tabla N°4: Ensayos de Penetración estándar (SPT)
Se Ejecutaron 2 Ensayos de este tipo
1 1,05 1,50 0,45 0,25 7 11 16 27
2 2,50 2,50 0,00 0,00 50+ R:N1
LISTADO DE ENSAYOS DE PENETRACION ESTANDAR (SPT)
SONDAJE S-40''', '''INFORME DIARIO DE SONDAJE ROTACION
2 2,60 2,60 2 0,00 50+ R:N1''']


def report():
    return parse_pages(PAGES)


def test_official_values_independent_of_recovery_and_refusal():
    r = report()
    h = r.boreholes[0]
    assert not h.errors()
    assert [v.recovery for v in h.intervals] == ['57','56','65','0','75']
    assert h.tests[0].nspt == '27' and h.tests[1].nspt == 'R:N1'
    assert [v.material for v in h.intervals] == ['grava','arena','grava','sin_asignar','hormigon']
    assert h.intervals[2].inclusions == ['bolones']
    assert h.tests[1].start == '2,50'
    assert any('2,60' in w and 'parte diario' in w for w in h.warnings)
    assert StratigraphyReport.from_dict(r.to_dict()).to_dict() == r.to_dict()


def test_continuation_and_sondaje_identity_not_water_caption():
    pages = [PAGES[0],PAGES[1], '3,50 4,50 1,00 0,5 50 Grava con arena.\nColor gris.', PAGES[2],
             '3.1.- SONDAJE S-94',PAGES[1],PAGES[2].replace('SONDAJE S-40','SONDAJE S-94\nCONTROL DE NIVEL SONDAJE S-95')]
    r = parse_pages(pages)
    assert [h.name for h in r.boreholes] == ['S-40','S-94']
    assert len(r.boreholes[0].intervals) == 6
    assert r.boreholes[0].intervals[-1].description.endswith('Color gris.')
    assert len(r.boreholes[1].tests) == 2


def test_scene_shared_depth_and_no_fake_zero_recovery_at_refusal():
    h = report().boreholes[0]
    scene = stratigraphy_scene(h)
    hatches = [i for i in scene['items'] if i['kind']=='hatch']
    assert hatches[0]['bounds'][1] == 27
    assert hatches[0]['bounds'][3] == pytest.approx(27+150*1.05/3.5)
    assert all(i['bounds'][3]>i['bounds'][1] for i in hatches)
    recovery = [i for i in scene['items'] if i['kind']=='line' and i['color']==5]
    assert recovery[0]['points'][0][0] == pytest.approx(38+80*.57)
    assert all(p[0]>38 for item in recovery for p in item['points'])
    assert any(i.get('text')=='R' for i in scene['items'])
    assert all(i['height']==2.5 for i in scene['items'] if i['kind']=='text')
    assert stratigraphy_scene(h,True)['viewbox'][3] > scene['viewbox'][3]


def test_errors_block_bad_geometry_unknown_soil_and_unreviewed_cad():
    h = report().boreholes[0]
    with pytest.raises(ValueError,match='Coteja'):
        build_stratigraphy_lisp(h, 'master.dwg')
    h.reviewed = True
    source = build_stratigraphy_lisp(h, 'master.dwg')
    assert 'SINCAL-ESTRATIGRAFIA' in source and 'RomanD' in source and '(* k 2.5)' in source
    assert 'vla-CopyObjects' in source and 'PROSPECCIONES' in source
    assert 'vla-Save' not in source and 'QSAVE' not in source
    assert 'vla-EndUndoMark' in source and 'vla-Delete' in source
    for attr,value in [('start','-1'),('end','NaN'),('recovery','101'),('material','inventado')]:
        bad = copy.deepcopy(h)
        setattr(bad.intervals[0],attr,value)
        assert bad.errors()
        with pytest.raises(ValueError):
            stratigraphy_scene(bad)


def test_source_warnings_do_not_modify_official_values():
    h = report().boreholes[0]
    h.intervals[0].recovery = '90'
    before = h.intervals[0].recovery
    assert any('cociente' in w for w in h.audit())
    assert h.intervals[0].recovery == before


def test_vs_bands_extend_only_vs_axis_not_soil_or_recovery():
    h = report().boreholes[0]
    h.vs_bands = [VsBand('0','1.49','185','185',19,'Arreglo 3-2',117),
                  VsBand('1.49','30','608','676',19,'Arreglo 3-2',117)]
    scene = stratigraphy_scene(h)
    assert scene['depth'] == 30
    assert sum(i['kind']=='triangle' for i in scene['items']) == 4
    assert any(i.get('text')=='VS = 608 - 676 m/s' for i in scene['items'])
    recovery = [i for i in scene['items'] if i['kind']=='line' and i['color']==5]
    assert max(p[1] for item in recovery for p in item['points']) == 27+3.5*8
    soil = [i for i in scene['items'] if i['kind']=='hatch' and i['bounds'][0]==12]
    assert max(i['bounds'][3] for i in soil) == 27+3.5*8
    r = report()
    r.boreholes[0] = h
    assert StratigraphyReport.from_dict(r.to_dict()).to_dict() == r.to_dict()
    h.vs_bands[1].start = '2'
    assert h.errors()


def test_drawing_typography_colors_and_official_text_unchanged():
    r = report()
    hole = r.boreholes[0]
    hole.vs_bands = [VsBand('0','3.5','608','676',19,'Arreglo 3-2',117)]
    original = copy.deepcopy(r.to_dict())
    scene = stratigraphy_scene(hole, include_table=True)
    labels = [i['text'] for i in scene['items'] if i['kind']=='text']
    assert 'SONDAJE S-40' in labels and 'PROF. (m)' in labels
    assert 'VS = 608 - 676 m/s' in labels
    assert 'DESDE m' in labels and 'NSPT' in labels
    assert all(drawing_label(t)==t for t in labels)
    assert drawing_label('Gravas T.M. 2,5 m, Vs 500 m/s') == 'GRAVAS T.M. 2,5 m, VS 500 m/s'
    assert all(i['color'] != 7 for i in scene['items'])
    assert all(i['color']==1 for i in scene['items'] if i['kind']=='triangle')
    assert all(i['color']==8 for i in scene['items'] if i['kind']=='hatch')
    assert any(i['color']==5 for i in scene['items'])
    assert r.to_dict() == original
    assert mtext_label('NSPT (GOLPES/PIE)') == r'N{\H0.7x;\S^SPT;} (GOLPES/PIE)'
    assert mtext_label('NSPT\nNSPT') == r'N{\H0.7x;\S^SPT;}\PN{\H0.7x;\S^SPT;}'
    assert mtext_label(r'{\C1;DOCUMENTO}') == '(/C1;DOCUMENTO)'
    hole.reviewed = True
    source = build_stratigraphy_lisp(hole, 'master.dwg', True)
    assert r'N{\\H0.7x;\\S^SPT;}' in source


def test_insertion_uses_installed_master_and_native_completion(tmp_path, monkeypatch):
    r=report()
    r.boreholes[0].reviewed=True
    service=Services(tmp_path/'service')
    service.cad=Mock(return_value={'message':'ok'})
    monkeypatch.setattr('sincal.runtime.ruta_recurso',Mock(side_effect=AssertionError('Do not use cached master')))
    monkeypatch.setattr('sincal.runtime.ruta_recurso_instalado',lambda *parts:str(tmp_path/'installed-master.dwg'))
    job=Mock(id='fixture')
    try:
        service.stratigraphy_insert(job,{'report':r.to_dict(),'key':r.boreholes[0].key})
        source=(service.runtime/'fixture/operation.lsp').read_text(encoding='utf-8')
        assert 'installed-master.dwg' in source
        assert source.index('(foreach obj (list') < source.index('(setq base (getpoint')
        assert '(se:finish "error"' in source and '(se:finish "ok"' in source
        assert service.cad.call_args.kwargs['completion']=='stratigraphy-v1'
    finally:
        service.jobs.close()


def test_services_boundary_grants_cancel_and_cad_guard(tmp_path):
    path = tmp_path/'report.txt'
    path.write_text('\f'.join(PAGES),encoding='utf-8')
    service = Services(tmp_path/'service')
    job = Mock()
    job.cancelled.is_set.return_value = False
    try:
        grant = service.files.grant(path,'report')
        result = service.stratigraphy(job,{'file':grant['id']})
        assert len(result['report']['boreholes'])==1 and result['checks'][0]['scene']
        with pytest.raises(ValueError):
            service.stratigraphy(job,{'file':str(path)})
        with pytest.raises(ValueError,match='Coteja'):
            service.stratigraphy_insert(job,{'report':result['report'],'key':result['report']['boreholes'][0]['key']})
        job.cancelled.is_set.return_value = True
        with pytest.raises(ImportCancelled):
            read_report(path,cancel=job.cancelled)
    finally:
        service.jobs.close()


def test_unrecognized_format_is_explicit_not_silent_empty(tmp_path):
    path = tmp_path/'unknown.txt'
    path.write_text('Un informe cualquiera',encoding='utf-8')
    with pytest.raises(ValueError,match='No se reconocieron'):
        read_report(path)


def test_session_schema_limits_and_duplicate_keys():
    data = report().to_dict()
    data['boreholes'].append(copy.deepcopy(data['boreholes'][0]))
    with pytest.raises(ValueError,match='Identificador'):
        StratigraphyReport.from_dict(data)
    with pytest.raises(ValueError):
        StratigraphyReport.from_dict({'boreholes':'bad'})


@pytest.mark.parametrize('field,value', [('start', 0), ('material', {}), ('page', True), ('description', ['bad'])])
def test_session_rejects_wrong_field_types(field, value):
    data = report().to_dict()
    data['boreholes'][0]['intervals'][0][field] = value
    with pytest.raises(ValueError):
        StratigraphyReport.from_dict(data)


def test_zero_depth_and_corrupt_evidence_are_rejected():
    h = Borehole('zero', 'Zero', [Interval('0','0','0','0','0','Rechazo',1)],
                 [Spt(1,'0','0','0','0','50+','','','R:N1',1)])
    assert h.errors()
    with pytest.raises(ValueError, match='profundidad positiva'):
        stratigraphy_scene(h)
    data = report().to_dict()
    data['pages'] = {'1': {'text': ['not text']}}
    with pytest.raises(ValueError, match='evidencia'):
        StratigraphyReport.from_dict(data)


@pytest.mark.skipif(not os.environ.get('SINCAL_CALERA_PDF'),reason='Local IMS integration fixture not distributed')
def test_real_calera_all_four_boreholes():
    r = read_report(os.environ['SINCAL_CALERA_PDF'])
    assert [(h.name,len(h.intervals),len(h.tests)) for h in r.boreholes] == [
        ('S-40',66,32),('S-94',29,14),('S-111',30,10),('S-125',29,14)]
    assert all(not h.errors() for h in r.boreholes)
    assert r.boreholes[0].intervals[0].recovery == '57'
    assert r.boreholes[0].tests[0].nspt == '27'
    assert r.boreholes[1].tests[2].start == '4,10'
    assert any('13 ensayos' in w for w in r.boreholes[1].warnings)
    assert r.pages['19']['image_png']
    assert [len(h.vs_bands) for h in r.boreholes] == [4,0,4,4]
    assert [(v.start,v.end,v.low,v.high) for v in r.boreholes[0].vs_bands] == [
        ('0,00','1,49','185','185'),('1,49','3,59','608','676'),
        ('3,59','9,10','744','786'),('9,10','30,00','854','896')]
    assert r.boreholes[2].vs_bands[-1].end == '30,00'
    assert any('890.03' in w for w in r.boreholes[-1].warnings)
