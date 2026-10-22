"""Intercambio, cotas declaradas y borradores sin dependencias CAD."""

from copy import deepcopy
import math
import unittest

from pasarela_bim.proyecto import (convertir_a_interno, convertir_a_portable,
                                  local_a_global, global_a_local, validar_georreferencia)
from pasarela_bim.topologia import validar, resolver_modelo


def proyecto_simple(tipo="maciza"):
    return {"version":2,"proyecto":{"id":"demo","uuid":"p-identidad-estable",
            "nombre":"Prueba portable","estado":"borrador","unidades":"m","revision":3},
            "nodos":[{"id":"A","uuid":"nodo-a","tipo":"encuentro","x":0,"y":0,"z":0},
                     {"id":"B","uuid":"nodo-b","tipo":"encuentro","x":6,"y":0,"z":3 if tipo=="escalera" else 0.48}],
            "tramos":[{"id":"T1","uuid":"tramo-estable","desde":"A","hasta":"B",
                       "tipo":"viga","funcion":"escalera" if tipo=="escalera" else "rampa",
                       "familia":"familia_m","ancho_m":2,"retranqueo_inicio_m":0,
                       "retranqueo_fin_m":0}],
            "familias":{"familia_m":{"tipo":tipo,"canto_m":0.2,
                                        **({"numero_peldanos":20} if tipo=="escalera" else {})}},
            "fundaciones":[],"soportes":[],
            "georreferencia":{"este_m":666123.25,"norte_m":5923123.75,"cota_m":102.4,
                               "norte_desde_x_horario_deg":270,"crs":"EPSG:32718"},
            "emplazamiento":{"planta":[{"x_m":666120,"y_m":5923100}],"terreno":{"cota_m":0}}}


class TestProyecto(unittest.TestCase):
    def test_roundtrip_metros_y_metadatos_sin_mutacion(self):
        portable = proyecto_simple()
        portable["proyecto"].update(galibo_m=5.5,cota_carretera_m=-1)
        portable["familias"]["familia_m"]["perfil_canto"] = [{"t":0,"canto_m":0.2},{"t":1,"canto_m":0.4}]
        portable["nodos"][0]["metadatos"] = {"sondeo_m":17.3,"revision":"A"}
        original = deepcopy(portable)
        interno = convertir_a_interno(portable)
        self.assertEqual(portable,original)
        self.assertEqual(interno["nodos"][1]["x"],6000)
        self.assertEqual(interno["tramos"][0]["ancho_mm"],2000)
        self.assertEqual(interno["familias"]["familia_m"]["perfil_canto"][1]["canto_mm"],400)
        self.assertEqual(interno["georreferencia"],portable["georreferencia"])
        self.assertEqual(interno["emplazamiento"],portable["emplazamiento"])
        self.assertEqual(interno["nodos"][0]["metadatos"],portable["nodos"][0]["metadatos"])
        self.assertEqual(interno["proyecto"]["galibo_m"],5.5)
        canonico = deepcopy(portable)
        canonico["proyecto"]["esquema_intercambio"] = 2
        self.assertEqual(convertir_a_portable(interno),canonico)
        self.assertEqual(convertir_a_interno(interno),interno)

    def test_version_unidad_y_dimensiones_ambiguas_rechazadas(self):
        m = proyecto_simple()
        m["proyecto"]["unidades"] = "mm"
        with self.assertRaises(ValueError):
            convertir_a_interno(m)
        self.assertFalse(validar(m)["valido"])
        m = proyecto_simple()
        m["familias"]["familia_m"]["canto_mm"] = 200
        with self.assertRaises(ValueError):
            convertir_a_interno(m)

    def test_terreno_por_apoyo_convierte_sin_completar_ausentes_desde_legado(self):
        portable = proyecto_simple()
        portable["proyecto"].update(cota_terreno_m=-9, cota_carretera_m=-8)
        portable["soportes"] = [
            {"id": "A", "nodo": "A", "fundacion": "D1", "cota_terreno_proyectado_m": -6.25},
            {"id": "B", "nodo": "B", "fundacion": "D1", "cota_terreno_proyectado_m": -5.9},
            {"id": "C", "nodo": "C", "fundacion": "D2"}]
        original = deepcopy(portable)
        interno = convertir_a_interno(portable)
        self.assertEqual(interno["soportes"][0]["cota_terreno_proyectado_mm"], -6250)
        self.assertEqual(interno["soportes"][1]["cota_terreno_proyectado_mm"], -5900)
        self.assertNotIn("cota_terreno_proyectado_mm", interno["soportes"][2])
        self.assertEqual(interno["proyecto"]["cota_terreno_m"], -9)
        vuelta = convertir_a_portable(interno)
        self.assertEqual(vuelta["soportes"], portable["soportes"])
        self.assertEqual(portable, original)

    def test_encuentros_libres_generan_sin_inventar_soportes(self):
        informe = validar(proyecto_simple())
        self.assertTrue(informe["valido"],informe["errores"])
        self.assertTrue(informe["generable"])
        resuelto = resolver_modelo(proyecto_simple())
        self.assertEqual(resuelto["version"],1)
        self.assertEqual(resuelto["tramos"][0]["longitud_planta_mm"],6000)
        self.assertEqual(resuelto["fundaciones"],[])

    def test_faltan_apoyos_es_pendiente_solo_en_borrador(self):
        m = proyecto_simple()
        for n in m["nodos"]:
            n["tipo"] = "columna"
        borrador = validar(m,borrador=True)
        self.assertTrue(borrador["valido"])
        self.assertFalse(borrador["generable"])
        self.assertEqual({e["codigo"] for e in borrador["pendientes"]},
                         {"pertenencia_fundacion","cantidad_soportes"})
        self.assertFalse(validar(m)["valido"])
        with self.assertRaises(ValueError):
            resolver_modelo(m)

    def test_borrador_no_oculta_geometria_invalida_ni_referencias_rotas(self):
        m = proyecto_simple()
        m["familias"]["familia_m"]["canto_m"] = -0.2
        self.assertFalse(validar(m,borrador=True)["valido"])
        m = proyecto_simple()
        m["tramos"][0]["hasta"] = "NO_EXISTE"
        self.assertFalse(validar(m,borrador=True)["valido"])

    def test_duplicar_entidad_no_puede_reutilizar_uuid(self):
        m = proyecto_simple()
        m["nodos"][1]["uuid"] = m["nodos"][0]["uuid"]
        self.assertIn("uuid_duplicado",{e["codigo"] for e in validar(m)["errores"]})

    def test_lienzo_vacio_es_borrador_no_generable(self):
        m = proyecto_simple()
        m["nodos"],m["tramos"] = [],[]
        informe = validar(m,borrador=True)
        self.assertTrue(informe["valido"])
        self.assertFalse(informe["generable"])

    def test_norte_horario_y_datum_vertical(self):
        geo = proyecto_simple()["georreferencia"]
        globales = local_a_global(12,8,3,geo)
        self.assertAlmostEqual(globales["este_m"],geo["este_m"]+12)
        self.assertAlmostEqual(globales["norte_m"],geo["norte_m"]+8)
        self.assertAlmostEqual(globales["cota_m"],105.4)
        geo["norte_desde_x_horario_deg"] = 0
        globales = local_a_global(12,8,3,geo)
        self.assertAlmostEqual(globales["este_m"],geo["este_m"]-8)
        self.assertAlmostEqual(globales["norte_m"],geo["norte_m"]+12)
        for angulo in (0,30,90,180,270,359):
            geo["norte_desde_x_horario_deg"] = angulo
            r = local_a_global(12.3,-7.8,4.5,geo)
            vuelta = global_a_local(r["este_m"],r["norte_m"],r["cota_m"],geo)
            for eje,esperado in zip("xyz",(12.3,-7.8,4.5)):
                self.assertAlmostEqual(vuelta[eje],esperado,places=8)

    def test_georreferencia_no_infiere_crs_ni_acepta_nan(self):
        geo = proyecto_simple()["georreferencia"]
        geo.pop("crs")
        self.assertEqual(validar_georreferencia(geo),[])
        geo["norte_m"] = math.nan
        self.assertTrue(validar_georreferencia(geo))
        m = proyecto_simple()
        m["georreferencia"] = geo
        self.assertFalse(validar(m)["valido"])

    def test_georreferencia_canonica_en_proyecto_se_conserva_y_valida(self):
        m = proyecto_simple()
        m["proyecto"]["georreferencia"] = m.pop("georreferencia")
        interno = convertir_a_interno(m)
        self.assertEqual(interno["proyecto"]["georreferencia"],m["proyecto"]["georreferencia"])
        self.assertTrue(validar(m)["valido"])
        m["proyecto"]["georreferencia"]["norte_desde_x_horario_deg"] = 360
        self.assertIn("georreferencia_invalida",{e["codigo"] for e in validar(m)["errores"]})

    def test_galibo_pendiente_no_infiere_calzada_de_cota_global_legacy(self):
        m = proyecto_simple()
        for n in m["nodos"]:
            n["z"] = 6
        m["tramos"][0]["funcion"] = "cruce"
        m["proyecto"].update(cota_carretera_m=1,galibo_m=5)
        r = validar(m)
        self.assertTrue(r["valido"])
        self.assertTrue(r["generable"])
        self.assertEqual(r["comprobaciones"][0]["estado"],"pendiente")
        self.assertEqual(r["comprobaciones"][0]["objetivo_m"],5)
        self.assertNotIn("galibo_minimo_m",r["comprobaciones"][0])
        m["proyecto"].pop("cota_carretera_m")
        self.assertEqual(validar(m)["comprobaciones"][0]["estado"],"pendiente")

    def test_escalera_resuelve_huella_y_rechaza_rasante_ambigua(self):
        m = proyecto_simple("escalera")
        tramo = resolver_modelo(m)["tramos"][0]
        self.assertAlmostEqual(tramo["huella_mm"],300)
        self.assertAlmostEqual(tramo["contrahuella_mm"],150)
        m["tramos"][0]["rasante"] = [{"t":0,"f":0},{"t":0.5,"f":0.4},{"t":1,"f":1}]
        self.assertIn("rasante_escalera",{e["codigo"] for e in validar(m)["errores"]})

    def test_regla_fija_8_calcula_geometria_y_no_confia_en_etiqueta(self):
        m = proyecto_simple()
        self.assertTrue(validar(m)["valido"])
        m["nodos"][1]["z"] = 0.474  # 7,9 %, aunque se declare otro valor en el tramo.
        m["tramos"][0]["pendiente_pct"] = 8
        self.assertIn("pendiente_fija_8",{e["codigo"] for e in validar(m)["errores"]})
        m = proyecto_simple()
        m["proyecto"]["reglas"] = {"pendiente_rampas_pct":7.9}
        self.assertIn("pendiente_fija_no_modificable",{e["codigo"] for e in validar(m)["errores"]})
        m["proyecto"]["reglas"]["pendiente_rampas_pct"] = 8
        m["nodos"][1]["z"] = -0.48
        self.assertTrue(validar(m)["valido"])

    def test_meseta_en_rampa_verifica_pendiente_de_cada_segmento(self):
        m = proyecto_simple()
        m["nodos"][1]["z"] = 0.36
        m["tramos"][0]["rasante"] = [{"t":0,"f":0},{"t":0.375,"f":0.5},{"t":0.625,"f":0.5},{"t":1,"f":1}]
        self.assertTrue(validar(m)["valido"])
        m["tramos"][0]["rasante"][1]["t"] = 0.4
        self.assertIn("pendiente_fija_8",{e["codigo"] for e in validar(m)["errores"]})

    def test_horizontal_debe_clasificarse_y_retorno_no_puede_inclinarse(self):
        m = proyecto_simple()
        m["nodos"][1]["z"] = 0
        self.assertIn("rampa_sin_desnivel",{e["codigo"] for e in validar(m)["errores"]})
        m["tramos"][0]["funcion"] = "descanso"
        self.assertTrue(validar(m)["valido"])
        m["tramos"][0]["funcion"] = "retorno"
        m["nodos"][1]["z"] = 0.48
        self.assertIn("descanso_inclinado",{e["codigo"] for e in validar(m)["errores"]})

    def test_v2_no_evade_regla_eliminando_funcion_incluso_tras_convertir(self):
        m = proyecto_simple()
        m["tramos"][0].pop("funcion")
        for variante in (m,convertir_a_interno(m)):
            self.assertIn("funcion_requerida",{e["codigo"] for e in validar(variante)["errores"]})
            borrador = validar(variante,borrador=True)
            self.assertTrue(borrador["valido"])
            self.assertFalse(borrador["generable"])
        legado = convertir_a_interno(m)
        legado["proyecto"].pop("esquema_intercambio")
        self.assertTrue(validar(legado)["valido"])
        self.assertIn("funcion_legacy_sin_verificar",{a["codigo"] for a in validar(legado)["avisos"]})


if __name__ == "__main__":
    unittest.main()
