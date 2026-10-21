"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const {createBridge}=require("../../pasarela_bim/web/integracion.js");

test("estado del editor se entrega sólo al origen enlazado y ready una sola vez",()=>{
  const messages=[],origin="http://127.0.0.1:8765";
  const bridge=createBridge({parentOrigin:origin,embedded:true,send:(data,target)=>messages.push({data,target})});
  bridge.ready();bridge.ready();bridge.setDirty(true);bridge.setDirty(true);bridge.setDirty(false);
  assert.deepEqual(messages.map(m=>m.data),[
    {type:"pasarela:ready",dirty:false,busy:false},
    {type:"pasarela:state",dirty:true,busy:false},
    {type:"pasarela:state",dirty:false,busy:false}
  ]);
  assert.ok(messages.every(m=>m.target===origin));
  assert.equal(bridge.shouldWarn(),false);
});

test("tareas simultáneas mantienen busy hasta que termina la última",()=>{
  const bridge=createBridge();
  bridge.setBusy("generation",true);bridge.setBusy("site-import",true);
  bridge.setBusy("site-import",false);bridge.setDirty(false);
  assert.deepEqual(bridge.snapshot(),{dirty:false,busy:true});assert.equal(bridge.shouldWarn(),true);
  bridge.setBusy("generation",false);assert.equal(bridge.shouldWarn(),false);
  bridge.setDirty(true);assert.equal(bridge.shouldWarn(),true);
});

test("standalone y orígenes inválidos nunca reciben postMessage",()=>{
  for(const parentOrigin of ["", "*", "https://other.test", "http://127.0.0.1:99999", "http://127.0.0.1:8765/"]){
    const bridge=createBridge({parentOrigin,embedded:true,send:()=>assert.fail("origen no autorizado")});
    bridge.ready();bridge.setDirty(true);assert.equal(bridge.embedded,false);assert.equal(bridge.shouldWarn(),true);
  }
  const standalone=createBridge({parentOrigin:"http://127.0.0.1:8765",embedded:false,send:()=>assert.fail("standalone")});
  standalone.ready();standalone.setDirty(true);assert.equal(standalone.embedded,false);
});
