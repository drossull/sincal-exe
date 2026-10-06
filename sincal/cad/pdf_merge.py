"""Assemble plot pages without changing the DWG's base name."""
import json
import os
from pathlib import Path
import tempfile


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
    writer = PdfWriter()
    temporary = None
    try:
        for page in pages:
            reader = PdfReader(page)
            if not reader.pages:
                raise ValueError('PDF sin páginas: ' + str(page))
            writer.append(reader)
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.sincal.pdf', delete=False) as stream:
            temporary = Path(stream.name)
            writer.write(stream)
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
        writer.close()
        if temporary and temporary.exists():
            temporary.unlink()


if __name__ == '__main__':
    import sys
    merge_request(sys.argv[1])
