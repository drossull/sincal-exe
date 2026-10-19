"""Opt-in native Vs test. New private CAD instance and unsaved drawings only."""
import ctypes
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from test_stratigraphy_native import wait_for
import win32com.client
from sincal.prospecciones import read_report
from sincal.cad.prospecciones import build_profile_lisp,profile_scene
from sincal.web.cad_worker import command_with_completion,read_completion


def main():
    report=read_report(os.environ['SINCAL_TEST_CASCADA_VS'],ocr=False)
    folder=Path(tempfile.mkdtemp(prefix='vs-cad-',dir=ROOT/'tmp'))
    existing={int(p.ProcessId) for p in win32com.client.GetObject('winmgmts:').ExecQuery("SELECT ProcessId FROM Win32_Process WHERE Name='acad.exe'")}
    app=win32com.client.DispatchEx('AutoCAD.Application.25')
    pid=ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(wait_for(lambda:app.HWND),ctypes.byref(pid))
    assert pid.value not in existing
    print('OWN_PID',pid.value,'OUTPUT',folder,flush=True)
    doc=None
    try:
        wait_for(lambda:app.GetAcadState().IsQuiescent)
        app.Visible=False
        doc=wait_for(lambda:app.Documents.Add())
        wait_for(lambda:app.GetAcadState().IsQuiescent)
        doc.SetVariable('INSUNITS',6)
        try:doc.TextStyles.Item('RomanD')
        except Exception:
            style=doc.TextStyles.Add('RomanD');style.FontFile='romand.shx'
        for denominator in (200,50):
            name=f'1:{denominator} (m)'
            doc.SetVariable('CANNOSCALE',name)
            scale=doc.GetVariable('CANNOSCALEVALUE')
            for profile in report.profiles:
                key=f'{denominator}-{profile.key}'
                path=folder/f'{key}.lsp'
                path.write_text(build_profile_lisp(profile,True,scale,name),encoding='utf8')
                request=dict(command=f'(progn (load "{path.as_posix()}") (c:SINCAL-PROSPECCIONES))\n',
                    marker=str(folder/f'{key}.txt'),token=key,completion='profile-v1')
                known={g.Name for g in doc.Groups}
                doc.SendCommand(command_with_completion(request)+'0,0\n')
                wait_for(lambda:read_completion(request))
                objects=list(next(g for g in doc.Groups if g.Name not in known))
                texts=[o for o in objects if o.ObjectName=='AcDbMText']
                assert all(t.StyleName=='RomanD' and abs(t.Height*scale-2.5)<1e-7 for t in texts)
                assert not any('GEOIBERICA' in t.TextString or 'IT-SEIS' in t.TextString for t in texts)
                points=next(i['points'] for i in profile_scene(profile,True,scale) if i['kind']=='polyline')
                lines=[o for o in objects if o.ObjectName=='AcDbLine' and o.Color==5]
                assert len(lines)==len(points)-1
                for line,(a,b) in zip(lines,zip(points,points[1:])):
                    for native,point in zip((line.StartPoint,line.EndPoint),(a,b)):
                        assert abs(native[0]-point[0]/scale)<1e-6 and abs(native[1]+point[1]/scale)<1e-6
                assert abs(lines[0].StartPoint[1]-lines[-1].EndPoint[1]-35)<1e-6
                assert doc.GetVariable('CANNOSCALE')==name
                print('OK',profile.name,name,'35 m; paper text 2.5; metadata excluded',flush=True)
        doc.SetVariable('CANNOSCALE','1:200 (m)')
        before=doc.ModelSpace.Count
        stale=dict(request,marker=str(folder/'stale.txt'),token='stale')
        doc.SendCommand(command_with_completion(stale))
        wait_for(lambda:Path(stale['marker']).exists())
        try:read_completion(stale)
        except RuntimeError as e:assert 'escala anotativa' in str(e)
        else:raise AssertionError('Stale scale accepted')
        assert doc.ModelSpace.Count==before
        print('STALE_SCALE_NO_GEOMETRY_OK',flush=True)
    finally:
        try:
            if doc is not None:doc.Close(False)
            for extra in list(app.Documents):extra.Close(False)
            app.Quit()
        except Exception:pass


if __name__=='__main__':main()
