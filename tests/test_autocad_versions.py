"""Version routing without starting CAD or touching user drawings."""
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from sincal import runtime
from sincal.cad import dwgprops, engine
from sincal.web import cad_probe, cad_worker


@pytest.mark.parametrize('frozen', [False, True])
def test_2026_uses_bundled_2025_connector_without_changing_other_versions(tmp_path, monkeypatch, frozen):
    monkeypatch.setattr(runtime, 'RUTA_INSTALACION', str(tmp_path))
    monkeypatch.setattr(sys, 'frozen', frozen, raising=False)
    base = tmp_path / 'native/dwgprops' if frozen else tmp_path / 'src/Sincal.DwgProps/bin'
    for year in (2025, 2027):
        path = base / str(year) / 'Sincal.DwgProps.dll'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'connector fixture; never executed')
    assert dwgprops.connector_path(2025) == base / '2025/Sincal.DwgProps.dll'
    assert dwgprops.connector_path(2026) == base / '2025/Sincal.DwgProps.dll'
    assert dwgprops.connector_path(2027) == base / '2027/Sincal.DwgProps.dll'
    assert not dwgprops.connector_path(2024).is_file()
    dedicated = base / '2026/Sincal.DwgProps.dll'
    dedicated.parent.mkdir()
    dedicated.write_bytes(b'dedicated connector fixture')
    assert dwgprops.connector_path(2026) == dedicated


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows CAD discovery')
def test_2026_is_offered_for_properties_and_revisions_with_only_2025_connector(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'RUTA_INSTALACION', str(tmp_path))
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    cad = tmp_path / 'Autodesk/AutoCAD 2026/accoreconsole.exe'
    cad.parent.mkdir(parents=True)
    cad.write_bytes(b'engine fixture; never executed')
    detected = engine.discover_cad_engines([str(tmp_path / 'Autodesk')])
    assert len(detected) == 1 and detected[0].year == 2026
    monkeypatch.setattr(engine, 'discover_cad_engines', lambda: detected)
    assert dwgprops.autocad_engines() == []
    connector = tmp_path / 'native/dwgprops/2025/Sincal.DwgProps.dll'
    connector.parent.mkdir(parents=True)
    connector.write_bytes(b'connector fixture; never executed')
    assert [item['year'] for item in dwgprops.autocad_engines()] == [2026]
    connector.unlink()
    assert dwgprops.autocad_engines() == []


@pytest.mark.parametrize(('family', 'identifier', 'version'), [
    ('AutoCAD', 'AutoCAD.Application.25', '25.0'),
    ('AutoCAD', 'AutoCAD.Application.25.1', '25.1'),
    ('AutoCAD', 'AutoCAD.Application.26', '26.0'),
    ('ZWCAD', 'ZWCAD.Application.26', '26'),
])
def test_probe_and_live_worker_find_version_when_generic_alias_is_unavailable(monkeypatch, family, identifier, version):
    app = Mock(Name=family, Version=version, HWND=123)
    doc = Mock(Name='test.dwg', FullName='C:/test.dwg')
    doc.GetVariable.side_effect = lambda name: {
        'CMDACTIVE': 0, 'INSUNITS': 6, 'CTAB': 'Model',
        'CANNOSCALE': '1:100', 'CANNOSCALEVALUE': .01,
    }[name]
    app.ActiveDocument = doc
    app.Documents.Count = 1
    app.Documents.Item.return_value = doc
    def get_active(prog_id):
        if prog_id == identifier:
            return app
        raise OSError('This alias does not expose the running instance')
    client = ModuleType('win32com.client')
    client.GetActiveObject = Mock(side_effect=get_active)
    client.GetObject = Mock()
    client.GetObject.return_value.ExecQuery.return_value = [
        SimpleNamespace(Name='acad.exe' if family == 'AutoCAD' else 'zwcad.exe')]
    package = ModuleType('win32com')
    package.client = client
    monkeypatch.setitem(sys.modules, 'win32com', package)
    monkeypatch.setitem(sys.modules, 'win32com.client', client)
    monkeypatch.setitem(sys.modules, 'pythoncom', SimpleNamespace(CoInitialize=Mock(), CoUninitialize=Mock()))
    result = cad_probe.probe()
    assert result['status'] == 'ready' and result['version'] == version
    assert cad_worker.active_application() is app
    doc.SendCommand.assert_not_called()
    doc.Save.assert_not_called()
