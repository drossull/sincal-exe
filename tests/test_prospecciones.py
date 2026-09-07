import json
import re
import pytest

from sincal.cad.prospecciones import build_profile_lisp, profile_scene
from sincal.prospecciones import VsLayer, VsProfile, VsReport, compare_summary, number, parse_pages, read_report
from sincal.sessions import SessionStore


PAGE = '''Figura 5-5: Perfil de suelo y Vs,30 - Arreglo Nº1-1
Nº Estratos Inicio [m] Final [m] Vs [m/s]
1 0,00 1,58 526,30
2 1,58 2,11 553,58
3 2,11 7,32 559,65
4 7,32 13,58 603,60
5 13,58 17,00 890,03
6 17,00 22,37 958,23
7 22,37 30,00 1138,58
Vs,30 = 754,00 m/s
'''


def test_extracts_official_values_and_page_without_rewriting():
    report = parse_pages(['Portada', PAGE])
    p = report.profiles[0]
    assert (p.name, p.page, len(p.layers)) == ('Arreglo 1-1', 2, 7)
    assert p.layers[0].start == '0,00'
    assert p.official_vs30 == '754,00'
    assert p.check_vs30() == pytest.approx(753.99674)
    assert p.warnings() == []


def test_summary_conflict_is_a_warning_not_a_replacement():
    report = parse_pages([PAGE])
    summary = '\n'.join(f'{r.index} {r.start} {r.end} {r.vs} II B' +
                        (' 700,00' if r.index == 4 else '') for r in report.profiles[0].layers)
    compare_summary(report, summary, 123)
    p = report.profiles[0]
    assert '700,00' in p.warnings()[0]
    assert '123' in p.warnings()[0]
    assert p.official_vs30 == '754,00'


def test_control_warns_but_does_not_replace_official():
    p = parse_pages([PAGE.replace('754,00', '900,00')]).profiles[0]
    assert 'control' in p.warnings()[0]
    assert p.official_vs30 == '900,00'
    assert '900,00 m/s' in build_profile_lisp(p)


def test_missing_official_remains_missing_and_bad_geometry_is_blocked():
    p = parse_pages([PAGE.replace('Vs,30 = 754,00 m/s', '')]).profiles[0]
    assert p.official_vs30 == ''
    assert 'No identificado' in build_profile_lisp(p)
    p.layers[1] = VsLayer(2, '1,00', '2,11', '553,58')
    assert p.errors()
    with pytest.raises(ValueError):
        profile_scene(p)


def test_control_clips_at_30_and_does_not_extrapolate():
    p = VsProfile('x', 'X', 1, [VsLayer(1, '0', '10', '200'), VsLayer(2, '10', '40', '400')])
    assert p.check_vs30() == pytest.approx(300)
    p.layers = p.layers[:1]
    assert p.check_vs30() is None


def test_other_decimal_conventions_and_header_aliases():
    page = PAGE.replace('Inicio', 'Desde').replace('Final', 'Hasta').replace(',', '.')
    p = parse_pages([page]).profiles[0]
    assert len(p.layers) == 7
    assert number('1.138,58') == number('1,138.58') == 1138.58


def test_repeated_arrangements_are_not_silently_collapsed():
    report = parse_pages([PAGE, PAGE])
    assert len(report.profiles) == 2
    assert report.profiles[0].key != report.profiles[1].key


def test_ambiguous_and_scanned_pages_do_not_invent_data():
    with pytest.raises(ValueError):
        parse_pages([''])
    report = parse_pages([PAGE, PAGE + '\n1 0 30 700'])
    assert len(report.profiles) == 1
    assert 'ambigua' in report.notices[0]


def test_session_round_trip_without_source_and_legacy_session(tmp_path):
    report = parse_pages([PAGE], path=str(tmp_path / 'missing.pdf'), sha256='abc')
    store = SessionStore(tmp_path, tmp_path / 'recovery')
    _, path = store.save({'prospecciones': {'report': report.to_dict(), 'selected_key': report.profiles[0].key}})
    loaded = store.load(path)['prospecciones']
    restored = VsReport.from_dict(loaded['report'])
    assert restored == report
    _, old = store.save({'metadata': {'name': 'Legacy'}})
    assert store.load(old).get('prospecciones') is None


def test_txt_import_and_unsupported_format(tmp_path):
    source = tmp_path / 'report.txt'
    source.write_text(PAGE, encoding='utf-8')
    assert len(read_report(str(source)).sha256) == 64
    with pytest.raises(ValueError):
        read_report('report.docx')


def test_vector_geometry_is_stepped_and_color_roles_are_preserved():
    p = parse_pages([PAGE]).profiles[0]
    scene = profile_scene(p)
    curve = next(s for s in scene if s['kind'] == 'polyline')
    assert curve['color'] == 5
    assert len(curve['points']) == 14
    for a, b in zip(curve['points'], curve['points'][1:]):
        assert a[0] == b[0] or a[1] == b[1]
    assert all(s['color'] == 3 for s in scene if s['kind'] == 'text')
    assert all(s['color'] == 1 for s in scene if s['kind'] == 'circle')
    assert len(profile_scene(p, False)) < len(scene)


def test_lisp_is_balanced_escaped_and_has_annotation_and_rollback():
    p = parse_pages([PAGE]).profiles[0]
    p.name = 'Perfil "A" (texto)'
    lisp = build_profile_lisp(p)
    no_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', lisp)
    balance = 0
    for char in no_strings:
        balance += (char == '(') - (char == ')')
        assert balance >= 0
    assert balance == 0
    assert '"RomanD"' in lisp
    assert '"Annotative" 1' in lisp
    assert 'vla-Delete (list obj)' in lisp
    assert 'vla-StartUndoMark' in lisp
    assert 'QSAVE' not in lisp
    assert 'vla-get-ModelSpace' in lisp


def test_real_report_when_explicitly_available():
    import os
    source = os.environ.get('SINCAL_TEST_IMS')
    if not source:
        pytest.skip('Set SINCAL_TEST_IMS to the local reference PDF')
    report = read_report(source)
    assert [p.page for p in report.profiles] == [101, 104, 107, 110, 114, 117]
    assert [len(p.layers) for p in report.profiles] == [7, 6, 7, 7, 4, 7]
    assert [p.official_vs30 for p in report.profiles] == ['754,00', '690,70', '791,54', '625,37', '704,63', '717,81']
    assert '657,29' in report.profiles[1].warnings()[0]
    assert VsReport.from_dict(json.loads(json.dumps(report.to_dict()))) == report
