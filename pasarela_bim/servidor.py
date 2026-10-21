"""Interfaz local de edición y generación, limitada a loopback."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
import json
import mimetypes
import os
from pathlib import Path
import secrets
import re
import sys
import tempfile
import threading
from urllib.parse import unquote, urlsplit
import uuid
import webbrowser

from . import __version__
from .ejecucion import generar_aislado, localizar_freecad, nueva_salida
from .topologia import validar
from .planta import importar_planta, localizar_conversor, MAX_UPLOAD
from .runtime import raiz_recursos, carpeta_generados

MAX_BODY = 20 * 1024 * 1024


def _origen_padre(valor):
    """Un origen loopback exacto; nunca una URL con ruta o credenciales."""
    if not isinstance(valor, str):
        raise ValueError("El origen de SINCAL debe ser http://127.0.0.1:puerto.")
    match = re.fullmatch(r"http://127\.0\.0\.1:([1-9][0-9]{0,4})", valor)
    if not match or not 1 <= int(match.group(1)) <= 65535:
        raise ValueError("El origen de SINCAL debe ser http://127.0.0.1:puerto, sin ruta ni otros datos.")
    return valor


class Aplicacion(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, direccion):
        super().__init__(direccion, Manejador)
        self.token = secrets.token_urlsafe(32)
        self.control_token = secrets.token_urlsafe(32)
        self.parent_origin = None
        self.trabajos = {}
        self.lock = threading.Lock()
        self.cerrando = False
        self.importaciones = 0
        self.host_control = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pasarela-freecad")

    @property
    def origen(self):
        return f"http://127.0.0.1:{self.server_port}"

    def ejecutar(self, id_trabajo, modelo, salida):
        try:
            resultado = generar_aislado(modelo, salida)
            archivos = [{"nombre": nombre, "url": f"/api/archivos/{id_trabajo}/{nombre}"}
                        for nombre in resultado["archivos"]]
            final = {"estado": "completado", "mensaje": "Modelo guardado y comprobado en FreeCAD.",
                     "archivos": archivos, "resultado": resultado.get("resultado", {})}
        except Exception as exc:
            final = {"estado": "error", "mensaje": str(exc), "archivos": []}
        with self.lock:
            self.trabajos[id_trabajo].update(final)

    def server_close(self):
        super().server_close()
        self.executor.shutdown(wait=False, cancel_futures=True)


class Manejador(BaseHTTPRequestHandler):
    server: Aplicacion

    def log_message(self, format, *args):
        pass

    def enviar(self, datos, status=200, tipo="application/json; charset=utf-8", parent_origin=None):
        contenido = json.dumps(datos, ensure_ascii=True).encode("ascii") if not isinstance(datos, bytes) else datos
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(contenido)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        ancestor = (self.server.parent_origin if parent_origin is None else parent_origin) or "'none'"
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors " + ancestor)
        self.end_headers()
        self.wfile.write(contenido)

    def permitido(self):
        esperado = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != esperado:
            self.enviar({"mensaje": "Host no permitido"}, 403)
            return False
        if self.headers.get("Origin") not in (None, self.server.origen):
            self.enviar({"mensaje": "Origen no permitido"}, 403)
            return False
        return True

    def do_GET(self):
        if not self.permitido():
            return
        ruta = unquote(urlsplit(self.path).path)
        if ruta == "/api/ejemplo":
            return self.enviar(json.loads((raiz_recursos() / "ejemplos" / "los_batros.json").read_text(encoding="utf-8")))
        if ruta == "/api/estado":
            return self.enviar({"freecad_disponible": localizar_freecad() is not None, "dwg_disponible": localizar_conversor() is not None, "version": __version__})
        if ruta == "/api/host-status":
            if not self.server.host_control:
                return self.enviar({"mensaje":"No encontrado"},404)
            if not secrets.compare_digest(self.headers.get("X-Pasarela-Token", "").encode("utf-8"),self.server.control_token.encode("ascii")):
                return self.enviar({"mensaje":"Control del anfitrión no autorizado"},403)
            return self.enviar({"version":__version__,"pid":os.getpid(),"embedding":1})
        if ruta.startswith("/api/trabajos/"):
            id_trabajo = ruta.split("/")[-1]
            with self.server.lock:
                trabajo = self.server.trabajos.get(id_trabajo)
                respuesta = {k: v for k, v in trabajo.items() if k != "carpeta"} if trabajo else None
            return self.enviar(respuesta or {"mensaje": "Trabajo no encontrado"}, 200 if respuesta else 404)
        if ruta.startswith("/api/archivos/"):
            piezas = ruta.split("/")
            if len(piezas) != 5:
                return self.enviar({"mensaje": "Archivo no encontrado"}, 404)
            id_trabajo, nombre = piezas[3:]
            with self.server.lock:
                trabajo = self.server.trabajos.get(id_trabajo, {})
                permitidos = {a["nombre"] for a in trabajo.get("archivos", [])}
                carpeta = trabajo.get("carpeta")
            if nombre not in permitidos or Path(nombre).name != nombre:
                return self.enviar({"mensaje": "Archivo no encontrado"}, 404)
            archivo = Path(carpeta) / nombre
            try:
                contenido = archivo.read_bytes()
            except OSError:
                return self.enviar({"mensaje": "El archivo ya no está disponible."}, 404)
            return self.enviar(contenido, tipo=mimetypes.guess_type(nombre)[0] or "application/octet-stream")
        recursos = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/style.css": "style.css",
                    "/proyecto.js": "proyecto.js", "/emplazamiento.js": "emplazamiento.js", "/secciones.js": "secciones.js",
                    "/volumen.js": "volumen.js", "/ejes.js": "ejes.js", "/integracion.js": "integracion.js"}
        if ruta not in recursos:
            return self.enviar({"mensaje": "No encontrado"}, 404)
        archivo = raiz_recursos() / "web" / recursos[ruta]
        datos = archivo.read_bytes()
        parent_origin = self.server.parent_origin or ""
        if archivo.suffix == ".html":
            datos = datos.replace(b"__PASARELA_TOKEN__", self.server.token.encode("ascii"))
            datos = datos.replace(b"__PASARELA_PARENT_ORIGIN__", escape(parent_origin, quote=True).encode("ascii"))
        self.enviar(datos, tipo={".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                                ".css": "text/css; charset=utf-8"}[archivo.suffix], parent_origin=parent_origin)

    def do_POST(self):
        if not self.permitido():
            return
        ruta = urlsplit(self.path).path
        if ruta == "/api/host/embed" and not self.server.host_control:
            return self.enviar({"mensaje":"No encontrado"},404)
        host_action = self.server.host_control and ruta in ("/api/host/embed", "/api/cerrar")
        token = self.server.control_token if host_action else self.server.token
        if not secrets.compare_digest(self.headers.get("X-Pasarela-Token", "").encode("utf-8"), token.encode("ascii")):
            return self.enviar({"mensaje": "Sesión no válida; recarga la aplicación."}, 403)
        if ruta == "/api/host/embed":
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.enviar({"mensaje":"Se requiere JSON"},415)
            try:
                longitud = int(self.headers.get("Content-Length", "0"))
                if not 0 < longitud <= 4096:
                    return self.enviar({"mensaje":"Configuración de integración demasiado grande o vacía"},400)
                datos = json.loads(self.rfile.read(longitud))
                if not isinstance(datos,dict) or set(datos) != {"parent_origin"}:
                    raise ValueError("Se requiere únicamente parent_origin.")
                origen = _origen_padre(datos["parent_origin"])
            except (ValueError,TypeError,RecursionError) as exc:
                return self.enviar({"mensaje":str(exc)},400)
            with self.server.lock:
                if self.server.cerrando:
                    return self.enviar({"mensaje":"El módulo se está cerrando."},409)
                self.server.parent_origin = origen
            return self.enviar({"embedding":1,"parent_origin":origen})
        if ruta == "/api/cerrar":
            with self.server.lock:
                if self.server.importaciones or any(t["estado"] == "ejecutando" for t in self.server.trabajos.values()):
                    return self.enviar({"mensaje":"Espera a que termine el trabajo en curso antes de cerrar el módulo."},409)
                self.server.cerrando = True
            self.enviar({"ok":True})
            threading.Thread(target=self.server.shutdown,name="pasarela-cerrar",daemon=True).start()
            return
        with self.server.lock:
            if self.server.cerrando:
                return self.enviar({"mensaje":"El módulo se está cerrando."},409)
        if ruta == "/api/planta":
            with self.server.lock:
                if self.server.cerrando:
                    return self.enviar({"mensaje":"El módulo se está cerrando."},409)
                self.server.importaciones += 1
            try:
                longitud = int(self.headers.get("Content-Length", "0"))
                if not 0 < longitud <= MAX_UPLOAD:
                    return self.enviar({"mensaje": "Carga un DWG o DXF de hasta 20 MB."}, 413)
                nombre = unquote(self.headers.get("X-File-Name", "planta.dxf"))
                planta = importar_planta(self.rfile.read(longitud), nombre, carpeta_generados() / "plantas")
                return self.enviar(planta)
            except (ValueError, TypeError, OSError, OverflowError) as exc:
                return self.enviar({"mensaje": str(exc)}, 400)
            finally:
                with self.server.lock:
                    self.server.importaciones -= 1
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.enviar({"mensaje": "Se requiere JSON"}, 415)
        try:
            longitud = int(self.headers.get("Content-Length", "0"))
            if not 0 < longitud <= MAX_BODY:
                return self.enviar({"mensaje": "Archivo vacío o demasiado grande (máximo 20 MB)."}, 413)
            modelo = json.loads(self.rfile.read(longitud))
            validacion = validar(modelo, borrador=ruta == "/api/validar")
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            return self.enviar({"mensaje": f"Entrada no válida: {exc}"}, 400)
        ruta = urlsplit(self.path).path
        if ruta == "/api/validar":
            return self.enviar(validacion)
        if ruta != "/api/generar":
            return self.enviar({"mensaje": "No encontrado"}, 404)
        if not validacion["valido"]:
            return self.enviar({"mensaje": "Resuelve los errores de la topología antes de generar.", **validacion}, 422)
        if not localizar_freecad():
            return self.enviar({"mensaje": "FreeCAD no está disponible en este equipo."}, 503)
        with self.server.lock:
            if self.server.cerrando:
                return self.enviar({"mensaje":"El módulo se está cerrando."},409)
            if any(t["estado"] == "ejecutando" for t in self.server.trabajos.values()):
                return self.enviar({"mensaje": "Ya hay una generación en curso."}, 409)
            id_trabajo = uuid.uuid4().hex
            salida = nueva_salida()
            self.server.trabajos[id_trabajo] = {"estado": "ejecutando", "mensaje": "Construyendo sólidos y vistas en FreeCAD…",
                                               "archivos": [], "carpeta": str(salida)}
        self.server.executor.submit(self.server.ejecutar, id_trabajo, modelo, salida)
        self.enviar({"trabajo_id": id_trabajo}, 202)


def _publicar_inicio(archivo, url, control_token):
    """Reemplazo atómico: el anfitrión nunca lee un JSON parcialmente escrito."""
    archivo = Path(archivo).expanduser().resolve()
    archivo.parent.mkdir(parents=True,exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=archivo.parent,
                                         prefix=archivo.name+".",suffix=".tmp",delete=False) as salida:
            temporal = Path(salida.name)
            json.dump({"url":url,"pid":os.getpid(),"control_token":control_token},salida,ensure_ascii=True)
        os.replace(temporal,archivo)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
    return archivo


def _retirar_inicio(archivo):
    """No retira el anuncio si ya pertenece a otra instancia del módulo."""
    try:
        if json.loads(archivo.read_text(encoding="utf-8")).get("pid") == os.getpid():
            archivo.unlink(missing_ok=True)
    except (OSError,ValueError,AttributeError):
        pass


def servir(port=8766, abrir_navegador=True, launch_info=None):
    recursos = raiz_recursos()
    if not (recursos/"web"/"index.html").is_file() or not (recursos/"ejemplos"/"los_batros.json").is_file():
        raise RuntimeError("Faltan recursos del editor; reinstala el módulo Pasarela BIM.")
    with Aplicacion(("127.0.0.1", port)) as servidor:
        servidor.host_control = launch_info is not None
        anuncio = None
        try:
            if launch_info:
                anuncio = _publicar_inicio(launch_info,servidor.origen,servidor.control_token)
            if sys.stdout is not None:
                print(f"Pasarela BIM disponible en {servidor.origen}", flush=True)
            if abrir_navegador:
                webbrowser.open(servidor.origen)
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if anuncio:
                _retirar_inicio(anuncio)
