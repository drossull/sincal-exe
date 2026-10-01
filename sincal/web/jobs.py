"""Bounded background work with one durable, redacted log per execution."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import uuid

from sincal.diagnostics import redact_text


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, directory, operation):
        self.id = uuid.uuid4().hex
        self.operation = operation
        self.created = datetime.now(timezone.utc).isoformat()
        self.state = 'queued'
        self.progress = None
        self.message = 'En espera'
        self.result = None
        self.cancelled = threading.Event()
        self.lock = threading.RLock()
        self.path = directory / f'{self.id}.jsonl'
        self.update('Ejecución creada')

    def update(self, message, progress=None):
        with self.lock:
            self.message = str(message)
            self.progress = None if progress is None else max(0, min(100, float(progress)))
            record = {'time': datetime.now(timezone.utc).isoformat(), 'operation': self.operation,
                      'state': self.state, 'progress': self.progress, 'message': redact_text(message)}
            if self.path.exists() and self.path.stat().st_size > 2 * 1024 * 1024 and self.state == 'running':
                return
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled('Cancelado. Los pasos ya terminados no se deshacen.')

    def snapshot(self):
        with self.lock:
            return dict(id=self.id, operation=self.operation, created=self.created, state=self.state,
                        progress=self.progress, message=self.message, result=self.result)


class Jobs:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='sincal-job')
        self.items = {}
        self.lock = threading.RLock()
        self.prune()

    def prune(self):
        # Only our own UUID-named logs; never delete user files or active logs.
        logs = sorted((p for p in self.directory.glob('*.jsonl')
                       if len(p.stem) == 32 and all(c in '0123456789abcdef' for c in p.stem)),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        active = {key for key, job in self.items.items() if job.state in ('queued', 'running')}
        for index, path in enumerate(logs):
            if path.stem not in active and (index >= 100 or time.time() - path.stat().st_mtime > 30 * 86400):
                path.unlink(missing_ok=True)

    def submit(self, operation, function):
        with self.lock:
            if sum(j.state in ('queued', 'running') for j in self.items.values()) >= 8:
                raise ValueError('Hay demasiadas operaciones pendientes.')
            self.prune()
            for key in list(self.items):
                if len(self.items) >= 100 and self.items[key].state not in ('queued', 'running'):
                    del self.items[key]
            job = Job(self.directory, operation)
            self.items[job.id] = job
            self.pool.submit(self._run, job, function)
            return {'id': job.id}

    @staticmethod
    def _run(job, function):
        try:
            job.check()
            job.state = 'running'
            job.update('Iniciando')
            result = function(job)
            with job.lock:
                job.result = result
                job.state = 'completed'
                job.update('Finalizado', 100)
        except Cancelled as error:
            job.state = 'cancelled'
            job.update(str(error))
        except Exception as error:
            job.state = 'failed'
            job.update(str(error))

    def get(self, key):
        with self.lock:
            if key not in self.items:
                raise ValueError('Ejecución no encontrada.')
            return self.items[key]

    def logfile(self, key):
        if not isinstance(key, str) or len(key) != 32 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Registro no válido.')
        path = self.directory / (key + '.jsonl')
        if not path.is_file():
            raise ValueError('Registro no encontrado o vencido.')
        return path

    def history(self):
        records = []
        for path in sorted(self.directory.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
            try:
                self.logfile(path.stem)
                lines = path.read_text(encoding='utf-8').splitlines()
                last = json.loads(lines[-1])
                if path.stem not in self.items and last['state'] in ('running', 'queued'):
                    last.update(state='interrupted', message='La aplicación terminó sin registrar el resultado. Revisa el destino antes de repetir.')
                records.append({'id': path.stem, **last})
            except (ValueError, OSError, IndexError):
                continue
        return records

    def close(self):
        for job in list(self.items.values()):
            job.cancelled.set()
        self.pool.shutdown(wait=False, cancel_futures=True)
