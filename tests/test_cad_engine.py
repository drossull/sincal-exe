import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sincal.cad import engine as cad_engine


class CadEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.runtime = self.root / "runtime"

    def _fake_engine(self, relative):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"MZ-fake-engine")
        return path

    def test_prefers_supported_2025_headless_engine(self):
        engine_2025 = self._fake_engine("Autodesk/AutoCAD 2025/accoreconsole.exe")
        engine_2027 = self._fake_engine("Autodesk/AutoCAD 2027/accoreconsole.exe")
        self._fake_engine("ZWSOFT/ZWCAD 2026/zwcad.exe")

        engines = cad_engine.discover_cad_engines([str(self.root)])

        self.assertEqual(Path(engines[0].path), engine_2025)
        self.assertEqual(Path(engines[1].path), engine_2027)
        self.assertTrue(engines[0].headless)
        self.assertFalse(engines[-1].headless)

    def test_persists_selection_and_compatibility_wrapper(self):
        engine_path = self._fake_engine("Autodesk/AutoCAD 2027/accoreconsole.exe")
        engine = cad_engine.discover_cad_engines([str(self.root)])[0]

        with patch.object(cad_engine, "ruta_runtime", side_effect=lambda *parts: str(self.runtime.joinpath(*parts))):
            selected = cad_engine.save_engine_selection(engine, (engine,))
            loaded = cad_engine.load_engine_state()
            state = json.loads((self.runtime / "cad_engine.json").read_text(encoding="utf-8"))
            wrapper = (self.runtime / "cad_wrapper.bat").read_text(encoding="utf-8")

        self.assertEqual(Path(selected.path), engine_path)
        self.assertEqual(Path(loaded.path), engine_path)
        self.assertEqual(state["selected"]["year"], 2027)
        self.assertIn(str(engine_path), wrapper)

    def test_cmd_launchers_use_builtin_powershell_and_support_zwcad_com(self):
        scripts = Path(__file__).resolve().parents[1] / "scripts"
        for launcher in scripts.glob("*.bat"):
            source = launcher.read_text(encoding="utf-8").lower()
            self.assertIn("windowspowershell\\v1.0\\powershell.exe", source, launcher.name)
            self.assertNotIn("\npwsh ", source, launcher.name)
        engine_helper = (scripts / "SINCAL_ENGINE.ps1").read_text(encoding="utf-8")
        self.assertIn("accoreconsole.exe", engine_helper)
        self.assertIn("ZWCAD.Application", engine_helper)
        self.assertIn("Invoke-SincalZwcadScript", engine_helper)
        self.assertIn('$application.Visible = $false', engine_helper)
        self.assertIn('Get-Process -Name ZWCAD', engine_helper)
        self.assertIn('Stop-Process -Id $createdProcessId', engine_helper)
        for script in scripts.glob("*.ps1"):
            if script.name == "SINCAL_ENGINE.ps1":
                continue
            source = script.read_text(encoding="utf-8")
            self.assertIn("Invoke-SincalCadScript", source, script.name)


if __name__ == "__main__":
    unittest.main()
