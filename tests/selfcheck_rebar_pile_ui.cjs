// Browser-only configuration checks: project APIs are mocked; CAD is never used.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

const harness=`<!doctype html><html lang="es" data-theme="dark"><head>
<meta charset="utf-8"><link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/palettes.css">
</head><body><main style="max-width:900px;margin:24px auto;padding:16px"><div class="rebar-assistant-inspector" id="host"></div></main>
<script type="module">
import {renderPilePreview} from '/rebar_pile.js';
const state=instance=>({geometry:{diameter_cm:instance==='entrada'?150:200,length_cm:instance==='entrada'?1000:1500,footing_height_cm:150},
  cover:{lateral_cm:null,inferior_cm:null},longitudinal:{diameter_mm:null,spacing_cm:null,hook_cm:40},
  ties:{diameter_mm:null,hook_90_cm:15,hook_45_cm:25,overrun_cm:null},confinement_cm:null,
  zones:['lower','middle','upper'].map(key=>({key,from_cm:null,to_cm:null,spacing_cm:null}))});
const project={data:{test:true},rebar:{}};
const fixture=window.fixture={project,calls:[],changes:0,errors:[],active:true,delayNext:0,current:true};
const node=(tag,text,cls)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
const api=async(route,payload)=>{
  fixture.calls.push({route,payload:structuredClone(payload)});
  if(route==='rebar/pile/from-project')return {present:fixture.active,state:state(payload.instance_key)};
  if(route==='rebar/from-project')return {entrada:{geometry:{},cover:{},rules:[]},salida:{geometry:{},cover:{},rules:[]}};
  if(route!=='rebar/pile/preview')throw Error('Unexpected API call: '+route);
  const delay=fixture.delayNext;fixture.delayNext=0;
  const value=structuredClone(payload.state);
  if(delay)await new Promise(resolve=>setTimeout(resolve,delay));
  const cover=value.cover.inferior_cm,diameter=value.longitudinal.diameter_mm;
  const firstTie=typeof cover==='number'&&cover>=0&&typeof diameter==='number'&&diameter>0?cover+diameter/20+3*diameter/10:null;
  value.zones[0].from_cm=firstTie;
  return {valid:true,geometry:value.geometry,confinement_cm:value.confinement_cm,first_tie_height_cm:firstTie,
    issues:[{message:'Penetración evaluada: '+value.confinement_cm}],
    zones:value.zones.filter(zone=>[zone.from_cm,zone.to_cm,zone.spacing_cm].every(v=>typeof v==='number')&&zone.to_cm>zone.from_cm)};
};
fixture.render=async instance=>{const host=document.getElementById('host');host.replaceChildren();await renderPilePreview({project,api,node,changed:()=>fixture.changes++,current:()=>fixture.current,notify:message=>fixture.errors.push(message)},host,instance);};
await fixture.render('entrada');window.ready=true;
</script></body></html>`;

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1200,height:950}}),errors=[];
    page.setDefaultTimeout(10000);
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',async route=>{
      const name=new URL(route.request().url()).pathname.slice(1);
      if(!name){await route.fulfill({body:harness,contentType:'text/html'});return;}
      if(name==='palettes.css'){await route.fulfill({body:'',contentType:'text/css'});return;}
      const file=path.resolve(__dirname,'../sincal/web/static',name);
      if(['app.css','rebar_pile.js'].includes(name)){
        await route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':'text/css'});
      }else await route.fulfill({status:404,body:''});
    });
    await page.goto('http://sincal-pile.test/');
    await page.waitForFunction(()=>window.ready);
    await page.getByText('Penetración evaluada: null',{exact:true}).waitFor();
    const field=label=>page.getByLabel(label,{exact:true});
    for(const label of ['Penetración en la zapata','Recubrimiento lateral del pilote','Recubrimiento inferior del pilote','Diámetro longitudinal · mm','Diámetro del estribo circular · mm','Inferior: separación','Medio: separación','Superior / confinamiento: separación'])assert.equal(await field(label).inputValue(),'');
    assert.equal(await field('Diámetro del pilote').inputValue(),'150');
    assert.equal(await field('Largo bajo la zapata').inputValue(),'1000');
    assert.equal(await field('Gancho inferior · tramo recto · cm').inputValue(),'40');
    assert.equal(await field('Gancho de 90° · tramo recto · cm').inputValue(),'15');
    assert.equal(await field('Gancho de 45° · tramo recto · cm').inputValue(),'25');
    const fill=async(label,value)=>field(label).fill(String(value));
    for(const [label,value] of [
      ['Penetración en la zapata',100],['Recubrimiento lateral del pilote',5],['Recubrimiento inferior del pilote',7.5],
      ['Diámetro longitudinal · mm',22],['Separación entre ejes sobre la circunferencia · cm',15],['Gancho inferior · tramo recto · cm',40],
      ['Diámetro del estribo circular · mm',12],['Gancho de 90° · tramo recto · cm',12],['Gancho de 45° · tramo recto · cm',15],['Longitud adicional a la vuelta · cm',20],
      ['Inferior: hasta',200],['Inferior: separación',10],
      ['Medio: desde',200],['Medio: hasta',800],['Medio: separación',20],
      ['Superior / confinamiento: desde',800],['Superior / confinamiento: hasta',1100],['Superior / confinamiento: separación',10],
    ])await fill(label,value);
    await page.getByText('Penetración evaluada: 100',{exact:true}).waitFor();
    await page.getByText('Inferior: 15,2–200 cm · separación 10 cm.',{exact:true}).waitFor();
    assert(await field('Inferior: desde').evaluate(element=>element.readOnly));
    assert.equal(await field('Inferior: desde').inputValue(),'15.2');
    await page.getByText('Primer estribo circular: 15,2 cm desde el fondo, al inicio del doblez del longitudinal.',{exact:true}).waitFor();
    assert.equal(await page.locator('[data-first-tie-height-cm]').count(),1);
    await page.getByText('Superior / confinamiento: 800–1.100 cm · separación 10 cm.',{exact:true}).waitFor();
    assert.equal(await page.getByRole('img',{name:'Elevación del pilote con penetración en la zapata y rangos de separación'}).count(),1);
    const screenshot=process.env.SINCAL_PILE_UI_SCREENSHOT||path.resolve(__dirname,'../tmp/pile-preview-ui.png');
    fs.mkdirSync(path.dirname(screenshot),{recursive:true});
    await page.screenshot({path:screenshot,fullPage:true});
    await page.setViewportSize({width:440,height:950});
    await page.screenshot({path:screenshot.replace(/\.png$/,'-narrow.png'),fullPage:true});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    await page.setViewportSize({width:1200,height:950});

    await page.evaluate(()=>fixture.render('salida'));
    await page.getByText('Penetración evaluada: null',{exact:true}).waitFor();
    assert.equal(await field('Largo bajo la zapata').inputValue(),'1500');
    assert.equal(await field('Recubrimiento lateral del pilote').inputValue(),'');
    await fill('Penetración en la zapata',80);await fill('Recubrimiento lateral del pilote',7.5);
    await page.getByText('Penetración evaluada: 80',{exact:true}).waitFor();
    await page.evaluate(()=>fixture.render('entrada'));
    await page.getByText('Penetración evaluada: 100',{exact:true}).waitFor();
    assert.equal(await field('Recubrimiento lateral del pilote').inputValue(),'5');
    assert.equal(await field('Gancho de 45° · tramo recto · cm').inputValue(),'15');
    await field('Gancho de 45° · tramo recto · cm').fill('');
    await page.evaluate(()=>fixture.render('entrada'));
    assert.equal(await field('Gancho de 45° · tramo recto · cm').inputValue(),'');
    assert.equal(await field('Gancho de 45° · tramo recto · cm').getAttribute('placeholder'),'Ej.: 25');
    assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.pile.ties.hook_45_cm),null);

    // A slow response for a previous edit must not replace the newest preview.
    await page.evaluate(()=>{fixture.delayNext=650;});
    await fill('Penetración en la zapata',90);
    await page.waitForFunction(()=>fixture.calls.at(-1)?.route==='rebar/pile/preview'&&fixture.calls.at(-1).payload.state.confinement_cm===90);
    await fill('Penetración en la zapata',110);
    await page.getByText('Penetración evaluada: 110',{exact:true}).waitFor();
    await page.waitForTimeout(700);
    assert.equal(await page.getByText('Penetración evaluada: 90',{exact:true}).count(),0);
    assert.equal(await page.getByText('Penetración evaluada: 110',{exact:true}).count(),1);
    await field('Recubrimiento inferior del pilote').fill('');
    await page.waitForFunction(()=>fixture.calls.at(-1)?.payload?.state?.cover?.inferior_cm===null);
    await page.waitForFunction(()=>fixture.project.rebar.entrada.pile.zones[0].from_cm===null);
    assert.equal(await field('Inferior: desde').inputValue(),'');
    assert.equal(await page.locator('[data-first-tie-height-cm]').count(),0);
    assert.equal(await page.evaluate(()=>fixture.project.rebar.entrada.pile.cover.inferior_cm),null);
    assert.equal(await page.evaluate(()=>fixture.project.rebar.salida.pile.cover.lateral_cm),7.5);

    const before=await page.evaluate(()=>structuredClone(fixture.project.rebar.entrada.pile));
    await page.evaluate(()=>{fixture.active=false;return fixture.render('entrada');});
    await page.getByText('El JSON no activa pilotes para este estribo.',{exact:true}).waitFor();
    assert.equal(await page.locator('input').count(),0);
    assert.equal(await page.getByRole('img').count(),0);
    assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.pile),before);
    assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);
    assert.deepEqual(errors,[]);
    assert((await page.evaluate(()=>fixture.calls)).every(call=>['rebar/pile/from-project','rebar/from-project','rebar/pile/preview'].includes(call.route)));
    console.log('OK: preview, null inputs, separate instances, persistence, stale responses and absent piles; no CAD calls.');
    console.log('Screenshot: '+screenshot);
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
