const assert = require('node:assert/strict');
const fs = require('node:fs');
const io = require('../../pasarela_bim/web/proyecto.js');
const fixture=JSON.parse(fs.readFileSync('pasarela_bim/ejemplos/los_batros.json','utf8'));
const portable=io.toPortable(fixture);
assert.equal(portable.version,2);
assert.equal(portable.proyecto.unidades,'m');
assert.equal(portable.familias.atravieso.canto_m,1.45);
const back=io.toInternal(portable);
for(const n of fixture.nodos){const b=back.nodos.find(x=>x.id===n.id); for(const axis of ['x','y','z'])assert.ok(Math.abs(b[axis]-n[axis])<1e-8);}
const model=io.newProject({este_m:350000,norte_m:6000000,cota_m:120,norte_desde_x_horario_deg:270});
model.nodos=[{id:'N1',x:15000,y:5000,z:6500}];
model.emplazamiento={planta:{entidades:[{puntos_m:[[350001,6000000,121]]}]}};
assert.deepEqual(io.toPortable(model).proyecto.georreferencia,model.proyecto.georreferencia);
assert.deepEqual(io.toPortable(model).emplazamiento,model.emplazamiento);
const w=io.localToWorld(model,15,5,6.5);
assert.deepEqual(w,[350015,6000005,126.5]);
for(const angle of [0,90,180,270,32.7]){
 model.proyecto.georreferencia.norte_desde_x_horario_deg=angle;
 const global=io.localToWorld(model,15,5,6.5),local=io.worldToLocal(model,...global);
 for(const [i,v] of [15,5,6.5].entries())assert.ok(Math.abs(local[i]-v)<1e-8);
}
assert.throws(()=>io.toInternal({...portable,version:42}));
assert.throws(()=>io.toInternal({...portable,proyecto:{...portable.proyecto,unidades:'mm'}}));
console.log('Project IO: metres, legacy import, geographic rotation and round-trip passed.');
