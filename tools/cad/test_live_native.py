"""Explicit opt-in: replaces clipboard, private CAD instance and unsaved test DWGs."""
import ctypes
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from sincal.web.cad_worker import execute, execute_all
from sincal.web.cad_readiness import read_when_ready, wait_for_document


def main():
    import win32com.client
    folder=Path(tempfile.mkdtemp(prefix='SINCAL-live-qa-'))
    print('OUTPUT',folder,flush=True)
    existing={int(p.ProcessId) for p in win32com.client.GetObject('winmgmts:').ExecQuery("SELECT ProcessId FROM Win32_Process WHERE Name='acad.exe'")}
    app=win32com.client.DispatchEx('AutoCAD.Application.25')
    pid=ctypes.c_ulong()
    hwnd=read_when_ready(lambda: app.HWND,timeout=60)
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    assert pid.value and pid.value not in existing
    print('OWN_PID',pid.value,flush=True)
    owned=[]
    try:
        app.Visible=False
        # Wait for initial CAD startup before creating our disposable documents.
        deadline=time.monotonic()+60
        while not read_when_ready(lambda: app.GetAcadState().IsQuiescent):
            if time.monotonic()>deadline:raise TimeoutError('CAD startup')
            time.sleep(.25)
        for _ in range(3):
            doc=app.Documents.Add();owned.append(doc)
            wait_for_document(app,{'name':str(doc.Name),'path':str(doc.FullName)})
        def expected():
            doc=read_when_ready(lambda: app.ActiveDocument)
            return {'instance':str(app.HWND),'status':'ready','active':{'name':str(doc.Name),'path':str(doc.FullName)},
                    'documents':[{'name':str(app.Documents.Item(i).Name),'path':str(app.Documents.Item(i).FullName)} for i in range(app.Documents.Count)]}
        counter=0
        def request(command,completion=None):
            nonlocal counter
            counter+=1
            return dict(command=command,expected=expected(),marker=str(folder/f'done-{counter}.txt'),token=f'test-{counter}',completion=completion,timeout=45,clipboard=completion=='live-v1')
        with patch('sincal.web.cad_worker.active_application',return_value=app):
            seed='(progn (setvar "TILEMODE" 1) (entmakex \'((0 . "LINE") (10 10.0 20.0 0.0) (11 20.0 20.0 0.0))) (command "_.COPYBASE" "_non" \'(0.0 0.0 0.0) (ssget "_X" \'((0 . "LINE"))) ""))\n'
            execute(request(seed))
            command=f'(progn (load "{(ROOT/"lisps/P0.lsp").as_posix()}") (c:P0))\n'
            before={str(d.Name):d.ModelSpace.Count for d in owned}
            # Test the exact multi-drawing worker with AutoCAD activation waits.
            result=execute_all(request(command,'live-v1'))
            assert len(result['documents'])==app.Documents.Count
            for doc in owned:
                assert doc.ModelSpace.Count==before[str(doc.Name)]+1
                block=doc.ModelSpace.Item(doc.ModelSpace.Count-1)
                assert block.ObjectName=='AcDbBlockReference'
                assert all(abs(x)<1e-8 for x in block.InsertionPoint)
            # Shift UCS and verify P0 still inserts at the WCS origin.
            execute(request('(progn (setvar "CMDECHO" 0) (command "_.UCS" "_Origin" \'(100.0 200.0 0.0)))\n'))
            result=execute(request(command,'live-v1'))
            doc=app.ActiveDocument
            block=doc.ModelSpace.Item(doc.ModelSpace.Count-1)
            assert all(abs(x)<1e-8 for x in block.InsertionPoint)
            assert doc.GetVariable('CMDECHO')==0
            # Empty text clipboard must not be reported as a successful paste.
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard();win32clipboard.SetClipboardText('SINCAL P0 test')
            finally:win32clipboard.CloseClipboard()
            count=doc.ModelSpace.Count
            try:execute(request(command,'live-v1'))
            except ValueError as error:
                assert 'portapapeles' in str(error)
            else:raise AssertionError('P0 accepted a non-CAD clipboard')
            assert doc.ModelSpace.Count==count and doc.GetVariable('CMDECHO')==0
            print('PASS: multi-document P0, WCS origin, CMDECHO restoration, invalid clipboard failure',flush=True)
            (folder/'result.json').write_text(json.dumps({'ok':True,'documents':len(owned)}))
    finally:
        for doc in owned:
            try:doc.Close(False)
            except Exception:pass
        try:app.Quit()
        except Exception:pass


if __name__=='__main__':main()
