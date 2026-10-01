"""Desktop operations exposed as a finite, token-protected API, not a shell."""
from dataclasses import asdict
import json
import hashlib
import math
import os
from pathlib import Path
import subprocess
import shutil
import sys
import threading
import time
import uuid

from .files import Files, rename_plan, apply_rename
from .jobs import Jobs, Cancelled
from .cad_connection import connection_status
from .rebar import domain, defaults, from_project

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = {
    'BV': 'Bloquea los viewports del layout activo.',
    'DL2': 'Elimina las presentaciones Layout2 y A1 si existen.',
    'P0': 'Pega el portapapeles como bloque en 0,0,0.',
    'PURGEALL': 'Limpia elementos y escalas no utilizados. Guarda una copia antes.',
    'SETUP-A1': 'Prepara el formato A1 del dibujo.',
    'STO': 'Establece la altura de los estilos de texto en cero.',
    'W08': 'Aplica Width Factor 0.8 a los estilos de texto.',
    'ZE': 'Zoom a la extensión del dibujo.',
    'PLOTYA': 'Ejecuta el ploteo configurado en el dibujo.',
    'VPTOGGLE': 'Alterna la visualización de la capa Viewport layer.',
    'LAYORIGIN': 'Corrige el origen de presentación con área de ploteo Layout.',
}


class Services:
    def __init__(self, directory):
        self.directory = directory
        self.files = Files()
        self.jobs = Jobs(directory / 'logs')
        self.runtime = directory / 'operations'
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.plans = {}
        self.artifacts = {}
        self.detections = {}
        self.cad_lock = threading.Lock()
        self.lock = threading.RLock()
        self.clean_runtime()

    def clean_runtime(self):
        root = self.runtime.resolve()
        for path in root.iterdir():
            if (path.is_symlink() or len(path.stem) != 32 or any(c not in '0123456789abcdef' for c in path.stem)
                    or time.time() - path.stat().st_mtime < 7 * 86400 or path.resolve().parent != root):
                continue
            if path.is_dir():
                shutil.rmtree(path)
            elif path.suffix in ('.zip', '.png'):
                path.unlink()

    def remember(self, collection, value):
        with self.lock:
            if len(collection) >= 100:
                del collection[next(iter(collection))]
            key = uuid.uuid4().hex
            collection[key] = value
        return key

    def artifact(self, path, mime):
        return {'artifact': self.remember(self.artifacts, (path, mime)), 'name': path.name}

    def run_worker(self, job, request, timeout=195):
        if os.name != 'nt':
            raise ValueError('El proceso CAD requiere Windows.')
        job.check()
        folder = self.runtime / job.id
        folder.mkdir(exist_ok=True)
        request.update(marker=str(folder / 'done.txt'), token=uuid.uuid4().hex)
        (folder / 'result.json').unlink(missing_ok=True)
        (folder / 'progress.json').unlink(missing_ok=True)
        (folder / 'request.json').write_text(json.dumps(request), encoding='utf-8')
        command = [sys.executable, '--sincal-cad-worker'] if getattr(sys, 'frozen', False) else [sys.executable, '-m', 'sincal.web.cad_worker']
        process = subprocess.Popen([*command, str(folder / 'request.json')],
                                   cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
        start = time.monotonic()
        previous_progress = None
        try:
            while process.poll() is None:
                progress_file = folder / 'progress.json'
                if progress_file.exists():
                    try:
                        progress = json.loads(progress_file.read_text(encoding='utf-8'))
                        if progress != previous_progress:
                            job.update(progress['message'], progress['progress'])
                            previous_progress = progress
                    except (OSError, ValueError, KeyError):
                        pass
                if time.monotonic() - start > timeout or job.cancelled.is_set():
                    process.kill()  # Only our isolated worker, NEVER CAD.
                    process.communicate()
                    raise RuntimeError('Se dejó de esperar a CAD. La orden podría continuar; revisa CAD antes de repetir. No se cerró ni se guardó el dibujo.')
                time.sleep(.2)
            stdout, stderr = process.communicate()
            try:
                result_file = folder / 'result.json'
                result = json.loads(result_file.read_text(encoding='utf-8') if result_file.exists() else stdout)
            except ValueError as error:
                raise RuntimeError('El proceso CAD no devolvió un resultado válido. Revisa CAD; no se reenvió la orden.') from error
            if not result.get('ok'):
                raise RuntimeError(result.get('error', 'Error CAD'))
            job.update(result['result']['message'])
            return result['result']
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def cad(self, job, expected, command, metres=False, candidate=None, scope='active'):
        if not isinstance(expected, dict) or expected.get('status') != 'ready' or not expected.get('instance'):
            raise ValueError('Comprueba y confirma el dibujo de destino antes de enviar.')
        if not self.cad_lock.acquire(blocking=False):
            raise ValueError('Hay otra operación CAD en curso.')
        try:
            job.update('Preparando envío a los destinos confirmados. Si pide un punto, selecciónalo en CAD.')
            count = len(expected.get('documents', [])) if scope == 'all' else 1
            return self.run_worker(job, dict(expected=expected, command=command, metres=metres, candidate=candidate, scope=scope),
                                   timeout=min(3600, max(195, count * 195)))
        finally:
            self.cad_lock.release()

    def lisp(self, job, source):
        folder = self.runtime / job.id
        folder.mkdir(exist_ok=True)
        path = folder / 'operation.lsp'
        path.write_text(source, encoding='utf-8')
        return str(path).replace('\\', '/')

    def operation(self, operation, payload):
        handlers = {'sync-check': self.sync_check, 'sync-apply': self.sync_apply,
                    'diagnostics': self.diagnostics, 'rename': self.rename,
                    'convert': self.convert, 'location': self.location,
                    'location-render': self.location_render, 'prospect': self.prospect,
                    'cad-command': self.command, 'cad-detect': self.detect,
                    'cad-rebar': self.rebar, 'cad-profile': self.profile,
                    'cad-prepare': self.prepare, 'cad-crossbeam': self.crossbeam,
                    'engines': self.engines, 'engine-select': self.engine_select}
        if operation not in handlers:
            raise ValueError('Operación no permitida.')
        return self.jobs.submit(operation, lambda job: handlers[operation](job, payload))

    def sync_check(self, job, payload):
        from sincal.resources import check_resource_updates
        job.update('Consultando manifiesto de recursos. Requiere Internet.')
        plan = check_resource_updates()
        return {'plan': self.remember(self.plans, ('sync', plan)), **asdict(plan)}

    def sync_apply(self, job, payload):
        from sincal.resources import apply_resource_updates
        with self.lock:
            item = self.plans.pop(payload.get('plan'), None)
        if not item or item[0] != 'sync':
            raise ValueError('Vuelve a comprobar las actualizaciones.')
        job.check()
        job.update('Descargando y verificando recursos; espera a que termine esta etapa.')
        return asdict(apply_resource_updates(item[1]))

    def prepare(self, job, payload):
        if payload.get('confirm') is not True:
            raise ValueError('Confirma la modificación de rutas CAD de tu usuario.')
        from sincal.resources import materialize_cad_resources
        from sincal.cad.integration import registrar_ruta_cad_usuario, registrar_scripts_en_path
        job.check()
        paths = materialize_cad_resources()
        changes = registrar_ruta_cad_usuario()
        registrar_scripts_en_path()
        return {'resources': list(paths), 'changes': list(changes), 'message': 'Reinicia CAD para cargar la integración.'}

    def diagnostics(self, job, payload):
        from sincal.diagnostics import create_diagnostic_bundle, format_summary
        destination = self.runtime / f'{job.id}.zip'
        job.update('Comprobando entorno y reuniendo diagnóstico redactado.')
        path, report = create_diagnostic_bundle(str(destination), description=str(payload.get('description', ''))[:2000])
        return {'summary': format_summary(report), **self.artifact(Path(path), 'application/zip')}

    def engines(self, job, payload):
        from sincal.cad.engine import discover_cad_engines, load_engine_state
        candidates = discover_cad_engines()
        selected = load_engine_state()
        return {'engines': [dict(id=self.remember(self.plans, ('engine', engine)), **engine.to_dict()) for engine in candidates],
                'selected': selected.to_dict() if selected else None}

    def engine_select(self, job, payload):
        from sincal.cad.engine import save_engine_selection
        item = self.plans.get(payload.get('id'))
        if not item or item[0] != 'engine':
            raise ValueError('Vuelve a detectar los motores instalados.')
        return save_engine_selection(item[1]).to_dict()

    def plan_rename(self, payload):
        folder = self.files.get(payload.get('folder'), 'folder')
        changes = rename_plan(folder, payload.get('search'), payload.get('replacement'))
        return {'plan': self.remember(self.plans, ('rename', folder, changes)), 'changes': changes}

    def rename(self, job, payload):
        with self.lock:
            plan = self.plans.pop(payload.get('plan'), None)
        if not plan or plan[0] != 'rename':
            raise ValueError('Genera una nueva vista previa de renombrado.')
        return apply_rename(plan[1], plan[2], job)

    def convert(self, job, payload):
        status = connection_status()
        if status.get('status') != 'disconnected':
            raise ValueError('Cierra AutoCAD y ZWCAD antes de convertir para garantizar que solo se use una instancia temporal.')
        sources = [self.files.get(key, 'dxf') for key in payload.get('files', [])]
        folder = self.files.get(payload.get('folder'), 'folder')
        engine = payload.get('engine')
        if not sources or len(sources) > 100 or engine not in ('AutoCAD', 'ZWCAD'):
            raise ValueError('Selecciona de 1 a 100 DXF y un motor CAD.')
        destinations = [folder / (source.stem + '.dwg') for source in sources]
        if len({str(p).casefold() for p in destinations}) != len(destinations) or any(p.exists() for p in destinations):
            raise ValueError('Hay destinos repetidos o existentes; elige una carpeta de salida vacía.')
        if not self.cad_lock.acquire(blocking=False):
            raise ValueError('Hay una operación CAD en curso.')
        try:
            done = []
            for index, (source, destination) in enumerate(zip(sources, destinations)):
                job.check()
                job.update(f'Convirtiendo {source.name}', index * 100 / len(sources))
                done.append(self.run_worker(job, dict(operation='convert', engine=engine,
                                                      source=str(source), destination=str(destination)), timeout=180))
            return {'files': done}
        finally:
            self.cad_lock.release()

    def location(self, job, payload):
        from sincal.ui.tabs.ubicacion import _leer_kml_desde_kmz, _parsear_kml_puntos
        path = self.files.get(payload.get('file'), 'location')
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError('El límite del KML/KMZ es 10 MB.')
        raw = _leer_kml_desde_kmz(str(path))[0] if path.suffix.lower() == '.kmz' else path.read_bytes()
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise ValueError('KML con entidades XML no admitidas.')
        points, ignored = _parsear_kml_puntos(raw)
        return {'points': points, 'ignored': ignored}

    @staticmethod
    def maps():
        from sincal.runtime import ruta_recurso
        from sincal.ui.tabs.ubicacion import TabUbicacion
        path = Path(ruta_recurso('mapas', 'mapas_calibrados.json'))
        return {name: config for name, config in json.loads(path.read_text(encoding='utf-8')).items()
                if TabUbicacion.mapa_esta_calibrado(config)}

    def location_render(self, job, payload):
        from PIL import Image, ImageDraw
        from sincal.resources import ensure_resource_available
        config = self.maps().get(payload.get('map'))
        if not config:
            raise ValueError('Mapa desconocido.')
        lat, lon = map(float, payload['point'])
        dx, dy = float(payload.get('dx', 0)), float(payload.get('dy', 0))
        if not all(map(math.isfinite, (lat, lon, dx, dy))) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError('Coordenadas no válidas.')
        job.update('Preparando mapa. Si falta, se descargará el recurso verificado.')
        path = ensure_resource_available('mapas/' + Path(config['archivo']).name)
        job.check()
        (lat1, lon1), (lat2, lon2) = config['pt1_geo'], config['pt2_geo']
        (x1, y1), (x2, y2) = config['pt1_pixel'], config['pt2_pixel']
        x = x1 + (lon - lon1) * (x2 - x1) / (lon2 - lon1) + dx + config.get('ajuste_x', 0)
        y = y1 + (lat - lat1) * (y2 - y1) / (lat2 - lat1) + dy + config.get('ajuste_y', 0)
        with Image.open(path) as source:
            if not (0 <= x < source.width and 0 <= y < source.height):
                raise ValueError('El punto queda fuera del mapa seleccionado.')
            image = source.convert('RGB')
        draw = ImageDraw.Draw(image)
        draw.ellipse((x-15, y-15, x+15, y+15), fill='black', width=4)
        draw.ellipse((x-4, y-4, x+4, y+4), fill='red')
        output = self.runtime / f'{job.id}.png'
        image.save(output)
        return self.artifact(output, 'image/png')

    def prospect(self, job, payload):
        from sincal.prospecciones import read_report
        path = self.files.get(payload.get('file'), 'report')
        if path.stat().st_size > 100 * 1024 * 1024:
            raise ValueError('Informe demasiado grande (máximo 100 MB).')
        def progress(*args):
            job.update(' · '.join(map(str, args)))
        report = read_report(str(path), ocr=True, exhaustive=payload.get('exhaustive') is True,
                             progress=progress, cancel=job.cancelled.is_set)
        job.check()
        return self.describe_report(report)

    @staticmethod
    def describe_report(report):
        from sincal.cad.prospecciones import profile_scene
        return {'report': report.to_dict(), 'checks': [dict(key=p.key, errors=p.errors(), warnings=p.warnings(),
            scene=profile_scene(p, False) if not p.errors() else []) for p in report.profiles]}

    def command(self, job, payload):
        from sincal.cad.commands import normalizar_comando_cad_autonomo
        command = normalizar_comando_cad_autonomo(payload.get('command'))
        if command.upper() == 'STO':
            command = 'ST0'
        if command.upper().lstrip('_.') not in (*COMMANDS, 'ST0') and payload.get('autonomous') is not True:
            raise ValueError('Confirma que el comando personalizado no requiere interacción.')
        return self.cad(job, payload.get('expected'), command + '\n', scope='all' if payload.get('scope') == 'all' else 'active')

    def crossbeam(self, job, payload):
        from sincal.cad.crossbeam import build_crossbeam_lisp, build_crossbeam_detail_lisp
        from .rebar import number
        state = payload.get('state', {})
        quadrant = payload.get('quadrant')
        if quadrant not in ('EXT_IZQ', 'EXT_DER', 'INT_TOPE', 'INT_MACIZO', 'INT_VIGA'):
            raise ValueError('Cuadrante desconocido.')
        values = [number(state, key, low, high) for key, low, high in (
            ('recub', 0, 30), ('espesor', 1, 1000), ('esviaje', -89, 89),
            ('phi_ext', 12, 36), ('phi_horiz', 12, 36), ('phi_estr', 12, 36), ('largo_viga', 1, 1200))]
        if values[1] <= 2 * values[0] or any(value not in (12, 16, 18, 22, 25, 28, 32, 36) for value in values[3:6]):
            raise ValueError('Espesor/recubrimiento o diámetro no válido.')
        if payload.get('detail'):
            count = number(state, 'cant_trav', 1, 100)
            if int(count) != count:
                raise ValueError('La cantidad debe ser entera.')
            source = build_crossbeam_detail_lisp(quadrant, *values, int(count))
            command = 'SINCAL-DESPIECE-TRAV'
        else:
            source = build_crossbeam_lisp(quadrant, *values)
            command = 'SINCAL-TRAVESANO'
        path = self.lisp(job, source)
        signature = hashlib.sha256(json.dumps([quadrant, state], sort_keys=True).encode()).hexdigest()
        if payload.get('detail'):
            guard = f'(if (or (not (boundp \'*SINCAL_WEB_TRAV_SIGNATURE*)) (/= *SINCAL_WEB_TRAV_SIGNATURE* "{signature}")) (progn (alert "Genere este cuadrante con estos parametros antes de pedir su despiece.") (exit))) '
            order = f'(progn {guard}(load "{path}") (c:{command}))\n'
        else:
            order = f'(progn (setq *SINCAL_TRAV_HANDLE* nil *SINCAL_WEB_TRAV_SIGNATURE* "{signature}") (load "{path}") (c:{command}))\n'
        return self.cad(job, payload.get('expected'), order, True)

    def detect(self, job, payload):
        from sincal.ui.tabs.armaduras import TabArmaduras
        from sincal.cad.moldajes import parse_moldaje_detection
        folder = self.runtime / job.id
        folder.mkdir(exist_ok=True)
        output = folder / 'moldajes.txt'
        path = self.lisp(job, TabArmaduras._lisp_detector_moldajes(str(output)))
        self.cad(job, payload.get('expected'), f'(progn (load "{path}") (c:SINCAL-DETECTAR-ZAPATA))\n', True)
        if not output.exists():
            raise ValueError('El detector no generó un resultado. Revisa CAD.')
        detection = parse_moldaje_detection(output.read_text(encoding='utf-8'))
        key = self.remember(self.detections, (payload['expected'], detection))
        return {'detection': key, **asdict(detection)}

    def rebar(self, job, payload):
        from sincal.cad.zapata_views import build_zapata_lisp
        from sincal.cad.zapata_detail import build_zapata_detail_lisp
        from sincal.rebar.model import build_zapata_schedule
        from sincal.runtime import ruta_recurso
        geometry, cover, rules = domain(payload['state'])
        schedule = build_zapata_schedule(geometry, cover, rules)
        if not schedule.is_valid:
            raise ValueError('Corrige las advertencias del cálculo antes de dibujar.')
        key = payload.get('abutment')
        if key not in ('entrada', 'salida'):
            raise ValueError('Estribo no válido.')
        master = ruta_recurso('masters', 'FORMATOS ANOTATIVOS ACAD_2025.dwg')
        candidate = None
        if payload.get('view') == 'detail':
            source = build_zapata_detail_lisp(schedule, rules, geometry, key, master)
            command = 'SINCAL-ZAPATA-DESPIECE'
            expected = payload.get('expected')
        else:
            detection = self.detections.get(payload.get('detection'))
            if not detection:
                raise ValueError('Detecta y confirma moldajes de este dibujo primero.')
            expected, result = detection
            candidate = next((c for c in result.candidates if c.handle == payload.get('handle') and c.is_valid), None)
            view = payload.get('view')
            if view not in ('FR', 'AA', 'BB', 'CC', 'DD', 'EE') or not candidate or candidate.layer != view + '_ZAP':
                raise ValueError('Selecciona un contorno válido para esa vista.')
            source = build_zapata_lisp(view, candidate, geometry, cover, rules, key, master)
            command = 'SINCAL-ZAPATA-GENERAR'
        path = self.lisp(job, source)
        return self.cad(job, expected, f'(progn (load "{path}") (c:{command}))\n', True,
                        asdict(candidate) if candidate else None)

    def profile(self, job, payload):
        from sincal.prospecciones import VsReport
        from sincal.cad.prospecciones import build_profile_lisp
        report = VsReport.from_dict(payload['report'])
        profile = next((p for p in report.profiles if p.key == payload.get('key')), None)
        if not profile or profile.errors() or (profile.method == 'ocr' and not profile.reviewed):
            raise ValueError('Coteja el OCR y resuelve los errores antes de insertar.')
        path = self.lisp(job, build_profile_lisp(profile, payload.get('table') is not False))
        return self.cad(job, payload.get('expected'), f'(progn (load "{path}") (c:SINCAL-PROSPECCIONES))\n', True)
