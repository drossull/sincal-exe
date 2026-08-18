import os
import tempfile
import unittest
from unittest.mock import patch

import sincal_resource_sync as resource_sync


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
    def __init__(self, tree, downloads=None, manifest=None):
        self.tree = tree
        self.downloads = downloads or {}
        self.manifest = manifest
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/git/trees/" in url:
            return FakeResponse(payload=self.tree)
        if url.endswith("/manifest.json") and self.manifest is not None:
            return FakeResponse(payload=self.manifest)
        for path, content in self.downloads.items():
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
        self._write_installed("lisps/SINCAL.lsp", self.sincal_lsp)
        self._write_installed("masters/FORMATOS ANOTATIVOS ACAD_2025.dwg", self.master)

        patch.object(resource_sync, "RUTA_RECURSOS_USUARIO", self.cache).start()
        patch.object(resource_sync, "ruta_recurso_instalado", side_effect=self._installed_path).start()
        patch.object(resource_sync, "ruta_recurso", side_effect=self._effective_path).start()
        patch.object(resource_sync, "ruta_cad_usuario", side_effect=self._cad_path).start()
        self.addCleanup(patch.stopall)

    def _installed_path(self, *parts):
        return os.path.join(self.installed, *parts)

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
            self._tree_entry("core_sincal.py", b"not-hot-updatable"),
        ]
        entries.extend(extra or [])
        return {"sha": "a" * 40, "truncated": False, "tree": entries}

    def test_detects_new_lisp_without_editing_a_manifest(self):
        new_lisp = b"(defun c:G45 () (princ))\n"
        tree = self._tree([self._tree_entry("lisps/G45.lsp", new_lisp)])
        session = FakeSession(tree, {"lisps/G45.lsp": new_lisp})

        plan = resource_sync.check_resource_updates(session=session)
        self.assertEqual([entry.path for entry in plan.changed], ["lisps/G45.lsp"])
        self.assertNotIn("core_sincal.py", [entry.path for entry in plan.resources])

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

        with patch.object(resource_sync.time, "time", return_value=125):
            result = resource_sync.distribution_manifest_revision(session=session)

        self.assertEqual(result, revision)
        url, kwargs = session.calls[0]
        self.assertEqual(url, resource_sync.DISTRIBUTION_MANIFEST_URL)
        self.assertEqual(kwargs["params"], {"minute": 2})
        self.assertEqual(kwargs["headers"]["Cache-Control"], "no-cache")

    def test_rejects_invalid_distribution_revision(self):
        session = FakeSession({}, manifest={"source_commit": "not-a-sha"})

        with self.assertRaisesRegex(ValueError, "revisión válida"):
            resource_sync.distribution_manifest_revision(session=session)

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
        session = FakeSession({}, {entry.path: tampered})

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
