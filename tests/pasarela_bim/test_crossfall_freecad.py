import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('FreeCAD'), 'Requiere FreeCAD')
class CrossfallTest(unittest.TestCase):
    def test_continuous_beam_with_central_landing(self):
        import FreeCAD as App
        import Part
        from pasarela_bim.freecad_backend import _tramo_shape
        edge=dict(id='V',tipo='viga',desde='A',hasta='B',longitud_planta_mm=10000,ancho_mm=2000,ux=1,uy=0,
                  rasante=[dict(t=0,f=0),dict(t=.425,f=.5),dict(t=.575,f=.5),dict(t=1,f=1)])
        family=dict(tipo='cajon',canto_mm=1000,ancho_alma_superior_mm=1260,ancho_inferior_mm=1000,
                    losa_superior_mm=150,losa_inferior_mm=140,alma_mm=140,macizado_mm=500)
        shape=_tramo_shape(Part,App,edge,family,dict(A=dict(x=0,y=0,z=5000),B=dict(x=10000,y=0,z=5680)))
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids),1)
        self.assertAlmostEqual(shape.BoundBox.XLength,10000)
        self.assertAlmostEqual(shape.BoundBox.YLength,2000)
        for x in [4250,5000,5750]:
            self.assertLess(shape.distToShape(Part.Vertex(App.Vector(x,0,5340)))[0],1e-6)
        for x in [0,2000,4250,5000,5750,8000,10000]:
            self.assertLess(shape.distToShape(Part.Vertex(App.Vector(x,0,3880+.08*x)))[0],1e-6)
        down=_tramo_shape(Part,App,edge,family,dict(A=dict(x=0,y=0,z=5680),B=dict(x=10000,y=0,z=5000)))
        self.assertTrue(down.isValid())
        for x in [0,2000,4250,5000,5750,8000,10000]:
            self.assertLess(down.distToShape(Part.Vertex(App.Vector(x,0,4680-.08*x)))[0],1e-6)
        with self.assertRaises(ValueError):
            _tramo_shape(Part,App,edge,{**family,'macizado_mm':300},dict(A=dict(x=0,y=0,z=5000),B=dict(x=10000,y=0,z=5680)))

    def test_volume_and_surface(self):
        import FreeCAD as App
        import Part
        from pasarela_bim.freecad_backend import _tramo_shape
        edge = dict(id='V', tipo='viga', desde='a', hasta='b', longitud_planta_mm=10000,
                    ancho_mm=2000, ux=1, uy=0, rasante=[dict(t=0,f=0),dict(t=1,f=1)])
        nodes = dict(a=dict(x=0,y=0,z=5000),b=dict(x=10000,y=0,z=5800))
        family = dict(tipo='cajon',canto_mm=1450,ancho_alma_superior_mm=1260,
                      ancho_inferior_mm=1000,losa_superior_mm=150,losa_inferior_mm=140,
                      alma_mm=140,macizado_mm=500)
        for kind in ['cajon', 'maciza']:
            family['tipo'] = kind
            if kind == 'maciza':
                family['ancho_inferior_mm'] = 2000
            legacy = _tramo_shape(Part,App,edge,family,nodes)
            slope = _tramo_shape(Part,App,edge,{**family,'pendiente_transversal_pct':1},nodes)
            self.assertTrue(slope.isValid())
            self.assertEqual(len(slope.Solids),1)
            self.assertAlmostEqual(legacy.Volume,slope.Volume,delta=1)
            for y in [-1000,0,1000]:
                p=App.Vector(0,y,5000-abs(y)*.01)
                self.assertLess(slope.distToShape(Part.Vertex(p))[0],1e-6)
            with self.assertRaises(ValueError):
                _tramo_shape(Part,App,edge,{**family,'pendiente_transversal_pct':100},nodes)


if __name__ == '__main__':
    unittest.main()
