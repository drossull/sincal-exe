'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {arrowPair}=require('../../pasarela_bim/web/cotas.js');
const distance=(a,b)=>Math.hypot(b[0]-a[0],b[1]-a[1]);
test('GSG_COTAS conserva punta en cada extremo, proporción 3:1 y largo igual al texto al girar la cota',()=>{
 for(const [a,b] of [[[0,0],[100,0]],[[0,100],[0,0]],[[7,-9],[-93,91]]]){
  const original=structuredClone([a,b]),pair=arrowPair(a,b,11);assert.equal(pair.outside,false);
  for(const [i,head] of pair.heads.entries()){
   const [tip,left,right]=head,base=[(left[0]+right[0])/2,(left[1]+right[1])/2];assert.deepEqual(tip,i===0?a:b);
   assert(Math.abs(distance(tip,base)-11)<1e-10);assert(Math.abs(distance(left,right)-11/3)<1e-10);
   const other=i===0?b:a;assert((base[0]-tip[0])*(other[0]-tip[0])+(base[1]-tip[1])*(other[1]-tip[1])>0,'Las bases quedan dentro del intervalo.');
  }
  assert.deepEqual([a,b],original);
 }
});
test('cota corta conserva puntos de medida y lleva cuerpos y prolongaciones fuera del intervalo',()=>{
 const pair=arrowPair([0,0],[10,0],10);assert(pair.outside);assert.equal(pair.extensions.length,2);
 assert.deepEqual(pair.heads.map(p=>p[0]),[[0,0],[10,0]]);
 assert(pair.heads[0].slice(1).every(p=>p[0]<0));assert(pair.heads[1].slice(1).every(p=>p[0]>10));
 assert(pair.extensions[0][1][0]<-10);assert(pair.extensions[1][1][0]>20);
});
test('flechas escalan con el texto y descartan intervalos degenerados',()=>{
 const first=arrowPair([0,0],[100,0],10),scaled=arrowPair([0,0],[200,0],20);
 assert.deepEqual(scaled.heads,first.heads.map(h=>h.map(p=>p.map(v=>v*2))));
 assert.equal(arrowPair([0,0],[0,0],10),null);assert.equal(arrowPair([0,0],[100,0],NaN),null);assert.equal(arrowPair([0,0],[100,0],0),null);
});
