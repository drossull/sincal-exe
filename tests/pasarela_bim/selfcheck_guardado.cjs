// UI source check: no native dialogs and no running user session is touched.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[],downloads=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('download',d=>downloads.push(d));page.on('dialog',d=>d.accept());
  const fixture=JSON.parse(fs.readFileSync('pasarela_bim/ejemplos/los_batros.json','utf8'));
  const descriptor=(id='first')=>({id,nombre:id+'.json',ruta:'C:/Proyectos/'+id+'.json'});
  let response={guardado:true,documento:descriptor()},openResponse={modelo:fixture,documento:descriptor('existing')},hold,release;
  await page.route('http://pasarela.test/**',async route=>{
   const pathname=new URL(route.request().url()).pathname;
   if(pathname==='/api/proyecto/guardar'){
    writes.push(route.request().postDataJSON());if(hold)await new Promise(resolve=>{release=resolve;});
    return route.fulfill({status:response.status||200,json:response});
   }
   if(pathname==='/api/proyecto/abrir')return route.fulfill({json:openResponse});
   if(pathname.startsWith('/api/'))return route.fulfill({json:pathname==='/api/estado'?{guardado_local:true,freecad_disponible:false}:pathname==='/api/ejemplo'?fixture:{valido:true,generable:false,errores:[],avisos:[],pendientes:[]}});
   return route.fulfill({path:path.resolve('pasarela_bim/web',pathname==='/'?'index.html':pathname.slice(1))});
  });
  const dirty=()=>page.evaluate(()=>PasarelaIntegration.snapshot().dirty);
  const status=page.locator('#project-file-status'),button=page.locator('#export-json');
  const save=async action=>{const reply=page.waitForResponse('**/api/proyecto/guardar');await action();await reply;await page.waitForFunction(()=>!PasarelaIntegration.snapshot().busy);};
  const edit=async name=>{await page.locator('#entity-list [data-select-type="node"]').first().click();await page.locator('#inspector [data-field="id"]').fill(name);};
  await page.goto('http://pasarela.test/');await page.locator('#load-example').click();await page.waitForFunction(()=>!document.querySelector('#export-json').disabled);
  assert.equal(await button.textContent(),'Guardar JSON…');assert(await dirty());
  await save(()=>button.click());assert.equal(await button.textContent(),'Guardar cambios');assert(!await dirty());assert.match(await status.textContent(),/first.json · Guardado/);
  assert(!Object.hasOwn(writes[0],'documento_id'));assert.equal(writes[0].modelo.version,2);
  // Ctrl+S commits the focused field before taking its saved snapshot.
  await edit('E_guardado');assert(await dirty());await save(()=>page.keyboard.press('Control+s'));
  assert.equal(writes.at(-1).documento_id,'first');assert(writes.at(-1).modelo.nodos.some(n=>n.id==='E_guardado'));assert(!await dirty());
  response={cancelado:true};await save(()=>page.locator('#save-as-json').click());assert.equal(writes.at(-1).guardar_como,true);assert.match(await status.textContent(),/first.json/);
  await edit('E_pendiente');response={status:500,mensaje:'No se pudo guardar: ensayo de disco'};await save(()=>button.click());assert(await dirty());assert.match(await page.locator('#toast').textContent(),/ensayo de disco/);
  // A slow save must not mark text typed afterwards as saved, even before blur.
  response={guardado:true,documento:descriptor()};hold=true;await button.click();await page.waitForFunction(()=>PasarelaIntegration.snapshot().busy);
  await edit('E_escrito_durante_guardado');release();hold=false;await page.waitForFunction(()=>!PasarelaIntegration.snapshot().busy);
  assert(await dirty());assert.match(await status.textContent(),/Cambios sin guardar/);
  await save(()=>page.keyboard.press('Control+s'));assert(!await dirty());assert(writes.at(-1).modelo.nodos.some(n=>n.id==='E_escrito_durante_guardado'));
  response={guardado:true,documento:descriptor('copy')};await save(()=>page.keyboard.press('Control+Shift+s'));assert.equal(writes.at(-1).guardar_como,true);assert.match(await status.textContent(),/copy.json/);
  await save(()=>button.click());assert.equal(writes.at(-1).documento_id,'copy');
  // Invalid imports leave both the current model and bound file intact.
  openResponse={modelo:{...fixture,pendientes_documentales:[null]},documento:descriptor('invalid')};
  await page.locator('#import-json').click();await page.waitForFunction(()=>!PasarelaIntegration.snapshot().busy);
  assert.match(await status.textContent(),/copy.json/);assert.equal(await button.textContent(),'Guardar cambios');assert.match(await page.locator('#toast').textContent(),/notas/);
  openResponse={modelo:fixture,documento:descriptor('existing')};await page.locator('#import-json').click();await page.waitForFunction(()=>document.querySelector('#project-file-status').textContent.includes('existing.json'));
  response={guardado:true,documento:descriptor('existing')};await save(()=>button.click());assert.equal(writes.at(-1).documento_id,'existing');
  // Undo crossing the opened-document boundary must not overwrite that file.
  await page.locator('#undo').click();assert.equal(await button.textContent(),'Guardar JSON…');assert.match(await status.textContent(),/Sin archivo asociado/);
  response={guardado:true,documento:descriptor('recovered')};await save(()=>button.click());assert(!Object.hasOwn(writes.at(-1),'documento_id'));
  // Draft form edits cannot silently be omitted by Ctrl+S.
  await page.locator('#project-settings').click();const count=writes.length;await page.keyboard.press('Control+s');assert.equal(writes.length,count);assert.match(await page.locator('#toast').textContent(),/formulario/);
  await page.getByRole('button',{name:'Cancelar',exact:true}).click();
  await page.screenshot({path:'tmp/guardado-local-editor.png'});
  assert.deepEqual(downloads,[]);assert.deepEqual(errors,[]);
  console.log('Local save UI: overwrite, Save As, open, Ctrl+S field commit, cancellation, failure, concurrent typing, invalid import and cross-document undo passed. No downloads.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
