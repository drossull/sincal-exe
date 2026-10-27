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
import pywintypes

# Reuse the existing guarded process lifecycle, without running NIVEL tests.
from test_nivel_base_native import retry, close_owned, lisp_string


def send(doc, command):
    deadline = time.monotonic() + 30
    while True:
        try:
            return doc.SendCommand(command)
        except pywintypes.com_error as exc:
            # Only retry an explicitly rejected call, never an ambiguous result.
            if exc.hresult != -2147418111 or time.monotonic() >= deadline:
                raise
            time.sleep(.5)


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
    test_loaded = False
    try:
        retry(lambda: setattr(app, 'Visible', False))
        doc = retry(lambda: app.Documents.Add(), 60)
        pickfirst = retry(lambda: doc.GetVariable('PICKFIRST'))
        retry(lambda: doc.SetVariable('PICKFIRST', win32com.client.VARIANT(pythoncom.VT_I2, 1)))
        send(doc,
            f'(load {lisp_string(root / "lisps/OF2.lsp")})\n'
            f'(load {lisp_string(root / "tests/cad/of2_regression.lsp")})\n'
            f'(OF2T:Prepare {lisp_string(report)})\n')
        test_loaded = True
        command_ok = True
        cases = (
            ('', '4', 2.0, 'T', 'initial default Total'),
            ('', '6', 3.0, 'T', 'remember Total'),
            ('L', '2', 2.0, 'L', 'explicit Lado'),
            ('', '', 2.0, 'L', 'remember Lado and distance'),
            ('T', '', 2.0, 'T', 'convert default to total width'),
            ('L', '', 2.0, 'L', 'convert default back to per-side'),
            ('T\nL\nT', '', 2.0, 'T', 'change mode repeatedly before entering measure'),
        )
        for mode, measure, offset, saved, label in cases:
            send(doc, '(OF2T:Select)\n')
            existing = retry(lambda: {obj.Handle for obj in list(doc.ModelSpace)})
            # No initial confirmation for the remembered mode: a number (or
            # Enter for the previous measure) is the very first response.
            mode_input = f'{mode}\n' if mode else ''
            send(doc, f'OF2\n{mode_input}{measure}\n')
            ys = retry(lambda: sorted(obj.StartPoint[1] for obj in list(doc.ModelSpace)
                                      if obj.Handle not in existing))
            ok = len(ys) == 2 and all(abs(a - b) < 1e-8
                for a, b in zip(ys, (50 - offset, 50 + offset)))
            command_ok = command_ok and ok
            with report.open('a') as stream:
                stream.write(('PASS ' if ok else 'FAIL ') + label + ': geometry\n')
            # Read-only COM assertions do not add an empty undo step in ZWCAD.
            send(doc, f'_.U\n(OF2T:CheckUndo {offset} "{saved}")\n')
        send(doc, '(OF2T:Finish)\n')
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
            try:
                if test_loaded:
                    send(doc, '(OF2T:RestoreMode)\n')
            finally:
                if pickfirst is not None:
                    retry(lambda: doc.SetVariable('PICKFIRST',
                        win32com.client.VARIANT(pythoncom.VT_I2, pickfirst)), 5)
        finally:
            close_owned(app, handle, pid)


if __name__ == '__main__':
    raise SystemExit(main())
