"""Fixtures sintéticas: no publican el informe ni los dibujos del cliente."""
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace

from PIL import Image
import pytest

from sincal.cad.prospecciones import build_profile_lisp, profile_scene
from sincal.prospecciones import VsReport, compare_summary, parse_pages, read_report
from sincal.prospecciones_ocr import ImportCancelled, contexts, extract_images, parse_ocr
from test_prospecciones import PAGE


def raw_table(rows=None, official='400,00', confidence=.999, combined=False):
    rows = rows or [('1', '0,00', '10,00', '200,00'), ('2', '10,00', '30,00', '500,00')]
    tokens = [('Nº Estratos', 30, 20), ('Inicio [m]', 130, 20), ('Final [m]', 230, 20), ('Vs [m/s]', 330, 20)]
    for index, row in enumerate(rows):
        tokens += [(text, 30+100*column, 50+index*25) for column, text in enumerate(row)]
    y = 65+len(rows)*25
    if combined:
        tokens.append(('Vs,30 = '+official, 180, y))
    else:
        tokens += [('Vs,30 =', 130, y), (official, 230, y)]
    return {'rec_texts': [t[0] for t in tokens], 'rec_scores': [confidence]*len(tokens),
            'rec_boxes': [[x-25, y-8, x+25, y+8] for _, x, y in tokens]}


class Engine:
    closed = False
    def __init__(self, cancel=None):
        self.cancel = cancel
    def recognize(self, image):
        return raw_table()
    def close(self):
        type(self).closed = True


def reader(text='Descripción del perfil de suelo Vs'):
    page = SimpleNamespace(images=[SimpleNamespace(name='tabla.png', image=Image.new('RGB', (450, 240), 'white'))],
                           extract_text=lambda **kwargs: text)
    return SimpleNamespace(pages=[page], is_encrypted=False)


def test_coordinates_preserve_values_and_combined_vs30():
    for combined in (False, True):
        parsed = parse_ocr(raw_table(combined=combined))
        assert parsed['rows'][1] == ['2', '10,00', '30,00', '500,00']
        assert parsed['official'] == '400,00'
        assert parsed['errors'] == []
        assert len(parsed['cells']) == 9


def test_not_a_table_and_incomplete_protocol():
    raw = raw_table()
    raw['rec_texts'][1] = 'Fotografía'
    assert parse_ocr(raw) is None
    raw['rec_scores'].pop()
    with pytest.raises(ValueError, match='incompleta'):
        parse_ocr(raw)


def test_full_page_footer_and_neighbouring_graph_do_not_become_cells():
    raw = raw_table()
    raw['rec_texts'] += ['17', '800']
    raw['rec_scores'] += [.999, .999]
    raw['rec_boxes'] += [[120, 790, 160, 810], [650, 45, 700, 61]]
    parsed = parse_ocr(raw)
    assert not parsed['errors'] and len(parsed['rows']) == 2


def test_missing_or_merged_numeric_cell_is_not_repaired():
    for invalid in ('5OO,00', '500,00 600,00'):
        raw = raw_table()
        raw['rec_texts'][11] = invalid
        result = parse_ocr(raw)
        assert result['errors']
        assert len(result['rows']) == 1


def test_multiple_tables_are_rejected_not_merged():
    raw = raw_table()
    for name in raw:
        raw[name] += raw[name]
    result = parse_ocr(raw)
    assert result['rows'] == []
    assert 'Varios bloques' in result['errors'][0]


def test_context_distinguishes_annex_and_flags_wrong_caption():
    pages = ['VS30 – P33 TRINCHERA\n5.5. PERFIL GEOFÍSICO N°5\nArreglo N°4-1', 'Tabla',
             'VS30 – P17 OTRA ESTRUCTURA\nArreglo N°4-1']
    assert contexts(pages) == [('P33', '5', '4-1'), ('P33', '5', '4-1'), ('P17', '', '4-1')]
    report = VsReport('source', 'sha', [])
    document = reader()
    extract_images(document, [pages[0]+'\nDescripción del perfil de suelo Vs' + 'x'*100], report, b'', engine_factory=Engine)
    profile = report.profiles[0]
    assert 'P33' in profile.name and 'Perfil 5' in profile.name and 'Arreglo 4-1' in profile.name
    assert 'rótulo' in profile.extraction_warnings[0]


def test_evidence_roundtrip_and_review_gate():
    report = VsReport('source', 'sha', [])
    document = reader('Descripción del perfil de suelo Vs '+ 'x'*100)
    extract_images(document, [document.pages[0].extract_text()], report, b'', engine_factory=Engine)
    assert Engine.closed
    assert len(report.profiles) == 1
    profile = report.profiles[0]
    assert profile.method == 'ocr' and not profile.reviewed
    Image.open(BytesIO(base64.b64decode(profile.evidence['image_png']))).verify()
    restored = VsReport.from_dict(json.loads(json.dumps(report.to_dict())))
    assert restored == report
    assert profile_scene(profile)
    with pytest.raises(ValueError, match='Revisa'):
        build_profile_lisp(profile)
    profile.reviewed = True
    assert build_profile_lisp(profile)


def test_low_confidence_is_visible_never_auto_corrected():
    class Doubtful(Engine):
        def recognize(self, image):
            return raw_table(confidence=.6)
    report = VsReport('source', 'sha', [])
    extract_images(reader(), [''], report, b'', engine_factory=Doubtful)
    assert '98 %' in report.profiles[0].warnings()[0]
    assert report.profiles[0].official_vs30 == '400,00'


def test_engine_missing_keeps_native_and_reports_incomplete():
    report = parse_pages([PAGE])
    def missing(**kwargs):
        raise RuntimeError('motor ausente')
    extract_images(reader(), [PAGE], report, b'', engine_factory=missing)
    assert len(report.profiles) == 1
    assert any('INCOMPLETO' in n and 'motor ausente' in n for n in report.notices)


def test_cancellation_before_and_during_engine_releases_worker():
    event = threading.Event()
    event.set()
    with pytest.raises(ImportCancelled):
        extract_images(reader(), [PAGE], VsReport('', '', []), b'', cancel=event, engine_factory=Engine)
    class Cancelled(Engine):
        closed = False
        def recognize(self, image):
            raise ImportCancelled('Cancelado')
    with pytest.raises(ImportCancelled):
        extract_images(reader(), [PAGE], VsReport('', '', []), b'', engine_factory=Cancelled)
    assert Cancelled.closed


def test_text_preferred_over_identical_image():
    report = parse_pages([PAGE])
    profile = report.profiles[0]
    class Same(Engine):
        def recognize(self, image):
            return raw_table([(str(r.index), r.start, r.end, r.vs) for r in profile.layers], profile.official_vs30)
    extract_images(reader(), [PAGE], report, b'', engine_factory=Same)
    assert report.profiles == [profile] and profile.method == 'text'


def test_partial_summary_warns_without_filling_or_replacing():
    report = parse_pages([PAGE])
    p = report.profiles[0]
    summary = '\n'.join(f'{r.index} {r.start} {r.end} {r.vs} II B' + (' 777,00' if r.index == 3 else '')
                        for r in p.layers[:-1])
    compare_summary(report, summary, 10)
    assert p.references[0]['partial']
    assert any('no incluye todos' in warning for warning in p.warnings())
    assert p.official_vs30 == '754,00' and len(p.layers) == 7


def test_read_report_scanned_only_and_disabled_ocr(monkeypatch, tmp_path):
    source = tmp_path / 'scan.pdf'
    source.write_bytes(b'fixture')
    monkeypatch.setattr('pypdf.PdfReader', lambda *_: reader(''))
    report = read_report(str(source), engine_factory=Engine)
    assert report.profiles[0].method == 'ocr'
    with pytest.raises(ValueError, match='No se reconocieron'):
        read_report(str(source), ocr=False)


def test_real_loreto_integration_when_available():
    source = os.environ.get('SINCAL_TEST_LORETO')
    if not source:
        pytest.skip('Set SINCAL_TEST_LORETO and build OCR runtime for the full PDF integration')
    report = read_report(source)
    expected = {302: '540,82', 304: '615,01', 308: '645,38', 311: '632,61', 315: '636,87',
                318: '577,43', 321: '594,03', 324: '595,85', 327: '637,94', 330: '626,54'}
    for page, official in expected.items():
        profile = next(p for p in report.profiles if p.page == page)
        assert profile.official_vs30 == official and not profile.errors()
        assert profile.method == ('text' if page == 304 else 'ocr')
    assert not any('INCOMPLETO' in n for n in report.notices)
