import copy
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from sincal.stratigraphy import StratigraphyReport, read_report
from sincal.stratigraphy_octay import parse_individual_report
from sincal.cad.stratigraphy import stratigraphy_scene, build_stratigraphy_lisp
from sincal.web.services import Services


PAGES = ['''PERFIL ESTRATIGRAFICO
Sondaje : Puente de ejemplo, S-08
Prof. Napa : 2,24m
Horizonte Cotas Límites Espesor Descripción
No (m) (m)
1 0,00-1,05 1,05
Relleno/Terraplén. G ravas areno limosas. Cementación nula.
2 1,05-2,00 0,95
Terreno natural. Ar enas algo limosas. Presencia de bolones
''', '''Página 2 de 4
Horizonte Cotas Límites Espesor Descripción
No (m) (m)
de tamaño máximo 6 pulgadas. Clasificación USCS: SW-SM
Observaciones:
''', '''INFORME DIARIO DE TERRENO
RESUMEN DE OPERACIÓN, AVANCE Y MUESTREO EN SUELO
Sondaje S-8 Fecha Inicio 06-05-2026
Rec. (cm) Rec. (% ) N1 N2 N3 NF
HQ3 0,00 1,05 1 75 71%
SPT N° 1 1,05 1,05 R - - R 2 0 0%
HQ3 1,05 1,80 3 60 80%
SPT N° 2 1,80 2,25 10 40 44 84 4 35 78%
''', 'ANEXO C\nPERFIL ESTRATIGRAFICO', 'Página 5 de 5']


def test_independent_horizons_sampling_units_and_refusal():
    report = parse_individual_report(PAGES)
    hole = report.boreholes[0]
    assert hole.name == 'S-08' and not hole.errors()
    assert [r.material for r in hole.horizons] == ['grava','arena']
    assert hole.horizons[1].description.endswith('Clasificación USCS: SW-SM')
    assert hole.horizons[0].inclusions == []
    assert hole.horizons[1].inclusions == ['bolones']
    assert len(hole.samples) == 4 and len(hole.tests) == 2
    assert hole.tests[0].nspt == 'R' and hole.tests[0].refusal
    assert hole.tests[1].nspt == '84' and hole.tests[1].recovered == '35'
    assert hole.tests[1].recovered_unit == 'cm' and hole.tests[1].driven == ''
    assert hole.water_depth == '2,24'
    assert any('no se extrapola' in w for w in hole.warnings)
    assert '5' in report.pages
    assert StratigraphyReport.from_dict(report.to_dict()).to_dict() == report.to_dict()


def test_scene_keeps_depths_separate_and_no_false_cementation():
    hole = parse_individual_report(PAGES).boreholes[0]
    scene = stratigraphy_scene(hole, True)
    assert scene['depth'] == 2.25 and scene['nspt_max'] == 100
    layers = [r for r in scene['items'] if r['kind']=='hatch' and r['bounds'][0]==12]
    assert len(layers) == 3  # two horizons, plus explicitly described bolones
    assert all(r['material'] != 'cementacion' for r in layers)
    assert max(r['bounds'][3] for r in layers) == pytest.approx(27+2*scene['depth_scale'])
    recovery = [r for r in scene['items'] if r.get('series')=='recovery']
    assert max(p[1] for r in recovery for p in r['points']) == 27+scene['depth_scale']*2.25
    assert any(r.get('text')=='REC. cm' or r.get('text')=='REC. CM' for r in scene['items'])
    hole.reviewed = True
    hole.reviewed_format = hole.drawing_format
    lisp = build_stratigraphy_lisp(hole, 'master.dwg', True)
    assert 'RomanD' in lisp and '(* k 2.5)' in lisp and 'QSAVE' not in lisp


@pytest.mark.parametrize('before,after', [
    ('Sondaje S-8 Fecha','Sondaje S-7 Fecha'),
    ('10 40 44 84 4 35 78%','10 40 ? 84 4 35 78%'),
    ('HQ3 1,05 1,80 3','HQ3 1,05 1,80 4'),
    ('Rec. (cm)','Rec. (m)'),
    ('SPT N° 2','SPT N° 3'),
])
def test_incomplete_or_ambiguous_extraction_blocks_drawing(before,after):
    pages=[p.replace(before,after) for p in PAGES]
    hole=parse_individual_report(pages).boreholes[0]
    assert hole.errors()
    with pytest.raises(ValueError):
        stratigraphy_scene(hole)


def test_discrepancy_warns_never_replaces_nf():
    pages=[p.replace('10 40 44 84','10 40 44 83') for p in PAGES]
    hole=parse_individual_report(pages).boreholes[0]
    assert hole.tests[1].nspt == '83'
    assert any('N2+N3' in w for w in hole.warnings)


def test_multi_import_preserves_independent_sources(tmp_path):
    service=Services(tmp_path/'state')
    job=Mock();job.cancelled.is_set.return_value=False
    try:
        files=[]
        for i in [8,9]:
            p=tmp_path/f'S{i}.txt';p.write_text('\f'.join(PAGES).replace('S-08',f'S-{i:02d}').replace('S-8 Fecha',f'S-{i} Fecha'),encoding='utf-8')
            files.append(service.files.grant(p,'report')['id'])
        result=service.stratigraphy(job,{'files':files})
        assert [r['boreholes'][0]['name'] for r in result['reports']] == ['S-08','S-09']
        assert result['reports'][0]['pages']['1'] != result['reports'][1]['pages']['1']
        assert service.stratigraphy(job,{'file':files[0]})['report']['boreholes'][0]['name'] == 'S-08'
        with pytest.raises(ValueError):
            service.stratigraphy(job,{'files':[]})
        with pytest.raises(ValueError):
            service.stratigraphy(job,{'files':[str(tmp_path/'S8.txt')]})
        from sincal.web.server import Store
        store = Store(tmp_path/'sessions.sqlite')
        payload = {'data':{},'identification':{'ot':'G129','revision':'A','structure_name':'Las Cascadas'},
                   'stratigraphy':{'report':result['reports'][0],'library':result['reports'][1:]}}
        saved = store.save(payload)
        assert store.get(saved['id'])['stratigraphy'] == payload['stratigraphy']
        payload['stratigraphy']['library'] = [{'boreholes':'invalid'}]
        with pytest.raises(ValueError):
            store.save(payload)
    finally:
        service.jobs.close()


@pytest.mark.skipif(not os.getenv('SINCAL_TEST_OCTAY_FOLDER'), reason='Local user PDFs, not committed to repository')
@pytest.mark.parametrize('name,horizons,samples,tests,depth,max_nf,water',[
    ('S7',6,47,23,35,92,'2,78'), ('S8',5,50,25,35.25,77,'2,24')])
def test_real_individual_pdf(name,horizons,samples,tests,depth,max_nf,water):
    path=Path(os.environ['SINCAL_TEST_OCTAY_FOLDER'])/f'Proyecto Puerto Octay Ruta U-55-V {name}.pdf'
    report=read_report(path)
    hole=report.boreholes[0]
    assert not hole.errors()
    assert (len(hole.horizons),len(hole.samples),len(hole.tests)) == (horizons,samples,tests)
    assert hole.water_depth == water
    assert max(int(t.nspt) for t in hole.tests if not t.refusal)==max_nf
    assert stratigraphy_scene(hole)['depth'] == depth
    assert len(report.pages) == (9 if name=='S7' else 8)
    assert all(p['image_png'] for p in report.pages.values())
    assert all(s.description for s in hole.samples)
    assert hole.samples[0].description.startswith('Arenas' if name=='S7' else 'Gravas')
    if name=='S7':
        assert hole.samples[-2].description == 'Rechazo'
        assert [t.nspt for t in hole.tests] == ['7','10','15','25','30','16','17','19','15',*(['R']*5),'87','88','77','87','90','92','85','R','R']
        assert [(t.start,t.end) for t in hole.tests[-2:]] == [('32,50','32,50'),('34,00','34,00')]
    assert StratigraphyReport.from_dict(report.to_dict()).to_dict() == report.to_dict()
