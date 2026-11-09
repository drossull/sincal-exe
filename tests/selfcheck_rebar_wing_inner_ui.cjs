// Interior meshes are opt-in, copied once, then edited independently per side.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"></head><body class="outline-hidden"><div class="layout"><main></main></div><script nonce="fixture" type="module">
import {renderWingRebar} from '/rebar_wing.js';
const fixture=window.fixture={changes:0,calls:[],errors:[],current:true};
const inner=()=>({enabled:false,parameters_initialized:false,vertical:{diameter_mm:null,spacing_cm:null,hook_bottom_cm:40,hook_top_cm:40,mark_main:'',mark_extension:''},horizontal:{diameter_mm:null,spacing_cm:null,hook_ala_cm:40,hook_join_cm:null,mark_main:'',mark_upper:''},removed_pieces:[]});
const wing=()=>({geometry:{thickness_cm:100,main_length_cm:600,extension_length_cm:150,top_join_cm:500,top_edge_cm:450,top_tip_cm:400,tip_height_cm:150,front_height_cm:300,front_depth_cm:100,back_thickness_cm:60},geometry_confirmed:true,cover:{outside_cm:5,inside_cm:5,top_cm:5,end_cm:5,diagonal_cm:5},vertical:{diameter_mm:16,spacing_cm:20,hook_bottom_cm:35,hook_top_cm:45,mark_main:'11',mark_extension:'12'},horizontal:{diameter_mm:12,spacing_cm:15,hook_ala_cm:50,hook_join_cm:60,mark_main:'13',mark_upper:'14'},outer_family:'vertical',horizontal_start:'wall',removed_pieces:[]});
const abutment=()=>({geometry:{ancho_cm:1200,largo_cm:750,alto_cm:150,esviaje_grados:0},cover:{inferior_cm:7.5,superior_cm:5,lateral_cm:5},rules:[],wings:{left:wing(),right:wing()}});
const project=fixture.project={data:{source:'JSON original'},rebar:{entrada:abutment(),salida:abutment()}};
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
const button=(label,fn)=>{const el=node('button',label);el.type='button';el.onclick=()=>Promise.resolve(fn()).catch(error=>fixture.errors.push(error.message));return el;};
const result=state=>{
 const mark=(number,location)=>({key:location,mark:number,element:'Ala izquierda',location,quantity:10,diameter_mm:16,spacing_cm:20,unit_length_cm:580,total_length_cm:5800,area_cm2:2.011,kg:91.64,views:['BB'],piece_role:'completa',length_variants:[]});
 const innerValid=!state.interior.enabled||Object.values(state.interior.vertical).every(value=>value!==null&&value!=='')&&Object.values(state.interior.horizontal).every(value=>value!==null&&value!=='');
 return {valid:innerValid,issues:innerValid?[]:[{message:'Completa las marcas interiores.',severity:'error'}],marks:[mark(state.vertical.mark_main,'Malla exterior'),...(state.interior.enabled&&innerValid?[mark(state.interior.vertical.mark_main,'Malla interior')]:[])],details:[],bars:[],total_kg:innerValid&&state.interior.enabled?183.28:91.64};
};
const api=async(route,payload)=>{fixture.calls.push({route,payload:structuredClone(payload)});
 if(route==='rebar/wing/from-project')return {present:true,state:{...wing(),interior:inner()},issues:[]};
 if(route==='rebar/wing/preview')return result(payload.state);
 if(route==='rebar/abutment/scene')return {elements:[],bars:[],issues:[]};
 throw Error('Unexpected/CAD API '+route);
};
const ctx={project,node,button,api,current:()=>fixture.current,changed:()=>fixture.changes++,notify:message=>fixture.errors.push(message)};
fixture.render=async(instance='entrada',side='left')=>{fixture.controller?.dispose();document.querySelector('main').replaceChildren();const section=node('section');section.id='asistente-armaduras';const host=node('div',undefined,'rebar-assistant-inspector');section.append(host);document.querySelector('main').append(section);fixture.controller=await renderWingRebar(ctx,host,instance,side);};
await fixture.render();window.ready=true;
</script></body></html>`;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[],csp=[];
  page.setDefaultTimeout(12000);page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.text().includes('Content Security Policy'))csp.push(message.text());});
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:harness,contentType:'text/html',headers:{'Content-Security-Policy':"default-src 'self'; script-src 'self' 'nonce-fixture'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'"}});
   const file=path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name);
   return fs.existsSync(file)?route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'}):route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-wing-inner.test/');await page.waitForFunction(()=>window.ready);
  const wing=page.locator('.rebar-wing'),field=label=>wing.getByLabel(label,{exact:true});
  const ready=()=>page.waitForFunction(()=>document.querySelector('.rebar-wing-output')?.getAttribute('aria-busy')==='false');
  const state=()=>page.evaluate(()=>structuredClone(fixture.project.rebar.entrada.wings.left));
  const initial=await page.evaluate(()=>structuredClone(fixture.project));
  assert.equal((await state()).interior.enabled,false);assert.equal((await state()).interior.parameters_initialized,false);
  assert.equal(await field('Diámetro interior vertical · mm').count(),0);
  assert.equal(await wing.getByRole('table').locator('tbody tr').count(),1);
  // First activation copies every known numerical parameter, never outer marks.
  await field('Incluir malla interior').check();await ready();
  let current=await state();assert(current.interior.enabled);assert(current.interior.parameters_initialized);
  for(const group of ['vertical','horizontal'])for(const [key,value] of Object.entries(current[group]))assert.deepEqual(current.interior[group][key],key.startsWith('mark_')?'':value);
  assert.equal(await wing.getByText('Hay datos o armaduras pendientes. Se muestran sólo las marcas que pudieron calcularse.',{exact:true}).count(),1);
  assert.equal(await wing.getByRole('table').locator('tbody tr').count(),1,'Valid exterior rows stay visible while interior marks are incomplete');
  for(const [label,value] of [['Marca interior vertical del ala','21'],['Marca interior vertical de la aleta','22'],['Marca interior horizontal principal','23'],['Marca interior horizontal superior','24'],['Diámetro interior vertical · mm',22],['Separación interior vertical · cm',12],['Gancho interior superior vertical · cm',55],['Gancho interior horizontal en el encuentro · cm',65]])await field(label).fill(String(value));
  await ready();assert.equal(await wing.getByRole('table').locator('tbody tr').count(),2);
  const removal={id:'wing:left:inner_vertical_main:0',signature:'c'.repeat(64)};
  await page.evaluate(record=>{fixture.project.rebar.entrada.wings.left.interior.removed_pieces=[record];},removal);
  current=await state();const innerSaved=structuredClone(current.interior);
  // Editing the exterior after activation does not silently copy over interior.
  await field('Diámetro vertical · mm').fill('25');await field('Gancho horizontal en el encuentro · cm').fill('75');await ready();
  assert.deepEqual((await state()).interior,innerSaved);
  await field('Incluir malla interior').uncheck();await ready();assert.equal(await wing.getByRole('table').locator('tbody tr').count(),1);
  await page.evaluate(()=>fixture.render());await ready();await field('Incluir malla interior').check();await ready();
  assert.deepEqual((await state()).interior,innerSaved);
  // The explicit copy refreshes parameters and preserves all four marks/bajas.
  await wing.getByRole('button',{name:'Copiar parámetros de la malla exterior',exact:true}).click();await ready();current=await state();
  for(const group of ['vertical','horizontal'])for(const [key,value] of Object.entries(current[group]))assert.deepEqual(current.interior[group][key],key.startsWith('mark_')?innerSaved[group][key]:value);
  assert.deepEqual(current.interior.removed_pieces,[removal]);assert.equal(await field('Diámetro interior vertical · mm').inputValue(),'25');
  // An intentionally cleared initialized draft stays empty after reopening.
  await field('Diámetro interior vertical · mm').fill('');await field('Separación interior vertical · cm').fill('');await ready();
  await field('Incluir malla interior').uncheck();await ready();await page.evaluate(()=>fixture.render());await field('Incluir malla interior').check();await ready();
  assert.equal(await field('Diámetro interior vertical · mm').inputValue(),'');assert.equal(await field('Separación interior vertical · cm').inputValue(),'');
  assert.deepEqual((await state()).interior.removed_pieces,[removal]);
  const saved=await state();
  await page.evaluate(()=>fixture.render('entrada','right'));await ready();assert.equal(await field('Incluir malla interior').isChecked(),false);
  await page.evaluate(()=>fixture.render('salida','left'));await ready();assert.equal(await field('Incluir malla interior').isChecked(),false);
  await page.evaluate(()=>fixture.render('entrada','left'));await ready();assert.deepEqual(await state(),saved);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.geometry),initial.rebar.entrada.geometry);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.rules),initial.rebar.entrada.rules);
  assert.deepEqual(await page.evaluate(()=>fixture.project.data),initial.data);
  // Earlier interior drafts without the indicator count as already edited when
  // they contain parameters, enabling, or removals; enabling must preserve them.
  await page.evaluate(()=>{const wing=fixture.project.rebar.entrada.wings.left;delete wing.interior.parameters_initialized;wing.interior.enabled=false;wing.interior.vertical.diameter_mm=18;return fixture.render();});await ready();
  assert.equal((await state()).interior.parameters_initialized,true);await field('Incluir malla interior').check();await ready();assert.equal(await field('Diámetro interior vertical · mm').inputValue(),'18');
  await page.setViewportSize({width:440,height:950});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);assert.deepEqual(csp,[]);assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);
  assert((await page.evaluate(()=>fixture.calls)).every(call=>['rebar/wing/from-project','rebar/wing/preview','rebar/abutment/scene'].includes(call.route)));
  console.log('OK: malla interior optativa, primera copia persistente, edición independiente, copia explícita sin cambiar marcas/bajas, tabla combinada parcial, migración legacy, lados/instancias; CSP; sin CAD.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
