"""Apertura y guardado nativos: sesión, límites y protección frente al cierre."""

from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import threading
import time
import unittest
from unittest.mock import Mock, patch

from pasarela_bim.archivos import FileBusy, FileConflict
from pasarela_bim.servidor import Aplicacion, MAX_BODY


class TestArchivosHTTP(unittest.TestCase):
    def setUp(self):
        self.files = Mock(available=True)
        self.documento = {"id": "documento-autorizado", "nombre": "Pasarela.json", "ruta": "C:/Proyectos/Pasarela.json"}
        self.modelo = {"version": 2, "proyecto": {"nombre": "Pasarela de ensayo"}, "nodos": []}
        self.files.open_project.return_value = {"documento": self.documento, "modelo": self.modelo}
        self.files.save_project.return_value = {"guardado": True, "documento": self.documento}
        with patch("pasarela_bim.servidor.ProjectFiles", return_value=self.files):
            self.servidor = Aplicacion(("127.0.0.1", 0))
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.hilo.join(3)

    def solicitud(self, ruta, datos=None, *, headers=None, raw=None, metodo="POST"):
        conexion = http.client.HTTPConnection("127.0.0.1", self.servidor.server_port, timeout=5)
        cabeceras = {"Content-Type": "application/json", "X-Pasarela-Token": self.servidor.token}
        cabeceras.update(headers or {})
        cuerpo = raw if raw is not None else json.dumps(datos if datos is not None else {}).encode("utf-8")
        # Evita que Windows aborte el envio del cuerpo tras un rechazo temprano.
        with patch.object(conexion, "send") as enviar:
            conexion.request(metodo, ruta, cuerpo if metodo == "POST" else None, cabeceras)
        conexion.send(b"".join(llamada.args[0] for llamada in enviar.call_args_list))
        respuesta = conexion.getresponse()
        status, contenido = respuesta.status, respuesta.read()
        conexion.close()
        return status, json.loads(contenido)

    def assertSinOperacion(self):
        limite = time.monotonic() + 1
        while time.monotonic() < limite:
            with self.servidor.lock:
                operaciones = self.servidor.operaciones_archivo
            if operaciones == 0:
                return
            time.sleep(0.005)
        self.assertEqual(operaciones, 0)

    def test_abrir_devuelve_documento_y_guardar_reutiliza_su_identidad(self):
        status, abierto = self.solicitud("/api/proyecto/abrir")
        self.assertEqual(status, 200)
        self.assertEqual(abierto, {"documento": self.documento, "modelo": self.modelo})
        self.files.open_project.assert_called_once_with()
        payload = {"modelo": self.modelo, "documento_id": abierto["documento"]["id"], "guardar_como": False,
                   "nombre_sugerido": "Pasarela.json"}
        status, guardado = self.solicitud("/api/proyecto/guardar", payload)
        self.assertEqual(status, 200)
        self.assertTrue(guardado["guardado"])
        self.assertEqual(guardado["documento"], self.documento)
        self.files.save_project.assert_called_once_with(payload)
        self.assertSinOperacion()

    def test_cancelar_no_es_guardado_exitoso(self):
        for ruta, funcion, datos in (("/api/proyecto/abrir", self.files.open_project, {}),
                                      ("/api/proyecto/guardar", self.files.save_project, {"modelo": self.modelo})):
            with self.subTest(ruta=ruta):
                funcion.return_value = {"cancelado": True}
                status, resultado = self.solicitud(ruta, datos)
                self.assertEqual(status, 200)
                self.assertEqual(resultado, {"cancelado": True})
                self.assertNotIn("guardado", resultado)
                self.assertSinOperacion()

    def test_sesion_host_origen_y_token_del_anfitrion_no_autorizan_archivos(self):
        self.servidor.host_control = True
        for ruta in ("/api/proyecto/abrir", "/api/proyecto/guardar"):
            for headers in ({"X-Pasarela-Token": "incorrecto"}, {"X-Pasarela-Token": ""},
                            {"X-Pasarela-Token": self.servidor.control_token},
                            {"Host": "otro.example"}, {"Origin": "https://otro.example"}):
                with self.subTest(ruta=ruta, headers=headers):
                    self.assertEqual(self.solicitud(ruta, {"modelo": self.modelo}, headers=headers)[0], 403)
        self.files.open_project.assert_not_called()
        self.files.save_project.assert_not_called()

    def test_payload_json_malformado_y_limites_no_abren_selector(self):
        casos = [({"Content-Type": "text/plain"}, b"{}", 415),
                 ({"Content-Length": str(MAX_BODY + 1)}, b"", 413),
                 ({"Content-Length": "0"}, b"", 413),
                 ({"Content-Length": "incorrecto"}, b"", 400),
                 ({}, b"{", 400), ({}, b"[" * 2000 + b"]" * 2000, 400),
                 ({}, b"\xff", 400), ({}, b"[]", 400)]
        for headers, raw, esperado in casos:
            with self.subTest(headers=headers, raw=raw[:20]):
                self.assertEqual(self.solicitud("/api/proyecto/guardar", headers=headers, raw=raw)[0], esperado)
                self.assertSinOperacion()
        self.files.open_project.assert_not_called()
        self.files.save_project.assert_not_called()

    def test_rutas_y_tipos_no_admitidos_no_llegan_al_almacen(self):
        for datos in ({"ruta": "C:/Proyectos/otro.json"}, {"documento_id": "otro"}):
            self.assertEqual(self.solicitud("/api/proyecto/abrir", datos)[0], 400)
        casos = [{"modelo": self.modelo, "ruta": "C:/Proyectos/otro.json"},
                 {"modelo": self.modelo, "path": "../otro.json"},
                 {}, {"modelo": []}, {"modelo": self.modelo, "documento_id": {}},
                 {"modelo": self.modelo, "guardar_como": "false"},
                 {"modelo": self.modelo, "nombre_sugerido": []}]
        for datos in casos:
            with self.subTest(datos=datos):
                self.assertEqual(self.solicitud("/api/proyecto/guardar", datos)[0], 400)
        self.files.open_project.assert_not_called()
        self.files.save_project.assert_not_called()
        self.assertSinOperacion()

    def test_errores_de_almacen_liberan_la_operacion_y_no_declaran_guardado(self):
        for error, esperado in ((FileConflict("Archivo modificado fuera del editor."), 409),
                                (FileBusy("Hay un selector abierto."), 409),
                                (ValueError("Documento desconocido."), 400),
                                (OSError("No se puede escribir el archivo."), 500)):
            with self.subTest(error=type(error).__name__):
                self.files.save_project.side_effect = error
                status, resultado = self.solicitud("/api/proyecto/guardar", {"modelo": self.modelo})
                self.assertEqual(status, esperado)
                self.assertIn(str(error), resultado["mensaje"])
                self.assertNotIn("guardado", resultado)
                self.assertSinOperacion()
        self.files.save_project.side_effect = None
        self.assertEqual(self.solicitud("/api/proyecto/guardar", {"modelo": self.modelo})[0], 200)

    def test_operacion_activa_bloquea_cierre_cambio_de_host_y_otro_selector(self):
        entrada = threading.Event()
        terminar = threading.Event()

        def abrir():
            entrada.set()
            if not terminar.wait(4):
                raise OSError("La prueba no liberó el selector.")
            return {"cancelado": True}

        self.files.open_project.side_effect = abrir
        self.servidor.host_control = True
        self.servidor.parent_origin = "http://127.0.0.1:8000"
        host_headers = {"X-Pasarela-Token": self.servidor.control_token}
        with ThreadPoolExecutor(max_workers=1) as executor:
            futuro = executor.submit(self.solicitud, "/api/proyecto/abrir")
            try:
                self.assertTrue(entrada.wait(2))
                self.assertEqual(self.solicitud("/api/cerrar", headers=host_headers)[0], 409)
                self.assertFalse(self.servidor.cerrando)
                self.assertEqual(self.solicitud("/api/host/embed", {"parent_origin": "http://127.0.0.1:9000"},
                                               headers=host_headers)[0], 409)
                self.assertEqual(self.servidor.parent_origin, "http://127.0.0.1:8000")
                self.assertEqual(self.solicitud("/api/proyecto/guardar", {"modelo": self.modelo})[0], 409)
                self.files.save_project.assert_not_called()
            finally:
                terminar.set()
            self.assertEqual(futuro.result(timeout=3), (200, {"cancelado": True}))
        self.assertSinOperacion()
        self.assertEqual(self.solicitud("/api/host/embed", {"parent_origin": "http://127.0.0.1:9000"},
                                       headers=host_headers)[0], 200)

    def test_no_se_inicia_selector_durante_cierre_o_sin_capacidad_nativa(self):
        self.servidor.cerrando = True
        self.assertEqual(self.solicitud("/api/proyecto/abrir")[0], 409)
        self.servidor.cerrando = False
        self.files.available = False
        status, estado = self.solicitud("/api/estado", metodo="GET")
        self.assertEqual(status, 200)
        self.assertIs(estado["guardado_local"], False)
        self.assertEqual(self.solicitud("/api/proyecto/abrir")[0], 503)
        self.files.open_project.assert_not_called()
        self.files.available = True
        self.assertIs(self.solicitud("/api/estado", metodo="GET")[1]["guardado_local"], True)


if __name__ == "__main__":
    unittest.main()
