import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkbenchLayoutTests(unittest.TestCase):
    def test_primary_navigation_is_ordered_and_not_tabview_based(self):
        source = (ROOT / "core_sincal.py").read_text(encoding="utf-8")
        expected = [
            '"sincronizador", "⌂  Sincronizador"',
            '"documentacion", "▤  Documentación"',
            '"procesamiento", "▣  Procesamiento masivo"',
            '"ubicacion", "⌖  Ubicación"',
            '"estructural", "▦  Módulo estructural"',
        ]
        positions = [source.index(item) for item in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("CTkTabview", source)
        self.assertNotIn("consola_scripts", source)

    def test_console_is_dockable_and_dxf_is_a_separate_module(self):
        source = (ROOT / "core_sincal.py").read_text(encoding="utf-8")
        self.assertIn('"Consola: inferior"', source)
        self.assertIn('"Consola: derecha"', source)
        self.assertIn("def setup_tab_conversion_dxf", source)
        self.assertIn('"conversion", "⇄  Conversión DXF"', source)

    def test_private_fonts_are_supplied_in_the_application_payload(self):
        theme = (ROOT / "sincal_ui.py").read_text(encoding="utf-8")
        build = (ROOT / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn('("Workbench", 32)', theme)
        self.assertIn('("Passion One", 22)', theme)
        self.assertIn('("Lekton", 13)', theme)
        self.assertIn('("Consolas", 11)', theme)
        self.assertIn("Join-Path $ProjectRoot 'assets'", build)


if __name__ == "__main__":
    unittest.main()
