import json, math, sys
from pathlib import Path
root=Path(sys.argv[1]); inv=json.loads((root/'inventory.json').read_text())
data={p['file']:p for p in map(json.loads,(root/'audit.jsonl').read_text().splitlines())}
def equal(a,b):return len(a)==len(b) and all(math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-7) for x,y in zip(a,b))
results=[]
for source in inv['sources']:
    current=data[inv['copies'][source]]
    row={'source':source,'references':[]}
    for ref in inv['candidates'][source]:
        other=data[inv['copies'][ref]]
        if 'error' in current or 'error' in other:
            row['references'].append({'reference':ref,'error':other.get('error',current.get('error'))});continue
        a={v['handle']:v for v in current['views'] if not v.get('overall')};b={v['handle']:v for v in other['views'] if not v.get('overall')}
        common=a.keys()&b.keys()
        frames=[h for h in common if a[h]['layout']!=b[h]['layout'] or not equal(a[h]['frame'],b[h]['frame'])]
        changed=[h for h in common if not equal(a[h]['view'],b[h]['view'])]
        row['references'].append({'reference':ref,'count':len(a),'identities_equal':a.keys()==b.keys(),
            'frame_changes':frames,'view_changes':changed})
    results.append(row)
(root/'comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for row in results:
    refs=row['references']
    print(Path(row['source']).parent.name,Path(row['source']).name,[(('BAK' if r['reference'].endswith('.bak') else 'BACKUP' if 'SINCAL_Backups' in r['reference'] else 'G'),r.get('identities_equal'),len(r.get('frame_changes',[])),len(r.get('view_changes',[])),r.get('error')) for r in refs])
