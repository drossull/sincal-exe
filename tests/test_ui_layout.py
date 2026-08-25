import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "sincal" / "app.py"
THEME = ROOT / "sincal" / "ui" / "theme.py"
ICONS = ROOT / "sincal" / "ui" / "icons.py"
ARMADURAS = ROOT / "sincal" / "ui" / "tabs" / "armaduras.py"
DOCUMENTACION = ROOT / "sincal" / "ui" / "tabs" / "documentacion.py"


class WorkbenchLayoutTests(unittest.TestCase):
    def test_primary_navigation_is_ordered_and_not_tabview_based(self):
        source = APP.read_text(encoding="utf-8")
        expected = [
            '"sincronizador", "home", "Sincronizador"',
            '"comandos", "terminal", "Comandos en vivo"',
            '"documentacion", "book", "Documentación"',
            '"procesamiento", "rename", "Renombrado"',
            '"ubicacion", "pin", "Ubicación"',
            '"estructural", "structure", "Módulo estructural"',
        ]
        positions = [source.index(item) for item in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("CTkTabview", source)
        self.assertNotIn("consola_scripts", source)
        self.assertNotIn("Automatización de planos cerrados", source)
        self.assertNotIn("lanzar_script", source)

    def test_console_is_dockable_and_dxf_is_a_separate_module(self):
        source = APP.read_text(encoding="utf-8")
        self.assertIn('"Consola: inferior"', source)
        self.assertIn('"Consola: derecha"', source)
        self.assertIn("def setup_tab_conversion_dxf", source)
        self.assertIn('"conversion", "convert", "Conversión DXF"', source)
        self.assertIn("def ocultar_menu_lateral", source)
        self.assertIn("def cambiar_tamano_letra", source)
        self.assertIn("def cambiar_tema", source)
        self.assertIn("def _construir_menu_superior", source)
        self.assertIn("def seleccionar_tema_ttk", source)
        self.assertIn('ver.add_cascade(label="Tema ttkbootstrap"', source)
        self.assertIn("self.bootstrap_style.theme_names()", source)
        self.assertIn("self.font_slider = ttk.Scale", source)
        self.assertIn("def _redimensionar_menu", source)
        self.assertIn("def _redimensionar_consola", source)
        self.assertNotIn("self.log_rename", source)
        self.assertNotIn("#007FFF", source)

    def test_private_fonts_are_supplied_in_the_application_payload(self):
        theme = THEME.read_text(encoding="utf-8")
        build = (ROOT / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn('FAMILIA_PRESSURA = "GT Pressura"', theme)
        self.assertIn('FAMILIA_PRESSURA_BOLD = "GTPressura-Bold"', theme)
        self.assertIn('(FAMILIA_PRESSURA_BOLD, 28)', theme)
        self.assertIn('(FAMILIA_PRESSURA, 13)', theme)
        self.assertIn('("Consolas", 11)', theme)
        self.assertIn("GT Pressura Regular.ttf", build)
        self.assertIn('TTK_PRESET_OSCURO = "nord"', theme)
        self.assertIn("ThemeDefinition(", theme)
        self.assertIn('TTK_PRESET_CLARO = "sandstone"', theme)
        self.assertIn('COLOR_FONDO = ("#F8F5F0", _NORD_COLORS["bg"])', theme)
        self.assertTrue((ROOT / "assets" / "fonts" / "GT Pressura Regular.ttf").is_file())
        self.assertTrue((ROOT / "assets" / "fonts" / "GTPressura-Bold.ttf").is_file())

    def test_bootstrap_preset_icons_and_responsive_shell_are_integrated(self):
        core = APP.read_text(encoding="utf-8")
        icons = ICONS.read_text(encoding="utf-8")
        requirements = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
        self.assertIn("crear_estilo_bootstrap()", core)
        self.assertIn("def _adaptar_layout_principal", core)
        self.assertIn("def _reordenar_acciones_inicio", core)
        self.assertIn("width < 1080", core)
        self.assertIn("obtener_icono(icon_name, 18)", core)
        self.assertIn("def obtener_icono", icons)
        self.assertIn("ttkbootstrap==1.18.2", requirements)

    def test_responsive_panels_and_single_console(self):
        core = APP.read_text(encoding="utf-8")
        docs = DOCUMENTACION.read_text(encoding="utf-8")
        structural = ARMADURAS.read_text(encoding="utf-8")
        self.assertIn("def _redimensionar_panel", docs)
        self.assertIn("wraplength=wrap", docs)
        self.assertIn("ttk.Panedwindow", structural)
        self.assertIn("self.ruta_adv_var", core)
        self.assertIn("self.ruta_conversion_var", core)
        self.assertNotIn("self.lbl_ruta_adv", core)
        self.assertNotIn("self.lbl_ruta_conversion", core)

    def test_modules_import_the_small_body_font_when_using_it(self):
        for path in (ARMADURAS, ROOT / "sincal" / "ui" / "tabs" / "ubicacion.py"):
            source = path.read_text(encoding="utf-8")
            self.assertIn("FUENTE_NORMAL_PEQUENA,", source, str(path))

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
        source = ARMADURAS.read_text(encoding="utf-8")
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
        self.assertIn("build_zapata_lisp", source)
        self.assertIn("build_zapata_detail_lisp", source)
        self.assertIn("ttk.Notebook", source)
        self.assertIn("ttk.Spinbox", source)
        self.assertIn("ttk.Checkbutton", source)
        self.assertIn("ttk.Radiobutton", source)
        self.assertIn("ttk.Progressbar", source)
        self.assertIn("Tableview(", source)
        self.assertIn("ToolTip(", source)
        self.assertIn("ttk.Separator", source)
        self.assertIn("def mostrar_vista_previa_marcas", source)
        self.assertIn("def generar_despiece_zapata", source)
        self.assertIn('text="Generar despiece general de zapata"', source)
        self.assertNotIn("def generar_despiece_cad", source)
        self.assertIn('"FORMATOS ANOTATIVOS ACAD_2025.dwg"', source)
        self.assertIn("SINCAL-ZAPATA-GENERAR", source)
        self.assertIn('("D-D", "DD")', source)
        self.assertIn('("E-E", "EE")', source)
        self.assertNotIn("self.ent_phi_inf", source)
        self.assertNotIn("self.ent_espac_inf", source)

    def test_zapata_moldajes_are_read_from_the_active_cad_document_only(self):
        core = APP.read_text(encoding="utf-8")
        structural = ARMADURAS.read_text(encoding="utf-8")
        self.assertIn("def enviar_comando_cad_activo", core)
        self.assertIn("app.ActiveDocument", core)
        self.assertIn("GetRunningObjectTable", core)
        self.assertIn("QueryInterface(pythoncom.IID_IDispatch)", core)
        self.assertIn("def detectar_moldajes_cad", structural)
        self.assertIn("def confirmar_moldajes_cad", structural)
        self.assertIn("INSUNITS", structural)

    def test_header_uses_breadcrumb_without_duplicate_console_selector(self):
        core = APP.read_text(encoding="utf-8")
        structural = ARMADURAS.read_text(encoding="utf-8")
        self.assertIn("def actualizar_ruta_interna", core)
        self.assertIn('route = " > ".join', core)
        self.assertIn("def actualizar_breadcrumb", structural)
        self.assertNotIn("self.console_menu =", core)
        self.assertNotIn("self.theme_menu =", core)
        self.assertIn("Creado por Gonzalo Mardones V.", core)

    def test_active_moldaje_detection_keeps_a_valid_com_connection(self):
        core = APP.read_text(encoding="utf-8")
        structural = ARMADURAS.read_text(encoding="utf-8")
        active_worker = core.split("def _hilo_comando_cad_activo", 1)[1].split(
            "def _hilo_comando_en_vivo", 1)[0]
        self.assertNotIn('SendCommand("\\x03\\x03")', active_worker)
        self.assertIn('(progn (load', structural)
        self.assertIn('(c:SINCAL-DETECTAR-ZAPATA))\\n', structural)


if __name__ == "__main__":
    unittest.main()
