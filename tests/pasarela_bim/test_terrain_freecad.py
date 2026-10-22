"""Signed point levels persist on supports without generating terrain solids."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from tests.pasarela_bim.test_elevaciones import modelo_ejes


@unittest.skipUnless(importlib.util.find_spec("FreeCAD"), "Requiere el Python de FreeCAD")
class TestTerrainFreeCAD(unittest.TestCase):
    def test_niveles_individuales_persisten_en_apoyos_de_fundacion_compartida(self):
        import FreeCAD as App
        from pasarela_bim.freecad_backend import generar

        modelo = modelo_ejes()
        modelo["soportes"][0]["cota_terreno_proyectado_m"] = -0.3
        modelo["soportes"][1]["cota_terreno_proyectado_m"] = -0.7
        modelo["soportes"][1]["fundacion"] = "D1"
        modelo["fundaciones"][0].update(nodos=["E1","C1"],largo_m=13)
        modelo["fundaciones"] = [f for f in modelo["fundaciones"] if f["id"] != "D2"]
        with tempfile.TemporaryDirectory() as temporal:
            initial_docs = set(App.listDocuments())
            try:
                generar(modelo,Path(temporal)/"terreno",con_vistas=False)
                doc = App.ActiveDocument
                a,b = doc.getObject("SOPORTE_E1"),doc.getObject("SOPORTE_C1")
                self.assertEqual(a.FundacionVinculada,b.FundacionVinculada)
                for support,xyz in ((a,(0,0,-300)),(b,(10000,0,-700))):
                    self.assertEqual(support.CotaTerrenoProyectado.Value,xyz[2])
                    self.assertEqual(tuple(support.CentroTerrenoProyectado),xyz)
                    self.assertEqual(json.loads(support.ParametrosJSON)["cota_terreno_proyectado_m"],xyz[2]/1000)
                    self.assertEqual(support.Shape.BoundBox.ZMin,-1000)
                    self.assertEqual(support.Shape.BoundBox.ZMax,900)
                self.assertNotIn("CotaTerrenoProyectado",doc.getObject("SOPORTE_C2").PropertiesList)
                self.assertFalse(any(getattr(o,"RolBIM",None) == "terreno" for o in doc.Objects))
            finally:
                for name in set(App.listDocuments())-initial_docs:
                    App.closeDocument(name)


if __name__ == "__main__":
    unittest.main()
