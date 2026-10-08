"""Custom-property snapshots and copy-on-write DWG editing."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from .batch import drawing_available


class CadUnavailable(RuntimeError):
    """Stop the batch instead of launching more instances after a timeout."""


def autocad_engines():
    """Only expose engines with a matching, bundled native connector."""
    if os.name != 'nt':
        return []
    from .engine import discover_cad_engines
    return [{'id': item.path, 'name': f'AutoCAD {item.year} · Core Console', 'year': item.year}
            for item in discover_cad_engines() if item.headless and connector_path(item.year).is_file()]


def connector_path(year):
    from sincal.runtime import RUTA_INSTALACION
    root = Path(RUTA_INSTALACION)
    if getattr(sys, 'frozen', False):
        return root / 'native' / 'dwgprops' / str(year) / 'Sincal.DwgProps.dll'
    return root / 'src' / 'Sincal.DwgProps' / 'bin' / str(year) / 'Sincal.DwgProps.dll'


def fingerprint(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def changeset(value):
    if not isinstance(value, dict) or not 1 <= len(value) <= 200:
        raise ValueError('Marca entre 1 y 200 propiedades para modificar.')
    seen = set()
    for key, item in value.items():
        if (not isinstance(key, str) or not key.strip() or key != key.strip()
                or len(key) > 255 or any(ord(c) < 32 for c in key) or key.casefold() in seen):
            raise ValueError('Nombre de propiedad vacío, repetido o no válido.')
        if item is not None and (not isinstance(item, str) or len(item) > 4096 or '\x00' in item):
            raise ValueError('Valor no válido; el límite es 4096 caracteres.')
        seen.add(key.casefold())
    return dict(value)


def patched(properties, changes):
    result = dict(properties)
    for key, value in changeset(changes).items():
        actual = next((name for name in result if name.casefold() == key.casefold()), key)
        if value is None:
            result.pop(actual, None)
        else:
            result[actual] = value
    return result


def cad_copy(path, changes, directory, engine=None):
    """Worker can access only a disposable copy, never the user's original."""
    if os.name != 'nt':
        raise ValueError('El editor DWGPROPS requiere Windows y AutoCAD instalado.')
    engines = autocad_engines()
    if engine is None and engines:
        engine = engines[0]['id']
    if engine not in {item['id'] for item in engines}:
        raise CadUnavailable('No hay un AutoCAD Core Console con conector DWGPROPS compatible. Revisa la instalación.')
    selected = next(item for item in engines if item['id'] == engine)
    connector = connector_path(selected['year'])
    request = directory / 'request.json'
    output = directory / 'result.json'
    done = directory / 'result.json.done'
    saved = directory / 'verified.dwg'
    output.unlink(missing_ok=True)
    done.unlink(missing_ok=True)
    saved.unlink(missing_ok=True)
    request.write_text(json.dumps({'file': str(path), 'changes': changes, 'output': str(output), 'saved': str(saved)}), encoding='utf-8')
    script = directory / 'properties.scr'
    # QSAVE affects only the disposable editor copy (startup hooks may dirty it).
    # Writes use the separately verified DWG, never this editor copy.
    script.write_text('_.NETLOAD\n"' + connector.as_posix() + '"\nSINCAL_DWGPROPS\n_.QSAVE\n_.QUIT\n', encoding='utf-8')
    environment = dict(os.environ, SINCAL_DWGPROPS_REQUEST=str(request))
    with (directory / 'worker.log').open('wb') as log:
        process = subprocess.Popen([engine, '/i', str(path), '/s', str(script), '/l', 'en-US'],
                                   cwd=directory, env=environment, stdout=log, stderr=log,
                                   stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 120
        controlled_stop = False
        try:
            while process.poll() is None and not done.is_file():
                if time.monotonic() >= deadline:
                    raise CadUnavailable('Core Console no respondió. Se detuvo solo el proceso de esta copia; el original no se modificó.')
                time.sleep(.1)
            if done.is_file():
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # Only our process, and only after the connector closed and
                    # verified all databases. No user drawing is open in it.
                    process.kill()
                    process.wait()
                    controlled_stop = True
            else:
                process.wait()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    if not output.exists() or not done.is_file():
        raise CadUnavailable('Core Console no confirmó el resultado. Revisa el registro del conector; el original no se modificó.')
    result = json.loads(output.read_text(encoding='utf-8'))
    if (process.returncode and not controlled_stop) or not result.get('ok'):
        raise RuntimeError(result.get('error', 'No se pudo procesar la copia DWG.'))
    if changes is not None:
        if not saved.is_file():
            raise RuntimeError('No se generó el DWG verificado; el original no se modificó.')
        os.replace(saved, path)
    return result['properties']


class CadBatch:
    """One private Core Console per job; requests and DWGs stay in temporary copies."""

    def __init__(self, directory, engine=None):
        self.directory = Path(directory).resolve()
        self.engine = engine
        self.process = None
        self.log = None
        self.closed = False
        self.request_options = {}
        self.result = None

    def _wait(self, marker):
        deadline = time.monotonic() + 120
        while not marker.is_file():
            if self.process.poll() is not None or time.monotonic() >= deadline:
                self.close()
                raise CadUnavailable('Core Console dejó de responder. Se detuvo el lote; no se modificó el original en curso.')
            time.sleep(.05)

    def _start(self, path):
        engines = autocad_engines()
        selected = next((e for e in engines if self.engine is None or e['id'] == self.engine), None)
        if not selected:
            raise CadUnavailable('No hay un AutoCAD Core Console con conector DWGPROPS compatible.')
        self.directory.mkdir(parents=True, exist_ok=True)
        # The editor opens a separate throwaway bootstrap, never a request DWG.
        bootstrap = self.directory / 'bootstrap.dwg'
        shutil.copy2(path, bootstrap)
        script = self.directory / 'batch.scr'
        script.write_text('_.NETLOAD\n"' + connector_path(selected['year']).as_posix()
                          + '"\nSINCAL_DWGPROPS_BATCH\n_.QSAVE\n_.QUIT\n', encoding='utf-8')
        self.log = (self.directory / 'worker.log').open('wb')
        try:
            self.process = subprocess.Popen([selected['id'], '/i', str(bootstrap), '/s', str(script), '/l', 'en-US'],
                cwd=self.directory, env=dict(os.environ, SINCAL_DWGPROPS_BATCH=str(self.directory)),
                stdout=self.log, stderr=self.log, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            self._wait(self.directory / 'ready')
        except BaseException:
            self.close()
            raise

    def __call__(self, path, changes, directory, engine=None):
        if self.closed:
            raise CadUnavailable('El conector del lote ya está cerrado.')
        directory = Path(directory).resolve()
        if directory.parent != self.directory:
            raise ValueError('La copia debe pertenecer a la carpeta temporal del lote.')
        if self.process is None:
            self._start(path)
        request, output, saved = (directory / name for name in ('request.json', 'result.json', 'verified.dwg'))
        request.write_text(json.dumps({'file': str(path), 'changes': changes, 'output': str(output), 'saved': str(saved), **self.request_options}), encoding='utf-8')
        pending = self.directory / 'next.tmp'
        pending.write_text(json.dumps(str(request)), encoding='utf-8')
        os.replace(pending, self.directory / 'next.json')
        self._wait(directory / 'result.json.done')
        result = json.loads(output.read_text(encoding='utf-8'))
        if not result.get('ok'):
            raise RuntimeError(result.get('error', 'No se pudo procesar la copia DWG.'))
        if changes is not None or self.request_options.get('revisionValues') is not None or self.request_options.get('revisionEdits') is not None:
            if not saved.is_file():
                raise RuntimeError('No se generó el DWG verificado; el original no se modificó.')
            os.replace(saved, path)
        self.result = result
        return result['properties']

    def close(self):
        self.closed = True
        try:
            if self.process is not None and self.process.poll() is None:
                (self.directory / 'stop').touch()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # Only this job's dedicated process owns these disposable copies.
                    self.process.kill()
                    self.process.wait()
        finally:
            if self.log is not None:
                self.log.close()


def process_file(path, directory, changes=None, expected=None, worker=cad_copy, engine=None, known_properties=None, write=False):
    path = Path(path)
    if path.is_symlink() or path.resolve() != path or not path.is_file() or path.suffix.lower() != '.dwg':
        raise ValueError('El archivo ya no es un DWG regular.')
    drawing_available(path)
    before = fingerprint(path)
    if expected is not None and before != expected:
        raise ValueError('El DWG cambió desde la lectura; vuelve a cargar sus propiedades.')
    if changes is not None and expected is not None and known_properties is not None and patched(known_properties, changes) == known_properties:
        return {'properties': dict(known_properties), 'fingerprint': before, 'unchanged': True}
    directory.mkdir(parents=True, exist_ok=True)
    copy = directory / path.name
    shutil.copy2(path, copy)
    if fingerprint(copy) != before:
        raise ValueError('El DWG cambió durante la copia; vuelve a leerlo.')
    properties = worker(copy, changes, directory, engine=engine) if engine else worker(copy, changes, directory)
    if changes is None and not write:
        return {'properties': properties, 'fingerprint': before}
    drawing_available(path)
    if fingerprint(path) != before:
        raise ValueError('El original cambió durante la edición; no se reemplazó.')
    backup = path.parent / 'SINCAL_Backups' / directory.parent.name / path.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    # Never replace an existing backup.
    with backup.open('xb') as target, path.open('rb') as source:
        shutil.copyfileobj(source, target)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.sincal-props-', suffix='.dwg', dir=path.parent, delete=False) as target:
            temporary = Path(target.name)
            with copy.open('rb') as source:
                shutil.copyfileobj(source, target)
        drawing_available(path)
        if fingerprint(path) != before:
            raise ValueError('El original cambió antes del guardado; no se reemplazó.')
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return {'properties': properties, 'fingerprint': fingerprint(path), 'backup': str(backup)}
