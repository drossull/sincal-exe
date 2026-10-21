"""Módulo instalable: recursos de lectura, datos escribibles y lifecycle local."""

from contextlib import nullcontext
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from pasarela_bim import runtime
from pasarela_bim.ejecucion import generar_aislado,nueva_salida
from pasarela_bim.servidor import _publicar_inicio,_retirar_inicio


class TestRuntime(unittest.TestCase):
    def test_raices_frozen_separan_recursos_motor_y_datos_sin_escribir_instalacion(self):
        with tempfile.TemporaryDirectory() as temporal:
            base = Path(temporal)
            bundle = base/"Program Files"/"SINCAL-Pasarela"/"_internal"
            paquete = bundle/"runtime"/"pasarela_bim"
            paquete.mkdir(parents=True)
            for nombre in ("__init__.py","worker.py","freecad_backend.py","topologia.py","proyecto.py","ejes.py"):
                (paquete/nombre).write_text("",encoding="utf-8")
            local = base/"usuario"/"local"
            with patch.object(sys,"frozen",True,create=True),patch.object(sys,"_MEIPASS",str(bundle),create=True), \
                 patch.dict(os.environ,{"LOCALAPPDATA":str(local),"XDG_DATA_HOME":str(local),"PASARELA_DATA_DIR":""}):
                self.assertEqual(runtime.raiz_recursos(),bundle/"pasarela_bim")
                self.assertEqual(runtime.raiz_codigo_motor(),bundle/"runtime")
                self.assertEqual(nueva_salida().parent,local/"SINCAL"/"pasarela-bim"/"generados")
                self.assertFalse(local.exists())
                (paquete/"worker.py").unlink()
                with self.assertRaisesRegex(RuntimeError,"fuentes del motor"):
                    runtime.raiz_codigo_motor()

    def test_override_de_datos_no_modifica_raiz_de_recursos(self):
        with tempfile.TemporaryDirectory() as temporal,patch.dict(os.environ,{"PASARELA_DATA_DIR":temporal}):
            self.assertEqual(nueva_salida().parent,Path(temporal)/"generados")
            self.assertNotEqual(runtime.raiz_recursos(),Path(temporal))

    def test_entorno_externo_restablece_bibliotecas_sin_mutar_padre(self):
        with tempfile.TemporaryDirectory() as temporal:
            bundle = Path(temporal)/"bundle"
            original = {"PATH":os.pathsep.join([str(bundle),str(bundle/"Qt"),str(bundle)+"-vecino",str(Path(temporal)/"sistema")]),
                        "PYTHONHOME":"bundle","PYTHONPATH":"bundle","QT_PLUGIN_PATH":"bundle",
                        "LD_LIBRARY_PATH":"bundle","LD_LIBRARY_PATH_ORIG":"sistema","LIBPATH":"bundle"}
            with patch.dict(os.environ,original,clear=True),patch.object(sys,"frozen",True,create=True), \
                 patch.object(sys,"_MEIPASS",str(bundle),create=True):
                entorno = runtime.entorno_externo()
                self.assertEqual(entorno["PATH"],os.pathsep.join([str(bundle)+"-vecino",str(Path(temporal)/"sistema")]))
                self.assertEqual(entorno["LD_LIBRARY_PATH"],"sistema")
                for clave in ("PYTHONHOME","PYTHONPATH","QT_PLUGIN_PATH","LIBPATH"):
                    self.assertNotIn(clave,entorno)
                self.assertEqual(dict(os.environ),original)

    def test_macro_frozen_importa_fuentes_externas_y_no_usa_exe_como_python(self):
        modelo = {"version":1,"proyecto":{"id":"p","nombre":"Prueba","estado":"conceptual","unidades":"mm"},
                  "nodos":[{"id":"A","tipo":"encuentro","x":0,"y":0,"z":0},
                           {"id":"B","tipo":"encuentro","x":6000,"y":0,"z":480}],
                  "tramos":[{"id":"T","tipo":"viga","funcion":"rampa","desde":"A","hasta":"B","familia":"losa","ancho_mm":2000}],
                  "familias":{"losa":{"tipo":"maciza","canto_mm":200}},"fundaciones":[],"soportes":[]}
        with tempfile.TemporaryDirectory() as temporal:
            base = Path(temporal);fuentes = base/"bundle"/"runtime";destino = base/"datos"/"generados"/"ensayo"
            def terminar(**kwargs):
                (destino/"m.FCStd").write_bytes(b"simulado")
                (destino/"resultado_proceso.json").write_text(json.dumps({"estado":"completado","resultado":{"valido":True}}),encoding="utf-8")
                return 0
            with patch("pasarela_bim.ejecucion.localizar_freecad",return_value=base/"FreeCAD.exe"), \
                 patch("pasarela_bim.ejecucion.raiz_codigo_motor",return_value=fuentes), \
                 patch("pasarela_bim.ejecucion.bibliotecas_sistema",return_value=nullcontext()) as dll, \
                 patch("pasarela_bim.ejecucion.subprocess.Popen") as proceso:
                proceso.return_value.wait.side_effect = terminar
                generar_aislado(modelo,destino)
            macro = (destino/"generar.FCMacro").read_text(encoding="utf-8")
            self.assertIn(f"sys.path.insert(0, {str(fuentes)!r})",macro)
            self.assertEqual(proceso.call_args.args[0][0],str(base/"FreeCAD.exe"))
            self.assertEqual(proceso.call_args.kwargs["env"]["PYTHONDONTWRITEBYTECODE"],"1")
            dll.assert_called_once()

    def test_anuncio_atomico_y_retiro_solo_de_instancia_propia(self):
        with tempfile.TemporaryDirectory() as temporal:
            path = Path(temporal)/"inicio.json"
            _publicar_inicio(path,"http://127.0.0.1:1234","secreto")
            self.assertEqual(json.loads(path.read_text()),{"url":"http://127.0.0.1:1234","pid":os.getpid(),"control_token":"secreto"})
            self.assertEqual(list(Path(temporal).glob("*.tmp")),[])
            path.write_text(json.dumps({"pid":os.getpid()+1}),encoding="utf-8")
            _retirar_inicio(path)
            self.assertTrue(path.exists())
            _publicar_inicio(path,"http://127.0.0.1:1234","otro")
            _retirar_inicio(path)
            self.assertFalse(path.exists())

    def test_proceso_real_puerto_efimero_recursos_control_y_cierre(self):
        raiz = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporal:
            base = Path(temporal);inicio = base/"sesion"/"ready.json"
            opciones = {"creationflags":getattr(subprocess,"CREATE_NO_WINDOW",0)}
            with (base/"servidor.log").open("wb") as log:
                proceso = subprocess.Popen([sys.executable,"-m","pasarela_bim","--port","0","--sin-navegador",
                                            "--launch-info",str(inicio),"--data-dir",str(base/"datos")],
                                           cwd=raiz,stdout=log,stderr=log,**opciones)
                try:
                    limite = time.monotonic()+10
                    while not inicio.is_file() and proceso.poll() is None and time.monotonic()<limite:
                        time.sleep(.03)
                    self.assertTrue(inicio.is_file(),(base/"servidor.log").read_text(errors="replace"))
                    ready = json.loads(inicio.read_text(encoding="utf-8"));url = urlsplit(ready["url"])
                    self.assertEqual(url.hostname,"127.0.0.1");self.assertGreater(url.port,0)
                    self.assertEqual(ready["pid"],proceso.pid)
                    def solicitar(metodo,ruta,token=None):
                        conn = http.client.HTTPConnection(url.hostname,url.port,timeout=3)
                        conn.request(metodo,ruta,headers={"X-Pasarela-Token":token} if token else {})
                        respuesta = conn.getresponse();valor = respuesta.read();conn.close()
                        return respuesta.status,valor
                    status,html = solicitar("GET","/");self.assertEqual(status,200)
                    self.assertNotIn(ready["control_token"].encode(),html)
                    self.assertIn(b'name="pasarela-token"',html)
                    self.assertEqual(solicitar("GET","/api/host-status")[0],403)
                    status,estado = solicitar("GET","/api/host-status",ready["control_token"])
                    self.assertEqual(status,200);self.assertEqual(json.loads(estado)["pid"],proceso.pid)
                    self.assertEqual(json.loads(estado)["embedding"],1)
                    estado = json.loads(solicitar("GET","/api/estado")[1])
                    self.assertNotIn("control_token",estado)
                    self.assertEqual(solicitar("GET","/api/ejemplo")[0],200)
                    self.assertEqual(solicitar("POST","/api/cerrar","incorrecto")[0],403)
                    status,cierre = solicitar("POST","/api/cerrar",ready["control_token"])
                    self.assertEqual(status,200);self.assertEqual(json.loads(cierre),{"ok":True})
                    self.assertEqual(proceso.wait(timeout=8),0)
                    self.assertFalse(inicio.exists())
                finally:
                    if proceso.poll() is None:
                        proceso.kill();proceso.wait(timeout=8)


if __name__ == "__main__":
    unittest.main()
