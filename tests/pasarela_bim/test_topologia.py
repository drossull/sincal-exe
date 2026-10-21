"""Pruebas del contrato y sus invariantes, sin FreeCAD ni paquetes externos."""

from copy import deepcopy
import math
import unittest

from pasarela_bim.topologia import interpolar_rasante, resolver_modelo, validar


def ejemplo():
    nodos = [
        {"id": "E1", "tipo": "estribo", "x": 0, "y": 0, "z": 5000},
        {"id": "C1", "tipo": "columna", "x": 10000, "y": 0, "z": 5500},
        {"id": "C2", "tipo": "columna", "x": 10000, "y": 5000, "z": 5500},
        {"id": "E2", "tipo": "estribo", "x": 0, "y": 5000, "z": 5000},
    ]
    return {
        "version": 1,
        "proyecto": {"id": "PRUEBA", "nombre": "Pasarela de prueba", "estado": "conceptual", "unidades": "mm"},
        "nodos": nodos,
        "tramos": [
            {"id": "V1", "desde": "E1", "hasta": "C1", "tipo": "viga", "familia": "cajon", "ancho_mm": 2000},
            {"id": "R1", "desde": "C1", "hasta": "C2", "tipo": "retorno", "familia": "macizo", "ancho_mm": 2000},
            {"id": "V2", "desde": "C2", "hasta": "E2", "tipo": "viga", "familia": "cajon", "ancho_mm": 2000},
        ],
        "familias": {
            "cajon": {"canto_mm": 800, "ancho_inferior_mm": 900, "ancho_alma_superior_mm": 1200,
                      "ala_mm": 400, "losa_superior_mm": 150, "losa_inferior_mm": 100, "alma_mm": 100, "macizado_mm": 300},
            "macizo": {"canto_mm": 600},
        },
        "fundaciones": [
            {"id": "D1", "nodos": ["E1"], "largo_mm": 3000, "ancho_mm": 2500, "alto_mm": 1000, "cota_superior_mm": 0, "pilotes": []},
            {"id": "D2", "nodos": ["C1", "C2"], "largo_mm": 7000, "ancho_mm": 3000, "alto_mm": 1000, "cota_superior_mm": 0,
             "pilotes": [{"id": "P1", "dx_mm": -2000, "dy_mm": 0, "diametro_mm": 1000, "longitud_mm": 15000},
                         {"id": "P2", "dx_mm": 2000, "dy_mm": 0, "diametro_mm": 1000, "longitud_mm": 15000}]},
            {"id": "D3", "nodos": ["E2"], "largo_mm": 3000, "ancho_mm": 2500, "alto_mm": 1000, "cota_superior_mm": 0, "pilotes": []},
        ],
        "soportes": [
            {"id": "E1", "nodo": "E1", "fundacion": "D1", "ancho_mm": 2000, "largo_mm": 1000, "cota_superior_mm": 4000},
            {"id": "C1", "nodo": "C1", "fundacion": "D2", "diametro_mm": 1000, "cota_superior_mm": 4500},
            {"id": "C2", "nodo": "C2", "fundacion": "D2", "diametro_mm": 1000, "cota_superior_mm": 4500},
            {"id": "E2", "nodo": "E2", "fundacion": "D3", "ancho_mm": 2000, "largo_mm": 1000, "cota_superior_mm": 4000},
        ],
        "pendientes_documentales": ["Confirmar longitud del perno del detalle"], "vistas": [],
    }


class TestTopologia(unittest.TestCase):
    def assert_error(self, modelo, codigo):
        informe = validar(modelo)
        self.assertFalse(informe["valido"])
        self.assertIn(codigo, {e["codigo"] for e in informe["errores"]})

    def test_recorrido_e_inventario_con_dado_compartido_unico(self):
        informe = validar(ejemplo())
        self.assertTrue(informe["valido"], informe["errores"])
        self.assertEqual(informe["recorrido"], ["E1", "C1", "C2", "E2"])
        self.assertEqual(informe["resumen"], {"nodos": 4, "tramos": 3, "vigas": 2, "retornos": 1,
                                             "fustes": 2, "estribos": 2, "dados": 3, "pilotes": 2})
        self.assertEqual(informe["avisos"][0]["codigo"], "pendiente_documental")

    def test_compartir_dado_no_repara_recorrido_roto(self):
        modelo = ejemplo()
        modelo["tramos"].pop(1)
        self.assert_error(modelo, "recorrido_desconectado")

    def test_ids_globales_y_alias_soporte(self):
        modelo = ejemplo()
        self.assertTrue(validar(modelo)["valido"])
        modelo["fundaciones"][1]["pilotes"][0]["id"] = "V1"
        self.assert_error(modelo, "id_duplicado")
        modelo = ejemplo()
        modelo["soportes"].append(deepcopy(modelo["soportes"][0]))
        self.assert_error(modelo, "id_duplicado")
        self.assert_error(modelo, "cantidad_soportes")

    def test_nodo_no_puede_pertenecer_a_dos_dados(self):
        modelo = ejemplo()
        modelo["fundaciones"][0]["nodos"].append("C1")
        self.assert_error(modelo, "pertenencia_fundacion")
        modelo = ejemplo()
        modelo["fundaciones"][1]["nodos"].append("C1")
        self.assert_error(modelo, "pertenencia_duplicada")

    def test_referencias_desconocidas(self):
        for entidad, clave, codigo in (("tramos", "hasta", "referencia_nodo"),
                                      ("tramos", "familia", "referencia_familia"),
                                      ("soportes", "fundacion", "referencia_fundacion")):
            with self.subTest(entidad=entidad, clave=clave):
                modelo = ejemplo()
                modelo[entidad][0][clave] = "NO_EXISTE"
                self.assert_error(modelo, codigo)

    def test_entradas_malformadas_no_producen_excepciones(self):
        for valor in (None, [], 1, "texto", {}):
            with self.subTest(valor=valor):
                self.assertFalse(validar(valor)["valido"])
        for valor in (False, float("nan"), float("inf"), -1, 0, "800", 10**500):
            with self.subTest(valor=str(valor)[:30]):
                modelo = ejemplo()
                modelo["familias"]["cajon"]["canto_mm"] = valor
                self.assert_error(modelo, "dimension_invalida")
        for clave in ("nodos", "tramos", "fundaciones", "soportes"):
            modelo = ejemplo()
            modelo[clave] = [None, 1, []]
            self.assert_error(modelo, "entidad_invalida")

    def test_cajon_degenerado_y_retranqueos(self):
        modelo = ejemplo()
        modelo["familias"]["cajon"]["canto_mm"] = 250
        self.assert_error(modelo, "cajon_sin_hueco")
        modelo = ejemplo()
        modelo["familias"]["cajon"]["alma_mm"] = 450
        self.assert_error(modelo, "cajon_sin_hueco")
        modelo = ejemplo()
        modelo["tramos"][0].update(retranqueo_inicio_mm=5000, retranqueo_fin_mm=5000)
        self.assert_error(modelo, "retranqueos_excesivos")
        modelo = ejemplo()
        modelo["familias"]["cajon"]["macizado_mm"] = 5000
        self.assert_error(modelo, "macizados_excesivos")

    def test_tipo_familia_independiente_del_tipo_topologico(self):
        modelo = ejemplo()
        modelo["tramos"][0]["familia"] = "macizo"
        modelo["familias"]["macizo"]["tipo"] = "maciza"
        self.assertTrue(validar(modelo)["valido"])
        modelo["familias"]["macizo"]["tipo"] = "cajon"
        self.assert_error(modelo, "dimension_invalida")
        modelo["familias"]["macizo"]["tipo"] = "desconocido"
        self.assert_error(modelo, "tipo_familia_invalido")

    def test_coordenadas_finitas_no_admiten_distancia_desbordada(self):
        modelo = ejemplo()
        modelo["nodos"][0]["x"] = -1e308
        modelo["nodos"][1]["x"] = 1e308
        self.assert_error(modelo, "longitud_invalida")

    def test_descanso_y_retranqueos_conservan_rasante(self):
        modelo = ejemplo()
        modelo["tramos"][0].update(retranqueo_inicio_mm=1000, retranqueo_fin_mm=500,
            rasante=[{"t": 0, "f": 0}, {"t": 0.4, "f": 0.5}, {"t": 0.6, "f": 0.5}, {"t": 1, "f": 1}])
        original = deepcopy(modelo)
        resuelto = resolver_modelo(modelo)
        tramo = resuelto["tramos"][0]
        self.assertEqual(modelo, original)
        self.assertAlmostEqual(tramo["longitud_util_mm"], 8500)
        self.assertEqual(tramo["inicio"], [1000, 0, 5062.5])
        self.assertEqual(tramo["puntos_eje"][1], [4000, 0, 5250])
        self.assertEqual(tramo["puntos_eje"][2], [6000, 0, 5250])
        self.assertAlmostEqual(tramo["fin"][2], 5468.75)

    def test_rasante_desordenada_y_canto_variable(self):
        modelo = ejemplo()
        modelo["tramos"][0]["rasante"] = [{"t": 0, "f": 0}, {"t": 0, "f": 0.4}, {"t": 1, "f": 1}]
        self.assert_error(modelo, "orden_rasante")
        modelo = ejemplo()
        modelo["tramos"][0]["rasante"] = [{"t": 0, "f": 0}, {"t": 0.4, "f": 0.8}, {"t": 0.6, "f": 0.2}, {"t": 1, "f": 1}]
        self.assert_error(modelo, "orden_rasante")
        modelo = ejemplo()
        modelo["familias"]["cajon"]["perfil_canto"] = [{"t": 0, "canto_mm": 600}, {"t": 0.46, "canto_mm": 600},
                                                          {"t": 0.54, "canto_mm": 720}, {"t": 1, "canto_mm": 720}]
        self.assertTrue(validar(modelo)["valido"])
        modelo["familias"]["cajon"]["perfil_canto"][1]["canto_mm"] = 240
        self.assert_error(modelo, "cajon_sin_hueco")

    def test_rotacion_dado_pilotes_y_altura_soporte(self):
        resuelto = resolver_modelo(ejemplo())
        dado = resuelto["fundaciones"][1]
        self.assertEqual(dado["centro"], [10000, 2500, 0])
        self.assertAlmostEqual(dado["angulo_deg"], 90)
        self.assertAlmostEqual(dado["pilotes"][0]["centro"][0], 10000)
        self.assertAlmostEqual(dado["pilotes"][0]["centro"][1], 500)
        self.assertEqual(dado["pilotes"][0]["centro"][2], -1000)
        self.assertEqual(resuelto["soportes"][1]["altura_mm"], 4500)

    def test_soporte_entre_dado_y_rasante(self):
        for cota, codigo in ((5500, "soporte_sobre_rasante"), (0, "soporte_sin_altura")):
            modelo = ejemplo()
            modelo["soportes"][1]["cota_superior_mm"] = cota
            self.assert_error(modelo, codigo)
        modelo = ejemplo()
        modelo["soportes"][1]["cota_superior_mm"] = 4800
        self.assert_error(modelo, "soporte_atraviesa_intrados")

    def test_huellas_en_dado_compartido_corto_o_rotado(self):
        modelo = ejemplo()
        modelo["fundaciones"][1]["largo_mm"] = 5500
        self.assert_error(modelo, "soporte_fuera_dado")
        modelo = ejemplo()
        modelo["fundaciones"][1]["angulo_deg"] = 0
        self.assert_error(modelo, "soporte_fuera_dado")
        modelo["fundaciones"][1]["angulo_deg"] = 90
        self.assertTrue(validar(modelo)["valido"])

    def test_pilote_fuera_dado_incluye_radio(self):
        modelo = ejemplo()
        modelo["fundaciones"][1]["pilotes"][0]["dx_mm"] = 3100
        self.assert_error(modelo, "pilote_fuera_dado")
        modelo = ejemplo()
        modelo["fundaciones"][1]["pilotes"][0]["dy_mm"] = 1100
        self.assert_error(modelo, "pilote_fuera_dado")

    def test_huella_estribo_sigue_orientacion_dado(self):
        modelo = ejemplo()
        modelo["fundaciones"][0].update(largo_mm=7000, ancho_mm=2500, angulo_deg=90)
        modelo["soportes"][0].update(largo_mm=6500, ancho_mm=2000)
        self.assertTrue(validar(modelo)["valido"])
        modelo["soportes"][0]["largo_mm"] = 7001
        self.assert_error(modelo, "soporte_fuera_dado")

    def test_datos_anidados_malformados_producen_errores(self):
        cambios = [
            ("nodos", 0, "id", []), ("nodos", 0, "x", {}),
            ("tramos", 0, "desde", []), ("tramos", 0, "familia", {}), ("tramos", 0, "rasante", [None]),
            ("fundaciones", 0, "nodos", [{}]), ("fundaciones", 0, "pilotes", [None]),
            ("fundaciones", 0, "angulo_deg", []), ("soportes", 0, "nodo", []),
            ("soportes", 0, "id", {}), ("soportes", 0, "fundacion", []),
        ]
        for grupo, indice, clave, valor in cambios:
            with self.subTest(grupo=grupo, clave=clave):
                modelo = ejemplo()
                modelo[grupo][indice][clave] = valor
                self.assertFalse(validar(modelo)["valido"])

    def test_circuitos_y_bifurcaciones_son_avisos(self):
        modelo = ejemplo()
        modelo["tramos"].append({"id": "R2", "desde": "E2", "hasta": "E1", "tipo": "retorno", "familia": "macizo", "ancho_mm": 2000})
        informe = validar(modelo)
        self.assertTrue(informe["valido"], informe["errores"])
        self.assertEqual(informe["recorrido"], [])
        self.assertIn("recorrido_circuito", {a["codigo"] for a in informe["avisos"]})
        modelo["tramos"].append({"id": "R3", "desde": "E1", "hasta": "C2", "tipo": "retorno", "familia": "macizo", "ancho_mm": 2000})
        informe = validar(modelo)
        self.assertTrue(informe["valido"], informe["errores"])
        self.assertIn("recorrido_bifurcado", {a["codigo"] for a in informe["avisos"]})

    def test_resolver_rechaza_modelo_invalido(self):
        with self.assertRaisesRegex(ValueError, "Modelo inválido"):
            resolver_modelo({})
        with self.assertRaises(ValueError):
            interpolar_rasante([{"t": 0, "f": 0}, {"t": 1, "f": 1}], math.inf)


if __name__ == "__main__":
    unittest.main()
