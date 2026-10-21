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
assert.equal(geometry.outer.length, 8);
assert.equal(geometry.inner.length, 4);
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
