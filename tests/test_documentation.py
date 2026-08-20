import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_tutorials_cover_every_published_lisp_command(self):
        data = json.loads((ROOT / "tutoriales.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], 2)
        documented = set(data["comandos_lisp"])
        expected = {
            "SINCAL", "BV", "CEVIADA", "CPOL", "DIMEL", "DL2",
            "DUP / DUPLICAR", "EXTRIMOUT", "MC", "MPEND", "P0", "PND",
            "PURGEALL", "RMLAY", "SETUP-A1", "SINCAL-ESCALAS", "ST0",
            "VRAP", "W08", "ZE", "CUSTOM-PROPS", "COPY-PROPS",
            "PASTE-PROPS", "REPARAR-PROPS", "C-INICIO / C-FIN", "C0 … C9",
        }
        self.assertEqual(documented, expected)

    def test_tutorials_cover_every_main_interface_area(self):
        data = json.loads((ROOT / "tutoriales.json").read_text(encoding="utf-8"))
        topic_ids = {topic["id"] for topic in data["temas"]}
        expected = {
            "primer-inicio", "actualizaciones", "integracion-cad", "startup",
            "master-dwg", "inventario-recursos", "procesamiento-general",
            "renombrado", "conversion-dxf", "comandos-vivo", "automatizacion-cerrada",
            "modulo-estructural", "modulo-ubicacion", "solucion-problemas",
            "diagnostico-soporte",
        }
        self.assertTrue(expected.issubset(topic_ids))

    def test_readme_describes_web_install_and_lazy_maps(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("instalador web", readme.lower())
        self.assertIn("solamente cuando se selecciona", readme.lower())


class WebInstallerConfigurationTests(unittest.TestCase):
    def test_pyinstaller_does_not_embed_hot_resources(self):
        spec = (ROOT / "SINCAL.spec").read_text(encoding="utf-8")
        self.assertIn("datas=[]", spec)
        self.assertNotIn("('mapas', 'mapas')", spec)
        self.assertNotIn("('masters', 'masters')", spec)

    def test_installer_downloads_hash_pinned_payloads(self):
        installer = (ROOT / "SINCAL_Installer.iss").read_text(encoding="utf-8")
        self.assertEqual(installer.count("external download extractarchive"), 2)
        self.assertIn('Hash: "{#AppPayloadHash}"', installer)
        self.assertIn('Hash: "{#PluginPayloadHash}"', installer)

    def test_web_payload_bundles_core_resources_but_not_regional_maps(self):
        build_script = (ROOT / "tools" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("scripts/AUDIT.ps1", build_script)
        self.assertIn("mapas/mapas_calibrados.json", build_script)
        self.assertIn("mapas/ayuda_travesano.png", build_script)
        self.assertIn("scripts/SINCAL_ENGINE.ps1", build_script)
        self.assertIn("assets/fonts/Workbench.ttf", build_script)
        self.assertIn("^mapas/Region_.*\\.png$", build_script)


class MassProcessingConfigurationTests(unittest.TestCase):
    def test_scripts_resolve_selected_engine_directly(self):
        script_names = (
            "AUDIT.ps1", "BV.ps1", "DL2.ps1", "PAGESETUP-A1.ps1",
            "PUBLISH-A1.ps1", "PURGEALL.ps1", "ZE.ps1",
        )
        for name in script_names:
            script = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertIn("Get-SincalCadEngine", script, name)
            self.assertIn("Start-Process -FilePath $enginePath", script, name)
            self.assertNotIn("$wrapperPath", script, name)

        purge = (ROOT / "scripts" / "PURGEALL.ps1").read_text(encoding="utf-8")
        self.assertNotIn('Start-Process -FilePath "cmd.exe"', purge)


if __name__ == "__main__":
    unittest.main()
