import hashlib
import json
from pathlib import Path
import stat
import sys
from unittest.mock import patch
import zipfile

import pytest

from sincal.optional_modules import PasarelaModule, ENTRYPOINT


ROOT = Path(__file__).resolve().parents[1]


def package(path, *, version="0.3.0", content=b"MZmodule-test", extra=None, change=None):
    files = {ENTRYPOINT: content, **(extra or {})}
    manifest = {"schema": 1, "id": "pasarela-bim", "version": version, "entrypoint": ENTRYPOINT,
                "host_api": 1, "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    if change:
        change(manifest)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("module.json", json.dumps(manifest))
        for name, data in files.items():
            archive.writestr(name, data)
    return path


def host(tmp_path, source=False):
    return PasarelaModule(user_dir=tmp_path / "user", application_dir=tmp_path / "application",
                          source_dir=ROOT, allow_source=source)


def test_absent_module_and_explicit_development_source(tmp_path):
    absent = host(tmp_path).status()
    assert not absent["installed"] and absent["source"] is None
    current = host(tmp_path, True).status()
    assert current["installed"] and current["source"] == "development"
    assert current["version"] == "0.3.1"
    assert current["embedded_supported"]
    with patch.object(sys, "frozen", True, create=True):
        assert not PasarelaModule(user_dir=tmp_path, application_dir=tmp_path).status()["installed"]


def test_install_is_separate_does_not_execute_and_updates_atomically(tmp_path):
    manager = host(tmp_path)
    manager.application_dir.mkdir()
    main = manager.application_dir / "SINCAL.exe"
    main.write_bytes(b"existing-core")
    with patch("sincal.optional_modules.subprocess.Popen") as start:
        result = manager.install(package(tmp_path / "first.zip"))
        assert result["installed"] and result["source"] == "user"
        manager.install(package(tmp_path / "second.zip", version="0.3.1", content=b"MZnew-module"))
        assert manager.status()["version"] == "0.3.1"
        start.assert_not_called()
    assert main.read_bytes() == b"existing-core"
    assert not list(manager.target.parent.glob(".pasarela-*"))


def test_user_install_overrides_application_component(tmp_path):
    manager = host(tmp_path)
    system = manager.application_dir / "modules" / "pasarela-bim"
    system.mkdir(parents=True)
    with zipfile.ZipFile(package(tmp_path / "app.zip")) as archive:
        archive.extractall(system)
    assert manager.status()["source"] == "application"
    manager.install(package(tmp_path / "user.zip", version="0.3.1"))
    assert manager.status()["source"] == "user"
    assert json.loads((system / "module.json").read_text())["version"] == "0.3.0"


@pytest.mark.parametrize("name", ["../escape.exe", "/absolute.exe", "C:/outside.exe", "a\\outside.exe", "dir/../outside", "NUL", "a./x", "a//b"])
def test_unsafe_archive_paths_rejected_without_affecting_installed_module(tmp_path, name):
    manager = host(tmp_path)
    manager.install(package(tmp_path / "valid.zip"))
    with pytest.raises(ValueError):
        manager.install(package(tmp_path / "bad.zip", extra={name: b"bad"}))
    assert (manager.target / ENTRYPOINT).read_bytes() == b"MZmodule-test"
    assert not (tmp_path / "escape.exe").exists()


@pytest.mark.parametrize("change", [
    lambda m: m.update(id="another-module"), lambda m: m.update(host_api=99),
    lambda m: m.update(entrypoint="../other.exe"), lambda m: m.update(version="latest"),
    lambda m: m["files"].update({ENTRYPOINT: "0" * 64}), lambda m: m.update(files={})])
def test_wrong_package_or_checksum_is_not_installed(tmp_path, change):
    manager = host(tmp_path)
    with pytest.raises(ValueError):
        manager.install(package(tmp_path / "bad.zip", change=change))
    assert not manager.target.exists()


def test_unlisted_files_symlinks_and_case_duplicates_are_rejected(tmp_path):
    for kind in ("extra", "symlink", "case"):
        path = package(tmp_path / f"{kind}.zip")
        with zipfile.ZipFile(path, "a") as archive:
            if kind == "symlink":
                entry = zipfile.ZipInfo("link")
                entry.create_system = 3
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(entry, "../../elsewhere")
            else:
                archive.writestr(ENTRYPOINT.upper() if kind == "case" else "unexpected.exe", b"bad")
        with pytest.raises(ValueError):
            host(tmp_path).install(path)


def test_replacement_failure_restores_previous_install(tmp_path):
    manager = host(tmp_path)
    manager.install(package(tmp_path / "good.zip"))
    candidate = package(tmp_path / "new.zip", version="0.3.1")
    original = Path.rename
    def fail_stage(path, target):
        if path.name.startswith(".pasarela-stage-"):
            raise OSError("simulated lock")
        return original(path, target)
    with patch.object(Path, "rename", fail_stage), pytest.raises(ValueError):
        manager.install(candidate)
    assert manager.status()["version"] == "0.3.0"
    assert not list(manager.target.parent.glob(".pasarela-*"))


def test_changed_executable_not_launched(tmp_path):
    manager = host(tmp_path)
    manager.install(package(tmp_path / "good.zip"))
    (manager.target / ENTRYPOINT).write_bytes(b"MZtampered")
    with patch("sincal.optional_modules.subprocess.Popen") as start, pytest.raises(ValueError, match="cambió"):
        manager.launch(open_browser=False)
    start.assert_not_called()


def test_real_source_launch_reuses_recovers_and_closes_without_freecad(tmp_path):
    manager = host(tmp_path, True)
    try:
        with patch("sincal.optional_modules.webbrowser.open") as browser:
            first = manager.launch()
            assert first["url"].startswith("http://127.0.0.1:")
            assert manager.status()["running"]
            assert manager.launch()["url"] == first["url"]
            assert browser.call_count == 2
        recovered = host(tmp_path, True)
        assert recovered.status()["running"]
        assert recovered.launch(open_browser=False)["url"] == first["url"]
        with pytest.raises(ValueError, match="Cerrar módulo"):
            recovered.install(package(tmp_path / "blocked.zip"))
        assert recovered.close()["running"] is False
        assert manager.process.poll() is not None, "El cierre recuperado debe esperar a que termine el proceso"
        manager.process.wait(timeout=10)
        assert not manager.status()["running"]
        assert not manager.active_file.exists()
    finally:
        if manager.process is not None and manager.process.poll() is None:
            manager.close()
