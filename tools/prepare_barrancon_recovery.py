import concurrent.futures, json
from pathlib import Path
from recover_viewport_copies import recover
folder=Path(r'C:\Users\Usuario\Documents\SINCAL\G130\Rev. H\PI El Barrancón\NATIVOS')
reference=folder/'SINCAL_Backups/8f6fecf01bf8417d9d0bb611bdb773f8'
destination=folder/'SINCAL_Recuperacion_viewports_20261007'
connector=Path(__file__).parent.resolve()/'ViewportRecovery/bin/Release/net8.0-windows/ViewportRecovery.dll'
def run(source):
    if (destination/'recuperados'/source.name).exists(): return {'file':source.name,'state':'already-prepared'}
    if not (reference/source.name).exists():return {'file':source.name,'state':'no-reference'}
    try:return recover(source,reference/source.name,destination,connector)
    except Exception as error:return {'file':source.name,'state':'review-required','error':str(error)}
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    tasks={pool.submit(run,p):p for p in sorted(folder.glob('*.dwg'))}
    for future in concurrent.futures.as_completed(tasks):
        row=future.result();results.append(row)
        (destination/'report.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(json.dumps(row),flush=True)
