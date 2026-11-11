"""Native revision-editor checks in an owned, hidden CAD process; no screenshots.

Build the plugin with RevisionGripTests=true, then provide its --dll path.
Only temporary fixture drawings are opened or changed. No SECURELOAD changes.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import tempfile
import threading
import time

import win32api
import win32com.client
import win32con
import win32process

from test_nivel_base_native import close_owned, retry


def wait_report(path, marker, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
        if '\nFAIL ' in '\n' + text:
            raise AssertionError(text)
        if marker in text:
            return text
        time.sleep(.25)
    raise TimeoutError(f'Native test did not report {marker}: {path}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--progid', required=True)
    parser.add_argument('--dll', type=Path, required=True)
    parser.add_argument('--master', type=Path)
    parser.add_argument('--suite', choices=('revisions', 'properties'), default='revisions')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    master = args.master or root / 'masters/FORMATOS ANOTATIVOS ACAD_2025.dwg'
    dll = args.dll.resolve(strict=True)
    master_digest = hashlib.sha256(master.read_bytes()).hexdigest()
    folder = Path(tempfile.mkdtemp(prefix='sincal-revision-grip-native-'))
    report = folder / 'native-result.txt'
    shutil.copy2(master, folder / 'seed.dwg')
    print(f'Report: {folder}', flush=True)
    previous_pids = set(win32process.EnumProcesses())
    app = win32com.client.DispatchEx(args.progid)
    pid = retry(lambda: win32process.GetWindowThreadProcessId(app.HWND)[1], 60)
    if pid in previous_pids:
        raise RuntimeError('Refusing to use an existing CAD process; nothing was changed')
    print(f'Owned {args.progid} process: {pid}', flush=True)
    handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, pid)
    def timed_out():
        print(f'Timeout: terminating owned scratch CAD process {pid}', flush=True)
        try:
            win32api.TerminateProcess(handle, 1)
        except Exception:
            pass
    watchdog = threading.Timer(240, timed_out)
    watchdog.daemon = True
    watchdog.start()
    try:
        retry(lambda: setattr(app, 'Visible', False))
        seed = retry(lambda: app.Documents.Open(str(folder / 'seed.dwg')), 60)
        # Commands are submitted once; retries after an ambiguous COM error can duplicate mutations.
        fixture_command = 'SINCAL_PROPS_FIXTURES' if args.suite == 'properties' else 'SINCAL_REV_FIXTURES'
        seed.SendCommand(f'_.NETLOAD\n"{dll.as_posix()}"\n'
                         f'(progn (setq f (open "{report.as_posix()}" "a")) '
                         f'(write-line (if (getcname "{fixture_command}") "PLUGIN_LOADED" '
                         '"FAIL NETLOAD: native test commands unavailable; check the TEST assembly and trust path") f) (close f) (princ))\n')
        wait_report(report, 'PLUGIN_LOADED')
        seed.SendCommand(fixture_command + '\n')
        wait_report(report, 'FIXTURES_READY')
        documents = {}
        hashes = {}
        names = ('source', 'target', 'omitted', 'fault') + (('readonly',) if args.suite == 'properties' else ())
        for name in names:
            print(f'Opening {name}.dwg', flush=True)
            path = folder / (name + '.dwg')
            hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
            documents[name] = retry(lambda path=path, name=name: app.Documents.Open(str(path), name == 'readonly'), 60)
        source = documents['source']
        retry(source.Activate)
        print('Running native checks', flush=True)
        source.SendCommand('SINCAL_PROPS_SMOKE\n' if args.suite == 'properties' else 'SINCAL_REV_SMOKE\n')
        print(wait_report(report, 'PROPS_SMOKE_DONE' if args.suite == 'properties' else 'SMOKE_DONE'), flush=True)
        retry(source.Activate)
        loader = root / 'lisps/REV-EDIT.lsp'
        with tempfile.NamedTemporaryFile(dir=dll.parent, prefix='Sincal.RevisionGrip.TEST.', suffix='.lsp', delete=False) as temporary:
            temporary.write(loader.read_bytes())
            trusted_loader = Path(temporary.name)
        try:
            source.SendCommand(f'(progn (load "{trusted_loader.as_posix()}") '
                               f'(setq f (open "{report.as_posix()}" "a")) '
                               '(write-line (if (SRG:Load nil) "LOADER_DONE" "FAIL LOADER") f) (close f) (princ))\n')
            wait_report(report, 'LOADER_DONE')
        finally:
            trusted_loader.unlink(missing_ok=True)
        if args.suite == 'properties':
            source.SendCommand('SINCAL_PROPS_DIALOG_SMOKE\n')
            wait_report(report, 'PROPS_DIALOG_DONE')
        else:
            source.SendCommand('SINCAL_REV_DIALOG_SMOKE\n')
            wait_report(report, 'DIALOG_DONE')
            source.SendCommand('SINCAL_REV_WRAPPER_SMOKE\n')
            wait_report(report, 'WRAPPER_DONE')
            # ZWCAD records even read-only AutoLISP expressions in undo history.
            # Inspect through COM so no intervening Lisp command consumes the circle's U.
            entity_count = retry(lambda: source.ModelSpace.Count)
            source.SendCommand('_.CIRCLE\n_non\n10000,10000,0\n1\n')
            assert retry(lambda: source.ModelSpace.Count) == entity_count + 1, 'Native circle was not created'
            source.SendCommand('_.U\n')
            assert retry(lambda: source.ModelSpace.Count) == entity_count, 'Native circle undo failed'
            source.SendCommand('_.REDO\n')
            assert retry(lambda: source.ModelSpace.Count) == entity_count + 1, 'Native circle redo failed'
            with report.open('a', encoding='utf-8') as output:
                output.write('PASS native circle undo and redo\n')
            for name in ('source', 'target'):
                document = documents[name]
                retry(document.Activate)
                document.SendCommand('_.U\n_.REGEN\nSINCAL_REV_CHECK_UNDO\n')
                wait_report(report, f'REGEN_DONE {name}.dwg')
                wait_report(report, f'UNDO_DONE {name}.dwg')
        for path, digest in hashes.items():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Drawing saved unexpectedly: {path}'
        assert hashlib.sha256(master.read_bytes()).hexdigest() == master_digest, 'Source master changed'
        print(report.read_text(encoding='utf-8-sig'), flush=True)
        print(f'PASS native {args.suite}, dialog, no automatic save, source master unchanged', flush=True)
    finally:
        try:
            close_owned(app, handle, pid)
        finally:
            watchdog.cancel()


if __name__ == '__main__':
    main()
