const assert=require('node:assert/strict'),io=require('../../pasarela_bim/web/proyecto.js');
const m=io.newProject({cota_m:100});
assert.equal(m.proyecto.referencia_vertical,'tope_atravieso');
assert.ok(!Object.hasOwn(m.proyecto,'cota_carretera_m'));
assert.ok(!Object.hasOwn(m.proyecto,'cota_terreno_m'));
const old=structuredClone(m);delete old.proyecto.referencia_vertical;old.proyecto.cota_carretera_m=0;old.proyecto.cota_terreno_m=0;
old.nodos=[{id:'A',x:-10000,y:0,z:6500},{id:'B',x:0,y:0,z:6500},{id:'C',x:10000,y:0,z:6500},{id:'D',x:20000,y:0,z:5700}];
old.tramos=[{id:'T1',desde:'A',hasta:'B',funcion:'cruce'},{id:'T2',desde:'B',hasta:'C',funcion:'cruce'},{id:'R',desde:'C',hasta:'D',funcion:'rampa'}];
old.soportes=[{id:'A',nodo:'A',cota_superior_mm:5000,cota_terreno_proyectado_mm:300},{id:'B',nodo:'B',cota_superior_mm:5000},{id:'C',nodo:'C',cota_superior_mm:5000,cota_terreno_proyectado_mm:-100}];old.fundaciones=[{id:'F',cota_superior_mm:0,pilotes:[{longitud_mm:10000,dx_mm:0,dy_mm:0}]}];
const {model,shiftMm}=io.rebaseToCrossing(old);
assert.equal(shiftMm,6500);assert.equal(model.proyecto.georreferencia.cota_m,106.5);
assert.equal(model.nodos[1].z,0);assert.equal(model.nodos[3].z,-800);
assert.equal(model.proyecto.cota_carretera_m,-6.5);assert.equal(model.proyecto.cota_terreno_m,-6.5);
assert.equal(model.soportes[0].cota_superior_mm,-1500);assert.equal(model.fundaciones[0].cota_superior_mm,-6500);
assert.equal(model.soportes[0].cota_terreno_proyectado_mm,-6200);
assert.equal(model.soportes[2].cota_terreno_proyectado_mm,-6600);
assert.ok(!Object.hasOwn(model.soportes[1],'cota_terreno_proyectado_mm'));
for(const s of [old.soportes[0],old.soportes[2]]){
 const before=old.nodos.find(n=>n.id===s.nodo),after=model.nodos.find(n=>n.id===s.nodo),rebased=model.soportes.find(x=>x.id===s.id);
 assert.deepEqual(io.localToWorld(old,before.x/1000,before.y/1000,s.cota_terreno_proyectado_mm/1000),io.localToWorld(model,after.x/1000,after.y/1000,rebased.cota_terreno_proyectado_mm/1000));
}
assert.equal(model.fundaciones[0].pilotes[0].longitud_mm,10000);
for(let i=0;i<old.nodos.length;i++){const a=old.nodos[i],b=model.nodos[i];assert.deepEqual(io.localToWorld(old,a.x/1000,a.y/1000,a.z/1000),io.localToWorld(model,b.x/1000,b.y/1000,b.z/1000));}
assert.equal(io.rebaseToCrossing(model).shiftMm,0);
assert.deepEqual(io.toInternal(io.toPortable(model)).proyecto,model.proyecto);
const noLegacy=structuredClone(old);delete noLegacy.proyecto.cota_carretera_m;delete noLegacy.proyecto.cota_terreno_m;
const rebasedNoLegacy=io.rebaseToCrossing(noLegacy).model;
assert.ok(!Object.hasOwn(rebasedNoLegacy.proyecto,'cota_carretera_m'));
assert.ok(!Object.hasOwn(rebasedNoLegacy.proyecto,'cota_terreno_m'));
assert.ok(!Object.hasOwn(rebasedNoLegacy.soportes[1],'cota_terreno_proyectado_mm'));
const tilted=structuredClone(old);tilted.nodos[1].z=7000;assert.equal(io.rebaseToCrossing(tilted).shiftMm,7000);
assert.throws(()=>io.rebaseToCrossing({...old,tramos:[]}),/eje principal/);
console.log('Top origin: two spans, midpoint, terrain, road, foundations, piles, world position and JSON passed');
