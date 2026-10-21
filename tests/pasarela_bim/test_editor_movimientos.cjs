"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {connectedIds,movementPlan,applyMovement,renameEntity,resolveElevation,resolveDirection,checkSlopeRules} = require("../../pasarela_bim/web/app.js");
function model() {
  return {
    nodos:[{id:"A",x:0,y:0,z:6000},{id:"B",x:5000,y:0,z:6000},{id:"C",x:10000,y:0,z:6000,cota_fija:true}],
    tramos:[{id:"V1",desde:"A",hasta:"B"},{id:"V2",desde:"B",hasta:"C"}],
    soportes:[{id:"A",nodo:"A",fundacion:"F1",cota_superior_mm:4800},{id:"B",nodo:"B",fundacion:"F1",cota_superior_mm:4800}],
    fundaciones:[{id:"F1",nodos:["A","B"],cota_superior_mm:-1000,pilotes:[{id:"P1"}]}]
  };
}
test("una cota fija se conserva al desplazar el recorrido y sus soportes",()=>{
  const m=model(), before=structuredClone(m), plan=movementPlan(m,connectedIds(m,"A"),{x:0,y:0,z:500});
  assert.deepEqual(m,before,"la vista previa no modifica el proyecto");
  assert.deepEqual(plan.omitidos,["C"]);assert.equal(plan.fundaciones.length,0);
  applyMovement(m,plan);assert.equal(m.nodos[0].z,6500);assert.equal(m.nodos[2].z,6000);
  assert.equal(m.soportes[0].cota_superior_mm,5300);assert.equal(m.fundaciones[0].cota_superior_mm,-1000);
});
test("una fundación compartida sólo acompaña si todos sus nodos se trasladan explícitamente",()=>{
  const m=model();assert.equal(movementPlan(m,["A"],{z:500},true).fundaciones.length,0);
  const plan=movementPlan(m,["A","B"],{z:500},true);assert.equal(plan.fundaciones.length,1);
  applyMovement(m,plan);assert.equal(m.fundaciones[0].cota_superior_mm,-500);
});
test("una cota fija impide trasladar la fundación compartida",()=>{
  const m=model();m.nodos[1].cota_fija=true;
  assert.equal(movementPlan(m,["A","B"],{z:500},true).fundaciones.length,0);
});
test("editar una dirección desplaza su rama y conserva las cotas",()=>{
  const m=model(), ids=connectedIds(m,"B","V1");assert.deepEqual(ids,["B","C"]);
  applyMovement(m,movementPlan(m,ids,{x:-5000,y:5000,z:0}));
  assert.deepEqual(m.nodos.map(n=>[n.x,n.y,n.z]),[[0,0,6000],[0,5000,6000],[5000,5000,6000]]);
});
test("un circuito se reconoce antes de proponer mover una rama que contiene el origen",()=>{
  const m=model();m.tramos.push({id:"V3",desde:"C",hasta:"A"});
  assert.ok(connectedIds(m,"B","V1").includes("A"));
});
test("renombrar un nodo conserva todas sus relaciones y la identidad persistente",()=>{
  const m=model();m.nodos[0].uuid="stable-node";m.soportes[0].uuid="stable-support";
  renameEntity(m,"node","A","C1");assert.equal(m.tramos[0].desde,"C1");
  assert.equal(m.soportes[0].id,"C1");assert.equal(m.soportes[0].nodo,"C1");
  assert.equal(m.fundaciones[0].nodos[0],"C1");assert.equal(m.nodos[0].uuid,"stable-node");assert.equal(m.soportes[0].uuid,"stable-support");
});
test("renombrar no admite colisiones entre tipos de entidad ni pilotes",()=>{
  for(const id of ["V1","F1","P1",""])assert.throws(()=>renameEntity(model(),"node","A",id));
});
test("un desplazamiento no finito se rechaza antes de generar una vista previa",()=>{
  assert.throws(()=>movementPlan(model(),["A"],{z:NaN}));
});
function rampModel(){return {
  nodos:[{id:"C1",x:0,y:0,z:6500},{id:"C2",x:30000,y:0,z:6500},{id:"N1",x:0,y:20000,z:4900},{id:"N2",x:2000,y:20000,z:4900}],
  tramos:[{id:"V1",desde:"C1",hasta:"C2",funcion:"cruce"},{id:"R1",desde:"C1",hasta:"N1",funcion:"rampa"},{id:"D1",desde:"N1",hasta:"N2",funcion:"descanso"}],
  soportes:[{id:"N1",nodo:"N1",fundacion:"F1",cota_superior_mm:3500}],
  fundaciones:[{id:"F1",nodos:["N1"],cota_superior_mm:0}]
};}
test("cambiar cota compensa longitud de la rampa al 8 % y conserva el atravieso",()=>{
  const m=rampModel(),before=structuredClone(m),plan=resolveElevation(m,"N1",-400);
  assert.deepEqual(m,before);applyMovement(m,plan);checkSlopeRules(m);
  assert.deepEqual(m.nodos[0],before.nodos[0]);assert.deepEqual(m.nodos[1],before.nodos[1]);
  assert.equal(m.nodos[2].y,25000);assert.equal(m.nodos[2].z,4500);
  assert.equal(m.nodos[3].y,25000);assert.equal(m.nodos[3].z,4500);
  assert.equal(m.soportes[0].cota_superior_mm,3100);assert.equal(m.fundaciones[0].cota_superior_mm,0);
  assert.equal(Math.abs(m.nodos[2].z-m.nodos[0].z)/Math.hypot(m.nodos[2].x,m.nodos[2].y),.08);
});
test("no se aplica una compensación de longitud sobre un circuito",()=>{
  const m=rampModel();m.tramos.push({id:"CICLO",desde:"N2",hasta:"C2",funcion:"escalera"});
  assert.throws(()=>resolveElevation(m,"N1",-400),/circuito/);
});
test("dos anclas en planta bloquean una compensación incompatible",()=>{
  const m=rampModel();m.nodos[0].xy_fijo=true;m.nodos[2].xy_fijo=true;
  assert.throws(()=>resolveElevation(m,"N1",-400),/N1.*posición fija/);
});
test("la cota fija de un descanso impide mover parcialmente su plano horizontal",()=>{
  const m=rampModel();m.nodos[3].cota_fija=true;
  assert.throws(()=>resolveElevation(m,"N1",-400),/N2.*cota fija/);
});
test("el cambio global de cota conserva largos, cotas relativas y el 8 %",()=>{
  const m=rampModel();applyMovement(m,resolveElevation(m,"C1",1000,{scope:"component"}));checkSlopeRules(m);
  assert.equal(m.nodos[2].y,20000);assert.equal(m.nodos[2].z,5900);
});
test("cambiar dirección y longitud de rampa ajusta desnivel de toda su rama",()=>{
  const m=rampModel();applyMovement(m,resolveDirection(m,"R1",[-1,0],10000));checkSlopeRules(m);
  assert.deepEqual([m.nodos[2].x,m.nodos[2].y,m.nodos[2].z],[-10000,0,5700]);
  assert.deepEqual([m.nodos[3].x,m.nodos[3].y,m.nodos[3].z],[-8000,0,5700]);
});
test("una rasante con descanso interno conserva el 8 % sólo en la parte inclinada",()=>{
  const m=rampModel();m.tramos[1].rasante=[{t:0,f:0},{t:.2,f:0},{t:1,f:1}];m.nodos[2].y=25000;m.nodos[3].y=25000;
  applyMovement(m,resolveElevation(m,"N1",-400));checkSlopeRules(m);
  assert.equal(m.nodos[2].y,31250);
});
test("mover una coordenada libre no permite introducir una pendiente distinta de 8 %",()=>{
  const m=rampModel();m.nodos[2].y=19000;assert.throws(()=>checkSlopeRules(m),/8 %/);
});
test("renombrar nodos y tramos conserva los ejes y sus UUID",()=>{
  const m=model();m.ejes=[{id:"EA1",uuid:"axis-main",tipo:"atravieso",tramos:["V1","V2"]},{id:"EC1",uuid:"axis-support",tipo:"apoyo",nodo:"A"}];
  renameEntity(m,"node","A","NUEVO");assert.equal(m.ejes[1].nodo,"NUEVO");
  renameEntity(m,"edge","V1","R1");assert.deepEqual(m.ejes[0].tramos,["R1","V2"]);assert.equal(m.ejes[0].uuid,"axis-main");
  renameEntity(m,"axis","EA1","EJE_PRINCIPAL");assert.equal(m.ejes[0].id,"EJE_PRINCIPAL");assert.equal(m.ejes[0].uuid,"axis-main");
});
test("los identificadores de ejes participan en la unicidad global",()=>{
  const m=model();m.ejes=[{id:"EA1",tramos:["V1"]}];assert.throws(()=>renameEntity(m,"node","A","EA1"));
});
