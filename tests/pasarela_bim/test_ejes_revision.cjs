"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const Axis = require("../../pasarela_bim/web/ejes.js");
global.ProjectIO = require("../../pasarela_bim/web/proyecto.js");
global.PasarelaEditing = require("../../pasarela_bim/web/app.js");

function modelo() {
  return {version:1,proyecto:{id:"p",nombre:"Revisión",estado:"conceptual",unidades:"mm"},
    nodos:[{id:"A",tipo:"estribo",x:-2000,y:0,z:5000},{id:"B",tipo:"estribo",x:2000,y:0,z:5000}],
    tramos:[{id:"AB",desde:"A",hasta:"B",funcion:"descanso",tipo:"viga",familia:"losa",ancho_mm:2000}],
    familias:{losa:{tipo:"maciza",canto_mm:200}},
    soportes:[{id:"A",nodo:"A",fundacion:"F",largo_mm:2000,ancho_mm:1000,cota_superior_mm:4000},
              {id:"B",nodo:"B",fundacion:"F",largo_mm:2000,ancho_mm:1000,cota_superior_mm:4000}],
    fundaciones:[{id:"F",nodos:["A","B"],largo_mm:6000,ancho_mm:1500,alto_mm:500,cota_superior_mm:0,pilotes:[]}],
    ejes:[{id:"R",tipo:"recorrido",nombre:"Ruta",tramos:["AB"]},
          {id:"EA",tipo:"apoyo",nombre:"A",nodo:"A"},{id:"EB",tipo:"apoyo",nombre:"B",nodo:"B"}]};
}

test("renombrar tramo no agrega referencias longitudinales a ejes de apoyo",()=>{
  const m=modelo();m.tramos[0].id="RENOMBRADO";
  Axis.renameReferences(m,"edge","AB","RENOMBRADO");
  assert.deepEqual(m.ejes[0].tramos,["RENOMBRADO"]);
  for(const a of m.ejes.filter(a=>a.tipo==="apoyo"))assert.equal(Object.hasOwn(a,"tramos"),false);
});

test("cambio de función reconcilia categoría y creación rechaza categoría incompatible",()=>{
  const m=modelo();m.tramos[0].funcion="cruce";Axis.reconcile(m);
  const owner=m.ejes.find(a=>a.tramos?.includes("AB"));
  assert.equal(owner.tipo,"atravieso");
  const invalid=modelo();invalid.ejes=[];
  assert.throws(()=>Axis.create(invalid,{tipo:"atravieso",nombre:"Incompatible",tramos:["AB"]}));
});

test("crear eje exige referencias exclusivas, identidad única y principal booleano",()=>{
  for(const params of [
    {tipo:"apoyo",nodo:"A",tramos:["AB"]},
    {tipo:"recorrido",tramos:["AB"],nodo:"A"},
    {tipo:"recorrido",tramos:["AB"],nombre:"   "},
    {tipo:"recorrido",tramos:["AB"],id:"   "},
    {tipo:"recorrido",tramos:["AB"],principal:"no"}
  ]){
    const m=modelo();m.ejes=[];
    assert.throws(()=>Axis.create(m,params),JSON.stringify(params));
    assert.equal(m.ejes.length,0);
  }
  const duplicate=modelo();duplicate.ejes=[{...duplicate.ejes[0],uuid:"identidad-unica"}];
  assert.throws(()=>Axis.create(duplicate,{tipo:"apoyo",nodo:"A",uuid:"identidad-unica"}));
});

test("huella rectangular real permite mover estribo dentro del dado compartido",()=>{
  const m=modelo(),original=structuredClone(m);
  const p=Axis.movePreview(m,"EA",{x:100,y:0});
  assert.equal(p.modelo_resultante.nodos[0].x,-1900);
  assert.deepEqual(m,original);
  assert.equal(p.fundaciones_en_planta[0].after.x,50);
});

test("marco de fundación respeta orden de sus nodos, independiente del inventario",()=>{
  const m=modelo();m.fundaciones[0].nodos=["B","A"];
  const p=Axis.movePreview(m,"R",{x:100,y:0});
  assert.ok(Math.abs(Math.abs(p.fundaciones_en_planta[0].before.angle)-Math.PI)<1e-10);
  assert.ok(Math.abs(Math.abs(p.fundaciones_en_planta[0].after.angle)-Math.PI)<1e-10);
});

test("recentrado con norte oblicuo conserva posiciones mundiales fuera del alcance y cota",()=>{
  const m=modelo();m.ejes[0].tipo="atravieso";m.ejes[0].principal=true;m.tramos[0].funcion="cruce";
  m.proyecto.georreferencia={este_m:350000,norte_m:6000000,cota_m:120,norte_desde_x_horario_deg:35};
  m.nodos.push({id:"EXTERIOR",tipo:"encuentro",x:15000,y:10000,z:3500,xy_fijo:true});
  m.emplazamiento={planta:{entidades:[{tipo:"punto",puntos:[[350010,6000005]]}]}};
  const before=new Map(m.nodos.map(n=>[n.id,ProjectIO.localToWorld(m,n.x/1000,n.y/1000,n.z/1000)]));
  const original=structuredClone(m),p=Axis.movePreview(m,"R",{x:1500,y:-2000});
  assert.deepEqual(m,original);Axis.applyMove(m,p);
  assert.deepEqual(m.emplazamiento,original.emplazamiento);
  assert.equal(m.proyecto.georreferencia.cota_m,120);
  assert.equal((m.nodos[0].x+m.nodos[1].x)/2,0);
  assert.equal((m.nodos[0].y+m.nodos[1].y)/2,0);
  for(const n of m.nodos){
    const actual=ProjectIO.localToWorld(m,n.x/1000,n.y/1000,n.z/1000);
    const expected=n.id==="EXTERIOR"?before.get(n.id):ProjectIO.localToWorld(original,(original.nodos.find(o=>o.id===n.id).x+1500)/1000,-2,n.z/1000);
    actual.forEach((v,i)=>assert.ok(Math.abs(v-expected[i])<1e-7));
  }
});
