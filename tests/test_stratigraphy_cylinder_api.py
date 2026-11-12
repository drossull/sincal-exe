import copy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import Mock

import pytest

from sincal.web.server import Server, Store
from sincal.web.services import Services
from test_stratigraphy import report


def test_output_mode_preview_and_session_roundtrip(tmp_path):
    data = report().to_dict()
    original = copy.deepcopy(data)
    payload = {'data': {}, 'identification': {'ot': 'TEST', 'revision': 'A', 'structure_name': 'Cilindro'},
               'stratigraphy': {'report': data, 'output_mode': 'isometric-cylinder'}}
    store = Store(tmp_path / 'sessions.db')
    saved = store.save(payload)
    assert store.get(saved['id']) == payload
    assert data == original
    payload['stratigraphy'].pop('output_mode')
    assert store.get(store.save(payload)['id']) == payload  # Older sessions keep full output.
    for mode in [None, True, [], {}, 'unknown']:
        payload['stratigraphy']['output_mode'] = mode
        with pytest.raises(ValueError):
            store.save(payload)


def test_http_mode_reaches_scene_and_rejects_invalid_values(tmp_path):
    with Server(0, tmp_path / 'server') as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def preview(mode):
            request = Request(server.origin + '/api/stratigraphy/preview',
                              data=json.dumps({'report': report().to_dict(), 'table': True,
                                               'output_mode': mode, 'annotation_scale': 5}).encode(),
                              headers={'X-Sincal-Token': server.token, 'Content-Type': 'application/json'})
            return urlopen(request, timeout=10)
        try:
            with preview('isometric-cylinder') as response:
                scene = json.load(response)['checks'][0]['scene']
            assert scene['depth_scale'] == 5
            assert any(i['kind'] == 'ellipse' for i in scene['items'])
            assert not any('NSPT' in i.get('text', '') for i in scene['items'])
            with preview('full') as response:
                full = json.load(response)['checks'][0]['scene']
            assert any('NSPT' in i.get('text', '') for i in full['items'])
            assert not any(i['kind'] == 'ellipse' for i in full['items'])
            with pytest.raises(HTTPError) as invalid:
                preview('unknown')
            assert invalid.value.code == 400
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_insertion_passes_mode_without_relaxing_review_or_cad_guard(tmp_path, monkeypatch):
    r = report()
    hole = r.boreholes[0]
    service = Services(tmp_path / 'service')
    service.cad = Mock(return_value={'message': 'ok'})
    service.lisp = Mock(return_value='fixture.lsp')
    builder = Mock(return_value='test source')
    monkeypatch.setattr('sincal.cad.stratigraphy.build_stratigraphy_lisp', builder)
    payload = {'report': r.to_dict(), 'key': hole.key, 'output_mode': 'isometric-cylinder',
               'expected': {'active': {'annotation_scale': {'name': '1:200 (m)', 'value': 5}}}}
    try:
        with pytest.raises(ValueError, match='Coteja'):
            service.stratigraphy_insert(Mock(), payload)
        service.cad.assert_not_called()
        hole.reviewed = True
        payload['report'] = r.to_dict()
        service.stratigraphy_insert(Mock(), payload)
        assert builder.call_args.kwargs['output_mode'] == 'isometric-cylinder'
        assert builder.call_args.args[-2:] == (5, '1:200 (m)')
        assert service.cad.call_args.args[1] == payload['expected']
        assert service.cad.call_args.kwargs['completion'] == 'stratigraphy-v1'
    finally:
        service.jobs.close()
