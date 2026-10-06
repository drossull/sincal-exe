import json
from pathlib import Path
import subprocess
import os
import pytest
from pypdf import PdfReader, PdfWriter
from sincal.cad.batch import validate_selection, drawing_available
from sincal.cad.pdf_merge import merge_request


def test_selection_is_exact_and_never_expands_folder(tmp_path):
    a, b = tmp_path/'a.dwg', tmp_path/'b.dwg'
    a.touch(); b.touch()
    assert validate_selection({'operation':'ze','files':[str(a),str(a)]})['files'] == [str(a)]
    for files in ([], [str(tmp_path)], ['relative.dwg']):
        with pytest.raises(ValueError): validate_selection({'operation':'ze','files':files})
    a.with_suffix('.dwl').touch()
    with pytest.raises(ValueError): drawing_available(a)


def test_pdf_name_multipage_and_no_unapproved_overwrite(tmp_path):
    pages=[]
    for i in range(2):
        path=tmp_path/f'page{i}.pdf'
        writer=PdfWriter();writer.add_blank_page(width=100+i,height=100);writer.write(path);writer.close();pages.append(str(path))
    target=tmp_path/'Plano con espacios - Rev. G.pdf'
    request=tmp_path/'merge.json'
    request.write_text(json.dumps({'target':str(target),'pages':pages,'overwrite':False}))
    merge_request(request)
    assert len(PdfReader(target).pages)==2
    before=target.read_bytes()
    with pytest.raises(FileExistsError):merge_request(request)
    assert target.read_bytes()==before


@pytest.mark.skipif(os.name != 'nt', reason='PowerShell selector')
def test_cmd_default_and_explicit_selection(tmp_path):
    for name in ('a.dwg','b.dwg'): (tmp_path/name).touch()
    manifest=tmp_path/'selection.json'
    manifest.write_text(json.dumps({'schema':1,'files':[str(tmp_path/'a.dwg')]}))
    helper=Path('scripts/SINCAL_SELECTION.ps1').resolve()
    def run(argument):
        script=f". '{helper}'; @(Get-SincalDrawingSelection {argument}) | ForEach-Object Name"
        return subprocess.check_output(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',script],cwd=tmp_path,text=True).splitlines()
    assert sorted(run(''))==['a.dwg','b.dwg']
    assert run(f"'{manifest}'")==['a.dwg']
