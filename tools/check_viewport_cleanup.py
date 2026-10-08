"""Compare cleanup stages on a disposable DWG, without saving the source."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from inspect_viewport_copies import digest

source = Path(sys.argv[1]).resolve()
before = digest(source)
root = Path(tempfile.mkdtemp(prefix='SINCAL-cleanup-stages-'))
print(root, flush=True)
copy = root / 'copy.dwg'
shutil.copy2(source, copy)
repo = Path(__file__).resolve().parents[1]
stages = [
    ('before', ''),
    ('vg', f'(load "{(repo / "lisps/PURGEALL.lsp").as_posix()}")\n(load "{(repo / "lisps/VG.lsp").as_posix()}")\nVG\n'),
    ('audit', '_.AUDIT\n_Y\n'),
    ('zoom', '_.ZOOM\n_E\n'),
]
commands = f'(load "{(repo / "tools/inspect_viewports.lsp").as_posix()}")\n'
for name, command in stages:
    commands += command + f'(setq SINCAL:VPReport "{(root / (name + ".txt")).as_posix()}")\nSINCAL_VP_INSPECT\n'
commands += '_.QUIT\n_Y\n'
script = root / 'stages.scr'
script.write_text(commands, encoding='ascii')
with (root / 'console.log').open('wb') as log:
    process = subprocess.Popen([r'C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe',
        '/i', str(copy), '/s', str(script), '/l', 'en-US'], cwd=root,
        stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 60
    try:
        while process.poll() is None and not (root / 'zoom.txt').exists():
            if time.monotonic() > deadline:
                raise RuntimeError('Stage test timed out')
            time.sleep(.1)
    finally:
        if process.poll() is None:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
assert digest(source) == before
previous = None
for name, _ in stages:
    lines = (root / (name + '.txt')).read_text().splitlines()
    if previous is not None:
        print(name, json.dumps({'removed': sorted(set(previous)-set(lines)),
                                'added': sorted(set(lines)-set(previous))}), flush=True)
    previous = lines
