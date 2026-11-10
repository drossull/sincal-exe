"""Exercise ZET only in a newly owned CAD process with disposable drawings."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile

import pythoncom
import win32api
import win32com.client
import win32con
import win32process

from test_nivel_base_native import retry, close_owned


def point(x, y):
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (x, y, 0.0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--progid', default='ZWCAD.Application.2026')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    folder = Path(tempfile.mkdtemp(prefix='sincal-ze-native-'))
    print(f'Report: {folder}', flush=True)
    before = set(win32process.EnumProcesses())
    app = win32com.client.DispatchEx(args.progid)
    pid = retry(lambda: win32process.GetWindowThreadProcessId(app.HWND)[1], 30)
    if pid in before:
        raise RuntimeError('Refusing an existing CAD process; no drawings modified')
    handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, pid)
    try:
        retry(lambda: setattr(app, 'Visible', True))
        for _ in range(2):
            retry(lambda: app.Documents.Add(), 30)
        docs = list(app.Documents)
        expected = []
        saved = []
        for i, doc in enumerate(docs):
            retry(doc.Activate)
            retry(lambda: doc.SetVariable('TILEMODE', 0 if i == len(docs)-1 else 1))
            space = doc.PaperSpace if i == len(docs)-1 else doc.ModelSpace
            retry(lambda: space.AddLine(point(0, 0), point(100+i*20, 50)))
            retry(app.ZoomExtents)
            expected.append((doc.GetVariable('CTAB'), doc.GetVariable('VIEWCTR'),
                             doc.GetVariable('VIEWSIZE'), space.Count))
            retry(lambda: app.ZoomCenter(point(5000, 5000), 20000.0))
            # Leave one drawing unsaved and verify saved sources stay untouched.
            if i == 0:
                path = folder/'fixture.dwg'
                retry(lambda: doc.SaveAs(str(path)))
                saved.append((path, hashlib.sha256(path.read_bytes()).hexdigest()))
        origin = docs[0]
        retry(origin.Activate)
        hwnd = int(app.HWND)
        command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
                   '-ExecutionPolicy', 'Bypass', '-File', str(root/'scripts/ZE-TODOS.ps1'),
                   '-ProgId', args.progid, '-WindowHandle']
        wrong = subprocess.run(command+[str(hwnd+1), '-LogPath', str(folder/'wrong.log')],
                               capture_output=True, timeout=25)
        assert wrong.returncode != 0
        assert origin.GetVariable('VIEWSIZE') > 10000, 'Wrong instance was modified'
        result = subprocess.run(command+[str(hwnd), '-LogPath', str(folder/'result.log')],
                                capture_output=True, timeout=55)
        print((folder/'result.log').read_text(encoding='utf-8-sig'), flush=True)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        assert app.ActiveDocument.Name == origin.Name, 'Initial document not restored'
        for i, doc in enumerate(docs):
            retry(doc.Activate)
            tab, center, height, count = expected[i]
            assert doc.GetVariable('CTAB') == tab
            assert abs(doc.GetVariable('VIEWSIZE')-height) < 1e-5
            assert all(abs(a-b) < 1e-5 for a, b in zip(doc.GetVariable('VIEWCTR'), center))
            space = doc.PaperSpace if i == len(docs)-1 else doc.ModelSpace
            assert space.Count == count, 'Geometry changed'
        for path, digest in saved:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Drawing saved'
        print('PASS all open documents, paper/model space, unsaved drawing, original restored, no save, wrong instance rejected', flush=True)
    finally:
        close_owned(app, handle, pid)


if __name__ == '__main__':
    main()
