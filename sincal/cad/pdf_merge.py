"""Assemble plot pages without changing the DWG's base name."""
import json
import os
from pathlib import Path
import tempfile
import shutil


def validate_pdf(path, expected_pages=None):
    """Require a complete, renderable PDF before exposing the final filename."""
    import pypdfium2 as pdfium
    with Path(path).open('rb') as stream:
        if not stream.read(8).startswith(b'%PDF-'):
            raise ValueError('Cabecera PDF ausente: ' + str(path))
        stream.seek(max(0, stream.seek(0, 2) - 4096))
        if b'%%EOF' not in stream.read():
            raise ValueError('PDF incompleto (sin fin de archivo): ' + str(path))
    with pdfium.PdfDocument(path) as document:
        count = len(document)
        if not count or (expected_pages is not None and count != expected_pages):
            raise ValueError('Numero de paginas PDF incorrecto: ' + str(path))
        for index in range(count):
            page = document[index]
            try:
                width, height = page.get_size()
                if width <= 0 or height <= 0:
                    raise ValueError('Tamano de pagina PDF no valido.')
                # Bounded preview: exercise fonts/images/streams without the
                # memory and latency of rasterizing an A1 sheet at print DPI.
                bitmap = page.render(scale=min(1, 1024 / max(width, height)))
                bitmap.close()
            finally:
                page.close()
    return count


def merge_request(request_path):
    from pypdf import PdfReader, PdfWriter
    data = json.loads(Path(request_path).read_text(encoding='utf-8-sig'))
    target = Path(data['target'])
    pages = [Path(p) for p in data['pages']]
    if not target.is_absolute() or target.suffix.lower() != '.pdf' or not pages:
        raise ValueError('Destino PDF o páginas no válidos.')
    overwrite = data.get('overwrite') is True
    if target.exists() and not overwrite:
        raise FileExistsError('El PDF ya existe: ' + str(target))
    writer = None
    temporary = None
    try:
        expected = sum(validate_pdf(page) for page in pages)
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.sincal.pdf', delete=False) as stream:
            temporary = Path(stream.name)
            if len(pages) == 1:
                # Do not rebuild AutoCAD's catalog/layers/fonts for one file.
                with pages[0].open('rb') as source:
                    shutil.copyfileobj(source, stream)
            else:
                writer = PdfWriter()
                for page in pages:
                    writer.append(PdfReader(page))
                writer.write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        validate_pdf(temporary, expected_pages=expected)
        if overwrite:
            os.replace(temporary, target)
        else:
            # Windows rename rejects a destination created since the initial check.
            if os.name == 'nt':
                temporary.rename(target)
            else:
                os.link(temporary, target)
                temporary.unlink()
    finally:
        if writer is not None:
            writer.close()
        if temporary and temporary.exists():
            temporary.unlink()


if __name__ == '__main__':
    import sys
    merge_request(sys.argv[1])
