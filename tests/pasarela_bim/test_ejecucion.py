"""Verifica el límite entre intercambio portable y entrada privada del motor."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pasarela_bim.ejecucion import generar_aislado
from pasarela_bim.proyecto import convertir_a_portable


class TestIntercambioGenerado(unittest.TestCase):
    def test_exporta_metros_y_conserva_entrada_legacy_privada(self):
        raiz = Path(__file__).resolve().parents[2]
        legacy = json.loads((raiz/"pasarela_bim/ejemplos/los_batros.json").read_text(encoding="utf-8"))
        nuevo = {"version":2,"proyecto":{"id":"p","nombre":"Prueba","estado":"conceptual","unidades":"m"},
                 "nodos":[{"id":"A","tipo":"encuentro","x":0,"y":0,"z":0},
                          {"id":"B","tipo":"encuentro","x":6,"y":0,"z":0.48}],
                 "tramos":[{"id":"T","tipo":"viga","funcion":"rampa","desde":"A","hasta":"B",
                            "familia":"losa","ancho_m":2}],
                 "familias":{"losa":{"tipo":"maciza","canto_m":0.2}},"fundaciones":[],"soportes":[]}
        for modelo in (legacy,nuevo):
            with self.subTest(version=modelo["version"]), tempfile.TemporaryDirectory() as temporal:
                destino = Path(temporal)/"salida"
                def finalizar(**kwargs):
                    (destino/"modelo.FCStd").write_bytes(b"resultado simulado")
                    (destino/"resultado_proceso.json").write_text(
                        json.dumps({"estado":"completado","resultado":{"valido":True}}),encoding="utf-8")
                    return 0
                with patch("pasarela_bim.ejecucion.localizar_freecad",return_value=Path("FreeCAD.exe")), \
                     patch("pasarela_bim.ejecucion.subprocess.Popen") as proceso:
                    proceso.return_value.wait.side_effect = finalizar
                    resultado = generar_aislado(modelo,destino)
                portable = json.loads((destino/"topologia.json").read_text(encoding="utf-8"))
                interno = json.loads((destino/"entrada_motor.json").read_text(encoding="utf-8"))
                self.assertEqual(portable,convertir_a_portable(modelo))
                self.assertEqual(interno["version"],1)
                self.assertEqual(interno["proyecto"]["unidades"],"mm")
                self.assertEqual(interno["proyecto"].get("esquema_intercambio"),2 if modelo["version"]==2 else None)
                self.assertIn("topologia.json",resultado["archivos"])
                self.assertNotIn("entrada_motor.json",resultado["archivos"])
                self.assertNotIn("resultado_proceso.json",resultado["archivos"])
                self.assertIn("entrada_motor.json",(destino/"generar.FCMacro").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
