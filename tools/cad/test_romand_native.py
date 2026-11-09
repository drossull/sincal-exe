"""Run against a disposable Core Console drawing, not an open user document."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import shutil
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', default=r'C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe')
    parser.add_argument('--drawing', type=Path, help='Read-only source to copy into the disposable test folder')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    folder = Path(tempfile.mkdtemp(prefix='sincal-romand-'))
    print(f'Report: {folder}', flush=True)
    report = folder / 'result.txt'
    env = dict(os.environ, SINCAL_TEST_ROOT=root.as_posix(), SINCAL_ROMAND_REPORT=report.as_posix())
    if Path(args.engine).name.lower() == 'zwcad.exe':
        template = Path(args.engine).parent / 'UserDataCache/en-US/Template/zwcadiso.dwt'
        drawing = folder / 'ROMAND_TEST.dwg'
        shutil.copy2(args.drawing or template, drawing)
        script = folder / 'run.scr'
        # Pass paths in the script: an already running CAD must not receive
        # our automation. A dedicated process opens only this scratch DWG.
        source = ('(if (= (strcase (vl-string-translate "\\\\" "/" '
                  '(strcat (getvar "DWGPREFIX") (getvar "DWGNAME")))) '
                  f'(strcase "{drawing.as_posix()}")) (progn '
                  f'(setq SRDT:report "{report.as_posix()}") '
                  f'(load "{(root / "lisps/ROMAND.lsp").as_posix()}") '
                  f'(load "{(root / "tests/cad/romand_regression.lsp").as_posix()}")))\n')
        script.write_text(source, encoding='ascii')
        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        process = subprocess.Popen([args.engine, str(drawing), '/b', str(script)],
                                   cwd=folder, env=env, startupinfo=startup)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                output = report.read_text(errors='replace') if report.exists() else ''
                if 'ROMAND-TEST DONE' in output:
                    break
                if process.poll() is not None:
                    raise RuntimeError('ZWCAD exited without completing the tests')
                time.sleep(.25)
            else:
                raise TimeoutError(f'Tests incomplete: {folder}')
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    else:
        result = subprocess.run(
            [args.engine, '/s', str(root / 'tests/cad/romand_regression.scr'), '/l', 'en-US'],
            cwd=folder, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
        )
        output = result.stdout.decode('utf-16-le', errors='replace')
        (folder / 'console.txt').write_text(output, encoding='utf-8')
    print(output)
    return 0 if 'ROMAND-TEST DONE failures=0' in output and 'ROMAND-TEST FAIL' not in output else 1


if __name__ == '__main__':
    raise SystemExit(main())
