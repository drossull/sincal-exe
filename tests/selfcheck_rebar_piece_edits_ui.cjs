// Local browser interaction checks for individual physical-piece edits.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const bars=[
 {id:'mesh_x:superior:0:0',signature:'a'.repeat(64),key:'mesh_x',mark:'1',piece_role:'inicial',length_cm:1200,level:'superior',diameter_mm:22,element_key:'abutment.footing',placement_id:'mesh_x:superior:0',points:[[-3,-1,1.4],[1,-1,1.4]]},
 {id:'mesh_x:superior:0:1',signature:'b'.repeat(64),key:'mesh_x',mark:'2',piece_role:'terminal',length_cm:300,level:'superior',diameter_mm:22,element_key:'abutment.footing',placement_id:'mesh_x:superior:0',points:[[0,-1,1.4],[3,-1,1.4]],lap_segments:[[[0,-1,1.4],[1,-1,1.4]]]},
 {id:'mesh_x:superior:1:0',signature:'c'.repeat(64),key:'mesh_x',mark:'1',piece_role:'inicial',length_cm:1200,level:'superior',diameter_mm:22,element_key:'abutment.footing',placement_id:'mesh_x:superior:1',points:[[-3,1,1.4],[1,1,1.4]]},
];
const fixtureScene={units:'m',elements:[{key:'abutment.footing',label:'Fundación',meshes:[{vertices:[[-4,-2,0],[4,-2,0],[4,2,0],[-4,2,0],[-4,-2,1.5],[4,-2,1.5],[4,2,1.5],[-4,2,1.5]],faces:[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]]}]}],bars,issues:[]};
const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8"><link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/fixture.css"></head><body><div id="host"></div>
<script nonce="fixture" type="module">
import {mountAbutmentIsometric} from '/rebar_isometric.js';
const state=()=>({geometry:{alto_cm:150},rules:[{key:'mesh_x',label:'Malla 1–2',mark:'1',removed_pieces:[]}]});
const project={data:{estribos:{}},identification:{structure_name:'Prueba selección'},rebar:{entrada:state(),salida:state()}};
const scene=${JSON.stringify(fixtureScene)};
const fixture=window.fixture={project,changes:0,edits:[],errors:[],calls:[],current:true,delayNext:0,failNext:false,unresolved:false};
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
const ctx={project,node,current:()=>fixture.current,notify:message=>fixture.errors.push(message),changed:()=>fixture.changes++,
 api:async(route,payload)=>{if(route!=='rebar/abutment/scene')throw Error('CAD/unexpected route '+route);fixture.calls.push(structuredClone(payload));
 if(fixture.failNext){fixture.failNext=false;throw Error('Fallo de prueba recuperable');}
 const ids=new Set(payload.state.rules.flatMap(rule=>rule.removed_pieces||[]).map(p=>p.id+':'+p.signature));
 const result={...structuredClone(scene),bars:scene.bars.filter(bar=>!ids.has(bar.id+':'+bar.signature)),removed_bars:scene.bars.filter(bar=>ids.has(bar.id+':'+bar.signature))};
 if(fixture.unresolved)result.removed_bars=result.removed_bars.map(bar=>({id:bar.id,signature:bar.signature,key:bar.key,label:'Malla 1–2',status:'unresolved'}));
 const delay=fixture.delayNext;fixture.delayNext=0;if(delay)await new Promise(resolve=>setTimeout(resolve,delay));return result;}};
fixture.mount=async(instance='entrada')=>{fixture.viewer?.dispose();fixture.viewer=mountAbutmentIsometric(ctx,instance,document.getElementById('host'),{onPiecesChanged:key=>fixture.edits.push({key,changes:fixture.changes,state:structuredClone(project.rebar[key])})});await fixture.viewer.ready;};
await fixture.mount();window.ready=true;
</script></body></html>`;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1360,height:1000}}),errors=[],csp=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.text().includes('Content Security Policy'))csp.push(m.text());});
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:harness,contentType:'text/html',headers:{'Content-Security-Policy':"default-src 'self'; script-src 'self' 'nonce-fixture'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'"}});
   if(name==='fixture.css')return route.fulfill({body:'body{padding:20px}#host{max-width:1050px;margin:auto}',contentType:'text/css'});
   if(['rebar_isometric.js','app.css'].includes(name)||name.endsWith('.ttf'))return route.fulfill({body:fs.readFileSync(path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-piece-edits.test');await page.waitForFunction(()=>window.ready);
  const embedded=page.getByRole('region',{name:'Vista isométrica del estribo',exact:true});
  const ready=async(scope=embedded)=>{await scope.locator('svg').waitFor();await page.waitForFunction(()=>[...document.querySelectorAll('.rebar-isometric')].every(e=>e.getAttribute('aria-busy')!=='true'));};
  const pointOn=async(scope,id,t=.2)=>scope.locator(`[data-layer="armaduras"] polyline[data-piece="${id}"]`).evaluate((el,t)=>{const a=el.points[0],b=el.points[1],p=new DOMPoint(a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t).matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y};},t);
  const clickAt=async p=>page.mouse.click(p.x,p.y);
  const removed=()=>page.evaluate(()=>fixture.project.rebar.entrada.rules[0].removed_pieces);
  const camera=scope=>scope.locator('svg').evaluate(e=>Object.fromEntries(['yaw','pitch','zoom','scale','target'].map(key=>[key,e.dataset[key]])));
  await ready();const originalCamera=await camera(embedded);
  const initialSource=await page.evaluate(()=>structuredClone(fixture.project.data));
  // The overlapping pair is selected explicitly; only the chosen terminal
  // physical piece is removed, not its initial partner or the whole mark.
  await clickAt(await pointOn(embedded,bars[0].id,.875));
  const chooser=embedded.getByRole('combobox',{name:'Elegir fierro superpuesto'});await chooser.waitFor();
  const terminal=await chooser.locator('option').evaluateAll(options=>options.find(o=>o.textContent.includes('Marca 2')).value);
  await chooser.selectOption(terminal);
  assert.equal(await embedded.locator('[data-piece-highlight]').getAttribute('data-piece-highlight'),bars[1].id);
  await embedded.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();await ready();
  assert.deepEqual(await removed(),[{id:bars[1].id,signature:bars[1].signature}]);
  assert.equal(await embedded.locator('[data-layer="armaduras"] polyline').count(),2);
  assert.equal(await embedded.locator(`[data-layer="armaduras"] [data-piece="${bars[0].id}"]`).count(),1);
  assert.deepEqual(await camera(embedded),originalCamera);
  assert.equal(await page.evaluate(()=>fixture.edits[0].changes),1,'State is saved before quantity invalidation callback');
  assert.equal(await page.evaluate(()=>fixture.edits[0].state.rules[0].removed_pieces.length),1);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.salida.rules[0].removed_pieces),[]);
  await embedded.getByRole('button',{name:'Deshacer eliminación',exact:true}).click();await ready();
  assert.deepEqual(await removed(),[]);assert.equal(await embedded.locator('[data-layer="armaduras"] polyline').count(),3);
  // A left drag and a middle orbit must not open a destructive action panel.
  const dragPoint=await pointOn(embedded,bars[2].id);
  await page.mouse.move(dragPoint.x,dragPoint.y);await page.mouse.down();await page.mouse.move(dragPoint.x+20,dragPoint.y+20);await page.mouse.up();
  assert.equal(await embedded.getByRole('button',{name:'Eliminar este fierro',exact:true}).isVisible(),false);
  await page.keyboard.down('Shift');await page.mouse.down({button:'middle'});await page.mouse.move(dragPoint.x+35,dragPoint.y+30);await page.mouse.up({button:'middle'});await page.keyboard.up('Shift');
  assert.equal(await embedded.getByRole('button',{name:'Eliminar este fierro',exact:true}).isVisible(),false);
  await embedded.getByRole('button',{name:'Isométrica',exact:true}).click();
  // Deletion from the expanded viewer updates the compact scene when closed.
  await embedded.getByRole('button',{name:'Ampliar visor',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Vista isométrica del estribo',exact:true});await ready(dialog);
  if(process.env.SINCAL_PIECE_PREVIEW){
   await clickAt(await pointOn(dialog,bars[0].id,.875));
   const select=dialog.getByRole('combobox',{name:'Elegir fierro superpuesto'});
   await select.selectOption(await select.locator('option').evaluateAll(options=>options.find(o=>o.textContent.includes('Marca 2')).value));
   await dialog.screenshot({path:process.env.SINCAL_PIECE_PREVIEW});
   await dialog.getByRole('button',{name:'Cancelar selección',exact:true}).click();
  }
  await clickAt(await pointOn(dialog,bars[2].id));await dialog.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();await ready(dialog);
  await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await page.locator('dialog.rebar-isometric').waitFor({state:'detached'});await ready();
  assert.equal(await embedded.locator('[data-layer="armaduras"] polyline').count(),2);
  // Saved records remain restorable even after remounting (no in-memory undo).
  await page.evaluate(()=>fixture.mount());await ready();
  await embedded.getByRole('button',{name:'Ver eliminados',exact:true}).click();await ready(dialog);
  await dialog.getByText('Fierros eliminados · 1',{exact:true}).click();
  await dialog.getByRole('button',{name:/^Restaurar Marca 1/}).click();await ready(dialog);assert.deepEqual(await removed(),[]);
  await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await page.locator('dialog.rebar-isometric').waitFor({state:'detached'});await ready();
  // A stale geometry selection cannot delete a different future bar at the
  // same generated index. A new scene and explicit selection are required.
  await clickAt(await pointOn(embedded,bars[0].id));
  await page.evaluate(()=>{fixture.project.rebar.entrada.geometry.alto_cm=200;});
  await embedded.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();await ready();
  assert.deepEqual(await removed(),[]);
  assert.equal(await page.evaluate(()=>fixture.errors.length),1);
  assert.match(await page.evaluate(()=>fixture.errors[0]),/armadura cambió/);
  assert.deepEqual(await page.evaluate(()=>fixture.project.data),initialSource);
  assert.equal(await page.evaluate(()=>fixture.changes),4);assert.equal(await page.evaluate(()=>fixture.edits.length),4);
  // Failed scene reloads must still offer reversal of the last piece edit.
  await clickAt(await pointOn(embedded,bars[2].id));await page.evaluate(()=>{fixture.failNext=true;});
  await embedded.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();
  await embedded.getByRole('button',{name:'Volver a intentar',exact:true}).waitFor();
  await embedded.getByRole('button',{name:'Deshacer eliminación',exact:true}).click();await ready();
  assert.deepEqual(await removed(),[]);assert.equal(await page.evaluate(()=>fixture.changes),6);
  // Invalidated records remain identifiable and restorable without undefined
  // diameter/mark labels, both with a prior cache and in a newly opened viewer.
  await page.evaluate(record=>{fixture.project.rebar.entrada.rules[0].removed_pieces=[record];fixture.unresolved=true;fixture.viewer.update();},{id:bars[2].id,signature:bars[2].signature});await ready();
  await embedded.getByRole('button',{name:'Ver eliminados',exact:true}).click();await ready(dialog);
  await dialog.getByText('Fierros eliminados · 1',{exact:true}).click();
  assert.match(await dialog.locator('.iso-removed-piece').textContent(),/Marca 1.*Ø22 mm.*Revisar/);
  await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await page.locator('dialog.rebar-isometric').waitFor({state:'detached'});
  await page.evaluate(()=>fixture.mount());await ready();await embedded.getByRole('button',{name:'Ver eliminados',exact:true}).click();await ready(dialog);
  await dialog.getByText('Fierros eliminados · 1',{exact:true}).click();
  assert.match(await dialog.locator('.iso-removed-piece').textContent(),/Malla 1–2 · Revisar/);
  assert.doesNotMatch(await dialog.locator('.iso-removed-piece').textContent(),/undefined|NaN/);
  assert.deepEqual(errors,[]);assert.deepEqual(csp,[]);
  console.log('OK: selección individual, piezas superpuestas, eliminación exacta, deshacer/restaurar, persistencia, cámara e instancias; edición desfasada bloqueada; CSP; sin CAD.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
