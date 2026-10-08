"""Opt-in native regression: private AutoCAD instance + disposable drawing only.

Run directly with Python on Windows. Does not register, install, save or edit
user drawings. Tests the exact completion expression used by the web worker.
"""
import ctypes
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import win32com.client
from sincal.stratigraphy import Borehole, Interval, Spt, VsBand
from sincal.stratigraphy_hatches import HATCHES
from sincal.cad.stratigraphy import build_stratigraphy_lisp
from sincal.web.cad_worker import command_with_completion, read_completion


def wait_for(callback, seconds=90):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        try:
            result = callback()
            if result:
                return result
        except Exception:
            pass
        time.sleep(.25)
    raise TimeoutError('Private CAD test did not reach expected state')


def main():
    existing = {int(p.ProcessId) for p in win32com.client.GetObject('winmgmts:').ExecQuery("SELECT ProcessId FROM Win32_Process WHERE Name='acad.exe'")}
    folder = Path(tempfile.mkdtemp(prefix='stratigraphy-cad-', dir=ROOT/'tmp'))
    app = win32com.client.DispatchEx('AutoCAD.Application.25')
    process_id = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(app.HWND, ctypes.byref(process_id))
    assert process_id.value not in existing, 'Refuse to use an existing CAD instance'
    print('OWN_PID', process_id.value, 'OUTPUT', folder, flush=True)
    doc = None
    try:
        wait_for(lambda: app.GetAcadState().IsQuiescent)
        app.Visible = False
        doc = app.Documents.Add()
        wait_for(lambda: app.GetAcadState().IsQuiescent)
        doc.SetVariable('INSUNITS', 6)
        doc.SetVariable('CANNOSCALE', '1:100 (m)')
        doc.SetVariable('LOGFILEMODE', 1)
        hole = Borehole('test','QA', [Interval(str(i),str(i+1),'1','.6','60',m,1,m) for i,m in enumerate(HATCHES)],
            [Spt(1,'.5','.95','.45','.2','5','10','12','22',1)], reviewed=True,
            vs_bands=[VsBand('0','1.49','185','185',19,'Arreglo 3-2',117),
                      VsBand('1.49','3.59','608','676',19,'Arreglo 3-2',117),
                      VsBand('3.59','9.10','744','786',19,'Arreglo 3-2',117),
                      VsBand('9.10','30','854','896',19,'Arreglo 3-2',117)])
        source = build_stratigraphy_lisp(hole, ROOT/'masters/FORMATOS ANOTATIVOS ACAD_2025.dwg')
        path = folder/'draw.lsp'
        path.write_text(source, encoding='utf-8')
        request = dict(command=f'(progn (load "{path.as_posix()}") (c:SINCAL-ESTRATIGRAFIA))\n',
                       marker=str(folder/'done.txt'),token='qa-success',completion='stratigraphy-v1')
        print('LOG', doc.GetVariable('LOGFILENAME'), flush=True)
        # Only point coordinates follow the complete expression. The completion
        # message stays inside the command, not in getpoint's input stream.
        doc.SendCommand(command_with_completion(request)+'0,0\n')
        result = wait_for(lambda: read_completion(request))
        groups = [g for g in doc.Groups if g.Name.startswith('SINCAL_ESTRAT_')]
        assert len(groups) == 1
        entities = list(groups[0])
        texts = [o for o in entities if o.ObjectName == 'AcDbMText']
        hatches = [o for o in entities if o.ObjectName == 'AcDbHatch']
        assert {h.PatternName for h in hatches} == {v['pattern'] for v in HATCHES.values()}
        assert all(h.Area > 0 for h in hatches)
        assert sum(o.ObjectName=='AcDbSolid' for o in entities) == 8
        scale = doc.GetVariable('CANNOSCALEVALUE')
        assert all(t.StyleName=='RomanD' and abs(t.Height*scale-2.5)<1e-8 for t in texts)
        assert any('608 - 676' in t.TextString for t in texts)
        assert any(r'N{\H0.7x;\S^SPT;}' in t.TextString for t in texts)
        assert all(o.Color==1 for o in entities if o.ObjectName=='AcDbSolid')
        assert all(o.Color in (1,5,8) for o in entities if o.ObjectName=='AcDbLine')
        assert any('VS = 608 - 676 m/s' in t.TextString for t in texts)
        log = Path(doc.GetVariable('LOGFILENAME')).read_text(errors='replace')
        assert "Can't reenter LISP" not in log and 'Invalid point' not in log
        print('SUCCESS', json.dumps(result), len(entities), 'entities', flush=True)
        before = doc.ModelSpace.Count
        bad = folder/'missing.lsp'
        bad.write_text(source.replace('"ANSI31"', '"SINCAL_MISSING_TEST"'), encoding='utf-8')
        failed = dict(request, command=f'(progn (load "{bad.as_posix()}") (c:SINCAL-ESTRATIGRAFIA))\n',
                      marker=str(folder/'error.txt'),token='qa-failure')
        doc.SendCommand(command_with_completion(failed))
        wait_for(lambda: Path(failed['marker']).exists())
        try:
            read_completion(failed)
        except RuntimeError as error:
            assert 'Falta hatch en master: SINCAL_MISSING_TEST' in str(error), str(error)
        else:
            raise AssertionError('Missing hatch was reported as success')
        assert doc.ModelSpace.Count == before
        print('MISSING_HATCH_FAILS_BEFORE_DRAWING_OK', flush=True)
        cancelled = dict(request, marker=str(folder/'cancelled.txt'),token='qa-cancel')
        doc.SendCommand(command_with_completion(cancelled)+'\n')
        wait_for(lambda: Path(cancelled['marker']).exists())
        assert Path(cancelled['marker']).read_text().splitlines()[1] == 'cancelled'
        assert doc.ModelSpace.Count == before
        print('CANCEL_WITHOUT_GEOMETRY_OK', flush=True)
        doc.SaveAs(str(folder/'qa.dxf'), 65)
        print('DXF', folder/'qa.dxf', flush=True)
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        try:
            if app.Documents.Count == 0:
                app.Quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
