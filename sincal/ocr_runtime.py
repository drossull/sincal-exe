"""Proceso OCR aislado y cancelable; no instala dependencias en el equipo."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

from sincal.runtime import RUTA_INSTALACION


def find_runtime(application_dir=None, user_dir=None):
    """Prefer the separately installed engine; retain pre-module installations."""
    application = Path(application_dir or RUTA_INSTALACION)
    user = Path(user_dir) if user_dir is not None else Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'SINCAL'
    for module in (user / 'modules' / 'prospecciones-ocr', application / 'modules' / 'prospecciones-ocr'):
        if not module.exists():
            continue
        try:
            manifest = json.loads((module / 'module.json').read_text(encoding='utf-8'))
            compatible = (manifest.get('schema') == 1 and manifest.get('id') == 'prospecciones-ocr'
                          and type(manifest.get('worker_api')) is int and manifest['worker_api'] == 1
                          and manifest.get('python_abi') == '3.12' and manifest.get('runtime') == 'ocr_runtime')
            root = module / 'ocr_runtime'
            if not compatible or not all((root / name).is_file() for name in ('python.exe', 'worker.pyc', 'runtime-manifest.json')):
                raise ValueError('Módulo incompleto o incompatible.')
            return root
        except (OSError, ValueError, TypeError, AttributeError) as error:
            raise RuntimeError('Reinstala el complemento OCR de Prospecciones: su instalación está incompleta o no es compatible.') from error
    legacy = application / 'ocr_runtime'
    if (legacy / 'python.exe').is_file() and (legacy / 'worker.pyc').is_file():
        return legacy
    raise RuntimeError('Falta el complemento OCR de Prospecciones. Instala Setup_SINCAL_OCR y vuelve a importar el informe; no necesitas reinstalar SINCAL.')


class PaddleWorker:
    def __init__(self, *, cancel=None):
        root = find_runtime()
        python = root / 'python.exe'
        worker = root / 'worker.pyc'
        self.cancel = cancel
        self._close_lock = threading.Lock()
        self._closed = False
        self.temp = tempfile.TemporaryDirectory(prefix='sincal-ocr-')
        self.messages = queue.Queue()
        self.log = open(Path(self.temp.name) / 'worker.log', 'w+', encoding='utf-8')
        try:
            self.process = subprocess.Popen(
                [str(python), '-u', '-B', str(worker)], cwd=self.temp.name,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                text=True, encoding='utf-8', errors='replace',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception:
            self.log.close()
            self.temp.cleanup()
            raise
        self.receiver = threading.Thread(target=self._receive, daemon=True)
        self.receiver.start()
        atexit.register(self.close)

    def _receive(self):
        try:
            for line in self.process.stdout:
                if line.startswith('SINCAL_OCR:'):
                    try:
                        self.messages.put(json.loads(line[len('SINCAL_OCR:'):]))
                    except ValueError:
                        pass
        finally:
            self.messages.put({'error': 'El proceso OCR terminó inesperadamente.'})

    def recognize(self, image):
        from sincal.prospecciones_ocr import ImportCancelled
        path = Path(self.temp.name) / 'input.png'
        image.save(path, format='PNG')
        self.process.stdin.write(json.dumps({'image': str(path)}) + '\n')
        self.process.stdin.flush()
        deadline = time.monotonic() + 240
        while True:
            if self.cancel and self.cancel.is_set():
                raise ImportCancelled('OCR cancelado.')
            if time.monotonic() > deadline:
                raise RuntimeError('El motor OCR superó 240 segundos para una imagen.')
            try:
                result = self.messages.get(timeout=.1)
            except queue.Empty:
                continue
            if 'error' in result:
                raise RuntimeError(result['error'])
            return result

    def close(self):
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            self._close()

    def _close(self):
        atexit.unregister(self.close)
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process.stdin.close()
        self.receiver.join(timeout=2)
        self.process.stdout.close()
        self.log.close()
        self.temp.cleanup()
