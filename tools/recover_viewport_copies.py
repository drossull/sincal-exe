"""Prepare verified recovery copies; originals are never replaced by this tool."""
import argparse
import collections
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from inspect_viewport_copies import inspect, digest

NUMBERS = re.compile(r'[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?')


def equal_value(a, b):
    if a == b:
        return True
    try:
        aa = [float(x) for x in a.strip('() ').split()]
        bb = [float(x) for x in b.strip('() ').split()]
    except ValueError:
        return False
    return len(aa) == len(bb) and all(math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-8) for x, y in zip(aa, bb))


def model_equal(before, after):
    def read(path):
        result = collections.defaultdict(list)
        for line in path.read_text().splitlines():
            handle, code, value = line.split('|', 2)
            # Anonymous dimension block names are renumbered when saving.
            if code == '2' and value.startswith('"*D'):
                continue
            result[handle, code].append(value)
        return result
    a, b = read(before), read(after)
    return a.keys() == b.keys() and all(len(a[k]) == len(b[k]) and all(equal_value(x,y) for x,y in zip(a[k],b[k])) for k in a)


def recover(source, reference, destination, connector, allow_reference_model_difference=False):
    original_hash, reference_hash = digest(source), digest(reference)
    root = Path(tempfile.mkdtemp(prefix='SINCAL-viewport-recovery-'))
    current = root / 'current.dwg'
    baseline = root / 'reference.dwg'
    output = root / 'recovered.dwg'
    shutil.copy2(source, current)
    shutil.copy2(reference, baseline)
    a = inspect(current, root, 'before', model=False)
    b = inspect(baseline, root, 'reference-view', model=False)
    av = {h:v for h,v in a['viewports'].items() if v.get('69') != ['1']}
    bv = {h:v for h,v in b['viewports'].items() if v.get('69') != ['1']}
    if not av or av.keys() != bv.keys():
        raise ValueError(f'Viewport identities differ; review manually: {root}')
    handles = []
    for handle, value in av.items():
        old = bv[handle]
        if value['layout'] != old['layout'] or any(not equal_value(value[c][0],old[c][0]) for c in ['10','40','41']):
            raise ValueError(f'Viewport frame changed: {handle}; {root}')
        if any(not equal_value(value[c][0],old[c][0]) for c in ['12','16','17','45','51']):
            handles.append(handle)
    if not handles:
        return {'file': source.name, 'state': 'unchanged', 'sha256': original_hash, 'work': str(root)}
    inspect(current,root,'before-model')
    inspect(baseline,root,'reference-model')
    reference_model_equal=model_equal(root/'before-model/viewports.txt.model',root/'reference-model/viewports.txt.model')
    if not reference_model_equal and not allow_reference_model_difference:
        raise ValueError(f'Model geometry differs from reference; review manually: {root}')
    request = root / 'request.json'
    request.write_text(json.dumps({'current':str(current),'reference':str(baseline),'output':str(output),'handles':handles}),encoding='utf-8')
    script = root / 'recover.scr'
    script.write_text(f'_.NETLOAD\n"{connector.as_posix()}"\nSINCAL_RECOVER_VIEWPORT_COPIES\n_.QUIT\n_Y\n',encoding='ascii')
    with (root / 'recovery.log').open('wb') as log:
        process = subprocess.Popen([r'C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe',
            '/i',str(root/'before/copy.dwg'),'/s',str(script),'/l','en-US'],cwd=root,
            env=dict(os.environ,SINCAL_VIEWPORT_RECOVERY_REQUEST=str(request)),stdout=log,stderr=log,
            stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+90
        try:
            while process.poll() is None and not (root/'done').exists():
                if time.monotonic()>deadline:
                    raise RuntimeError(f'Recovery timed out: {root}')
                time.sleep(.1)
        finally:
            if process.poll() is None:
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait()
    result=json.loads((root/'result.json').read_text())
    if not result.get('ok'):
        raise ValueError(f'{result}: {root}')
    final=inspect(output,root,'verified')
    if not model_equal(root/'before-model/viewports.txt.model',root/'verified/viewports.txt.model'):
        raise ValueError(f'Recovered model geometry changed: {root}')
    for handle,value in av.items():
        actual=final['viewports'][handle]
        desired=bv[handle] if handle in handles else value
        for code in ['12','16','17','45','51']:
            if not equal_value(actual[code][0],desired[code][0]):
                raise ValueError(f'Reopened view differs: {handle}/{code}; {root}')
        for code in ['10','40','41','90','331','340']:
            if actual.get(code)!=value.get(code):
                raise ValueError(f'Frame/layers/flags changed: {handle}/{code}; {root}')
    if digest(source)!=original_hash or digest(reference)!=reference_hash:
        raise ValueError('Source changed externally during recovery')
    destination.mkdir(parents=True,exist_ok=True)
    for name,path in [('antes',source),('recuperados',output)]:
        folder=destination/name;folder.mkdir(exist_ok=True)
        target=folder/source.name
        with target.open('xb') as out,path.open('rb') as inp:
            shutil.copyfileobj(inp,out)
    return {'file':source.name,'state':'prepared','source':str(source),'reference':str(reference),
        'sha256':original_hash,'recovered_sha256':digest(output),'handles':handles,'work':str(root),
        'reference_model_equal':reference_model_equal,'current_model_preserved':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('reference',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--allow-reference-model-difference',action='store_true',help='Only after reviewing the reference difference; current model preservation remains mandatory')
    args=parser.parse_args()
    connector=Path(__file__).resolve().parent/'ViewportRecovery/bin/Release/net8.0-windows/ViewportRecovery.dll'
    print(json.dumps(recover(args.source.resolve(),args.reference.resolve(),args.destination.resolve(),connector,args.allow_reference_model_difference),indent=2),flush=True)
