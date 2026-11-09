"""Package the optional OCR engine independently, without building SINCAL or CAD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile

if __package__:
    from .build_cache import fingerprint, matches, record, sha256
    from .build_pasarela_module import localizar_iscc
else:
    from build_cache import fingerprint, matches, record, sha256
    from build_pasarela_module import localizar_iscc

ROOT = Path(__file__).resolve().parents[1]


def runtime_files(runtime):
    return sorted(p for p in runtime.rglob('*') if p.is_file() and '__pycache__' not in p.relative_to(runtime).parts)


def validate_runtime(root, runtime):
    manifest = json.loads((runtime / 'runtime-manifest.json').read_text(encoding='utf-8'))
    expected = json.loads((root / 'packaging/ocr/models.json').read_text(encoding='utf-8'))
    if (manifest.get('requirements_sha256') != sha256(root / 'requirements-ocr-lock.txt')
            or manifest.get('worker_sha256') != sha256(root / 'packaging/ocr/worker.py')
            or manifest.get('models') != expected or not manifest.get('python', '').startswith('3.12.')):
        raise ValueError('El runtime OCR no coincide con sus fuentes. Ejecuta tools/build_ocr_runtime.py con Python 3.12 x64.')
    for name in ('python.exe', 'python312.dll', 'python312._pth', 'worker.pyc', 'NOTICE.txt'):
        if not (runtime / name).is_file() or not (runtime / name).stat().st_size:
            raise ValueError(f'Runtime incompleto: {name}')
    # CPython 3.12 bytecode: do not distribute a worker compiled by the host's other Python.
    if (runtime / 'worker.pyc').read_bytes()[:4] != b'\xcb\r\r\n':
        raise ValueError('El worker OCR no está compilado para Python 3.12.')
    for model, entries in expected.items():
        for name, digest in entries.items():
            if sha256(runtime / 'models' / model / name) != digest:
                raise ValueError(f'Modelo OCR dañado: {model}/{name}')


def package(runtime, output, descriptor):
    stage = output / 'module-stage'
    stage.mkdir(parents=True, exist_ok=True)
    files = runtime_files(runtime)
    manifest = dict(descriptor, files={'ocr_runtime/' + p.relative_to(runtime).as_posix(): sha256(p) for p in files})
    manifest_path = stage / 'module.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    archive = output / f"SINCAL_OCR_v{descriptor['version']}.zip"
    temporary = archive.with_suffix('.zip.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as stream:
            stream.write(manifest_path, 'module.json')
            for path in files:
                stream.write(path, 'ocr_runtime/' + path.relative_to(runtime).as_posix())
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    return {'id': descriptor['id'], 'version': descriptor['version'], 'worker_api': descriptor['worker_api'],
            'zip': str(archive), 'bytes': archive.stat().st_size, 'sha256': sha256(archive),
            'installed_bytes': sum(p.stat().st_size for p in files)+manifest_path.stat().st_size,
            'stage': str(stage)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--skip-runtime', action='store_true', help='Usar el runtime existente, validando fuentes y modelos')
    parser.add_argument('--skip-installer', action='store_true')
    parser.add_argument('--force', action='store_true', help='Reempaquetar aunque coincidan las huellas')
    parser.add_argument('--iscc', type=Path)
    args = parser.parse_args(argv)
    descriptor = json.loads((ROOT / 'packaging/windows/prospecciones-ocr/module.json').read_text(encoding='utf-8'))
    output = (args.output_dir or ROOT / f"installer_output/prospecciones-ocr/v{descriptor['version']}").resolve()
    output.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / 'ocr_runtime'
    if not args.skip_runtime:
        subprocess.run([sys.executable, str(ROOT / 'tools/build_ocr_runtime.py')], check=True, stdout=sys.stderr)
    validate_runtime(ROOT, runtime)
    iscc = None if args.skip_installer else localizar_iscc(args.iscc)
    inputs = runtime_files(runtime) + [Path(__file__), ROOT / 'tools/build_cache.py', ROOT / 'tools/build_pasarela_module.py',
        ROOT / 'packaging/windows/prospecciones-ocr/module.json', ROOT / 'packaging/windows/SINCAL_OCR_Installer.iss',
        ROOT / 'assets/icons/logo.ico'] + ([iscc] if iscc else [])
    key = fingerprint(inputs, json.dumps({'skip_installer': args.skip_installer, 'output': str(output)}))
    report = output / 'ocr-module-build.json'
    receipt = output / 'build-receipt.json'
    archive = output / f"SINCAL_OCR_v{descriptor['version']}.zip"
    installer = output / f"Setup_SINCAL_OCR_v{descriptor['version']}.exe"
    outputs = [report, archive, output / 'module-stage/module.json'] + ([installer] if iscc else [])
    if not args.force and matches(receipt, key, outputs):
        result = json.loads(report.read_text(encoding='utf-8'))
        print(json.dumps(dict(result, reused=True)))
        return 0
    result = package(runtime, output, descriptor)
    if iscc:
        with (output / 'inno.log').open('wb') as log:
            subprocess.run([str(iscc), '/Qp', f"/DModuleVersion={descriptor['version']}",
                            f"/DModuleStageDir={result['stage']}", f'/DOcrRuntimeDir={runtime}',
                            f'/DModuleOutputDir={output}', str(ROOT / 'packaging/windows/SINCAL_OCR_Installer.iss')],
                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        result['installer'] = str(installer)
    report.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    record(receipt, key, outputs)
    print(json.dumps(dict(result, reused=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
