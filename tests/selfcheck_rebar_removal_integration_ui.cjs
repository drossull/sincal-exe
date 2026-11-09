// Real editor + isometric viewer + Python calculation, in an isolated headless
// browser. No installed SINCAL, user project or running CAD session is touched.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const python=`
import json, sys
from sincal.web.rebar import defaults, preview
from sincal.web.abutment_scene import build_scene
route=sys.argv[1]
payload=json.load(sys.stdin)
if route=='rebar/from-project':
    state=defaults()
    state['geometry']['esviaje_grados']=-12
    result={'entrada':state,'salida':state}
elif route=='rebar/preview':
    result=preview(payload)
elif route=='rebar/abutment/scene':
    result=build_scene(payload['project'],payload['instance_key'],payload['state'],use_state_geometry=True)
else:
    raise ValueError('Forbidden route: '+route)
print(json.dumps(result))
`;
const html='<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8">'+
 '<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"></head>'+
 '<body><main id="host"></main><script type="module" src="/fixture.js"></script></body></html>';
const fixtureJs=`
import {renderRebar} from '/rebar.js';
const project={data:{estribos:{tipo_estribo_entrada:'muro_lleno',tipo_estribo_salida:'muro_lleno'}},identification:{structure_name:'Eliminación individual · prueba local'}};
const fixture=window.fixture={project,calls:[],responses:[],errors:[],notices:[],jobs:[],changes:0,previewDelay:0,releaseCad:null};
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const button=(text,action,primary=false)=>{const e=node('button',text,primary?'primary':'');e.type='button';e.addEventListener('click',async()=>{try{await action();}catch(error){fixture.errors.push(error.message);}});return e;};
const section=(id,title)=>{const e=node('section');e.id=id;e.append(node('h2',title));document.getElementById('host').append(e);return e;};
const api=async(route,payload)=>{
 const request=structuredClone(payload);fixture.calls.push({route,payload:request});
 if(route==='cad/status')return await new Promise(resolve=>fixture.releaseCad=()=>resolve({status:'ready',active:{name:'isolated-fixture.dwg'}}));
 if(route==='rebar/preview'&&fixture.previewDelay){const delay=fixture.previewDelay;fixture.previewDelay=0;await new Promise(resolve=>setTimeout(resolve,delay));}
 const response=await fetch('/api/'+route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
 const result=await response.json();if(!response.ok)throw Error(result.error);fixture.responses.push({route,payload:request,result});return result;
};
const ctx={project,node,button,section,api,current:()=>true,changed:()=>fixture.changes++,notify:message=>fixture.notices.push(message),job:(...args)=>{fixture.jobs.push(args);throw Error('CAD operation forbidden');}};
fixture.mount=async()=>{document.getElementById('host').replaceChildren();await renderRebar(ctx);};
fixture.save=()=>fixture.saved=JSON.stringify(project);
fixture.reload=async()=>{Object.assign(project,JSON.parse(fixture.saved));await fixture.mount();};
await fixture.mount();window.ready=true;
`;

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
  page.setDefaultTimeout(15000);page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:html,contentType:'text/html'});
   if(name==='fixture.js')return route.fulfill({body:fixtureJs,contentType:'text/javascript'});
   if(name.startsWith('api/')){
    try{
     const body=execFileSync(process.env.PYTHON||'python',['-c',python,name.slice(4)],
      {cwd:root,input:route.request().postData()||'{}',encoding:'utf8',maxBuffer:16*1024*1024});
     return route.fulfill({body,contentType:'application/json'});
    }catch(error){return route.fulfill({status:500,body:JSON.stringify({error:String(error)}),contentType:'application/json'});}
   }
   if(['app.css','rebar.js','rebar_isometric.js','rebar_splitter.js','rebar_splices.js'].includes(name)||name.endsWith('.ttf')){
    const file=path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name);
    return route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
   }
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-removal-integration.test/');await page.waitForFunction(()=>window.ready);
  const editor=page.locator('.rebar-live-editor'),embedded=page.locator('.iso-embedded');
  const dialog=page.locator('dialog.rebar-isometric');
  const ready=async()=>page.waitForFunction(()=>document.querySelector('.iso-embedded')?.getAttribute('aria-busy')==='false');
  const calculate=async()=>{await editor.getByRole('button',{name:'Calcular marcas',exact:true}).click();await editor.getByRole('button',{name:'Ampliar tabla de marcas',exact:true}).waitFor();};
  const marks=()=>editor.locator('table tbody tr').evaluateAll(rows=>Object.fromEntries(rows.map(row=>[row.cells[0].textContent,Number(row.cells[3].textContent)])));
  const waitQuantity=async(mark,quantity)=>page.waitForFunction(({mark,quantity})=>Array.from(document.querySelectorAll('.rebar-live-editor table tbody tr')).some(row=>row.cells[0].textContent===mark&&Number(row.cells[3].textContent)===quantity),{mark,quantity});
  const expand=async()=>{await embedded.getByRole('button',{name:'Ampliar visor',exact:true}).click();await page.waitForFunction(()=>document.querySelector('dialog.rebar-isometric')?.getAttribute('aria-busy')==='false');};
  const collapse=async()=>{await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await dialog.waitFor({state:'detached'});await ready();};
  await ready();await calculate();
  const originalMarks=await marks(),sourceData=await page.evaluate(()=>structuredClone(fixture.project.data));
  const baseline=await page.evaluate(()=>fixture.responses.find(item=>item.route==='rebar/preview').result);

  // Keep one explicit insertion awaiting CAD status. A removal must invalidate
  // that ticket before any asynchronous recalculation can complete.
  await editor.getByRole('button',{name:'Insertar Frontal (FR)',exact:true}).click();
  await page.waitForFunction(()=>Boolean(fixture.releaseCad));await expand();
  const point=await dialog.locator('[data-layer="armaduras"] polyline[data-piece]').first().evaluate(el=>{
   const p=el.getPointAtLength(el.getTotalLength()*.35),q=new DOMPoint(p.x,p.y).matrixTransform(el.getScreenCTM());return {x:q.x,y:q.y};
  });
  await page.mouse.click(point.x,point.y);
  const remove=dialog.getByRole('button',{name:'Eliminar este fierro',exact:true});await remove.waitFor();
  const pieceId=await dialog.locator('.iso-piece-panel').getAttribute('data-piece');
  const chosen=await page.evaluate(id=>fixture.responses.filter(item=>item.route==='rebar/abutment/scene').at(-1).result.bars.find(bar=>bar.id===id),pieceId);
  assert(chosen&&chosen.signature);
  await page.evaluate(()=>fixture.previewDelay=800);await remove.click();
  assert.equal(await editor.getByRole('button',{name:'Insertar A–A',exact:true}).isDisabled(),true,'Removal synchronously blocks the previous calculation');
  await page.evaluate(()=>fixture.releaseCad());
  await waitQuantity(chosen.mark,originalMarks[chosen.mark]-1);
  await page.waitForFunction(()=>document.querySelector('dialog.rebar-isometric')?.getAttribute('aria-busy')==='false');
  assert.equal(await dialog.locator(`[data-layer="armaduras"] [data-piece="${pieceId}"]`).count(),0);
  const changedMarks=await marks();assert.deepEqual(changedMarks,{...originalMarks,[chosen.mark]:originalMarks[chosen.mark]-1});
  const modified=await page.evaluate(()=>fixture.responses.filter(item=>item.route==='rebar/preview').at(-1).result);
  assert(modified.total_kg<baseline.total_kg,'Removing a manufactured piece reduces steel weight');
  assert.deepEqual(await page.evaluate(()=>fixture.jobs),[],'The obsolete insertion ticket never reaches a CAD operation');
  assert((await page.evaluate(()=>fixture.notices)).some(message=>message.includes('El cálculo cambió')));
  const record=await page.evaluate(()=>fixture.project.rebar.entrada.rules.flatMap(rule=>rule.removed_pieces||[]));
  assert.deepEqual(record,[{id:chosen.id,signature:chosen.signature}]);
  await collapse();await page.evaluate(()=>fixture.save());

  // The same project JSON restores the physical deletion and lets the user
  // restore it without an in-memory undo history from the preceding mount.
  await page.evaluate(()=>fixture.reload());await ready();await calculate();
  assert.deepEqual(await marks(),changedMarks);
  assert.equal(await embedded.locator(`[data-layer="armaduras"] [data-piece="${pieceId}"]`).count(),0);
  await page.getByRole('button',{name:'Estribo de salida',exact:true}).click();await ready();await calculate();
  assert.deepEqual(await marks(),originalMarks,'Exit abutment keeps its independent quantities');
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.salida.rules.flatMap(rule=>rule.removed_pieces||[])),[]);
  await page.getByRole('button',{name:'Estribo de entrada',exact:true}).click();await ready();await calculate();
  assert.deepEqual(await marks(),changedMarks,'Returning to entry retains the deletion');
  await expand();await dialog.locator('.iso-removed-pieces summary').click();
  await dialog.getByRole('button',{name:/^Restaurar /}).click();
  await waitQuantity(chosen.mark,originalMarks[chosen.mark]);
  await page.waitForFunction(()=>document.querySelector('dialog.rebar-isometric')?.getAttribute('aria-busy')==='false');
  assert.equal(await dialog.locator(`[data-layer="armaduras"] [data-piece="${pieceId}"]`).count(),1);
  assert.deepEqual(await marks(),originalMarks);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.rules.flatMap(rule=>rule.removed_pieces||[])),[]);
  assert.deepEqual(await page.evaluate(()=>fixture.project.data),sourceData);
  assert.equal(await page.evaluate(()=>fixture.calls.filter(call=>call.route==='cad/status').length),1,'Only the test’s explicit insertion requested CAD status');
  assert.deepEqual(await page.evaluate(()=>fixture.jobs),[]);
  assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);assert.deepEqual(errors,[]);
  console.log('OK: eliminación desde visor → tabla y peso reales, ticket CAD invalidado, guardado/recarga, restauración e instancias aisladas; navegador headless sin CAD.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
