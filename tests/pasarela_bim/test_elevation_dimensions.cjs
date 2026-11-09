"use strict";
const test=require('node:test'),assert=require('node:assert/strict');
class Element {
  constructor(name){this.name=name;this.attributes={};this.children=[];}
  setAttribute(name,value){this.attributes[name]=String(value);}
  append(...items){this.children.push(...items);}
}
global.document={createElementNS:(_ns,name)=>new Element(name)};
global.VolumePreview=require('../../pasarela_bim/web/volumen.js');
const Axis=require('../../pasarela_bim/web/ejes.js');
const all=node=>[node,...node.children.flatMap(all)];
const dims=(view,kind)=>all(view.group).filter(n=>n.attributes['data-dimension-kind']===kind);
const values=(view,kind)=>dims(view,kind).map(n=>Number(n.attributes['data-value-mm']));
const text=node=>all(node).filter(n=>n.name==='text').map(n=>n.textContent).join(' ');
function fixture(){return {
  nodos:[{id:'A',tipo:'columna',x:0,y:0,z:0},{id:'B',tipo:'columna',x:10000,y:0,z:-680},{id:'C',tipo:'estribo',x:10000,y:10000,z:-1480},{id:'X',tipo:'columna',x:90000,y:0,z:0}],
  tramos:[{id:'V1',desde:'A',hasta:'B',familia:'box',ancho_mm:2000,retranqueo_inicio_mm:500,retranqueo_fin_mm:500,rasante:[{t:0,f:0},{t:.425,f:.5},{t:.575,f:.5},{t:1,f:1}]},{id:'V2',desde:'C',hasta:'B',familia:'box',ancho_mm:2000}],
  familias:{box:{tipo:'cajon',canto_mm:1000,losa_superior_mm:150,losa_inferior_mm:140,macizado_mm:500}},
  soportes:[{id:'SA',nodo:'A',fundacion:'F1',diametro_mm:1000,cota_superior_mm:-1500,cota_terreno_proyectado_mm:-5000},{id:'SB',nodo:'B',fundacion:'F2',diametro_mm:800,cota_superior_mm:-2300},{id:'SC',nodo:'C',fundacion:'F3',largo_mm:1000,ancho_mm:1500,cota_superior_mm:-3100}],
  fundaciones:[{id:'F1',nodos:['A'],largo_mm:3000,ancho_mm:3000,alto_mm:1000,cota_superior_mm:-6000,pilotes:[{id:'P1',dx_mm:0,dy_mm:0,diametro_mm:1200,longitud_mm:8000},{id:'P_OUT',dx_mm:0,dy_mm:2000,diametro_mm:1200,longitud_mm:100000}]},{id:'F2',nodos:['B'],largo_mm:3000,ancho_mm:3000,alto_mm:1200,cota_superior_mm:-6500},{id:'F3',nodos:['C'],largo_mm:3000,ancho_mm:3000,alto_mm:900,cota_superior_mm:-6000},{id:'FX',nodos:['X'],largo_mm:3000,ancho_mm:3000,alto_mm:10000,cota_superior_mm:-500000}],
  ejes:[{id:'ER',tipo:'recorrido',tramos:['V1','V2']},{id:'EC1',tipo:'apoyo',nodo:'A'},{id:'EC2',tipo:'apoyo',nodo:'B'},{id:'EE1',tipo:'apoyo',nodo:'C'}]
};}

test('cotas derivadas del corte: distancias entre ejes, altura variable, descanso, apoyos y pilotes visibles',()=>{
  const m=fixture(),before=structuredClone(m),view=Axis.elevation(m,'ER');
  assert.equal(view.developed,true);assert.deepEqual(view.stations,[0,10000,20000]);
  assert.deepEqual(values(view,'span'),[10000,10000]);assert.deepEqual(values(view,'total'),[20000]);
  assert.deepEqual(values(view,'station'),[0,10000,20000]);assert.deepEqual(values(view,'level'),[0,-680,-1480]);
  assert(Math.abs(values(view,'landing')[0]-1500)<1e-7);
  const beam=dims(view,'beam-height').filter(d=>d.attributes['data-element-id']==='V1');
  assert.deepEqual(beam.map(d=>Number(d.attributes['data-station-mm'])),[500,9500]);
  assert(Math.abs(Number(beam[0].attributes['data-value-mm'])-1000)<1e-8);
  assert(Math.abs(Number(beam[1].attributes['data-value-mm'])-1120)<1e-8);
  assert.deepEqual(values(view,'support-height'),[4500,4200,2900]);
  assert.deepEqual(values(view,'foundation-thickness'),[1000,1200,900]);assert.deepEqual(values(view,'pile-length'),[8000]);
  assert.equal(dims(view,'pile-length')[0].attributes['data-element-id'],'P1');
  assert.match(text(view.group),/1,500 m/);assert.match(text(view.group),/H 1,120 m/);
  assert.equal(all(view.group).find(n=>n.attributes.class==='elevation-dimensions').attributes['pointer-events'],'none');
  assert(Math.max(...view.bounds.map(p=>p[1]))<450,'La fundación ajena al eje y el pilote no intersectado no alteran el encuadre');
  assert.deepEqual(m,before,'Acotar no modifica la topología ni las familias');
});

test('el sentido inverso conserva alturas reales y reubica cada cota en su estación desarrollada',()=>{
  const m=fixture();m.ejes[0].tramos=['V2','V1'];
  const view=Axis.elevation(m,'ER'),beam=dims(view,'beam-height').filter(d=>d.attributes['data-element-id']==='V1');
  assert.deepEqual(values(view,'level'),[-1480,-680,0]);assert.deepEqual(values(view,'span'),[10000,10000]);
  assert.deepEqual(beam.map(d=>Number(d.attributes['data-station-mm'])),[19500,10500]);
  assert(Math.abs(Number(beam[0].attributes['data-value-mm'])-1000)<1e-8);
  assert(Math.abs(Number(beam[1].attributes['data-value-mm'])-1120)<1e-8);
  assert(Math.abs(values(view,'landing')[0]-1500)<1e-8);
});

test('ocultar cotas conserva el corte, identificadores de nodos/ejes y terreno puntual',()=>{
  const m=fixture(),shown=Axis.elevation(m,'ER'),hidden=Axis.elevation(m,'ER',{dimensions:false});
  assert(!all(hidden.group).some(n=>n.attributes['data-dimension-kind']||n.attributes.class==='elevation-dimensions'));
  assert.deepEqual(hidden.group.children.filter(n=>n.attributes.class==='projected-terrain-level'),shown.group.children.filter(n=>n.attributes.class==='projected-terrain-level'));
  for(const id of ['A','B','C','EC1','EC2','EE1','V1','V2'])assert(text(hidden.group).split(' ').includes(id));
  assert.equal(all(hidden.group).filter(n=>n.attributes.class==='beam-longitudinal-cut').length,2);
  assert(!/s 10,000 m|Z -0,680 m/.test(text(hidden.group)));
});

test('datos incompletos no inventan alturas y todas las coordenadas y rótulos quedan dentro del encuadre',()=>{
  const m=fixture();delete m.soportes[0].cota_superior_mm;delete m.fundaciones[1].alto_mm;m.soportes[2].fundacion='pendiente';
  const view=Axis.elevation(m,'ER');
  assert.deepEqual(dims(view,'support-height').map(d=>d.attributes['data-element-id']),['SB']);
  assert.deepEqual(dims(view,'foundation-thickness').map(d=>d.attributes['data-element-id']),['F1']);
  assert(all(view.group).every(n=>Object.values(n.attributes).every(v=>!v.includes('NaN')&&!v.includes('Infinity'))));
  const xs=view.bounds.map(p=>p[0]),ys=view.bounds.map(p=>p[1]),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  for(const n of all(view.group).filter(n=>n.name==='text')){
    const x=Number(n.attributes.x),y=Number(n.attributes.y),size=Number(n.attributes['font-size']||9),width=n.textContent.length*size*.55,anchor=n.attributes['text-anchor'],left=anchor==='middle'?x-width/2:anchor==='end'?x-width:x;
    assert(left>=minX-1e-8&&left+width<=maxX+1e-8&&y-size>=minY-1e-8&&y+3<=maxY+1e-8,`Rótulo fuera de encuadre: ${n.textContent}`);
  }
});

test('fundación y pilote compartidos no duplican sus cotas en un mismo corte recto',()=>{
  const m=fixture();m.nodos[2].x=20000;m.nodos[2].y=0;
  m.soportes[1].fundacion='F1';m.fundaciones[0].nodos=['A','B'];m.fundaciones[0].largo_mm=14000;
  const view=Axis.elevation(m,'ER');
  assert.equal(dims(view,'foundation-thickness').filter(d=>d.attributes['data-element-id']==='F1').length,1);
  assert.equal(dims(view,'pile-length').filter(d=>d.attributes['data-element-id']==='P1').length,1);
});
