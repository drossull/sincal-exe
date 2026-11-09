"""Real, headless FreeCAD check for one return with an anchored centre column."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from tests.pasarela_bim.test_anclaje_retorno import modelo


@unittest.skipUnless(importlib.util.find_spec("FreeCAD"), "Requiere el Python de FreeCAD")
class TestReturnFreeCADIntegration(unittest.TestCase):
    def test_central_return_column_base_pile_and_axis_survive_regeneration(self):
        import FreeCAD as App
        from pasarela_bim.freecad_backend import generar
        from pasarela_bim.proyecto import convertir_a_interno
        from pasarela_bim.topologia import validar

        # This check must run in its own Python process, never in a user's GUI.
        if App.GuiUp or App.listDocuments():
            self.skipTest("Esta prueba requiere un proceso FreeCAD sin GUI ni documentos abiertos")
        initial_documents = set(App.listDocuments())
        configuration = modelo()
        configuration["proyecto"]["uuid"] = "return-integration-project"
        for collection in ("nodos", "tramos", "soportes", "fundaciones", "ejes"):
            for item in configuration[collection]:
                item["uuid"] = f"return-integration-{collection}-{item['id']}"
        configuration["fundaciones"][0]["pilotes"][0]["uuid"] = "return-integration-pile"
        original = deepcopy(configuration)

        def physical(document):
            return {obj.Name: obj for obj in document.Objects
                    if "RolBIM" in obj.PropertiesList and obj.RolBIM in
                    ("tramo", "soporte", "dado", "pilote", "capitel")}

        def verify(document, expected_x, expected_y, expected_z):
            objects = physical(document)
            self.assertEqual(set(objects), {"TRAMO_R", "SOPORTE_C", "DADO_F", "PILOTE_P"})
            for obj in objects.values():
                self.assertTrue(obj.Shape.isValid(), obj.Name)
                self.assertFalse(obj.Shape.isNull(), obj.Name)
                self.assertEqual(len(obj.Shape.Solids), 1, obj.Name)
                self.assertGreater(obj.Shape.Volume, 0, obj.Name)
            deck, column, base, pile = (objects[name] for name in
                                       ("TRAMO_R", "SOPORTE_C", "DADO_F", "PILOTE_P"))
            self.assertEqual(deck.FuncionTramo, "retorno")
            self.assertEqual(list(deck.NodosTopologicos), ["A", "B"])
            self.assertAlmostEqual(deck.Shape.BoundBox.ZMin, expected_z - 600, places=6)
            self.assertAlmostEqual(column.Shape.BoundBox.ZMax, expected_z - 600, places=6)
            self.assertAlmostEqual(column.Shape.distToShape(deck.Shape)[0], 0, places=6)
            self.assertAlmostEqual(column.Shape.common(deck.Shape).Volume, 0, delta=1e-3)
            self.assertAlmostEqual(column.Shape.CenterOfMass.x, expected_x, places=6)
            self.assertAlmostEqual(column.Shape.CenterOfMass.y, expected_y, places=6)
            self.assertAlmostEqual(column.Shape.BoundBox.ZMin, -1000, places=6)
            self.assertAlmostEqual(base.Shape.CenterOfMass.x, expected_x, places=6)
            self.assertAlmostEqual(base.Shape.CenterOfMass.y, expected_y, places=6)
            self.assertAlmostEqual(base.Shape.BoundBox.ZMax, -1000, places=6)
            self.assertAlmostEqual(base.Shape.BoundBox.ZMin, -2000, places=6)
            self.assertAlmostEqual(pile.Shape.CenterOfMass.x, expected_x, places=6)
            self.assertAlmostEqual(pile.Shape.CenterOfMass.y, expected_y, places=6)
            self.assertAlmostEqual(pile.Shape.BoundBox.ZMax, -2000, places=6)
            self.assertAlmostEqual(pile.Shape.BoundBox.ZMin, -8000, places=6)
            self.assertEqual(column.FundacionVinculada.Name, "DADO_F")
            self.assertEqual(pile.FundacionVinculada.Name, "DADO_F")
            self.assertAlmostEqual(column.CotaTerrenoProyectado.Value, -500, places=6)
            anchor = document.getObject("NODO_C")
            self.assertEqual(json.loads(anchor.ParametrosJSON)["anclaje_tramo"], {"tramo": "R", "t": .5})
            self.assertAlmostEqual(anchor.CoordenadaPaso.x, expected_x, places=6)
            self.assertAlmostEqual(anchor.CoordenadaPaso.y, expected_y, places=6)
            self.assertAlmostEqual(anchor.CoordenadaPaso.z, expected_z, places=6)
            route_axis, support_axis = document.getObject("EJE_ER"), document.getObject("EJE_EC")
            self.assertEqual({n.Name for n in route_axis.NodosVinculados}, {"NODO_A", "NODO_B", "NODO_C"})
            self.assertEqual([n.Name for n in support_axis.NodosVinculados], ["NODO_C"])
            self.assertEqual([t.Name for t in route_axis.TramosVinculados], ["TRAMO_R"])
            stations = json.loads(route_axis.EstacionesResueltasJSON)["estaciones"]
            central_station = next(station for station in stations if station["nodo"] == "C")
            self.assertEqual(central_station["estacion_mm"], 3000)
            self.assertEqual(central_station["soportes"][0]["id"], "C")
            self.assertEqual(central_station["fundaciones"][0]["id"], "F")
            self.assertEqual(central_station["ejes_apoyo"][0]["id"], "EC")
            for axis in (route_axis, support_axis):
                self.assertTrue(axis.Shape.isValid())
                self.assertFalse(axis.Shape.Solids)
                self.assertFalse(axis.IncluidoEnCantidades)
            return {name: obj.UUIDBIM for name, obj in objects.items()}

        with tempfile.TemporaryDirectory(prefix="pasarela-return-freecad-") as directory:
            try:
                result = generar(configuration, Path(directory) / "original", con_vistas=False)
                self.assertEqual(configuration, original, "La generación no debe modificar la configuración")
                self.assertEqual(result["conteos"], {"dado": 1, "pilote": 1, "tramo": 1, "soporte": 1})
                self.assertTrue(result["verificacion"]["guardado_y_reabierto"])
                self.assertTrue(result["verificacion"]["conexiones_conservadas"])
                self.assertTrue(result["verificacion"]["sin_solapes_mayores_1cm3"])
                self.assertEqual(result["verificacion"]["ejes_referencia_conservados"], 2)
                identities = verify(App.ActiveDocument, 3000, 0, 4000)

                # Explicitly close and reopen the saved result, without touching other sessions.
                current_name = App.ActiveDocument.Name
                App.closeDocument(current_name)
                reopened = App.openDocument(result["archivo_fcstd"])
                self.assertEqual(verify(reopened, 3000, 0, 4000), identities)
                portable = json.loads(reopened.ConfiguracionPasarelaJSON)
                self.assertEqual(portable["version"], 2)
                moved = convertir_a_interno(portable)

                # Rotate and translate the whole return in plan, then raise its deck.
                by_id = {node["id"]: node for node in moved["nodos"]}
                by_id["A"].update(x=1000, y=2000, z=4500)
                by_id["B"].update(x=1000, y=8000, z=4500)
                self.assertIn("anclaje_coordenadas_incoherentes", {error["codigo"] for error in validar(moved)["errores"]})
                attachment = by_id["C"]["anclaje_tramo"]
                t = attachment["t"]
                previous_z = by_id["C"]["z"]
                for coordinate in ("x", "y", "z"):
                    by_id["C"][coordinate] = by_id["A"][coordinate] + t * (by_id["B"][coordinate] - by_id["A"][coordinate])
                moved["soportes"][0]["cota_superior_mm"] += by_id["C"]["z"] - previous_z
                self.assertTrue(validar(moved)["valido"], validar(moved)["errores"])
                after = generar(moved, Path(directory) / "moved", con_vistas=False)
                self.assertNotEqual(after["revision_parametros"], result["revision_parametros"])
                self.assertEqual(verify(App.ActiveDocument, 1000, 5000, 4500), identities)
                self.assertEqual(after["conteos"], result["conteos"])
                self.assertTrue(after["verificacion"]["guardado_y_reabierto"])
                self.assertTrue(after["verificacion"]["sin_solapes_mayores_1cm3"])
            finally:
                for name in set(App.listDocuments()) - initial_documents:
                    App.closeDocument(name)


if __name__ == "__main__":
    unittest.main()
