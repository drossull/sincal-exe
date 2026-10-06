import os
from pathlib import Path
import shutil
import threading
import uuid

import pytest

from sincal.web.revisions import revision_values
from sincal.web.services import Services
from sincal.cad.dwgprops import fingerprint, autocad_engines


@pytest.mark.parametrize('value', [None, [], ['A']*5, ['']*6, ['a'*251]*6, ['%<field>%']*6, ['a\nb']*6, [1]*6])
def test_invalid_revision(value):
    with pytest.raises(ValueError):
        revision_values(value)


def test_manual_revision():
    assert revision_values([' H ', '05/10/26', 'GM', 'AR', 'GS', 'Revisión']) == ['H','05/10/26','GM','AR','GS','Revisión']


class Job:
    def __init__(self):
        self.id=uuid.uuid4().hex
        self.cancelled=threading.Event()
    def update(self,*args):
        pass


def test_unconfirmed_revision_rejected(tmp_path):
    service=Services(tmp_path)
    try:
        with pytest.raises(ValueError,match='Confirma'):
            service.revisions_write(Job(),{})
        with pytest.raises(ValueError,match='Selecciona'):
            service.revisions_read(Job(),{'files':[]})
    finally:
        service.jobs.close()


@pytest.mark.skipif(not os.environ.get('SINCAL_TEST_REVISION_DWG'),reason='Requires explicit example DWG; tests modify temporary copies only')
@pytest.mark.parametrize('year',[2025,2027])
def test_native_revision_on_temporary_copies(tmp_path,year):
    source=Path(os.environ['SINCAL_TEST_REVISION_DWG'])
    source_hash=fingerprint(source)
    engine=next((e['id'] for e in autocad_engines() if e['year']==year),None)
    if engine is None:
        pytest.skip('Engine unavailable')
    drawings=tmp_path/'drawings';drawings.mkdir()
    service=Services(tmp_path/'state')
    try:
        grants=[]
        for name in ['A.dwg','B.dwg']:
            target=drawings/name;shutil.copy2(source,target);grants.append(service.files.grant(target,'dwg')['id'])
        read=service.revisions_read(Job(),{'files':grants,'engine':engine})
        assert len(read['files'])==2 and all('error' not in row for row in read['files']),read
        ids=[row['id'] for row in read['files']]
        values=['Z','05/10/26','T.D.','T.R.','T.A.','ENSAYO TEMPORAL']
        payload={'snapshot':read['snapshot'],'ids':ids,'values':values,'confirm':True}
        written=service.revisions_write(Job(),payload)
        assert all('error' not in row for row in written['files']),written
        for before,after in zip(read['files'],written['files']):
            old,new=before['revision'],after['revision']
            assert new['rows']==[values]+old['rows'][:-1]
            assert new['fields']==old['fields']
            assert new['geometry']==old['geometry']
            assert after['archived']==old['rows'][-1]
            assert fingerprint(Path(after['backup']))==source_hash
        hashes=[fingerprint(drawings/name) for name in ['A.dwg','B.dwg']]
        repeated=service.revisions_write(Job(),payload)
        assert all('coincide' in r['error'] for r in repeated['files'])
        assert hashes==[fingerprint(drawings/name) for name in ['A.dwg','B.dwg']]
        too_long=service.revisions_write(Job(),{**payload,'ids':ids[:1],
            'values':['REVISION-QUE-NO-CABE','05/10/26','TD','TR','TA','ENSAYO']})
        assert 'no caben' in too_long['files'][0]['error'],too_long
        assert hashes==[fingerprint(drawings/name) for name in ['A.dwg','B.dwg']]
        reopened=service.revisions_read(Job(),{'files':grants,'engine':engine})
        assert all(r['revision']['rows'][0]==values for r in reopened['files']),reopened
        next_values=['Y',*values[1:]]
        second=service.revisions_write(Job(),{**payload,'ids':ids[:1],'values':next_values})
        assert 'error' not in second['files'][0],second
        assert second['files'][0]['revision']['rows'][0]==next_values
        assert second['files'][0]['revision']['rows'][1]==values
        assert fingerprint(drawings/'B.dwg')==hashes[1]
        assert fingerprint(source)==source_hash
        assert not list(drawings.glob('*.dwl*'))
    finally:
        service.jobs.close()
