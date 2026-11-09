// Exercise source UI in a new headless page; never attach to or reload the user's editor.
'use strict';
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1150}}),errors=[],writes=[],validations=[];
  page.on('pageerror',error=>errors.push(error.message));
  const model={version:1,proyecto:{id:'pile-plan-test',nombre:'Fundación compartida · distribución de pilotes',unidades:'mm'},
   nodos:[{id:'C1',uuid:'node-1',tipo:'columna',x:0,y:0,z:0},{id:'C2',uuid:'node-2',tipo:'columna',x:0,y:4000,z:0}],
   tramos:[{id:'R1',uuid:'return-1',tipo:'retorno',funcion:'retorno',desde:'C1',hasta:'C2',familia:'losa',ancho_mm:2000}],
   familias:{losa:{tipo:'maciza',canto_mm:500,pendiente_transversal_pct:1,macizado_mm:500}},
   soportes:[{id:'SC1',uuid:'support-1',nodo:'C1',fundacion:'F1',diametro_mm:900,cota_superior_mm:-800},{id:'SC2',uuid:'support-2',nodo:'C2',fundacion:'F1',diametro_mm:900,cota_superior_mm:-800}],
   fundaciones:[{id:'F1',uuid:'foundation-1',tipo:'dado',nodos:['C1','C2'],largo_mm:6000,ancho_mm:4000,alto_mm:1000,cota_superior_mm:-5000,angulo_deg:90,pilotes:[
    {id:'P1',uuid:'pile-1',dx_mm:-1500,dy_mm:0,diametro_mm:800,longitud_mm:10000},
    {id:'P2',uuid:'pile-2',dx_mm:1500,dy_mm:0,diametro_mm:800,longitud_mm:10000}]}],
   ejes:[{id:'ER1',tipo:'recorrido',nombre:'Eje del retorno',tramos:['R1']},{id:'EC1',tipo:'apoyo',nodo:'C1'},{id:'EC2',tipo:'apoyo',nodo:'C2'}]};
  await page.route('http://pasarela.test/**',async route=>{
   const pathname=new URL(route.request().url()).pathname;
   if(pathname==='/api/proyecto/guardar'){
    writes.push(route.request().postDataJSON());
    return route.fulfill({json:{guardado:true,documento:{id:'pile-plan-file',nombre:'pilotes.json',ruta:'C:/Proyectos/pilotes.json'}}});
   }
   if(pathname==='/api/validar')validations.push(route.request().postDataJSON());
   if(pathname.startsWith('/api/'))return route.fulfill({json:pathname==='/api/estado'?{guardado_local:true,freecad_disponible:false}:{valido:true,generable:false,errores:[],avisos:[],pendientes:[]}});
   return route.fulfill({path:path.resolve('pasarela_bim/web',pathname==='/'?'index.html':pathname.slice(1))});
  });
  const dirty=()=>page.evaluate(()=>PasarelaIntegration.snapshot().dirty);
  const inspect=async()=>{const response=page.waitForResponse('**/api/validar');await page.locator('#validate').click();await response;return validations.at(-1);};
  const save=async()=>{const response=page.waitForResponse('**/api/proyecto/guardar');await page.locator('#export-json').click();await response;await page.waitForFunction(()=>!PasarelaIntegration.snapshot().busy);return writes.at(-1).modelo;};
  const showFoundation=async()=>{await page.locator('#entity-list [data-select-type="foundation"][data-select-id="F1"]').click();await page.locator('#inspector [data-action="pile-plan"]').click();};
  const dialog=page.locator('.pile-plan-dialog'),field=key=>dialog.locator(`[data-pile-field="${key}"]`),spacing=key=>dialog.locator(`[data-spacing-field="${key}"]`);
  const choose=async id=>dialog.locator(`[data-pile-list-id="${id}"]`).click();
  const dimensionValues=kind=>page.locator(`#scene [data-dimension-kind="${kind}"]`).evaluateAll(items=>items.map(el=>Number(el.getAttribute('data-value-mm'))));
  const checkDimensionSeparation=async(axis,distance)=>{
   const boxes=await dialog.locator('[data-pile-dimensions] text').evaluateAll((items,{axis,distance})=>{
    const a=items.find(el=>el.textContent.startsWith(`Δ${axis} `)),b=items.find(el=>el.textContent===distance);
    if(!a||!b)throw new Error('Faltan cotas entre pilotes para comprobar su legibilidad.');
    const aa=a.getBoundingClientRect(),bb=b.getBoundingClientRect();return{a:{left:aa.left,top:aa.top,right:aa.right,bottom:aa.bottom},b:{left:bb.left,top:bb.top,right:bb.right,bottom:bb.bottom}};
   },{axis,distance});
   if(axis==='X')assert(boxes.b.top>boxes.a.bottom,'La distancia entre centros debe quedar debajo de la separación X, en ambos sentidos.');
   else assert(boxes.b.right<boxes.a.left,'La distancia entre centros debe quedar a la izquierda de la separación Y, en ambos sentidos.');
  };

  await page.goto('http://pasarela.test/');
  await page.locator('#file-input').setInputFiles({name:'pilotes-rotados.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(model))});
  await page.locator('#entity-list [data-select-id="F1"]').waitFor();
  const initial=await inspect(),initialFoundation=structuredClone(initial.fundaciones[0]);
  assert.equal(await dirty(),false);
  await showFoundation();
  assert.equal(await dialog.locator('[data-plan-support]').count(),2);
  const supportCentres=await dialog.locator('[data-plan-support]').evaluateAll(items=>items.map(el=>({x:Number(el.getAttribute('cx')),y:Number(el.getAttribute('cy'))})));
  assert(supportCentres[1].x>supportCentres[0].x,'Una fundación girada 90° debe mostrar las columnas alineadas en X local.');
  assert(Math.abs(supportCentres[0].y-supportCentres[1].y)<1e-8);
  assert.match(await dialog.locator('[data-pile-summary]').textContent(),/90°/);
  assert(await dialog.locator('.dimension-arrowhead[data-arrow-style="GSG_COTAS"]').count()>=8);

  // Editing a cancelled draft changes neither the live model nor the dirty marker.
  await choose('P2');await field('dx_mm').fill('1.2');await field('longitud_mm').fill('12');
  assert.equal(await spacing('dx').inputValue(),'2.7');assert.equal(await dirty(),false);
  await dialog.locator('[data-pile-cancel]').click();assert.equal(await dialog.count(),0);
  assert.deepEqual((await inspect()).fundaciones[0],initialFoundation);assert.equal(await dirty(),false);

  // The same editor is accessible from a support node as well as from the foundation.
  await page.locator('#entity-list [data-select-type="node"][data-select-id="C1"]').click();
  await page.locator('#inspector [data-action="pile-plan"][data-foundation-id="F1"]').click();
  await choose('P2');await spacing('dx').fill('3.25');assert.equal(await field('dx_mm').inputValue(),'1.75');
  await checkDimensionSeparation('X','3,250 m');
  await spacing('distance').fill('2');assert.equal(await field('dx_mm').inputValue(),'0.5');
  await spacing('angle').fill('30');assert.equal(await field('dy_mm').inputValue(),'1');
  await field('dx_mm').fill('-1.5');await field('dy_mm').fill('0');
  assert(await dialog.locator('[data-pile-apply]').isDisabled());assert.match(await dialog.locator('[data-pile-errors]').textContent(),/superponen/);
  await field('dx_mm').fill('5');assert(await dialog.locator('[data-pile-apply]').isDisabled());assert.match(await dialog.locator('[data-pile-errors]').textContent(),/dentro/);
  await field('dx_mm').fill('1.5');assert(await dialog.locator('[data-pile-apply]').isEnabled());

  // Real pointer dragging and keyboard movement operate in foundation-local coordinates.
  const circle=await dialog.locator('[data-pile-id="P2"] circle').boundingBox();assert(circle);
  await page.mouse.move(circle.x+circle.width/2,circle.y+circle.height/2);await page.mouse.down();
  await page.mouse.move(circle.x+circle.width/2-30,circle.y+circle.height/2-40,{steps:5});await page.mouse.up();
  assert(Number(await field('dx_mm').inputValue())<1.5);assert(Number(await field('dy_mm').inputValue())>0);
  const xBefore=Number(await field('dx_mm').inputValue());
  await dialog.locator('[data-pile-id="P2"]').press('Shift+ArrowRight');
  assert(Math.abs(Number(await field('dx_mm').inputValue())-xBefore-.1)<1e-8);
  await field('dx_mm').fill('1.75');await field('dy_mm').fill('0');await field('longitud_mm').fill('12');
  await dialog.locator('[data-pile-add]').click();assert.equal(await dialog.locator('[data-pile-list-id]').count(),3);
  assert.equal(await dialog.locator('[data-pile-selected-title]').textContent(),'P3');
  await field('dx_mm').fill('0');await field('dy_mm').fill('0');await field('diametro_mm').fill('0.6');await field('longitud_mm').fill('7.5');
  await dialog.locator('[data-pile-reference]').selectOption('P2');assert.equal(await spacing('dx').inputValue(),'-1.75');
  await checkDimensionSeparation('X','1,750 m');
  await field('dx_mm').fill('1.75');await field('dy_mm').fill('1.5');await checkDimensionSeparation('Y','1,500 m');
  await field('dy_mm').fill('-1.5');await checkDimensionSeparation('Y','1,500 m');
  await field('dx_mm').fill('0');await field('dy_mm').fill('0');
  assert(await dialog.locator('[data-pile-apply]').isEnabled());assert.equal(await dirty(),false);
  fs.mkdirSync('tmp',{recursive:true});await dialog.screenshot({path:'tmp/planta-fundacion-pilotes.png'});
  await dialog.locator('[data-pile-apply]').click();await dialog.waitFor({state:'detached'});
  assert.equal(await dirty(),true);assert.equal(await page.locator('#selection-kind').textContent(),'DADO');
  assert.equal(await page.locator('#scene .pile-preview circle').count(),3);
  const edited=await inspect(),f=edited.fundaciones[0];assert.equal(f.tipo,'dado');assert.equal(f.uuid,'foundation-1');
  assert.deepEqual(f.nodos,['C1','C2']);assert.equal(f.angulo_deg,90);assert.equal(f.pilotes.length,3);
  assert.deepEqual(f.pilotes[0],initialFoundation.pilotes[0]);
  assert.equal(f.pilotes[1].uuid,'pile-2');assert.equal(f.pilotes[1].dx_mm,1750);assert.equal(f.pilotes[1].dy_mm,0);assert.equal(f.pilotes[1].longitud_mm,12000);
  assert(f.pilotes[2].uuid);assert.equal(f.pilotes[2].diametro_mm,600);assert.equal(f.pilotes[2].longitud_mm,7500);
  assert.equal(new Set([...edited.nodos,...edited.tramos,...edited.ejes,...edited.fundaciones,...f.pilotes].map(item=>item.id)).size,edited.nodos.length+edited.tramos.length+edited.ejes.length+edited.fundaciones.length+f.pilotes.length);

  // Generated preview geometry and section dimensions follow the committed local positions.
  await page.locator('#view-iso').click();assert.equal(await page.locator('#scene .pile-preview line').count(),3);
  await page.locator('#view-elevation').click();await page.locator('#elevation-axis').selectOption('ER1');
  assert.deepEqual((await dimensionValues('pile-length')).sort((a,b)=>a-b),[7500,10000,12000]);
  assert.deepEqual(await dimensionValues('foundation-thickness'),[1000]);
  assert.equal(await page.locator('#scene .pile-longitudinal-cut').count(),3);
  await page.locator('.canvas-panel').screenshot({path:'tmp/elevacion-fundacion-pilotes.png'});

  // Save remains portable in metres and retains identities; round-trip recovers exact mm geometry.
  const portable=await save();assert.equal(portable.version,2);assert.equal(portable.proyecto.unidades,'m');
  const saved=portable.fundaciones[0];assert.equal(saved.pilotes[1].dx_m,1.75);assert.equal(saved.pilotes[1].longitud_m,12);assert.equal(saved.pilotes[1].uuid,'pile-2');
  assert.equal(saved.pilotes[2].diametro_m,.6);assert.equal(saved.pilotes[2].uuid,f.pilotes[2].uuid);
  assert(!Object.hasOwn(saved.pilotes[2],'diametro_mm'));
  const roundTrip=await page.evaluate(value=>ProjectIO.toInternal(value),portable);assert.deepEqual(roundTrip.fundaciones[0],f);assert.equal(await dirty(),false);

  // Undo returns the complete earlier layout and section dimensions, preserving identities.
  await page.locator('#undo').click();assert.deepEqual((await inspect()).fundaciones[0],initialFoundation);
  assert.deepEqual(await dimensionValues('pile-length'),[10000,10000]);assert.equal(await page.locator('#scene .pile-longitudinal-cut').count(),2);
  await showFoundation();await field('longitud_mm').fill('11');const afterUndoDirty=await dirty();
  await page.keyboard.press('Escape');assert.equal(await dialog.count(),0);assert.equal(await dirty(),afterUndoDirty);
  assert.deepEqual((await inspect()).fundaciones[0],initialFoundation);

  // Legacy shared foundations may derive their rotation from the first/last support nodes.
  const implicit=structuredClone(model);delete implicit.fundaciones[0].angulo_deg;implicit.proyecto.nombre+=' · giro implícito';
  await page.locator('#file-input').setInputFiles({name:'pilotes-giro-implicito.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(implicit))});
  await page.waitForFunction(()=>document.querySelector('#project-name').textContent.endsWith('giro implícito'));
  await page.locator('#view-elevation').click();await page.locator('#elevation-axis').selectOption('ER1');
  assert.deepEqual(await dimensionValues('pile-length'),[10000,10000]);assert.equal(await page.locator('#scene .pile-longitudinal-cut').count(),2);
  await showFoundation();assert.match(await dialog.locator('[data-pile-summary]').textContent(),/90°/);
  const implicitSupportCentres=await dialog.locator('[data-plan-support]').evaluateAll(items=>items.map(el=>({x:Number(el.getAttribute('cx')),y:Number(el.getAttribute('cy'))})));
  assert.deepEqual(implicitSupportCentres,supportCentres);await dialog.locator('[data-pile-cancel]').click();
  assert(!Object.hasOwn((await inspect()).fundaciones[0],'angulo_deg'),'Abrir la planta no debe convertir el giro implícito en un dato fijo.');
  assert.deepEqual(errors,[]);
  console.log('Pile layout UI: shared rotated foundation, two supports, both entry points, draft cancellation, drag/keyboard, editable separations and legible dimensions, validation, apply, plan/iso/elevation, portable JSON, undo and implicit rotation passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
