// Actual Python HTTP endpoints and static modules, with a temporary data store.
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const withEdge=process.env.SINCAL_WING_EDGE==='1';
const side=process.env.SINCAL_WING_SIDE||'left';
assert(['left','right'].includes(side),'SINCAL_WING_SIDE must be left or right');
const capturePath=name=>path.join(root,'tmp',side==='left'?name:name.replace(/\.png$/,'-right.png'));
const start=`import json
from pathlib import Path
from tempfile import TemporaryDirectory
from sincal.web.server import Server
from tests.test_web_wing_geometry import project
from tests.test_wing_mesh_geometry import configured
project_data = ${withEdge?`configured(side='${side}',skew=-12,extension=True)[0]`:"project(extension=False,skew=0)"}
with TemporaryDirectory(prefix='sincal-wing-ui-') as directory:
    with Server(0, Path(directory)) as server:
        print(json.dumps({'origin':server.origin,'token':server.token,'project':project_data}),flush=True)
        server.serve_forever()
`;
const server=spawn(process.env.PYTHON||'python',['-u','-c',start],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
const metadata=new Promise((resolve,reject)=>{
 let output='',errors='';const timeout=setTimeout(()=>reject(Error('Temporary server did not start: '+errors)),15000);
 server.stderr.on('data',chunk=>{errors+=chunk;});server.once('error',error=>{clearTimeout(timeout);reject(error);});
 server.once('exit',code=>{clearTimeout(timeout);reject(Error('Temporary server exited '+code+': '+errors));});
 server.stdout.on('data',chunk=>{output+=chunk;const end=output.indexOf('\n');if(end>=0){clearTimeout(timeout);try{resolve(JSON.parse(output.slice(0,end)));}catch(error){reject(error);}}});
});
(async()=>{
 let browser;
 try{
  const backend=await metadata;
  browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];
  page.setDefaultTimeout(15000);page.on('pageerror',error=>errors.push(error.message));
  const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8"><link rel="stylesheet" href="/app.css"></head><body class="outline-hidden"><div class="layout"><main><section id="asistente-armaduras"><h2>Asistente de armaduras · Prueba local</h2><div id="host" class="rebar-assistant-inspector"></div></section></main></div><script nonce="fixture" type="module">
import {renderWingRebar} from '/rebar_wing.js';
const project={data:${JSON.stringify(backend.project)},identification:{structure_name:'Prueba real de ala'},rebar:{}};
const fixture=window.fixture={project,side:${JSON.stringify(side)},calls:[],changes:0,errors:[]};
const node=(tag,text,cls)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
const button=(text,fn)=>{const element=node('button',text);element.type='button';element.onclick=()=>Promise.resolve(fn()).catch(error=>fixture.errors.push(error.message));return element;};
const api=async(route,payload)=>{
 if(!['rebar/from-project','rebar/wing/from-project','rebar/wing/preview','rebar/abutment/scene'].includes(route))throw Error('Unexpected/CAD call '+route);
 const response=await fetch('/api/'+route,{method:'POST',headers:{'Content-Type':'application/json','X-Sincal-Token':${JSON.stringify(backend.token)}},body:JSON.stringify(payload)});
 const data=await response.json();fixture.calls.push({route,payload:structuredClone(payload),response:data});if(!response.ok)throw Error(data.error||'HTTP '+response.status);return data;
};
const ctx={project,api,node,button,current:()=>true,changed:()=>fixture.changes++,notify:message=>fixture.errors.push(message)};
fixture.reopen=async(saved)=>{fixture.controller?.dispose();Object.assign(project,JSON.parse(saved));document.querySelector('#host').replaceChildren();fixture.controller=await renderWingRebar(ctx,document.querySelector('#host'),'entrada',fixture.side);};
fixture.controller=await renderWingRebar(ctx,document.querySelector('#host'),'entrada',fixture.side);window.ready=true;
</script></body></html>`;
  await page.route(backend.origin+'/',route=>route.fulfill({body:harness,contentType:'text/html',headers:{'Content-Security-Policy':"default-src 'self'; script-src 'self' 'nonce-fixture'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'"}}));
  await page.goto(backend.origin+'/');await page.waitForFunction(()=>window.ready);
  const wing=page.locator('.rebar-wing'),field=label=>wing.getByLabel(label,{exact:true});
  const ready=()=>page.waitForFunction(()=>document.querySelector('.rebar-wing-output')?.getAttribute('aria-busy')==='false'&&document.querySelector('.rebar-isometric')?.getAttribute('aria-busy')==='false');
  const values=[['Espesor del ala · cm',withEdge?80:100],['Recubrimiento exterior · cm',5],['Recubrimiento interior · cm',5],['Recubrimiento superior · cm',5],['Recubrimiento en extremos · cm',5],['Recubrimiento en diagonal · cm',5],['Diámetro vertical · mm',16],['Separación vertical · cm',20],['Diámetro horizontal · mm',12],['Separación horizontal · cm',20],['Gancho horizontal en el encuentro · cm',40],['Marca vertical del ala','11'],['Marca vertical de la aleta','12'],['Marca horizontal principal','13'],['Marca horizontal superior','14']];
  for(const [label,value] of values)await field(label).fill(String(value));
  if(withEdge)for(const [label,value] of [['Cantidad de fierros de canto','3'],['Diámetro del fierro de canto · mm','16'],['Largo total del fierro de canto · cm','650'],['Prolongación mínima del fierro de canto · cm','100'],['Marca del fierro de canto','51']])await field(label).fill(value);
  assert.equal(await field('Familia más exterior').count(),0);assert.equal(await field('Inicio del reparto horizontal').count(),0);
  assert.deepEqual(await page.evaluate(()=>[fixture.project.rebar.entrada.wings[fixture.side].outer_family,fixture.project.rebar.entrada.wings[fixture.side].horizontal_start]),['vertical','wall']);
  await field('Confirmo las cotas y dimensiones del ala').check();
  await wing.getByRole('table').waitFor();await ready();
  const result=()=>page.evaluate(()=>fixture.calls.filter(call=>call.route==='rebar/wing/preview').at(-1).response);
  const exterior=await result();assert(exterior.valid,JSON.stringify(exterior.issues));
  await field('Incluir malla interior').check();await ready();
  const partial=await result();assert.equal(partial.valid,false);assert.deepEqual(partial.marks,exterior.marks);
  assert.equal(await wing.getByRole('table').locator('tbody tr').count(),exterior.marks.length);
  assert.equal(await field('Diámetro interior vertical · mm').inputValue(),'16');assert.equal(await field('Diámetro interior horizontal · mm').inputValue(),'12');
  for(const [label,value] of [['Marca interior vertical del ala','21'],['Marca interior vertical de la aleta','22'],['Marca interior horizontal principal','23'],['Marca interior horizontal superior','24']])await field(label).fill(value);
  await ready();
  const before=await result();assert(before.valid,JSON.stringify(before.issues));assert(before.bars.length>0);
  assert(before.bars.every(bar=>bar.id.startsWith(`wing:${side}:`)&&bar.element_key===`abutment.${side}_wing`));
  assert(before.marks.every(mark=>JSON.stringify(mark.views)===JSON.stringify([side==='left'?'BB':'CC','DD','EE'])));
  assert(before.bars.some(bar=>bar.key.includes('_inner_')));assert(before.bars.some(bar=>!bar.key.includes('_inner_')));
  assert.equal(before.marks.reduce((sum,mark)=>sum+mark.quantity,0),before.bars.length);
  assert.equal(await wing.getByRole('table').locator('tbody tr').count(),before.marks.length);
  const viewer=wing.getByRole('region',{name:'Vista isométrica del estribo',exact:true});
  assert.equal(await viewer.locator(`[data-layer="armaduras"] [data-piece^="wing:${side}:"]`).count(),before.bars.length);
  await wing.getByRole('button',{name:before.marks[0].mark,exact:true}).click();
  const detail=page.locator('dialog.rebar-detail-dialog');await detail.waitFor();assert.equal(await detail.locator('svg[data-dimstyle="GSG_COTAS"]').count(),1);
  await detail.getByRole('button',{name:'Cerrar',exact:true}).click();
  if(withEdge){
   const edgeDetail=before.details.find(piece=>piece.key.endsWith('_edge'));assert(edgeDetail);assert.equal(edgeDetail.total_cm,650);assert.equal(edgeDetail.length_variants.length,0);
   await wing.getByRole('button',{name:'51',exact:true}).click();await detail.waitFor();
   assert.equal(await detail.getByText(edgeDetail.detail_note,{exact:true}).count(),1);assert.equal(await detail.getByText(/^Serie de largos variables/).count(),0);
   assert.equal(await detail.locator('svg .dimension-text').filter({hasText:'VAR. L='}).count(),edgeDetail.partial_ranges_cm.filter(range=>range.min_cm!==range.max_cm).length);
   fs.mkdirSync(path.join(root,'tmp'),{recursive:true});await detail.screenshot({path:capturePath('wing-edge-detail-real-ui.png')});
   await detail.getByRole('button',{name:'Cerrar',exact:true}).click();
   assert.equal(before.edge_extensions_cm.length,3);assert(before.edge_extensions_cm.every(piece=>piece.extension_cm>=100));
   assert.equal(await field('Fierro de canto 1').getAttribute('readonly'),'');
  }
  await viewer.getByRole('button',{name:'Ampliar visor',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Vista isométrica del estribo',exact:true});await dialog.locator('svg').waitFor();
  const interiorBar=before.bars.find(bar=>bar.key.includes('_inner_'));
  const bar=dialog.locator(`[data-layer="armaduras"] [data-piece="${interiorBar.id}"]`);
  const p=await bar.evaluate(element=>{const p=element.getPointAtLength(element.getTotalLength()*.55);return new DOMPoint(p.x,p.y).matrixTransform(element.getScreenCTM()).toJSON();});
  await page.mouse.click(p.x,p.y);
  const chooser=dialog.getByRole('combobox',{name:'Elegir fierro superpuesto'});
  if(await chooser.isVisible()){
   const option=await chooser.locator('option').evaluateAll((items,mark)=>items.find(item=>item.textContent.includes('Marca '+mark+' ·')).value,interiorBar.mark);await chooser.selectOption(option);
  }
  const selected=await dialog.locator('.iso-piece-panel').getAttribute('data-piece');assert(selected.startsWith(`wing:${side}:inner_`));
  await dialog.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();await ready();
  await page.waitForFunction(()=>[...document.querySelectorAll('.rebar-isometric')].every(element=>element.getAttribute('aria-busy')==='false'));
  const after=await result();assert(after.valid);assert.equal(after.bars.length,before.bars.length-1);assert(after.total_kg<before.total_kg);
  assert.equal(after.marks.reduce((sum,mark)=>sum+mark.quantity,0),after.bars.length);
  const removed=[{id:selected,signature:before.bars.find(bar=>bar.id===selected).signature}];
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings[fixture.side].interior.removed_pieces),removed);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings[fixture.side].removed_pieces),[]);
  const saved=await page.evaluate(()=>JSON.stringify(fixture.project));
  await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await dialog.waitFor({state:'detached'});
  await page.evaluate(saved=>fixture.reopen(saved),saved);await ready();
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings[fixture.side].interior.removed_pieces),removed);
  assert.equal((await result()).bars.length,before.bars.length-1);
  assert.equal(await field('Incluir malla interior').isChecked(),true);assert.equal(await field('Marca interior vertical del ala').inputValue(),'21');
  await viewer.getByRole('button',{name:'Ver eliminados',exact:true}).click();await dialog.locator('svg').waitFor();
  await dialog.getByText('Fierros eliminados · 1',{exact:true}).click();
  await dialog.getByRole('button',{name:new RegExp('^Restaurar Marca '+interiorBar.mark+'(?:\\s|$)')}).click();await ready();
  await page.waitForFunction(()=>[...document.querySelectorAll('.rebar-isometric')].every(element=>element.getAttribute('aria-busy')==='false'));
  assert.equal((await result()).bars.length,before.bars.length);
  const screenshot=capturePath('wing-rebar-real-ui.png');fs.mkdirSync(path.dirname(screenshot),{recursive:true});await dialog.screenshot({path:screenshot});
  if(withEdge){
   const edgeBar=before.bars.find(bar=>bar.key.endsWith('_edge'));
   const p=await dialog.locator(`[data-layer="armaduras"] [data-piece="${edgeBar.id}"]`).evaluate(element=>{const p=element.getPointAtLength(element.getTotalLength()*.6);return new DOMPoint(p.x,p.y).matrixTransform(element.getScreenCTM()).toJSON();});await page.mouse.click(p.x,p.y);
   const choice=dialog.getByRole('combobox',{name:'Elegir fierro superpuesto'});if(await choice.isVisible())await choice.selectOption(await choice.locator('option').evaluateAll(items=>items.find(item=>item.textContent.includes('Marca 51 ·')).value));
   assert((await dialog.locator('.iso-piece-panel').getAttribute('data-piece')).startsWith(`wing:${side}:edge:`));
   await dialog.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();await ready();await page.waitForFunction(()=>[...document.querySelectorAll('.rebar-isometric')].every(element=>element.getAttribute('aria-busy')==='false'));
   assert.equal((await result()).edge_extensions_cm.length,2);assert.equal((await result()).bars.length,before.bars.length-1);
   assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.wings[fixture.side].edge_rebar.removed_pieces.length),1);
   await dialog.getByRole('button',{name:'Deshacer eliminación',exact:true}).click();await ready();await page.waitForFunction(()=>[...document.querySelectorAll('.rebar-isometric')].every(element=>element.getAttribute('aria-busy')==='false'));
   assert.equal((await result()).edge_extensions_cm.length,3);await dialog.screenshot({path:capturePath('wing-rebar-edge-real-ui.png')});
   assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);assert.deepEqual(errors,[]);
   console.log('OK: canto real3×650cm, prolongaciones>=100 sólo lectura, detalle total fijo/parciales VAR, baja/restauración propias y mallas conservadas.');return;
  }
  await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await dialog.waitFor({state:'detached'});await ready();
  const camera=()=>viewer.locator('svg').evaluate(element=>Object.fromEntries(['yaw','pitch','zoom','scale','target'].map(key=>[key,element.dataset[key]])));
  const legacy={axilla:{enabled:true,start_cm:20,end_cm:80,diameter_mm:16,spacing_cm:20},upper:{enabled:true,start_cm:150,end_cm:260,diameter_mm:12,spacing_cm:15}};
  await page.evaluate(legacy=>{fixture.project.rebar.entrada.wings[fixture.side].supplements=legacy;return fixture.reopen(JSON.stringify(fixture.project));},legacy);await ready();
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings[fixture.side].supplements_legacy),legacy);
  assert.equal(await field('Altura del grupo frontal hacia abajo desde su coronación · cm').inputValue(),'');
  assert.equal(await field('Diámetro del grupo hacia el frontal · mm').inputValue(),'16');assert.equal(await field('Diámetro del grupo hacia el espaldar · mm').inputValue(),'12');
  const cameraBefore=await camera(),profile=(await result()).range_preview;
  await field('Incluir grupo hacia el frontal').check();await field('Incluir grupo hacia el espaldar').check();
  for(const [label,value] of [['Altura del grupo frontal hacia abajo desde su coronación · cm',Math.round(profile.front_height_cm*.5)],['Tramo desde el gancho al extremo libre · frontal · cm',200],['Tramo desde el gancho al extremo libre · espaldar · cm',220],['Marca del grupo hacia el frontal','31'],['Marca del grupo hacia el espaldar','32']])await field(label).fill(String(value));
  await ready();const withRanges=await result();assert.equal(withRanges.valid,false);assert.equal(withRanges.bars.length,before.bars.length);assert.deepEqual(withRanges.marks,before.marks);
  assert.equal(await wing.locator('.wing-supplement-band').count(),2);assert.equal(await wing.getByRole('slider').count(),1);assert.deepEqual(await camera(),cameraBefore);
  const rangesSaved=await page.evaluate(()=>JSON.stringify(fixture.project));await page.evaluate(saved=>fixture.reopen(saved),rangesSaved);await ready();
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings[fixture.side].supplements),JSON.parse(rangesSaved).rebar.entrada.wings[side].supplements);
  const mainLength=await field('Largo principal del ala · cm').inputValue();await field('Largo principal del ala · cm').fill('');await ready();
  assert.equal(await wing.locator('.rebar-wing-supplements svg').isVisible(),false,'A rejected geometry hides the stale range profile');
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings[fixture.side].supplements),JSON.parse(rangesSaved).rebar.entrada.wings[side].supplements);
  await field('Largo principal del ala · cm').fill(mainLength);await field('Confirmo las cotas y dimensiones del ala').check();await ready();assert.equal(await wing.locator('.rebar-wing-supplements svg').isVisible(),true);
  await wing.locator('.rebar-wing-supplements svg').screenshot({path:capturePath('wing-supplement-controls-real-ui.png')});
  for(const [label,value] of [['Altura del grupo frontal hacia abajo desde su coronación · cm',80],['Diámetro del grupo hacia el frontal · mm',12],['Separación del grupo hacia el frontal · cm',20],['Gancho hacia el frontal · cm',40],['Tramo desde el gancho al extremo libre · frontal · cm',300],['Marca del grupo hacia el frontal','51'],['Diámetro del grupo hacia el espaldar · mm',12],['Separación del grupo hacia el espaldar · cm',20],['Gancho hacia el espaldar · cm',40],['Tramo desde el gancho al extremo libre · espaldar · cm',300],['Marca del grupo hacia el espaldar','52']])await field(label).fill(String(value));
  await ready();const green=await result();assert(green.valid,JSON.stringify(green.issues));assert(green.bars.length>before.bars.length);
  assert.equal(green.marks.length,before.marks.length+2);assert(green.supplement_ranges_cm.front);assert(green.supplement_ranges_cm.back);
  await viewer.getByRole('button',{name:'Ampliar visor',exact:true}).click();await dialog.locator('svg').waitFor();
  const greenBar=green.bars.find(bar=>bar.key.endsWith('_inner_supplement_front'));
  const gp=await dialog.locator(`[data-layer="armaduras"] [data-piece="${greenBar.id}"]`).evaluate(element=>{const p=element.getPointAtLength(element.getTotalLength()*.55);return new DOMPoint(p.x,p.y).matrixTransform(element.getScreenCTM()).toJSON();});await page.mouse.click(gp.x,gp.y);
  const gc=dialog.getByRole('combobox',{name:'Elegir fierro superpuesto'});if(await gc.isVisible())await gc.selectOption(await gc.locator('option').evaluateAll(items=>items.find(item=>item.textContent.includes('Marca 51 ·')).value));
  assert((await dialog.locator('.iso-piece-panel').getAttribute('data-piece')).startsWith(`wing:${side}:inner_supplement_front:`));
  await dialog.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();await ready();await page.waitForFunction(()=>[...document.querySelectorAll('.rebar-isometric')].every(element=>element.getAttribute('aria-busy')==='false'));
  assert.equal((await result()).bars.length,green.bars.length-1);assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.wings[fixture.side].supplements.front.removed_pieces.length),1);assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.wings[fixture.side].interior.removed_pieces.length),0);
  await dialog.getByRole('button',{name:'Deshacer eliminación',exact:true}).click();await ready();await page.waitForFunction(()=>[...document.querySelectorAll('.rebar-isometric')].every(element=>element.getAttribute('aria-busy')==='false'));assert.equal((await result()).bars.length,green.bars.length);
  await dialog.screenshot({path:capturePath('wing-supplements-real-ui.png')});
  assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);assert.deepEqual(errors,[]);
  console.log('OK: servidor real, mallas '+before.bars.length+' fierros/'+before.marks.length+' marcas; con suples '+green.bars.length+' fierros/'+green.marks.length+' marcas; bajas/reapertura/restauración separadas; migración legacy, cámara conservada y perfil inválido oculto.');
 }finally{await browser?.close();server.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
