// Real Python calculations, isolated browser. No installed SINCAL or CAD access.
const {chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const calculate=state=>JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',
  'import sys,json; from sincal.web.rebar import preview; print(json.dumps(preview(json.load(sys.stdin))))'],
  {cwd:root,input:JSON.stringify(state),encoding:'utf8'}));
const defaults=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',
  'import json; from sincal.web.rebar import defaults; print(json.dumps(defaults()))'],{cwd:root,encoding:'utf8'}));
const harness=`<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"></head>
<body><main id="host"></main><script type="module">
import {renderRebar} from '/rebar.js';
const defaults=${JSON.stringify(defaults)};
const project={data:{fixture:true},identification:{structure_name:'Zapata · prueba de empalmes'}};
const fixture=window.fixture={project,calls:[],errors:[],changes:0,delayNext:0};
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const button=(label,fn,primary=false)=>{const e=node('button',label,primary?'primary':'');e.type='button';e.onclick=async()=>{try{await fn();}catch(error){fixture.errors.push(error.message);}};return e;};
const section=(id,label)=>{const e=node('section');e.id=id;e.append(node('h2',label));document.getElementById('host').append(e);return e;};
const api=async(route,payload)=>{
 fixture.calls.push({route,payload:structuredClone(payload)});
 if(route==='rebar/from-project')return {entrada:structuredClone(defaults),salida:structuredClone(defaults)};
 if(route==='rebar/abutment/scene')return {elements:[],bars:[],issues:[]};
 if(route==='rebar/preview'){
   const delay=fixture.delayNext;fixture.delayNext=0;
   const res=await fetch('/calculate',{method:'POST',body:JSON.stringify(payload)}),data=await res.json();
   if(delay)await new Promise(resolve=>setTimeout(resolve,delay));return data;
 }
 throw Error('Forbidden route '+route);
};
await renderRebar({project,api,node,button,section,current:()=>true,changed:()=>fixture.changes++,notify:message=>fixture.errors.push(message),job:()=>{throw Error('CAD forbidden');}});window.ready=true;
</script></body></html>`;

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];
  page.setDefaultTimeout(12000);page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:harness,contentType:'text/html'});
   if(name==='calculate')return route.fulfill({body:JSON.stringify(calculate(JSON.parse(route.request().postData()))),contentType:'application/json'});
   if(['app.css','rebar.js','rebar_isometric.js','rebar_splitter.js','rebar_splices.js'].includes(name)||name.endsWith('.ttf')){
    const file=path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name);
    return route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
   }return route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-splices.test/');await page.waitForFunction(()=>window.ready);
  const editor=page.locator('.rebar-live-editor'),first=editor.getByLabel('Largo del primer fierro · cm',{exact:true}).first();
  const open=()=>editor.getByRole('button',{name:'Ver y ajustar empalme',exact:true}).first().click();
  const dialog=page.getByRole('dialog'),drawing=dialog.locator('.rebar-splice-preview');
  const waitPreview=()=>page.waitForFunction(()=>document.querySelector('.rebar-splice-dialog')?.getAttribute('aria-busy')==='false');
  const apply=dialog.getByRole('button',{name:'Aplicar largo',exact:true});
  await editor.getByRole('button',{name:'Calcular marcas',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('.rebar-live-editor button.primary')?.disabled);
  const insert=editor.getByRole('button',{name:'Insertar Frontal (FR)',exact:true});await insert.waitFor();
  await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(e=>e.textContent==='Insertar Frontal (FR)'&&!e.disabled));
  await open();await waitPreview();assert.equal(await drawing.locator('[data-splice-mark]').count(),2);
  assert.equal(await drawing.locator('[data-splice-lap]').count(),1);
  assert.equal(await dialog.getByText(/150 cm de traslapo/).count(),1);
  const basePoints=await drawing.locator('[data-splice-mark="1"]').getAttribute('points');
  await dialog.getByLabel('Largo del primer fierro · cm',{exact:true}).fill('900');
  assert.equal(await apply.isDisabled(),true);await waitPreview();
  assert.notEqual(await drawing.locator('[data-splice-mark="1"]').getAttribute('points'),basePoints);
  assert.equal(await dialog.locator('.rebar-splice-legend').getByText('Marca 1 · 900 cm',{exact:true}).count(),1);
  assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.rules[0].first_piece_cm),0,'Draft does not mutate parameters');
  assert.equal(await dialog.getByText(/150 cm de traslapo/).count(),1,'Lap length is unchanged');
  const screenshot=path.join(root,'tmp','rebar-splice-900-preview.png');await dialog.screenshot({path:screenshot});
  await apply.click();await dialog.waitFor({state:'detached'});
  assert.equal(await first.inputValue(),'900');assert.equal(await insert.isDisabled(),true,'Changed length invalidates CAD calculation');
  await editor.getByRole('button',{name:'Calcular marcas',exact:true}).click();
  await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(e=>e.textContent==='Insertar Frontal (FR)'&&!e.disabled));
  assert.equal(await page.evaluate(()=>fixture.calls.filter(c=>c.route==='rebar/preview').at(-1).payload.rules[0].first_piece_cm),900);
  await open();await waitPreview();
  await dialog.getByLabel('Largo del primer fierro · cm',{exact:true}).fill('200');await waitPreview();
  assert.equal(await apply.isDisabled(),true);assert.equal(await drawing.count(),0,'Invalid geometry cannot look current');
  assert.match(await dialog.getByRole('status').textContent(),/traslapo|primer fierro|recto/i);
  await dialog.getByRole('button',{name:'Cerrar',exact:true}).click();assert.equal(await first.inputValue(),'900','Closing discards invalid draft');
  await open();await waitPreview();
  await page.evaluate(()=>fixture.delayNext=1600);
  await dialog.getByLabel('Largo del primer fierro · cm',{exact:true}).fill('1000');
  await page.waitForFunction(()=>fixture.calls.filter(c=>c.route==='rebar/preview').at(-1).payload.rules[0].first_piece_cm===1000);
  await dialog.getByLabel('Largo del primer fierro · cm',{exact:true}).fill('800');await waitPreview();
  await page.waitForTimeout(1800);
  assert.equal(await dialog.locator('.rebar-splice-legend').getByText('Marca 1 · 800 cm',{exact:true}).count(),1,'Late response cannot replace newer preview');
  await dialog.getByRole('button',{name:'Automático',exact:true}).click();await waitPreview();
  assert.equal(await dialog.locator('.rebar-splice-legend').getByText('Marca 1 · 1200 cm',{exact:true}).count(),1);
  await apply.click();assert.equal(await first.inputValue(),'0');
  // Multiple laps and a narrow viewport remain readable and usable.
  await editor.getByLabel('Ancho',{exact:true}).fill('2300');await open();await waitPreview();
  assert.equal(await drawing.locator('[data-splice-mark]').count(),3);assert.equal(await drawing.locator('[data-splice-lap]').count(),2);
  await dialog.screenshot({path:path.join(root,'tmp','rebar-splice-multiple-preview.png')});
  await page.setViewportSize({width:430,height:850});
  assert(await dialog.evaluate(e=>e.scrollWidth<=e.clientWidth+1),'Narrow dialog has no horizontal overflow');
  await dialog.getByRole('button',{name:'Cerrar',exact:true}).click();
  await page.setViewportSize({width:1500,height:1100});
  await editor.getByLabel('Ancho',{exact:true}).fill('4000');await first.fill('500');await open();await waitPreview();
  assert.equal(await drawing.locator('[data-splice-lap]').count(),4);
  const labelsInside=await drawing.evaluate(svg=>{
    const box=svg.viewBox.baseVal;
    return [...svg.querySelectorAll('text')].every(text=>{const b=text.getBBox();return b.y>=box.y&&b.x>=box.x&&b.y+b.height<=box.y+box.height&&b.x+b.width<=box.x+box.width;});
  });assert(labelsInside,'All dimensions remain in the viewBox with four laps');
  await dialog.getByRole('button',{name:'Cerrar',exact:true}).click();
  await editor.getByLabel('Ancho',{exact:true}).fill('500');await open();await waitPreview();
  assert.equal(await drawing.count(),0);assert.match(await dialog.getByRole('status').textContent(),/no necesita empalmes/);
  assert.equal(await apply.isDisabled(),true);await dialog.getByRole('button',{name:'Cerrar',exact:true}).click();
  await first.fill('');
  await page.getByRole('button',{name:'Estribo de salida',exact:true}).click();
  await page.getByRole('button',{name:'Estribo de entrada',exact:true}).click();
  assert.equal(await first.inputValue(),'');assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.rules[0].first_piece_cm),null,'Unfinished input is not silently replaced with automatic');
  assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);
  assert((await page.evaluate(()=>fixture.calls)).every(c=>!c.route.startsWith('cad/')));
  console.log('Splice UI passed: physical pieces, editable shared parameter, unchanged laps, stale response rejection, invalidation, multiple laps, responsive and no CAD access.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
