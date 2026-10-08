"""Read-only comparison of audited frames, including references with new handles."""
import json, math, sys
from pathlib import Path
root=Path(sys.argv[1])
inv=json.loads((root/'inventory.json').read_text())
data={r['file']:r for r in map(json.loads,(root/'audit.jsonl').read_text().splitlines())}
def same(a,b):
    return len(a)==len(b) and all(math.isclose(x,y,abs_tol=1e-6,rel_tol=1e-10) for x,y in zip(a,b))
results=[]
for source in inv['sources']:
    current=data[inv['copies'][source]].get('views',[])
    refs=[]
    for ref in inv['candidates'][source]:
        old=data[inv['copies'][ref]].get('views',[])
        pairs=[]
        for v in current:
            matches=[w for w in old if same(v['frame'],w['frame'])]
            if len(matches)==1:
                pairs.append((v,matches[0]))
        refs.append({'reference':ref,'current_count':len(current),'reference_count':len(old),
                     'matched_frames':len(pairs),'same_views':sum(same(v['view'],w['view']) for v,w in pairs),
                     'changed':[v['handle'] for v,w in pairs if not same(v['view'],w['view'])]})
    results.append({'source':source,'references':refs})
(root/'frame_comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for row in results:
    older=[r for r in row['references'] if 'Rev. H' not in r['reference'] and 'Rev. G' not in r['reference']]
    best=max(older,key=lambda r:r['same_views'],default={})
    print(Path(row['source']).name, json.dumps(best))

# Identify identical camera states reused between different projects. This is
# diagnostic evidence only: standard plan templates can legitimately match.
from collections import defaultdict
states=defaultdict(list)
for source in inv['sources']:
    for v in data[inv['copies'][source]].get('views',[]):
        states[tuple(round(x,7) for x in v['view'])].append((source,v['handle']))
shared=[]
for values in states.values():
    projects={str(Path(p).relative_to(Path(r'C:\Users\Usuario\Documents\SINCAL\G130\Rev. H')).parts[0]) for p,h in values}
    if len(projects)>1: shared.append(values)
(root/'shared_cameras.json').write_text(json.dumps(shared,indent=2),encoding='utf-8')
