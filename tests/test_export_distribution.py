import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.export_distribution import export_distribution


class DistributionExportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.source = Path(self.temp_dir.name) / "source"
        self.destination = Path(self.temp_dir.name) / "distribution"
        self.source.mkdir()
        self.destination.mkdir()
        self._write("version.json", b'{"version":"v28.0.1"}')
        self._write("lisps/SINCAL.lsp", b"(princ)\n")
        self._write("masters/FORMATOS ANOTATIVOS ACAD_2025.dwg", b"AC1032master")
        self._write("scripts/SINCAL_ENGINE.ps1", b"function Get-SincalCadEngine { 'test' }\n")

    def _write(self, relative, data):
        path = self.source / Path(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def test_exports_only_allowed_resources_and_manifest(self):
        self._write("lisps/G45.lsp", b"(defun c:G45 () (princ))\n")
        self._write("core_sincal.py", b"private source")

        result = export_distribution(
            self.source,
            self.destination,
            source_commit="a" * 40,
        )

        self.assertIn("lisps/G45.lsp", result["copied"])
        self.assertTrue((self.destination / "lisps" / "G45.lsp").is_file())
        self.assertFalse((self.destination / "core_sincal.py").exists())
        manifest = json.loads((self.destination / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["release"], "v28.0.1")
        self.assertEqual(manifest["source_commit"], "a" * 40)
        self.assertIn("lisps/G45.lsp", manifest["resources"])

    def test_removes_a_resource_deleted_from_private_source(self):
        self._write("lisps/OLD.lsp", b"(princ)\n")
        export_distribution(self.source, self.destination)
        os.remove(self.source / "lisps" / "OLD.lsp")

        result = export_distribution(self.source, self.destination)

        self.assertEqual(result["removed"], ("lisps/OLD.lsp",))
        self.assertFalse((self.destination / "lisps" / "OLD.lsp").exists())


if __name__ == "__main__":
    unittest.main()
