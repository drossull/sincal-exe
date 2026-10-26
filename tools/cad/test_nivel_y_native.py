"""Test NIVEL/NIVEL_MM in a disposable copy, never in an open user drawing.

Example: python tools/cad/test_nivel_y_native.py --progid ZWCAD.Application.2026
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import tempfile
import time

import win32com.client
import win32process


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--progid', default='AutoCAD.Application.25')
    parser.add_argument('--drawing', type=Path, default=root / 'masters/FORMATOS ANOTATIVOS ACAD_2025.dwg')
    args = parser.parse_args()
    before_hash = hashlib.sha256(args.drawing.read_bytes()).hexdigest()
    folder = Path(tempfile.mkdtemp(prefix='sincal-nivel-y-test-'))
    scratch, report = folder / 'scratch.dwg', folder / 'report.txt'
    shutil.copy2(args.drawing, scratch)
    before = set(win32process.EnumProcesses())
    app = win32com.client.DispatchEx(args.progid)
    for attempt in range(60):
        try:
            pid = win32process.GetWindowThreadProcessId(app.HWND)[1]
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError('CAD did not initialize')
    if pid in before:
        raise RuntimeError('Refusing to use an existing CAD process')
    try:
        app.Visible = False
        doc = app.Documents.Open(str(scratch))
        time.sleep(4)
        command = f'''(progn (setvar "CMDECHO" 0)
          (setq SNY:report (open "{report.as_posix()}" "w"))
          (defun *error* (m) (if SNY:report (progn
            (write-line (strcat "ERROR " m) SNY:report) (close SNY:report))) (princ))
          (load "{root.as_posix()}/tests/cad/nivel_y_regression.lsp") (SNY:Test))'''
        doc.SendCommand(command.replace('\n', ' ') + '\n')
        for attempt in range(180):
            text = report.read_text(errors='replace') if report.exists() else ''
            if 'DONE' in text or 'ERROR' in text:
                break
            time.sleep(.5)
        print(text)
        print(f'Report: {report}')
        assert before_hash == hashlib.sha256(args.drawing.read_bytes()).hexdigest(), 'Source DWG changed'
        return 0 if 'DONE checks=580 failures=0' in text else 1
    finally:
        # This process was created by this test. Its startup Drawing1 is also
        # disposable; close it explicitly to avoid a hidden save prompt on Quit.
        for attempt in range(20):
            try:
                for opened in list(app.Documents):
                    opened.Close(False)
                app.Quit()
                break
            except Exception:
                time.sleep(.5)
        else:
            print(f'Close scratch CAD process {pid} without saving.')


if __name__ == '__main__':
    raise SystemExit(main())
