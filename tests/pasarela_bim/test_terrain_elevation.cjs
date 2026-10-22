"use strict";
const test=require('node:test'),assert=require('node:assert/strict');
const Axis=require('../../pasarela_bim/web/ejes.js');

class Element {
  constructor(name){this.name=name;this.attributes={};this.children=[];}
  setAttribute(name,value){this.attributes[name]=String(value);}
  append(...items){this.children.push(...items);}
}
global.document={createElementNS:(_ns,name)=>new Element(name)};
const markers=view=>view.group.children.filter(e=>e.attributes.class==='projected-terrain-level');
function fixture(){return {
  nodos:[{id:'A',tipo:'columna',x:1000,y:2000,z:0},{id:'B',tipo:'columna',x:11000,y:2000,z:0},{id:'C',tipo:'columna',x:21000,y:2000,z:0}],
  tramos:[{id:'AB',desde:'A',hasta:'B',familia:'M'},{id:'BC',desde:'B',hasta:'C',familia:'M'}],familias:{M:{canto_mm:1000}},
  soportes:[{id:'SA',nodo:'A',fundacion:'F',diametro_mm:800,cota_superior_mm:-1500,cota_terreno_proyectado_mm:-5000},
    {id:'SB',nodo:'B',fundacion:'F',diametro_mm:800,cota_superior_mm:-1500,cota_terreno_proyectado_mm:-5500},
    {id:'SC',nodo:'C',fundacion:'FC',diametro_mm:800,cota_superior_mm:-1500}],
  fundaciones:[{id:'F',nodos:['A','B'],largo_mm:13000,ancho_mm:2500,alto_mm:1000,cota_superior_mm:-6000}],
  ejes:[{id:'ER',tipo:'recorrido',tramos:['AB','BC']},{id:'EA',tipo:'apoyo',nodo:'A'},{id:'EB',tipo:'apoyo',nodo:'B'}]
};}

test('terreno proyectado usa el centro de cada apoyo y niveles propios sobre una fundación compartida',()=>{
  const m=fixture(),before=structuredClone(m),view=Axis.elevation(m,'ER'),levels=markers(view);
  assert.equal(levels.length,2);
  for(const [i,level] of levels.entries()){
    assert.equal(level.attributes['data-support-id'],['SA','SB'][i]);
    assert.equal(level.attributes['data-node-id'],['A','B'][i]);
    const circle=level.children.find(e=>e.name==='circle'),line=level.children.find(e=>e.name==='line'),text=level.children.find(e=>e.name==='text');
    assert.equal(Number(circle.attributes.cx),i*140); // 10 m between support centres, not footing centre.
    assert.equal(Number(circle.attributes.cy),[70,77][i]);
    assert.equal((Number(line.attributes.x1)+Number(line.attributes.x2))/2,Number(circle.attributes.cx));
    assert.equal(Number(line.attributes.x2)-Number(line.attributes.x1),22);
    assert.equal(text.attributes['text-anchor'],'middle');
    assert.match(text.textContent,/Terreno proyectado -5\.[05]00 m/);
    assert.equal(level.children.some(e=>e.name==='polyline'||e.name==='polygon'),false);
  }
  assert.deepEqual(m,before,'Renderizar la cota no modifica soportes ni fundaciones');
});

test('ausencia de cota no inventa terreno; encuadre incluye cotas extremas',()=>{
  const m=fixture();for(const support of m.soportes)delete support.cota_terreno_proyectado_mm;
  assert.equal(markers(Axis.elevation(m,'ER')).length,0);
  m.soportes[0].cota_terreno_proyectado_mm=-15000;m.soportes[1].cota_terreno_proyectado_mm=2000;
  const view=Axis.elevation(m,'ER');
  assert.ok(Math.max(...view.bounds.map(p=>p[1]))>210);
  assert.ok(Math.min(...view.bounds.map(p=>p[1])) < -28);
  for(const level of markers(view)){const c=level.children.find(e=>e.name==='circle');assert.ok(view.bounds.some(p=>p[1]===Number(c.attributes.cy)));}
});
