// Browser integration only. Native file dialogs/CAD are mocked; no user drawings touched.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],picks=[];let operation='',payload=null;
  let acceptDialog=true;
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>acceptDialog?d.accept():d.dismiss());
  await page.route('**/*',async route=>{
   const p=new URL(route.request().url()).pathname;
   if(p.startsWith('/api/')){
    let data={};
    if(p==='/api/preferences')data={theme:'dark',palette:'sincal',zoom:'100'};
    else if(['/api/palettes','/api/jobs','/api/maps','/api/dwgprops/engines'].includes(p)&&route.request().method()==='GET')data=[];
    else if(p==='/api/shell-selection')data={selection:null};
    else if(p==='/api/files/choose'){const kind=route.request().postDataJSON().kind;picks.push(kind);data=kind==='report'?[{id:'ims',name:'IMS.pdf',path:'C:/Proyecto/IMS.pdf'},{id:'vs',name:'Vs.pdf',path:'C:/Proyecto/Vs.pdf'}]:[{id:kind,name:kind==='folder'?'Planos':'Mapa.kmz',path:'C:/Proyecto/'+kind}];}
    else if(p==='/api/files/list')data=[{name:'Plano.dwg',bytes:1024}];
    else if(p==='/api/jobs'&&route.request().method()==='POST'){({operation,payload}=route.request().postDataJSON());data={id:'test'};}
    else if(p==='/api/jobs/test')data={state:'completed',message:'OK',progress:100,result:{report:{profiles:[],notices:[]},checks:[]}};
    else if(p==='/api/prospect/preview')data={checks:[]};
    else if(p==='/api/cad/status')data={message:'Sin CAD abierto',status:'disconnected'};
    else if(p==='/api/project/preview')data={warnings:[],sections:[],text:'Proyecto de prueba'};
    else if(p==='/api/rebar/from-project'){const state={geometry:{largo_cm:900,ancho_cm:2000,alto_cm:200,esviaje_grados:0},cover:{inferior_cm:7.5,superior_cm:5,lateral_cm:5},rules:[]};data={entrada:state,salida:structuredClone(state)};}
    await route.fulfill({json:data});return;
   }
   const name=p==='/'?'index.html':p.slice(1),file=path.resolve(__dirname,'../sincal/web/static',name);
   if(fs.existsSync(file)&&fs.statSync(file).isFile())await route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
   else await route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal.test/#token=test');
  const expected=['Home','Documentación','Proyecto','Archivo','Propiedades','Revisiones','Prospecciones','Mapa de ubicación','Comandos en vivo','Generador de armadura','Estribos','Viga','Cepa','Travesaño','Losa','Consulta de proyecto','Diagnóstico'];
  assert.deepEqual(await page.locator('#sidebar nav button span').allTextContents(),expected);
  assert.equal(await page.locator('#sidebar nav button svg').count(),17);
  assert.deepEqual(await page.locator('#sidebar .subnav span').allTextContents(),[...expected.slice(3,8),...expected.slice(10,15)]);
  await page.locator('[data-page="archivo"]').click();
  await page.getByRole('button',{name:'Elegir carpeta',exact:true}).click();
  assert.equal(picks.length,0);assert.equal(await page.locator('input[type=file]').count(),0);
  await page.getByText('No hay archivos disponibles de este tipo: Carpetas. Añádelos primero en Proyecto.',{exact:true}).waitFor();
  await page.locator('[data-page="rebar"]').click();await page.getByRole('heading',{name:'Generador de armadura',exact:true}).waitFor();
  await page.locator('[data-page="consulta"]').click();await page.getByRole('heading',{name:'Consulta del proyecto',exact:true}).waitFor();
  assert.equal(await page.locator('input[type=file]').count(),0);
  await page.locator('[data-page="project"]').click();
  await page.getByRole('button',{name:'Añadir Informes PDF / TXT',exact:true}).click();
  await page.getByRole('button',{name:'Añadir Carpetas',exact:true}).click();
  await page.locator('#archivos-proyecto').getByText('Planos',{exact:true}).waitFor();
  assert.equal(await page.locator('#archivos-proyecto tr').count(),4);
  await page.locator('[data-page="archivo"]').click();assert.equal(await page.locator('.module-tabs button').count(),2);
  await page.getByRole('button',{name:'Elegir carpeta',exact:true}).click();
  await page.locator('dialog .asset-choice input').check();await page.getByRole('button',{name:'Usar selección',exact:true}).click();
  await page.getByText('Plano.dwg',{exact:true}).waitFor();assert.equal(picks.filter(k=>k==='folder').length,1);
  await page.locator('[data-page="convert"]').click();await page.getByRole('heading',{name:'Conversión DXF–DWG',exact:true}).waitFor();
  await page.getByRole('button',{name:'Carpeta de salida',exact:true}).click();assert.equal(picks.filter(k=>k==='folder').length,2);assert.equal(await page.locator('dialog').count(),0);
  await page.locator('[data-page="revisiones"]').click();await page.getByRole('heading',{name:'Editor de revisiones',exact:true}).waitFor();
  await page.locator('[data-page="revisions"]').click();await page.getByRole('heading',{name:'Nueva revisión de planos',exact:true}).waitFor();
  await page.locator('[data-page="prospecciones"]').click();await page.locator('[data-page="prospect"]').click();
  await page.getByRole('button',{name:'Usar informe de Proyecto',exact:true}).click();
  await page.locator('dialog .asset-choice').filter({hasText:'Vs.pdf'}).locator('input').check();
  assert.equal(await page.getByRole('button',{name:'Añadir desde el equipo'}).count(),0);
  await page.getByRole('button',{name:'Usar selección',exact:true}).click();await page.locator('#activity').waitFor({state:'hidden'});
  assert.equal(operation,'prospect');assert.equal(payload.file,'vs');assert.equal(picks.filter(k=>k==='report').length,1);
  await page.locator('[data-page="location"]').click();await page.getByRole('heading',{name:'Ubicación geográfica',exact:true}).waitFor();
  await page.locator('[data-page="diagnostics"]').click();await page.getByRole('button',{name:'Comprobar conexión',exact:true}).click();await page.getByText('Sin CAD abierto',{exact:true}).waitFor();
  assert.equal(await page.locator('#sidebar [data-page="cad"]').count(),0);
  assert.equal(await page.getByRole('button',{name:'Preparar integración CAD',exact:true}).count(),1);
  await page.locator('[data-page="project"]').click();assert.equal(await page.locator('#archivos-proyecto tr').count(),4);
  await page.locator('#archivos-proyecto tr').filter({hasText:'IMS.pdf'}).getByRole('button',{name:'Quitar'}).click();assert.equal(await page.locator('#archivos-proyecto tr').count(),3);
  if(process.env.SINCAL_UI_SCREENSHOT)await page.screenshot({path:process.env.SINCAL_UI_SCREENSHOT,fullPage:true});
  acceptDialog=false;await page.getByRole('button',{name:'Descartar proyecto actual',exact:true}).click();
  assert.equal(await page.locator('#archivos-proyecto tr').count(),3);
  acceptDialog=true;await page.getByRole('button',{name:'Descartar proyecto actual',exact:true}).click();
  await page.getByText('Todavía no hay archivos incorporados.',{exact:true}).waitFor();
  await page.locator('[data-page="rebar-abutments"]').click();
  await page.getByText('Incorpora el JSON del puente en Proyecto para configurar sus armaduras.',{exact:true}).waitFor();
  await page.locator('[data-page="rebar"]').click();
  await page.getByRole('button',{name:'Añadir Memoria PDF',exact:true}).click();
  await page.locator('#memorias table').waitFor();
  await page.getByRole('button',{name:'Añadir Memoria Excel',exact:true}).click();
  await page.locator('#memorias tr').nth(2).waitFor();
  await page.getByLabel('Cargar JSON del proyecto',{exact:true}).setInputFiles({name:'puente.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({bridge:'test'}))});
  await page.getByText('JSON activo: puente.json',{exact:true}).waitFor();
  await page.locator('[data-page="rebar-abutments"]').click();
  await page.getByLabel('Largo',{exact:true}).fill('1100');
  await page.getByRole('button',{name:'Estribo de salida',exact:true}).click();assert.equal(await page.getByLabel('Largo',{exact:true}).inputValue(),'900');
  await page.getByRole('button',{name:'Estribo de entrada',exact:true}).click();assert.equal(await page.getByLabel('Largo',{exact:true}).inputValue(),'1100');
  await page.locator('[data-page="rebar-crossbeam"]').click();await page.getByRole('button',{name:'Intermedio',exact:true}).click();
  await page.getByText('Intermedio: configuración específica pendiente',{exact:false}).waitFor();
  await page.locator('[data-page="rebar-abutments"]').click();assert.equal(await page.getByLabel('Largo',{exact:true}).inputValue(),'1100');
  for(const structure of ['rebar-beam','rebar-pier','rebar-slab']){await page.locator(`[data-page="${structure}"]`).click();await page.getByText('Generador pendiente de desarrollo.',{exact:false}).waitFor();assert.equal(await page.locator('input[type=file]').count(),0);}
  await page.locator('[data-page="rebar"]').click();assert.equal(await page.locator('#memorias tr').count(),3);
  await page.locator('[data-page="project"]').click();
  await page.setViewportSize({width:700,height:900});await page.locator('#panels').click();assert(await page.locator('#sidebar').isVisible());
  assert.deepEqual(errors,[]);console.log('OK: exact menu/icons, nested tools, shared reports/folders, explicit output folder, CAD diagnosis and local-only removal.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
