// Inspect dimensions in an isolated UI; never reload the user's editor.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://pasarela.test/**',route=>{
   const pathname=new URL(route.request().url()).pathname;
   if(pathname.startsWith('/api/'))return route.fulfill({json:pathname==='/api/estado'?{guardado_local:true,freecad_disponible:false}:{valido:true,generable:false,errores:[],avisos:[],pendientes:[]}});
   return route.fulfill({path:path.resolve('pasarela_bim/web',pathname==='/'?'index.html':pathname.slice(1))});
  });
  const model={version:1,proyecto:{id:'dims',nombre:'Cotas de elevación por eje',unidades:'mm'},
   nodos:[{id:'C1',tipo:'columna',x:0,y:0,z:0},{id:'C2',tipo:'columna',x:10000,y:0,z:-680},{id:'E1',tipo:'estribo',x:10000,y:10000,z:-1480},{id:'D',tipo:'encuentro',x:50000,y:0,z:0},{id:'E',tipo:'encuentro',x:82500,y:0,z:0}],
   tramos:[{id:'V1',tipo:'viga',funcion:'rampa',desde:'C1',hasta:'C2',familia:'box',ancho_mm:2000,descanso_central_mm:1500},{id:'V2',tipo:'viga',funcion:'rampa',desde:'E1',hasta:'C2',familia:'box',ancho_mm:2000,retranqueo_inicio_mm:200,retranqueo_fin_mm:400},{id:'V3',tipo:'viga',funcion:'cruce',desde:'D',hasta:'E',familia:'box',ancho_mm:2000}],
   familias:{box:{tipo:'cajon',canto_mm:1000,ancho_alma_superior_mm:1260,ancho_inferior_mm:1000,losa_superior_mm:150,losa_inferior_mm:140,alma_mm:140,macizado_mm:500}},
   soportes:[{id:'C1',nodo:'C1',fundacion:'F1',diametro_mm:1000,cota_superior_mm:-1500,cota_terreno_proyectado_mm:-5000},{id:'C2',nodo:'C2',fundacion:'F2',diametro_mm:1000,cota_superior_mm:-2300,cota_terreno_proyectado_mm:-5100},{id:'E1',nodo:'E1',fundacion:'F3',largo_mm:1200,ancho_mm:1600,cota_superior_mm:-3100}],
   fundaciones:['C1','C2','E1'].map((id,i)=>({id:'F'+(i+1),nodos:[id],largo_mm:3000,ancho_mm:3000,alto_mm:1000,cota_superior_mm:-6000,pilotes:i===0?[{id:'P1',dx_mm:0,dy_mm:0,diametro_mm:1200,longitud_mm:8000}]:[]})),
   ejes:[{id:'ER1',tipo:'recorrido',nombre:'Acceso con descanso',tramos:['V1','V2']},{id:'EA1',tipo:'atravieso',nombre:'Atravieso',tramos:['V3']},...['C1','C2','E1'].map((id,i)=>({id:'EC'+(i+1),tipo:'apoyo',nodo:id}))]};
  await page.goto('http://pasarela.test/');await page.locator('#file-input').setInputFiles({name:'dimensiones.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(model))});
  await page.locator('#entity-list [data-select-id="C1"]').first().waitFor();
  assert(await page.locator('#elevation-dimensions-wrap').isHidden());
  await page.locator('#view-elevation').click();assert(await page.locator('#plan-dimensions-wrap').isHidden());
  const control=page.locator('#show-elevation-dimensions'),layer=page.locator('.elevation-dimensions');
  assert(await control.isChecked());assert.equal(await layer.count(),1);
  const values=async kind=>page.locator(`[data-dimension-kind="${kind}"]`).evaluateAll(items=>items.map(el=>Number(el.getAttribute('data-value-mm'))));
  assert.deepEqual(await values('span'),[10000,10000]);assert.deepEqual(await values('total'),[20000]);assert.equal((await values('landing')).length,1);assert(Math.abs((await values('landing'))[0]-1500)<1e-6);
  assert((await values('beam-height')).some(v=>Math.abs(v-1120)<1e-6));assert((await values('beam-height')).some(v=>Math.abs(v-1000)<1e-6));
  assert((await values('support-height')).includes(4500));assert((await values('foundation-thickness')).includes(1000));assert((await values('pile-length')).includes(8000));
  assert.deepEqual(await values('level'),[0,-680,-1480]);
  assert((await layer.textContent()).includes('1,500 m'));assert(!(await layer.innerHTML()).includes('NaN'));
  const measured=page.locator('[data-dimension-kind]:not([data-dimension-kind="station"]):not([data-dimension-kind="level"])');
  assert.equal(await layer.locator('.dimension-arrowhead[data-arrow-style="GSG_COTAS"]').count(),2*await measured.count());
  assert(await layer.locator('.dimension-arrowhead[data-arrow-outside="true"]').count()>0,'Las cotas cortas ubican las flechas por fuera.');
  assert.equal(await layer.locator('[data-dimension-kind="level"] .dimension-arrowhead').count(),0);
  const terrain=await page.locator('.projected-terrain-level').count(),cuts=await page.locator('.beam-longitudinal-cut').count();
  assert.equal(await page.evaluate(()=>PasarelaIntegration.snapshot().dirty),false);
  await control.uncheck();assert.equal(await layer.count(),0);assert.equal(await page.locator('.beam-longitudinal-cut').count(),cuts);assert.equal(await page.locator('.projected-terrain-level').count(),terrain);
  await page.locator('#view-plan').click();assert(await page.locator('#elevation-dimensions-wrap').isHidden());
  await page.locator('#view-elevation').click();assert(!await control.isChecked());await control.check();
  await page.locator('#zoom-in').click();assert.deepEqual(await values('span'),[10000,10000]);await page.locator('#fit').click();
  await page.locator('#elevation-axis').selectOption('EA1');assert.deepEqual(await values('span'),[32500]);assert.equal(await page.locator('.projected-terrain-level').count(),0);
  await page.locator('#elevation-axis').selectOption('ER1');assert.deepEqual(await values('span'),[10000,10000]);
  assert.equal(await page.evaluate(()=>PasarelaIntegration.snapshot().dirty),false);
  await page.locator('.canvas-panel').screenshot({path:'tmp/cotas-elevacion-eje.png'});
  // Support edits immediately refresh the displayed height, without stale dimensions.
  await page.locator('#entity-list [data-select-type="node"][data-select-id="C1"]').click();
  const height=page.locator('[data-field="support:0:height"]');await height.fill('5');await height.press('Tab');assert((await values('support-height')).includes(5000));
  await page.setViewportSize({width:1100,height:900});
  const toolbar=await page.locator('.canvas-toolbar').boundingBox(),controls=await page.locator('.canvas-tools').boundingBox();
  assert(controls.x>=toolbar.x&&controls.x+controls.width<=toolbar.x+toolbar.width+1,'Las cotas y el zoom deben caber en la barra de una ventana estrecha.');
  await page.locator('#fit').click();await page.locator('.canvas-panel').screenshot({path:'tmp/cotas-elevacion-ventana-estrecha.png'});
  assert.deepEqual(errors,[]);
  console.log('Axis elevation dimensions UI: automatic dimensions, variable beam depth, landing, foundations/piles, visibility, axis switching, zoom and live support edits passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
