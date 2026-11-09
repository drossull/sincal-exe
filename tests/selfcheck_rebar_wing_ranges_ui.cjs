// Fixed interior supplementary groups and one editable lower front boundary.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/fixture.css"></head><body><main class="rebar-wing"><h2>Suples de malla interior y fierro de canto</h2><div id="host"></div></main><script nonce="fixture" type="module">
import {mountWingSupplementControls} from '/rebar_wing_ranges.js';
const group=()=>({enabled:false,diameter_mm:null,spacing_cm:null,hook_cm:null,straight_cm:null,mark:'',removed_pieces:[]});
const state=()=>({supplements:{front:{...group(),range_height_cm:null},back:group()},edge_rebar:{quantity:null,diameter_mm:null,top_hook_enabled:true,top_hook_cm:20,total_cm:null,min_extension_cm:100,mark:'',removed_pieces:[]}});
const fixture=window.fixture={states:{left:state(),right:state()},changes:0,profile:{profile_cm:[[-100,0],[0,0],[350,0],[600,160],[600,300],[350,400],[0,500],[-50,500],[-50,300],[-100,300]],main_length_cm:350,extension_length_cm:250,front_height_cm:300,back_thickness_cm:50,reference:'footing_top',extension_enabled:true}};
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
fixture.mount=(side='left')=>{fixture.controller?.dispose();document.querySelector('#host').replaceChildren();fixture.controller=mountWingSupplementControls({node},document.querySelector('#host'),fixture.states[side],fixture.profile,()=>fixture.changes++);};
fixture.mount();window.ready=true;
</script></body></html>`;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1200}}),errors=[],csp=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.text().includes('Content Security Policy'))csp.push(m.text());});
  await page.route('**/*',route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:harness,contentType:'text/html',headers:{'Content-Security-Policy':"default-src 'self'; script-src 'self' 'nonce-fixture'; style-src 'self'; font-src 'self'"}});
   if(name==='fixture.css')return route.fulfill({body:'main{max-width:1000px;padding:20px;margin:auto}html{scroll-behavior:auto}',contentType:'text/css'});
   const file=path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name);return fs.existsSync(file)?route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'}):route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-wing-supplements.test/');await page.waitForFunction(()=>window.ready);
  const field=label=>page.getByLabel(label,{exact:true}),svg=page.getByRole('group',{name:'Perfil de suples del ala, frontal y espaldar',exact:true});
  const state=()=>page.evaluate(()=>structuredClone(fixture.states.left));
  const height='Altura del grupo frontal hacia abajo desde su coronación · cm',original=await page.evaluate(()=>structuredClone(fixture.profile));
  assert.equal(await field(height).inputValue(),'');assert(await field(height).isDisabled());
  assert.equal(await page.getByLabel(/Inicio de|Fin de/).count(),0);assert.equal(await page.getByRole('slider').count(),0);
  assert.equal(await page.locator('.wing-supplement-band').count(),0);assert.equal(await page.locator('[data-piece]').count(),0);
  assert(await page.locator('.wing-supplement-profile').evaluate(el=>el.points[0].x>el.points[3].x));
  await field('Incluir grupo hacia el frontal').check();await field('Incluir grupo hacia el espaldar').check();
  assert.equal(await page.locator('.wing-supplement-band').count(),1,'Upper band uses fixed front crown and roof');
  await page.getByRole('button',{name:'Elegir límite inferior en el perfil',exact:true}).click();await svg.scrollIntoViewIfNeeded();
  const pointAt=async(z,x=500)=>svg.evaluate((element,{z,x})=>{const profile=element.querySelector('.wing-supplement-profile'),a=profile.points[0],b=profile.points[6],y=a.y-z/500*(a.y-b.y);return new DOMPoint(x,y).matrixTransform(element.getScreenCTM()).toJSON();},{z,x});
  const chosen=await pointAt(100);await page.mouse.click(chosen.x,chosen.y);assert(Math.abs((await state()).supplements.front.range_height_cm-200)<=1);
  await field(height).fill('200');await svg.scrollIntoViewIfNeeded();
  assert.equal(await page.getByRole('slider').count(),1);assert.equal(await page.locator('.wing-supplement-band').count(),2);
  const handle=page.getByRole('slider',{name:'Límite inferior del grupo frontal',exact:true});await handle.focus();await page.keyboard.press('ArrowUp');await page.keyboard.press('Shift+ArrowDown');assert.equal((await state()).supplements.front.range_height_cm,209);
  const from=await pointAt(91,880),to=await pointAt(130,880);await page.mouse.move(from.x,from.y);await page.mouse.down();await page.mouse.move(to.x,to.y,{steps:4});await page.mouse.up();assert(Math.abs((await state()).supplements.front.range_height_cm-170)<=1);
  for(const [label,value] of [['Marca del grupo hacia el frontal','31'],['Diámetro del grupo hacia el frontal · mm','16'],['Separación del grupo hacia el frontal · cm','20'],['Gancho hacia el frontal · cm','40'],['Tramo desde el gancho al extremo libre · frontal · cm','250'],['Marca del grupo hacia el espaldar','32'],['Gancho hacia el espaldar · cm','45'],['Tramo desde el gancho al extremo libre · espaldar · cm','240'],['Cantidad de fierros de canto','3'],['Diámetro del fierro de canto · mm','16'],['Largo total del fierro de canto · cm','600'],['Marca del fierro de canto','33']])await field(label).fill(value);
  assert.equal(await field('Gancho superior del fierro de canto · cm').inputValue(),'20');assert.equal(await field('Prolongación mínima del fierro de canto · cm').inputValue(),'100');
  assert.equal(await page.getByRole('checkbox').count(),3,'Only the two groups and the optional top hook can be disabled');
  await field('Incluir gancho superior del fierro de canto').uncheck();assert(await field('Gancho superior del fierro de canto · cm').isDisabled());assert.equal((await state()).edge_rebar.top_hook_cm,20);await field('Incluir gancho superior del fierro de canto').check();
  await page.evaluate(()=>fixture.controller.update(fixture.profile,{edge_extensions_cm:[{id:'wing:left:edge:0',extension_cm:123.456}]}));assert.equal(await field('Fierro de canto 1').getAttribute('readonly'),'');assert.equal(await field('Fierro de canto 1').inputValue(),'123,46');
  await page.evaluate(()=>fixture.controller.invalidate());assert.equal(await field('Fierro de canto 1').count(),0);
  const screenshot=path.join(root,'tmp','wing-supplement-controls-ui.png');fs.mkdirSync(path.dirname(screenshot),{recursive:true});await svg.screenshot({path:screenshot});
  await field(height).fill('350');assert.equal((await state()).supplements.front.range_height_cm,350);assert.equal(await field(height).getAttribute('aria-invalid'),'true');
  await field('Prolongación mínima del fierro de canto · cm').fill('90');assert.equal((await state()).edge_rebar.min_extension_cm,90);assert.equal(await field('Prolongación mínima del fierro de canto · cm').getAttribute('aria-invalid'),'true');
  const saved=await state();await page.evaluate(()=>fixture.mount('right'));assert.equal(await field(height).inputValue(),'');
  await page.evaluate(()=>{fixture.states.left=JSON.parse(JSON.stringify(fixture.states.left));fixture.mount('left');});assert.deepEqual(await state(),saved);
  await page.evaluate(()=>fixture.controller.update(null));assert.equal(await svg.isVisible(),false);assert.deepEqual(await state(),saved);
  await page.evaluate(()=>fixture.controller.update({...fixture.profile,extension_enabled:false}));assert.equal(await field('Cantidad de fierros de canto').isVisible(),false);assert.deepEqual(await state(),saved);
  assert.deepEqual(await page.evaluate(()=>fixture.profile),original);
  await page.setViewportSize({width:440,height:950});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert.deepEqual(errors,[]);assert.deepEqual(csp,[]);
  console.log('OK: grupos fijos interiores, un límite inferior móvil, unión/techo fijos, canto obligatorio y gancho opcional, largos exactos, mínimos sin clamp, prolongación real readonly, lados/reapertura; CSP. Captura: '+screenshot);
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
