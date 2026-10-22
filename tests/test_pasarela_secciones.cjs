// Ejecutar con Node: node tests/test_pasarela_secciones.cjs
"use strict";
const assert = require("node:assert/strict");
const sections = require("../pasarela_bim/web/secciones.js");
const example = require("../pasarela_bim/ejemplos/los_batros.json");

for (const [id, family] of Object.entries(example.familias)) {
  assert.deepEqual(sections.validate(family, 2000), [], id);
}
const box = sections.defaults("cajon");
const geometry = sections.geometry(box, 2000);
assert.equal(geometry.outer.length, 9);
assert.equal(geometry.inner.length, 4);
const winged=sections.withWingWidth({...box,canto_mm:1450},2000,370);
assert.deepEqual(sections.validate(winged,2000),[]);
assert.equal(winged.ancho_alma_superior_mm,1260);
const wingedGeometry=sections.geometry(winged,2000);
const crowned={...winged,pendiente_transversal_pct:1};
assert.deepEqual(sections.geometry(crowned,2000).outer.slice(0,3),[[-1000,10],[0,0],[1000,10]]);
assert.deepEqual(sections.geometry(crowned,2000).inner,wingedGeometry.inner);
assert.deepEqual(sections.validate(crowned,2000),[]);
for(const slope of [-1,0,2,NaN,Infinity,15])assert(sections.validate({...crowned,pendiente_transversal_pct:slope},2000).length);
const io=require('../pasarela_bim/web/proyecto.js');
const saved=io.toInternal(io.toPortable({...example,familias:{...example.familias,crowned}}));
assert.equal(saved.familias.crowned.pendiente_transversal_pct,1);
const volume=require('../pasarela_bim/web/volumen.js');
const edge={desde:'a',hasta:'b',ancho_mm:2000,familia:'box'};
const faces=volume.faces({nodos:[{id:'a',x:0,y:0,z:5000},{id:'b',x:10000,y:0,z:5800}],familias:{box:crowned}},edge);
assert.deepEqual(faces[0].slice(0,3),[[0,-1000,4990],[0,0,5000],[0,1000,4990]]);
assert.deepEqual(faces[1].slice(0,3),[[10000,-1000,5790],[10000,0,5800],[10000,1000,5790]]);
assert.equal(wingedGeometry.outer[3][0]-wingedGeometry.outer[4][0],370);
assert.equal(wingedGeometry.outer[7][0]-wingedGeometry.outer[8][0],370);
assert.equal(sections.wingWidth(winged,2000),370);
assert(sections.render(winged,2000).includes('0,37 m'));
assert(sections.validate(sections.withWingWidth(box,2000,-10),2000).length);
assert(sections.validate(sections.withWingWidth(box,2000,1000),2000).length);
assert(sections.validate(sections.withWingWidth(box,2000,NaN),2000).length);
// Fórmula del backend: espesor horizontal de alma y paredes inclinadas.
assert(Math.abs(geometry.inner[2][0] - (1000 + 260 * 140 / 450 - 280) / 2) < 1e-8);
assert(sections.validate({...box, canto_mm:250}, 2000).some(s=>s.includes("suma")));
assert(sections.validate({...box, alma_mm:800}, 2000).length);
assert(sections.validate({...box, canto_mm:NaN}, 2000).length);
assert(sections.validate({...box, perfil_canto:[{t:0,canto_mm:500},{t:0,canto_mm:600},{t:1,canto_mm:600}]}, 2000).length);
assert.equal(sections.depthAt({canto_mm:500, perfil_canto:[{t:0,canto_mm:500},{t:0.5,canto_mm:500},{t:1,canto_mm:800}]}, 0.75),650);
const stair = sections.defaults("escalera");
assert.deepEqual(sections.validate(stair,2000,{lengthMm:6000,riseMm:3000}),[]);
assert(sections.validate(stair,2000,{lengthMm:6000,riseMm:0}).length);
assert(sections.validate({...stair,numero_peldanos:2.5},2000).length);
const model={nodos:[{id:"A",x:0,y:0},{id:"B",x:6000,y:0}],soportes:[{nodo:"A",diametro_mm:1000},{nodo:"B",diametro_mm:1000}]};
const layout=sections.foundationLayout(model,["A","B"],{largo_mm:6000,ancho_mm:2000});
assert.deepEqual(layout.centre,[3000,0]);
assert.deepEqual(layout.outside,["A","B"]);
assert.deepEqual(sections.foundationLayout(model,["A","B"],{largo_mm:8000,ancho_mm:2000}).outside,[]);
assert.deepEqual(sections.foundationLayout(model,["A","B"],{largo_mm:2000,ancho_mm:8000,angulo_deg:90}).outside,[]);
console.log("Secciones: geometría de cajón, canto variable, errores, escaleras y contorno de fundaciones correctos.");
