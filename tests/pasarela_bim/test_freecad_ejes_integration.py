"""Persistencia real de ejes y separación de las cantidades de hormigón."""

import importlib.util
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tests.pasarela_bim.test_elevaciones import modelo_ejes


@unittest.skipUnless(importlib.util.find_spec("FreeCAD"),"Requiere el Python de FreeCAD")
class TestFreeCADEjes(unittest.TestCase):
    def test_ejes_persisten_sin_entrar_en_cantidades_y_svg_trazable(self):
        import FreeCAD as App
        from pasarela_bim.freecad_backend import generar

        modelo = modelo_ejes()
        with tempfile.TemporaryDirectory() as temporal:
            try:
                reporte = generar(modelo,Path(temporal)/"ejes",con_vistas=bool(App.GuiUp))
                self.assertEqual(reporte["verificacion"]["ejes_referencia_conservados"],5)
                self.assertEqual(reporte["verificacion"]["elevaciones_derivadas"],1)
                doc = App.ActiveDocument
                referencias = [o for o in doc.Objects if "TipoEje" in o.PropertiesList]
                self.assertEqual(len(referencias),5)
                self.assertEqual(len([o for o in referencias if o.TipoEje == "apoyo"]),4)
                for obj in referencias:
                    self.assertFalse(obj.IncluidoEnCantidades)
                    self.assertNotIn("MaterialBIM",obj.PropertiesList)
                    self.assertEqual(len(obj.Shape.Solids),0)
                    self.assertEqual(obj.RevisionParametros,reporte["revision_parametros"])
                self.assertNotIn("eje",reporte["conteos"])
                identidad = next(o.UUIDBIM for o in referencias if o.TipoEje == "recorrido")
                if App.GuiUp:
                    self.assertEqual(reporte["verificacion"]["vistas_asociativas_conservadas"],4)
                    for view in doc.getObject("LAMINA_A1").Views:
                        self.assertFalse(any("TipoEje" in o.PropertiesList for o in view.Source))
                xml = ET.parse(reporte["archivos_elevaciones"][0]).getroot()
                self.assertIn("ELEVACIÓN DESARROLLADA"," ".join(xml.itertext()))
                self.assertIn("E1 / estribo"," ".join(xml.itertext()))
                self.assertIn(reporte["revision_parametros"],xml.find("{*}metadata").text)
                renombrado = deepcopy(modelo)
                eje = next(e for e in renombrado["ejes"] if e["tipo"] == "recorrido")
                eje.update(id="RUTA_RENOMBRADA",nombre="Nuevo rótulo")
                siguiente = generar(renombrado,Path(temporal)/"renombrado",con_vistas=False)
                self.assertEqual(App.ActiveDocument.getObject("EJE_RUTA_RENOMBRADA").UUIDBIM,identidad)
                self.assertNotEqual(reporte["revision_parametros"],siguiente["revision_parametros"])
                legacy = deepcopy(modelo)
                legacy.pop("ejes")
                sin_ejes = generar(legacy,Path(temporal)/"legacy",con_vistas=False)
                self.assertEqual(reporte["cantidades"],sin_ejes["cantidades"])
                self.assertEqual(sin_ejes["verificacion"]["ejes_referencia_conservados"],0)
                self.assertEqual(sin_ejes["archivos_elevaciones"],[])
            finally:
                for nombre in list(App.listDocuments()):
                    App.closeDocument(nombre)


if __name__ == "__main__":
    unittest.main()
