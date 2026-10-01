import pytest

from sincal.web.files import Files


def test_folder_listing_requires_grant_and_only_lists_direct_files(tmp_path):
    (tmp_path / 'B.dwg').write_bytes(b'123')
    (tmp_path / 'a.txt').write_text('a')
    nested = tmp_path / 'nested'
    nested.mkdir()
    (nested / 'hidden.txt').write_text('hidden')
    files = Files()
    with pytest.raises(ValueError):
        files.list_folder(str(tmp_path))
    grant = files.grant(tmp_path, 'folder')
    assert files.list_folder(grant['id']) == [
        {'name': 'a.txt', 'bytes': 1}, {'name': 'B.dwg', 'bytes': 3}]
    (tmp_path / 'B.dwg').rename(tmp_path / 'C.dwg')
    assert files.list_folder(grant['id'])[1]['name'] == 'C.dwg'
