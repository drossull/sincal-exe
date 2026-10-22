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
assert.ok(!Object.hasOwn(model.proyecto,'cota_carretera_m'));
assert.ok(!Object.hasOwn(model.proyecto,'cota_terreno_m'));
assert.equal(model.proyecto.galibo_m,5.5);
model.nodos=[{id:'N1',x:15000,y:5000,z:6500}];
model.emplazamiento={planta:{entidades:[{puntos_m:[[350001,6000000,121]]}]}};
assert.deepEqual(io.toPortable(model).proyecto.georreferencia,model.proyecto.georreferencia);
assert.deepEqual(io.toPortable(model).emplazamiento,model.emplazamiento);
// Each support owns its projected terrain elevation, including when two
// supports share a foundation. Unknown elevations stay absent on exchange.
model.soportes=[
 {id:'C1',nodo:'C1',fundacion:'D1',cota_terreno_proyectado_mm:-6250},
 {id:'C2',nodo:'C2',fundacion:'D1',cota_terreno_proyectado_mm:-5900},
 {id:'E1',nodo:'E1',fundacion:'D2'}
];
const terrainPortable=io.toPortable(model),terrainBack=io.toInternal(JSON.parse(JSON.stringify(terrainPortable)));
assert.equal(terrainPortable.soportes[0].cota_terreno_proyectado_m,-6.25);
assert.equal(terrainPortable.soportes[1].cota_terreno_proyectado_m,-5.9);
assert.ok(!Object.hasOwn(terrainPortable.soportes[2],'cota_terreno_proyectado_m'));
assert.deepEqual(terrainBack.soportes,model.soportes);
const globalLegacy=structuredClone(model);globalLegacy.proyecto.cota_terreno_m=-8;globalLegacy.proyecto.cota_carretera_m=-7;
delete globalLegacy.soportes[0].cota_terreno_proyectado_mm;
const legacyRoundTrip=io.toInternal(io.toPortable(globalLegacy));
assert.deepEqual(legacyRoundTrip.proyecto,globalLegacy.proyecto);
assert.ok(!Object.hasOwn(legacyRoundTrip.soportes[0],'cota_terreno_proyectado_mm'));
const w=io.localToWorld(model,15,5,6.5);
assert.deepEqual(w,[350015,6000005,126.5]);
for(const angle of [0,90,180,270,32.7]){
 model.proyecto.georreferencia.norte_desde_x_horario_deg=angle;
 const global=io.localToWorld(model,15,5,6.5),local=io.worldToLocal(model,...global);
 for(const [i,v] of [15,5,6.5].entries())assert.ok(Math.abs(local[i]-v)<1e-8);
}
assert.throws(()=>io.toInternal({...portable,version:42}));
assert.throws(()=>io.toInternal({...portable,proyecto:{...portable.proyecto,unidades:'mm'}}));
// Clockwise from +Y: a unit vector toward the displayed north must map to
// exactly one metre north in global coordinates, including after JSON exchange.
for(const angle of [0,90,180,270,345.638]){
 const m=io.newProject({este_m:350000,norte_m:6000000,cota_m:120,norte_desde_y_horario_deg:angle});
 const reopened=io.toInternal(JSON.parse(JSON.stringify(io.toPortable(m))));
 assert.ok(Math.abs(io.northAngleFromY(reopened.proyecto.georreferencia)-angle)<1e-10);
 const a=angle*Math.PI/180, w=io.localToWorld(reopened,Math.sin(a),Math.cos(a),0);
 assert.ok(Math.abs(w[0]-350000)<1e-8);
 assert.ok(Math.abs(w[1]-6000001)<1e-8);
}
const legacy=io.newProject({norte_desde_x_horario_deg:255.638});
const displayed=io.northAngleFromY(legacy.proyecto.georreferencia);
assert.ok(Math.abs(displayed-345.638)<1e-10);
const edited=io.newProject({norte_desde_y_horario_deg:displayed});
for(const [i,v] of io.localToWorld(legacy,15,5,6.5).entries())assert.ok(Math.abs(io.localToWorld(edited,15,5,6.5)[i]-v)<1e-10);
for(const angle of [-1,360,Infinity,NaN])assert.throws(()=>io.newProject({norte_desde_y_horario_deg:angle}));
console.log('Project IO: metres, legacy import, geographic rotation and round-trip passed.');
