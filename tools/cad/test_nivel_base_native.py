"""Check NIVEL_MM BASE fields in an isolated CAD process and disposable DWGs.

Examples:
  python tools/cad/test_nivel_base_native.py --progid AutoCAD.Application.25
  python tools/cad/test_nivel_base_native.py --progid AutoCAD.Application.26
  python tools/cad/test_nivel_base_native.py --progid ZWCAD.Application.2026
  python tools/cad/test_nivel_base_native.py --master C:/temp/candidate.dwg

The source master is copied, never opened for editing. No LOGFILEMODE changes.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import tempfile
import time

import win32api
import win32com.client
import win32con
import win32event
import win32process


def retry(call, seconds=30):
    deadline = time.monotonic() + seconds
    while True:
        try:
            return call()
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.5)


def lisp_string(value):
    return '"' + str(value).replace('\\', '/').replace('"', '\\"') + '"'


def phase(app, doc, name, master, report, root):
    retry(doc.Activate)
    # Second line of defense if the LISP error handler cannot complete.
    previous = {key: retry(lambda key=key: doc.GetVariable(key))
                for key in ('FILEDIA', 'ATTREQ')}
    try:
        action = ('(SNB:PrepareUndo {master} {report})' if name == 'UNDO'
                  else '(SNB:Run {phase} {master} {report})')
        command = ('(progn (load {updater}) (load {test}) ' + action + ')\n').format(
            updater=lisp_string(root / 'lisps/UPDATEBLOCK.lsp'),
            test=lisp_string(root / 'tests/cad/nivel_base_regression.lsp'),
            phase=lisp_string(name), master=lisp_string(master), report=lisp_string(report))
        retry(lambda: doc.SendCommand(command))
        deadline = time.monotonic() + 180
        undo_group_sent = False
        undo_sent = False
        while time.monotonic() < deadline:
            content = report.read_text(errors='replace') if report.exists() else ''
            match = re.search(rf'^PHASE_DONE {name} failures=(\d+)$', content, re.M)
            if match:
                return int(match.group(1))
            if (name == 'UNDO' and not undo_group_sent
                    and re.search(r'^UNDO_FIXTURE_READY$', content, re.M)):
                undo_group_sent = True
                doc.SendCommand(f'(SNB:RunUndoGroup {lisp_string(report)})\n')
            if name == 'UNDO' and not undo_sent and re.search(r'^UNDO_READY$', content, re.M):
                undo_sent = True
                # One separate expression. Do not retry U after an ambiguous
                # SendCommand result, which could undo the fixture itself.
                doc.SendCommand(f'_.U\n(SNB:CheckUndo {lisp_string(report)})\n')
            time.sleep(.5)
        raise TimeoutError(f'{name} did not produce PHASE_DONE; report: {report}')
    finally:
        for key, value in previous.items():
            try:
                if retry(lambda key=key: doc.GetVariable(key), 5) != value:
                    retry(lambda key=key, value=value: doc.SetVariable(key, value), 5)
            except Exception as exc:
                print(f'Could not restore {key} in scratch process: {exc}', flush=True)


def close_owned(app, process_handle, pid):
    """All documents belong to the new PID; never attach to a user's process."""
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                for doc in list(app.Documents):
                    doc.Close(False)
                app.Quit()
                break
            except Exception:
                time.sleep(.5)
        if win32event.WaitForSingleObject(process_handle, 5000) == win32con.WAIT_TIMEOUT:
            # The retained process handle prevents killing a recycled PID.
            print(f'Closing owned scratch CAD process {pid} after graceful close failed.', flush=True)
            win32api.TerminateProcess(process_handle, 1)
            win32event.WaitForSingleObject(process_handle, 5000)
    finally:
        process_handle.Close()


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--progid', default='AutoCAD.Application.25')
    parser.add_argument('--master', type=Path, default=root / 'masters/FORMATOS ANOTATIVOS ACAD_2025.dwg')
    args = parser.parse_args()
    master = args.master.resolve(strict=True)
    before_hash = hashlib.sha256(master.read_bytes()).hexdigest()
    folder = Path(tempfile.mkdtemp(prefix='sincal-nivel-base-test-'))
    scratch, report = folder / 'master-copy.dwg', folder / 'report.txt'
    import_source = folder / 'import-source.dwg'
    shutil.copy2(master, scratch)
    # ObjectDBX gets its own closed file, never a file open in the CAD editor.
    shutil.copy2(master, import_source)
    print(f'Report: {report}', flush=True)
    before = set(win32process.EnumProcesses())
    app = win32com.client.DispatchEx(args.progid)
    pid = retry(lambda: win32process.GetWindowThreadProcessId(app.HWND)[1], 60)
    if pid in before:
        raise RuntimeError('COM returned an existing CAD process; refusing to touch it.')
    process_handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, pid)
    failures = 0
    try:
        retry(lambda: setattr(app, 'Visible', False))
        doc = retry(lambda: app.Documents.Open(str(scratch)), 60)
        time.sleep(3)
        failures += phase(app, doc, 'MASTER', scratch, report, root)
        blank = retry(lambda: app.Documents.Add(), 60)
        time.sleep(3)
        failures += phase(app, blank, 'IMPORT', import_source, report, root)
        undo_doc = retry(lambda: app.Documents.Add(), 60)
        time.sleep(3)
        failures += phase(app, undo_doc, 'UNDO', import_source, report, root)
        if hashlib.sha256(master.read_bytes()).hexdigest() != before_hash:
            raise AssertionError('Source master changed during the test.')
        known = report.read_text(errors='replace').count('KNOWN_LIMITATION ')
        summary = f'DONE failures={failures} phases=3 known_limitations={known}'
        with report.open('a', encoding='utf-8') as stream:
            stream.write(summary + '\n')
        print(report.read_text(errors='replace'), flush=True)
        return 0 if failures == 0 else 1
    finally:
        close_owned(app, process_handle, pid)


if __name__ == '__main__':
    raise SystemExit(main())
