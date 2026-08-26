import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
APP = ROOT / "sincal" / "app.py"
THEME = ROOT / "sincal" / "ui" / "theme.py"
ICONS = ROOT / "sincal" / "ui" / "icons.py"
ACTIVITY = ROOT / "sincal" / "ui" / "activity.py"
ARMADURAS = ROOT / "sincal" / "ui" / "tabs" / "armaduras.py"
DOCUMENTACION = ROOT / "sincal" / "ui" / "tabs" / "documentacion.py"


class WorkbenchLayoutTests(unittest.TestCase):
    def test_primary_navigation_is_ordered_and_not_tabview_based(self):
        source = APP.read_text(encoding="utf-8")
        expected = [
            '"sincronizador", "home", "Home"',
            '"documentacion", "book", "Documentación"',
            '"comandos", "terminal", "Comandos en vivo"',
            '"conversion", "convert", "Conversión DXF–DWG"',
            '"procesamiento", "rename", "Renombrado"',
            '"ubicacion", "pin", "Ubicación"',
            '"estructural", "structure", "Generador de armadura"',
            '"diagnostico", "diagnostic", "Diagnóstico"',
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
        self.assertNotIn('"Consola: derecha"', source)
        self.assertIn("def setup_tab_conversion_dxf", source)
        self.assertIn('"conversion", "convert", "Conversión DXF–DWG"', source)
        self.assertIn("def ocultar_menu_lateral", source)
        self.assertIn("def cambiar_tamano_letra", source)
        self.assertIn("def cambiar_tema", source)
        self.assertIn("def _construir_menu_superior", source)
        self.assertIn('label="Consola", variable=self._console_visible_var', source)
        self.assertIn('self.menu_ver.add_cascade(label="Zoom texto · 100 %"', source)
        self.assertIn('self.menu_ver.add_cascade(label="Tema"', source)
        self.assertIn('for label in ("Tema oscuro", "Tema claro", "Tema del sistema")', source)
        self.assertIn('label=label.replace("Tema ", "").title()', source)
        self.assertNotIn("self.font_slider", source)
        self.assertNotIn('text="Aa"', source)
        self.assertNotIn("font_controls", source)
        self.assertIn('("Aa  ·  90 %", 0.90)', source)
        self.assertIn('("Aa  ·  100 %", 1.00)', source)
        self.assertIn('("Aa  ·  115 %", 1.15)', source)
        self.assertIn("def _redimensionar_menu", source)
        self.assertIn("def _redimensionar_consola", source)
        self.assertNotIn("self.log_rename", source)
        self.assertNotIn("#007FFF", source)

    def test_private_fonts_are_supplied_in_the_application_payload(self):
        theme = THEME.read_text(encoding="utf-8")
        build = (ROOT / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn('FAMILIA_PRESSURA = "GT Pressura"', theme)
        self.assertIn('(FAMILIA_PRESSURA, 28, "bold")', theme)
        self.assertIn('FAMILIA_CUERPO = "Helvetica Neue"', theme)
        self.assertIn('(FAMILIA_CUERPO, 13)', theme)
        self.assertIn('("Consolas", 13)', theme)
        self.assertIn("GT Pressura Regular.ttf", build)
        self.assertIn("HelveticaNeueRoman.otf", build)
        self.assertIn("HelveticaNeueBold.otf", build)
        self.assertIn("os.listdir(font_dir)", theme)
        self.assertIn('TTK_PRESET_OSCURO = "sincal-dark"', theme)
        self.assertIn("ThemeDefinition(", theme)
        self.assertIn('TTK_PRESET_CLARO = "sincal-light"', theme)
        self.assertIn('"fondo": "#1E1F25"', theme)
        self.assertIn('"fondo": "#F7E6D6"', theme)
        self.assertNotIn("#0A0A0C", theme)
        self.assertTrue((ROOT / "assets" / "fonts" / "GT Pressura Regular.ttf").is_file())
        self.assertTrue((ROOT / "assets" / "fonts" / "GTPressura-Bold.ttf").is_file())
        self.assertTrue((ROOT / "assets" / "fonts" / "HelveticaNeueRoman.otf").is_file())
        self.assertTrue((ROOT / "assets" / "fonts" / "HelveticaNeueBold.otf").is_file())

    def test_action_buttons_use_the_shared_offset_shadow(self):
        widget_source = (ROOT / "sincal" / "ui" / "widgets.py").read_text(
            encoding="utf-8")
        self.assertIn("class ShadowButton", widget_source)
        self.assertIn("x=size", widget_source)
        self.assertIn("y=size", widget_source)
        self.assertIn("shadow_color=COLOR_ACENTO", widget_source)
        for path in (
            APP,
            ARMADURAS,
            ROOT / "sincal" / "ui" / "tabs" / "ubicacion.py",
            ROOT / "sincal" / "ui" / "tabs" / "diagnostico.py",
        ):
            source = path.read_text(encoding="utf-8")
            self.assertIn("ShadowButton", source)

    def test_dpi_and_ttk_typography_are_configured_before_the_root(self):
        main = MAIN.read_text(encoding="utf-8")
        app = APP.read_text(encoding="utf-8")
        theme = THEME.read_text(encoding="utf-8")
        self.assertLess(main.index("configurar_dpi_windows()"), main.index("import tkinter as tk"))
        self.assertLess(app.index("configurar_dpi_windows()"), app.index("import tkinter as tk"))
        init = app.split("class ActualizadorCAD", 1)[1].split("asegurar_directorios()", 1)[0]
        self.assertLess(init.index("registrar_fuentes()"), init.index("super().__init__()"))
        self.assertIn('FUENTE_TTK_NORMAL = (FAMILIA_CUERPO, -13)', theme)
        self.assertIn('FUENTE_TTK_TABLA = (FAMILIA_CUERPO, -12)', theme)
        self.assertIn('f"{prefix}Table.Treeview"', theme)

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
        self.assertIn("def configurar_navegacion_pagina", core)
        self.assertNotIn("self.page_nav_panel", core)
        self.assertIn("self.page_nav_container = ctk.CTkFrame", core)
        self.assertNotIn("self.page_nav_container = ctk.CTkScrollableFrame", core)
        self.assertIn('orient="vertical"', core)
        self.assertIn("def _registrar_ancla_pagina", core)
        self.assertIn("def _enfocar_ancla_pagina", core)
        self.assertIn('padx=(32, 44)', core)
        self.assertIn('width=260', core)
        self.assertIn('("sincronizador", "acciones", botones_sec_frame)', core)
        self.assertIn('("sincronizador", "historial", history_panel)', core)
        self.assertIn('("procesamiento", "reemplazo", h1_frame)', core)
        self.assertIn('("conversion", "conversion", self.btn_convertir_dxf)', core)
        self.assertIn("self.tab_diagnostico.ir_a_seccion(anchor)", core)
        self.assertIn("def obtener_navegacion", docs)
        self.assertIn("def mostrar_tema_por_id", docs)
        self.assertIn('topic_id.startswith("categoria::")', docs)
        self.assertIn('topic_id.startswith("grupo::")', docs)
        self.assertNotIn("ttk.Panedwindow", structural)
        self.assertIn("ttk.Labelframe", structural)
        self.assertIn("self.ruta_adv_var", core)
        self.assertIn("self.ruta_conversion_var", core)
        self.assertNotIn("self.lbl_ruta_adv", core)
        self.assertNotIn("self.lbl_ruta_conversion", core)

    def test_home_commands_and_product_identity_are_complete(self):
        core = APP.read_text(encoding="utf-8")
        installer = (ROOT / "packaging" / "windows" / "SINCAL_Installer.iss").read_text(
            encoding="utf-8")
        self.assertIn('self.title("SINCAL Suite — Workbench")', core)
        self.assertIn('text="SINCAL SUITE"', core)
        self.assertIn('text="SINCRONIZADOR"', core)
        self.assertIn("def _resumir_commit", core)
        self.assertIn('self.entrada_comando.bind("<Return>"', core)
        self.assertIn('text="GLOSARIO DE COMANDOS"', core)
        self.assertIn('("comandos", "glosario", glossary)', core)
        self.assertIn("AppName=SINCAL Suite", installer)
        self.assertNotIn("AppName=SINCAL 2.0", installer)

    def test_global_vector_activity_indicator_is_integrated(self):
        core = APP.read_text(encoding="utf-8")
        activity = ACTIVITY.read_text(encoding="utf-8")
        self.assertIn("ActivityIndicator(self)", core)
        self.assertIn("def iniciar_actividad", core)
        self.assertIn("def actualizar_actividad", core)
        self.assertIn("def finalizar_actividad", core)
        self.assertIn('"conversion_dxf"', core)
        self.assertIn("class BridgeMotion", activity)
        self.assertIn('Image.new("RGBA"', activity)
        self.assertIn('anchor="se"', activity)
        self.assertIn('f"{round(current.progress):d} %"', activity)
        self.assertIn("0.8 - (time.monotonic() - self._shown_at)", activity)
        self.assertIn("ImageTk.PhotoImage(frame, master=self)", activity)

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
        self.assertIn('self._labelframe(page, "2. REVISIÓN Y MARCAS")', source)
        self.assertIn("SafeScrollableFrame", source)
        self.assertIn('("MUROS",', source)
        self.assertIn('("CONSOLAS",', source)
        self.assertIn('("TOPES",', source)
        self.assertIn('("CONTRAFUERTE",', source)
        self.assertIn('self._abutments = {}', source)
        self.assertIn("default_zapata_rules", source)
        self.assertIn("def actualizar_revision_zapata", source)
        self.assertIn("build_zapata_lisp", source)
        self.assertIn("build_zapata_detail_lisp", source)
        self.assertIn("ttk.Notebook", source)
        self.assertIn("ttk.Entry", source)
        self.assertIn("ttk.Combobox", source)
        self.assertIn("ttk.Checkbutton", source)
        self.assertIn("ttk.Radiobutton", source)
        self.assertIn("ttk.Progressbar", source)
        self.assertIn("Tableview(", source)
        self.assertIn("ToolTip(", source)
        self.assertIn("ttk.Separator", source)
        self.assertIn("def mostrar_vista_previa_marcas", source)
        self.assertIn("def mostrar_vista_previa_fierro", source)
        self.assertIn('"Marca", "Elemento", "Grupo / ubicación"', source)
        self.assertIn("def generar_despiece_zapata", source)
        self.assertIn('text="Generar despiece general de zapata"', source)
        self.assertNotIn("def generar_despiece_cad", source)
        self.assertIn('"FORMATOS ANOTATIVOS ACAD_2025.dwg"', source)
        self.assertIn("SINCAL-ZAPATA-GENERAR", source)
        self.assertIn('("D-D", "DD")', source)
        self.assertIn('("E-E", "EE")', source)
        self.assertNotIn("self.ent_phi_inf", source)
        self.assertNotIn("self.ent_espac_inf", source)
        self.assertIn('text="ESTRIBOS"', source)
        self.assertIn('text="TRAVESAÑOS"', source)
        self.assertIn('self._labelframe(parent, "ZAPATA")', source)
        self.assertIn('increment=100', source)
        self.assertIn('increment=50', source)

    def test_each_structural_subtab_has_only_one_page_scroll(self):
        source = ARMADURAS.read_text(encoding="utf-8")
        self.assertIn("tab_trav_host = ctk.CTkFrame", source)
        self.assertIn("tab_trav_main = SafeScrollableFrame", source)
        self.assertIn("page = SafeScrollableFrame", source)
        self.assertIn("table = ctk.CTkFrame", source)
        self.assertNotIn("table = ctk.CTkScrollableFrame", source)
        self.assertEqual(source.count("SafeScrollableFrame("), 2)

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
        self.assertIn("SINCAL SUITE", core)
        self.assertIn("Por Gonzalo M. para SINCAL Ltda. 2026.", core)
        self.assertIn('text=f"Versión {VERSION_ACTUAL}"', core)
        self.assertIn("self.sidebar.pack_forget()", core)
        self.assertNotIn("def _animar_menu_lateral", core)

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
