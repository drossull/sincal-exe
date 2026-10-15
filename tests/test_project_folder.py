import json
from pathlib import Path
import subprocess

import pytest
from sincal.web.files import Files


def test_catalog_classifies_recursively_without_opening_documents(tmp_path):
    folder=tmp_path/'Proyecto';folder.mkdir()
    nested=folder/'Informes';nested.mkdir()
    for name in ['S7.pdf','S8.pdf','mapa.kmz','plano.dwg','otro.dxf','memoria.xlsx','macro.xlsm','texto.docx']:
        (nested/name).write_bytes(b'not parsed or executed')
    (folder/'puente.json').write_text('{"tableros": []}',encoding='utf8')
    backup=folder/'SINCAL_Backups';backup.mkdir();(backup/'old.dwg').touch()
    files=Files();root=files.grant(folder,'folder')['id']
    catalog=files.project_catalog(root)
    entries={e['name']:e for e in catalog['entries']}
    assert set(entries['S7.pdf']['grants'])=={'report','memory_pdf'}
    assert set(entries['macro.xlsm']['grants'])=={'memory_excel'}
    assert entries['plano.dwg']['relative']==str(Path('Informes/plano.dwg'))
    assert 'old.dwg' not in entries and 'SINCAL_Backups' not in entries
    assert files.read_json(entries['puente.json']['grants']['session'])['value']=={'tableros':[]}
    assert files.project_catalog(root)==catalog  # refresh reuses grants
    with pytest.raises(ValueError):
        files.project_catalog(str(folder))
    with pytest.raises(ValueError):
        files.read_json(entries['plano.dwg']['grants']['dwg'])


def test_replaced_source_is_rejected(tmp_path):
    path=tmp_path/'data.json';path.write_text('[]')
    files=Files();key=files.grant(path,'session')['id']
    with pytest.raises(ValueError,match='objeto'):
        files.read_json(key)


@pytest.mark.skipif(__import__('os').name!='nt', reason='Windows junction safety')
def test_catalog_does_not_follow_junction(tmp_path):
    root=tmp_path/'root';outside=tmp_path/'outside';root.mkdir();outside.mkdir()
    (outside/'secret.json').write_text('{}')
    junction=root/'junction'
    subprocess.run(['cmd','/c','mklink','/J',str(junction),str(outside)],check=True,capture_output=True)
    try:
        files=Files();catalog=files.project_catalog(files.grant(root,'folder')['id'])
        assert len(catalog['entries'])==1
    finally:
        # Remove the junction itself, never recurse or touch its target.
        junction.rmdir()
