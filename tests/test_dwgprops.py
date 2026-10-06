import json
from pathlib import Path

import pytest

from sincal.cad.dwgprops import changeset, patched, process_file, fingerprint
from sincal.web.services import Services


def test_patch_preserves_unselected_and_supports_empty_delete():
    original = {'REV': 'A', 'FECHA': 'ayer', 'ESTRUCTURA': 'Puente'}
    assert patched(original, {'rev': 'B', 'FECHA': None, 'NOTA': ''}) == {
        'REV': 'B', 'ESTRUCTURA': 'Puente', 'NOTA': ''}
    assert original['REV'] == 'A'


@pytest.mark.parametrize('data', [{}, {'': 'a'}, {'A': 1}, {'A': '1', 'a': '2'}, {' A': 'x'}, {'A': 'x'*4097}])
def test_reject_invalid_changes(data):
    with pytest.raises(ValueError):
        changeset(data)


def fake_worker(path, changes, folder):
    props = json.loads(path.read_text())
    if changes is not None:
        props = patched(props, changes)
        path.write_text(json.dumps(props))
    return props


def test_copy_on_write_backup_and_read_only(tmp_path):
    drawing = tmp_path / 'Plano ñ.dwg'
    drawing.write_text('{"REV":"A","KEEP":"yes"}')
    before = drawing.read_bytes()
    read = process_file(drawing, tmp_path / 'runtime' / 'read' / 'one', worker=fake_worker)
    assert drawing.read_bytes() == before
    result = process_file(drawing, tmp_path / 'runtime' / 'write' / 'one', {'REV': 'B'}, read['fingerprint'], fake_worker)
    assert json.loads(drawing.read_text()) == {'REV': 'B', 'KEEP': 'yes'}
    assert Path(result['backup']).read_bytes() == before


def test_external_change_and_worker_failure_never_replace(tmp_path):
    drawing = tmp_path / 'a.dwg'
    drawing.write_text('{}')
    old = fingerprint(drawing)
    drawing.write_text('{"NEW":"data"}')
    with pytest.raises(ValueError, match='cambió'):
        process_file(drawing, tmp_path / 'job' / 'one', {'X': 'y'}, old, fake_worker)
    def failure(path, changes, folder):
        path.write_text('bad copy')
        raise RuntimeError('CAD failed')
    with pytest.raises(RuntimeError):
        process_file(drawing, tmp_path / 'job' / 'two', {'X': 'y'}, worker=failure)
    assert json.loads(drawing.read_text()) == {'NEW': 'data'}


def test_change_during_processing_is_not_overwritten(tmp_path):
    drawing = tmp_path / 'a.dwg'
    drawing.write_text('{}')
    def changed(path, changes, folder):
        drawing.write_text('{"external":"change"}')
        return fake_worker(path, changes, folder)
    with pytest.raises(ValueError, match='cambió'):
        process_file(drawing, tmp_path / 'job' / 'one', {'X': 'y'}, worker=changed)
    assert json.loads(drawing.read_text()) == {'external': 'change'}


def test_locked_drawing_not_processed(tmp_path):
    drawing = tmp_path / 'a.dwg'
    drawing.write_text('{}')
    drawing.with_suffix('.dwl').touch()
    with pytest.raises(ValueError, match='bloqueo'):
        process_file(drawing, tmp_path / 'job' / 'one', worker=fake_worker)


def test_unchanged_skips_cad_backup_and_rewrite(tmp_path):
    drawing = tmp_path / 'a.dwg'
    drawing.write_text('{"REV":"A"}')
    before = drawing.stat().st_mtime_ns
    def unexpected(*args):
        pytest.fail('CAD must not start for unchanged properties')
    result = process_file(drawing, tmp_path / 'job' / 'one', {'rev': 'A', 'ABSENT': None},
                          fingerprint(drawing), unexpected, known_properties={'REV': 'A'})
    assert result['unchanged'] and 'backup' not in result
    assert drawing.stat().st_mtime_ns == before
    assert not (tmp_path / 'job').exists()
    assert not (tmp_path / 'SINCAL_Backups').exists()


def test_unchanged_still_rejects_stale_snapshot(tmp_path):
    drawing = tmp_path / 'a.dwg'
    drawing.write_text('{"REV":"A"}')
    old = fingerprint(drawing)
    drawing.write_text('{"REV":"B"}')
    with pytest.raises(ValueError, match='cambió'):
        process_file(drawing, tmp_path / 'job' / 'one', {'REV': 'A'}, old,
                     known_properties={'REV': 'A'})


def test_batch_does_not_start_until_needed_and_rejects_outside_copy(tmp_path):
    from sincal.cad.dwgprops import CadBatch, CadUnavailable
    batch = CadBatch(tmp_path / 'job')
    with pytest.raises(ValueError, match='carpeta temporal'):
        batch(tmp_path / 'outside.dwg', None, tmp_path)
    assert batch.process is None
    batch.close()
    batch.close()
    with pytest.raises(CadUnavailable):
        batch(tmp_path / 'job' / 'one' / 'a.dwg', None, tmp_path / 'job' / 'one')


class Job:
    id = 'test-job'
    from threading import Event
    cancelled = Event()
    def update(self, *args):
        pass


def test_timeout_stops_read_batch(tmp_path, monkeypatch):
    import sincal.cad.dwgprops as module
    calls = []
    def unavailable(*args, **kwargs):
        calls.append(args)
        raise module.CadUnavailable('timeout')
    monkeypatch.setattr(module, 'process_file', unavailable)
    folder = tmp_path / 'drawings'
    folder.mkdir()
    for name in ['a.dwg', 'b.dwg']:
        (folder / name).write_text('{}')
    services = Services(tmp_path / 'state')
    try:
        grant = services.files.grant(folder, 'folder')
        result = services.properties_read(Job(), {'folder': grant['id']})
        assert len(calls) == 1
        assert len(result['files']) == 2
        assert all('error' in row for row in result['files'])
    finally:
        services.jobs.close()


def test_service_writes_only_selected_and_requires_confirmation(tmp_path, monkeypatch):
    import sincal.cad.dwgprops as module
    real = module.process_file
    def mocked(*args, **kwargs):
        kwargs['worker'] = fake_worker
        return real(*args, **kwargs)
    monkeypatch.setattr(module, 'process_file', mocked)
    folder = tmp_path / 'drawings'
    folder.mkdir()
    for name in ['a.dwg', 'b.dwg']:
        (folder / name).write_text('{"REV":"A"}')
    services = Services(tmp_path / 'state')
    try:
        grant = services.files.grant(folder, 'folder')
        data = services.properties_read(Job(), {'folder': grant['id']})
        assert len(data['files']) == 2
        payload = {'snapshot': data['snapshot'], 'ids': [data['files'][0]['id']], 'changes': {'REV': 'B'}}
        with pytest.raises(ValueError, match='Confirma'):
            services.properties_write(Job(), payload)
        payload['confirm'] = True
        result = services.properties_write(Job(), payload)
        assert result['files'][0]['status'] == 'Guardado'
        assert json.loads((folder / 'a.dwg').read_text())['REV'] == 'B'
        assert json.loads((folder / 'b.dwg').read_text())['REV'] == 'A'
    finally:
        services.jobs.close()


@pytest.mark.parametrize('outcome', ['cancel', 'file-error', 'cad-error'])
def test_batch_lifecycle_on_cancel_and_errors(tmp_path, monkeypatch, outcome):
    import threading
    from types import SimpleNamespace
    import sincal.cad.dwgprops as module
    instances, calls = [], []
    class Batch:
        def __init__(self, *args):
            self.closed = False
            instances.append(self)
        def close(self):
            self.closed = True
    job = SimpleNamespace(id='job', cancelled=threading.Event(), update=lambda *args: None)
    def process(path, directory, **kwargs):
        assert kwargs['worker'] is instances[0]
        calls.append(path)
        if len(calls) == 1:
            if outcome == 'cancel':
                job.cancelled.set()
            elif outcome == 'file-error':
                raise RuntimeError('invalid drawing')
            else:
                raise module.CadUnavailable('timeout')
        return {'properties': {}, 'fingerprint': 'hash'}
    monkeypatch.setattr(module, 'CadBatch', Batch)
    monkeypatch.setattr(module, 'process_file', process)
    folder = tmp_path / 'drawings'
    folder.mkdir()
    for name in ['a.dwg', 'b.dwg']:
        (folder / name).write_text('{}')
    services = Services(tmp_path / 'state')
    try:
        grant = services.files.grant(folder, 'folder')
        result = services.properties_read(job, {'folder': grant['id']})
        assert len(instances) == 1 and instances[0].closed
        assert len(calls) == (2 if outcome == 'file-error' else 1)
        assert result['cancelled'] == (outcome == 'cancel')
        assert not services.cad_lock.locked()
    finally:
        services.jobs.close()
