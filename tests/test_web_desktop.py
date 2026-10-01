from unittest.mock import Mock
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
import pytest

from sincal.web.desktop import run


@pytest.mark.parametrize('fail', [False, True])
def test_window_uses_local_api_and_always_stops_it(tmp_path, fail):
    shell = Mock()
    shell.settings = {}
    origins = []
    def start(**kwargs):
        url = shell.create_window.call_args.kwargs['url']
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        origins.append(origin)
        token = parts.fragment.removeprefix('token=')
        with urlopen(Request(origin+'/api/preferences', headers={'X-Sincal-Token':token})) as response:
            assert response.status == 200
        assert kwargs['gui'] == 'edgechromium'
        assert kwargs['debug'] is False
        if fail:
            raise RuntimeError('Simulated renderer startup failure')
    shell.start.side_effect = start
    if fail:
        with pytest.raises(RuntimeError):
            run(shell, tmp_path)
    else:
        run(shell, tmp_path)
    with pytest.raises(OSError):
        urlopen(origins[0], timeout=1)
    assert shell.create_window.call_args.kwargs['confirm_close'] is True
    assert 'js_api' not in shell.create_window.call_args.kwargs
    assert shell.settings['ALLOW_FILE_URLS'] is False
