"""Host binding restricts framing without exposing the private control token."""
import http.client
import json
import threading

import pytest

from pasarela_bim.servidor import Aplicacion


@pytest.fixture
def server():
    app = Aplicacion(("127.0.0.1", 0))
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    try:
        yield app
    finally:
        app.shutdown()
        app.server_close()
        thread.join(3)


def request(app, method, path, value=None, *, token=None, headers=None, raw=None):
    connection = http.client.HTTPConnection("127.0.0.1", app.server_port, timeout=3)
    h = {"Content-Type":"application/json"}
    if token is not None:
        h["X-Pasarela-Token"] = token
    h.update(headers or {})
    body = raw if raw is not None else json.dumps(value) if value is not None else None
    connection.request(method, path, body, h)
    response = connection.getresponse()
    result = response.status, response.read(), dict(response.getheaders())
    connection.close()
    return result


def bind(app, origin, **kwargs):
    return request(app, "POST", "/api/host/embed", {"parent_origin":origin}, token=app.control_token, **kwargs)


def test_standalone_cannot_be_bound_and_disallows_framing(server):
    status, html, headers = request(server, "GET", "/")
    assert status == 200
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert b'name="pasarela-parent-origin" content=""' in html
    assert bind(server, "http://127.0.0.1:8765")[0] == 404
    assert request(server, "GET", "/api/host-status", token=server.control_token)[0] == 404


def test_binding_rebinding_and_private_control(server):
    server.host_control = True
    origin = "http://127.0.0.1:8765"
    for token in (None, "incorrect", server.token):
        assert request(server, "POST", "/api/host/embed", {"parent_origin":origin}, token=token)[0] == 403
        assert request(server, "GET", "/api/host-status", token=token)[0] == 403
        assert request(server, "POST", "/api/cerrar", {}, token=token)[0] == 403
    status, info, _ = request(server, "GET", "/api/host-status", token=server.control_token)
    assert status == 200 and json.loads(info)["embedding"] == 1
    for origin in (origin, "http://127.0.0.1:54321"):
        status, response, _ = bind(server, origin)
        assert status == 200 and json.loads(response) == {"embedding":1,"parent_origin":origin}
        status, html, headers = request(server, "GET", "/")
        assert status == 200
        assert headers["Content-Security-Policy"].endswith("frame-ancestors "+origin)
        assert f'name="pasarela-parent-origin" content="{origin}"'.encode() in html
        assert server.control_token.encode() not in html
        assert server.token.encode() in html
    assert request(server, "GET", "/integracion.js")[0] == 200


@pytest.mark.parametrize("origin", [
    "http://localhost:8765", "https://127.0.0.1:8765", "http://127.0.0.1", "http://127.0.0.1:0",
    "http://127.0.0.1:65536", "http://127.0.0.1:08765", "http://127.0.0.1:8765/",
    "http://127.0.0.1:8765/path", "http://127.0.0.1:8765?x=1", "http://127.0.0.1:8765#part",
    "http://user:password@127.0.0.1:8765", "http://127.0.0.1:8765\n", "http://127.0.0.1:8765 'unsafe-inline'",
    "http://example.test:8765", 8765, None,
])
def test_invalid_origin_cannot_widen_or_replace_policy(server, origin):
    server.host_control = True
    assert bind(server, "http://127.0.0.1:12345")[0] == 200
    assert bind(server, origin)[0] == 400
    assert server.parent_origin == "http://127.0.0.1:12345"


def test_binding_does_not_relax_editor_origin_or_csrf(server):
    server.host_control = True
    origin = "http://127.0.0.1:12345"
    assert bind(server, origin)[0] == 200
    # The parent binds through a private server request. Browser editor writes
    # still originate at the module and need its separate UI session token.
    assert request(server, "POST", "/api/validar", {}, token=server.control_token)[0] == 403
    assert request(server, "POST", "/api/validar", {}, token=server.token,
                   headers={"Origin":origin})[0] == 403
    assert request(server, "POST", "/api/validar", {}, token=server.token,
                   headers={"Origin":server.origen})[0] == 200
    assert bind(server, origin, headers={"Origin":"http://foreign.test"})[0] == 403


def test_binding_limits_input_and_rejects_changes_while_closing(server):
    server.host_control = True
    assert bind(server, "http://127.0.0.1:12345", headers={"Content-Type":"text/plain"})[0] == 415
    assert request(server, "POST", "/api/host/embed", token=server.control_token, raw="["*10000)[0] == 400
    assert request(server, "POST", "/api/host/embed", [], token=server.control_token)[0] == 400
    server.cerrando = True
    assert bind(server, "http://127.0.0.1:12345")[0] == 409
    assert server.parent_origin is None
