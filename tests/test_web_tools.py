from dataclasses import asdict
import json
import os
import time
from unittest.mock import Mock, patch

import pytest

from sincal.web.files import Files, rename_plan, apply_rename
from sincal.web.jobs import Jobs
from sincal.web.services import Services
from sincal.web.session_import import normalize_session
from sincal.web.rebar import from_project, defaults, validate_draft
from sincal.web.server import Store
from sincal.web.cad_worker import execute, execute_all
from sincal.cad.crossbeam import build_crossbeam_lisp, build_crossbeam_detail_lisp
from sincal.prospecciones import VsReport, VsProfile, VsLayer


def wait(jobs, key):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = jobs.get(key).snapshot()
        if snapshot['state'] not in ('queued', 'running'):
            return snapshot
        time.sleep(.01)
    pytest.fail('Job did not finish')


def test_native_grants_and_no_arbitrary_paths(tmp_path):
    files = Files()
    with pytest.raises(ValueError):
        files.choose('folder')
    with pytest.raises(ValueError):
        files.get(str(tmp_path), 'folder')
    grant = files.grant(tmp_path, 'folder')
    assert files.get(grant['id'], 'folder') == tmp_path
    with pytest.raises(ValueError):
        files.get(grant['id'], 'report')
    files.picker = lambda kind: [tmp_path]
    assert len(files.choose('folder')) == 1


def test_rename_preview_revalidation_and_nonrecursive(tmp_path):
    (tmp_path/'old.dwg').write_bytes(b'DWG')
    (tmp_path/'nested').mkdir()
    (tmp_path/'nested'/'old.dwg').write_bytes(b'untouched')
    plan = rename_plan(tmp_path, 'old', 'new')
    assert len(plan) == 1
    assert apply_rename(tmp_path, plan, Mock())['renamed'] == 1
    assert (tmp_path/'new.dwg').read_bytes() == b'DWG'
    assert (tmp_path/'nested'/'old.dwg').exists()
    plan = rename_plan(tmp_path, 'new', 'other')
    (tmp_path/'new.dwg').write_bytes(b'changed')
    with pytest.raises(ValueError):
        apply_rename(tmp_path, plan, Mock())
    (tmp_path/'other.dwg').write_bytes(b'exists')
    with pytest.raises(ValueError):
        rename_plan(tmp_path, 'new', 'other')
    with pytest.raises(ValueError):
        rename_plan(tmp_path, 'new', '../elsewhere')


def test_job_logs_survive_restart_and_retention_excludes_other_files(tmp_path):
    jobs = Jobs(tmp_path)
    key = jobs.submit('test', lambda job: {'ok': True})['id']
    assert wait(jobs, key)['state'] == 'completed'
    assert jobs.history()[0]['state'] == 'completed'
    jobs.close()
    other = tmp_path/'user.jsonl'
    other.write_text('keep')
    stale = tmp_path/('a'*32+'.jsonl')
    stale.write_text('{}')
    os.utime(stale, (0, 0))
    reopened = Jobs(tmp_path)
    try:
        assert not stale.exists() and other.exists()
        assert reopened.logfile(key).exists()
        assert reopened.history()[0]['id'] == key
        with pytest.raises(ValueError):
            reopened.logfile('../user')
    finally:
        reopened.close()


def test_failed_job_records_error(tmp_path):
    jobs = Jobs(tmp_path)
    try:
        key = jobs.submit('bad', lambda job: (_ for _ in ()).throw(ValueError('test failure')))['id']
        assert wait(jobs, key)['state'] == 'failed'
        assert 'test failure' in jobs.logfile(key).read_text()
    finally:
        jobs.close()


def test_geometry_import_mm_to_cm_and_missing_not_invented():
    states = from_project({'estribos': {'dado_muro_frontal_largo_entrada': 9000},
                           'parametros_generales': {'angulo_esviaje_puente': 20}})
    assert states['entrada']['geometry']['largo_cm'] == 900
    assert states['salida']['geometry']['largo_cm'] is None
    validate_draft(states['salida'])


def test_legacy_import_preserves_source_without_trusting_handles():
    document = {'schema_version': 1, 'source_json': {'snapshot': {}}, 'project': {'ot':'T'},
                'workspace': {'skew':'5', 'abutments': {'entrada': {
                    'entries': {'largo':'900', 'ancho':'1200', 'alto':'200', 'rec_inf':'7,5', 'rec_sup':'5', 'rec_lat':'5'},
                    'moldaje_references': {'FR_ZAP': {'handle':'bad'}},
                    'rules': {'mesh_x': {'diameter':'22', 'spacing':'20', 'hook':'110', 'origin':'Final', 'enabled':True}}
                }}}}
    result = normalize_session(document)
    assert result['legacy_snapshot'] == document
    state = result['rebar']['entrada']
    assert state['rules'][0]['hook_cm'] == 110
    assert state['rules'][0]['origin'] == 'final'
    assert 'moldaje_references' not in state
    validate_draft(state)


def test_preferences_persist_and_reject_unknown_keys(tmp_path):
    store = Store(tmp_path/'sessions.db')
    store.preferences({'palette':'nord', 'theme':'light', 'zoom':'115'})
    assert Store(tmp_path/'sessions.db').preferences()['palette'] == 'nord'
    with pytest.raises(ValueError):
        store.preferences({'shell':'anything'})
    with pytest.raises(ValueError):
        store.preferences({'last_session':'not-found'})


def test_cad_worker_rejects_changed_document_without_sending(tmp_path):
    app = Mock()
    app.HWND = 42
    app.ActiveDocument.Name = 'other.dwg'
    app.ActiveDocument.FullName = 'C:/other.dwg'
    with patch('sincal.web.cad_worker.active_application', return_value=app):
        with pytest.raises(ValueError, match='Cambió'):
            execute({'expected':{'instance':'42','active':{'name':'test.dwg','path':'C:/test.dwg'}}})
    app.ActiveDocument.SendCommand.assert_not_called()


def test_cad_worker_does_not_retry_uncertain_send(tmp_path):
    app = Mock()
    app.HWND = 42
    doc = app.ActiveDocument
    doc.Name = 'test.dwg'
    doc.FullName = 'C:/test.dwg'
    doc.GetVariable.return_value = 0
    doc.SendCommand.side_effect = RuntimeError('COM accepted then failed')
    with patch('sincal.web.cad_worker.active_application', return_value=app):
        with pytest.raises(RuntimeError, match='No se reenvió'):
            execute({'expected':{'instance':'42','active':{'name':doc.Name,'path':doc.FullName}},
                     'marker':str(tmp_path/'done'), 'token':'abc', 'command':'ZE\n'})
    assert doc.SendCommand.call_count == 1
    doc.Save.assert_not_called()
    app.Quit.assert_not_called()


@pytest.mark.parametrize('quadrant', ['EXT_IZQ', 'EXT_DER', 'INT_TOPE', 'INT_MACIZO', 'INT_VIGA'])
def test_shared_crossbeam_generators(quadrant):
    args = (quadrant, 2.5, 25, 0, 22, 12, 12, 200)
    assert '(defun c:SINCAL-TRAVESANO' in build_crossbeam_lisp(*args)
    assert '(defun c:SINCAL-DESPIECE-TRAV' in build_crossbeam_detail_lisp(*args, 1)


def test_profile_checks_and_local_kml(tmp_path):
    services = Services(tmp_path)
    try:
        report = VsReport('test.txt', 'abc', [VsProfile('A','A',1,[VsLayer(1,'0','30','300')], '300')])
        assert services.describe_report(report)['checks'][0]['errors'] == []
        path = tmp_path/'test.kml'
        path.write_text('<kml><Placemark><name>Demo</name><Point><coordinates>-70,-33,0</coordinates></Point></Placemark></kml>')
        grant = services.files.grant(path, 'location')
        assert services.location(Mock(), {'file': grant['id']})['points']['Demo'] == (-33, -70)
        with pytest.raises(ValueError):
            services.operation('shell', {})
    finally:
        services.jobs.close()


def test_palette_accent_contrast():
    from sincal.web.palettes import FAMILIES, readable_accent, contrast
    for palette in FAMILIES.values():
        for mode in ('light', 'dark'):
            bg, fg = palette[mode]
            assert contrast(readable_accent(palette['primary'], bg, fg), bg) >= 4.5


def test_recovery_is_separate_from_saved_sessions(tmp_path):
    store = Store(tmp_path/'sessions.db')
    payload = {'data': {}, 'identification': {}}
    store.recover('a'*32, payload)
    assert store.recover()['payload'] == payload
    assert store.list() == []
    store.recover('a'*32)
    assert store.recover() is None


def test_all_documents_run_sequentially_and_stop_on_failure(tmp_path):
    app = Mock()
    app.HWND = 42
    docs = []
    for name in ('one.dwg', 'two.dwg', 'three.dwg'):
        doc = Mock()
        doc.Name, doc.FullName = name, 'C:/'+name
        doc.GetVariable.return_value = 0
        doc.Activate.side_effect = lambda doc=doc: setattr(app, 'ActiveDocument', doc)
        docs.append(doc)
    app.ActiveDocument = docs[0]
    app.Documents.Count = len(docs)
    app.Documents.Item.side_effect = lambda index: docs[index]
    targets = [{'name':d.Name, 'path':d.FullName} for d in docs]
    request = {'expected':{'instance':'42', 'active':targets[0], 'documents':targets},
               'marker':str(tmp_path/'done.txt'), 'token':'test', 'command':'ZE\n'}
    with patch('sincal.web.cad_worker.active_application', return_value=app), \
         patch('sincal.web.cad_worker.execute', side_effect=[{'message':'ok'}, RuntimeError('uncertain')]) as send:
        with pytest.raises(RuntimeError):
            execute_all(request)
    assert send.call_count == 2
    docs[2].Activate.assert_not_called()
    progress = json.loads((tmp_path/'progress.json').read_text())
    assert progress['progress'] == pytest.approx(100/3)


def test_frozen_probe_uses_worker_entry(monkeypatch, tmp_path):
    import sincal.web.cad_connection as connection
    monkeypatch.setattr(connection.sys, 'frozen', True, raising=False)
    def run(command, **kwargs):
        assert command[1] == '--sincal-cad-probe'
        from pathlib import Path
        Path(command[2]).write_text('{"status":"ready"}', encoding='utf-8')
        return Mock(returncode=0)
    with patch.object(connection.subprocess, 'run', side_effect=run):
        assert connection.connection_status()['status'] == 'ready'
