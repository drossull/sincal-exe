import copy
import json
import os
from pathlib import Path

import pytest

from sincal.prospecciones import parse_pages, read_report, VsReport
from sincal.cad.prospecciones import profile_scene, build_profile_lisp
from sincal.web.services import Services

HEADER = '''GEOIBERICA SpA – Dirección documental de prueba
ESTUDIO GEOFÍSICO - ReMi
Documento QA-REM-001
Fecha 12/05/2026
Elaborado por AAA
Aprobado por BBB
mail: estudio@example.comCelular: +56 9 1234 5678
www.example.com
'''
TABLE = '''LOCALIZACION: PUENTE DE PRUEBA, PERFIL 1 EN SENTIDO NW – SE
PROFUNDIDAD Vs (m/s) ESPESOR CAPA (m) densidad POISSON G K E
0,00 - 2,73 167,84 2,73 1200 0,30 33,80 11,72 87,89
2,73 - 17,30 210,05 14,58 1400 0,30 61,77 21,41 160,60
17,30 - 35,00 510,80 17,70 1800 0,30 469,66 162,81 1221,11
Vs30= 298,85
'''
PAGES = [HEADER+'PERFIL 1 EN SENTIDO NW – SE', HEADER+'velocidades máximas de 510,90 m/s',
         HEADER+'Figura 4: perfil tomográfico', HEADER+TABLE,
         HEADER+TABLE.replace('PERFIL 1 EN SENTIDO NW – SE','PERFIL 2 EN SENTIDO SW – NE')]


def test_geoiberica_identity_metadata_precision_and_session_roundtrip():
    report=parse_pages(PAGES, path='anything.txt')
    assert [p.name for p in report.profiles]==['Perfil 1 · NW–SE','Perfil 2 · SW–NE']
    p=report.profiles[0]
    assert p.page==4 and p.layers[-1].vs=='510,80'
    assert p.study_info['company']=='GEOIBERICA SpA'
    assert p.study_info['email']=='estudio@example.com'
    assert p.study_info['prepared_by']=='AAA' and p.study_info['approved_by']=='BBB'
    assert any('14,58' in w for w in p.warnings())
    assert any('510,90' in w and 'p. 2' in w for w in p.warnings())
    assert not any('510,90' in w for w in report.profiles[1].warnings())
    assert p.documentary_rows[1]['thickness']=='14,58'  # never silently corrected
    assert VsReport.from_dict(json.loads(json.dumps(report.to_dict())))==report
    legacy=report.to_dict()
    for profile in legacy['profiles']:
        for key in ('study_info','documentary_rows','source_format'):profile.pop(key)
    assert VsReport.from_dict(legacy).profiles[0].study_info=={}


@pytest.mark.parametrize('change', [lambda s:s.replace('1200 0,30','1200'),
    lambda s:s.replace('2,73 - 17,30','2,80 - 17,30'),
    lambda s:s+'Vs30= 999,00\n',lambda s:s+TABLE,
    lambda s:s.replace('LOCALIZACION:','UBICACION:')])
def test_incomplete_ambiguous_or_discontinuous_table_cannot_be_inserted(change):
    profile=parse_pages([HEADER+change(TABLE)]).profiles[0]
    assert profile.errors()
    with pytest.raises(ValueError):build_profile_lisp(profile)


def test_metadata_and_documentary_parameters_never_enter_cad():
    profile=parse_pages(PAGES).profiles[0]
    original=copy.deepcopy(profile)
    for with_table in (True,False):
        scene=profile_scene(profile,with_table,5)
        source=build_profile_lisp(profile,with_table,5,'1:200 (m)')
        for secret in ('GEOIBERICA','QA-REM-001','estudio@example.com','AAA','BBB','469,66','1221,11'):
            assert secret not in source and secret not in str(scene)
        curve=next(i for i in scene if i['kind']=='polyline')
        assert (curve['points'][-1][1]-curve['points'][0][1])/5==pytest.approx(35)
        assert '(sp:scale)' in source and '"_Add" scale-name' in source
    assert profile==original


def test_unrelated_report_not_misidentified():
    from test_prospecciones import PAGE
    report=parse_pages([PAGE])
    assert report.profiles[0].study_info=={}
    assert report.profiles[0].source_format==''


def test_profile_completion_preserves_native_rollback_and_error_messages(tmp_path):
    from sincal.web.cad_worker import command_with_completion,read_completion
    request={'command':'(c:SINCAL-PROSPECCIONES)\n','marker':str(tmp_path/'done'),'token':'qa','completion':'profile-v1'}
    command=command_with_completion(request)
    assert '*SINCAL_PROFILE_COMPLETION*' in command
    assert 'vl-catch-all-apply' not in command  # do not intercept the command's *error* rollback
    Path(request['marker']).write_text('qa\nerror\nCambio la escala anotativa\n',encoding='utf8')
    with pytest.raises(RuntimeError,match='escala anotativa'):read_completion(request)


def test_real_la_cascada_without_ocr():
    source=os.environ.get('SINCAL_TEST_CASCADA_VS')
    if not source:pytest.skip('Set SINCAL_TEST_CASCADA_VS for the local source PDF')
    original=Path(source).read_bytes()
    def no_ocr():raise AssertionError('Native tables must not need OCR')
    report=read_report(source,engine_factory=no_ocr)
    assert [p.page for p in report.profiles]==[4,8]
    assert [len(p.layers) for p in report.profiles]==[8,8]
    assert [p.official_vs30 for p in report.profiles]==['298,85','276,42']
    expected=[['167,84','210,05','222,36','322,61','389,45','436,94','465,08','510,80'],
              ['159,05','210,05','282,16','322,61','334,93','345,48','359,55','368,34']]
    assert [[r.vs for r in p.layers] for p in report.profiles]==expected
    for profile in report.profiles:
        assert not profile.errors() and profile.layers[-1].end=='35,00'
        assert profile.study_info['company']=='GEOIBERICA SpA'
    assert [len(p.extraction_warnings) for p in report.profiles]==[2,4]
    assert len(Services.describe_report(report,5)['checks'])==2
    assert Path(source).read_bytes()==original
