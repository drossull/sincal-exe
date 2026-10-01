from unittest.mock import Mock, patch
import subprocess
import pytest
from sincal.web.cad_probe import inspect_application
from sincal.web.cad_connection import connection_status


def test_probe_reads_active_drawing_without_commands():
    app = Mock()
    app.Name='AutoCAD'
    app.Version='25.0'
    doc = Mock()
    doc.Name='prueba.dwg'
    doc.FullName='C:/prueba.dwg'
    doc.GetVariable.side_effect=lambda name: {'CMDACTIVE':0,'INSUNITS':6,'CTAB':'Model'}[name]
    app.ActiveDocument=doc
    app.Documents.Count=1
    app.Documents.Item.return_value=doc
    result=inspect_application(app)
    assert result['status']=='ready'
    assert result['active']['insunits']==6
    doc.SendCommand.assert_not_called()
    doc.Save.assert_not_called()
    app.Quit.assert_not_called()


def test_no_document():
    app=Mock()
    app.Documents.Count=0
    assert inspect_application(app)['status']=='no_document'


@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows connector')
def test_timeout_only_targets_probe():
    with patch('sincal.web.cad_connection.subprocess.run', side_effect=subprocess.TimeoutExpired('probe',15)) as run:
        assert connection_status()['status']=='timeout'
        assert run.call_args.args[0][-1]=='sincal.web.cad_probe'
        assert run.call_args.kwargs['timeout']==15


@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows connector')
def test_bad_response():
    with patch('sincal.web.cad_connection.subprocess.run',return_value=Mock(returncode=0,stdout='invalid')):
        assert connection_status()['status']=='unavailable'
