"""An interior return column is structural, never an artificial pedestrian edge."""
from copy import deepcopy
import unittest

from pasarela_bim.ejes import autoconstruir_ejes
from pasarela_bim.proyecto import convertir_a_portable
from pasarela_bim.topologia import resolver_modelo, validar
from pasarela_bim.freecad_backend import _svg_elevacion


def modelo():
    return {"version":1,"proyecto":{"id":"RET","nombre":"Retorno central","estado":"conceptual","unidades":"mm"},
            "nodos":[{"id":"A","tipo":"encuentro","x":0,"y":0,"z":4000},
                     {"id":"B","tipo":"encuentro","x":6000,"y":0,"z":4000},
                     {"id":"C","tipo":"columna","x":3000,"y":0,"z":4000,"anclaje_tramo":{"tramo":"R","t":.5}}],
            "tramos":[{"id":"R","tipo":"retorno","funcion":"retorno","desde":"A","hasta":"B","familia":"losa","ancho_mm":2000}],
            "familias":{"losa":{"tipo":"maciza","canto_mm":600}},
            "soportes":[{"id":"C","nodo":"C","fundacion":"F","diametro_mm":1000,"cota_superior_mm":3400,"cota_terreno_proyectado_mm":-500}],
            "fundaciones":[{"id":"F","nodos":["C"],"tipo":"dado","largo_mm":3000,"ancho_mm":3000,"alto_mm":1000,"cota_superior_mm":-1000,
                            "pilotes":[{"id":"P","diametro_mm":800,"longitud_mm":6000,"dx_mm":0,"dy_mm":0}]}],
            "ejes":[{"id":"ER","nombre":"Retorno","tipo":"recorrido","tramos":["R"]},
                    {"id":"EC","nombre":"Cepa central","tipo":"apoyo","nodo":"C"}]}


class TestAnclajeRetorno(unittest.TestCase):
    def test_column_does_not_split_return_or_break_pedestrian_graph(self):
        m=modelo(); before=deepcopy(m); report=validar(m)
        self.assertTrue(report["valido"],report["errores"])
        self.assertEqual(report["recorrido"],["A","B"])
        resolved=resolver_modelo(m)
        self.assertEqual(len(resolved["tramos"]),1)
        self.assertEqual(resolved["tramos"][0]["longitud_planta_mm"],6000)
        self.assertEqual(resolved["soportes"][0]["centro"],[3000,0,-1000])
        self.assertEqual(resolved["fundaciones"][0]["pilotes"][0]["centro"],[3000,0,-2000])
        self.assertEqual(m,before)

    def test_section_and_export_have_interior_station_and_own_axis(self):
        m=modelo(); axis=resolver_modelo(m)["ejes_resueltos"][0]
        self.assertEqual(axis["nodos"],["A","B"])
        self.assertEqual(axis["nodos_apoyo_interiores"],["C"])
        self.assertEqual(len(axis["segmentos"]),1)
        self.assertEqual([(p["nodo"],p["estacion_mm"]) for p in axis["estaciones"]],[("A",0),("C",3000),("B",6000)])
        centre=axis["estaciones"][1]
        self.assertEqual(centre["ejes_apoyo"][0]["id"],"EC")
        self.assertEqual(centre["soportes"][0]["cota_terreno_proyectado_mm"],-500)
        self.assertEqual(centre["fundaciones"][0]["id"],"F")
        svg=_svg_elevacion(axis,m["familias"],m["proyecto"],"local")
        self.assertIn('id="marca-2-EC"',svg)
        self.assertIn('data-node-id="C"',svg)
        self.assertIn('C / cepa',svg)
        self.assertIn('Longitud en planta: 6.000 m',svg)

    def test_reversed_axis_and_portable_json_preserve_anchor_fraction(self):
        m=modelo();m["nodos"].append({"id":"D","tipo":"encuentro","x":9000,"y":0,"z":4000})
        m["tramos"].append({**m["tramos"][0],"id":"R2","desde":"D","hasta":"B"})
        m["ejes"][0]["tramos"]=["R2","R"]
        portable=convertir_a_portable(m)
        self.assertEqual(portable["nodos"][2]["anclaje_tramo"],{"tramo":"R","t":.5})
        axis=resolver_modelo(portable)["ejes_resueltos"][0]
        self.assertEqual(axis["nodos"],["D","B","A"])
        self.assertEqual(next(p["estacion_mm"] for p in axis["estaciones"] if p["nodo"]=="C"),6000)
        self.assertEqual(axis["longitud_mm"],9000)

    def test_stale_anchor_is_rejected_and_consistent_move_changes_foundation(self):
        m=modelo();m["nodos"][0]["y"]=2000;m["nodos"][1]["y"]=2000
        self.assertIn("anclaje_coordenadas_incoherentes",{e["codigo"] for e in validar(m,borrador=True)["errores"]})
        with self.assertRaises(ValueError): resolver_modelo(m)
        m["nodos"][2]["y"]=2000
        self.assertEqual(resolver_modelo(m)["fundaciones"][0]["centro"],[3000,2000,-1000])

    def test_anchor_errors_are_not_silently_ignored(self):
        for value in (None,[],{},"R",{"tramo":"R","t":True},{"tramo":"R","t":float("nan")},{"tramo":"R","t":0},{"tramo":"R","t":1}):
            with self.subTest(value=value):
                m=modelo();m["nodos"][2]["anclaje_tramo"]=value
                self.assertIn("anclaje_tramo_invalido",{e["codigo"] for e in validar(m,borrador=True)["errores"]})
        for missing in (True,False):
            m=modelo()
            if missing: m["nodos"][2]["anclaje_tramo"]["tramo"]="missing"
            else: m["tramos"][0].update(tipo="viga",funcion="descanso")
            self.assertIn("anclaje_retorno_inexistente",{e["codigo"] for e in validar(m)["errores"]})

    def test_interior_support_cannot_intersect_intrados_or_become_walk_node(self):
        m=modelo();m["soportes"][0]["cota_superior_mm"]=3500
        self.assertIn("soporte_atraviesa_intrados",{e["codigo"] for e in validar(m)["errores"]})
        m=modelo();m["tramos"].append({**m["tramos"][0],"id":"BAD","desde":"C"})
        self.assertIn("anclaje_en_recorrido",{e["codigo"] for e in validar(m)["errores"]})

    def test_auto_axes_include_central_column(self):
        m=modelo();m.pop("ejes");m=autoconstruir_ejes(m)
        self.assertEqual(len([e for e in m["ejes"] if e.get("nodo")=="C"]),1)
        self.assertTrue(validar(m)["valido"])

    def test_piles_may_touch_but_must_not_overlap(self):
        m=modelo();p=m["fundaciones"][0]["pilotes"][0]
        m["fundaciones"][0]["pilotes"].append({**p,"id":"P2","dx_mm":799})
        self.assertIn("pilotes_superpuestos",{e["codigo"] for e in validar(m,borrador=True)["errores"]})
        m["fundaciones"][0]["pilotes"][1]["dx_mm"]=800
        self.assertTrue(validar(m)["valido"])


if __name__ == "__main__": unittest.main()
