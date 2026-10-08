"""Inspect disposable DWG copies only. Never opens source drawings in CAD."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inspect(source, root, index, model=True):
    before = digest(source)
    work = root / str(index)
    work.mkdir()
    drawing = work / 'copy.dwg'
    shutil.copy2(source, drawing)
    report = work / 'viewports.txt'
    lisp = Path(__file__).with_name('inspect_viewports.lsp').resolve()
    script = work / 'inspect.scr'
    script.write_text(f'(load "{lisp.as_posix()}")\n(setq SINCAL:VPSkipModel {"nil" if model else "T"})\nSINCAL_VP_INSPECT\n_.QUIT\n_Y\n', encoding='ascii')
    with (work / 'console.log').open('wb') as log:
        process = subprocess.Popen([
            r'C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe',
            '/i', str(drawing), '/s', str(script), '/l', 'en-US'],
            cwd=work, env=dict(os.environ, SINCAL_VP_REPORT=str(report)),
            stdout=log, stderr=log, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 180
            while process.poll() is None and not Path(str(report) + '.done').exists():
                if time.monotonic() > deadline:
                    raise subprocess.TimeoutExpired(process.args, 180)
                time.sleep(.1)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # Only our throwaway reader. No drawing writes are performed.
                process.kill()
                process.wait()
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError(f'Diagnostic timed out: {source.name}')
    if digest(source) != before:
        raise RuntimeError('Source changed externally during inspection')
    if not report.exists():
        raise RuntimeError(f'Missing report: {work}')
    result = {}
    for line in report.read_text(encoding='utf-8', errors='replace').splitlines():
        handle, layout, code, value = line.split('|', 3)
        result.setdefault(handle, {'layout': layout}).setdefault(code, []).append(value)
    return {'source': str(source), 'sha256': before, 'viewports': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+', type=Path)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='SINCAL-viewport-inspection-'))
    print(root, flush=True)
    results = []
    for index, source in enumerate(args.files):
        result = inspect(source.resolve(), root, index)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    (root / 'report.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
