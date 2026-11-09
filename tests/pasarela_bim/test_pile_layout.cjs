'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const Piles=require('../../pasarela_bim/web/pilotes.js');
const foundation={id:'F1',nodos:['A','B'],largo_mm:5000,ancho_mm:3000};
const pile=(id,x,y,diameter=1000)=>({id,uuid:`uuid-${id}`,dx_mm:x,dy_mm:y,diametro_mm:diameter,longitud_mm:10000});

test('pilotes contenidos, separados o tangentes; el validador no cambia el proyecto',()=>{
  const draft=[pile('P1',-500,0),pile('P2',500,0),pile('P3',2000,1000)],before=structuredClone(draft);
  assert.deepEqual(Piles.validateLayout(foundation,draft),{valid:true,errors:[],invalidPileIds:[]});
  assert.deepEqual(draft,before);
  const invalid=Piles.validateLayout(foundation,[pile('P1',-499,0),pile('P2',499,0),pile('P3',2001,0)]);
  assert.equal(invalid.valid,false);assert.deepEqual(new Set(invalid.invalidPileIds),new Set(['P1','P2','P3']));
  assert(invalid.errors.some(error=>error.includes('superponen')));assert(invalid.errors.some(error=>error.includes('dentro')));
});

test('datos vacíos, infinitos, dimensiones negativas e identificaciones repetidas se bloquean',()=>{
  for(const bad of [{diametro_mm:0},{longitud_mm:-1},{dx_mm:NaN},{dy_mm:Infinity},{id:''}])assert.equal(Piles.validateLayout(foundation,[{...pile('P',0,0),...bad}]).valid,false);
  assert.equal(Piles.validateLayout({...foundation,largo_mm:NaN},[]).valid,false);
  assert.equal(Piles.validateLayout(foundation,[pile('P',-1000,0),pile('P',1000,0)]).valid,false);
  const legacy=pile('P',0,0);delete legacy.dx_mm;delete legacy.dy_mm;
  assert.equal(Piles.validateLayout(foundation,[legacy]).valid,true);
  assert.equal(Piles.validateLayout(foundation,[]).valid,true);
});

test('planta de apoyos usa el centro y giro efectivo de la fundación compartida',()=>{
  const m={nodos:[{id:'A',x:1000,y:2000},{id:'B',x:1000,y:6000},{id:'C',x:0,y:0}],soportes:[{id:'SA',nodo:'A',fundacion:'F1',diametro_mm:800},{id:'SB',nodo:'B',fundacion:'F1',largo_mm:1000,ancho_mm:600},{id:'SC',nodo:'C',fundacion:'F2',diametro_mm:900}]};
  const before=structuredClone(m),layout=Piles.supportLayout(m,foundation);
  assert.deepEqual(layout.centre,[1000,4000]);assert(Math.abs(layout.angle-Math.PI/2)<1e-12);assert.equal(layout.nodes.length,2);
  assert(Math.abs(layout.nodes[0].x+2000)<1e-9);assert(Math.abs(layout.nodes[0].y)<1e-9);assert.equal(layout.nodes[0].shape,'circle');assert.equal(layout.nodes[0].rx,400);
  assert.equal(layout.nodes[1].shape,'rectangle');assert.equal(layout.nodes[1].rx,500);assert.equal(layout.nodes[1].ry,300);
  const explicit=Piles.supportLayout(m,{...foundation,angulo_deg:0});assert.equal(explicit.angle,0);assert.equal(explicit.nodes[0].x,0);assert.equal(explicit.nodes[0].y,-2000);
  assert.deepEqual(m,before);
});

test('apoyos sin ubicación o sin dimensiones no producen NaN ni inventan geometría',()=>{
  const absent=Piles.supportLayout({nodos:[],soportes:[{id:'S',nodo:'A',fundacion:'F1'}]},foundation);
  assert.deepEqual(absent,{centre:[0,0],angle:0,located:false,nodes:[]});
  const m={nodos:[{id:'A',x:0,y:0},{id:'B',x:NaN,y:0}],soportes:[{id:'S',nodo:'A',fundacion:'F1'}]};
  const layout=Piles.supportLayout(m,foundation);assert.equal(layout.nodes[0].rx,0);assert.equal(layout.nodes[0].ry,0);assert.equal(layout.nodes[0].x,0);
});

test('distancias editadas mueven sólo el pilote seleccionado y conservan orientación al editar entre centros',()=>{
  const a=pile('A',4000,5000),b=pile('B',1000,1000),beforeA=structuredClone(a),beforeB=structuredClone(b);
  const x=Piles.setSpacing(a,b,{dx:-1500});assert.equal(x.dx_mm,-500);assert.equal(x.dy_mm,5000);
  const y=Piles.setSpacing(a,b,{dy:2000});assert.equal(y.dx_mm,4000);assert.equal(y.dy_mm,3000);
  const doubled=Piles.setSpacing(a,b,{distance:10000});assert(Math.abs(doubled.dx_mm-7000)<1e-8);assert(Math.abs(doubled.dy_mm-9000)<1e-8);
  const north=Piles.setSpacing(a,b,{angle:90});assert(Math.abs(north.dx_mm-1000)<1e-8);assert(Math.abs(north.dy_mm-6000)<1e-8);
  assert.throws(()=>Piles.setSpacing(a,b,{distance:-1}));assert.throws(()=>Piles.setSpacing(a,b,{angle:NaN}));
  assert.deepEqual(a,beforeA);assert.deepEqual(b,beforeB);assert.equal(doubled.uuid,a.uuid);
});

test('nuevos identificadores no colisionan con ninguna colección ni pilotes de otras fundaciones',()=>{
  const model={nodos:[{id:'P1'}],tramos:[{id:'P2'}],soportes:[{id:'P3'}],ejes:[{id:'P4'}],fundaciones:[{id:'P5',pilotes:[{id:'P6'}]}]};
  assert.equal(Piles.nextPileId(model,[{id:'P7'}]),'P8');
});
