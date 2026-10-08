"""Reproduce DWGPROPS saves on a disposable copy and compare viewports."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sincal.cad.dwgprops import CadBatch
import sincal.cad.dwgprops as dwgprops
from inspect_viewport_copies import inspect, digest

source = Path(sys.argv[1]).resolve()
original_hash = digest(source)
root = Path(tempfile.mkdtemp(prefix='SINCAL-viewport-roundtrip-'))
print(root, flush=True)
before = inspect(source, root, 'before')
job = root / 'job'
directory = job / 'file'
directory.mkdir(parents=True)
copy = directory / 'copy.dwg'
shutil.copy2(source, copy)
batch = CadBatch(job)
try:
    if '--installed' in sys.argv:
        dwgprops.connector_path=lambda year: Path(r'C:\Program Files\SINCAL\native\dwgprops')/str(year)/'Sincal.DwgProps.dll'
    if '--bootstrap' in sys.argv:
        batch._start(Path(sys.argv[sys.argv.index('--bootstrap')+1]).resolve())
    batch(copy, {'SINCAL_DIAGNOSTIC_TEMP': 'temporary copy only'}, directory)
finally:
    batch.close()
after = inspect(copy, root, 'after')
assert digest(source) == original_hash
report = {'before': before, 'after': after}
(root / 'comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
changes=[h for h in before['viewports'] if before['viewports'][h]!=after['viewports'].get(h)]
print(json.dumps({'changed_viewports':changes,'report':str(root/'comparison.json')}),flush=True)
