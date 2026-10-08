import copy
import os
from pathlib import Path
import shutil
import threading
import uuid

import pytest

from sincal.cad.dwgprops import autocad_engines, fingerprint
from sincal.web.revision_editor import edits
from sincal.web.services import Services


class Job:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.cancelled = threading.Event()

    def update(self, *args):
        pass


def snapshot():
    return {'tables': [{'id': 'T', 'cells': [[
        {'text': 'H', 'editable': True, 'property': 'Revision'},
        {'text': 'OTHER', 'editable': False, 'property': None},
        {'text': 'H', 'editable': True, 'property': 'Revision'},
    ]]}]}


def patch(**kwargs):
    return dict(table='T', row=0, column=0, value='J', **kwargs)


@pytest.mark.parametrize('changes', [None, [], [dict(table='T', row=True, column=0, value='J')],
    [dict(table='X', row=0, column=0, value='J')],
    [dict(table='T', row=0, column=1, value='J')],
    [dict(table='T', row=0, column=0, value='%<field>%')],
    [dict(table='T', row=0, column=0, value='x'*251)],
    [patch(), patch()], [patch(), dict(table='T', row=0, column=2, value='K')]])
def test_reject_invalid_edits(changes):
    with pytest.raises(ValueError):
        edits(changes, snapshot())


def test_validate_edits():
    assert edits([patch()], snapshot()) == [patch()]
    assert edits([dict(table='T', row=0, column=0, value='')], snapshot())[0]['value'] == ''


def test_editor_requires_confirmation_and_file_grants(tmp_path):
    service = Services(tmp_path)
    try:
        with pytest.raises(ValueError, match='Confirma'):
            service.revision_editor_write(Job(), {})
        with pytest.raises(ValueError):
            service.revision_editor_read(Job(), {'files': []})
        with pytest.raises((ValueError, KeyError)):
            service.revision_editor_read(Job(), {'folder': str(tmp_path)})
    finally:
        service.jobs.close()


@pytest.mark.skipif(not os.environ.get('SINCAL_TEST_EDITOR_FOLDER'), reason='Explicit native examples required; modifies copies only')
@pytest.mark.parametrize('year', [2025, 2027])
def test_native_editor_preserves_fields_and_history(tmp_path, year):
    folder = Path(os.environ['SINCAL_TEST_EDITOR_FOLDER'])
    sources = [folder / f'ROS-B-ES-V05T17-{kind}-PIBAR-01-G.dwg' for kind in ('DD', 'PG')]
    hashes = [fingerprint(p) for p in sources]
    engine = next((e['id'] for e in autocad_engines() if e['year'] == year), None)
    if engine is None:
        pytest.skip('Engine unavailable')
    drawings = tmp_path / 'drawings'
    drawings.mkdir()
    service = Services(tmp_path / 'state')
    try:
        for source in sources:
            shutil.copy2(source, drawings / source.name)
        folder_id = service.files.grant(drawings, 'folder')['id']
        read = service.revision_editor_read(Job(), {'folder': folder_id, 'engine': engine})
        assert len(read['files']) == 2 and all('error' not in r for r in read['files']), read
        requests = []
        for row in read['files']:
            table = row['editor']['tables'][0]
            changes = [dict(table=table['id'], row=r, column=c, value=v) for r,c,v in
                       [(0,0,'Z'), (0,2,'T.D.'), (0,3,'T.R.'), (1,5,'ENSAYO TEMPORAL')]]
            requests.append({'id': row['id'], 'changes': changes})
        written = service.revision_editor_write(Job(), {'snapshot': read['snapshot'], 'files': requests, 'confirm': True})
        assert len(written['files']) == 2 and all('error' not in r for r in written['files']), written
        for before, after, request, source_hash in zip(read['files'], written['files'], requests, hashes):
            assert after['editor']['integrity'] == before['editor']['integrity']
            expected = copy.deepcopy(before['editor']['tables'])
            for change in request['changes']:
                expected[0]['cells'][change['row']][change['column']]['text'] = change['value']
            assert after['editor']['tables'] == expected
            assert fingerprint(Path(after['backup'])) == source_hash
        reopened = service.revision_editor_read(Job(), {'folder': folder_id, 'engine': engine})
        assert [r['editor'] for r in reopened['files']] == [r['editor'] for r in written['files']]
        table = written['files'][0]['editor']['tables'][0]
        before_hash = fingerprint(drawings / sources[0].name)
        oversized = service.revision_editor_write(Job(), {'snapshot': read['snapshot'], 'confirm': True,
            'files': [{'id': requests[0]['id'], 'changes': [dict(table=table['id'], row=1, column=0, value='X'*250)]}]})
        assert 'error' in oversized['files'][0], oversized
        assert fingerprint(drawings / sources[0].name) == before_hash
        # A second operation affecting only history must not destroy any Fields.
        history = service.revision_editor_write(Job(), {'snapshot': read['snapshot'], 'confirm': True,
            'files': [{'id': requests[0]['id'], 'changes': [dict(table=table['id'], row=2, column=5, value='HISTORIAL')]}]})
        assert 'error' not in history['files'][0], history
        assert history['files'][0]['editor']['integrity'] == written['files'][0]['editor']['integrity']
        assert history['files'][0]['editor']['tables'][0]['cells'][0] == table['cells'][0]
        # An external change after preview invalidates the old snapshot.
        target = drawings / sources[0].name
        shutil.copy2(sources[0], target)
        stale = service.revision_editor_write(Job(), {'snapshot': read['snapshot'], 'files': requests[:1], 'confirm': True})
        assert 'cambió' in stale['files'][0]['error']
        assert fingerprint(target) == hashes[0]
        assert [fingerprint(p) for p in sources] == hashes
    finally:
        service.jobs.close()
