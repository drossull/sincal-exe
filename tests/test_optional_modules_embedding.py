"""Host integration is local, explicit, recoverable and private to this session."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import threading

import pytest

from sincal import optional_modules as modules
from tests.test_optional_modules import host, package


TOKEN = "private-control-token-for-tests-only"
PARENT = "http://127.0.0.1:48101"


@pytest.fixture
def module_service(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_json(self, data, status=200):
            raw = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.server.calls.append(("GET", self.path, self.headers.get("X-Pasarela-Token"), None))
            if self.server.redirect:
                self.send_response(302)
                self.send_header("Location", self.server.redirect)
                self.end_headers()
                return
            if self.headers.get("X-Pasarela-Token") != TOKEN:
                self.send_json({"mensaje": "Sesión no autorizada"}, 403)
                return
            self.send_json(self.server.identity)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.server.calls.append(("POST", self.path, self.headers.get("X-Pasarela-Token"), body))
            if self.headers.get("X-Pasarela-Token") != TOKEN:
                self.send_json({"mensaje": "Sesión no autorizada"}, 403)
                return
            self.send_json(self.server.embed_result or {"embedding": 1, "parent_origin": body["parent_origin"]})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.calls = []
    server.redirect = None
    server.identity = {"pid": 13579, "version": "0.3.1", "embedding": 1}
    server.embed_result = None
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    manager = host(tmp_path)
    manager.install(package(tmp_path / "module.zip", version="0.3.1", change=lambda m: m.update(embedding=1)))
    ready = {**server.identity, "url": f"http://127.0.0.1:{server.server_port}/", "control_token": TOKEN}
    manager.active_file.parent.mkdir(parents=True, exist_ok=True)
    manager.active_file.write_text(json.dumps(ready), encoding="utf-8")
    try:
        yield manager, server, ready
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)


@pytest.mark.parametrize("origin", [
    "https://127.0.0.1:1234", "http://localhost:1234", "http://127.1:1234",
    "http://[::1]:1234", "http://127.0.0.1:1234/", "http://127.0.0.1:1234/path",
    "http://user:password@127.0.0.1:1234", "http://127.0.0.1:1234?query=1",
    "http://127.0.0.1:1234#token", "http://127.0.0.1:0", "http://127.0.0.1:65536",
    " http://127.0.0.1:1234", "http://127.0.0.1:1234\n", "http://127.0.0.1:01234",
    "http://127.0.0.1:1234?", "http://127.0.0.1:1234#", "http://example.test:1234", True, 1234,
])
def test_parent_origin_must_be_exact_before_starting(tmp_path, origin):
    manager = host(tmp_path)
    with patch.object(manager, "_running_info") as running, patch.object(modules.subprocess, "Popen") as start:
        with pytest.raises(ValueError, match="integración"):
            manager.launch(parent_origin=origin)
        running.assert_not_called()
        start.assert_not_called()


def test_legacy_package_offers_update_without_launch_or_automatic_close(tmp_path):
    manager = host(tmp_path)
    manager.install(package(tmp_path / "legacy.zip"))
    assert manager.status()["installed"]
    assert not manager.status()["embedded_supported"]
    assert "Actualiza" in manager.status()["message"]
    with patch.object(modules.subprocess, "Popen") as start, patch.object(modules.webbrowser, "open") as browser, patch.object(manager, "close") as close:
        with pytest.raises(ValueError, match="Actualiza"):
            manager.launch(parent_origin=PARENT)
        start.assert_not_called()
        browser.assert_not_called()
        close.assert_not_called()


def test_recovery_binds_each_parent_and_keeps_control_token_private(module_service):
    manager, server, ready = module_service
    with patch.object(modules.subprocess, "Popen") as start, patch.object(modules.webbrowser, "open") as browser:
        first = manager.launch(parent_origin=PARENT)
        assert first == {"url": ready["url"], "embedding": 1, "parent_origin": PARENT,
                         "message": "Editor abierto dentro de SINCAL. Sus proyectos se guardan mediante JSON."}
        reopened = host(manager.user_dir.parent)
        second_origin = "http://127.0.0.1:48102"
        second = reopened.launch(open_browser=False, parent_origin=second_origin)
        assert second["parent_origin"] == second_origin and second["url"] == first["url"]
        status = reopened.status()
        assert status["running"] and status["embedded_supported"]
        assert TOKEN not in json.dumps([first, second, status])
        browser.assert_not_called()
        start.assert_not_called()
    posts = [call for call in server.calls if call[0] == "POST"]
    assert posts == [("POST", "/api/host/embed", TOKEN, {"parent_origin": PARENT}),
                     ("POST", "/api/host/embed", TOKEN, {"parent_origin": second_origin})]


def test_old_running_session_is_preserved_even_if_new_package_is_installed(module_service):
    manager, server, _ = module_service
    server.identity.pop("embedding")
    status = manager.status()
    assert status["running"] and not status["embedded_supported"]
    with patch.object(manager, "close") as close, patch.object(modules.subprocess, "Popen") as start:
        with pytest.raises(ValueError, match="Cerrar módulo"):
            manager.launch(parent_origin=PARENT)
        with pytest.raises(ValueError, match="Cerrar módulo"):
            manager.install_online()
        close.assert_not_called()
        start.assert_not_called()
    assert manager.active_file.exists()
    assert not any(call[0] == "POST" for call in server.calls)


@pytest.mark.parametrize("response", [{"embedding": True, "parent_origin": PARENT},
                                      {"embedding": 1, "parent_origin": "http://127.0.0.1:48103"}])
def test_embed_confirmation_must_match_and_does_not_close_recovered_session(module_service, response):
    manager, server, _ = module_service
    server.embed_result = response
    with patch.object(manager, "close") as close:
        with pytest.raises(ValueError, match="confirmó"):
            manager.launch(parent_origin=PARENT)
        close.assert_not_called()
    assert manager.active_file.exists() and manager.status()["running"]


def test_control_requests_refuse_redirects_and_foreign_session(module_service):
    manager, server, ready = module_service
    server.redirect = f"{ready['url']}stolen-token"
    assert manager._running_info() is None
    assert [call[1] for call in server.calls] == ["/api/host-status"]
    server.redirect = None
    server.identity["pid"] += 1
    assert manager._running_info() is None
    server.identity["pid"] = ready["pid"]
    changed = dict(ready, control_token="incorrect-control-token-long-enough")
    manager.active_file.write_text(json.dumps(changed), encoding="utf-8")
    assert manager._running_info() is None


def test_real_source_embedded_launch_and_rebind_without_opening_browser(tmp_path):
    manager = host(tmp_path, True)
    try:
        with patch.object(modules.webbrowser, "open") as browser:
            result = manager.launch(parent_origin=PARENT)
            assert result["embedding"] == 1 and result["parent_origin"] == PARENT
            recovered = host(tmp_path, True)
            rebound = recovered.launch(parent_origin="http://127.0.0.1:48102")
            assert rebound["url"] == result["url"]
            browser.assert_not_called()
            with modules.urlopen(result["url"], timeout=2) as response:
                assert "frame-ancestors http://127.0.0.1:48102" in response.headers["Content-Security-Policy"]
                assert manager.ready["control_token"].encode() not in response.read()
            assert recovered.close()["running"] is False
            manager.process.wait(timeout=10)
    finally:
        if manager.process is not None and manager.process.poll() is None:
            manager.close()
