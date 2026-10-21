"""Contrato HTTP local: aislamiento de entradas, sesión y artefactos."""

import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from pasarela_bim.servidor import Aplicacion


class TestServidor(unittest.TestCase):
    def setUp(self):
        self.servidor = Aplicacion(("127.0.0.1", 0))
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.hilo.join(3)

    def solicitud(self, metodo, ruta, datos=None, headers=None):
        conexion = http.client.HTTPConnection("127.0.0.1", self.servidor.server_port, timeout=5)
        cabeceras = {"Content-Type": "application/json", "X-Pasarela-Token": self.servidor.token}
        cabeceras.update(headers or {})
        cuerpo = json.dumps(datos) if datos is not None else None
        conexion.request(metodo, ruta, cuerpo, cabeceras)
        respuesta = conexion.getresponse()
        status, contenido = respuesta.status, respuesta.read()
        conexion.close()
        return status, contenido

    def test_ejemplo_real_valida_y_no_expone_rutas(self):
        status, datos = self.solicitud("GET", "/api/ejemplo")
        self.assertEqual(status, 200)
        status, informe = self.solicitud("POST", "/api/validar", json.loads(datos))
        informe = json.loads(informe)
        self.assertEqual(status, 200)
        self.assertTrue(informe["valido"], informe["errores"])
        self.assertEqual(informe["resumen"]["dados"], 10)
        self.assertEqual(informe["resumen"]["pilotes"], 18)
        status, _ = self.solicitud("GET", "/../../README.md")
        self.assertEqual(status, 404)

    def test_cierre_rechaza_trabajos_y_host_status_no_habilitado_por_defecto(self):
        status,_ = self.solicitud("GET","/api/host-status")
        self.assertEqual(status,404)
        self.servidor.trabajos["activo"] = {"estado":"ejecutando"}
        status,_ = self.solicitud("POST","/api/cerrar",{})
        self.assertEqual(status,409)
        self.assertFalse(self.servidor.cerrando)
        self.servidor.trabajos.clear()
        self.servidor.importaciones = 1
        status,_ = self.solicitud("POST","/api/cerrar",{})
        self.assertEqual(status,409)
        self.servidor.importaciones = 0
        self.servidor.cerrando = True
        status,_ = self.solicitud("POST","/api/validar",{})
        self.assertEqual(status,409)

    def test_sesion_origen_y_host(self):
        for headers in ({"X-Pasarela-Token": "incorrecto"}, {"X-Pasarela-Token": "ñ"},
                        {"Origin": "https://otro.example"}, {"Host": "otro.example"}):
            with self.subTest(headers=headers):
                status, _ = self.solicitud("POST", "/api/validar", {}, headers)
                self.assertEqual(status, 403)
        status, _ = self.solicitud("POST", "/api/validar", {}, {"Content-Type": "text/plain"})
        self.assertEqual(status, 415)

    def test_modelo_roto_no_inicia_freecad(self):
        with patch("pasarela_bim.servidor.generar_aislado") as generar:
            status, cuerpo = self.solicitud("POST", "/api/generar", {})
        self.assertEqual(status, 422)
        self.assertFalse(json.loads(cuerpo)["valido"])
        generar.assert_not_called()

    def test_planta_upload_y_scripts_del_editor(self):
        from tests.pasarela_bim.test_planta import drawing
        conexion = http.client.HTTPConnection("127.0.0.1", self.servidor.server_port, timeout=5)
        contenido = drawing("0\nLINE\n8\nCAMINO\n10\n350000\n20\n6000000\n11\n350020\n21\n6000000\n")
        conexion.request("POST", "/api/planta", contenido, {"Content-Type":"application/octet-stream",
            "X-Pasarela-Token":self.servidor.token, "X-File-Name":"planta.dxf"})
        respuesta = conexion.getresponse()
        self.assertEqual(respuesta.status,200)
        planta = json.loads(respuesta.read())
        self.assertEqual(planta["capas"],["CAMINO"])
        self.assertEqual(planta["entidades"][0]["puntos_m"][0],[350000,6000000,0])
        conexion.close()
        for recurso in ("/proyecto.js", "/emplazamiento.js", "/secciones.js", "/ejes.js"):
            self.assertEqual(self.solicitud("GET",recurso)[0],200)

    def test_borrador_vacio_se_puede_validar_pero_no_generar(self):
        modelo = {"version":2,"proyecto":{"id":"vacio","nombre":"Vacio","estado":"borrador","unidades":"m"},
                  "nodos":[],"tramos":[],"familias":{},"soportes":[],"fundaciones":[]}
        status, content = self.solicitud("POST","/api/validar",modelo)
        self.assertEqual(status,200)
        result = json.loads(content)
        self.assertTrue(result["valido"])
        self.assertFalse(result["generable"])
        self.assertTrue(result["pendientes"])
        self.assertEqual(self.solicitud("POST","/api/generar",modelo)[0],422)

    def test_json_profundo_y_unicode_no_cierran_la_conexion(self):
        conexion = http.client.HTTPConnection("127.0.0.1", self.servidor.server_port, timeout=5)
        conexion.request("POST", "/api/validar", "[" * 10000 + "]" * 10000,
                         {"Content-Type": "application/json", "X-Pasarela-Token": self.servidor.token})
        respuesta = conexion.getresponse()
        self.assertEqual(respuesta.status, 400)
        respuesta.read()
        conexion.close()
        modelo = json.loads(self.solicitud("GET", "/api/ejemplo")[1])
        modelo["pendientes_documentales"] = ["\ud800"]
        status, contenido = self.solicitud("POST", "/api/validar", modelo)
        self.assertEqual(status, 200)
        self.assertIn("avisos", json.loads(contenido))

    def test_trabajo_aislado_y_descarga_autorizada(self):
        modelo = json.loads(self.solicitud("GET", "/api/ejemplo")[1])
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal) / "trabajo"

            def generador(entrada, salida):
                carpeta.mkdir()
                (carpeta / "modelo.FCStd").write_bytes(b"modelo de ensayo HTTP")
                return {"archivos": ["modelo.FCStd"], "resultado": {"verificado": True}}

            with patch("pasarela_bim.servidor.localizar_freecad", return_value=Path("freecad.exe")), \
                 patch("pasarela_bim.servidor.nueva_salida", return_value=carpeta), \
                 patch("pasarela_bim.servidor.generar_aislado", side_effect=generador):
                status, respuesta = self.solicitud("POST", "/api/generar", modelo)
                self.assertEqual(status, 202)
                id_trabajo = json.loads(respuesta)["trabajo_id"]
                for _ in range(100):
                    _, estado = self.solicitud("GET", "/api/trabajos/" + id_trabajo)
                    estado = json.loads(estado)
                    if estado["estado"] != "ejecutando":
                        break
                    time.sleep(0.01)
                self.assertEqual(estado["estado"], "completado")
                self.assertNotIn("carpeta", estado)
                status, contenido = self.solicitud("GET", estado["archivos"][0]["url"])
                self.assertEqual((status, contenido), (200, b"modelo de ensayo HTTP"))
                status, _ = self.solicitud("GET", f"/api/archivos/{id_trabajo}/generar.FCMacro")
                self.assertEqual(status, 404)
                (carpeta / "modelo.FCStd").unlink()
                status, _ = self.solicitud("GET", estado["archivos"][0]["url"])
                self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
