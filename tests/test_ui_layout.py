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
        self.assertIn("def _construir_menu_superior", source)
        self.assertIn("self.font_slider = ctk.CTkSlider", source)
        self.assertIn("def _redimensionar_menu", source)
        self.assertIn("def _redimensionar_consola", source)
        self.assertNotIn("self.log_rename", source)
        self.assertNotIn("#007FFF", source)

    def test_private_fonts_are_supplied_in_the_application_payload(self):
        theme = (ROOT / "sincal_ui.py").read_text(encoding="utf-8")
        build = (ROOT / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn('FAMILIA_PRESSURA = "GT Pressura"', theme)
        self.assertIn('FAMILIA_PRESSURA_BOLD = "GTPressura-Bold"', theme)
        self.assertIn('(FAMILIA_PRESSURA_BOLD, 28)', theme)
        self.assertIn('(FAMILIA_PRESSURA, 13)', theme)
        self.assertIn('("Consolas", 11)', theme)
        self.assertIn("GT Pressura Regular.ttf", build)
        self.assertIn('COLOR_FONDO = ("#F1E7D8", "#1E1E1E")', theme)
        self.assertTrue((ROOT / "assets" / "fonts" / "GT Pressura Regular.ttf").is_file())
        self.assertTrue((ROOT / "assets" / "fonts" / "GTPressura-Bold.ttf").is_file())

    def test_responsive_panels_and_single_console(self):
        core = (ROOT / "core_sincal.py").read_text(encoding="utf-8")
        docs = (ROOT / "modulos" / "tab_docs.py").read_text(encoding="utf-8")
        structural = (ROOT / "modulos" / "tab_armaduras.py").read_text(encoding="utf-8")
        self.assertIn("def _redimensionar_panel", docs)
        self.assertIn("wraplength=wrap", docs)
        self.assertIn("def _redimensionar_estribo", structural)
        self.assertIn("self.ruta_adv_var", core)
        self.assertIn("self.ruta_conversion_var", core)
        self.assertNotIn("self.lbl_ruta_adv", core)
        self.assertNotIn("self.lbl_ruta_conversion", core)

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

    def test_zapata_review_is_backed_by_the_parametric_rebar_model(self):
        source = (ROOT / "modulos" / "tab_armaduras.py").read_text(encoding="utf-8")
        self.assertIn('"Estribo de entrada"', source)
        self.assertIn('"Estribo de salida"', source)
        self.assertIn('text="REVISIÓN Y MARCAS"', source)
        self.assertIn("CTkScrollableFrame", source)
        self.assertIn('("2. MUROS",', source)
        self.assertIn('("3. CONSOLAS",', source)
        self.assertIn('("4. TOPES",', source)
        self.assertIn('("5. CONTRAFUERTE",', source)
        self.assertIn('self._abutments = {}', source)
        self.assertIn("default_zapata_rules", source)
        self.assertIn("def actualizar_revision_zapata", source)
        self.assertIn('("D-D", "DD")', source)
        self.assertIn('("E-E", "EE")', source)
        self.assertNotIn("self.ent_phi_inf", source)
        self.assertNotIn("self.ent_espac_inf", source)

    def test_zapata_moldajes_are_read_from_the_active_cad_document_only(self):
        core = (ROOT / "core_sincal.py").read_text(encoding="utf-8")
        structural = (ROOT / "modulos" / "tab_armaduras.py").read_text(encoding="utf-8")
        self.assertIn("def enviar_comando_cad_activo", core)
        self.assertIn("app.ActiveDocument", core)
        self.assertIn("GetRunningObjectTable", core)
        self.assertIn("QueryInterface(pythoncom.IID_IDispatch)", core)
        self.assertIn("def detectar_moldajes_cad", structural)
        self.assertIn("def confirmar_moldajes_cad", structural)
        self.assertIn("INSUNITS", structural)


if __name__ == "__main__":
    unittest.main()
