"""Referencias persistentes y desarrollo de perfiles por cadenas topológicas."""

from copy import deepcopy
import unittest

from pasarela_bim.ejes import autoconstruir_ejes, nodos_de_cadena, resolver_ejes, validar_ejes
from pasarela_bim.proyecto import convertir_a_portable
from pasarela_bim.topologia import resolver_modelo, validar
from test_topologia import ejemplo


def linea():
    return {"version":1,"proyecto":{"id":"p","nombre":"Ejes","estado":"conceptual","unidades":"mm"},
            "nodos":[{"id":i,"uuid":i+"-estable","tipo":"encuentro","x":x,"y":0,"z":5000}
                     for i,x in (("A",0),("B",10000),("C",20000))],
            "tramos":[{"id":i,"uuid":i+"-estable","tipo":"viga","funcion":"cruce","desde":a,"hasta":b,
                       "familia":"losa","ancho_mm":2000} for i,a,b in (("AB","A","B"),("BC","B","C"))],
            "familias":{"losa":{"tipo":"maciza","canto_mm":200}},"soportes":[],"fundaciones":[]}


class TestEjes(unittest.TestCase):
    def test_legacy_sin_ejes_no_se_muta_y_cobertura_explicita_es_pendiente(self):
        m = linea()
        self.assertTrue(validar(m)["valido"])
        self.assertIn("ejes_legacy_sin_definir",{a["codigo"] for a in validar(m)["avisos"]})
        self.assertEqual(resolver_modelo(m)["ejes_resueltos"],[])
        self.assertNotIn("ejes",m)
        m["ejes"] = []
        self.assertFalse(validar(m)["valido"])
        borrador = validar(m,borrador=True)
        self.assertTrue(borrador["valido"])
        self.assertFalse(borrador["generable"])
        self.assertEqual({p["codigo"] for p in borrador["pendientes"]},{"tramo_sin_eje"})

    def test_autoconstruccion_preserva_uuid_nombre_y_extiende_sin_fusionar(self):
        m = linea()
        m["ejes"] = [{"id":"X","uuid":"persistente","nombre":"Cruce central","tipo":"atravieso","tramos":["AB"],"principal":True}]
        original = deepcopy(m)
        auto = autoconstruir_ejes(m)
        self.assertEqual(m,original)
        self.assertEqual(auto["ejes"][0],{**m["ejes"][0],"tramos":["AB","BC"]})
        self.assertEqual(autoconstruir_ejes(auto),auto)
        m["ejes"].append({"id":"Y","uuid":"otra-identidad","nombre":"Segundo vano","tipo":"atravieso","tramos":["BC"]})
        self.assertEqual(autoconstruir_ejes(m)["ejes"],m["ejes"])

    def test_apoyos_independientes_aunque_compartan_dado(self):
        auto = autoconstruir_ejes(ejemplo())
        self.assertTrue(validar(auto)["valido"])
        apoyos = [e for e in auto["ejes"] if e["tipo"] == "apoyo"]
        self.assertEqual({e["nodo"] for e in apoyos},{"E1","C1","C2","E2"})
        self.assertEqual(len({e["uuid"] for e in apoyos}),4)
        eje = next(e for e in resolver_modelo(auto)["ejes_resueltos"] if e["tipo"] == "recorrido")
        self.assertEqual(eje["longitud_mm"],25000)
        self.assertFalse(eje["es_recto"])
        c1,c2 = eje["estaciones"][1:3]
        self.assertEqual(c1["fundaciones"],c2["fundaciones"])
        self.assertEqual(c1["fundaciones"][0]["cota_inferior_mm"],-1000)
        self.assertNotEqual(c1["ejes_apoyo"][0]["id"],c2["ejes_apoyo"][0]["id"])
        auto["ejes"] = [e for e in auto["ejes"] if e.get("nodo") != "C1"]
        self.assertIn("nodo_sin_eje_apoyo",{p["codigo"] for p in validar(auto,borrador=True)["pendientes"]})

    def test_cadena_invertida_retranqueos_rasante_y_canto(self):
        m = ejemplo()
        m["tramos"][2].update(desde="E2",hasta="C2",retranqueo_inicio_mm=1000,retranqueo_fin_mm=2000,
            rasante=[{"t":0,"f":0},{"t":.2,"f":.2},{"t":.8,"f":.2},{"t":1,"f":1}])
        m["familias"]["cajon"]["perfil_canto"] = [{"t":0,"canto_mm":800},{"t":.5,"canto_mm":1000},{"t":1,"canto_mm":900}]
        m = autoconstruir_ejes(m)
        eje = next(e for e in resolver_modelo(m)["ejes_resueltos"] if e["tipo"] == "recorrido")
        tramo = eje["segmentos"][2]
        self.assertTrue(tramo["invertido"])
        self.assertEqual((tramo["desde"],tramo["hasta"]),("C2","E2"))
        self.assertEqual((tramo["estacion_inicio_mm"],tramo["estacion_fin_mm"]),(15000,25000))
        self.assertEqual((tramo["estacion_inicio_util_mm"],tramo["estacion_fin_util_mm"]),(17000,24000))
        self.assertEqual([p["estacion_mm"] for p in tramo["puntos_rasante"]],[17000,20000,23000,24000])
        self.assertAlmostEqual(tramo["puntos_rasante"][0]["z_mm"],5100)
        self.assertEqual([p["canto_mm"] for p in tramo["perfil_canto"]],[940,1000,880,840])

    def test_bifurcacion_y_circuito_se_separan_en_cadenas_abiertas(self):
        m = linea()
        for t in m["tramos"]:
            t["funcion"] = "descanso"
        m["nodos"].append({"id":"D","tipo":"encuentro","x":10000,"y":10000,"z":5000})
        m["tramos"].append({"id":"BD","desde":"B","hasta":"D","tipo":"viga","funcion":"descanso","familia":"losa","ancho_mm":2000})
        auto = autoconstruir_ejes(m)
        self.assertEqual(len(auto["ejes"]),3)
        self.assertTrue(validar(auto)["valido"])
        # Cierra A-B-C-D-A sin ramificación: no se inventa una estación doble.
        m["tramos"][-1].update(id="CD",desde="C",hasta="D")
        m["tramos"].append({**m["tramos"][-1],"id":"DA","desde":"D","hasta":"A"})
        auto = autoconstruir_ejes(m)
        self.assertEqual(len(auto["ejes"]),2)
        self.assertTrue(validar(auto)["valido"])
        for e in auto["ejes"]:
            ns = nodos_de_cadena(e,{t["id"]:t for t in m["tramos"]})
            self.assertEqual(len(ns),len(set(ns)))

    def test_atravieso_debe_ser_recto_y_solo_uno_principal(self):
        m = autoconstruir_ejes(linea())
        m["nodos"][2]["y"] = 1000
        self.assertIn("atravieso_no_recto",{e["codigo"] for e in validar(m)["errores"]})
        m.pop("ejes")
        auto = autoconstruir_ejes(m)
        self.assertEqual(len(auto["ejes"]),2)
        self.assertTrue(validar(auto)["valido"])
        auto["ejes"][1]["principal"] = True
        self.assertIn("varios_ejes_principales",{e["codigo"] for e in validar(auto)["errores"]})

    def test_referencias_duplicadas_cadenas_rotas_y_malformados(self):
        base = autoconstruir_ejes(linea())
        variantes = [({"ejes":None},"ejes_invalidos"),
                     ({"ejes":[{"id":"X","nombre":"X","tipo":[]}]},"tipo_eje_invalido"),
                     ({"ejes":[{"id":"X","nombre":"X","tipo":"recorrido","tramos":[{}]}]},"cadena_eje_invalida")]
        for cambio,codigo in variantes:
            with self.subTest(codigo=codigo):
                self.assertIn(codigo,{e["codigo"] for e in validar({**base,**cambio})["errores"]})
        duplicado = deepcopy(base)
        duplicado["ejes"].append({**duplicado["ejes"][0],"id":"otro","uuid":"otro","principal":False})
        self.assertIn("tramo_varios_ejes",{e["codigo"] for e in validar(duplicado)["errores"]})
        rota = deepcopy(base)
        rota["ejes"][0]["tramos"] = ["AB","inexistente"]
        self.assertIn("cadena_eje_invalida",{e["codigo"] for e in validar(rota)["errores"]})

    def test_portable_preserva_referencias_y_resuelve_mm_sin_cambiar_origen(self):
        m = autoconstruir_ejes(linea())
        m["proyecto"]["georreferencia"] = {"este_m":350000,"norte_m":6000000,"cota_m":100,"norte_desde_x_horario_deg":270}
        portable = convertir_a_portable(m)
        self.assertEqual(portable["ejes"],m["ejes"])
        self.assertEqual(resolver_ejes(portable),resolver_ejes(m))
        self.assertEqual(portable["nodos"][2]["x"],20)
        self.assertEqual(portable["proyecto"]["georreferencia"],m["proyecto"]["georreferencia"])

    def test_identificadores_de_eje_no_colisionan_con_entidades_ni_pilotes(self):
        m = ejemplo()
        m["fundaciones"][1]["pilotes"][0]["id"] = "AX1"
        m["fundaciones"][1]["pilotes"][1]["id"] = "EA1"
        auto = autoconstruir_ejes(m)
        self.assertTrue(validar(auto)["valido"])
        self.assertTrue(all(e["id"] not in ("AX1","EA1") for e in auto["ejes"]))
        auto["ejes"][0]["id"] = "AX1"
        self.assertIn("id_eje_invalido",{e["codigo"] for e in validar(auto)["errores"]})


if __name__ == "__main__":
    unittest.main()
