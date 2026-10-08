from unittest.mock import Mock

import pytest

from sincal.web.cad_worker import command_with_completion, read_completion, execute


def request(tmp_path, **kw):
    return dict(command='(progn (load "test.lsp") (c:SINCAL-ESTRATIGRAFIA))\n',
                marker=str(tmp_path/'done.txt'), token='test-token', **kw)


def test_interactive_lisp_is_one_expression_not_queued_input(tmp_path):
    value = request(tmp_path, completion='stratigraphy-v1')
    command = command_with_completion(value)
    assert command.count('\n') == 1 and command.endswith('))\n')
    assert '*SINCAL_ESTRAT_COMPLETION*' in command
    assert '(write-line' not in command
    legacy = command_with_completion(request(tmp_path))
    assert legacy.startswith('(progn (progn') and legacy.count('\n') == 1
    ordinary = dict(request(tmp_path), command='_.ZOOM\n_E\n')
    assert command_with_completion(ordinary).startswith('_.ZOOM\n_E\n(progn')


def test_completion_requires_matching_token_and_complete_status(tmp_path):
    value = request(tmp_path, completion='stratigraphy-v1')
    path = tmp_path/'done.txt'
    assert read_completion(value) is None
    path.write_text('old-token\nok\nold success\n')
    assert read_completion(value) is None
    path.write_text('test-token\nok\n')
    assert read_completion(value) is None
    path.write_text('test-token\nok\nInserted\n')
    assert read_completion(value) == {'message':'Inserted'}
    for status in ('error','cancelled'):
        path.write_text(f'test-token\n{status}\nMissing hatch\n')
        with pytest.raises(RuntimeError, match='Missing hatch'):
            read_completion(value)


def test_worker_reports_native_error_instead_of_success_or_timeout(tmp_path, monkeypatch):
    value = request(tmp_path, completion='stratigraphy-v1')
    doc = Mock(Name='test.dwg', FullName='C:/test.dwg')
    doc.GetVariable.side_effect=lambda name: {'CMDACTIVE':0,'INSUNITS':6,'TILEMODE':1}[name]
    app = Mock(ActiveDocument=doc, HWND=123)
    monkeypatch.setattr('sincal.web.cad_worker.active_application',lambda:app)
    value['expected'] = dict(instance='123',active={'name':'test.dwg','path':'C:/test.dwg'})
    doc.SendCommand.side_effect=lambda _: (tmp_path/'done.txt').write_text('test-token\nerror\nFalta hatch ANSI31\n')
    with pytest.raises(RuntimeError, match='Falta hatch ANSI31'):
        execute(value)
    assert doc.SendCommand.call_count == 1
    doc.Save.assert_not_called()
    app.Quit.assert_not_called()
