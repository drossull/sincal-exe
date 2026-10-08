// Real UI, mocked local API: no user drawings or CAD processes.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const errors=[];let saved=null,operation='';
  const revision={layout:'01',block:'VIÑETA',fields:['field','field','field',null,null,'field'],rows:[['H','02/10/26','GM','AR','GS','EMITIDO'],['G','01/09/26','GM','AR','GS','ANTERIOR']]};
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.route('**/*',async route=>{
   const p=new URL(route.request().url()).pathname;
   if(p.startsWith('/api/')){
    let data={};
    if(p==='/api/preferences')data={theme:'dark',palette:'sincal',zoom:'100'};
    else if(p==='/api/palettes'||p==='/api/jobs'&&route.request().method()==='GET')data=[];
    else if(p==='/api/shell-selection')data={selection:null};
    else if(p==='/api/dwgprops/engines')data=[{id:'core',name:'AutoCAD de prueba'}];
    else if(p==='/api/files/choose'){assert.equal(route.request().postDataJSON().kind,'dwg');data=[{id:'file1',name:'A.dwg'},{id:'file2',name:'B.dwg'}];}
    else if(p==='/api/jobs'){
     const body=route.request().postDataJSON();operation=body.operation;if(operation==='revision-write')saved=body.payload;data={id:'job'};
    }else if(p==='/api/jobs/job')data={state:'completed',progress:100,message:'Listo',result:operation==='revision-read'?{snapshot:'snapshot',files:[{id:'a',name:'A.dwg',revision},{id:'b',name:'B.dwg',revision}]}:{files:['a','b'].map((id,i)=>({id,name:i?'B.dwg':'A.dwg',status:'Revisión creada',backup:'backup.dwg',revision:{...revision,rows:[saved.values,revision.rows[0]]}}))}};
    await route.fulfill({json:data});return;
   }
   const name=p==='/'?'index.html':p.slice(1),file=path.resolve(__dirname,'../sincal/web/static',name);
   if(fs.existsSync(file)&&fs.statSync(file).isFile())await route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
   else await route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal.test/#token=test');
  await page.locator('[data-page="project"]').click();
  await page.getByRole('button',{name:'Añadir Planos DWG',exact:true}).click();
  await page.locator('#archivos-proyecto table').waitFor();
  await page.locator('[data-page="revisiones"]').click();
  await page.locator('[data-page="revisions"]').click();
  await page.getByRole('button',{name:'Seleccionar DWG y leer revisiones'}).click();
  for(const check of await page.locator('dialog .asset-choice input').all())await check.check();
  await page.getByRole('button',{name:'Usar selección',exact:true}).click();
  await page.getByLabel('Nueva Revisión',{exact:true}).fill('I');
  await page.getByLabel('Nueva Fecha',{exact:true}).fill('05/10/26');
  assert.equal(await page.locator('#revision-preview details').count(),2);
  await page.getByRole('button',{name:'Crear revisión en seleccionados'}).click();
  await page.getByText('A.dwg: Revisión creada',{exact:false}).waitFor();
  assert.deepEqual(saved.ids,['a','b']);assert.deepEqual(saved.values,['I','05/10/26','GM','AR','GS','EMITIDO']);assert(saved.confirm);
  assert.deepEqual(errors,[]);
  console.log('OK: DWG selection, preview, manual revision, batch confirmation and backup results.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
