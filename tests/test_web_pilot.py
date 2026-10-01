import json
import threading
import urllib.error
import urllib.request

import pytest

from sincal.web.server import Server, Store, project_result


def payload():
    return {"data": {"parametros_generales": {"ancho_mm": 11800}},
            "identification": {"ot": "TEST", "revision": "A", "structure_name": "Puente de prueba"}}


def test_private_snapshot_store(tmp_path):
    store = Store(tmp_path / "one" / "sessions.db")
    first = store.save(payload())
    second = store.save(payload())
    assert first != second
    assert store.get(first["id"]) == payload()
    assert len(store.list()) == 2
    assert Store(tmp_path / "two" / "sessions.db").list() == []
    assert Store(tmp_path / "one" / "sessions.db").get(first["id"]) == payload()


def test_validation():
    assert "11" in project_result(payload())["text"]
    with pytest.raises(ValueError):
        project_result({"data": {"estribos": []}})


def test_http_auth_origin_assets_and_roundtrip(tmp_path):
    server = Server(0, tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(path, data=None, headers=None):
        req = urllib.request.Request(server.origin + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=headers or {})
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers
    try:
        auth = {"X-Sincal-Token": server.token, "Content-Type": "application/json"}
        assert request("/api/sessions")[0] == 401
        assert request("/api/sessions", headers={**auth, "Origin": "https://evil.example"})[0] == 403
        assert request("/", headers={"Host": "evil.example"})[0] == 403
        assert request("/../../README.md")[0] == 404
        assert request("/roboto-400.ttf")[0] == 200
        assert request("/")[2]["Content-Security-Policy"]
        assert request("/api/project/preview", payload(), auth)[0] == 200
        code, raw, _ = request("/api/rebar/defaults", headers=auth)
        assert code == 200
        code, preview, _ = request("/api/rebar/preview", json.loads(raw), auth)
        assert code == 200 and json.loads(preview)["valid"]
        for path in ('/api/sessions', '/api/sessions/example', '/api/sessions/import',
                     '/api/recovery', '/api/recovery/clear', '/api/recovery/consumed'):
            assert request(path, headers=auth)[0] == 404
            assert request(path, payload(), auth)[0] == 404
        assert server.store.list() == []
        assert server.store.recover() is None
        assert request("/api/sessions", [], auth)[0] == 400
        assert request("/api/cad/execute", payload(), auth)[0] == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
