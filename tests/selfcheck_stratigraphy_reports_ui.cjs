// Real module + actual parsed fixtures. No CAD connection or user drawing changes.
const {chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const python=`import json,runpy,os
from pathlib import Path
from sincal.stratigraphy import read_report
from sincal.stratigraphy_octay import parse_individual_report
from sincal.web.services import Services
pages=runpy.run_path('tests/test_stratigraphy_octay.py')['PAGES']
folder=os.getenv('SINCAL_TEST_OCTAY_FOLDER')
reports=[read_report(Path(folder)/f'Proyecto Puerto Octay Ruta U-55-V S{i}.pdf') if folder else parse_individual_report([p.replace('S-08',f'S-{i:02d}').replace('S-8 Fecha',f'S-{i} Fecha') for p in pages],f'S{i}.pdf',str(i)*64) for i in [7,8]]
print(json.dumps([dict(report=r.to_dict(),scaled=Services.describe_stratigraphy(r,annotation_scale=5),**Services.describe_stratigraphy(r)) for r in reports]))`;
const fixtures=JSON.parse(execFileSync('python',['-c',python],{encoding:'utf8',maxBuffer:32*1024*1024}));
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
  await page.evaluate(async fixtures=>{
   const {renderStratigraphy}=await import('/stratigraphy.js');
   const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
   const button=(text,action)=>{const e=node('button',text);e.onclick=async()=>{await action();};return e;};
   const section=(id,title)=>{const e=node('section');e.id=id;e.append(node('h2',title));document.querySelector('main').append(e);return e;};
   window.testProject={};window.fixtureReports=fixtures;
   await renderStratigraphy({node,button,section,project:window.testProject,current:()=>true,changed:()=>{},notify:()=>{},
    api:async (route,payload)=>{
     if(route==='files/choose'){if(!payload.multiple)throw Error('Multiple selection required');return [{id:'7'},{id:'8'}];}
     if(route==='stratigraphy/preview'){window.lastPreviewScale=payload.annotation_scale;const {report,scaled,...checks}=fixtures.find(f=>f.report.sha256===payload.report.sha256);return payload.annotation_scale===5?scaled:checks;}
     if(route==='cad/status')return {status:'ready',instance:'qa',active:{name:'qa.dwg',insunits:6,annotation_scale:{name:'1:200 (m)',value:5}}};
     throw Error('Unexpected API '+route);
    },job:async(op,payload)=>{if(op!=='stratigraphy'||payload.files.join(',')!=='7,8')throw Error('Bad import');return {reports:structuredClone(fixtures.map(f=>f.report))};}});
  },fixtures);
  await page.getByRole('button',{name:'Añadir informes de Proyecto'}).click();
  await page.getByLabel('Informe de estratigrafía').waitFor();
  assert.equal(await page.locator('.stratigraphy-preview').count(),1);
  assert(await page.getByText('Formato identificado: Puerto Octay · ensayos por intervalo',{exact:true}).isVisible());
  assert(await page.getByRole('button',{name:'Insertar este sondaje en AutoCAD / ZWCAD'}).isDisabled());
  const patterns=await page.locator('.stratigraphy-preview path').evaluateAll(paths=>paths.map(p=>p.getAttribute('d')));
  assert(patterns.length>0&&patterns.every(d=>d.length>0),'Every hatch must produce visible pattern geometry');
  await page.getByLabel('He cotejado',{exact:false}).check();
  assert.equal(await page.evaluate(()=>window.testProject.stratigraphy.report.boreholes[0].reviewed_format),'octay-intervals-v1');
  await page.getByRole('button',{name:'Tomar escala anotativa de CAD'}).click();
  await page.getByText('Escala de vista previa: 1:200 (m). Profundidades reales en metros; textos de 2,5 mm en papel.',{exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>window.lastPreviewScale),5);
  assert.equal(await page.evaluate(()=>window.testProject.stratigraphy.checks[0].scene.depth_scale),5);
  const confirmPromise=page.waitForEvent('dialog');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.getByRole('button',{name:'Insertar este sondaje en AutoCAD / ZWCAD'}).click();
  const confirmation=await confirmPromise;
  assert(confirmation.message().includes('1:200 (m)')&&confirmation.message().includes('1 m = 1 unidad'));
  if(process.env.SINCAL_UI_SCREENSHOT_S7)await page.locator('.stratigraphy-preview').screenshot({path:process.env.SINCAL_UI_SCREENSHOT_S7});
  await page.getByLabel('Informe de estratigrafía').selectOption('1');
  await page.waitForFunction(()=>window.testProject.stratigraphy.report.boreholes[0].name==='S-08');
  assert.equal(await page.getByLabel('He cotejado',{exact:false}).isChecked(),false);
  await page.getByText('Pasadas y recuperación — no son los límites de los estratos',{exact:true}).click();
  assert(await page.getByText('Recuperado cm',{exact:true}).isVisible());
  if(process.env.SINCAL_UI_SCREENSHOT)await page.locator('.stratigraphy-preview').screenshot({path:process.env.SINCAL_UI_SCREENSHOT});
  await page.getByLabel('Informe de estratigrafía').selectOption('1');
  await page.waitForFunction(()=>window.testProject.stratigraphy.report.boreholes[0].name==='S-07');
  assert.equal(await page.getByLabel('He cotejado',{exact:false}).isChecked(),true);
  await page.getByRole('button',{name:'Añadir informes de Proyecto'}).click();
  assert.equal(await page.getByLabel('Informe de estratigrafía').locator('option').count(),2);
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Guardar reconocimiento'}).click();
  const download=await downloadPromise,stream=await download.createReadStream(),chunks=[];
  for await(const chunk of stream)chunks.push(chunk);
  const saved=JSON.parse(Buffer.concat(chunks).toString());
  assert.equal(saved.schema,'sincal-stratigraphy-2');assert.equal(saved.reports.length,2);
  assert.equal(saved.reports[0].boreholes[0].reviewed,true);
  assert.equal(saved.reports[0].boreholes[0].reviewed_format,'octay-intervals-v1');
  assert.deepEqual(errors,[]);
  console.log('OK: independent reports, preview, cm units, review state, deduplication and multi-report export.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
