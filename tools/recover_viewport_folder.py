"""Prepare separate recovery copies for this folder, recording every outcome."""
import json
from pathlib import Path
import sys
from recover_viewport_copies import recover

folder=Path(sys.argv[1]).resolve()
destination=Path(sys.argv[2]).resolve()
destination.mkdir(exist_ok=True)
connector=Path(__file__).resolve().parent/'ViewportRecovery/bin/Release/net8.0-windows/ViewportRecovery.dll'
results=[]
for source in sorted(folder.glob('*.dwg')):
    if (destination/'recuperados'/source.name).exists():
        print('Already prepared:',source.name,flush=True)
        continue
    references=list((folder/'SINCAL_Backups').rglob(source.name))
    if not references:
        alternate=source.name.replace('ROS-B-HS-','ROS-B-GS-').replace('-H.dwg','-G.dwg')
        references=list((folder/'SINCAL_Backups').rglob(alternate))
    try:
        if not references: raise ValueError('No reference backup found')
        reference=max(references,key=lambda p:p.stat().st_mtime)
        print('Preparing:',source.name,flush=True)
        result=recover(source,reference,destination,connector)
    except Exception as error:
        result={'file':source.name,'state':'review-required','error':str(error)}
    results.append(result)
    (destination/'report.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
