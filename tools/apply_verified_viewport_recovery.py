"""Apply already verified recovery copies, retaining exact pre-recovery DWGs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sincal.cad.batch import drawing_available
from sincal.cad.dwgprops import fingerprint

parser=argparse.ArgumentParser()
parser.add_argument('folder',type=Path)
parser.add_argument('recovery',type=Path)
parser.add_argument('--apply',action='store_true')
args=parser.parse_args()
folder=args.folder.resolve(strict=True)
recovery=args.recovery.resolve(strict=True)
items=[]
for ready in sorted((recovery/'recuperados').glob('*.dwg')):
    target=folder/ready.name
    backup=recovery/'antes'/ready.name
    if target.resolve().parent!=folder or target.is_symlink() or not backup.is_file():
        raise ValueError('Unsafe target or missing backup')
    drawing_available(target)
    previous=fingerprint(backup)
    if fingerprint(target)!=previous:
        raise ValueError(f'Drawing changed since preparation: {target.name}')
    items.append({'file':target.name,'before':previous,'after':fingerprint(ready)})
print(json.dumps({'count':len(items),'files':[r['file'] for r in items]}),flush=True)
if not args.apply:
    sys.exit(0)
manifest=recovery/'applied.json'
if manifest.exists():
    raise ValueError('An application manifest already exists; do not overwrite it')
applied=[]
for item in items:
    target=folder/item['file']
    drawing_available(target)
    if fingerprint(target)!=item['before']:
        raise ValueError('Drawing changed during recovery')
    staging=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.sincal-recovery-',suffix='.dwg',dir=folder,delete=False) as out:
            staging=Path(out.name)
            with (recovery/'recuperados'/item['file']).open('rb') as inp:
                shutil.copyfileobj(inp,out)
        if fingerprint(staging)!=item['after']:
            raise ValueError('Staging copy verification failed')
        drawing_available(target)
        if fingerprint(target)!=item['before']:
            raise ValueError('Drawing changed immediately before replacement')
        os.replace(staging,target)
        if fingerprint(target)!=item['after']:
            raise ValueError('Replacement verification failed; backup preserved')
        applied.append(item)
        manifest.write_text(json.dumps(applied,indent=2),encoding='utf-8')
        print('Recovered: '+item['file'],flush=True)
    finally:
        if staging is not None and staging.exists():
            staging.unlink()
