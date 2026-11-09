"""Repair must consume only the connector's verified copy, never its input."""
import json
import os
from pathlib import Path
import shutil

import pytest

from sincal.cad import dwgprops


@pytest.mark.parametrize('outcome', ['verified', 'rejected', 'missing'])
def test_field_repair_accepts_only_verified_output(tmp_path, monkeypatch, outcome):
    root = tmp_path / 'worker'
    folder = root / 'request'
    folder.mkdir(parents=True)
    drawing = folder / 'copy.dwg'
    drawing.write_bytes(b'original copy')
    worker = dwgprops.CadBatch(root)
    worker.request_options = {'revisionFieldRepairTables': ['5CDFB']}
    # No CAD process: emulate its response after the inbox was written.
    worker.process = object()

    def complete(marker):
        request = json.loads((folder / 'request.json').read_text())
        assert request['changes'] is None
        assert request['revisionFieldRepairTables'] == ['5CDFB']
        if outcome == 'verified':
            Path(request['saved']).write_bytes(b'verified repair')
        Path(request['output']).write_text(json.dumps({
            'ok': outcome != 'rejected', 'properties': {'Revision': 'H'},
            'error': 'The saved Fields did not preserve the drawing',
        }))

    monkeypatch.setattr(worker, '_wait', complete)
    if outcome == 'verified':
        assert worker(drawing, None, folder) == {'Revision': 'H'}
        assert drawing.read_bytes() == b'verified repair'
    else:
        with pytest.raises(RuntimeError):
            worker(drawing, None, folder)
        assert drawing.read_bytes() == b'original copy'


@pytest.mark.skipif(not os.environ.get('SINCAL_TEST_FIELD_DWG'),
                    reason='Requires an explicitly supplied DWG; modifies temporary copies only')
@pytest.mark.parametrize('year', [2025, 2026, 2027])
def test_native_field_repair_preserves_original_and_rejects_invalid_target(tmp_path, monkeypatch, year):
    source = Path(os.environ['SINCAL_TEST_FIELD_DWG'])
    table = os.environ['SINCAL_TEST_FIELD_TABLE']
    before = dwgprops.fingerprint(source)
    if connector_root := os.environ.get('SINCAL_TEST_CONNECTOR_ROOT'):
        monkeypatch.setattr(dwgprops, 'connector_path',
                            lambda version: Path(connector_root) / f'bin{version}' / 'Sincal.DwgProps.dll')
    engine = next((item['id'] for item in dwgprops.autocad_engines() if item['year'] == year), None)
    if engine is None:
        pytest.skip('Compatible connector/engine unavailable')
    folder = tmp_path / 'worker' / 'request'
    folder.mkdir(parents=True)
    drawing = folder / 'copy.dwg'
    shutil.copy2(source, drawing)
    worker = dwgprops.CadBatch(folder.parent, engine=engine)
    try:
        worker.request_options = {'revisionFieldRepairTables': [table]}
        properties = worker(drawing, None, folder)
        assert worker.result['ok']
        # The native connector checks reopened Fields, history, geometry,
        # viewports, properties, DWG version and entity inventory before success.
        repaired = dwgprops.fingerprint(drawing)
        invalid = folder.parent / 'invalid'
        invalid.mkdir()
        invalid_copy = invalid / 'copy.dwg'
        shutil.copy2(drawing, invalid_copy)
        worker.request_options = {'revisionFieldRepairTables': ['FFFFFFFFFFFFFF']}
        with pytest.raises(RuntimeError):
            worker(invalid_copy, None, invalid)
        assert dwgprops.fingerprint(invalid_copy) == repaired
        assert properties['Revision']
    finally:
        worker.close()
    assert dwgprops.fingerprint(source) == before
