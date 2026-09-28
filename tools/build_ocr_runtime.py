"""Empaqueta CPython/Paddle en una carpeta aislada, con modelos locales fijados.

Ejecutar con CPython 3.12 x64 de python.org y requirements-build.txt instalado.
El entorno de dependencias no contiene PyMuPDF ni los scripts/datos de la prueba.
"""
from pathlib import Path
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'ocr_runtime'
ENV = ROOT / 'tmp' / 'ocr-build-env'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sys.version_info[:2] != (3, 12) or sys.platform != 'win32':
        raise SystemExit('El runtime OCR requiere CPython 3.12 para Windows x64.')
    requirements = ROOT / 'requirements-ocr-lock.txt'
    fingerprint = digest(requirements)
    marker = TARGET / 'runtime-manifest.json'
    if marker.exists() and json.loads(marker.read_text())['requirements_sha256'] != fingerprint:
        raise SystemExit('Cambió el lock OCR: archiva o retira ocr_runtime antes de recompilar.')
    python = ENV / 'Scripts' / 'python.exe'
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(ENV)], check=True)
    if not marker.exists():
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirements)], check=True)
        base = Path(sys.base_prefix)
        TARGET.mkdir(exist_ok=True)
        for name in ('python.exe', 'pythonw.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll',
                     'vcruntime140_1.dll', 'LICENSE.txt'):
            source = base / name
            if source.exists():
                shutil.copy2(source, TARGET / name)
        shutil.copytree(base / 'DLLs', TARGET / 'DLLs', dirs_exist_ok=True)
        shutil.copytree(base / 'Lib', TARGET / 'Lib', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests',
                                                     'idlelib', 'tkinter', 'ensurepip'))
        shutil.copytree(ENV / 'Lib' / 'site-packages', TARGET / 'Lib' / 'site-packages', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', 'pip', 'pip-*'))
        (TARGET / 'python312._pth').write_text('Lib\nDLLs\nLib/site-packages\n.\nimport site\n', encoding='ascii')
    models = json.loads((ROOT / 'packaging' / 'ocr' / 'models.json').read_text())
    for model, files in models.items():
        destination = TARGET / 'models' / model
        destination.mkdir(parents=True, exist_ok=True)
        for name, sha256 in files.items():
            target = destination / name
            if target.exists() and digest(target) == sha256:
                continue
            cached = Path.home() / '.paddlex' / 'official_models' / model / name
            if cached.exists() and digest(cached) == sha256:
                shutil.copy2(cached, target)
            else:
                url = f'https://huggingface.co/PaddlePaddle/{model}/resolve/main/{name}'
                with urllib.request.urlopen(url, timeout=120) as response:
                    target.write_bytes(response.read())
            if digest(target) != sha256:
                raise SystemExit(f'SHA-256 inesperado del modelo: {model}/{name}')
    worker = ROOT / 'packaging' / 'ocr' / 'worker.py'
    py_compile.compile(str(worker), cfile=str(TARGET / 'worker.pyc'), dfile='sincal_ocr_worker.py', doraise=True)
    shutil.copy2(ROOT / 'packaging' / 'ocr' / 'NOTICE.txt', TARGET / 'NOTICE.txt')
    marker.write_text(json.dumps({'python': sys.version, 'requirements_sha256': fingerprint,
                                  'worker_sha256': digest(worker), 'models': models}, indent=2), encoding='utf-8')
    # Validate relocation/isolation: no user site-packages or installed Python required.
    subprocess.run([str(TARGET / 'python.exe'), '-B', '-c',
                    'import sys, paddle, paddleocr; print(sys.version); print(paddle.__version__, paddleocr.__version__); '
                    'assert sys.flags.isolated; assert not sys.flags.ignore_environment == 0'], check=True,
                   cwd=str(ROOT / 'tmp'), env={**os.environ, 'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK': 'True'})
    print('Runtime OCR listo:', TARGET, flush=True)


if __name__ == '__main__':
    main()
