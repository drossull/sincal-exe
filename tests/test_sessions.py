import json
from pathlib import Path

import pytest

from sincal.sessions import (
    SESSION_SUFFIX, SessionStore, atomic_json_write, safe_session_filename,
    sha256_file,
)


def session_payload(name="Puente La Tetera"):
    return {
        "metadata": {"name": name},
        "project": {"bridge_name": name, "json_name": "G45.json"},
        "workspace": {"abutments": {}},
        "overview": {"mark_count": 6, "total_kg": 123.4},
    }


def test_session_store_round_trip_and_backup(tmp_path):
    store = SessionStore(tmp_path / "library", tmp_path / "recovery")
    document, path = store.save(session_payload())
    assert path.name.endswith(SESSION_SUFFIX)
    assert store.load(path)["metadata"]["id"] == document["metadata"]["id"]

    document["overview"]["mark_count"] = 7
    store.save(document, path)
    assert store.load(path)["overview"]["mark_count"] == 7
    assert Path(str(path) + ".bak").is_file()


def test_library_ignores_corrupt_sessions_and_searches_metadata(tmp_path):
    store = SessionStore(tmp_path / "library", tmp_path / "recovery")
    _, path = store.save(session_payload("Puente Ñuble"))
    (path.parent / f"corrupt{SESSION_SUFFIX}").write_text("{", encoding="utf-8")
    summaries = store.summaries()
    assert len(summaries) == 1
    assert "puente nuble" in summaries[0]["search_text"]


def test_autosave_is_separate_and_clearable(tmp_path):
    store = SessionStore(tmp_path / "library", tmp_path / "recovery")
    payload = session_payload()
    payload["metadata"]["id"] = "abc"
    recovery = store.autosave(payload)
    assert recovery.is_file()
    assert store.load(recovery)["metadata"]["id"] == "abc"
    assert store.pending_recoveries()[0]["path"] == str(recovery)
    store.clear_autosave("abc")
    assert not recovery.exists()


def test_atomic_write_leaves_valid_json_and_hash_detects_change(tmp_path):
    target = tmp_path / "data.json"
    atomic_json_write(target, {"value": 1})
    first = sha256_file(target)
    atomic_json_write(target, {"value": 2}, backup=False)
    assert json.loads(target.read_text(encoding="utf-8"))["value"] == 2
    assert sha256_file(target) != first


def test_filename_is_safe_and_schema_is_validated(tmp_path):
    assert safe_session_filename("Puente Ñuble / Entrada").endswith(SESSION_SUFFIX)
    store = SessionStore(tmp_path, tmp_path / "recovery")
    invalid = tmp_path / f"old{SESSION_SUFFIX}"
    invalid.write_text('{"schema_version": 99, "metadata": {}}', encoding="utf-8")
    with pytest.raises(ValueError):
        store.load(invalid)
