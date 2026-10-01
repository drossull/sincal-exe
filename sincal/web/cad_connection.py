"""Isolated read-only connection check; never launches CAD."""
import json
import os
import subprocess
import sys
import threading
import tempfile
from pathlib import Path

_lock = threading.Lock()


def connection_status():
    if os.name != 'nt':
        return {"status": "unsupported", "message": "El conector CAD requiere Windows."}
    if not _lock.acquire(blocking=False):
        return {"status": "checking", "message": "Ya hay una comprobación CAD en curso."}
    try:
        with tempfile.TemporaryDirectory(prefix='sincal-probe-') as directory:
            output = Path(directory) / 'probe.json'
            frozen = getattr(sys, 'frozen', False)
            command = ([sys.executable, '--sincal-cad-probe', str(output)] if frozen else
                       [sys.executable, '-m', 'sincal.web.cad_probe'])
            result = subprocess.run(command,
                capture_output=True, text=True, encoding='utf-8', timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            if result.returncode:
                return {"status": "unavailable", "message": "No se pudo iniciar el conector CAD local."}
            return json.loads(output.read_text(encoding='utf-8') if frozen else result.stdout)
    except subprocess.TimeoutExpired:
        # subprocess.run kills only our probe, never the CAD process.
        return {"status": "timeout", "message": "CAD no respondió en 15 segundos. No se cerró CAD ni se envió ningún comando."}
    except (ValueError, OSError):
        return {"status": "unavailable", "message": "Respuesta del conector no disponible."}
    finally:
        _lock.release()
