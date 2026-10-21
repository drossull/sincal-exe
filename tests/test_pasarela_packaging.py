"""Contrato y separación del complemento opcional, sin instalar aplicaciones."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.build_pasarela_module import crear_paquete, descriptor, ROOT


class PasarelaPackagingTests(unittest.TestCase):
    def test_zip_manifiesto_cubre_todo_y_es_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            executable = directory/"binario.exe"
            executable.write_bytes(b"MZ prueba empaquetado, no ejecutable real")
            output = directory/"salida"
            result = crear_paquete(executable,output,descriptor())
            with zipfile.ZipFile(result["zip"]) as archive:
                self.assertEqual(set(archive.namelist()),{"SINCAL-Pasarela.exe","module.json"})
                manifest = json.loads(archive.read("module.json"))
                self.assertEqual(manifest["schema"],1)
                self.assertEqual(manifest["id"],"pasarela-bim")
                self.assertEqual(manifest["host_api"],1)
                self.assertEqual(set(manifest["files"]),set(archive.namelist())-{"module.json"})
                for path,digest in manifest["files"].items():
                    self.assertEqual(hashlib.sha256(archive.read(path)).hexdigest(),digest)
                self.assertEqual(sum(e.file_size for e in archive.infolist()),result["installed_bytes"])
            # Un archivo ajeno al stage no se añade accidentalmente al módulo.
            (Path(result["stage"])/"proyecto_privado.json").write_text("{}",encoding="utf-8")
            again = crear_paquete(executable,output,descriptor())
            self.assertEqual(again["sha256"],result["sha256"])

    def test_rechaza_binario_inexistente_o_vacio(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"vacio.exe"
            for create in (False,True):
                if create:
                    path.touch()
                with self.assertRaises(ValueError):
                    crear_paquete(path,Path(folder)/"out",descriptor())

    def test_core_excluye_modulo_y_spec_separada_excluye_freecad(self):
        for name in ("SINCAL.spec","SINCAL_Web.spec"):
            source = (ROOT/"packaging/windows"/name).read_text(encoding="utf-8")
            self.assertIn("excludes=['pasarela_bim']",source)
            self.assertNotIn("runtime/pasarela_bim",source)
        source = (ROOT/"packaging/windows/SINCAL_Pasarela.spec").read_text(encoding="utf-8")
        self.assertIn('"runtime/pasarela_bim"',source)
        self.assertIn('"FreeCAD", "FreeCADGui", "Part", "TechDraw"',source)
        self.assertNotIn("collect_all",source)

    def test_instalacion_opcional_y_complemento_por_usuario(self):
        main = (ROOT/"packaging/windows/SINCAL_Installer.iss").read_text(encoding="utf-8")
        component = next(line for line in main.splitlines() if line.startswith('Name: "pasarela";'))
        self.assertNotIn("Types:",component)
        self.assertNotIn("fixed",component)
        self.assertIn('Hash: "{#PasarelaPayloadHash}"; Components: pasarela',main)
        self.assertIn('{app}\\modules\\pasarela-bim',main)
        addon = (ROOT/"packaging/windows/SINCAL_Pasarela_Installer.iss").read_text(encoding="utf-8")
        self.assertIn("PrivilegesRequired=lowest",addon)
        self.assertIn("DefaultDirName={localappdata}\\SINCAL\\modules\\pasarela-bim",addon)
        self.assertEqual(addon.count('Parameters: "--port 0"'),2)
        self.assertNotIn("[UninstallDelete]",addon)
        self.assertNotIn("[InstallDelete]",addon)


if __name__ == "__main__":
    unittest.main()
