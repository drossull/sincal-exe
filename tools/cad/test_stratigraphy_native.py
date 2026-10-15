"""Opt-in native regression: private AutoCAD instance + disposable drawing only.

Run directly with Python on Windows. Does not register, install, save or edit
user drawings. Tests the exact completion expression used by the web worker.
"""
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import win32com.client
from sincal.stratigraphy import Borehole, Interval, Spt, VsBand
from sincal.stratigraphy_hatches import HATCHES
from sincal.cad.stratigraphy import build_stratigraphy_lisp, stratigraphy_scene
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
    ctypes.windll.user32.GetWindowThreadProcessId(wait_for(lambda: app.HWND), ctypes.byref(process_id))
    assert process_id.value not in existing, 'Refuse to use an existing CAD instance'
    print('OWN_PID', process_id.value, 'OUTPUT', folder, flush=True)
    doc = None
    try:
        wait_for(lambda: app.GetAcadState().IsQuiescent)
        app.Visible = False
        doc = wait_for(lambda: app.Documents.Add())
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
        if os.environ.get('SINCAL_TEST_STRATIGRAPHY_PDF'):
            from sincal.stratigraphy import read_report
            hole = read_report(os.environ['SINCAL_TEST_STRATIGRAPHY_PDF']).boreholes[0]
            assert not hole.errors(), hole.errors()
            hole.reviewed = True
            hole.reviewed_format = hole.drawing_format
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
        expected_patterns = {HATCHES[m]['pattern'] for r in hole.strata for m in [r.material,*r.inclusions]}
        assert {h.PatternName for h in hatches} == expected_patterns
        assert all(h.Area > 0 for h in hatches)
        assert sum(o.ObjectName=='AcDbSolid' for o in entities) == 2*len(hole.vs_bands)
        scale = doc.GetVariable('CANNOSCALEVALUE')
        assert all(t.StyleName=='RomanD' and abs(t.Height*scale-2.5)<1e-8 for t in texts)
        if hole.vs_bands:
            assert any('608 - 676' in t.TextString for t in texts)
        assert any(r'N{\H0.7x;\S^SPT;}' in t.TextString for t in texts)
        assert all(o.Color==1 for o in entities if o.ObjectName=='AcDbSolid')
        assert all(o.Color in (1,5,8) for o in entities if o.ObjectName=='AcDbLine')
        expected_blue=[i for i in stratigraphy_scene(hole)['items'] if i['kind']=='line' and i['color']==5]
        actual_blue=[o for o in entities if o.ObjectName=='AcDbLine' and o.Color==5]
        assert len(actual_blue)==len(expected_blue)
        for actual,expected in zip(actual_blue,expected_blue):
            for native,point in zip((actual.StartPoint,actual.EndPoint),expected['points']):
                assert abs(native[0]-point[0]/scale)<1e-6 and abs(native[1]+point[1]/scale)<1e-6
        print('PREVIEW_CAD_BLUE_GEOMETRY_MATCH',len(actual_blue),flush=True)
        if hole.vs_bands:
            assert any('VS = 608 - 676 m/s' in t.TextString for t in texts)
        log = Path(doc.GetVariable('LOGFILENAME')).read_text(errors='replace')
        assert "Can't reenter LISP" not in log and 'Invalid point' not in log
        print('SUCCESS', json.dumps(result), len(entities), 'entities', flush=True)
        # The same report must keep true model depths while paper symbols scale.
        for denominator in (200, 50):
            name = f'1:{denominator} (m)'
            doc.SetVariable('CANNOSCALE', name)
            ratio = doc.GetVariable('CANNOSCALEVALUE')
            scaled_scene = stratigraphy_scene(hole, annotation_scale=ratio)
            scaled_path = folder/f'scale-{denominator}.lsp'
            scaled_path.write_text(build_stratigraphy_lisp(hole, ROOT/'masters/FORMATOS ANOTATIVOS ACAD_2025.dwg',
                annotation_scale=ratio, scale_name=name), encoding='utf-8')
            known = {g.Name for g in doc.Groups}
            scaled_request = dict(request, command=f'(progn (load "{scaled_path.as_posix()}") (c:SINCAL-ESTRATIGRAFIA))\n',
                                  marker=str(folder/f'scale-{denominator}.txt'), token=f'scale-{denominator}')
            doc.SendCommand(command_with_completion(scaled_request)+'0,0\n')
            wait_for(lambda: read_completion(scaled_request))
            added = next(g for g in doc.Groups if g.Name not in known)
            native = list(added)
            assert doc.GetVariable('CANNOSCALE') == name
            assert all(abs(o.Height*ratio-2.5)<1e-8 for o in native if o.ObjectName=='AcDbMText')
            blue = [o for o in native if o.ObjectName=='AcDbLine' and o.Color==5]
            expected = [i for i in scaled_scene['items'] if i['kind']=='line' and i['color']==5]
            for obj,item in zip(blue,expected):
                for point,xy in zip((obj.StartPoint,obj.EndPoint),item['points']):
                    assert abs(point[0]-xy[0]/ratio)<1e-6 and abs(point[1]+xy[1]/ratio)<1e-6
            # Deepest point on a soil-column outline is the actual soil depth.
            outlines = [o for o in native if o.ObjectName=='AcDbLine' and o.Color==1
                        and abs(o.StartPoint[0]-12/ratio)<1e-7 and abs(o.EndPoint[0]-12/ratio)<1e-7]
            from sincal.prospecciones import number
            assert abs(min(o.EndPoint[1] for o in outlines)+27/ratio+max(number(r.end) for r in hole.strata))<1e-6
            scaled_hatches = [o for o in native if o.ObjectName=='AcDbHatch']
            assert all(o.Area>0 for o in scaled_hatches)
            for previous,current in zip(hatches,scaled_hatches):
                assert abs(previous.PatternScale*scale-current.PatternScale*ratio)<1e-6
            print('REAL_DEPTH_AND_PAPER_SYMBOLS_OK',name,flush=True)
        # A stale confirmed scale must abort before creating any geometry.
        count = doc.ModelSpace.Count
        stale = dict(request, marker=str(folder/'stale.txt'), token='stale-scale')
        doc.SendCommand(command_with_completion(stale))  # original source expects 1:100
        wait_for(lambda: Path(stale['marker']).exists())
        try:
            read_completion(stale)
        except RuntimeError as error:
            assert 'escala anotativa' in str(error), str(error)
        else:
            raise AssertionError('Stale scale was accepted')
        assert doc.ModelSpace.Count == count
        doc.SetVariable('CANNOSCALE','1:100 (m)')
        print('STALE_SCALE_ABORTS_BEFORE_DRAWING_OK',flush=True)
        before = doc.ModelSpace.Count
        bad = folder/'missing.lsp'
        bad.write_text(source.replace('"'+sorted(expected_patterns)[0]+'"', '"SINCAL_MISSING_TEST"'), encoding='utf-8')
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
            # This PID was proven private before entering the try block.
            for extra in list(app.Documents):
                extra.Close(False)
            app.Quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
