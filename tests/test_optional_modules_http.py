import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sincal.web.server import Server
from sincal.optional_modules import MAX_PACKAGE_BYTES
from tests.test_optional_modules import host, package


def test_module_routes_require_session_and_install_after_core(tmp_path, monkeypatch):
    server = Server(0, tmp_path / "web")
    server.module_host = host(tmp_path)
    online_calls = []
    opened_urls = []
    monkeypatch.setattr(server.module_host, "install_online", lambda: online_calls.append(True) or server.module_host.status())
    monkeypatch.setattr("sincal.web.server.webbrowser.open", opened_urls.append)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    def request(route, data=None, headers=None):
        try:
            with urlopen(Request(server.origin + route, data=data, headers=headers or {})) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()
    auth = {"X-Sincal-Token": server.token}
    route = "/api/modules/pasarela/"
    archive = package(tmp_path / "package.zip").read_bytes()
    try:
        assert request(route + "status")[0] == 401
        assert not json.loads(request(route + "status", headers=auth)[1])["installed"]
        assert request(route + "install", archive)[0] == 401
        assert request(route + "install-online", b"{}")[0] == 401
        assert request(route + "install-online", b"{}", {**auth, "Origin": "https://other.example"})[0] == 403
        assert not online_calls
        assert request(route + "install-online", b"{}", {**auth, "Content-Type": "application/json"})[0] == 200
        assert online_calls == [True]
        assert request(route + "release", b"{}")[0] == 401
        assert not opened_urls
        code, publication = request(route + "release", b"{}", {**auth, "Content-Type": "application/json"})
        assert code == 200
        assert json.loads(publication)["url"] == server.module_host.status()["release_url"]
        assert not opened_urls, "Consultar la publicación no debe abrir un navegador externo."
        assert request(route + "install", archive, {**auth, "Origin": "https://other.example"})[0] == 403
        assert request(route + "install", archive, {**auth, "Content-Type": "application/json"})[0] == 415
        assert request(route + "install", b"x", {**auth, "Content-Type": "application/zip", "Content-Length": str(MAX_PACKAGE_BYTES + 1)})[0] == 413
        assert request(route + "install", b"not-a-zip", {**auth, "Content-Type": "application/zip"})[0] == 400
        code, raw = request(route + "install", archive, {**auth, "Content-Type": "application/zip"})
        assert code == 200 and json.loads(raw)["installed"]
        status = json.loads(request(route + "status", headers=auth)[1])
        assert status["source"] == "user" and status["version"] == "0.3.0"
        assert "control_token" not in status
        assert request("/optional_modules.js")[0] == 200
        assert request(route + "close", b"{}", {**auth, "Content-Type": "application/json"})[0] == 200
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)


def test_web_open_embeds_only_in_current_session_without_browser(tmp_path, monkeypatch):
    server = Server(0, tmp_path / "web")
    server.module_host = host(tmp_path)
    opened = []
    browsers = []
    monkeypatch.setattr("sincal.web.server.webbrowser.open", browsers.append)
    def launch(**kwargs):
        opened.append(kwargs)
        return {"url": "http://127.0.0.1:49001/", "embedding": 1, "parent_origin": kwargs["parent_origin"]}
    monkeypatch.setattr(server.module_host, "launch", launch)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    def request(path, data=None, headers=None):
        try:
            with urlopen(Request(server.origin + path, data=data, headers=headers or {})) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers
    route = "/api/modules/pasarela/open"
    auth = {"X-Sincal-Token": server.token, "Content-Type": "application/json"}
    try:
        assert request(route, b"{}")[0] == 401
        assert request(route, b"{}", {**auth, "Origin": "http://127.0.0.1:49002"})[0] == 403
        assert request(route, b"{}", {**auth, "Host": "attacker.test"})[0] == 403
        assert not opened
        # Even an authenticated caller cannot select a different parent origin.
        code, body, headers = request(route, b'{"parent_origin":"https://attacker.test"}', {**auth, "Origin": server.origin})
        assert code == 200
        assert opened == [{"open_browser": False, "parent_origin": server.origin}]
        assert json.loads(body)["parent_origin"] == server.origin
        assert "control_token" not in body.decode()
        assert not browsers
        policy = headers["Content-Security-Policy"]
        assert "frame-src http://127.0.0.1:*;" in policy
        assert "connect-src 'self';" in policy and "frame-ancestors 'none';" in policy
        assert "default-src 'self';" in policy and "script-src 'self';" in policy
        assert request("/")[2]["Content-Security-Policy"] == policy
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)


def test_web_legacy_module_requires_update_without_launch(tmp_path, monkeypatch):
    server = Server(0, tmp_path / "web")
    server.module_host = host(tmp_path)
    server.module_host.install(package(tmp_path / "legacy.zip"))
    starts = []
    monkeypatch.setattr("sincal.optional_modules.subprocess.Popen", starts.append)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    headers = {"X-Sincal-Token": server.token, "Content-Type": "application/json"}
    try:
        with urlopen(Request(server.origin + "/api/modules/pasarela/status", headers=headers)) as response:
            assert not json.load(response)["embedded_supported"]
        try:
            urlopen(Request(server.origin + "/api/modules/pasarela/open", data=b"{}", headers=headers))
            assert False, "Una versión anterior no debe abrirse en un navegador externo."
        except HTTPError as error:
            assert error.code == 400 and "Actualiza" in json.load(error)["error"]
        assert not starts
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)
