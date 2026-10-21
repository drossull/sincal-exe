"""Perfiles y salidas SVG sin depender de FreeCAD."""

from copy import deepcopy
import json
import unittest
import xml.etree.ElementTree as ET

from pasarela_bim.ejes import autoconstruir_ejes
from pasarela_bim.freecad_backend import _perfil_elevacion, _svg_elevacion
from pasarela_bim.topologia import resolver_modelo


def modelo_ejes():
    """U horizontal: un retorno invertido y cuatro apoyos individuales."""
    nodos = [{"id":i,"uuid":"nodo-"+i,"tipo":tipo,"x":x,"y":y,"z":2}
             for i,tipo,x,y in (("E1","estribo",0,0),("C1","columna",10,0),
                                ("C2","columna",10,5),("E2","estribo",0,5))]
    modelo = {"version":2,"proyecto":{"id":"ejes","uuid":"proyecto-ejes",
              "nombre":"Ensayo U y apoyos","estado":"conceptual","unidades":"m"},
              "nodos":nodos,"familias":{"M":{"tipo":"maciza","canto_m":0.4,
                          "perfil_canto":[{"t":0,"canto_m":0.4},{"t":1,"canto_m":0.6}]}},
              "tramos":[{"id":i,"uuid":"tramo-"+i,"tipo":"viga","funcion":"descanso",
                         "desde":a,"hasta":b,"familia":"M","ancho_m":1.2}
                         for i,a,b in (("V1","E1","C1"),("V2","C2","C1"),("V3","C2","E2"))],
              "fundaciones":[],"soportes":[]}
    modelo["tramos"][1].update(retranqueo_inicio_m=0.2,retranqueo_fin_m=0.4)
    for i,n in enumerate(nodos):
        dado = "D"+str(i+1)
        modelo["fundaciones"].append({"id":dado,"uuid":"fundacion-"+dado,"nodos":[n["id"]],
            "largo_m":3,"ancho_m":3,"alto_m":0.8,"cota_superior_m":-1,"pilotes":[]})
        modelo["soportes"].append({"id":n["id"],"uuid":"soporte-"+n["id"],"nodo":n["id"],
            "fundacion":dado,"diametro_m":0.8,"ancho_m":1.2,"largo_m":1,"cota_superior_m":0.9})
    return autoconstruir_ejes(modelo)


class TestElevaciones(unittest.TestCase):
    def test_eje_recto_tiene_rotulo_longitudinal(self):
        modelo = modelo_ejes()
        modelo.pop("ejes")
        for clave in ("nodos","soportes","fundaciones"):
            modelo[clave] = modelo[clave][:2]
        modelo["tramos"] = modelo["tramos"][:1]
        modelo = autoconstruir_ejes(modelo)
        datos = resolver_modelo(modelo)
        eje = next(e for e in datos["ejes_resueltos"] if e["tipo"] == "recorrido")
        self.assertTrue(eje["es_recto"])
        xml = ET.fromstring(_svg_elevacion(eje,datos["familias"],modelo["proyecto"],"recto"))
        self.assertIn("ELEVACIÓN LONGITUDINAL",xml.find("{*}title").text)
        self.assertNotIn("DESARROLLADA",xml.find("{*}title").text)

    def test_u_desarrollada_estaciones_y_cotas_sin_confundir_retranqueos(self):
        modelo = modelo_ejes()
        datos = resolver_modelo(modelo)
        eje = next(e for e in datos["ejes_resueltos"] if e["tipo"] == "recorrido")
        svg = _svg_elevacion(eje,datos["familias"],modelo["proyecto"],"revision-prueba")
        xml = ET.fromstring(svg)
        textos = " ".join(xml.itertext())
        self.assertIn("ELEVACIÓN DESARROLLADA",textos)
        self.assertIn("E1 / estribo",textos)
        self.assertIn("C1 / cepa",textos)
        self.assertIn("25.000",textos)
        self.assertIn("-1.000 / -1.800",textos)
        metadatos = json.loads(xml.find("{*}metadata").text)
        self.assertEqual([p["estacion_m"] for p in metadatos["estaciones"]],[0,10,15,25])
        self.assertEqual(metadatos["revision_parametros"],"revision-prueba")
        marcas = [g.attrib["id"] for g in xml.findall("{*}g") if g.attrib["id"].startswith("marca-")]
        self.assertEqual(len(marcas),4)
        self.assertEqual(len(set(marcas)),4)
        # El tramo invertido inicia después del retranqueo final de la pieza.
        segmento = eje["segmentos"][1]
        self.assertTrue(segmento["invertido"])
        sup,inf = _perfil_elevacion(segmento,datos["familias"])
        self.assertEqual((sup[0][0],sup[-1][0]),(10400,14800))
        self.assertAlmostEqual(sup[0][1]-inf[0][1],584)
        self.assertAlmostEqual(sup[-1][1]-inf[-1][1],408)

    def test_contorno_peldanos_ascendente_y_descendente(self):
        familia = {"E":{"tipo":"escalera","numero_peldanos":3}}
        segmento = {"familia":"E","puntos_rasante":[{"estacion_mm":100,"z_mm":0},
                   {"estacion_mm":1000,"z_mm":600}],"perfil_canto":[
                   {"estacion_mm":100,"canto_mm":200},{"estacion_mm":1000,"canto_mm":200}]}
        sup,inf = _perfil_elevacion(segmento,familia)
        self.assertEqual(sup,[(100,0),(100,200),(400,200),(400,400),(700,400),(700,600),(1000,600)])
        self.assertEqual(inf,[(100,-200),(1000,400)])
        inverso = deepcopy(segmento)
        inverso["puntos_rasante"][0]["z_mm"],inverso["puntos_rasante"][1]["z_mm"] = 600,0
        sup,inf = _perfil_elevacion(inverso,familia)
        self.assertEqual(sup,[(100,600),(400,600),(400,400),(700,400),(700,200),(1000,200),(1000,0)])
        self.assertEqual(inf,[(100,400),(1000,-200)])

    def test_rotulos_escapados_y_trazabilidad(self):
        modelo = modelo_ejes()
        datos = resolver_modelo(modelo)
        eje = next(e for e in datos["ejes_resueltos"] if e["tipo"] == "recorrido")
        eje["nombre"] = 'Acceso <norte> & "sur"'
        svg = _svg_elevacion(eje,datos["familias"],modelo["proyecto"],"r1")
        xml = ET.fromstring(svg)
        self.assertIn(eje["nombre"],xml.find("{*}title").text)
        self.assertNotIn("<norte>",svg)


if __name__ == "__main__":
    unittest.main()
