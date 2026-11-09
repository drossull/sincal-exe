// Isolated live-preview UI checks. Only local source assets and deterministic
// scene responses are used; no user project, installed app or CAD is touched.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const defaults=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',
  'import json; from sincal.web.rebar import defaults; print(json.dumps(defaults()))'],{cwd:root,encoding:'utf8'}));
const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"></head>
<body><aside id="sidebar"><strong>SINCAL SUITE</strong><nav><button>Generador de armadura</button></nav></aside>
<div id="workspace"><header><button>☰</button><span>Estribos</span></header>
<div class="layout"><main id="main"></main><aside id="outline"><strong>En esta página</strong><nav id="anchors"></nav></aside></div></div>
<script type="module">
import {renderRebar} from '/rebar.js';
const defaults=${JSON.stringify(defaults)};
const project={data:{source:'unchanged JSON fixture'},identification:{structure_name:'Puente de prueba · vista previa en vivo'}};
const fixture=window.fixture={project,calls:[],errors:[],changes:0,current:true,delayNext:0,errorNext:false};
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const button=(label,fn,primary=false)=>{const e=node('button',label,primary?'primary':'');e.type='button';e.addEventListener('click',async()=>{try{await fn();}catch(error){fixture.errors.push(error.message);}});return e;};
const section=(id,label)=>{const e=node('section');e.id=id;e.append(node('h2',label));document.getElementById('main').append(e);return e;};
const mesh=(x,y,z0,z1)=>({vertices:[[-x,-y,z0],[x,-y,z0],[x,y,z0],[-x,y,z0],[-x,-y,z1],[x,-y,z1],[x,y,z1],[-x,y,z1]],faces:[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]]});
function scene(payload){
 const g=payload.state.geometry,l=g.largo_cm,h=g.alto_cm,w=g.ancho_cm,spacing=payload.state.rules[0].spacing_cm;
 if([l,h,w,g.esviaje_grados].some(v=>v===null||!Number.isFinite(v))||Math.min(l,h,w)<=0)return {elements:[],bars:[],issues:['Completa las dimensiones de la zapata.']};
 const label='L='+l+' H='+h+' @='+spacing, count=spacing>0?Math.ceil(w/spacing):0;
 return {units:'m',geometry_source:'parameters',geometry_edited:true,instance_key:payload.instance_key,
  elements:[{key:'abutment.footing',label:'Fundación',meshes:[mesh(w/200,l/200,0,h/100)]},...(l>=500?[{key:'abutment.front_wall',label:'Muro frontal',meshes:[mesh(w/250,.4,h/100,h/100+4)]}]:[])],
  bars:Array.from({length:count},(_,i)=>({key:'mesh_x',mark:'1',label,element_key:'abutment.footing',diameter_mm:22,points:[[-w/200+.1,-l/200+.1+i*(l/100-.2)/Math.max(1,count-1),.2],[w/200-.1,-l/200+.1+i*(l/100-.2)/Math.max(1,count-1),.2]]})),issues:[]};
}
const api=async(route,payload)=>{
 const call={route,payload:structuredClone(payload)};fixture.calls.push(call);
 if(route==='rebar/from-project'){const salida=structuredClone(defaults);salida.geometry.alto_cm=200;return {entrada:structuredClone(defaults),salida};}
 if(route==='rebar/abutment/scene'){
  const result=scene(call.payload),delay=fixture.delayNext,error=fixture.errorNext;fixture.delayNext=0;fixture.errorNext=false;
  if(delay)await new Promise(resolve=>setTimeout(resolve,delay));if(error)throw Error('Fallo de escena simulado');return result;
 }
 if(route==='rebar/preview')return {valid:true,issues:[],marks:[],details:[],total_kg:0};
 throw Error('Forbidden API route: '+route);
};
const ctx={project,api,node,button,section,current:()=>fixture.current,notify:message=>fixture.errors.push(message),changed:()=>fixture.changes++,job:()=>{throw Error('CAD forbidden');}};
fixture.mount=async()=>{fixture.current=true;document.getElementById('main').replaceChildren();await renderRebar(ctx);};
fixture.leave=()=>{fixture.current=false;document.getElementById('main').replaceChildren(node('section','Otra página'));};
await fixture.mount();window.ready=true;
</script></body></html>`;

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:harness,contentType:'text/html'});
   if(['app.css','rebar.js','rebar_isometric.js','rebar_splitter.js','rebar_splices.js'].includes(name)||name.endsWith('.ttf')){
    const file=path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name);
    return route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
   }return route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-live.test/');await page.waitForFunction(()=>window.ready);
  const viewer=page.getByRole('region',{name:'Vista isométrica del estribo',exact:true}),drawing=viewer.getByRole('img');
  const editor=page.locator('.rebar-live-editor');
  const calls=()=>page.evaluate(()=>fixture.calls.filter(c=>c.route==='rebar/abutment/scene'));
  const camera=()=>drawing.evaluate(e=>Object.fromEntries(['yaw','pitch','zoom','scale','target'].map(key=>[key,e.dataset[key]])));
  const label=()=>drawing.locator('[data-layer="armaduras"] title').first().textContent();
  const ready=async()=>{await drawing.waitFor();await page.waitForFunction(()=>document.querySelector('.iso-embedded')?.getAttribute('aria-busy')==='false');};
  const waitLabel=async text=>page.waitForFunction(value=>document.querySelector('.iso-embedded [data-layer="armaduras"] title')?.textContent.includes(value),text);
  const dialog=page.getByRole('dialog',{name:'Vista isométrica del estribo',exact:true});
  const expand=async()=>{await viewer.getByRole('button',{name:'Ampliar visor',exact:true}).click();await dialog.getByRole('img').waitFor();};
  const collapse=async()=>{await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await page.locator('dialog.rebar-isometric').waitFor({state:'detached'});await ready();};
  await ready();assert.equal(await page.getByRole('dialog').count(),0);
  assert.equal(await viewer.locator('details,aside,.iso-mark,.iso-legend').count(),0,'Compact preview has no filter sections or long legend');
  const source=await page.evaluate(()=>structuredClone(fixture.project.data));
  assert.equal((await calls()).length,1);assert.equal((await calls())[0].payload.use_state_geometry,true);
  assert.equal(await editor.getByRole('button',{name:'Insertar Frontal (FR)',exact:true}).isDisabled(),true);

  // The expanded layout stays local to this page and respects saved panel visibility.
  for(const width of [1440,1920]){
   await page.setViewportSize({width,height:1000});
   for(const classes of ['', 'outline-hidden','panels-hidden outline-hidden']){
    await page.evaluate(classes=>document.body.className=classes,classes);
    const [left,right]=await Promise.all([editor.boundingBox(),page.locator('.rebar-live-preview').boundingBox()]);
    assert(right.x>=left.x+left.width+15,'Viewer appears to the right of parameters');
    assert.equal(await page.locator('.layout').evaluate(e=>getComputedStyle(e).maxWidth),'none');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Wide page must not overflow');
   }
  }
  await page.setViewportSize({width:1440,height:1000});
  // Resize the actual editor/viewer pair without recalculating, editing project
  // parameters, or resetting the existing scene and camera.
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const divider=page.getByRole('separator',{name:'Ancho de parámetros y visor'});
  const splitBefore=await editor.boundingBox(),grip=await divider.boundingBox();
  const beforeResize={camera:await camera(),calls:(await calls()).length,state:await page.evaluate(()=>JSON.stringify(fixture.project.rebar)),changes:await page.evaluate(()=>fixture.changes)};
  await page.mouse.move(grip.x+grip.width/2,grip.y+30);await page.mouse.down();
  await page.mouse.move(grip.x+grip.width/2+80,grip.y+30,{steps:4});await page.mouse.up();
  assert(Math.abs((await editor.boundingBox()).width-splitBefore.width-80)<1);
  assert.deepEqual(await camera(),beforeResize.camera);assert.equal((await calls()).length,beforeResize.calls);
  assert.equal(await page.evaluate(()=>JSON.stringify(fixture.project.rebar)),beforeResize.state);
  assert.equal(await page.evaluate(()=>fixture.changes),beforeResize.changes);
  await drawing.focus();await drawing.press('ArrowRight');
  await viewer.getByRole('button',{name:'Acercar',exact:true}).click();
  await expand();
  await dialog.getByRole('checkbox',{name:'Mostrar Muro frontal',exact:true}).uncheck();
  await dialog.getByRole('button',{name:'Muro frontal',exact:true}).click();
  await dialog.getByRole('slider',{name:'Intensidad del moldaje',exact:true}).fill('14');
  await collapse();
  const viewBefore=await camera(),oldPolygon=await drawing.locator('polygon').first().getAttribute('points');
  const originalCount=await drawing.locator('[data-layer="armaduras"] polyline').count();

  // Rapid edits coalesce, update geometry and do not reset navigation or filters.
  const beforeCount=(await calls()).length;
  await editor.getByLabel('Largo',{exact:true}).fill('820');
  await editor.getByLabel('Largo',{exact:true}).fill('830');
  await editor.getByLabel('Largo',{exact:true}).fill('840');
  assert.equal(await viewer.getAttribute('aria-busy'),'true');
  await waitLabel('L=840');await ready();
  assert.equal((await calls()).length,beforeCount+1,'Only the latest rapid input is requested');
  assert.notEqual(await drawing.locator('polygon').first().getAttribute('points'),oldPolygon);
  assert.deepEqual(await camera(),viewBefore);
  assert.equal(await drawing.locator('polygon[data-element="abutment.front_wall"]').count(),0);
  await expand();
  assert.equal(await dialog.getByRole('checkbox',{name:'Mostrar Muro frontal',exact:true}).isChecked(),false);
  assert.equal(await dialog.getByRole('slider',{name:'Intensidad del moldaje',exact:true}).inputValue(),'14');
  await collapse();
  await editor.getByLabel('Alto',{exact:true}).fill('180');await waitLabel('H=180');
  const spacing=editor.getByLabel('Separación · cm',{exact:true}).first();
  await spacing.fill('40');await waitLabel('@=40');
  assert.notEqual(await drawing.locator('[data-layer="armaduras"] polyline').count(),originalCount);
  assert.deepEqual(await camera(),viewBefore);

  // Temporarily omitted geometry retains its hidden state and selection when
  // valid dimensions allow that element to return in the following response.
  await editor.getByLabel('Largo',{exact:true}).fill('300');await waitLabel('L=300');
  await expand();
  assert.equal(await dialog.getByRole('checkbox',{name:'Mostrar Muro frontal',exact:true}).count(),0);
  assert.equal(await dialog.getByRole('button',{name:'Muro frontal',exact:true}).count(),0);
  await collapse();
  await editor.getByLabel('Largo',{exact:true}).fill('840');await waitLabel('L=840');
  await expand();
  assert.equal(await dialog.getByRole('checkbox',{name:'Mostrar Muro frontal',exact:true}).isChecked(),false);
  assert.equal(await dialog.getByRole('button',{name:'Muro frontal',exact:true}).getAttribute('aria-pressed'),'true');
  await collapse();
  assert.equal(await drawing.locator('polygon[data-element="abutment.front_wall"]').count(),0);
  assert.deepEqual(await camera(),viewBefore,'Omitted geometry cannot reset the camera or its saved selection');

  // An incomplete number removes stale geometry, then restores the same camera.
  await editor.getByLabel('Alto',{exact:true}).fill('');await ready();
  await drawing.getByText('No hay elementos visibles con geometría disponible.',{exact:true}).waitFor();
  assert.equal(await drawing.locator('polygon,polyline').count(),0);
  assert.equal(await viewer.locator('.iso-issues').count(),0);
  await expand();
  await dialog.locator('.iso-issues > summary').click();await dialog.getByText('Completa las dimensiones de la zapata.',{exact:true}).waitFor();
  await collapse();
  await editor.getByLabel('Alto',{exact:true}).fill('190');await waitLabel('H=190');
  assert.deepEqual(await camera(),viewBefore,'Recovery retains the last valid camera');

  // A queued reload consumes the newest edit and cancels its still-pending
  // debounce timer, so a slow response cannot cause a redundant third request.
  const n=(await calls()).length;
  await page.evaluate(()=>fixture.delayNext=1200);
  await editor.getByLabel('Largo',{exact:true}).fill('850');
  await page.waitForFunction(n=>fixture.calls.filter(c=>c.route==='rebar/abutment/scene').length>n,n);
  await editor.getByLabel('Largo',{exact:true}).fill('855');
  await page.waitForTimeout(1000);
  await editor.getByLabel('Largo',{exact:true}).fill('860');
  await waitLabel('L=860');await ready();await page.waitForTimeout(350);
  assert.equal((await calls()).length,n+2,'One slow request plus one current follow-up, without a duplicate timer request');
  assert((await label()).includes('L=860'));assert.deepEqual(await camera(),viewBefore);

  // Expansion starts from the inline camera and returns changes on closing.
  await expand();
  assert.deepEqual(await dialog.getByRole('img').evaluate(e=>Object.fromEntries(['yaw','pitch','zoom','scale','target'].map(key=>[key,e.dataset[key]]))),viewBefore);
  assert.equal((await calls()).at(-1).payload.use_state_geometry,true);
  await dialog.getByRole('button',{name:'Acercar',exact:true}).click();
  const expandedCamera=await dialog.getByRole('img').evaluate(e=>Object.fromEntries(['yaw','pitch','zoom','scale','target'].map(key=>[key,e.dataset[key]])));
  await collapse();assert.deepEqual(await camera(),expandedCamera);

  // A pending entry scene must not appear after the user selects the exit abutment.
  const countBeforeSwitch=(await calls()).length;await page.evaluate(()=>fixture.delayNext=700);
  await editor.getByLabel('Alto',{exact:true}).fill('195');
  await page.waitForFunction(n=>fixture.calls.filter(c=>c.route==='rebar/abutment/scene').length>n,countBeforeSwitch);
  await page.getByRole('button',{name:'Estribo de salida',exact:true}).click();await ready();await waitLabel('H=200');
  await page.waitForTimeout(750);await waitLabel('H=200');
  assert.equal(await viewer.getByRole('heading',{name:'Estribo de salida · Isométrica',exact:true}).count(),1);
  assert.equal(await page.locator('.iso-embedded').count(),1);
  await page.getByRole('button',{name:'Estribo de entrada',exact:true}).click();await ready();await waitLabel('H=195');
  assert.equal(await editor.getByLabel('Largo',{exact:true}).inputValue(),'860');

  // Preview requests never unlock CAD insertion; only an explicit calculation does.
  assert.equal(await editor.getByRole('button',{name:'Insertar Frontal (FR)',exact:true}).isDisabled(),true);
  assert.equal(await page.evaluate(()=>fixture.calls.some(c=>c.route==='rebar/preview')),false);
  await editor.getByRole('button',{name:'Calcular marcas',exact:true}).click();
  assert.equal(await editor.getByRole('button',{name:'Insertar Frontal (FR)',exact:true}).isEnabled(),true);
  await editor.getByLabel('Alto',{exact:true}).fill('200');
  assert.equal(await editor.getByRole('button',{name:'Insertar Frontal (FR)',exact:true}).isDisabled(),true);await waitLabel('H=200');

  // Record desktop and stacked mobile layouts for visual inspection.
  fs.mkdirSync(path.join(root,'tmp'),{recursive:true});await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:path.join(root,'tmp/rebar-live-desktop.png')});
  await page.setViewportSize({width:410,height:950});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.equal(await page.locator('.rebar-live-preview').evaluate(e=>getComputedStyle(e).position),'static');
  await page.screenshot({path:path.join(root,'tmp/rebar-live-narrow.png')});
  await viewer.scrollIntoViewIfNeeded();await viewer.screenshot({path:path.join(root,'tmp/rebar-live-narrow-viewer.png')});

  // Navigating away cancels a queued update and restores the original page width.
  await page.setViewportSize({width:1440,height:1000});
  const beforeLeave=(await calls()).length;
  await editor.getByLabel('Alto',{exact:true}).fill('210');await page.evaluate(()=>fixture.leave());
  await page.waitForTimeout(650);assert.equal((await calls()).length,beforeLeave);
  assert.equal(await page.locator('.iso-embedded').count(),0);
  assert.equal(await page.locator('.layout').evaluate(e=>getComputedStyle(e).maxWidth),'1180px');
  assert.deepEqual(await page.evaluate(()=>fixture.project.data),source);
  assert(await page.evaluate(()=>fixture.calls.every(c=>['rebar/from-project','rebar/abutment/scene','rebar/preview'].includes(c.route))));
  assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);assert.deepEqual(errors,[]);
  console.log('OK: visor lateral en vivo; layout aislado/responsive, debounce, cámara/filtros persistentes, parámetros inválidos, respuestas tardías, instancias, ampliación y cálculo explícito; sin CAD.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
