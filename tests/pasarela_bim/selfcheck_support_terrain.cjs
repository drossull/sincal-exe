// Exercise the real editor against its source files in an isolated browser.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const io=require('../../pasarela_bim/web/proyecto.js');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://pasarela.test/**',route=>{
   const url=new URL(route.request().url());
   if(url.pathname.startsWith('/api/'))return route.fulfill({json:url.pathname==='/api/estado'?{freecad_disponible:false}:{valido:true,generable:false,errores:[],avisos:[],pendientes:[]}});
   return route.fulfill({path:path.resolve('pasarela_bim/web',url.pathname==='/'?'index.html':url.pathname.slice(1))});
  });
  const select=async id=>page.locator(`#entity-list [data-select-type="node"][data-select-id="${id}"]`).click();
  const terrain=page.locator('[data-field="support:0:cota_terreno_proyectado_mm"]');
  const editTerrain=async value=>{await terrain.fill(value);await terrain.press('Tab');};
  const dump=async()=>{
   const downloaded=page.waitForEvent('download');await page.locator('#export-json').click();
   const stream=await(await downloaded).createReadStream(),chunks=[];
   for await(const chunk of stream)chunks.push(chunk);
   return JSON.parse(Buffer.concat(chunks).toString());
  };
  await page.goto('http://pasarela.test/');await page.locator('#new-project').click();
  assert.equal(await page.locator('[name="carretera"],[name="terreno"]').count(),0);
  await page.locator('[name="cota_m"]').fill('14.818');
  await page.getByRole('button',{name:'Crear proyecto',exact:true}).click();
  await page.locator('[name="canto"]').fill('2');
  assert((await page.locator('#crossing-preview').textContent()).includes('comprobación pendiente'));
  await page.getByRole('dialog').getByRole('button',{name:'Instalar atravieso',exact:true}).click();
  for(const [id,value] of [['C1','-6.8'],['C2','']]){
   await select(id);await page.locator('[data-action="create-support"]').click();
   assert.equal(await page.locator('[name="terreno_proyectado"]').inputValue(),'');
   if(value)await page.locator('[name="terreno_proyectado"]').fill(value);
   await page.getByRole('button',{name:'Crear apoyo',exact:true}).click();
  }
  const initial=await dump();
  assert(!Object.hasOwn(initial.proyecto,'cota_terreno_m'));assert(!Object.hasOwn(initial.proyecto,'cota_carretera_m'));
  assert.equal(initial.soportes[0].cota_terreno_proyectado_m,-6.8);
  assert(!Object.hasOwn(initial.soportes[1],'cota_terreno_proyectado_m'));
  await select('C1');assert((await page.locator('[data-terrain-reference]').textContent()).includes('8,018'));
  await editTerrain('-6.4');
  const edited=await dump();assert.deepEqual(edited.nodos,initial.nodos);assert.deepEqual(edited.fundaciones,initial.fundaciones);
  assert.equal(edited.soportes[0].cota_superior_m,initial.soportes[0].cota_superior_m);
  assert.equal(edited.soportes[0].cota_terreno_proyectado_m,-6.4);
  await select('C2');await editTerrain('0');assert.equal((await dump()).soportes[1].cota_terreno_proyectado_m,0);
  await editTerrain('');assert(!Object.hasOwn((await dump()).soportes[1],'cota_terreno_proyectado_m'));
  await page.locator('#undo').click();assert.equal((await dump()).soportes[1].cota_terreno_proyectado_m,0);
  // Two independently defined levels remain anchored to two supports sharing one base.
  const shared=io.toInternal(edited);
  shared.soportes[1].cota_terreno_proyectado_mm=-6100;
  shared.fundaciones=[{...shared.fundaciones[0],nodos:['C1','C2'],largo_mm:34000,cota_superior_mm:-7000}];
  shared.soportes.forEach(s=>s.fundacion=shared.fundaciones[0].id);
  await page.locator('#file-input').setInputFiles({name:'terreno-por-apoyo.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(io.toPortable(shared)))});
  await page.locator('#view-elevation').click();
  assert.equal(await page.locator('.projected-terrain-level').count(),2);
  for(const [id,z] of [['C1',-6400],['C2',-6100]]){
   assert(Math.abs(Number(await page.locator(`.projected-terrain-level[data-node-id="${id}"]`).getAttribute('data-z-mm'))-z)<1e-8);
  }
  await select('C1');await editTerrain('-6.25');
  const result=await dump();assert.deepEqual(result.fundaciones,io.toPortable(shared).fundaciones);
  assert(Math.abs(result.soportes[1].cota_terreno_proyectado_m+6.1)<1e-10);
  assert.equal(await page.locator('.projected-terrain-level[data-node-id="C1"]').getAttribute('data-z-mm'),'-6250');
  await page.locator('#model-canvas').screenshot({path:'tmp/terreno-proyectado-por-apoyo.png'});
  await page.locator('#inspector').screenshot({path:'tmp/terreno-proyectado-inspector.png'});
  assert.deepEqual(errors,[]);
  console.log('Support terrain UI: create, edit, clear, zero, undo, JSON exchange, independent shared-base levels and axis markers passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
