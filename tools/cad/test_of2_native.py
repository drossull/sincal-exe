"""Run OF2 geometry, actual command, and undo checks in an owned scratch CAD.

python tools/cad/test_of2_native.py --progid AutoCAD.Application.25
python tools/cad/test_of2_native.py --progid AutoCAD.Application.26
python tools/cad/test_of2_native.py --progid ZWCAD.Application.2026
"""
import argparse
from pathlib import Path
import tempfile
import time

import win32api
import win32com.client
import win32con
import win32process
import pythoncom

# Reuse the existing guarded process lifecycle, without running NIVEL tests.
from test_nivel_base_native import retry, close_owned, lisp_string


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--progid', default='AutoCAD.Application.25')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = Path(tempfile.mkdtemp(prefix='sincal-of2-test-')) / 'report.txt'
    print(f'Report: {report}', flush=True)
    before = set(win32process.EnumProcesses())
    app = win32com.client.DispatchEx(args.progid)
    pid = retry(lambda: win32process.GetWindowThreadProcessId(app.HWND)[1], 60)
    if pid in before:
        raise RuntimeError('Refusing to touch an existing CAD process.')
    handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, pid)
    pickfirst = None
    try:
        retry(lambda: setattr(app, 'Visible', False))
        doc = retry(lambda: app.Documents.Add(), 60)
        pickfirst = retry(lambda: doc.GetVariable('PICKFIRST'))
        retry(lambda: doc.SetVariable('PICKFIRST', win32com.client.VARIANT(pythoncom.VT_I2, 1)))
        doc.SendCommand(
            f'(load {lisp_string(root / "lisps/OF2.lsp")})\n'
            f'(load {lisp_string(root / "tests/cad/of2_regression.lsp")})\n'
            f'(OF2T:Prepare {lisp_string(report)})\n')
        before_count = retry(lambda: doc.ModelSpace.Count)
        doc.SendCommand('OF2\n2\n')
        command_ok = retry(lambda: doc.ModelSpace.Count) == before_count + 2
        with report.open('a') as stream:
            stream.write(('PASS ' if command_ok else 'FAIL ') +
                         'real command: preselection and distance\n')
        # Do not insert an assertion LISP expression before U: ZWCAD can make
        # that expression an empty undo step. Inspect via read-only COM above.
        doc.SendCommand('_.U\n(OF2T:CheckUndo)\n')
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            content = report.read_text(errors='replace') if report.exists() else ''
            if 'DONE failures=' in content:
                print(content, flush=True)
                return 0 if command_ok and 'DONE failures=0' in content else 1
            time.sleep(.5)
        raise TimeoutError(f'Native checks did not finish: {report}')
    finally:
        try:
            if pickfirst is not None:
                retry(lambda: doc.SetVariable('PICKFIRST',
                    win32com.client.VARIANT(pythoncom.VT_I2, pickfirst)), 5)
        finally:
            close_owned(app, handle, pid)


if __name__ == '__main__':
    raise SystemExit(main())
