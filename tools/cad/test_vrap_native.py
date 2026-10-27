"""Exercise the real VRAP command in a new, hidden CAD process.

Examples:
  python tools/cad/test_vrap_native.py --progid AutoCAD.Application.25
  python tools/cad/test_vrap_native.py --progid AutoCAD.Application.26
  python tools/cad/test_vrap_native.py --progid ZWCAD.Application.2026

Only disposable, unsaved documents are used. Existing CAD processes are never
attached to, activated, closed, or terminated. The report remains in temp.
"""
import argparse
import json
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


def report_text(report):
    return report.read_text(errors='replace') if report.exists() else ''


def wait_for(report, pattern, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        content = report_text(report)
        match = re.search(pattern, content, re.M)
        if match:
            return match
        time.sleep(.5)
    raise TimeoutError(f'Expected {pattern!r}; report: {report}\n{report_text(report)}')


def enable_log(doc, log_paths):
    # LOGFILEPATH may legitimately be empty or refer to a missing directory.
    # Never replace it: some CAD releases reject restoring those old values.
    try:
        retry(lambda: doc.SetVariable('LOGFILEMODE', 1), 5)
        path = str(retry(lambda: doc.GetVariable('LOGFILENAME'), 5))
        if path:
            log_paths.add(path)
    except Exception as exc:
        print(f'Native command log unavailable at the configured path: {exc}', flush=True)


def phase(app, name, report, root, log_paths):
    doc = retry(lambda: app.Documents.Add(), 60)
    retry(doc.Activate)
    enable_log(doc, log_paths)
    command = (
        f'(progn (load {lisp_string(root / "lisps/VRAP.lsp")}) '
        f'(load {lisp_string(root / "tests/cad/vrap_regression.lsp")}) '
        f'(SVR:Prepare {lisp_string(name)} {lisp_string(report)}))\n'
    )
    # Do not retry SendCommand: a rejected/ambiguous response could still have
    # queued input, and repeating it would create a second fixture/viewport.
    doc.SendCommand(command)
    ready = wait_for(report, rf'^(FIXTURE_READY {name}|PHASE_DONE {name} failures=(\d+))$')
    if ready.group(2) is not None:
        return int(ready.group(2))
    second = '1020,2010' if name == 'METRES' else '1200,2100'
    inputs = f'VRAP\n_non\n1000,2000\n_non\n{second}\n'
    if name == 'CANCEL':
        # Empty getpoint response returns nil and runs VRAP's cancellation
        # cleanup. SendCommand does not reliably interpret control characters
        # as keyboard Escape in all supported CAD releases.
        inputs += '\n'
    else:
        inputs += '_non\n20,30\n'
    # This check is queued after the native command's three point responses;
    # no additional Enter or pause is supplied to advance VRAP.
    inputs += '(SVR:Check)\n'
    doc.SendCommand(inputs)
    result = wait_for(report, rf'^PHASE_DONE {name} failures=(\d+)$')
    return int(result.group(1))


def close_owned(app, process_handle, pid):
    """Close only the newly created PID, retaining its original process handle."""
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
            print(f'Closing owned scratch CAD process {pid} after graceful close failed.', flush=True)
            win32api.TerminateProcess(process_handle, 1)
            win32event.WaitForSingleObject(process_handle, 5000)
    finally:
        process_handle.Close()


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--progid', default='AutoCAD.Application.25')
    parser.add_argument('--cases', nargs='+', choices=('MM', 'METRES', 'ROTATED', 'CANCEL'),
                        default=('MM', 'METRES', 'ROTATED', 'CANCEL'))
    args = parser.parse_args()
    folder = Path(tempfile.mkdtemp(prefix='sincal-vrap-test-'))
    report = folder / 'report.txt'
    print(f'Report: {report}', flush=True)
    before = set(win32process.EnumProcesses())
    app = win32com.client.DispatchEx(args.progid)
    pid = retry(lambda: win32process.GetWindowThreadProcessId(app.HWND)[1], 60)
    if pid in before:
        raise RuntimeError('COM returned an existing CAD process; refusing to touch it.')
    process_handle = win32api.OpenProcess(
        win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, pid)
    originals = {}
    log_paths = set()
    failures = 0
    try:
        retry(lambda: setattr(app, 'Visible', False))
        baseline_doc = retry(lambda: app.Documents.Add(), 60)
        for key in ('ANNOAUTOSCALE', 'LOGFILEPATH', 'LOGFILEMODE'):
            originals[key] = retry(lambda key=key: baseline_doc.GetVariable(key))
        snapshot = folder / 'original-settings.json'
        snapshot.write_text(json.dumps({'progid': args.progid, 'pid': pid,
            'variables': originals}, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'Original settings: {snapshot}', flush=True)
        enable_log(baseline_doc, log_paths)
        for name in args.cases:
            print(f'Running {name} in owned PID {pid}', flush=True)
            failures += phase(app, name, report, root, log_paths)
        summary = f'DONE failures={failures} phases={len(args.cases)}'
        with report.open('a', encoding='utf-8') as stream:
            stream.write(summary + '\n')
        print(report_text(report), flush=True)
        return 0 if failures == 0 else 1
    finally:
        # Restore changed settings even if a fixture or command failed.
        # LOGFILEPATH was only recorded, never modified. Close this run's log
        # before restoring its mode and shutting down the disposable process.
        if 'LOGFILEMODE' in originals:
            try:
                retry(lambda: app.ActiveDocument.SetVariable('LOGFILEMODE', 0), 5)
            except Exception as exc:
                print(f'Could not close scratch log: {exc}', flush=True)
        for key in ('ANNOAUTOSCALE', 'LOGFILEMODE'):
            if key in originals:
                try:
                    retry(lambda key=key: app.ActiveDocument.SetVariable(key, originals[key]), 5)
                except Exception as exc:
                    print(f'Could not restore scratch {key}: {exc}', flush=True)
        close_owned(app, process_handle, pid)
        print(f'Native log copies: {folder}', flush=True)
        for index, path in enumerate(sorted(log_paths), 1):
            try:
                source = Path(path)
                if source.is_file():
                    destination = folder / f'{index:02d}-{source.name}'
                    shutil.copy2(source, destination)
                    print(f'Native log: {destination}', flush=True)
                else:
                    print(f'Native log not created at configured path: {path}', flush=True)
            except OSError as exc:
                print(f'Could not copy native log {path}: {exc}', flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
