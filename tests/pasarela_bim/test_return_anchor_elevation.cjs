"use strict";
const test=require('node:test'),assert=require('node:assert/strict');
global.PasarelaEditing=require('../../pasarela_bim/web/app.js');
global.ReturnSupports=require('../../pasarela_bim/web/retornos.js');
global.VolumePreview=require('../../pasarela_bim/web/volumen.js');
const Axis=require('../../pasarela_bim/web/ejes.js');
class Element{constructor(name){this.name=name;this.attributes={};this.children=[];}setAttribute(k,v){this.attributes[k]=String(v);}append(...items){this.children.push(...items);}}
global.document={createElementNS:(_ns,name)=>new Element(name)};
const all=n=>[n,...n.children.flatMap(all)];
const classIs=(n,name)=>(n.attributes.class||'').split(' ').includes(name);
function fixture(){return {version:1,proyecto:{id:'RET',nombre:'Retorno',estado:'conceptual',unidades:'mm'},
  nodos:[{id:'A',tipo:'encuentro',x:0,y:0,z:4000},{id:'B',tipo:'encuentro',x:6000,y:0,z:4000},{id:'C',tipo:'columna',x:3000,y:0,z:4000,anclaje_tramo:{tramo:'R',t:.5}}],
  tramos:[{id:'R',tipo:'retorno',funcion:'retorno',desde:'A',hasta:'B',familia:'losa',ancho_mm:2000}],familias:{losa:{tipo:'maciza',canto_mm:600}},
  soportes:[{id:'C',nodo:'C',fundacion:'F',diametro_mm:1000,cota_superior_mm:3400,cota_terreno_proyectado_mm:-500}],
  fundaciones:[{id:'F',nodos:['C'],tipo:'dado',largo_mm:3000,ancho_mm:3000,alto_mm:1000,cota_superior_mm:-1000,pilotes:[{id:'P',diametro_mm:800,longitud_mm:6000,dx_mm:0,dy_mm:0}]}],
  ejes:[{id:'ER',nombre:'Retorno',tipo:'recorrido',tramos:['R']},{id:'EC',nombre:'Cepa central',tipo:'apoyo',nodo:'C'}]};}

test('columna central en su estación, sin partir el retorno ni alterar el recorrido',()=>{
  const m=fixture(),before=structuredClone(m),path=Axis.walk(m,m.ejes[0]);
  assert.deepEqual(path.nodes.map(n=>n.id),['A','B']);assert.deepEqual(path.stations,[0,6000]);assert.equal(path.length,6000);assert.equal(path.edges.length,1);
  assert.deepEqual(path.additionalNodes.map(p=>[p.node.id,p.station,p.edgeIndex]),[['C',3000,0]]);
  const view=Axis.elevation(m,'ER',{selected:{type:'node',id:'C'}}),items=all(view.group);
  for(const name of ['support-longitudinal-cut','foundation-longitudinal-cut','pile-longitudinal-cut'])assert.equal(items.filter(n=>classIs(n,name)).length,1,name);
  assert.equal(items.filter(n=>classIs(n,'beam-longitudinal-cut')).length,1);
  const column=items.find(n=>classIs(n,'elevation-support'));assert.equal(column.attributes['data-select-id'],'C');assert(classIs(column,'selected'));assert.equal(column.attributes.tabindex,'0');
  const axis=items.find(n=>classIs(n,'elevation-axis'));assert.equal(axis.attributes['data-select-id'],'EC');
  const bubble=axis.children.find(n=>classIs(n,'elevation-axis-bubble'));assert.equal(Number(bubble.attributes.cx),42);
  const pile=items.find(n=>classIs(n,'elevation-pile'));assert.equal(pile.attributes['data-select-id'],'F');assert.equal(pile.attributes['data-select-pile-id'],'P');
  const centreStation=items.find(n=>n.attributes['data-dimension-kind']==='station'&&n.attributes['data-element-id']==='C');assert.equal(centreStation.attributes['data-value-mm'],'3000');
  const span=items.filter(n=>n.attributes['data-dimension-kind']==='span');assert.equal(span.length,1);assert.equal(span[0].attributes['data-value-mm'],'6000');
  assert(items.some(n=>classIs(n,'projected-terrain-level')&&n.attributes['data-node-id']==='C'));
  assert.deepEqual(m,before,'La vista sólo deriva geometría');
});

test('las estaciones interiores respetan el sentido inverso del recorrido',()=>{
  const m=fixture();m.nodos.push({id:'D',tipo:'encuentro',x:9000,y:0,z:4000});m.tramos.push({...m.tramos[0],id:'R2',desde:'D',hasta:'B'});m.ejes[0].tramos=['R2','R'];
  const path=Axis.walk(m,m.ejes[0]);assert.deepEqual(path.nodes.map(n=>n.id),['D','B','A']);assert.equal(path.additionalNodes[0].station,6000);assert.equal(path.length,9000);
  const view=Axis.elevation(m,'ER');assert.equal(all(view.group).filter(n=>classIs(n,'beam-longitudinal-cut')).length,2);
});

test('mover eje del retorno mueve su columna, fundación y pilotes sin modificar la fuente',()=>{
  const m=fixture(),before=structuredClone(m),plan=Axis.movePreview(m,'ER',{x:1200,y:2500});
  assert.deepEqual(m,before);assert.deepEqual(plan.nodos.map(n=>n.id),['A','B','C']);assert.deepEqual(plan.soportes_en_planta,['C']);
  assert.equal(plan.fundaciones_en_planta[0].after.x,4200);assert.equal(plan.fundaciones_en_planta[0].after.y,2500);
  Axis.applyMove(m,plan);assert.equal(m.nodos[2].x,4200);assert.equal(m.nodos[2].y,2500);assert.equal(m.nodos[2].z,4000);assert.equal(m.tramos.length,1);
  assert.equal(Axis.walk(m,m.ejes[0]).additionalNodes[0].station,3000);
});

test('mover el eje propio de la cepa central desplaza el retorno vinculado',()=>{
  const m=fixture(),plan=Axis.movePreview(m,'EC',{x:0,y:800});assert.deepEqual(plan.nodos.map(n=>n.id),['A','B','C']);Axis.applyMove(m,plan);
  assert(m.nodos.every(n=>n.y===800));assert.deepEqual(m.ejes[0].tramos,['R']);
  const fixed=fixture();fixed.nodos[2].xy_fijo=true;assert.throws(()=>Axis.movePreview(fixed,'ER',{x:1,y:0}),/fija/);
});

test('anclaje desactualizado o usado como extremo peatonal se rechaza',()=>{
  const stale=fixture();stale.nodos[2].x=3100;assert.throws(()=>Axis.walk(stale,stale.ejes[0]),/coordenadas/);
  const connected=fixture();connected.tramos.push({...connected.tramos[0],id:'BAD',desde:'C'});assert.throws(()=>Axis.walk(connected,connected.ejes[0]),/extremo peatonal/);
  for(const t of [0,1,NaN,true]){const m=fixture();m.nodos[2].anclaje_tramo.t=t;assert.throws(()=>Axis.walk(m,m.ejes[0]),/anclaje interior/);}
});

test('base compartida sin giro explícito usa su orientación efectiva al cortar dado y pilotes',()=>{
  const m=fixture();m.nodos=m.nodos.slice(0,2);m.nodos[0].tipo='columna';Object.assign(m.nodos[1],{tipo:'columna',x:0,y:6000});
  m.soportes=m.nodos.map(n=>({...m.soportes[0],id:n.id,nodo:n.id}));
  Object.assign(m.fundaciones[0],{nodos:['A','B'],largo_mm:9000,ancho_mm:2000,pilotes:[-2000,2000].map((dx,i)=>({id:`P${i+1}`,diametro_mm:800,longitud_mm:6000,dx_mm:dx,dy_mm:0}))});
  m.ejes=[m.ejes[0],...m.nodos.map(n=>({id:`EC${n.id}`,nombre:n.id,tipo:'apoyo',nodo:n.id}))];
  const before=structuredClone(m),implicit=all(Axis.elevation(m,'ER').group),shape=name=>implicit.filter(n=>classIs(n,name));
  assert.equal(shape('foundation-longitudinal-cut').length,1,'La base compartida se corta una sola vez');
  const xs=shape('foundation-longitudinal-cut')[0].attributes.points.split(' ').map(p=>Number(p.split(',')[0]));
  assert.equal(Math.min(...xs),-21);assert.equal(Math.max(...xs),105,'El corte mide los 9 m del largo orientado');
  assert.equal(shape('pile-longitudinal-cut').length,2,'Ambos pilotes sobre el eje local longitudinal intersectan el corte');
  const centres=shape('pile-longitudinal-cut').map(n=>{const xs=n.attributes.points.split(' ').map(p=>Number(p.split(',')[0]));return (Math.min(...xs)+Math.max(...xs))/2;});
  assert.deepEqual(centres,[14,70]);assert.deepEqual(m,before);
  m.fundaciones[0].angulo_deg=90;
  const explicit=all(Axis.elevation(m,'ER').group);
  for(const name of ['foundation-longitudinal-cut','pile-longitudinal-cut'])assert.deepEqual(explicit.filter(n=>classIs(n,name)).map(n=>n.attributes.points),shape(name).map(n=>n.attributes.points));
});
