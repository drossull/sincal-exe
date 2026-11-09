// Local geometry preview checks. No native UI, installed app or CAD is used.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const projectData={parametros_generales:{angulo_esviaje_puente:-12},elementos_comunes:{vigas:{num_vigas:4,separacion_vigas:2600,offset_y_vigas:50}},tableros:[
 {nombre_grupo_tablero:'Tablero de referencia',tipo_viga_seleccionado:6,largo_losa:35734.19145,pendiente_longitudinal:-.005,usar_grupo_tablero:true},
 {nombre_grupo_tablero:'Segundo tablero',tipo_viga_seleccionado:3,largo_losa:24000,pendiente_longitudinal:.01,num_vigas:2,usar_grupo_tablero:false},
]};
function backend(project){
 return JSON.parse(execFileSync(process.env.PYTHON||'python',['-c','import sys,json; from sincal.web.beam_preview import preview; d=json.load(sys.stdin); print(json.dumps([[preview(d,i,j) for j in range(4)] for i in range(len(d["tableros"]))]))'],{cwd:root,input:JSON.stringify(project),encoding:'utf8',maxBuffer:64*1024*1024}));
}
const responses=backend(projectData);
const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"></head>
<body><div class="layout"><main id="main"></main></div>
<script type="module">
import {renderBeamPreview} from '/rebar_beam.js';
const fixture=window.fixture={project:{data:${JSON.stringify(projectData)}},responses:${JSON.stringify(responses)},calls:[],errors:[],current:true,delayNext:0,failNext:false};
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const section=(id,title)=>{const e=node('section');e.id=id;e.append(node('h2',title));document.getElementById('main').append(e);return e;};
const api=async(route,payload)=>{
 if(route!=='rebar/beam/preview')throw Error('Forbidden API route: '+route);
 fixture.calls.push({route,payload:structuredClone(payload)});
 const delay=fixture.delayNext,fail=fixture.failNext;fixture.delayNext=0;fixture.failNext=false;
 const response=structuredClone(fixture.responses[payload.board_index][payload.beam_index]);
 if(delay)await new Promise(resolve=>setTimeout(resolve,delay));
 if(fail)throw Error('Fallo simulado');return response;
};
fixture.mount=async()=>{fixture.current=true;document.getElementById('main').replaceChildren();fixture.controller=await renderBeamPreview({project:fixture.project,node,section,api,notify:m=>fixture.errors.push(m),current:()=>fixture.current});};
fixture.leave=()=>{fixture.current=false;document.getElementById('main').replaceChildren(node('p','Otra página'));};
await fixture.mount();window.ready=true;
</script></body></html>`;

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
  page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:harness,contentType:'text/html'});
   if(['app.css','rebar_beam.js'].includes(name)||name.endsWith('.ttf'))return route.fulfill({body:fs.readFileSync(path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://beam-preview.test/');await page.waitForFunction(()=>window.ready);
  const waitReady=()=>page.waitForFunction(()=>document.querySelector('.rebar-beam-page')?.getAttribute('aria-busy')==='false');
  const board=page.getByLabel('Tablero de la viga',{exact:true}),beam=page.getByLabel('Viga del tablero',{exact:true});
  const svg=page.locator('.rebar-beam-svg'),scope=page.getByLabel('Alcance de la vista de viga',{exact:true});
  const selectView=async(label,key)=>{await page.getByRole('button',{name:label,exact:true}).click();assert.equal(await svg.getAttribute('data-view'),key);assert.equal(await page.getByRole('button',{name:label,exact:true}).getAttribute('aria-pressed'),'true');};
  await waitReady();assert(await svg.isVisible());assert.equal(await svg.getAttribute('data-view'),'isometric');assert.equal(await scope.inputValue(),'sample');
  assert.equal(await svg.getAttribute('data-rebar-count'),'6');assert.equal(await svg.locator('.rebar-beam-bar').count(),6);
  // All four cameras project the same definition points; no bars are redistributed.
  for(const [label,key,indices]of [['Frontal','front',[0,2]],['Planta','plan',[1,0]],['Elevación','elevation',[1,2]]]){
   await selectView(label,key);const scale=Number(await svg.getAttribute('data-uniform-scale'));
   const bar=responses[0][0].definition.bars.find(b=>String(b.mark)==='3');
   const plotted=await svg.locator('[data-mark="3"]').evaluate(e=>[...e.points].map(p=>[p.x,p.y]));
   assert.equal(plotted.length,bar.points.length);
   assert(Math.abs(plotted[1][0]-plotted[0][0]-(bar.points[1][indices[0]]-bar.points[0][indices[0]])*scale)<.001);
   assert(Math.abs(plotted[1][1]-plotted[0][1]+(bar.points[1][indices[1]]-bar.points[0][indices[1]])*scale)<.001);
  }
  await selectView('Isométrica','isometric');
  const isoScale=Number(await svg.getAttribute('data-uniform-scale')),yawBefore=Number(await svg.getAttribute('data-camera-yaw'));
  let box=await svg.boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.keyboard.down('Shift');await page.mouse.down({button:'middle'});await page.mouse.move(box.x+box.width/2+40,box.y+box.height/2+20);await page.mouse.up({button:'middle'});await page.keyboard.up('Shift');
  assert(Number(await svg.getAttribute('data-camera-yaw'))!==yawBefore);assert.equal(Number(await svg.getAttribute('data-uniform-scale')),isoScale);assert.equal(await svg.getAttribute('data-z-vertical'),'true');
  const orbitYaw=await svg.getAttribute('data-camera-yaw');await selectView('Frontal','front');await selectView('Isométrica','isometric');assert.equal(await svg.getAttribute('data-camera-yaw'),orbitYaw);
  await page.getByRole('button',{name:'Ajustar',exact:true}).click();
  await scope.selectOption('full');await selectView('Elevación','elevation');
  assert.equal(await svg.getAttribute('data-rebar-count'),'0');assert.equal(await svg.locator('.rebar-beam-bar').count(),0);
  const elevation=svg;
  assert.equal(await board.locator('option').count(),2);assert.equal(await beam.locator('option').count(),4);
  assert((await page.locator('.rebar-beam-summary').textContent()).includes('35,634 m'));
  const point=svg=>svg.locator('.rebar-beam-outline').evaluate(e=>[e.points[0].x,e.points[0].y]);
  const original=await point(elevation);
  const scale=Number(await elevation.getAttribute('data-uniform-scale'));
  const source=responses[0][0].views.elevation.outline;
  const plotted=await elevation.locator('.rebar-beam-outline').evaluate(e=>[...e.points].map(p=>[p.x,p.y]));
  for(let i=1;i<source.length;i++){
   assert(Math.abs((plotted[i][0]-plotted[0][0])-(source[i][0]-source[0][0])*scale)<.001);
   assert(Math.abs((plotted[i][1]-plotted[0][1])+(source[i][1]-source[0][1])*scale)<.001);
  }
  await page.getByRole('button',{name:'Acercar vistas de la viga',exact:true}).click();
  assert(Number(await elevation.getAttribute('data-uniform-scale'))>scale);
  let before=await point(elevation);box=await elevation.boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down({button:'middle'});await page.mouse.move(box.x+box.width/2+30,box.y+box.height/2+18);await page.mouse.up({button:'middle'});
  let after=await point(elevation);assert(Math.abs(after[0]-before[0]-30)<.1);assert(Math.abs(after[1]-before[1]-18)<.1);
  before=after;box=await elevation.boundingBox();const anchor=[box.width/2+40,box.height/2+20];
  const scaleBeforeWheel=Number(await elevation.getAttribute('data-uniform-scale'));
  await page.mouse.move(box.x+anchor[0],box.y+anchor[1]);await page.mouse.wheel(0,-100);
  await page.waitForFunction(value=>Number(document.querySelector('[data-view=elevation]').getAttribute('data-uniform-scale'))>value,scaleBeforeWheel);
  after=await point(elevation);assert(Math.abs(after[0]-(anchor[0]+(before[0]-anchor[0])*1.15))<.3);assert(Math.abs(after[1]-(anchor[1]+(before[1]-anchor[1])*1.15))<.3);
  await page.getByRole('button',{name:'Ajustar',exact:true}).click();after=await point(elevation);assert(Math.abs(after[0]-original[0])<.001&&Math.abs(after[1]-original[1])<.001);
  await scope.selectOption('sample');await selectView('Isométrica','isometric');
  await page.getByRole('button',{name:'Ampliar vistas',exact:true}).click();
  assert.equal(await page.locator('dialog[open] .rebar-beam-svg').count(),1);assert.equal(await page.locator('dialog [style]').count(),0);
  assert((await page.locator('dialog .rebar-beam-status').textContent()).includes('encuentros y reparto pendientes'));
  const modalIssues=await page.locator('dialog .rebar-beam-messages').textContent();
  assert.doesNotMatch(modalIssues,/marca 3[^.]*ancho de encaje pendiente/i);
  assert.equal(await svg.locator('[data-mark="3"] title').textContent(),'Marca 3');
  await page.getByRole('button',{name:'Acercar vistas de la viga',exact:true}).click();const expandedZoom=await page.locator('.rebar-beam-zoom').textContent();
  await page.getByRole('button',{name:'Cerrar vistas',exact:true}).click();await page.locator('dialog').waitFor({state:'detached'});assert.equal(await page.locator('.rebar-beam-zoom').textContent(),expandedZoom);assert.equal(await page.locator('dialog').count(),0);
  await board.selectOption('1');await waitReady();assert.equal(await beam.locator('option').count(),2);assert((await page.locator('.rebar-beam-summary').textContent()).includes('Viga H151'));
  await beam.selectOption('1');await waitReady();assert.equal((await page.evaluate(()=>fixture.calls.at(-1))).payload.beam_index,1);
  await page.evaluate(()=>fixture.delayNext=250);await board.selectOption('0');await board.selectOption('1');await waitReady();
  await page.waitForTimeout(300);assert.equal(await board.inputValue(),'1');assert.equal(await beam.inputValue(),'0');assert((await page.locator('.rebar-beam-summary').textContent()).includes('Viga H151'));
  await page.setViewportSize({width:440,height:980});await waitReady();assert(await svg.isVisible());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.equal(await page.locator('.rebar-beam-page [style]').count(),0);
  const baseline=JSON.stringify(projectData);assert.equal(await page.evaluate(()=>JSON.stringify(fixture.project.data)),baseline);
  await page.evaluate(()=>{fixture.delayNext=200;fixture.failNext=true;});await beam.selectOption('1');await page.evaluate(()=>fixture.leave());await page.waitForTimeout(250);assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);
  await page.evaluate(()=>fixture.mount());await waitReady();assert.equal(await board.inputValue(),'1');
  // Domain errors remain visible and never leave an older drawing on screen.
  await page.evaluate(()=>{fixture.responses[0][0].valid=false;fixture.responses[0][0].issues=['Perfil sin medidas'];});await board.selectOption('0');await waitReady();await page.getByText('Perfil sin medidas',{exact:true}).waitFor();assert(!(await svg.isVisible()));
  await page.evaluate(()=>{fixture.project={data:{}};return fixture.mount();});await page.getByText('Incorpora el JSON del puente en Proyecto para ver la viga.',{exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  // Capture the actual T34 geometry when the local reference is available.
  const actual=process.env.SINCAL_BEAM_PROJECT_JSON||'C:/Users/Usuario/Documents/SINCAL/G131/SSE/34 Puente Aconcagua CS/T34.json';
  if(fs.existsSync(actual)){
   const source=JSON.parse(fs.readFileSync(actual,'utf8').replace(/^\uFEFF/,'')),actualResponses=backend(source);
   await page.setViewportSize({width:1500,height:1100});
   await page.evaluate(async({source,responses})=>{fixture.project={data:source};fixture.responses=responses;await fixture.mount();},{source,responses:actualResponses});await waitReady();
   const screenshot=path.join(root,'tmp/t34-viga-cuatro-vistas-ui.png');fs.mkdirSync(path.dirname(screenshot),{recursive:true});await page.locator('.rebar-beam-page').screenshot({path:screenshot});
   await page.getByRole('button',{name:'Ampliar vistas',exact:true}).click();await page.locator('dialog').screenshot({path:path.join(root,'tmp/t34-viga-cuatro-vistas-ampliado.png')});
  }
  console.log('OK: four beam views, shared definition, full geometry, true scale, X/Y zoom/pan, Z-fixed orbit, dialog with scope/issues, selections, stale responses, empty/error states, narrow layout and JSON preservation; no CAD calls.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
