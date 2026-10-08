from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sincal.prospecciones import VsLayer, VsProfile
from sincal.stratigraphy import Borehole, StratigraphyReport
from sincal.stratigraphy_vs import attach_vs_bands, match_profile


def profile():
    return VsProfile('p2', 'Arreglo 3-2', 2, [
        VsLayer(1, '0,00', '1,49', '185,69'),
        VsLayer(2, '1,49', '2,10', '608,87'),
        VsLayer(3, '2,10', '3,59', '676,58'),
    ])


def labels():
    return [dict(start=.003, end=1.494, low='185', high='185'),
            dict(start=1.494, end=3.585, low='608', high='676')]


def test_exact_table_depths_and_printed_vs_are_not_recalculated():
    source = labels()
    result = match_profile(source, profile())
    assert [(a, b) for a, b, _ in result] == [('0,00', '1,49'), ('1,49', '3,59')]
    assert source[1]['high'] == '676'
    assert match_profile([], profile()) is None
    source[1]['end'] = 4.0
    assert match_profile(source, profile()) is None
    source = labels()
    source[0]['low'] = '200'
    assert match_profile(source, profile()) is None


@pytest.mark.parametrize('mode', ['unique', 'ambiguous', 'missing', 'uncalibrated'])
def test_figure_association_is_fail_closed(monkeypatch, mode):
    pages = ['Estratigrafía S-40 Vs = 185 m/s', 'Official table']
    report = StratigraphyReport('fixture.pdf', 'sha', [Borehole('s40', 'S-40')])
    profiles = [profile()] if mode != 'missing' else []
    if mode == 'ambiguous':
        profiles.append(profile())
    monkeypatch.setattr('sincal.stratigraphy_vs.parse_pages', lambda *a, **k: SimpleNamespace(profiles=profiles))
    failure = 'No se pudo calibrar el eje.' if mode == 'uncalibrated' else ''
    monkeypatch.setattr('sincal.stratigraphy_vs.figure_panels', lambda *a: [('S-40', labels(), failure)])
    pdf = MagicMock()
    pdf.__enter__.return_value.pages = [object(), object()]
    monkeypatch.setattr('pdfplumber.open', lambda *a: pdf)
    attach_vs_bands(report, b'fixture', pages)
    hole = report.boreholes[0]
    if mode == 'unique':
        assert [(v.start, v.end, v.low, v.high) for v in hole.vs_bands] == [
            ('0,00', '1,49', '185', '185'), ('1,49', '3,59', '608', '676')]
        assert set(report.pages) == {'1', '2'}
        assert not hole.extraction_errors
    else:
        assert not hole.vs_bands
        assert hole.extraction_errors
