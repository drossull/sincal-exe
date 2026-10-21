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
        assert request(route + "release", b"{}", {**auth, "Content-Type": "application/json"})[0] == 200
        assert opened_urls == [server.module_host.status()["release_url"]]
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
