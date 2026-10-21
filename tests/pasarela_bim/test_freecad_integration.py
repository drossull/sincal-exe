"""Ensayo real de regeneración; se omite fuera del Python de FreeCAD."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy


@unittest.skipUnless(importlib.util.find_spec("FreeCAD"), "Requiere el Python de FreeCAD")
class TestFreeCAD(unittest.TestCase):
    def test_escalera_real_v2_volumen_peldanos_y_uuid_al_renombrar(self):
        import FreeCAD as App
        from pasarela_bim.freecad_backend import generar

        modelo = {"version":2,"proyecto":{"id":"escalera","uuid":"proyecto-permanente",
                  "nombre":"Escalera de prueba","estado":"conceptual","unidades":"m"},
                  "nodos":[{"id":"A","uuid":"a-permanente","tipo":"encuentro","x":0,"y":0,"z":0},
                           {"id":"B","uuid":"b-permanente","tipo":"encuentro","x":6,"y":0,"z":3}],
                  "tramos":[{"id":"T1","uuid":"tramo-permanente","tipo":"viga","funcion":"escalera",
                             "desde":"A","hasta":"B","familia":"escalera","ancho_m":2}],
                  "familias":{"escalera":{"tipo":"escalera","canto_m":0.2,"numero_peldanos":20}},
                  "fundaciones":[],"soportes":[]}
        with tempfile.TemporaryDirectory() as temporal:
            try:
                resultado = generar(modelo,Path(temporal)/"original",con_vistas=False)
                obj = App.ActiveDocument.getObject("TRAMO_T1")
                self.assertTrue(obj.Shape.isValid())
                self.assertEqual(len(obj.Shape.Solids),1)
                self.assertEqual(obj.NumeroPeldanos,20)
                self.assertAlmostEqual(obj.Huella.Value,300)
                self.assertAlmostEqual(obj.Contrahuella.Value,150)
                parametros = json.loads(obj.ParametrosJSON)
                self.assertEqual(parametros["ancho_m"],2)
                self.assertNotIn("ancho_mm",parametros)
                self.assertEqual(obj.UnidadesParametros,"m")
                self.assertEqual(json.loads(obj.PerfilCantoJSON)[0]["canto_m"],0.2)
                configuracion = json.loads(App.ActiveDocument.ConfiguracionPasarelaJSON)
                self.assertEqual(configuracion["version"],2)
                self.assertEqual(configuracion["proyecto"]["unidades"],"m")
                self.assertEqual(json.loads(App.ActiveDocument.getObject("NODO_B").ParametrosJSON)["z"],3)
                # Losa bajo la recta más los veinte prismas triangulares de peldaño.
                self.assertAlmostEqual(obj.Shape.Volume,2000*6000*(200+150/2),delta=1)
                horizontales = [f for f in obj.Shape.Faces if f.normalAt(0,0).z > 0.9999]
                self.assertEqual(len(horizontales),20)
                identidad = obj.UUIDBIM
                variantes = deepcopy(modelo)
                variantes["proyecto"]["id"] = "etiqueta-nueva"
                variantes["nodos"][0]["id"] = "ENTRADA"
                variantes["tramos"][0].update(id="ESCALERA",desde="ENTRADA")
                segundo = generar(variantes,Path(temporal)/"renombrado",con_vistas=False)
                self.assertEqual(App.ActiveDocument.getObject("TRAMO_ESCALERA").UUIDBIM,identidad)
                self.assertEqual(resultado["conteos"],{"tramo":1})
                self.assertTrue(segundo["verificacion"]["guardado_y_reabierto"])
                # El sentido descendente cambia el recorrido, no el volumen físico.
                variantes["nodos"][0]["z"],variantes["nodos"][1]["z"] = 3,0
                generar(variantes,Path(temporal)/"descendente",con_vistas=False)
                self.assertAlmostEqual(App.ActiveDocument.getObject("TRAMO_ESCALERA").Shape.Volume,
                                       2000*6000*(200+150/2),delta=1)
            finally:
                for nombre in list(App.listDocuments()):
                    App.closeDocument(nombre)

    def test_regenerar_conserva_identidades_y_actualiza_geometria(self):
        import FreeCAD as App
        from pasarela_bim.freecad_backend import generar

        raiz = Path(__file__).resolve().parents[2]
        modelo = json.loads((raiz / "pasarela_bim/ejemplos/los_batros.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporal:
            try:
                antes = generar(modelo, Path(temporal) / "antes", con_vistas=False)
                self.assertTrue(any("8%" in mensaje for mensaje in antes["avisos"]))
                self.assertEqual(json.loads(App.ActiveDocument.ConfiguracionPasarelaJSON)["version"],2)
                self.assertIn("ancho_m",json.loads(App.ActiveDocument.getObject("TRAMO_V7").ParametrosJSON))
                for nodo in modelo["nodos"]:
                    if nodo["id"] == "C8":
                        nodo["x"] += 1000
                despues = generar(modelo, Path(temporal) / "despues", con_vistas=False)
                por_id = lambda reporte: {(q["rol"], q["id"]): q for q in reporte["cantidades"]}
                a, b = por_id(antes), por_id(despues)
                self.assertEqual(set(a), set(b))
                self.assertEqual({k: q["uuid"] for k, q in a.items()}, {k: q["uuid"] for k, q in b.items()})
                self.assertNotEqual(a[("tramo", "V7")]["volumen_m3"], b[("tramo", "V7")]["volumen_m3"])
                self.assertEqual(despues["conteos"]["dado"], 10)
                self.assertEqual(despues["conteos"]["pilote"], 18)
                self.assertTrue(despues["verificacion"]["guardado_y_reabierto"])
                self.assertTrue(despues["verificacion"]["conexiones_conservadas"])
            finally:
                for nombre in list(App.listDocuments()):
                    App.closeDocument(nombre)


if __name__ == "__main__":
    unittest.main()
