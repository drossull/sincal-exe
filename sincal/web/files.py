"""Opaque native-picker grants; HTTP never accepts arbitrary filesystem paths."""
from pathlib import Path
import json
import os
import threading
import uuid


class Files:
    TYPES = {'folder': (), 'report': ('.pdf', '.txt'), 'location': ('.kmz', '.kml'),
             'memory_pdf': ('.pdf',), 'memory_excel': ('.xls', '.xlsx', '.xlsm'),
             'session': ('.json',), 'image': ('.png', '.jpg', '.jpeg'), 'dxf': ('.dxf',), 'dwg': ('.dwg',),
             'reference': ('.doc', '.docx', '.xls', '.xlsx', '.csv', '.png', '.jpg', '.jpeg', '.zip', '.ifc', '.rvt')}

    def __init__(self):
        self.picker = None
        self.items = {}
        self.lock = threading.Lock()

    def choose(self, kind):
        if kind not in self.TYPES:
            raise ValueError('Tipo de selección no permitido.')
        if self.picker is None:
            raise ValueError('Abre SINCAL en su ventana de escritorio para seleccionar archivos locales.')
        paths = self.picker(kind)
        return [self.grant(path, kind) for path in (paths or [])]

    def grant(self, path, kind):
        target = Path(path).resolve(strict=True)
        if kind == 'folder':
            if not target.is_dir():
                raise ValueError('Selecciona una carpeta.')
        elif not target.is_file() or target.suffix.lower() not in self.TYPES[kind]:
            raise ValueError('Archivo no compatible.')
        key = uuid.uuid4().hex
        with self.lock:
            for existing, item in self.items.items():
                if item == (target, kind):
                    return {'id': existing, 'name': target.name, 'path': str(target)}
            if len(self.items) >= 20000:
                raise ValueError('Demasiados archivos seleccionados; reinicia la vista previa.')
            self.items[key] = (target, kind)
        return {'id': key, 'name': target.name, 'path': str(target)}

    def get(self, key, kind):
        with self.lock:
            item = self.items.get(key)
        if not item or item[1] != kind:
            raise ValueError('Vuelve a seleccionar el archivo o carpeta.')
        if item[0].resolve(strict=True) != item[0]:
            raise ValueError('Cambió el destino del archivo o carpeta. Selecciónalo de nuevo.')
        return item[0]

    def project_catalog(self, key):
        """Index a picker-authorized root; never follow junctions/symlinks."""
        root = self.get(key, 'folder')
        entries, warnings, pending = [], [], [root]
        visited = 0
        excluded = {'.git', '.venv', 'node_modules', '__pycache__', 'sincal_backups', '$recycle.bin'}
        def add(path, kinds):
            entries.append({'name': path.name, 'path': str(path),
                            'relative': str(path.relative_to(root)) if path != root else '.',
                            'grants': {kind:self.grant(path,kind)['id'] for kind in kinds}})
        add(root, ['folder'])
        while pending and visited < 5000:
            folder = pending.pop()
            try:
                if folder != root and (folder.is_symlink() or folder.is_junction() or not folder.resolve(strict=True).is_relative_to(root)):
                    continue
                with os.scandir(folder) as scan:
                    for item in scan:
                        if visited >= 5000:
                            break
                        visited += 1
                        path = Path(item.path)
                        if item.is_symlink() or path.is_junction():
                            continue
                        if not path.resolve(strict=True).is_relative_to(root):
                            continue
                        if item.is_dir(follow_symlinks=False):
                            if item.name.lower() not in excluded:
                                add(path,['folder']);pending.append(path)
                        elif item.is_file(follow_symlinks=False):
                            kinds = [kind for kind, extensions in self.TYPES.items() if path.suffix.lower() in extensions]
                            if kinds:
                                add(path,kinds)
            except OSError:
                warnings.append('No se pudo leer: '+str(folder.relative_to(root)))
        if visited >= 5000:
            warnings.append('Se alcanzó el límite de 5000 elementos examinados. Selecciona una carpeta de proyecto más específica para ver los restantes.')
        return {'root':{'id':key,'name':root.name,'path':str(root)},
                'entries':sorted(entries,key=lambda e:e['relative'].casefold()),'warnings':warnings}

    def read_json(self, key):
        path = self.get(key, 'session')
        if path.stat().st_size > 48*1024*1024:
            raise ValueError('El JSON supera 48 MB.')
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict):
            raise ValueError('El JSON debe contener un objeto.')
        if value.get('schema') not in ('sincal-stratigraphy-1','sincal-stratigraphy-2') and path.stat().st_size > 4*1024*1024:
            raise ValueError('El JSON del proyecto supera 4 MB.')
        return {'name':path.name,'value':value}

    def list_folder(self, key):
        folder = self.get(key, 'folder')
        return [{'name': path.name, 'bytes': path.stat().st_size}
                for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold())
                if not path.is_symlink() and path.is_file()]


def rename_plan(folder, search, replacement):
    if not isinstance(search, str) or not search or not isinstance(replacement, str):
        raise ValueError('Escribe el texto que se debe buscar y su reemplazo.')
    if any(c in search + replacement for c in '\\/:*?"<>|\r\n\x00'):
        raise ValueError('El nombre contiene caracteres no permitidos.')
    changes = []
    destinations = set()
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.is_symlink() or search not in path.stem:
            continue
        name = path.stem.replace(search, replacement) + path.suffix
        if name == path.name:
            continue
        target = folder / name
        if not name.strip(' .') or name.endswith((' ', '.')) or target.is_reserved():
            raise ValueError(f'Nombre de destino no válido: {name}')
        if target.exists() or name.casefold() in destinations:
            raise ValueError(f'Existe o se repite el destino: {name}')
        destinations.add(name.casefold())
        stat = path.stat()
        changes.append({'source': path.name, 'target': name, 'size': stat.st_size, 'mtime': stat.st_mtime_ns})
    return changes


def apply_rename(folder, changes, job):
    for item in changes:
        path = folder / item['source']
        stat = path.stat()
        if path.is_symlink() or stat.st_size != item['size'] or stat.st_mtime_ns != item['mtime'] or (folder / item['target']).exists():
            raise ValueError('La carpeta cambió después de la vista previa. Genera otro plan.')
    done = []
    try:
        for index, item in enumerate(changes):
            job.check()
            source, target = folder / item['source'], folder / item['target']
            if target.exists():
                raise ValueError('El destino acaba de ser creado; no se sobrescribirá.')
            source.rename(target)
            done.append(item)
            job.update(f"Renombrado {item['source']} → {item['target']}", (index + 1) * 100 / len(changes))
    except Exception:
        for item in reversed(done):
            source, target = folder / item['source'], folder / item['target']
            if not source.exists():
                target.rename(source)
        raise
    return {'renamed': len(done), 'changes': changes}
