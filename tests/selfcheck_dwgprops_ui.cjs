// Offline browser regression: real UI modules, mocked finite API, no CAD calls.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    let saved=null,lastJob='';const errors=[];
    page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
    await page.route('**/*',async route=>{
      const request=route.request(),url=new URL(request.url()),p=url.pathname;
      if(p.startsWith('/api/')){
        let data={};
        if(p==='/api/preferences')data={theme:'dark',palette:'sincal',zoom:'100'};
        else if(p==='/api/palettes')data=[];
        else if(p==='/api/dwgprops/engines')data=[{id:'test-core',name:'AutoCAD de prueba'}];
        else if(p==='/api/shell-selection')data={selection:null};
        else if(p==='/api/files/choose')data=[{id:'folder',path:'C:\\Test DWGs'}];
        else if(p==='/api/files/list')data=[{name:'A.dwg'},{name:'B.dwg'}];
        else if(p==='/api/jobs'&&request.method()==='POST'){
          const body=request.postDataJSON();lastJob=body.operation;if(lastJob==='dwgprops-write')saved=body.payload;data={id:'test'};
        }else if(p==='/api/jobs/test')data={state:'completed',result:lastJob==='dwgprops-read'?{snapshot:'snap',files:[{id:'a',name:'A.dwg',properties:{REV:'A',OT:'130'}},{id:'b',name:'B.dwg',properties:{REV:'B',OT:'130'}}]}:{files:[{id:'a',name:'A.dwg',status:'Guardado',properties:{REV:'C',OT:'130'},backup:'backup/A.dwg'},{id:'b',name:'B.dwg',status:'Guardado',properties:{REV:'C',OT:'130'},backup:'backup/B.dwg'}]}};
        else if(p==='/api/jobs')data=[];
        if(p==='/api/jobs/test'){data.progress=100;data.message='Finalizado';}
        await route.fulfill({json:data});return;
      }
      const name=p==='/'?'index.html':p.slice(1),file=path.resolve(__dirname,'../sincal/web/static',name);
      if(fs.existsSync(file)&&fs.statSync(file).isFile())await route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
      else await route.fulfill({status:404,body:''});
    });
    await page.goto('http://sincal.test/#token=test');
  await page.locator('[data-page="project"]').click();
  await page.getByRole('button',{name:'Añadir Carpetas',exact:true}).click();
  await page.locator('#archivos-proyecto table').waitFor();
    await page.locator('[data-page="dwgprops"]').click();
    await page.getByLabel('Motor DWGPROPS').selectOption('test-core');
    await page.getByRole('button',{name:'Elegir carpeta y leer DWG'}).click();
  for(const check of await page.locator('dialog .asset-choice input').all())await check.check();
  await page.getByRole('button',{name:'Usar selección',exact:true}).click();
    try{await page.getByLabel('Seleccionar A.dwg').waitFor({timeout:5000});}catch(error){console.log('Aviso',await page.locator('#notice').innerText(),errors);throw error;}
    await page.getByRole('button',{name:'Seleccionar visibles'}).click();
    assert.equal(await page.getByLabel('Valor de REV',{exact:true}).getAttribute('placeholder'),'Valores distintos o propiedad ausente');
    await page.getByLabel('Valor de REV',{exact:true}).fill('C');
    await page.getByRole('button',{name:'Guardar en seleccionados'}).click();
    await page.getByText('A.dwg: Guardado',{exact:false}).waitFor();
    assert.deepEqual(saved.ids,['a','b']);assert.deepEqual(saved.changes,{REV:'C'});assert.equal(saved.confirm,true);
    assert.deepEqual(errors,[]);console.log('OK: navegación, carga, selección múltiple, valores mixtos y cambio exclusivo de REV.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
