const {chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const fixture=JSON.parse(execFileSync('python',['-c',`import json,os,runpy
from sincal.prospecciones import parse_pages,read_report
from sincal.web.services import Services
r=read_report(os.environ['SINCAL_TEST_CASCADA_VS'],ocr=False) if os.getenv('SINCAL_TEST_CASCADA_VS') else parse_pages(runpy.run_path('tests/test_prospecciones_geoiberica.py')['PAGES'])
print(json.dumps(dict(initial=Services.describe_report(r),scaled=Services.describe_report(r,5))))`],{encoding:'utf8',maxBuffer:16*1024*1024}));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({contentType:'text/html',body:'<link rel="stylesheet" href="/app.css"><main id="main"></main>'});
   const file=path.resolve(__dirname,'../sincal/web/static',name);
   if(!fs.existsSync(file))return route.fulfill({status:404,body:''});
   await route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':'text/css'});
  });
  await page.goto('http://sincal.test/');
  await page.evaluate(async fixture=>{
   const {renderTools}=await import('/tools.js');
   const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
   const button=(text,action)=>{const e=node('button',text);e.onclick=async()=>{await action();};return e;};
   const section=(id,title)=>{const e=node('section');e.id=id;e.append(node('h2',title));document.querySelector('main').append(e);return e;};
   window.project={prospecciones:fixture.initial};window.sent=[];
   await renderTools('prospect',{node,button,section,project:window.project,current:()=>true,changed:()=>{},notify:()=>{},
    api:async(route,payload)=>{
     if(route==='prospect/preview')return payload.annotation_scale===5?fixture.scaled:fixture.initial;
     if(route==='cad/status')return {status:'ready',instance:'qa',active:{name:'qa.dwg',insunits:6,annotation_scale:{name:'1:200 (m)',value:5}}};
     throw Error('Unexpected route '+route);
    },job:async(op,payload)=>{window.sent.push({op,payload});return {message:'QA'};}});
  },fixture);
  await page.locator('#arreglos > details').first().locator('summary').first().click();
  assert.equal(await page.locator('.study-information').count(),2);
  const box=page.locator('.study-information').first();
  assert((await box.innerText()).includes('GEOIBERICA SpA'));
  assert.equal(await box.locator('input,textarea,button').count(),0);
  assert(!(await page.locator('.profile-preview').first().textContent()).includes('GEOIBERICA'));
  await page.getByRole('button',{name:'Tomar escala anotativa de CAD'}).click();
  assert((await page.locator('#arreglos > .badge').first().innerText()).includes('1:200 (m)'));
  await page.locator('#arreglos > details').first().locator('summary').first().click();
  if(process.env.SINCAL_UI_SCREENSHOT)await page.screenshot({path:process.env.SINCAL_UI_SCREENSHOT,fullPage:true});
  page.once('dialog',async d=>{assert(d.message().includes('NO se enviará a CAD'));await d.accept();});
  await page.getByRole('button',{name:'Insertar perfil en CAD'}).first().click();
  await page.waitForFunction(()=>window.sent.length===1);
  assert.equal(await page.evaluate(()=>window.sent[0].payload.expected.active.annotation_scale.value),5);
  assert.deepEqual(errors,[]);
  console.log('OK: company consultation card, no editable fields, two profiles, scale preview and confirmed CAD request.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
