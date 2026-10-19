import json
from pathlib import Path
import subprocess
import os
import sys
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


def test_single_pdf_preserves_bytes_and_validates_before_replace(tmp_path):
    source = tmp_path/'source.pdf'
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(source)
    writer.close()
    target = tmp_path/'drawing.pdf'
    request = tmp_path/'merge.json'
    request.write_text(json.dumps({'target':str(target),'pages':[str(source)],'overwrite':True}))
    merge_request(request)
    assert target.read_bytes() == source.read_bytes()
    before = target.read_bytes()
    for bad in (b'', b'not a PDF', before.split(b'%%EOF')[0]):
        source.write_bytes(bad)
        with pytest.raises(Exception):
            merge_request(request)
        assert target.read_bytes() == before
        assert not list(tmp_path.glob('*.sincal.pdf'))


def test_output_validation_failure_keeps_previous_pdf(tmp_path, monkeypatch):
    from sincal.cad import pdf_merge
    source = tmp_path/'source.pdf'
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(source)
    writer.close()
    target = tmp_path/'drawing.pdf'
    target.write_bytes(b'previous PDF must survive')
    request = tmp_path/'merge.json'
    request.write_text(json.dumps({'target':str(target),'pages':[str(source)],'overwrite':True}))
    original = pdf_merge.validate_pdf
    def reject_output(path, expected_pages=None):
        if expected_pages is not None:
            raise ValueError('simulated renderer failure')
        return original(path)
    monkeypatch.setattr(pdf_merge, 'validate_pdf', reject_output)
    with pytest.raises(ValueError, match='renderer failure'):
        merge_request(request)
    assert target.read_bytes() == b'previous PDF must survive'
    assert not list(tmp_path.glob('*.sincal.pdf'))


def test_pdf_cli_reports_validation_result(tmp_path):
    source = tmp_path/'source.pdf'
    target = tmp_path/'drawing.pdf'
    request = tmp_path/'merge.json'
    request.write_text(json.dumps({'target':str(target),'pages':[str(source)]}))
    source.write_bytes(b'broken')
    command = [sys.executable, str(Path(__file__).resolve().parents[1]/'desktop_main.py'),
               '--merge-pdfs', str(request)]
    result = subprocess.run(command, capture_output=True, timeout=30)
    report = json.loads(request.with_suffix('.result.json').read_text(encoding='utf-8'))
    assert result.returncode == 1
    assert report['ok'] is False and 'Cabecera' in report['error']
    assert not target.exists()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(source)
    writer.close()
    result = subprocess.run(command, capture_output=True, timeout=30)
    assert result.returncode == 0
    assert json.loads(request.with_suffix('.result.json').read_text()) == {'ok':True}
    assert target.read_bytes() == source.read_bytes()


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
