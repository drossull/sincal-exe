"""Authenticated loopback service for the embedded desktop interface."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from urllib.parse import urlsplit
import uuid
import webbrowser

from sincal.project import ProjectContext, project_sections, project_text, validate_project_data
from .rebar import defaults as rebar_defaults, preview as rebar_preview
from .cad_connection import connection_status
from .services import Services, COMMANDS
from .rebar import from_project

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).with_name("static")
MAX_BODY = 64 * 1024 * 1024  # Session OCR evidence; project file UI stays limited to 4 MB.


def project_result(payload):
    data = payload.get("data")
    identity = payload.get("identification", {})
    if not isinstance(data, dict) or not isinstance(identity, dict):
        raise ValueError("El proyecto debe ser un objeto JSON con identificación válida.")
    for key in ("parametros_generales", "elementos_comunes", "cepas", "estribos", "materiales", "planos", "meta"):
        if key in data and not isinstance(data[key], dict):
            raise ValueError(f"El bloque {key} debe ser un objeto.")
    if "tableros" in data and not isinstance(data["tableros"], list):
        raise ValueError("Tableros debe ser una lista.")
    if "lista" in data.get("cepas", {}) and not isinstance(data["cepas"]["lista"], list):
        raise ValueError("La lista de cepas no es válida.")
    if any(not isinstance(value, str) or len(value) > 300 for value in identity.values()):
        raise ValueError("Los campos de identificación deben ser textos de hasta 300 caracteres.")
    context = ProjectContext(data=data, identification=identity, warnings=validate_project_data(data))
    return {"sections": project_sections(data), "warnings": context.warnings, "text": project_text(context)}


class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, updated TEXT, payload TEXT)")
            db.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS recovery (id TEXT PRIMARY KEY, updated TEXT, payload TEXT)')

    def recover(self, key=None, payload=None):
        with self.connect() as db:
            if key is not None:
                if payload is None:
                    db.execute('DELETE FROM recovery WHERE id = ?', (key,))
                else:
                    project_result(payload)
                    db.execute('INSERT OR REPLACE INTO recovery VALUES (?, ?, ?)',
                               (key, datetime.now(timezone.utc).isoformat(), json.dumps(payload, allow_nan=False)))
                return {'ok': True}
            row = db.execute('SELECT id, updated, payload FROM recovery ORDER BY updated DESC LIMIT 1').fetchone()
            return {'id': row[0], 'updated': row[1], 'payload': json.loads(row[2])} if row else None

    def preferences(self, values=None):
        from sincal.ui.cadence_palettes import FAMILIES
        allowed = {'theme': ('system', 'dark', 'light'), 'palette': ('sincal', *FAMILIES),
                   'zoom': ('90', '100', '115'), 'sidebar': (True, False), 'outline': (True, False)}
        if values is not None:
            for key, value in values.items():
                if key == 'last_session':
                    if value is not None and not self.get(value):
                        raise ValueError('Sesión desconocida.')
                elif key not in allowed or value not in allowed[key]:
                    raise ValueError('Preferencia no válida.')
            with self.connect() as db:
                for key, value in values.items():
                    db.execute('INSERT OR REPLACE INTO preferences VALUES (?, ?)', (key, json.dumps(value)))
        with self.connect() as db:
            return {key: json.loads(value) for key, value in db.execute('SELECT key, value FROM preferences')}

    def connect(self):
        return sqlite3.connect(self.path)

    def save(self, payload):
        project_result(payload)
        if isinstance(payload.get('prospecciones'), dict) and payload['prospecciones'].get('report'):
            from sincal.prospecciones import VsReport
            VsReport.from_dict(payload['prospecciones']['report'])
        if "rebar" in payload:
            if not isinstance(payload["rebar"], dict) or set(payload["rebar"]) - {"entrada", "salida"}:
                raise ValueError("Estado de estribos no válido.")
            from .rebar import validate_draft
            for state in payload["rebar"].values():
                validate_draft(state)
        identity = payload.get("identification", {})
        if any(not identity.get(key, "").strip() for key in ("ot", "revision", "structure_name")):
            raise ValueError("Completa OT, revisión y nombre de estructura antes de guardar.")
        # Immutable snapshots avoid silently overwriting another browser tab.
        session_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (
                session_id, identity["structure_name"], datetime.now(timezone.utc).isoformat(),
                json.dumps(payload, ensure_ascii=False, allow_nan=False)))
        self.preferences({'last_session': session_id})
        return {"id": session_id}

    def list(self):
        with self.connect() as db:
            return [dict(zip(("id", "title", "updated", "ot", "revision"), row)) for row in
                    db.execute("SELECT id, title, updated, json_extract(payload, '$.identification.ot'), "
                               "json_extract(payload, '$.identification.revision') FROM sessions ORDER BY updated DESC")]

    def get(self, session_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return json.loads(row[0]) if row else None


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, data_dir):
        super().__init__(("127.0.0.1", port), Handler)
        self.token = secrets.token_urlsafe(32)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.store = Store(data_dir / "sessions.sqlite3")
        self.services = Services(data_dir)
        self.recovery_id = uuid.uuid4().hex

    def server_close(self):
        self.services.jobs.close()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Do not write URLs, tokens or project contents to console.

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def send(self, status, content, mime="application/json; charset=utf-8"):
        body = json.dumps(content, ensure_ascii=False).encode() if not isinstance(content, bytes) else content
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, api=False):
        if self.headers.get("Host") != urlsplit(self.server.origin).netloc:
            self.send(403, {"error": "Host no autorizado"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin != self.server.origin:
            self.send(403, {"error": "Origen no autorizado"})
            return False
        if api and not secrets.compare_digest(self.headers.get("X-Sincal-Token", ""), self.server.token):
            self.send(401, {"error": "Abre la dirección generada por el lanzador local."})
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.authorized(path.startswith("/api/")):
            return
        if path == "/api/rebar/defaults":
            return self.send(200, rebar_defaults())
        if path == "/api/cad/status":
            return self.send(200, connection_status())
        if path == '/api/dwgprops/engines':
            from sincal.cad.dwgprops import autocad_engines
            return self.send(200, autocad_engines())
        if path == '/api/commands':
            from sincal.runtime import ruta_recurso
            document = json.loads(Path(ruta_recurso('tutoriales.json')).read_text(encoding='utf-8'))
            commands = document.get('comandos_lisp', {})
            return self.send(200, {key: commands.get('ST0' if key == 'STO' else key, {}).get('descripcion', description)
                                   for key, description in COMMANDS.items()})
        if path == '/api/preferences':
            return self.send(200, self.server.store.preferences())
        if path == '/api/shell-selection':
            from sincal.cad.engine import load_engine_state
            engine = load_engine_state()
            return self.send(200, {'selection': self.server.services.shell_selection,
                                   'engine': engine.label if engine else 'No seleccionado; usa Diagnóstico.'})
        if path == '/api/palettes':
            from sincal.ui.cadence_palettes import FAMILIES
            return self.send(200, list(FAMILIES))
        if path == '/palettes.css':
            from .palettes import stylesheet
            return self.send(200, stylesheet(), 'text/css; charset=utf-8')
        if path == '/api/documentation':
            from .documentation import documentation
            return self.send(200, documentation())
        if path == '/api/maps':
            try:
                return self.send(200, list(self.server.services.maps()))
            except Exception:
                return self.send(200, [])
        if path == '/api/jobs':
            return self.send(200, self.server.services.jobs.history())
        if path.startswith('/api/jobs/'):
            try:
                key = path.split('/')[3]
                if path.endswith('/log'):
                    return self.send(200, self.server.services.jobs.logfile(key).read_bytes(), 'text/plain; charset=utf-8')
                job = self.server.services.jobs.get(key)
                return self.send(200, job.snapshot())
            except ValueError as error:
                return self.send(404, {'error': str(error)})
        if path.startswith('/api/artifacts/'):
            artifact = self.server.services.artifacts.get(path.rsplit('/', 1)[1])
            if not artifact:
                return self.send(404, {'error': 'Resultado no encontrado.'})
            return self.send(200, artifact[0].read_bytes(), artifact[1])
        assets = {"/": (STATIC / "index.html", "text/html; charset=utf-8"),
                  "/app.js": (STATIC / "app.js", "text/javascript; charset=utf-8"),
                  "/rebar.js": (STATIC / "rebar.js", "text/javascript; charset=utf-8"),
                  "/tools.js": (STATIC / "tools.js", "text/javascript; charset=utf-8"),
                  "/dwgprops.js": (STATIC / "dwgprops.js", "text/javascript; charset=utf-8"),
                  "/revisions.js": (STATIC / "revisions.js", "text/javascript; charset=utf-8"),
                  "/app.css": (STATIC / "app.css", "text/css; charset=utf-8"),
                  "/logo.ico": (ROOT / "assets/icons/logo.ico", "image/x-icon")}
        for font in ("roboto-400.ttf", "roboto-700.ttf", "roboto-condensed-700.ttf", "roboto-flex-400.ttf", "roboto-mono-400.ttf"):
            assets["/" + font] = (ROOT / "assets/fonts" / font, "font/ttf")
        asset = assets.get(path)
        if asset:
            return self.send(200, asset[0].read_bytes(), asset[1])
        self.send(404, {"error": "Ruta no encontrada"})

    def do_POST(self):
        if not self.authorized(True):
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                return self.send(413, {"error": "El límite de la solicitud es 64 MB."})
            if self.headers.get_content_type() != "application/json":
                return self.send(415, {"error": "Se requiere JSON."})
            payload = json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Número no finito")))
            if not isinstance(payload, dict):
                raise ValueError("Se requiere un objeto JSON.")
            if self.path == "/api/project/preview":
                return self.send(200, project_result(payload))
            if self.path == "/api/rebar/preview":
                return self.send(200, rebar_preview(payload))
            if self.path == '/api/rebar/from-project':
                return self.send(200, from_project(payload))
            if self.path == '/api/prospect/preview':
                from sincal.prospecciones import VsReport
                return self.send(200, self.server.services.describe_report(VsReport.from_dict(payload)))
            if self.path == '/api/preferences':
                return self.send(200, self.server.store.preferences(payload))
            if self.path == '/api/files/choose':
                return self.send(200, self.server.services.files.choose(payload.get('kind')))
            if self.path == '/api/files/list':
                return self.send(200, self.server.services.files.list_folder(payload.get('folder')))
            if self.path == '/api/rename/plan':
                return self.send(200, self.server.services.plan_rename(payload))
            if self.path == '/api/jobs':
                return self.send(202, self.server.services.operation(payload.get('operation'), payload.get('payload', {})))
            if self.path == '/api/jobs/cancel':
                self.server.services.jobs.get(payload.get('id')).cancelled.set()
                return self.send(200, {'message': 'Cancelación solicitada; no se deshacen acciones ya terminadas.'})
            self.send(404, {"error": "Ruta no encontrada"})
        except (ValueError, TypeError, RecursionError, AttributeError) as error:
            self.send(400, {"error": f"Proyecto no válido: {error}"})
        except Exception:
            self.send(500, {"error": "No se pudo completar la operación local. Revisa el registro de diagnóstico."})


def main():
    parser = argparse.ArgumentParser(description="Piloto web local de SINCAL Suite")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    directory = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SINCAL/web-pilot"
    with Server(args.port, directory) as server:
        url = f"{server.origin}/#token={server.token}"
        print("SINCAL Suite · interfaz local de escritorio. Ctrl+C para salir.", flush=True)
        print(url, flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
