import json
import os
import tempfile
import unittest
from unittest.mock import patch

from sincal import resources as resource_sync


class FakeResponse:
    def __init__(self, *, payload=None, content=b"", status_code=200):
        self._payload = payload
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset : offset + chunk_size]


class FakeSession:
    def __init__(self, tree, downloads=None, manifest=None, *, mutable_tree=None, commit=None):
        self.tree = {**tree, "tree": list(tree.get("tree", []))}
        self.downloads = dict(downloads or {})
        self.manifest = manifest
        self.mutable_tree = mutable_tree
        self.commit = commit
        self.calls = []
        if manifest is not None and tree.get("sha"):
            data = json.dumps(manifest).encode("utf-8")
            self.tree["tree"].append({
                "path": "manifest.json", "mode": "100644", "type": "blob",
                "sha": resource_sync.git_blob_sha(data), "size": len(data),
            })
            self.downloads["manifest.json"] = data

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/commits/" in url:
            return FakeResponse(payload=self.commit or {
                "sha": "b" * 40,
                "commit": {"tree": {"sha": self.tree.get("sha")}},
            })
        if "/git/trees/" in url:
            if "/git/trees/main?" in url and self.mutable_tree is not None:
                return FakeResponse(payload=self.mutable_tree)
            return FakeResponse(payload=self.tree)
        if url == resource_sync.DISTRIBUTION_MANIFEST_URL and self.manifest is not None:
            return FakeResponse(payload=self.manifest)
        for path, content in self.downloads.items():
            entries = self.tree.get('tree', [])
            expected_sha = next((e['sha'] for e in entries if e['path'] == path), resource_sync.git_blob_sha(content))
            if url.endswith('/git/blobs/' + expected_sha):
                return FakeResponse(content=content)
            if url.endswith(path.replace(" ", "%20")):
                return FakeResponse(content=content)
        return FakeResponse(status_code=404)


class ResourceSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.installed = os.path.join(self.temp_dir.name, "installed")
        self.cache = os.path.join(self.temp_dir.name, "cache")
        self.cad = os.path.join(self.temp_dir.name, "cad")
        os.makedirs(self.installed)

        self.sincal_lsp = b"(defun c:SINCAL () (princ))\n"
        self.master = b"AC1032" + b"master-data"
        self.engine_helper = b"function Get-SincalCadEngine { 'test' }\n"
        self._write_installed("lisps/SINCAL.lsp", self.sincal_lsp)
        self._write_installed("masters/FORMATOS ANOTATIVOS ACAD_2025.dwg", self.master)
        self._write_installed("scripts/SINCAL_ENGINE.ps1", self.engine_helper)

        patch.object(resource_sync, "RUTA_RECURSOS_USUARIO", self.cache).start()
        patch.object(resource_sync, "ruta_recurso_instalado", side_effect=self._installed_path).start()
        patch.object(resource_sync, "ruta_recurso", side_effect=self._effective_path).start()
        patch.object(resource_sync, "ruta_cad_usuario", side_effect=self._cad_path).start()
        self.addCleanup(patch.stopall)
        resource_sync.materialize_cad_resources()

    def _installed_path(self, *parts):
        return os.path.join(self.installed, *parts)

    def test_materialize_registers_new_commands_and_repairs_stale_loaders(self):
        self._write_installed("lisps/PNDMAKE.lsp", b"(defun c:PNDMAKE () (princ))\n")
        resource_sync.materialize_cad_resources()
        for name in ("acaddoc.lsp", "zwcaddoc.lsp"):
            with open(self._cad_path(name), encoding="utf-8") as source:
                text = source.read()
            self.assertIn("/lisps/PNDMAKE.lsp", text)
            self.assertIn("vl-catch-all-apply", text)
            with open(self._cad_path(name), "w", encoding="utf-8") as target:
                target.write("; obsolete loader")
        self.assertEqual(resource_sync.materialize_cad_resources(), ())
        for name in ("acaddoc.lsp", "zwcaddoc.lsp"):
            with open(self._cad_path(name), encoding="utf-8") as source:
                self.assertIn("/lisps/PNDMAKE.lsp", source.read())

    def _effective_path(self, *parts):
        cached = os.path.join(self.cache, *parts)
        return cached if os.path.isfile(cached) else self._installed_path(*parts)

    def _cad_path(self, *parts):
        os.makedirs(self.cad, exist_ok=True)
        return os.path.join(self.cad, *parts)

    def _write_installed(self, relative, data):
        path = os.path.join(self.installed, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as target:
            target.write(data)

    @staticmethod
    def _tree_entry(path, data):
        return {
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": resource_sync.git_blob_sha(data),
            "size": len(data),
        }

    def _tree(self, extra=None):
        entries = [
            self._tree_entry("lisps/SINCAL.lsp", self.sincal_lsp),
            self._tree_entry("masters/FORMATOS ANOTATIVOS ACAD_2025.dwg", self.master),
            self._tree_entry("scripts/SINCAL_ENGINE.ps1", self.engine_helper),
            self._tree_entry("sincal/app.py", b"not-hot-updatable"),
        ]
        entries.extend(extra or [])
        return {"sha": "a" * 40, "truncated": False, "tree": entries}

    def test_detects_new_lisp_without_editing_a_manifest(self):
        new_lisp = b"(defun c:G45 () (princ))\n"
        tree = self._tree([self._tree_entry("lisps/G45.lsp", new_lisp)])
        session = FakeSession(tree, {"lisps/G45.lsp": new_lisp})

        plan = resource_sync.check_resource_updates(session=session)
        self.assertEqual([entry.path for entry in plan.changed], ["lisps/G45.lsp"])
        self.assertNotIn("sincal/app.py", [entry.path for entry in plan.resources])

        result = resource_sync.apply_resource_updates(plan, session=session)
        self.assertEqual(result.updated, ("lisps/G45.lsp",))
        with open(os.path.join(self.cache, "lisps", "G45.lsp"), "rb") as saved:
            self.assertEqual(saved.read(), new_lisp)

        copied = resource_sync.materialize_cad_resources()
        self.assertIn("lisps/G45.lsp", copied)
        self.assertTrue(os.path.isfile(os.path.join(self.cad, "lisps", "G45.lsp")))

        second_plan = resource_sync.check_resource_updates(session=session)
        self.assertFalse(second_plan.has_changes)

    def test_reads_lightweight_distribution_revision(self):
        revision = "d" * 40
        session = FakeSession({}, manifest={"source_commit": revision})

        with patch("time.time", return_value=125):
            result = resource_sync.distribution_manifest_revision(session=session)
            second_result = resource_sync.distribution_manifest_revision(session=session)

        self.assertEqual(result, revision)
        self.assertEqual(second_result, revision)
        url, kwargs = session.calls[0]
        self.assertEqual(url, resource_sync.DISTRIBUTION_MANIFEST_URL)
        self.assertRegex(kwargs["params"]["_sincal_check"], r"^[0-9a-f]{32}$")
        self.assertNotEqual(kwargs["params"], session.calls[1][1]["params"])
        self.assertEqual(kwargs["headers"]["Cache-Control"], "no-cache")

    def test_detects_publication_between_checks_in_same_minute_despite_stale_main_tree(self):
        old_tree = self._tree()
        session = FakeSession(old_tree, mutable_tree=old_tree)
        new_lisp = b'(defun c:NEW () (princ "new"))\n'
        new_tree = self._tree([self._tree_entry("lisps/NEW.lsp", new_lisp)])
        new_tree["sha"] = "c" * 40

        with patch("time.time", return_value=125):
            first = resource_sync.check_resource_updates(session=session)
            session.tree = new_tree
            second = resource_sync.check_resource_updates(session=session)

        self.assertFalse(first.has_changes)
        self.assertEqual(second.tree_sha, "c" * 40)
        self.assertEqual([entry.path for entry in second.changed], ["lisps/NEW.lsp"])
        commits = [(url, kwargs) for url, kwargs in session.calls if "/commits/" in url]
        self.assertEqual(len(commits), 2)
        self.assertTrue(all(url.endswith("/commits/main") for url, _ in commits))
        for _, kwargs in commits:
            self.assertEqual(kwargs["headers"]["Cache-Control"], "no-cache")
            self.assertRegex(kwargs["params"]["_sincal_check"], r"^[0-9a-f]{32}$")
        self.assertNotEqual(commits[0][1]["params"], commits[1][1]["params"])
        trees = [url for url, _ in session.calls if "/git/trees/" in url]
        self.assertEqual(trees, [
            resource_sync.distribution_api_url("git/trees/" + sha + "?recursive=1")
            for sha in ("a" * 40, "c" * 40)
        ])
        self.assertEqual(second.source_commit, "")

    def test_rejects_tree_that_does_not_match_resolved_public_commit(self):
        session = FakeSession(self._tree(), commit={
            "sha": "b" * 40, "commit": {"tree": {"sha": "c" * 40}},
        })
        with self.assertRaises(ValueError):
            resource_sync.check_resource_updates(session=session)
        self.assertFalse(os.path.exists(resource_sync.state_path()))

    def test_rejects_invalid_public_commit_before_fetching_tree(self):
        session = FakeSession(self._tree(), commit={
            "sha": "not-a-sha", "commit": {"tree": {"sha": "a" * 40}},
        })
        with self.assertRaises(ValueError):
            resource_sync.check_resource_updates(session=session)
        self.assertEqual(len(session.calls), 1)
        self.assertFalse(os.path.exists(resource_sync.state_path()))

    def test_records_source_commit_from_manifest_in_same_pinned_tree(self):
        revision = "d" * 40
        session = FakeSession(self._tree(), manifest={"source_commit": revision})
        # The floating manifest has already advanced. Only the manifest blob
        # belonging to the resolved tree is consistent with this update plan.
        session.manifest = {"source_commit": "e" * 40}
        plan = resource_sync.check_resource_updates(session=session)
        self.assertEqual(plan.source_commit, revision)
        result = resource_sync.apply_resource_updates(plan, session=session)
        self.assertEqual(result.source_commit, revision)
        with open(resource_sync.state_path(), encoding="utf-8") as saved:
            self.assertEqual(json.load(saved)["source_commit"], revision)
        pinned_url = (f"https://raw.githubusercontent.com/{resource_sync.DISTRIBUTION_OWNER}/"
                      f"{resource_sync.DISTRIBUTION_REPOSITORY}/{'b' * 40}/manifest.json")
        self.assertIn(pinned_url, [url for url, _ in session.calls])
        self.assertNotIn(resource_sync.DISTRIBUTION_MANIFEST_URL, [url for url, _ in session.calls])
        self.assertEqual(sum("api.github.com/" in url for url, _ in session.calls), 2)

    def test_rejects_manifest_blob_with_wrong_hash_or_invalid_source_revision(self):
        for failure in ("hash", "revision"):
            with self.subTest(failure=failure):
                revision = "d" * 40 if failure == "hash" else "not-a-sha"
                session = FakeSession(self._tree(), manifest={"source_commit": revision})
                if failure == "hash":
                    session.downloads["manifest.json"] = session.downloads["manifest.json"].replace(
                        b"d" * 40, b"e" * 40
                    )
                with self.assertRaises(ValueError):
                    resource_sync.check_resource_updates(session=session)
        self.assertFalse(os.path.exists(resource_sync.state_path()))

    def test_reuses_crlf_installed_startup_as_verified_lf(self):
        path = "startup/SINCAL_STARTUP.lsp"
        published = b"(vl-load-com)\n(princ)\n"
        self._write_installed(path, published.replace(b"\n", b"\r\n"))
        entry = resource_sync.ResourceEntry(path, resource_sync.git_blob_sha(published), len(published))
        plan = resource_sync.ResourceUpdatePlan("a" * 40, (entry,), (entry,), (), False)
        session = FakeSession({})
        resource_sync.apply_resource_updates(plan, session=session)
        with open(os.path.join(self.cache, *path.split("/")), "rb") as source:
            self.assertEqual(source.read(), published)
        self.assertEqual(session.calls, [])

    def test_preserves_exact_published_crlf(self):
        data = b"(princ)\r\n"
        self._write_installed("lisps/EXACT.lsp", data)
        entry = resource_sync.ResourceEntry("lisps/EXACT.lsp", resource_sync.git_blob_sha(data), len(data))
        self.assertEqual(resource_sync._download_resource(entry, FakeSession({})), data)

    def test_published_crlf_is_not_offered_again_after_successful_update(self):
        path = "lisps/EXACT.lsp"
        published = b'(defun c:EXACT () (princ "ok"))\r\n'
        session = FakeSession(self._tree([self._tree_entry(path, published)]), {path: published})
        plan = resource_sync.check_resource_updates(session=session)
        self.assertEqual([entry.path for entry in plan.changed], [path])
        resource_sync.apply_resource_updates(plan, session=session)
        resource_sync.materialize_cad_resources()
        with open(resource_sync.resource_cache_path(path), "rb") as saved:
            self.assertEqual(saved.read(), published)
        self.assertFalse(resource_sync.check_resource_updates(session=session).has_changes)

    def test_detects_same_size_binary_corruption_even_when_state_says_current(self):
        path = "masters/FORMATOS ANOTATIVOS ACAD_2025.dwg"
        session = FakeSession(self._tree())
        initial = resource_sync.check_resource_updates(session=session)
        resource_sync.apply_resource_updates(initial, session=session)
        corrupted = self.master[:-1] + b"!"
        self.assertEqual(len(corrupted), len(self.master))
        destination = resource_sync.resource_cache_path(path)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "wb") as saved:
            saved.write(corrupted)
        plan = resource_sync.check_resource_updates(session=session)
        self.assertEqual([entry.path for entry in plan.changed], [path])
        # The unchanged installed copy can repair the cache without downloading.
        session.calls.clear()
        resource_sync.apply_resource_updates(plan, session=session)
        self.assertEqual(session.calls, [])
        with open(destination, "rb") as saved:
            self.assertEqual(saved.read(), self.master)

    def test_repairs_stale_or_missing_cad_copy_using_verified_cache_without_download(self):
        path = "lisps/PURGEALL.lsp"
        published = b'(defun c:PURGEALL () (princ "fixed"))\n'
        self._write_installed(path, b'(defun c:PURGEALL () (princ "old"))\n')
        session = FakeSession(self._tree([self._tree_entry(path, published)]), {path: published})
        first = resource_sync.check_resource_updates(session=session)
        resource_sync.apply_resource_updates(first, session=session)
        # Simulate an interrupted update: download/state completed but activation
        # did not, or a later integration operation replaced the CAD copy.
        for stale in (None, b"; old integration copy\n"):
            with self.subTest(stale=stale is not None):
                cad_file = self._cad_path(*path.split("/"))
                if stale is None:
                    if os.path.isfile(cad_file):
                        os.remove(cad_file)
                else:
                    os.makedirs(os.path.dirname(cad_file), exist_ok=True)
                    with open(cad_file, "wb") as saved:
                        saved.write(stale)
                plan = resource_sync.check_resource_updates(session=session)
                self.assertEqual([entry.path for entry in plan.changed], [path])
                session.calls.clear()
                resource_sync.apply_resource_updates(plan, session=session)
                self.assertEqual(session.calls, [])
                resource_sync.materialize_cad_resources()
                with open(cad_file, "rb") as saved:
                    self.assertEqual(saved.read(), published)
                self.assertFalse(resource_sync.check_resource_updates(session=session).has_changes)

    def test_check_before_first_cad_integration_does_not_offer_unchanged_resources(self):
        os.remove(self._cad_path(".sincal_resources.json"))
        os.remove(self._cad_path("lisps", "SINCAL.lsp"))
        plan = resource_sync.check_resource_updates(session=FakeSession(self._tree()))
        self.assertFalse(plan.has_changes)

    def test_loader_failure_remains_repairable_even_when_all_resource_bytes_are_current(self):
        session = FakeSession(self._tree())
        current = resource_sync.check_resource_updates(session=session)
        resource_sync.apply_resource_updates(current, session=session)
        self.assertFalse(current.has_changes)
        for name in ("acaddoc.lsp", "zwcaddoc.lsp"):
            with open(self._cad_path(name), "w", encoding="utf-8") as saved:
                saved.write("; obsolete loader")

        with patch.object(resource_sync, "write_cad_loaders", side_effect=OSError("loader locked")):
            with self.assertRaisesRegex(OSError, "loader locked"):
                resource_sync.materialize_cad_resources()

        repair = resource_sync.check_resource_updates(session=session)
        self.assertTrue(repair.has_changes)
        self.assertTrue(all(entry.path.startswith(resource_sync.CAD_RESOURCE_PREFIXES)
                            for entry in repair.changed))
        session.calls.clear()
        resource_sync.apply_resource_updates(repair, session=session)
        self.assertEqual(session.calls, [])
        resource_sync.materialize_cad_resources()
        self.assertFalse(resource_sync.check_resource_updates(session=session).has_changes)
        for name in ("acaddoc.lsp", "zwcaddoc.lsp"):
            with open(self._cad_path(name), encoding="utf-8") as saved:
                self.assertIn("/lisps/SINCAL.lsp", saved.read())

    def test_does_not_normalize_downloaded_or_binary_bytes(self):
        for path, data in (("lisps/REMOTE.lsp", b"(princ)\n"),
                           ("masters/FORMATOS ANOTATIVOS ACAD_2025.dwg", b"AC1032\nbody")):
            with self.subTest(path=path):
                changed = data.replace(b"\n", b"\r\n")
                self._write_installed(path, changed if path.endswith(".dwg") else b"old")
                entry = resource_sync.ResourceEntry(path, resource_sync.git_blob_sha(data), len(data))
                with self.assertRaisesRegex(ValueError, "Tamaño|SHA"):
                    resource_sync._download_resource(entry, FakeSession({'tree':[{'path':path,'sha':entry.sha}]}, {path: changed}))

    def test_download_is_pinned_to_planned_blob_not_mutable_branch(self):
        data=b'(princ "pinned")\n'
        entry=resource_sync.ResourceEntry('lisps/PINNED.lsp',resource_sync.git_blob_sha(data),len(data))
        session=FakeSession({}, {entry.path:data})
        self.assertEqual(resource_sync._download_resource(entry,session),data)
        self.assertTrue(session.calls[0][0].endswith('/git/blobs/'+entry.sha))
        self.assertEqual(session.calls[0][1]['headers']['Accept'],'application/vnd.github.raw+json')

    def test_planned_download_uses_pinned_cdn_commit_when_branch_has_advanced(self):
        path = "lisps/PINNED.lsp"
        published = b'(princ "planned")\n'
        advanced = b'(princ "advanced")\n'

        class AdvancedMainSession(FakeSession):
            def get(self, url, **kwargs):
                if url.endswith("/main/" + path):
                    self.calls.append((url, kwargs))
                    return FakeResponse(content=advanced)
                return super().get(url, **kwargs)

        session = AdvancedMainSession(self._tree([self._tree_entry(path, published)]),
                                      {path: published})
        plan = resource_sync.check_resource_updates(session=session)
        entry = next(e for e in plan.changed if e.path == path)
        self.assertEqual(entry.publication_commit, "b" * 40)
        session.calls.clear()
        resource_sync.apply_resource_updates(plan, session=session)
        pinned_url = (f"https://raw.githubusercontent.com/{resource_sync.DISTRIBUTION_OWNER}/"
                      f"{resource_sync.DISTRIBUTION_REPOSITORY}/{'b' * 40}/{path}")
        self.assertEqual([url for url, _ in session.calls], [pinned_url])
        with open(resource_sync.resource_cache_path(path), "rb") as saved:
            self.assertEqual(saved.read(), published)

    def test_rejects_invalid_distribution_revision(self):
        session = FakeSession({}, manifest={"source_commit": "not-a-sha"})

        with self.assertRaisesRegex(ValueError, "revisión válida"):
            resource_sync.distribution_manifest_revision(session=session)

    def test_downloads_regional_map_only_when_requested(self):
        regional_map = b"\x89PNG\r\n\x1a\nregional-map"
        relative = "mapas/Region_Test.png"
        tree = self._tree([self._tree_entry(relative, regional_map)])
        session = FakeSession(tree, {relative: regional_map})

        plan = resource_sync.check_resource_updates(session=session)
        self.assertNotIn(relative, [entry.path for entry in plan.changed])

        downloaded = resource_sync.ensure_resource_available(relative, session=session)
        self.assertEqual(downloaded, os.path.join(self.cache, "mapas", "Region_Test.png"))
        with open(downloaded, "rb") as saved:
            self.assertEqual(saved.read(), regional_map)

    def test_rejects_tampered_master(self):
        published = b"AC1032" + b"new-master"
        tampered = b"AC1032" + b"tampered!!"
        entry = resource_sync.ResourceEntry(
            "masters/FORMATOS ANOTATIVOS ACAD_2025.dwg",
            resource_sync.git_blob_sha(published),
            len(published),
        )
        plan = resource_sync.ResourceUpdatePlan(
            tree_sha="b" * 40,
            resources=(entry,),
            changed=(entry,),
            removed=(),
            initial=False,
        )
        session = FakeSession({'tree':[{'path':entry.path,'sha':entry.sha}]}, {entry.path: tampered})

        with self.assertRaisesRegex(ValueError, "SHA|Tamaño"):
            resource_sync.apply_resource_updates(plan, session=session)
        self.assertFalse(os.path.exists(os.path.join(self.cache, "masters", os.path.basename(entry.path))))

    def test_detects_removed_lisp(self):
        old_lisp = b"(defun c:OLD () (princ))\n"
        first_tree = self._tree([self._tree_entry("lisps/OLD.lsp", old_lisp)])
        first_session = FakeSession(first_tree, {"lisps/OLD.lsp": old_lisp})
        first_plan = resource_sync.check_resource_updates(session=first_session)
        resource_sync.apply_resource_updates(first_plan, session=first_session)

        second_tree = self._tree()
        second_tree["sha"] = "c" * 40
        second_plan = resource_sync.check_resource_updates(session=FakeSession(second_tree))
        self.assertEqual(second_plan.removed, ("lisps/OLD.lsp",))


if __name__ == "__main__":
    unittest.main()
