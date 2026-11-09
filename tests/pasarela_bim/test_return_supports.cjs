"use strict";
const {test}=require('node:test');
const assert=require('node:assert/strict');
const ReturnSupports=require('../../pasarela_bim/web/retornos.js');
const ProjectIO=require('../../pasarela_bim/web/proyecto.js');
function fixture(){return {version:1,proyecto:{unidades:'mm'},nodos:[{id:'N1',tipo:'encuentro',x:0,y:0,z:0},{id:'N2',tipo:'encuentro',x:3000,y:4000,z:0}],tramos:[{id:'R1',desde:'N1',hasta:'N2',tipo:'retorno',funcion:'retorno',familia:'losa',ancho_mm:2000,rasante:[{t:0,f:0},{t:1,f:1}]}],familias:{losa:{tipo:'maciza',canto_mm:300,pendiente_transversal_pct:1}},soportes:[],fundaciones:[],ejes:[]};}
test('Central column anchors one continuous return, with no invented terrain level',()=>{
  const m=fixture(),before=structuredClone(m),p=ReturnSupports.preview(m,'R1',{layout:'central'});
  assert.deepEqual(m,before);assert.deepEqual(p.model.tramos,m.tramos);assert.equal(p.model.nodos.length,3);
  const n=p.model.nodos.find(n=>n.id===p.nodeIds[0]),s=p.model.soportes[0],f=p.model.fundaciones[0];
  assert.deepEqual(n.anclaje_tramo,{tramo:'R1',t:.5});assert.deepEqual([n.x,n.y,n.z],[1500,2000,0]);
  assert.equal(s.cota_superior_mm,-300);assert.equal(s.diametro_mm,1000);assert.equal(f.cota_superior_mm,-1300);
  assert.equal(Object.hasOwn(s,'cota_terreno_proyectado_mm'),false);assert.match(p.summary.warnings.join(' '),/terreno proyectado queda por definir/);
  const repeated=ReturnSupports.preview(p.model,'R1',{layout:'central'});assert.deepEqual(repeated.model,p.model);assert.deepEqual(repeated.summary.createdNodes,[]);
});
test('Two end columns can share an oriented foundation sized along the return',()=>{
  const p=ReturnSupports.preview(fixture(),'R1',{layout:'ends',shared:true,terrainMm:-6500}),f=p.model.fundaciones[0];
  assert.deepEqual(p.nodeIds,['N1','N2']);assert.equal(p.model.soportes.length,2);assert.equal(p.model.nodos.length,2);
  assert.equal(p.model.fundaciones.length,1);assert.equal(f.largo_mm,8000);assert.equal(f.ancho_mm,3000);assert.equal(f.cota_superior_mm,-6500);
  assert.ok(Math.abs(f.angulo_deg-Math.atan2(4000,3000)*180/Math.PI)<1e-10);
  for(const s of p.model.soportes){assert.equal(s.cota_superior_mm,-600);assert.equal(s.cota_terreno_proyectado_mm,-6500);assert.equal(s.fundacion,f.id);}
  assert.equal(ReturnSupports.describe(p.model,'R1').shared,true);assert.deepEqual(ReturnSupports.preview(p.model,'R1',{layout:'ends',shared:true}).model,p.model);
});
test('Individual bases and end-column top respect deeper adjacent families',()=>{
  const m=fixture();m.nodos.push({id:'N3',tipo:'encuentro',x:-5000,y:0,z:400});m.familias.cajon={tipo:'cajon',canto_mm:1000};
  m.tramos.push({id:'V1',desde:'N3',hasta:'N1',familia:'cajon',funcion:'rampa',ancho_mm:2000});
  const p=ReturnSupports.preview(m,'R1',{layout:'ends'});assert.equal(p.model.fundaciones.length,2);
  assert.equal(p.model.soportes.find(s=>s.nodo==='N1').cota_superior_mm,-1300);
  assert.equal(p.model.soportes.find(s=>s.nodo==='N2').cota_superior_mm,-600);
});
test('Switching layouts removes only unused generated supports and can be repeated',()=>{
  let p=ReturnSupports.preview(fixture(),'R1',{layout:'central'});const centreId=p.nodeIds[0],foundationId=p.foundationIds[0];
  p=ReturnSupports.preview(p.model,'R1',{layout:'ends',shared:true});assert.deepEqual(p.summary.removedNodes,[centreId]);assert.deepEqual(p.summary.removedFoundations,[foundationId]);
  assert.equal(p.model.nodos.length,2);assert.equal(p.model.soportes.length,2);
  p=ReturnSupports.preview(p.model,'R1',{layout:'central'});assert.equal(p.model.soportes.length,1);assert.equal(p.model.fundaciones.length,1);
  assert.equal(p.summary.removedSupports.length,2);assert.equal(p.summary.removedFoundations.length,1);assert.equal(p.model.nodos.find(n=>n.id==='N1').tipo,'encuentro');
  assert.deepEqual(ReturnSupports.preview(p.model,'R1',{layout:'central'}).model,p.model);
});
test('Pile-bearing, previously edited and shared foundations are never taken over',()=>{
  const m=ReturnSupports.preview(fixture(),'R1',{layout:'central'}).model,central=structuredClone(m.nodos.at(-1));
  m.fundaciones[0].pilotes=[{id:'P1',diametro_mm:1000,longitud_mm:10000,dx_mm:100,dy_mm:200}];
  const existing=structuredClone(m.fundaciones[0]),p=ReturnSupports.preview(m,'R1',{layout:'ends',shared:true});
  assert.deepEqual(p.model.fundaciones.find(f=>f.id===existing.id),existing);assert.deepEqual(p.model.nodos.find(n=>n.id===central.id),central);
  assert.equal(p.summary.preservedSupports.length,1);assert.equal(ReturnSupports.describe(p.model,'R1').layout,'mixed');
  const again=ReturnSupports.preview(p.model,'R1',{layout:'ends',shared:true});assert.deepEqual(again.model,p.model);
  const ordinary=ReturnSupports.preview(fixture(),'R1',{layout:'ends'}).model;delete ordinary.soportes[0].origen_retorno;delete ordinary.fundaciones[0].origen_retorno;
  const before=structuredClone(ordinary.fundaciones),shared=ReturnSupports.preview(ordinary,'R1',{layout:'ends',shared:true});
  assert.deepEqual(shared.model.fundaciones,before);assert.equal(shared.summary.shared,false);assert.match(shared.summary.warnings.join(' '),/asociación de fundaciones/);
});
test('Other ramp use preserves end supports when choosing central support',()=>{
  const m=fixture();m.nodos.push({id:'N3',tipo:'encuentro',x:-5000,y:0,z:400});m.tramos.push({id:'V1',desde:'N3',hasta:'N1',familia:'losa',funcion:'rampa'});
  const ends=ReturnSupports.preview(m,'R1',{layout:'ends'}).model,p=ReturnSupports.preview(ends,'R1',{layout:'central'});
  assert.ok(p.model.soportes.some(s=>s.nodo==='N1'));assert.ok(!p.model.soportes.some(s=>s.nodo==='N2'));
  assert.deepEqual(p.summary.preservedSupports,['N1']);assert.equal(ReturnSupports.describe(p.model,'R1').layout,'mixed');
  const shared=ReturnSupports.preview(m,'R1',{layout:'ends',shared:true}).model,base=structuredClone(shared.fundaciones[0]),central=ReturnSupports.preview(shared,'R1',{layout:'central'});
  assert.deepEqual(central.model.fundaciones.find(f=>f.id===base.id),base);
  assert.deepEqual(central.summary.preservedSupports,['N1','N2']);
});
test('Moving return endpoints synchronizes its centre and column top, with terrain and foundation Z fixed',()=>{
  const m=ReturnSupports.preview(fixture(),'R1',{layout:'central',terrainMm:-5000}).model,f=structuredClone(m.fundaciones[0]);
  for(const n of m.nodos.slice(0,2)){n.x+=1000;n.y-=2000;n.z+=500;}
  const changes=ReturnSupports.sync(m);assert.equal(changes.length,1);assert.deepEqual(changes[0].after,{x:2500,y:0,z:500});
  assert.equal(m.soportes[0].cota_superior_mm,200);assert.equal(m.soportes[0].cota_terreno_proyectado_mm,-5000);assert.deepEqual(m.fundaciones[0],f);
  assert.deepEqual(ReturnSupports.sync(m),[]);
});
test('JSON metre exchange preserves attachment and support identity',()=>{
  const m=ReturnSupports.preview(fixture(),'R1',{layout:'central',terrainMm:-5000}).model;
  const portable=ProjectIO.toPortable(m),roundtrip=ProjectIO.toInternal(portable);
  assert.deepEqual(roundtrip.nodos,m.nodos);assert.deepEqual(roundtrip.soportes,m.soportes);assert.deepEqual(roundtrip.fundaciones,m.fundaciones);
});
test('Invalid return or layout cannot create an accidental support',()=>{
  const m=fixture();assert.throws(()=>ReturnSupports.preview(m,'R1',{layout:'three'}),/central/);
  assert.throws(()=>ReturnSupports.preview(m,'R1',{terrainMm:NaN}),/terreno/);m.nodos[1].z=200;
  assert.throws(()=>ReturnSupports.preview(m,'R1',{}),/horizontal/);m.tramos[0].funcion='rampa';
  assert.throws(()=>ReturnSupports.preview(m,'R1',{}),/retorno/);
});
