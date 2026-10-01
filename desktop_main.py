"""Opt-in embedded UI entry point; the production Tk entry stays unchanged."""
import json
from pathlib import Path
import sys


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--sincal-cad-worker':
        from sincal.web.cad_worker import main as worker
        sys.argv = [sys.argv[0], sys.argv[2]]
        worker()
    elif len(sys.argv) == 3 and sys.argv[1] == '--sincal-cad-probe':
        from sincal.web.cad_probe import probe
        try:
            result = probe()
        except Exception:
            result = {'status':'unavailable', 'message':'CAD no pudo responder.'}
        Path(sys.argv[2]).write_text(json.dumps(result), encoding='utf-8')
    else:
        from sincal.web.desktop import main as desktop
        desktop()


if __name__ == '__main__':
    main()
