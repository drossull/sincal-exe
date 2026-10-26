"""Regression against a new, disposable CAD process; never opens a user DWG.

python tools/cad/test_updateblock_native.py --progid AutoCAD.Application.25
python tools/cad/test_updateblock_native.py --progid AutoCAD.Application.26
python tools/cad/test_updateblock_native.py --progid ZWCAD.Application.2026
"""
import argparse
import hashlib
from pathlib import Path
import tempfile
import time

import win32com.client
import win32process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--progid', default='AutoCAD.Application.25')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    master = root / 'masters/FORMATOS ANOTATIVOS ACAD_2025.dwg'
    original = hashlib.sha256(master.read_bytes()).hexdigest()
    folder = Path(tempfile.mkdtemp(prefix='sincal-updateblock-test-'))
    report = folder / 'report.txt'
    before = set(win32process.EnumProcesses())
    app = win32com.client.DispatchEx(args.progid)
    doc = None
    for attempt in range(60):
        try:
            pid = win32process.GetWindowThreadProcessId(app.HWND)[1]
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError('CAD did not initialize.')
    if pid in before:
        raise RuntimeError('COM returned an existing CAD process; refusing to use it.')
    try:
        app.Visible = False
        for attempt in range(60):
            try:
                doc = app.Documents.Add()
                break
            except Exception:
                time.sleep(1)
        if doc is None:
            raise RuntimeError('No scratch document.')
        time.sleep(5)
        log = Path(doc.GetVariable('LOGFILENAME'))
        command = f'''(progn (setvar "LOGFILEMODE" 1)
          (setq SUBT:report (open "{report.as_posix()}" "w"))
          (defun *error* (m) (write-line (strcat "ERROR " m) SUBT:report) (close SUBT:report) (princ))
          (setenv "SINCAL_TEST_ROOT" "{root.as_posix()}")
          (load "{root.as_posix()}/lisps/UPDATEBLOCK.lsp")
          (load "{root.as_posix()}/tests/cad/updateblock_regression.lsp") (SUBT:Run))'''
        doc.SendCommand(command.replace('\n', ' ') + '\n')
        for attempt in range(120):
            content = report.read_text(errors='replace') if report.exists() else ''
            if 'DONE' in content or 'ERROR' in content:
                break
            time.sleep(.5)
        if 'DONE failures=0' in content:
            # Run U separately, outside the expression that built the fixture.
            doc.SendCommand(f'_.U\n(setq SUBT:report (open "{report.as_posix()}" "a"))\n(SUBT:CheckUndo)\n')
            time.sleep(1)
            content = report.read_text(errors='replace')
        print(content)
        print(f'Report: {report}\nCAD log: {log}')
        if original != hashlib.sha256(master.read_bytes()).hexdigest():
            raise AssertionError('Master changed!')
        return 0 if 'UNDO DONE failures=0' in content else 1
    finally:
        # PID ownership was checked before touching CAD. Close only our process.
        for attempt in range(20):
            try:
                if doc is not None:
                    doc.Close(False)
                    doc = None
                app.Quit()
                break
            except Exception:
                time.sleep(.5)
        else:
            print(f'Scratch CAD {pid} could not close; close it without saving.')


if __name__ == '__main__':
    raise SystemExit(main())
