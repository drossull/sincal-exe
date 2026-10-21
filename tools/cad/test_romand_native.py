"""Run against a disposable Core Console drawing, not an open user document."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', default=r'C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sincal-romand-') as folder:
        result = subprocess.run(
            [args.engine, '/s', str(root / 'tests/cad/romand_regression.scr'), '/l', 'en-US'],
            cwd=folder, env=dict(os.environ, SINCAL_TEST_ROOT=root.as_posix()),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
        )
    output = result.stdout.decode('utf-16-le', errors='replace')
    print(output)
    return 0 if 'ROMAND-TEST DONE failures=0' in output and 'ROMAND-TEST FAIL' not in output else 1


if __name__ == '__main__':
    raise SystemExit(main())
