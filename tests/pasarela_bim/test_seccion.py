from copy import deepcopy
import unittest

from pasarela_bim.seccion import familia_del_tramo
from pasarela_bim.topologia import validar
from tests.pasarela_bim.test_topologia import ejemplo


class TestSeccionDescanso(unittest.TestCase):
    def setUp(self):
        self.familia = {'tipo': 'maciza', 'canto_mm': 1000}
        self.tramo = {'desde': 'A', 'hasta': 'B', 'rasante': [
            {'t': 0, 'f': 0}, {'t': .425, 'f': .5},
            {'t': .575, 'f': .5}, {'t': 1, 'f': 1}]}
        self.nodos = {'A': {'x': 0, 'y': 0, 'z': 0},
                      'B': {'x': 10000, 'y': 0, 'z': 680}}

    def test_deriva_canto_sin_mutar_familia_tramo_o_nodos(self):
        original = deepcopy((self.familia, self.tramo, self.nodos))
        result = familia_del_tramo(self.familia, self.tramo, self.nodos)
        self.assertEqual([round(p['canto_mm'], 6) for p in result['perfil_canto']],
                         [1120, 1120, 1000, 1000])
        self.assertEqual((self.familia, self.tramo, self.nodos), original)

    def test_datos_no_representables_quedan_para_validacion_sin_excepciones(self):
        for valor in (10**500, float('inf'), float('nan'), True, '1000'):
            with self.subTest(valor=str(valor)[:30]):
                familia = {**self.familia, 'canto_mm': valor}
                self.assertIs(familia_del_tramo(familia, self.tramo, self.nodos), familia)
                tramo = deepcopy(self.tramo)
                tramo['rasante'][1]['t'] = valor
                self.assertIs(familia_del_tramo(self.familia, tramo, self.nodos), self.familia)
        for ref in ([], {}, None, 4):
            self.assertIs(familia_del_tramo(self.familia, {**self.tramo, 'desde': ref}, self.nodos), self.familia)
        nodos = deepcopy(self.nodos)
        nodos['A']['x'], nodos['B']['x'] = -1e308, 1e308
        self.assertIs(familia_del_tramo(self.familia, self.tramo, nodos), self.familia)

    def test_validar_rechaza_canto_enorme_con_descanso_sin_crash(self):
        modelo = ejemplo()
        tramo = modelo['tramos'][0]
        tramo['rasante'] = deepcopy(self.tramo['rasante'])
        modelo['familias'][tramo['familia']]['canto_mm'] = 10**500
        self.assertFalse(validar(modelo)['valido'])


if __name__ == '__main__':
    unittest.main()
