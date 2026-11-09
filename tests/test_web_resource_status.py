import json
import threading
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from sincal.resources import ResourceEntry, ResourceSyncResult, ResourceUpdatePlan
from sincal.web.server import Server
from sincal.web.services import Services


def plan(revision='a', changed=True):
    entry = ResourceEntry('lisps/PURGEALL.lsp', 'c' * 40, 100)
    return ResourceUpdatePlan(revision * 40, (entry,), (entry,) if changed else (), (), False,
                              source_commit=revision * 40)


@pytest.fixture
def service(tmp_path):
    value = Services(tmp_path)
    with patch.object(value, '_resource_state_signature', return_value=(1, 100)):
        yield value
    value.jobs.close()


def test_background_checks_only_full_tree_for_new_revision(service):
    with patch('sincal.resources.distribution_manifest_revision', return_value='a' * 40) as manifest, \
            patch('sincal.resources.check_resource_updates', return_value=plan()) as check:
        assert service.resource_status()['changed'] == 1
        assert service.resource_status()['source_commit'] == 'a' * 40
        assert manifest.call_count == 1
        service.resource_status_checked -= 61
        assert service.resource_status()['available'] is True
        assert manifest.call_count == 2
        assert check.call_count == 1
        manifest.return_value = 'b' * 40
        check.return_value = plan('b')
        service.resource_status_checked -= 61
        assert service.resource_status()['source_commit'] == 'b' * 40
        assert check.call_count == 2


def test_background_remembers_plan_revision_not_earlier_manifest(service):
    with patch('sincal.resources.distribution_manifest_revision', return_value='a' * 40), \
            patch('sincal.resources.check_resource_updates', return_value=plan('b')):
        assert service.resource_status()['source_commit'] == 'b' * 40


def test_changed_local_state_invalidates_cached_pending_count(service):
    with patch('sincal.resources.distribution_manifest_revision', return_value='a' * 40), \
            patch('sincal.resources.check_resource_updates', side_effect=[plan(), plan(changed=False)]) as check:
        assert service.resource_status()['changed'] == 1
        service._resource_state_signature.return_value = (2, 100)
        assert service.resource_status()['changed'] == 0
        assert check.call_count == 2


def test_activation_failure_changes_local_status_signature(tmp_path):
    state, pending = tmp_path / 'resource_sync.json', tmp_path / '.cad_activation_pending'
    state.write_text('{}')
    with patch('sincal.resources.state_path', return_value=str(state)), \
            patch('sincal.resources._cad_activation_pending_path', return_value=str(pending)):
        initial = Services._resource_state_signature()
        pending.write_text('pending')
        assert Services._resource_state_signature() != initial
        pending.unlink()
        assert Services._resource_state_signature() == initial


def test_background_is_quiet_offline_and_does_not_lock_cad(service):
    service.cad_lock.acquire()
    try:
        with patch('sincal.resources.distribution_manifest_revision', side_effect=OSError('offline')):
            assert service.resource_status() == {'available': False}
        with patch('sincal.resources.check_resource_updates', side_effect=OSError('offline')):
            with pytest.raises(OSError, match='offline'):
                service.sync_check(Mock(), {})
    finally:
        service.cad_lock.release()


def test_apply_rejects_outdated_plan_without_downloading_or_activating(service):
    key = service.remember(service.plans, ('sync', plan('a')))
    with patch('sincal.resources.check_resource_updates', return_value=plan('b')), \
            patch('sincal.resources.apply_resource_updates') as apply, \
            patch('sincal.resources.materialize_cad_resources') as materialize:
        with pytest.raises(ValueError, match='publicación más reciente'):
            service.sync_apply(Mock(), {'plan': key})
        apply.assert_not_called()
        materialize.assert_not_called()


def test_apply_rechecks_local_changes_and_invalidates_status(service):
    old, fresh = plan(), plan(changed=False)
    key = service.remember(service.plans, ('sync', old))
    service._remember_resource_status(old)
    with patch('sincal.resources.check_resource_updates', return_value=fresh), \
            patch('sincal.resources.apply_resource_updates', return_value=ResourceSyncResult((), (), fresh.tree_sha)) as apply, \
            patch('sincal.resources.materialize_cad_resources'):
        service.sync_apply(Mock(), {'plan': key})
        apply.assert_called_once_with(fresh)
        assert service.resource_status_cache is None


@pytest.mark.parametrize('fail', [False, True])
def test_prepare_serializes_resource_writes_and_invalidates_status(service, fail):
    service._remember_resource_status(plan())
    service.resource_lock = threading.Lock()

    def materialize():
        assert not service.resource_lock.acquire(blocking=False)
        if fail:
            raise OSError('loader locked')
        return ('lisps/PURGEALL.lsp',)

    def register():
        assert not service.resource_lock.acquire(blocking=False)
        return ()

    with patch('sincal.resources.materialize_cad_resources', side_effect=materialize), \
            patch('sincal.cad.integration.registrar_ruta_cad_usuario', side_effect=register), \
            patch('sincal.cad.integration.registrar_scripts_en_path', side_effect=register):
        if fail:
            with pytest.raises(OSError, match='loader locked'):
                service.prepare(Mock(), {'confirm': True})
        else:
            result = service.prepare(Mock(), {'confirm': True})
            assert result['resources'] == ['lisps/PURGEALL.lsp']
        assert service.resource_status_cache is None
        assert service.resource_lock.acquire(blocking=False)
        service.resource_lock.release()

    with patch('sincal.resources.distribution_manifest_revision', return_value='a' * 40), \
            patch('sincal.resources.check_resource_updates', return_value=plan(changed=fail)) as check:
        assert service.resource_status()['changed'] == int(fail)
        check.assert_called_once()


def test_resource_status_endpoint_requires_local_token(tmp_path):
    server = Server(0, tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch.object(server.services, 'resource_status', return_value={'available': False}) as status:
            with pytest.raises(HTTPError) as failure:
                urlopen(server.origin + '/api/resources/status')
            assert failure.value.code == 401
            status.assert_not_called()
            request = Request(server.origin + '/api/resources/status', headers={'X-Sincal-Token': server.token})
            with urlopen(request) as response:
                assert json.load(response) == {'available': False}
                assert response.headers['Cache-Control'] == 'no-store'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
