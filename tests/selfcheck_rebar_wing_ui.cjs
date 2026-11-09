// Local source UI checks only; synthetic project responses, strict CSP, no CAD.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/fixture.css"></head>
<body class="outline-hidden"><div class="layout"><main id="main"></main></div>
<script nonce="fixture" type="module">
import {renderRebarAssistant} from '/rebar_assistant.js';
import {renderWingRebar} from '/rebar_wing.js';
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
const fixture=window.fixture={changes:0,calls:[],errors:[],viewerCallbacks:[],current:true,present:true,delayNext:0,sourceLength:600};
const project=fixture.project={data:{source:'original JSON'},identification:{structure_name:'Puente de prueba'},rebar:{}};
const baseline=side=>({geometry:{thickness_cm:80,main_length_cm:fixture.sourceLength,extension_length_cm:150,top_join_cm:520,top_edge_cm:490,top_tip_cm:450,tip_height_cm:180,front_height_cm:360,front_depth_cm:100,back_thickness_cm:60},geometry_confirmed:false,
 cover:{outside_cm:null,inside_cm:null,top_cm:null,end_cm:null,diagonal_cm:null},vertical:{diameter_mm:null,spacing_cm:null,hook_bottom_cm:40,hook_top_cm:40,mark_main:'',mark_extension:''},horizontal:{diameter_mm:null,spacing_cm:null,hook_ala_cm:40,hook_join_cm:40,mark_main:'',mark_upper:''},outer_family:'vertical',horizontal_start:'wall',removed_pieces:[]});
const footing=()=>({geometry:{ancho_cm:1200,largo_cm:750,alto_cm:150,esviaje_grados:0},cover:{inferior_cm:7.5,superior_cm:5,lateral_cm:5},rules:[]});
function result(state,side){
 const valid=state.geometry_confirmed&&Object.values(state.cover).every(v=>typeof v==='number')&&[state.vertical.diameter_mm,state.vertical.spacing_cm,state.horizontal.diameter_mm,state.horizontal.spacing_cm,state.horizontal.hook_join_cm].every(v=>typeof v==='number'&&v>0)&&state.outer_family&&state.horizontal_start&&state.vertical.mark_main;
 const count=Math.max(0,Math.ceil(state.geometry.main_length_cm/(state.vertical.spacing_cm||20))-(state.removed_pieces||[]).length),mark=state.vertical.mark_main||'7';
 const piece={key:'wing_vertical',mark,quantity:count,diameter_mm:state.vertical.diameter_mm,spacing_cm:state.vertical.spacing_cm,total_cm:580,measured_cm:579.2,developed_length_cm:579.2,points_m:[[0,-.4],[0,0],[5,0],[5,-.4]],vertices_m:[[0,-.4],[0,0],[5,0],[5,-.4]],bulges:[0,0,0,0],partials_cm:[40,500,40],partial_segments_m:[[[0,-.4],[0,0]],[[0,0],[5,0]],[[5,0],[5,-.4]]],partial_ranges_cm:[{min_cm:40,max_cm:40},{min_cm:500,max_cm:500},{min_cm:40,max_cm:40}],length_variants:[],bends:[]};
 return {valid:Boolean(valid),issues:[{message:'Separación evaluada: '+state.vertical.spacing_cm,severity:'info'}],marks:valid?[{key:piece.key,mark,element:side==='left'?'Ala izquierda':'Ala derecha',location:'Malla exterior · vertical',quantity:count,diameter_mm:piece.diameter_mm,spacing_cm:piece.spacing_cm,unit_length_cm:580,total_length_cm:580*count,area_cm2:2.011,kg:580*count*.0158,views:['BB','DD','EE'],piece_role:'completa',bend_radius_cm:4.8,length_variants:[]}]:[],details:valid?[piece]:[],bars:[],total_kg:580*count*.0158};
}
const mesh={vertices:[[-3,-2,0],[3,-2,0],[3,2,0],[-3,2,0],[-3,-2,1.5],[3,-2,1.5],[3,2,1.5],[-3,2,1.5]],faces:[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]]};
const api=async(route,payload)=>{
 fixture.calls.push({route,payload:structuredClone(payload)});
 if(route==='rebar/catalog')return {structures:[{key:'abutment',label:'Estribos',folder:'1-ESTRIBO',instances:['entrada','salida'].map(key=>({key,label:key==='entrada'?'Estribo de entrada':'Estribo de salida',elements:[{key:'abutment.footing',label:'Zapata',present:true,views:['FR','AA']},{key:'abutment.left_wing',label:'Ala izquierda',present:true,views:['BB','DD','EE']},{key:'abutment.right_wing',label:'Ala derecha',present:true,views:['CC','DD','EE']}]}))}]};
 if(route==='rebar/from-project')return {entrada:footing(),salida:footing()};
 if(route==='rebar/wing/from-project')return {present:fixture.present,state:baseline(payload.side),issues:[]};
 if(route==='rebar/abutment/scene')return {elements:[{key:'abutment.footing',label:'Zapata',meshes:[mesh]},{key:'abutment.left_wing',label:'Ala izquierda',meshes:[mesh]},{key:'abutment.right_wing',label:'Ala derecha',meshes:[mesh]}],bars:[],issues:[]};
 if(route==='rebar/wing/preview'){const response=result(payload.state,payload.side),delay=fixture.delayNext;fixture.delayNext=0;if(delay)await new Promise(resolve=>setTimeout(resolve,delay));return response;}
 throw Error('Forbidden API '+route);
};
const button=(label,fn,primary=false)=>{const b=node('button',label,primary?'primary':'');b.type='button';b.onclick=()=>Promise.resolve(fn()).catch(error=>fixture.errors.push(error.message));return b;};
const ctx={project,api,node,button,changed:()=>fixture.changes++,current:()=>fixture.current,notify:message=>fixture.errors.push(message),job:()=>{throw Error('CAD forbidden');},section:(id,label)=>{const s=node('section');s.id=id;s.append(node('h2',label));document.querySelector('main').append(s);return s;}};
fixture.render=async(instance='entrada',side='left')=>{document.querySelector('main').replaceChildren();const s=ctx.section('asistente-armaduras','Asistente de armaduras');const host=node('div',undefined,'rebar-assistant-inspector');s.append(host);fixture.controller=await renderWingRebar(ctx,host,instance,side);};
await renderRebarAssistant(ctx);window.ready=true;
</script></body></html>`;

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[],csp=[];
  page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));page.on('console',m=>{if(m.text().includes('Content Security Policy'))csp.push(m.text());});
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:harness,contentType:'text/html',headers:{'Content-Security-Policy':"default-src 'self'; script-src 'self' 'nonce-fixture'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'"}});
   if(name==='fixture.css')return route.fulfill({body:'body{padding:0}.layout{margin:0 auto}.rebar-wing-host{min-width:0}',contentType:'text/css'});
   const allowed=['app.css','rebar_assistant.js','rebar_wing.js','rebar_wing_ranges.js','rebar_pile.js','rebar.js','rebar_isometric.js','rebar_splitter.js','rebar_splices.js'];
   if(allowed.includes(name)||name.endsWith('.ttf')){
    let body=fs.readFileSync(path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name));
    if(name==='rebar_isometric.js')body=body.toString().replace('export function mountAbutmentIsometric(ctx,instanceKey,host,options={}){','export function mountAbutmentIsometric(ctx,instanceKey,host,options={}){ window.fixture.viewerCallbacks.push(options.onPiecesChanged);');
    return route.fulfill({body,contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
   }
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-wing.test/');await page.waitForFunction(()=>window.ready);
  await page.getByRole('button',{name:'Ala izquierda Mallas del ala',exact:true}).first().click();
  const wing=page.locator('.rebar-wing'),field=label=>wing.getByLabel(label,{exact:true});
  const evaluated=async value=>wing.getByText('Separación evaluada: '+value,{exact:true}).waitFor();
  const ready=async()=>{await page.waitForFunction(()=>document.querySelector('.rebar-wing-output')?.getAttribute('aria-busy')==='false');};
  await evaluated(null);await ready();
  const source=await page.evaluate(()=>structuredClone(fixture.project.data));
  for(const label of ['Recubrimiento exterior · cm','Recubrimiento interior · cm','Recubrimiento superior · cm','Recubrimiento en extremos · cm','Recubrimiento en diagonal · cm','Diámetro vertical · mm','Separación vertical · cm','Diámetro horizontal · mm','Marca vertical del ala'])assert.equal(await field(label).inputValue(),'');
  assert.equal(await field('Familia más exterior').count(),0);assert.equal(await field('Inicio del reparto horizontal').count(),0);
  assert.deepEqual(await page.evaluate(()=>[fixture.project.rebar.entrada.wings.left.outer_family,fixture.project.rebar.entrada.wings.left.horizontal_start]),['vertical','wall']);
  for(const text of ['Los fierros verticales van por fuera; los horizontales quedan pegados por dentro.','Los horizontales comienzan en la base del muro, sobre la zapata.','Cuando el ala está girada, el fierro horizontal se dobla en el encuentro y continúa siguiendo ambas caras.'])assert.equal(await wing.getByText(text,{exact:true}).count(),1);
  assert.equal(await field('Gancho inferior vertical · cm').inputValue(),'40');assert.equal(await field('Gancho superior vertical · cm').inputValue(),'40');assert.equal(await field('Gancho horizontal en el ala · cm').inputValue(),'40');
  assert.equal(await field('Gancho horizontal en el encuentro · cm').inputValue(),'40');
  assert.deepEqual(await page.evaluate(()=>{const s=fixture.project.rebar.entrada.wings.left;return [s.interior.horizontal.hook_join_cm,s.supplements.front.hook_cm,s.supplements.back.hook_cm];}),[40,40,40]);
  assert.equal(await field('Confirmo las cotas y dimensiones del ala').isChecked(),false);
  const [left,right]=await Promise.all([wing.locator('.rebar-live-editor').boundingBox(),wing.locator('.rebar-live-preview').boundingBox()]);
  assert(right.x>=left.x+left.width+15,'Wing preview appears beside its controls');
  const separator=wing.getByRole('separator',{name:'Ancho de parámetros y visor'});await separator.focus();await page.keyboard.press('ArrowRight');
  assert.equal(await page.getByRole('button',{name:/^Insertar/}).count(),0);
  const values=[['Recubrimiento exterior · cm',5],['Recubrimiento interior · cm',5],['Recubrimiento superior · cm',5],['Recubrimiento en extremos · cm',5],['Recubrimiento en diagonal · cm',5],['Diámetro vertical · mm',16],['Separación vertical · cm',20],['Diámetro horizontal · mm',16],['Separación horizontal · cm',20],['Gancho horizontal en el encuentro · cm',50],['Marca vertical del ala','7'],['Marca vertical de la aleta','8'],['Marca horizontal principal','9'],['Marca horizontal superior','10']];
  for(const [label,value] of values)await field(label).fill(String(value));
  await field('Confirmo las cotas y dimensiones del ala').check();
  await wing.getByRole('table',{name:'Marcas de ala izquierda',exact:true}).waitFor();await ready();
  assert.equal(await wing.getByRole('columnheader').count(),12);
  await wing.getByRole('button',{name:'7',exact:true}).click();
  const detail=page.locator('dialog.rebar-detail-dialog');await detail.waitFor();assert.equal(await detail.locator('svg[data-dimstyle="GSG_COTAS"]').count(),1);
  await detail.getByRole('button',{name:'Cerrar',exact:true}).click();await detail.waitFor({state:'detached'});
  await wing.getByRole('button',{name:'Ampliar tabla de marcas'}).click();
  const marks=page.getByRole('dialog',{name:'Marcas · Ala izquierda · entrada',exact:true});await marks.waitFor();assert.equal(await marks.getByRole('columnheader',{name:'Rol',exact:true}).count(),1);
  await marks.getByRole('button',{name:'Cerrar tabla'}).click();
  const screenshot=process.env.SINCAL_WING_UI_SCREENSHOT||path.join(root,'tmp','wing-rebar-ui.png');fs.mkdirSync(path.dirname(screenshot),{recursive:true});
  await wing.locator('.rebar-live-shell').evaluate(element=>element.scrollIntoView({block:'start'}));await page.screenshot({path:screenshot});
  await page.setViewportSize({width:440,height:950});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:screenshot.replace(/\.png$/,'-narrow.png'),fullPage:true});await page.setViewportSize({width:1920,height:1080});
  await field('Largo principal del ala · cm').fill('610');assert.equal(await field('Confirmo las cotas y dimensiones del ala').isChecked(),false);await ready();
  await field('Confirmo las cotas y dimensiones del ala').check();await ready();
  await page.evaluate(()=>{fixture.delayNext=800;});await field('Separación vertical · cm').fill('25');
  await page.waitForFunction(()=>fixture.calls.some(call=>call.route==='rebar/wing/preview'&&call.payload.state.vertical.spacing_cm===25));
  await field('Separación vertical · cm').fill('30');await evaluated(30);await page.waitForTimeout(850);assert.equal(await wing.getByText('Separación evaluada: 25',{exact:true}).count(),0);
  // The viewer callback refreshes quantities after its own persisted edit.
  const changes=await page.evaluate(()=>fixture.changes);
  await page.evaluate(()=>{fixture.project.rebar.entrada.wings.left.removed_pieces.push({id:'one',signature:'a'.repeat(64)});return fixture.viewerCallbacks.at(-1)('entrada');});await ready();
  assert.equal(await page.evaluate(()=>fixture.changes),changes,'Viewer already saves its edit; callback must not save it twice');
  assert.equal(await wing.getByRole('table').locator('tbody tr td').nth(3).textContent(),'20');
  const saved=await page.evaluate(()=>structuredClone(fixture.project.rebar.entrada.wings.left));
  await page.evaluate(()=>{fixture.sourceLength=999;return fixture.render('entrada','right');});await evaluated(null);assert.equal(await field('Largo principal del ala · cm').inputValue(),'999');
  await page.evaluate(()=>fixture.render('salida','left'));await evaluated(null);assert.equal(await field('Diámetro vertical · mm').inputValue(),'');
  await page.evaluate(()=>fixture.render('entrada','left'));await evaluated(30);assert.equal(await field('Largo principal del ala · cm').inputValue(),'610');assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left),saved);
  // Drafts saved before the rules were fixed migrate only these two nulls.
  const beforeMigration=await page.evaluate(()=>({geometry:structuredClone(fixture.project.rebar.entrada.geometry),rules:structuredClone(fixture.project.rebar.entrada.rules),otherWing:structuredClone(fixture.project.rebar.entrada.wings.right),changes:fixture.changes}));
  await page.evaluate(()=>{fixture.project.rebar.entrada.wings.left.outer_family=null;fixture.project.rebar.entrada.wings.left.horizontal_start=null;return fixture.render('entrada','left');});await evaluated(30);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left),saved);
  assert.deepEqual(await page.evaluate(()=>({geometry:fixture.project.rebar.entrada.geometry,rules:fixture.project.rebar.entrada.rules,otherWing:fixture.project.rebar.entrada.wings.right,changes:fixture.changes})),{...beforeMigration,changes:beforeMigration.changes+1});
  await field('Recubrimiento interior · cm').fill('');await ready();assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left.cover.inside_cm),null);
  assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.wings.right.cover.inside_cm),null);
  await field('Gancho horizontal en el encuentro · cm').fill('');await ready();
  await page.evaluate(()=>fixture.render('entrada','left'));await evaluated(30);
  assert.equal(await field('Gancho horizontal en el encuentro · cm').inputValue(),'');
  assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left.horizontal.hook_join_cm),null);
  const prior=await page.evaluate(()=>structuredClone(fixture.project.rebar.entrada.wings.left));
  await page.evaluate(()=>{fixture.present=false;return fixture.render();});await wing.getByText('Este proyecto no contiene un muro ala compatible para esta configuración.',{exact:true}).waitFor();assert.equal(await wing.locator('input,svg').count(),0);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left),prior);assert.deepEqual(await page.evaluate(()=>fixture.project.data),source);
  assert.deepEqual(errors,[]);assert.deepEqual(csp,[]);assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);
  assert((await page.evaluate(()=>fixture.calls)).every(call=>['rebar/catalog','rebar/from-project','rebar/wing/from-project','rebar/wing/preview','rebar/abutment/scene'].includes(call.route)));
  console.log('OK: inspector de alas, campos vacíos, reglas fijas y migración acotada, alturas confirmadas, parámetros independientes, persistencia, respuestas tardías, visor con divisor, tabla y despiece GSG_COTAS; CSP; sin CAD.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
