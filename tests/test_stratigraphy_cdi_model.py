import copy
import json

import pytest

from sincal.stratigraphy import Borehole, DrillingRecord, Horizon, Interval, Spt, StratigraphyReport


def report():
    hole = Borehole('S-2-p1', 'S-2', method='cdi-text')
    hole.horizons = [Horizon(1, '0.00', '2.00', '', 'Arena', 1, 'arena')]
    hole.drilling_records = [DrillingRecord('0.00', '1.00', '1.00', '.80', '80', '-', 1),
                             DrillingRecord('1.45', '3.00', '1.55', '1.00', '65', '', 1)]
    hole.tests = [Spt(1, '1.00', '1.45', '', '', '7', '9', '5', '14', 1, 'cm', '29', '42', 'Cuchara', 'HIDRAULICO'),
                  Spt(2, '2.00', '2.00', '', '', '59R', '-', '-', 'R', 1, 'cm', '29', '0', 'Cuchara', 'HIDRAULICO')]
    hole.study_info = {'company': 'CDI', 'email': 'cdi@example.test'}
    return StratigraphyReport('fixture.txt', 'a'*64, [hole])


def test_cdi_independent_units_and_roundtrip():
    original = report()
    restored = StratigraphyReport.from_dict(json.loads(json.dumps(original.to_dict())))
    assert restored.to_dict() == original.to_dict()
    hole = restored.boreholes[0]
    assert hole.drawing_format == 'cdi-spt-v1'
    assert not hole.errors()
    assert hole.strata is hole.horizons and hole.recovery_rows is hole.drilling_records
    assert hole.tests[0].recovered == '' and hole.tests[0].sample_length == '42'
    assert [r.sample_number for r in hole.tests] == ['29', '29']
    assert any('no se extrapola' in w for w in hole.audit())
    assert any('no se rellena' in w.lower() for w in hole.audit())
    assert hole.horizons[0].thickness == ''
    assert hole.drilling_records[-1].pressure == ''


def test_cdi_requires_review_of_identified_format():
    hole = report().boreholes[0]
    hole.reviewed = True
    assert not hole.ready_to_insert
    hole.reviewed_format = 'visan-summary-v1'
    assert not hole.ready_to_insert
    hole.reviewed_format = 'cdi-spt-v1'
    assert hole.ready_to_insert


@pytest.mark.parametrize('field,value', [('sample_length', ''), ('sample_length', '-1'),
                                        ('sample_number', ''), ('recovered', '42'),
                                        ('recovered_unit', 'm'), ('n1', 'texto')])
def test_cdi_invalid_spt_semantics_are_blocked(field, value):
    hole = report().boreholes[0]
    setattr(hole.tests[0], field, value)
    assert hole.errors()


def test_cdi_mixed_formats_and_duplicate_tests_are_blocked():
    hole = report().boreholes[0]
    duplicate = copy.deepcopy(hole.tests[0])
    duplicate.index = 3
    hole.tests.append(duplicate)
    assert hole.errors()
    hole = report().boreholes[0]
    hole.intervals.append(Interval('0', '1', '1', '.8', '80', 'Arena', 1, 'arena'))
    assert hole.drawing_format == '' and hole.errors()


def test_cdi_zero_length_recovery_is_preserved_without_geometric_layer():
    original = report()
    hole = original.boreholes[0]
    hole.drilling_records.insert(1, DrillingRecord('1.00','1.00','0.00','0.00','0','-',1))
    assert not hole.errors()
    roundtrip = StratigraphyReport.from_dict(original.to_dict())
    assert roundtrip.boreholes[0].drilling_records[1].end == '1.00'


@pytest.mark.parametrize('metadata', [[], {'company': None}, {'company': 'x'*5001}])
def test_cdi_metadata_validation(metadata):
    value = report().to_dict()
    value['boreholes'][0]['study_info'] = metadata
    with pytest.raises(ValueError, match='Información'):
        StratigraphyReport.from_dict(value)
