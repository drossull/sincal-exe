"""Native CDI tables: no image digitizing, guessing missing tests or N values."""
from collections import Counter
import os
from pathlib import Path

import pytest

from sincal.stratigraphy import StratigraphyReport
from sincal.stratigraphy_cdi import parse_cdi_report


CONTACT = '''“Estudio de Ingeniería de ejemplo”
Paseo Bulnes 317 Piso 7, Fono: (562)699 0053 Fax:(562) 699 3985, CP 6520418, email: cdi@cdi.cl - URL: http://www.cdi.cl Santiago - Chile
'''
RECOVERY_HEADER = '''PROFUNDIDAD RECUPERACIÓN PRESIÓN
PERF. [PSI] DESCRIPCIÓN SEGÚN SONDADOR
DESDE [m] HASTA [m] PERFORADO [m] RECUPERADO [m] RECUPERACIÓN [%]
'''
SPT_HEADER = '''REGISTRO PRUEBAS DE PENETRACIÓN ESTÁNDAR (M 63,5 kg cada 0,76 m)
HERRAMIENTA OCUPADA SPT MANUAL/HIDRAULICO
PROFUNDIDAD MUESTRA Registro SPT (N1+N3=Nspt)
DESDE [m] HASTA [m] NÚMERO LONG. (cm) N1 N2 N3 Nspt
'''
PAGES = [CONTACT + '''Página 1 de 3
1. REGISTRO SPT
Tabla 1: Registro de número de golpes/pie de ensayo SPT en S-2, desde 0.00 m hasta 2.00 m (Hoja 1).
''' + RECOVERY_HEADER + '''0.00 1.00 1.00 0.60 60 - H1 (0.00m-1.00m): Arena limosa.
H2 (1.00m-3.00m): Limo arcilloso, plasticidad baja.
1.03 2.00 0.97 0.80 82 1000
''' + SPT_HEADER + '''Cuchara Normal HIDRAULICO 1.00 1.03 1 0 50R - - R
''', CONTACT + '''Página 2 de 3
''' + RECOVERY_HEADER + '''2.00 2.00 0.00 0.00 0 -
H2 (1.00m-3.00m): Limo arcilloso,
plasticidad baja. 2.00 3.00 1.00 0.50 50
''' + SPT_HEADER + '''Cuchara Normal HIDRAULICO 2.00 2.00 3 0 59R - - R
Cuchara Normal HIDRAULICO 2.55 3.00 3 20 7 9 5 14
''', CONTACT + '''Página 15 de 3
Imagen 1. Gráfica del Ensayo SPT en Terreno y Perfil Estratigráfico de Descripción Visual.
''']


def test_independent_tables_and_literal_values():
    report = parse_cdi_report(PAGES, source='not-the-borehole-name.pdf', sha256='a'*64)
    hole = report.boreholes[0]
    assert hole.name == 'S-2' and hole.method == 'cdi-text'
    assert hole.drawing_format == 'cdi-spt-v1' and not hole.errors()
    assert not hole.intervals and not hole.samples and not hole.vs_bands
    assert len(hole.horizons) == 2 and len(hole.drilling_records) == 4 and len(hole.tests) == 3
    assert [h.thickness for h in hole.horizons] == ['', '']
    assert [h.material for h in hole.horizons] == ['arena', 'limo']
    assert hole.horizons[1].description == 'Limo arcilloso, plasticidad baja.'
    assert hole.drilling_records[2].start == hole.drilling_records[2].end == '2.00'
    assert hole.drilling_records[2].recovery == '0'
    assert hole.drilling_records[-1].pressure == ''
    assert [t.index for t in hole.tests] == [1, 2, 3]
    assert [t.sample_number for t in hole.tests] == ['1', '3', '3']
    assert [t.n1 for t in hole.tests] == ['50R', '59R', '7']
    assert [t.nspt for t in hole.tests] == ['R', 'R', '14']
    assert hole.tests[-1].sample_length == '20' and hole.tests[-1].recovered == ''
    assert all(t.recovered_unit == 'cm' and t.driven == '' for t in hole.tests)
    assert hole.tests[-1].tool == 'Cuchara Normal' and hole.tests[-1].mechanism == 'HIDRAULICO'
    assert set(report.pages) == {'1', '2', '3'}
    warnings = '\n'.join(hole.warnings)
    assert 'N1+N3' in warnings and 'repetida' in warnings and 'muestra 2.' in warnings
    assert 'Página 15 de 3' in warnings and 'presión' in warnings
    assert hole.study_info['company'] == 'CDI'
    assert hole.study_info['email'] == 'cdi@cdi.cl'
    assert hole.study_info['document'] == 'Estudio de Ingeniería de ejemplo'
    assert 'date' not in hole.study_info and 'prepared_by' not in hole.study_info
    assert StratigraphyReport.from_dict(report.to_dict()).to_dict() == report.to_dict()


def test_identity_and_format_are_not_guessed_from_filename():
    assert not parse_cdi_report(['Unknown data'], 'CDI S-2 Ruta29.pdf').boreholes
    assert not parse_cdi_report([p.replace('cdi.cl', 'unknown.example') for p in PAGES]).boreholes
    assert not parse_cdi_report([p.replace('Tabla 1:', 'Cuadro:') for p in PAGES], 'S-2.pdf').boreholes
    mixed = list(PAGES)
    mixed[1] = mixed[1].replace('Página 2 de 3', 'Tabla 2: Ensayo SPT en S-3, desde 2 m hasta 3 m.')
    hole = parse_cdi_report(mixed).boreholes[0]
    assert hole.extraction_errors and not hole.tests and not hole.drilling_records


@pytest.mark.parametrize('before,after', [
    ('0.00 1.00 1.00 0.60 60 -', '0.00 1.00 ? 0.60 60 -'),
    ('0.00 1.00 1.00 0.60 60 -', '0.00 1.00 1.00 60 -'),
    ('0.00 1.00 1.00 0.60 60 -', '0.00 1.00 1.00 0.60 60 ?'),
    ('Cuchara Normal HIDRAULICO 1.00 1.03 1 0 50R - - R', 'Cuchara Normal HIDRAULICO 1.00 1.03 1 0 50X - - R'),
    ('Cuchara Normal HIDRAULICO 1.00 1.03 1 0 50R - - R', 'Cuchara Normal HIDRAULICO 1.00 1.03 1 50R - - R'),
    ('H1 (0.00m-1.00m)', 'H1 (0.00m-?m)'),
    ('HASTA [m] PERFORADO [m]', 'HASTA [cm] PERFORADO [m]'),
    ('PERF. [PSI]', 'PERF. [MPa]'),
    ('LONG. (cm)', 'LONG. (m)'),
])
def test_malformed_numeric_rows_or_changed_units_fail_closed(before, after):
    pages = list(PAGES)
    pages[0] = pages[0].replace(before, after)
    # Global format signature remains present on the continuation sheet.
    hole = parse_cdi_report(pages).boreholes[0]
    assert hole.extraction_errors and hole.errors()


def test_conflicting_repeated_horizon_is_not_silently_replaced():
    pages = list(PAGES)
    pages[1] = pages[1].replace('1.00m-3.00m', '1.00m-3.50m')
    hole = parse_cdi_report(pages).boreholes[0]
    assert hole.horizons[1].end == '3.00'
    assert any('H2' in error and 'distintos' in error for error in hole.errors())


def test_published_nspt_discrepancy_is_preserved_not_recomputed():
    pages = [p.replace('7 9 5 14', '7 9 5 13') for p in PAGES]
    hole = parse_cdi_report(pages).boreholes[0]
    assert hole.tests[-1].nspt == '13'
    assert any('N2+N3' in warning for warning in hole.warnings)


@pytest.mark.skipif(not os.getenv('SINCAL_TEST_RUTA29_FOLDER'), reason='Local user PDFs are not committed')
@pytest.mark.parametrize('identifier,drilling_counts,spt_counts,last_depth', [
    (1, [5,10,11,2,5,5,2], [4,9,10,3,4,5,2], '40.00'),
    (2, [17,6,22,1,19,0,10,4], [0,11,0,12,0,9,5,2], '35.00'),
])
def test_real_cdi_reports(identifier, drilling_counts, spt_counts, last_depth):
    from pypdf import PdfReader
    source = Path(os.environ['SINCAL_TEST_RUTA29_FOLDER'])/f'ITS Enlace Ruta 29 S-{identifier} def.pdf'
    pages = [p.extract_text() for p in PdfReader(source).pages]
    report = parse_cdi_report(pages, str(source))
    hole = report.boreholes[0]
    assert not hole.errors()
    assert len(hole.horizons) == 15 and all(not h.thickness for h in hole.horizons)
    assert hole.horizons[-1].end == last_depth
    assert hole.drilling_records[-1].end == '40.00'
    assert [Counter(r.page for r in hole.drilling_records)[i] for i in range(1,len(pages))] == drilling_counts
    assert [Counter(r.page for r in hole.tests)[i] for i in range(1,len(pages))] == spt_counts
    assert len(report.pages) == len(pages)
    assert hole.study_info['company'] == 'CDI' and 'date' not in hole.study_info
    assert StratigraphyReport.from_dict(report.to_dict()).to_dict() == report.to_dict()
    if identifier == 1:
        assert [t.sample_number for t in hole.tests] == [str(n) for n in range(1,40) if n not in (14,25)]
        assert [t.nspt for t in hole.tests if not t.refusal] == ['72','68','66','42','14']
        assert any('leyenda indica 33.00–38.00' in w for w in hole.warnings)
    else:
        assert [t.sample_number for t in hole.tests[-7:]] == ['33','35','37','39','41','29','31']
        assert [t.nspt for t in hole.tests if not t.refusal] == ['14','66','63','63','59']
        assert next(t for t in hole.tests if t.start == '20.00').n1 == '59R'
        assert [r.start for r in hole.drilling_records if r.start == r.end] == ['20.00','24.00','34.00','38.00','39.00']
        assert next(r for r in hole.drilling_records if r.start == '31.24').pressure == ''
        assert next(t for t in hole.tests if t.start == '15.00').sample_length == '14'
        assert next(r for r in hole.drilling_records if r.start == '15.00').recovered == '0.07'
        assert any('no se extrapola el hatch' in w for w in hole.warnings)
        assert any('Pág. 4: la leyenda indica 12.00–23.00' in w for w in hole.warnings)
