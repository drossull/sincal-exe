"""Explicit, confirmed revision history updates on picker-granted DWGs."""
from pathlib import Path
import uuid

from sincal.cad.dwgprops import CadBatch, CadUnavailable, process_file


def revision_values(value):
    if (not isinstance(value, list) or len(value) != 6
            or any(not isinstance(s, str) or not s.strip() or len(s) > 250
                   or any(ord(c) < 32 for c in s) or any(c in s for c in ('%<', '\\', '{', '}')) for s in value)):
        raise ValueError('Completa los seis datos de la revisión con texto simple (máximo 250 caracteres por campo).')
    return [s.strip() for s in value]


def read(service, job, payload):
    ids = payload.get('files')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 500 or any(not isinstance(k,str) for k in ids):
        raise ValueError('Selecciona entre 1 y 500 archivos DWG.')
    paths = list(dict.fromkeys(service.files.get(key, 'dwg') for key in ids))
    if not service.cad_lock.acquire(blocking=False):
        raise ValueError('Hay otra operación CAD en curso.')
    batch = CadBatch(service.runtime / job.id, payload.get('engine'))
    batch.request_options = {'revisionRead': True}
    rows, snapshots = [], {}
    try:
        for index, path in enumerate(paths):
            if job.cancelled.is_set():
                break
            key = uuid.uuid4().hex
            job.update(f'Leyendo cuadro de revisiones · {path.name}', index * 100 / len(paths))
            try:
                result = process_file(path, service.runtime / job.id / key, worker=batch)
                revision = batch.result['revision']
                snapshots[key] = {'path': path, 'engine': payload.get('engine'), 'revision': revision, **result}
                rows.append({'id': key, 'name': path.name, 'revision': revision})
            except Exception as error:
                rows.append({'name': path.name, 'error': str(error)})
                job.update(f'{path.name}: {error}')
                if isinstance(error, CadUnavailable):
                    rows.extend({'name': p.name, 'error': 'No leído: AutoCAD dejó de responder.'} for p in paths[index+1:])
                    break
        return {'snapshot': service.remember(service.revision_snapshots, snapshots), 'files': rows, 'cancelled': job.cancelled.is_set()}
    finally:
        try:
            batch.close()
        finally:
            service.cad_lock.release()


def write(service, job, payload):
    if payload.get('confirm') is not True:
        raise ValueError('Confirma la nueva revisión y el desplazamiento del historial.')
    values = revision_values(payload.get('values'))
    with service.lock:
        snapshot = service.revision_snapshots.get(payload.get('snapshot'))
        ids = payload.get('ids')
        if not snapshot or not isinstance(ids,list) or not ids or any(not isinstance(k,str) or k not in snapshot for k in ids):
            raise ValueError('Vuelve a seleccionar y leer los archivos.')
        selected = [(k, dict(snapshot[k])) for k in dict.fromkeys(ids)]
    if not service.cad_lock.acquire(blocking=False):
        raise ValueError('Hay otra operación CAD en curso.')
    batch = CadBatch(service.runtime / job.id, selected[0][1].get('engine'))
    batch.request_options = {'revisionValues': values}
    rows = []
    try:
        for index, (key, item) in enumerate(selected):
            if job.cancelled.is_set():
                break
            path = Path(item['path'])
            job.update(f'Creando revisión {values[0]} · {path.name}', index * 100 / len(selected))
            try:
                if values[0].casefold() == item['revision']['rows'][0][0].strip().casefold():
                    raise ValueError('La nueva revisión coincide con la actual; no se desplazó el historial.')
                result = process_file(path, service.runtime / job.id / key, expected=item['fingerprint'], worker=batch, write=True)
                revision = batch.result['revision']
                archived = item['revision']['rows'][-1]
                with service.lock:
                    snapshot[key] = {'path': path, 'engine': item.get('engine'), 'revision': revision, **result}
                rows.append({'id': key, 'name': path.name, 'status': 'Revisión creada', 'revision': revision,
                             'backup': result['backup'], 'archived': archived})
                job.update(f'{path.name}: respaldo {result["backup"]}; fila saliente: {" | ".join(archived)}')
            except Exception as error:
                rows.append({'id': key, 'name': path.name, 'status': 'No modificado', 'error': str(error)})
                job.update(f'{path.name}: {error}')
                if isinstance(error, CadUnavailable):
                    rows.extend({'id': k, 'name': v['path'].name, 'status': 'No modificado', 'error': 'AutoCAD dejó de responder.'} for k,v in selected[index+1:])
                    break
        return {'files': rows, 'cancelled': job.cancelled.is_set()}
    finally:
        try:
            batch.close()
        finally:
            service.cad_lock.release()
