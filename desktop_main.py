"""Production entry point for SINCAL's local WebView2 desktop interface."""
import json
from pathlib import Path
import sys


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--merge-pdfs':
        from sincal.cad.pdf_merge import merge_request
        result_path = Path(sys.argv[2]).with_suffix('.result.json')
        try:
            merge_request(sys.argv[2])
        except Exception as error:
            result_path.write_text(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), encoding='utf-8')
            raise SystemExit(1)
        result_path.write_text(json.dumps({'ok': True}), encoding='utf-8')
    elif len(sys.argv) == 3 and sys.argv[1] == '--shell-request':
        from sincal.web.desktop import main as desktop
        from sincal.cad.batch import read_shell_request
        desktop(read_shell_request(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == '--sincal-cad-worker':
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
