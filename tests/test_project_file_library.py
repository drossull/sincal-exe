import pytest
from unittest.mock import Mock, patch

from sincal.web.files import Files
from sincal.web.services import Services


@pytest.mark.parametrize('kind,name', [('memory_pdf', 'Memoria.pdf'), ('memory_excel', 'Memoria.xlsx'), ('memory_excel', 'Memoria.xlsm')])
def test_calculation_memories_are_references_only(tmp_path, kind, name):
    source = tmp_path / name
    source.write_bytes(b'unparsed reference')
    files = Files()
    files.picker = lambda _: [source]
    grant = files.choose(kind)[0]
    assert files.get(grant['id'], kind) == source
    assert source.read_bytes() == b'unparsed reference'
    with pytest.raises(ValueError):
        files.get(grant['id'], 'dwg')


def test_reference_grants_are_not_cad_inputs(tmp_path):
    document = tmp_path / 'Memoria.docx'
    document.write_bytes(b'reference')
    files = Files()
    files.picker = lambda kind: [document]
    grant = files.choose('reference')[0]
    assert files.get(grant['id'], 'reference') == document
    with pytest.raises(ValueError):
        files.get(grant['id'], 'dwg')
    with pytest.raises(ValueError):
        files.grant(document, 'report')
    assert document.read_bytes() == b'reference'


def test_project_picker_grants_each_report(tmp_path):
    paths = [tmp_path / 'IMS.pdf', tmp_path / 'Vs.pdf']
    for p in paths:
        p.write_bytes(b'%PDF')
    files = Files()
    files.picker = lambda kind: paths
    grants = files.choose('report')
    assert [files.get(g['id'], 'report') for g in grants] == paths


def test_properties_reads_only_explicit_project_files(tmp_path):
    service = Services(tmp_path / 'state')
    selected = tmp_path / 'selected.dwg'
    selected.write_bytes(b'dwg')
    (tmp_path / 'not-selected.dwg').write_bytes(b'untouched')
    grant = service.files.grant(selected, 'dwg')
    job = Mock(id='test')
    job.cancelled.is_set.return_value = False
    try:
        with patch('sincal.cad.dwgprops.CadBatch'), patch('sincal.cad.dwgprops.process_file', return_value={'properties': {}}) as process:
            result = service.properties_read(job, {'files': [grant['id'], grant['id']]})
            assert len(result['files']) == 1
            assert process.call_count == 1
            assert process.call_args.args[0] == selected
        with pytest.raises(ValueError):
            service.properties_read(job, {'files': [str(selected)]})
        with pytest.raises(ValueError):
            service.properties_read(job, {'files': [grant['id']], 'folder': 'conflict'})
    finally:
        service.jobs.close()
