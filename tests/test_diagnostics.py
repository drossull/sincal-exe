import json
import os
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import sincal_diagnostics as diagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_redacts_identity_paths_and_email(self):
        environment = {
            "USERPROFILE": r"C:\Users\Colega",
            "LOCALAPPDATA": r"C:\Users\Colega\AppData\Local",
            "APPDATA": r"C:\Users\Colega\AppData\Roaming",
            "USERNAME": "Colega",
            "COMPUTERNAME": "PC-PUENTES",
        }
        with patch.dict(os.environ, environment, clear=False):
            text = diagnostics.redact_text(
                r"C:\Users\Colega\Proyecto\plano-secreto.dwg | PC-PUENTES | colega@empresa.cl",
                (r"C:\Users\Colega\Proyecto",),
            )

        self.assertNotIn("Colega", text)
        self.assertNotIn("PC-PUENTES", text)
        self.assertNotIn("colega@empresa.cl", text)
        self.assertNotIn("plano-secreto", text)
        self.assertIn("<PROYECTO>", text)
        self.assertIn("<EMAIL>", text)

    def test_bundle_contains_only_diagnostic_documents(self):
        report = {
            "report_id": "ABC12345",
            "created_at": "2026-08-18T12:00:00-04:00",
            "application": {"version": "v29.0.2"},
            "findings": [{"level": "ok", "message": "Sin bloqueos"}],
            "cad": {"selected": None, "engines": [], "legacy_wrapper_exists": False},
            "resources": {"expected_lisp_count": 21, "active_lisp_count": 21},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = os.path.join(temp_dir, "informe.zip")
            with (
                patch.object(diagnostics, "collect_diagnostics", return_value=report),
                patch.object(diagnostics, "_tail_text", return_value="registro anonimizado"),
            ):
                saved, returned = diagnostics.create_diagnostic_bundle(destination)

            with zipfile.ZipFile(saved) as archive:
                names = set(archive.namelist())
                payload = json.loads(archive.read("diagnostico.json"))

        self.assertEqual(returned["report_id"], "ABC12345")
        self.assertEqual(
            names,
            {"diagnostico.json", "resumen.txt", "sincal.log", "PRIVACIDAD.txt"},
        )
        self.assertFalse(any(name.lower().endswith(".dwg") for name in names))
        self.assertEqual(payload["report_id"], "ABC12345")

    def test_incidents_are_local_json_lines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(diagnostics, "diagnostics_directory", return_value=temp_dir):
                diagnostics.record_incident(
                    "procesamiento_masivo",
                    "error",
                    {"returncode": 1, "path": r"C:\Proyectos\Cliente\secreto.dwg"},
                    sensitive_paths=(r"C:\Proyectos\Cliente",),
                )
                events = diagnostics.load_incidents()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["operation"], "procesamiento_masivo")
        self.assertEqual(events[0]["details"]["returncode"], 1)
        self.assertNotIn("Cliente", events[0]["details"]["path"])


if __name__ == "__main__":
    unittest.main()
