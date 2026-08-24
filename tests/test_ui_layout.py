import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkbenchLayoutTests(unittest.TestCase):
    def test_primary_navigation_is_ordered_and_not_tabview_based(self):
        source = (ROOT / "core_sincal.py").read_text(encoding="utf-8")
        expected = [
            '"sincronizador", "⌂  Sincronizador"',
            '"comandos", "⌘  Comandos en vivo"',
            '"documentacion", "▤  Documentación"',
            '"procesamiento", "▣  Renombrado"',
            '"ubicacion", "⌖  Ubicación"',
            '"estructural", "▦  Módulo estructural"',
        ]
        positions = [source.index(item) for item in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("CTkTabview", source)
        self.assertNotIn("consola_scripts", source)
        self.assertNotIn("Automatización de planos cerrados", source)
        self.assertNotIn("lanzar_script", source)

    def test_console_is_dockable_and_dxf_is_a_separate_module(self):
        source = (ROOT / "core_sincal.py").read_text(encoding="utf-8")
        self.assertIn('"Consola: inferior"', source)
        self.assertIn('"Consola: derecha"', source)
        self.assertIn("def setup_tab_conversion_dxf", source)
        self.assertIn('"conversion", "⇄  Conversión DXF"', source)
        self.assertIn("def ocultar_menu_lateral", source)
        self.assertIn("def cambiar_tamano_letra", source)
        self.assertIn("def cambiar_tema", source)
        self.assertNotIn("#007FFF", source)

    def test_private_fonts_are_supplied_in_the_application_payload(self):
        theme = (ROOT / "sincal_ui.py").read_text(encoding="utf-8")
        build = (ROOT / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn('("Consolas", 28, "bold")', theme)
        self.assertIn('("Roboto Mono", 13)', theme)
        self.assertIn('("Consolas", 11)', theme)
        self.assertIn("RobotoMono.ttf", build)

    def test_modules_import_the_small_body_font_when_using_it(self):
        for relative in ("modulos/tab_armaduras.py", "modulos/tab_ubicacion.py"):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("FUENTE_NORMAL_PEQUENA,", source, relative)

    def test_structural_documentation_defines_the_approved_glossary(self):
        import json

        docs = json.loads((ROOT / "tutoriales.json").read_text(encoding="utf-8"))
        topics = {topic["id"]: topic for topic in docs["temas"]}
        self.assertIn("estribos-glosario", topics)
        glossary = topics["estribos-glosario"]["contenido"]
        self.assertIn("CTF — Contrafuerte", glossary)
        self.assertNotIn("CON — Contrafuerte", glossary)
        self.assertIn("EE (planta de fundación)", topics["estribos-vistas-y-capas"]["contenido"])


if __name__ == "__main__":
    unittest.main()
