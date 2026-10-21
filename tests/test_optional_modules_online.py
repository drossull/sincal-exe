"""Public-release installation without contacting the network or running code."""
import hashlib
from http.client import IncompleteRead
import io
import json
from pathlib import Path
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request
from unittest.mock import patch

import pytest

from sincal import optional_modules as modules
from tests.test_optional_modules import host, package


CORE_VERSION = "v3.0.24"
BASE = f"{modules.RELEASE_REPOSITORY}/releases/download/{CORE_VERSION}"
MANIFEST_URL = f"{BASE}/release-manifest_{CORE_VERSION}.json"


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, url, *, length=True):
        super().__init__(data)
        self.url = url
        self.headers = {"Content-Length": str(len(data))} if length else {}

    def geturl(self):
        return self.url


@pytest.fixture(autouse=True)
def installed_release(monkeypatch):
    monkeypatch.setattr("sincal.runtime.leer_version", lambda: CORE_VERSION)


def release_files(tmp_path, *, version="0.3.1", inner_version=None):
    data = package(tmp_path / "download.zip", version=inner_version or version,
                   content=b"MZdownloaded-module").read_bytes()
    name = f"SINCAL_Pasarela_v{version}.zip"
    manifest = {"schema": 1, "product": "SINCAL Suite", "release": CORE_VERSION,
                "assets": {"pasarela_bim": {"name": name, "version": version, "host_api": 1,
                    "url": f"{BASE}/{name}", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}}
    return manifest, data


def network(monkeypatch, manifest, data, *, during_download=None):
    calls = []
    asset_url = manifest["assets"]["pasarela_bim"]["url"]

    def open_download(url):
        calls.append(url)
        if url == MANIFEST_URL:
            # Release manifests written by Windows PowerShell may have a BOM.
            return Response(json.dumps(manifest).encode("utf-8-sig"), url)
        assert url == asset_url
        if during_download:
            during_download()
        return Response(data, url)

    monkeypatch.setattr(modules, "_open_release_download", open_download)
    return calls


def existing_install(manager, tmp_path):
    manager.install(package(tmp_path / "existing.zip", version="0.3.0", content=b"MZprevious-module"))
    manager.application_dir.mkdir()
    core = manager.application_dir / "SINCAL.exe"
    core.write_bytes(b"unchanged-core")
    return core


def assert_preserved(manager, core):
    assert (manager.target / modules.ENTRYPOINT).read_bytes() == b"MZprevious-module"
    assert manager.status()["version"] == "0.3.0"
    assert not manager.status()["installing"]
    assert core.read_bytes() == b"unchanged-core"
    assert not list(manager.target.parent.glob(".pasarela-*"))
    assert not list((manager.user_dir / "pasarela-bim" / "downloads").glob(".pasarela-*"))


def test_status_is_offline_and_pinned_to_installed_core(tmp_path, monkeypatch):
    manager = host(tmp_path)
    with patch.object(modules, "_open_release_download") as remote, patch.object(modules, "urlopen") as local:
        status = manager.status()
        assert status["online_install_available"]
        assert status["release_url"] == f"{modules.RELEASE_REPOSITORY}/releases/tag/{CORE_VERSION}"
        assert CORE_VERSION in status["install_message"]
        assert not status["installed"]
        remote.assert_not_called()
        local.assert_not_called()
    assert not manager.user_dir.exists()
    monkeypatch.setattr("sincal.runtime.leer_version", lambda: "v0.0.0")
    assert not manager.status()["online_install_available"]
    assert manager.status()["release_url"] is None
    with pytest.raises(ValueError, match="release instalado"):
        manager.install_online()


def test_install_online_validates_then_updates_only_module_without_launch(tmp_path, monkeypatch):
    manager = host(tmp_path)
    core = existing_install(manager, tmp_path)
    manifest, data = release_files(tmp_path)
    observed = []

    def while_downloading():
        # Downloading must leave status available and prevent concurrent launch.
        probe = threading.Thread(target=lambda: observed.append(manager.status()["installing"]))
        probe.start()
        probe.join(2)
        assert not probe.is_alive()
        with pytest.raises(ValueError, match="instalación"):
            manager.launch(open_browser=False)
        with pytest.raises(ValueError, match="instalando"):
            manager.install_online()

    calls = network(monkeypatch, manifest, data, during_download=while_downloading)
    with patch.object(modules.subprocess, "Popen") as start:
        result = manager.install_online()
        start.assert_not_called()
    assert result["installed"] and result["version"] == "0.3.1" and not result["installing"]
    assert calls == [MANIFEST_URL, manifest["assets"]["pasarela_bim"]["url"]]
    assert observed == [True]
    assert core.read_bytes() == b"unchanged-core"
    assert not list((manager.user_dir / "pasarela-bim" / "downloads").iterdir())


def test_corruption_is_rejected_before_zip_install_and_preserves_existing(tmp_path, monkeypatch):
    manager = host(tmp_path)
    core = existing_install(manager, tmp_path)
    manifest, data = release_files(tmp_path)
    network(monkeypatch, manifest, data[:-1] + bytes([data[-1] ^ 1]))
    with patch.object(manager, "install", wraps=manager.install) as install:
        with pytest.raises(ValueError, match="SHA-256"):
            manager.install_online()
        install.assert_not_called()
    assert_preserved(manager, core)


@pytest.mark.parametrize("url", [
    "https://github.com/other/repository/releases/download/v3.0.24/SINCAL_Pasarela_v0.3.1.zip",
    "https://github.com/drossull/sincal-updates/releases/download/v9.9.9/SINCAL_Pasarela_v0.3.1.zip",
    "https://example.test/SINCAL_Pasarela_v0.3.1.zip",
    f"http://github.com/drossull/sincal-updates/releases/download/{CORE_VERSION}/SINCAL_Pasarela_v0.3.1.zip",
    f"{BASE}/SINCAL_Pasarela_v0.3.1.zip?extra=1",
    f"{BASE}/../SINCAL_Pasarela_v0.3.1.zip",
])
def test_foreign_or_unpinned_asset_never_downloaded(tmp_path, monkeypatch, url):
    manager = host(tmp_path)
    core = existing_install(manager, tmp_path)
    manifest, data = release_files(tmp_path)
    manifest["assets"]["pasarela_bim"]["url"] = url
    calls = network(monkeypatch, manifest, data)
    with pytest.raises(ValueError, match="mismo release oficial"):
        manager.install_online()
    assert calls == [MANIFEST_URL]
    assert_preserved(manager, core)


@pytest.mark.parametrize("level,key,value", [
    ("manifest", "schema", True), ("manifest", "product", "Another product"),
    ("manifest", "release", "v3.0.25"), ("asset", "version", "latest"),
    ("asset", "host_api", True), ("asset", "host_api", 2),
    ("asset", "name", "other.zip"), ("asset", "bytes", True),
    ("asset", "bytes", 0), ("asset", "bytes", modules.MAX_PACKAGE_BYTES + 1),
    ("asset", "sha256", "unverified"),
])
def test_invalid_manifest_rejected_before_asset_download(tmp_path, monkeypatch, level, key, value):
    manifest, data = release_files(tmp_path)
    target = manifest if level == "manifest" else manifest["assets"]["pasarela_bim"]
    target[key] = value
    calls = network(monkeypatch, manifest, data)
    manager = host(tmp_path)
    with pytest.raises(ValueError):
        manager.install_online()
    assert calls == [MANIFEST_URL]
    assert not manager.target.exists() and not manager.status()["installing"]


def test_inner_version_must_match_release_before_replacement(tmp_path, monkeypatch):
    manager = host(tmp_path)
    core = existing_install(manager, tmp_path)
    manifest, data = release_files(tmp_path, inner_version="0.9.9")
    network(monkeypatch, manifest, data)
    with pytest.raises(ValueError, match="versión interna"):
        manager.install_online()
    assert_preserved(manager, core)


def test_online_update_rolls_back_if_replacement_fails(tmp_path, monkeypatch):
    manager = host(tmp_path)
    core = existing_install(manager, tmp_path)
    manifest, data = release_files(tmp_path)
    network(monkeypatch, manifest, data)
    original = Path.rename

    def fail_stage(path, target):
        if path.name.startswith(".pasarela-stage-"):
            raise OSError("simulated replacement failure")
        return original(path, target)

    monkeypatch.setattr(Path, "rename", fail_stage)
    with pytest.raises(ValueError, match="No se pudo instalar"):
        manager.install_online()
    assert_preserved(manager, core)


@pytest.mark.parametrize("mode", ["oversized", "truncated", "content_length", "malformed_length"])
def test_download_bound_and_completeness(tmp_path, monkeypatch, mode):
    url = f"{BASE}/test.zip"
    data = b"01234567890" if mode == "oversized" else b"12345"
    response = Response(data, url, length=False)
    expected_size = 7 if mode == "truncated" else None
    if mode == "content_length":
        response.headers["Content-Length"] = "200000000"
    if mode == "malformed_length":
        response.headers["Content-Length"] = "garbage"
    monkeypatch.setattr(modules, "_open_release_download", lambda _: response)
    output = io.BytesIO()
    with pytest.raises(ValueError):
        modules._stream_release(url, output, 10, expected_size=expected_size)
    assert len(output.getvalue()) <= 10


@pytest.mark.parametrize("failure", [
    HTTPError(MANIFEST_URL, 404, "missing", {}, None),
    URLError("proxy https://user:secret@example.test failed"),
    IncompleteRead(b"partial"),
])
def test_network_failure_is_clear_without_credentials_and_leaves_install_unchanged(tmp_path, monkeypatch, failure):
    manager = host(tmp_path)
    core = existing_install(manager, tmp_path)

    def fail(_):
        raise failure

    monkeypatch.setattr(modules, "_open_release_download", fail)
    with pytest.raises(ValueError) as error:
        manager.install_online()
    assert "secret" not in str(error.value)
    assert "http" not in str(error.value).lower()
    assert_preserved(manager, core)


@pytest.mark.parametrize("target", [
    "http://release-assets.githubusercontent.com/file", "https://example.test/file",
    "https://user:secret@release-assets.githubusercontent.com/file",
    "https://release-assets.githubusercontent.com:invalid/file",
    "https://github.com/other/repository/file", "file:///C:/unrelated",
])
def test_redirect_rejects_untrusted_destinations_before_following(target):
    with pytest.raises(ValueError, match="no autorizada"):
        modules._ReleaseRedirects(MANIFEST_URL).redirect_request(Request(MANIFEST_URL), None, 302, "", {}, target)


def test_redirect_allows_verified_github_cdn():
    url = "https://release-assets.githubusercontent.com/github-production-release-asset/example?signature=value"
    request = modules._ReleaseRedirects(MANIFEST_URL).redirect_request(Request(MANIFEST_URL), None, 302, "", {}, url)
    assert request.full_url == url


def test_running_module_blocks_download(tmp_path):
    manager = host(tmp_path)
    with patch.object(manager, "_running_info", return_value={"pid": 123}), patch.object(modules, "_open_release_download") as download:
        with pytest.raises(ValueError, match="Cerrar módulo"):
            manager.install_online()
        download.assert_not_called()
