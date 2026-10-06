"""Opt-in only: real CAD on disposable copies of repository fixtures."""
import os
from pathlib import Path
import shutil
import threading
import uuid
import time

import pytest

from sincal.cad.dwgprops import autocad_engines, process_file, fingerprint
from sincal.web.services import Services


class NativeJob:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.cancelled = threading.Event()

    def update(self, *args):
        pass


@pytest.mark.skipif(os.environ.get('SINCAL_TEST_NATIVE_DWGPROPS') != '1', reason='Explicit native CAD test opt-in required')
@pytest.mark.parametrize('year', [2025, 2027])
def test_native_individual_and_multiple_properties(tmp_path, year, monkeypatch):
    import sincal.cad.dwgprops as module
    launches = []
    original_popen = module.subprocess.Popen
    def tracked(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        launches.append(process)
        return process
    monkeypatch.setattr(module.subprocess, 'Popen', tracked)
    engine = next((e['id'] for e in autocad_engines() if e['year'] == year), None)
    if not engine:
        pytest.skip(f'AutoCAD {year} connector unavailable')
    drawings = tmp_path / 'drawings'
    drawings.mkdir()
    fixture = Path(__file__).resolve().parents[1] / 'masters/SINCAL_MARCA_DE_V1.dwg'
    before = fingerprint(fixture)
    for name in ('A ñ.dwg', 'B.dwg'):
        shutil.copy2(fixture, drawings / name)
    service = Services(tmp_path / 'state')
    try:
        grant = service.files.grant(drawings, 'folder')
        read = service.properties_read(NativeJob(), {'folder': grant['id'], 'engine': engine})
        assert len(read['files']) == 2 and all('error' not in f for f in read['files']), read
        assert len(launches) == 1 and launches[-1].poll() is not None
        ids = [row['id'] for row in read['files']]
        first = service.properties_write(NativeJob(), {'snapshot': read['snapshot'], 'ids': ids[:1],
            'changes': {'REVISIÓN': 'G', 'CONSERVAR': 'valor único'}, 'confirm': True})
        assert first['files'][0]['status'] == 'Guardado', first
        assert fingerprint(drawings / 'B.dwg') == before
        both = service.properties_write(NativeJob(), {'snapshot': read['snapshot'], 'ids': ids,
            'changes': {'REVISIÓN': 'H ñ', 'OT': '130', 'VACÍO': ''}, 'confirm': True})
        assert all(row['status'] == 'Guardado' for row in both['files']), both
        assert len(launches) == 3 and all(p.poll() is not None for p in launches)
        unchanged = service.properties_write(NativeJob(), {'snapshot': read['snapshot'], 'ids': ids,
            'changes': {'REVISIÓN': 'H ñ'}, 'confirm': True})
        assert all(row['status'] == 'Sin cambios' and 'backup' not in row for row in unchanged['files'])
        assert len(launches) == 3
        for row in both['files']:
            result = process_file(drawings / row['name'], tmp_path / uuid.uuid4().hex / 'verify', engine=engine)
            assert result['properties']['REVISIÓN'] == 'H ñ'
            assert result['properties']['VACÍO'] == ''
            assert Path(row['backup']).is_file()
            if row['name'].startswith('A'):
                assert result['properties']['CONSERVAR'] == 'valor único'
            else:
                assert 'CONSERVAR' not in result['properties']
        removed = service.properties_write(NativeJob(), {'snapshot': read['snapshot'], 'ids': ids[:1],
            'changes': {'OT': None}, 'confirm': True})
        assert removed['files'][0]['status'] == 'Guardado', removed
        assert 'OT' not in removed['files'][0]['properties']
        assert fingerprint(fixture) == before
        assert not list(drawings.glob('*.dwl')) and not list(drawings.glob('*.dwl2'))
    finally:
        service.jobs.close()


@pytest.mark.skipif(os.environ.get('SINCAL_TEST_NATIVE_DWGPROPS') != '1', reason='Explicit native CAD test opt-in required')
@pytest.mark.parametrize('year', [2025, 2027])
def test_native_batch_read_benchmark(tmp_path, year):
    from sincal.cad.dwgprops import CadBatch
    engine = next((e['id'] for e in autocad_engines() if e['year'] == year), None)
    if not engine:
        pytest.skip(f'AutoCAD {year} connector unavailable')
    fixture = Path(__file__).resolve().parents[1] / 'masters/SINCAL_MARCA_DE_V1.dwg'
    source_hash = fingerprint(fixture)
    drawings = []
    for i in range(4):
        drawing = tmp_path / f'{i}.dwg'
        shutil.copy2(fixture, drawing)
        drawings.append(drawing)
    started = time.perf_counter()
    old = [process_file(p, tmp_path / 'old' / str(i), engine=engine)['properties'] for i, p in enumerate(drawings)]
    old_seconds = time.perf_counter() - started
    batch = CadBatch(tmp_path / 'batch', engine)
    started = time.perf_counter()
    try:
        new = [process_file(p, tmp_path / 'batch' / str(i), worker=batch)['properties'] for i, p in enumerate(drawings)]
    finally:
        batch.close()
    new_seconds = time.perf_counter() - started
    assert new == old
    assert fingerprint(fixture) == source_hash
    assert all(fingerprint(p) == source_hash for p in drawings)
    assert batch.process.poll() is not None
    print(f'\nAutoCAD {year}, 4 DWG: per-file={old_seconds:.2f}s batch={new_seconds:.2f}s reduction={100*(1-new_seconds/old_seconds):.1f}%')
