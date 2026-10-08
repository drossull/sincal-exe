"""Read only temporary copies; inventory potential references without applying repairs."""
import json, os, shutil, subprocess, tempfile, time, sys, re, hashlib
from pathlib import Path

base=Path(r'C:\Users\Usuario\Documents\SINCAL\G130')
root=Path(tempfile.mkdtemp(prefix='SINCAL-vp-audit-'))
print(root,flush=True)
sources=[]; candidates={}; copies={}
older = '--older' in sys.argv
def key(path):
    match=re.search(r'-(DD|HL|PE|PG|PM)-(PI[A-Z]+)-(\d+)-',path.name.upper())
    return match.group(0) if match else None
historical={}
if older:
    for path in base.rglob('*'):
        if path.suffix.lower() not in ('.dwg','.bak') or 'Rev. H' in path.parts or 'Calera' in str(path): continue
        if key(path):historical.setdefault(key(path),[]).append(path)
hash_copies={}
for project in sorted((base/'Rev. H').iterdir()):
    if not project.is_dir() or project.name=='PS Calera de Tango': continue
    old=list((base/'Rev. G'/project.name).rglob('*.dwg'))
    for source in sorted(project.rglob('*.dwg')):
        if any(p.startswith('SINCAL_') for p in source.relative_to(project).parts): continue
        sources.append(source)
        refs=[]
        bak=source.with_suffix('.bak')
        if bak.is_file(): refs.append(bak)
        refs.extend(p for p in project.rglob(source.name) if 'SINCAL_Backups' in p.parts)
        refs.extend(p for p in old if p.name==source.name and not any(x.startswith('SINCAL_') for x in p.parts))
        if older: refs=list(dict.fromkeys([*refs,*historical.get(key(source),[])]))
        candidates[str(source)]=[str(p) for p in refs]
        for path in [source,*refs]:
            if str(path) not in copies:
                with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                if digest in hash_copies:
                    copies[str(path)]=hash_copies[digest];continue
                target=root/f'{len(copies):04d}.dwg'
                shutil.copy2(path,target); copies[str(path)]=str(target)
                hash_copies[digest]=str(target)
(root/'inventory.json').write_text(json.dumps({'sources':[str(s) for s in sources],'candidates':candidates,'copies':copies},indent=2),encoding='utf-8')
(root/'files.json').write_text(json.dumps(list(dict.fromkeys(copies.values()))),encoding='utf-8')
dll=Path(os.environ.get('SINCAL_AUDIT_DLL',str(Path(__file__).parent/'ViewportRecovery/bin/Release/net8.0-windows/ViewportRecovery.dll'))).resolve()
(root/'audit.scr').write_text(f'_.NETLOAD\n"{dll.as_posix()}"\nSINCAL_AUDIT_VIEWPORT_COPIES\n_.QUIT\n_Y\n',encoding='ascii')
with (root/'console.log').open('wb') as log:
    p=subprocess.Popen([r'C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe','/i',next(iter(copies.values())),'/s',str(root/'audit.scr'),'/l','en-US'],cwd=root,env=dict(os.environ,SINCAL_VP_AUDIT_ROOT=str(root)),stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline=time.monotonic()+900
        while not (root/'done').exists() and p.poll() is None:
            if time.monotonic()>deadline: raise TimeoutError(str(root))
            time.sleep(.5)
    finally:
        if p.poll() is None:
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:p.kill();p.wait()
if not (root/'done').exists(): raise RuntimeError(f'Audit incomplete: {root}')
print(f'Audited {len(sources)} current drawings, {len(copies)} copies total: {root}',flush=True)
