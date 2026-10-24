"""Reject an accidentally packaged legacy UI before signing or installing it."""
from pathlib import Path
import sys

from PyInstaller.archive.readers import CArchiveReader


def verify(path: Path) -> None:
    archive = CArchiveReader(str(path))
    entries = {name.replace('\\', '/') for name in archive.toc}
    required = {
        'desktop_main',
        'sincal/web/static/index.html',
        'sincal/web/static/app.js',
        'sincal/web/static/rebar.js',
        'sincal/web/static/rebar_assistant.js',
    }
    missing = required - entries
    if missing or 'main' in entries:
        raise ValueError(f'Interfaz empaquetada incorrecta. Faltan: {sorted(missing)}; arranque Tk: {"main" in entries}')
    modules = archive.open_embedded_archive('PYZ.pyz').toc
    for name in ('sincal.web.desktop', 'sincal.web.server', 'sincal.rebar.catalog'):
        if name not in modules:
            raise ValueError(f'Falta el módulo web requerido: {name}')
    print('OK: arranque WebView2, interfaz web y catálogo de armaduras incluidos en el ejecutable.')


if __name__ == '__main__':
    verify(Path(sys.argv[1]))
