"""Verify applied hashes and write a human-readable recovery record."""
import hashlib, json, sys
from collections import Counter
from pathlib import Path

audit=Path(sys.argv[1])
base=Path(r'C:\Users\Usuario\Documents\SINCAL\G130\Rev. H')
recovery=base/'PI El Barrancón/NATIVOS/SINCAL_Recuperacion_viewports_20261007'
inventory=json.loads((audit/'inventory.json').read_text())
comparison=json.loads((audit/'comparison.json').read_text())
prepared=json.loads((recovery/'report.json').read_text())
applied=json.loads((recovery/'applied.json').read_text())
names={r['file'] for r in applied}
def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
rows=[]
for row in comparison:
    source=Path(row['source'])
    if source.parent==recovery.parent and source.name in names:
        assert digest(source)==digest(recovery/'recuperados'/source.name)
        assert digest(recovery/'antes'/source.name)==digest(inventory['copies'][str(source)])
        state='RECUPERADO Y VERIFICADO'
        reference=str(recovery.parent/'SINCAL_Backups/8f6fecf01bf8417d9d0bb611bdb773f8'/source.name)
    else:
        assert digest(source)==digest(inventory['copies'][str(source)]), str(source)
        exact=[r for r in row['references'] if r.get('identities_equal') and not r['frame_changes'] and not r['view_changes'] and 'Rev. G' not in r['reference']]
        state='SIN CAMBIOS: coincide con respaldo comparable' if exact else 'SIN CAMBIOS: requiere referencia fiable si presenta problemas'
        reference=exact[0]['reference'] if exact else ''
        if source.name=='ROS-B-ES-V05T17-PM-PIBAR-03-G.dwg':
            cached=Path(r'C:\Users\Usuario\AppData\Local\SINCAL\web-pilot\operations\8f6fecf01bf8417d9d0bb611bdb773f8\cab7afd4b42241d49a6706f1efd1a0be')/source.name
            assert digest(source)==digest(cached)
            state='SIN CAMBIOS: idéntico a copia previa de operación';reference=str(cached)
    rows.append({'archivo':str(source),'estado':state,'referencia':reference,'sha256_actual':digest(source)})
counts=Counter(r['estado'] for r in rows)
views=sum(len(ref['view_changes']) for row in comparison if Path(row['source']).name in names
          for ref in row['references'] if Path(ref['reference']).parent == recovery.parent/'SINCAL_Backups/8f6fecf01bf8417d9d0bb611bdb773f8')
out=base/'SINCAL_Diagnostico_viewports_20261007';out.mkdir(exist_ok=True)
(out/'detalle.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['RECUPERACIÓN DE VIEWPORTS — 7 DE OCTUBRE DE 2026','',
       'Alcance: 132 DWG de seis proyectos en Rev. H. PS Calera de Tango EXCLUIDO.',
       f'Aplicados y verificados: {len(applied)} DWG de PI El Barrancón, {views} viewports.',
       'Solo se restauraron las vistas desde respaldo compatible. Modelo actual y propiedades conservados.',
       'Los archivos anteriores se conservan completos en: '+str(recovery/'antes'),
       'Comparaciones de respaldo no equivalen a una certificación visual de todos los planos.',
       'No se restauraron archivos usando referencias con marcos o identidades incompatibles.', '', 'RESUMEN']
lines += [f'{n}: {state}' for state,n in counts.items()]
lines += ['', 'ARCHIVOS SIN REFERENCIA COMPARABLE INDEPENDIENTE DE REV. G']
lines += [r['archivo'] for r in rows if 'requiere referencia' in r['estado']]
lines += ['', 'DETALLE']
for r in rows:lines += [r['archivo'],r['estado'],'Referencia: '+r['referencia'],'']
(out/'informe.txt').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'report':str(out/'informe.txt'),'counts':counts,'viewports':views},ensure_ascii=False))
