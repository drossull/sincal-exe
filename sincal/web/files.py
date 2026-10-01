"""Opaque native-picker grants; HTTP never accepts arbitrary filesystem paths."""
from pathlib import Path
import threading
import uuid


class Files:
    TYPES = {'folder': (), 'report': ('.pdf', '.txt'), 'location': ('.kmz', '.kml'),
             'session': ('.json',), 'image': ('.png', '.jpg', '.jpeg'), 'dxf': ('.dxf',)}

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
            if len(self.items) >= 500:
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
