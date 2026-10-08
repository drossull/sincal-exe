from unittest.mock import Mock, PropertyMock, patch
import pytest
import sys
from sincal.web.cad_readiness import read_when_ready, wait_for_document
from sincal.web.cad_worker import execute, command_with_completion, read_completion
from sincal.web.services import Services


def test_transient_read_is_retried():
    read = Mock(side_effect=[AttributeError('AutoCAD.Application.ActiveDocument'), 'ready'])
    assert read_when_ready(read, interval=0) == 'ready'
    assert read.call_count == 2


def test_read_timeout_has_actionable_message():
    with pytest.raises(RuntimeError, match='No se envió'):
        read_when_ready(Mock(side_effect=AttributeError('ActiveDocument')), timeout=0)


def test_unrelated_error_is_not_retried():
    read = Mock(side_effect=ValueError('wrong document'))
    with pytest.raises(ValueError):
        read_when_ready(read)
    assert read.call_count == 1


def test_busy_hresult_is_retried():
    error = Exception('busy'); error.hresult = -2147418111
    assert read_when_ready(Mock(side_effect=[error, 1]), interval=0) == 1


def test_activation_waits_for_requested_document():
    old, new = Mock(), Mock()
    old.Name, old.FullName = 'old', 'old'
    new.Name, new.FullName = 'new', 'new'
    with patch('sincal.web.cad_readiness.active_document', side_effect=[old,new]), patch('sincal.web.cad_readiness.time.sleep'):
        assert wait_for_document(Mock(), {'name':'new','path':'new'}) is new


def test_active_document_failure_never_sends():
    app=Mock()
    with patch('sincal.web.cad_worker.active_application', return_value=app), patch('sincal.web.cad_worker.active_document', side_effect=RuntimeError('busy')):
        with pytest.raises(RuntimeError):
            execute({})
    app.SendCommand.assert_not_called()


@pytest.mark.parametrize('status', ['error','ok'])
def test_live_completion_reports_paste_result(tmp_path, status):
    request={'marker':str(tmp_path/'done'),'token':'abc','completion':'live-v1','command':'(c:P0)\n'}
    expression=command_with_completion(request)
    assert 'vl-catch-all-apply' in expression and '*SINCAL_LIVE_RESULT*' in expression
    assert expression.count('\n')==1
    (tmp_path/'done').write_text('abc\n'+status+'\nP0 result\n')
    if status=='error':
        with pytest.raises(RuntimeError,match='P0 result'):read_completion(request)
    else:assert read_completion(request)['message']=='P0 result'


@pytest.mark.parametrize('command', ['P0','_.P0','STO','_STO'])
def test_catalog_loads_installed_routine_before_execution(tmp_path, command):
    service=Services(tmp_path)
    try:
        with patch.object(service,'cad',return_value={}) as cad:
            service.command(Mock(), {'command':command,'expected':{},'scope':'all'})
        assert '(load ' in cad.call_args.args[2]
        assert '(c:ST0)' in cad.call_args.args[2] if 'STO' in command else '(c:P0)' in cad.call_args.args[2]
        assert cad.call_args.kwargs['completion']=='live-v1'
        assert cad.call_args.kwargs['scope']=='all'
        assert cad.call_args.kwargs['clipboard']==('P0' in command)
    finally:service.jobs.close()


@pytest.mark.parametrize('name,valid', [('AutoCAD.r25',True),('ZWCAD.r24',True),('HTML Format',False)])
def test_clipboard_formats_are_checked_without_reading_data(name,valid):
    from sincal.web.cad_worker import ensure_cad_clipboard
    clipboard=Mock()
    clipboard.EnumClipboardFormats.side_effect=[13,0xc123,0]
    clipboard.GetClipboardFormatName.return_value=name
    with patch.dict(sys.modules,win32clipboard=clipboard):
        if valid:ensure_cad_clipboard()
        else:
            with pytest.raises(ValueError,match='COPYCLIP'):ensure_cad_clipboard()
    clipboard.CloseClipboard.assert_called_once()
    clipboard.GetClipboardData.assert_not_called()
    clipboard.EmptyClipboard.assert_not_called()
