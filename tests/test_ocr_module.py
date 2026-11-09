import json
from pathlib import Path
import zipfile

import pytest

from sincal.ocr_runtime import find_runtime
from tools import build_ocr_module as builder
from tools.build_cache import sha256

DESCRIPTOR = {'schema': 1, 'id': 'prospecciones-ocr', 'version': '1.0.0', 'worker_api': 1,
              'python_abi': '3.12', 'runtime': 'ocr_runtime'}


def engine(root, legacy=False):
    runtime = root/'ocr_runtime'
    runtime.mkdir(parents=True)
    for name in ('python.exe', 'worker.pyc', 'runtime-manifest.json'):
        (runtime/name).write_bytes(b'fixture')
    if not legacy:
        (root/'module.json').write_text(json.dumps(DESCRIPTOR), encoding='utf-8')
    return runtime


def test_new_module_precedes_bundled_module_and_preserves_legacy(tmp_path):
    application, user = tmp_path/'application', tmp_path/'profile'
    old = engine(application, legacy=True)
    assert find_runtime(application, user) == old
    bundled = engine(application/'modules/prospecciones-ocr')
    assert find_runtime(application, user) == bundled
    separate = engine(user/'modules/prospecciones-ocr')
    assert find_runtime(application, user) == separate
    assert old.is_dir()  # Discovery never moves/deletes the old engine.


@pytest.mark.parametrize('fault', ['api', 'missing', 'invalid', 'path'])
def test_incomplete_or_incompatible_module_has_clear_repair_error(tmp_path, fault):
    application, user = tmp_path/'application', tmp_path/'profile'
    engine(application, legacy=True)
    module = user/'modules/prospecciones-ocr'
    runtime = engine(module)
    manifest = dict(DESCRIPTOR)
    if fault == 'missing':
        (runtime/'worker.pyc').unlink()
    elif fault == 'invalid':
        (module/'module.json').write_text('invalid')
    else:
        manifest.update({'worker_api': 2} if fault == 'api' else {'runtime': '../../elsewhere'})
        (module/'module.json').write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match='Reinstala el complemento OCR'):
        find_runtime(application, user)


def test_no_engine_requests_only_complement_not_full_reinstall(tmp_path):
    with pytest.raises(RuntimeError, match='Instala Setup_SINCAL_OCR'):
        find_runtime(tmp_path/'app', tmp_path/'user')


def test_package_contains_only_engine_with_hashes_and_licenses(tmp_path):
    runtime = engine(tmp_path/'source')
    (runtime/'LICENSE.txt').write_text('license')
    (runtime/'__pycache__').mkdir()
    (runtime/'__pycache__/discard.pyc').write_bytes(b'discard')
    (tmp_path/'source/project-secret.json').write_text('not an engine file')
    result = builder.package(runtime, tmp_path/'output', DESCRIPTOR)
    with zipfile.ZipFile(result['zip']) as archive:
        manifest = json.loads(archive.read('module.json'))
        assert set(archive.namelist()) == {'module.json', *manifest['files']}
        assert 'ocr_runtime/LICENSE.txt' in manifest['files']
        assert not any('secret' in name or '__pycache__' in name for name in archive.namelist())
        for name, digest in manifest['files'].items():
            assert digest == sha256(tmp_path/'source'/name)
    assert result['sha256'] == sha256(result['zip'])


def test_module_cache_reuses_outputs_but_rebuilds_corrupted_zip(tmp_path, monkeypatch, capsys):
    engine(tmp_path)
    descriptor = tmp_path/'packaging/windows/prospecciones-ocr/module.json'
    descriptor.parent.mkdir(parents=True)
    descriptor.write_text(json.dumps(DESCRIPTOR))
    for name in ('tools/build_cache.py', 'tools/build_pasarela_module.py',
                 'packaging/windows/SINCAL_OCR_Installer.iss', 'assets/icons/logo.ico'):
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture')
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    monkeypatch.setattr(builder, 'validate_runtime', lambda *_: None)
    args = ['--skip-runtime', '--skip-installer']
    assert builder.main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert first['reused'] is False
    assert builder.main(args) == 0
    assert json.loads(capsys.readouterr().out)['reused'] is True
    Path(first['zip']).write_bytes(b'corrupt')
    assert builder.main(args) == 0
    assert json.loads(capsys.readouterr().out)['reused'] is False


def runtime_source_fixture(root):
    runtime = root/'ocr_runtime'
    runtime.mkdir()
    for name in ('python.exe', 'python312.dll', 'python312._pth', 'NOTICE.txt'):
        (runtime/name).write_bytes(b'fixture')
    (runtime/'worker.pyc').write_bytes(b'\xcb\r\r\nfixture')
    worker = root/'packaging/ocr/worker.py'
    worker.parent.mkdir(parents=True)
    worker.write_text('worker')
    lock = root/'requirements-ocr-lock.txt'
    lock.write_text('pinned')
    model = runtime/'models/sample/weights'
    model.parent.mkdir(parents=True)
    model.write_bytes(b'model weights')
    models = {'sample': {'weights': sha256(model)}}
    (worker.parent/'models.json').write_text(json.dumps(models))
    (runtime/'runtime-manifest.json').write_text(json.dumps({'python': '3.12.10',
        'requirements_sha256': sha256(lock), 'worker_sha256': sha256(worker), 'models': models}))
    return runtime


@pytest.mark.parametrize('changed', ['worker', 'lock', 'model', 'bytecode', 'missing'])
def test_existing_runtime_must_match_sources_and_model_hashes(tmp_path, changed):
    runtime = runtime_source_fixture(tmp_path)
    builder.validate_runtime(tmp_path, runtime)
    paths = {'worker': tmp_path/'packaging/ocr/worker.py', 'lock': tmp_path/'requirements-ocr-lock.txt',
             'model': runtime/'models/sample/weights', 'bytecode': runtime/'worker.pyc'}
    if changed == 'missing':
        (runtime/'python.exe').unlink()
    else:
        paths[changed].write_bytes(b'changed')
    with pytest.raises(ValueError):
        builder.validate_runtime(tmp_path, runtime)
