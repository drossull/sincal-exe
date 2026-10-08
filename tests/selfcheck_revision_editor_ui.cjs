// Component integration with a mocked local API. Never opens or modifies user DWGs.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const errors=[];let saved=null,operation='',kind='';
  const cells=[['H','02/10/26','GM','AR','GS','EMITIDO'],['G','01/09/26','GM','AR','GS','ANTERIOR']].map((row,r)=>row.map((text,c)=>({text,editable:true,field:r===0&&c===0?'field':null,property:r===0&&c===0?'Revision':null})));
  const editor={tables:[{id:'T',block:'VIÑETA G130',locations:['01 / VIÑETA G130'],cells}]};
  cells[1][4]={text:'GS',editable:false,field:'unsupported',property:null};
  let acceptDialog=true;
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>acceptDialog?d.accept():d.dismiss());
  await page.route('**/*',async route=>{
   const p=new URL(route.request().url()).pathname;
   if(p.startsWith('/api/')){
    let data={};
    if(p==='/api/preferences')data={theme:'dark',palette:'sincal',zoom:'100'};
    else if(p==='/api/palettes'||p==='/api/jobs'&&route.request().method()==='GET')data=[];
    else if(p==='/api/shell-selection')data={selection:null};
    else if(p==='/api/dwgprops/engines')data=[{id:'core',name:'AutoCAD de prueba'}];
    else if(p==='/api/files/choose'){kind=route.request().postDataJSON().kind;data=[{id:'folder',name:'Barrancón'}];}
    else if(p==='/api/jobs'){
     const body=route.request().postDataJSON();operation=body.operation;if(operation==='revision-editor-write')saved=body.payload;data={id:'job'};
    }else if(p==='/api/jobs/job'){
     const written=(saved?.files||[]).map(file=>{const updated=structuredClone(editor);for(const edit of file.changes)updated.tables[0].cells[edit.row][edit.column].text=edit.value;return {id:file.id,name:file.id.toUpperCase()+'.dwg',status:'Guardado',backup:'backup.dwg',editor:updated};});
     data={state:'completed',progress:100,message:'Listo',result:operation==='revision-editor-read'?{snapshot:'snapshot',files:[{id:'a',name:'A.dwg',path:'C:/A.dwg',editor},{id:'b',name:'B.dwg',path:'C:/B.dwg',editor}]}:{files:written}};
    }
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
  await page.locator('[data-page="revisiones"]').click();
  await page.getByRole('button',{name:'Seleccionar carpeta',exact:true}).click();
  for(const check of await page.locator('dialog .asset-choice input').all())await check.check();
  await page.getByRole('button',{name:'Usar selección',exact:true}).click();
  await page.getByLabel('Seleccionar A.dwg',{exact:true}).check();
  await page.getByLabel('Seleccionar B.dwg',{exact:true}).check();
  await page.getByLabel('Común: Dibujante',{exact:true}).fill('TEST');
  assert.equal(await page.getByLabel('VIÑETA G130 fila 1 Dibujante',{exact:true}).inputValue(),'TEST');
  await page.getByRole('button',{name:'Ver / editar B.dwg',exact:true}).click();
  assert.equal(await page.getByLabel('VIÑETA G130 fila 1 Dibujante',{exact:true}).inputValue(),'TEST');
  await page.getByLabel('VIÑETA G130 fila 1 Dibujante',{exact:true}).fill('OTRO');
  assert.equal(await page.getByLabel('Común: Dibujante',{exact:true}).inputValue(),'');
  assert.equal(await page.getByLabel('Común: Dibujante',{exact:true}).getAttribute('placeholder'),'Valores distintos');
  assert.equal(saved,null);
  if(process.env.SINCAL_UI_SCREENSHOT)await page.screenshot({path:process.env.SINCAL_UI_SCREENSHOT,fullPage:true});
  await page.getByLabel('Común: Dibujante',{exact:true}).fill('GM');
  await page.getByRole('button',{name:'Ver / editar A.dwg',exact:true}).click();
  await page.getByLabel('VIÑETA G130 fila 1 Revisión',{exact:true}).fill('I');
  await page.getByLabel('VIÑETA G130 fila 2 Descripción',{exact:true}).fill('CORREGIDO');
  assert(await page.getByLabel('VIÑETA G130 fila 2 Aprobador',{exact:true}).isDisabled());
  await page.locator('[data-page="revision-editor"]').click();
  assert.equal(await page.getByLabel('VIÑETA G130 fila 1 Revisión',{exact:true}).inputValue(),'I');
  acceptDialog=false;await page.locator('[data-page="revisions"]').click();
  assert.equal(await page.getByLabel('VIÑETA G130 fila 1 Revisión',{exact:true}).inputValue(),'I');acceptDialog=true;
  assert.equal(kind,'folder');
  await page.getByRole('button',{name:'Ver / editar B.dwg',exact:true}).click();
  assert.equal(await page.getByLabel('VIÑETA G130 fila 1 Revisión',{exact:true}).inputValue(),'H');
  await page.getByRole('button',{name:'Ver / editar A.dwg',exact:true}).click();
  assert.equal(await page.getByLabel('VIÑETA G130 fila 1 Revisión',{exact:true}).inputValue(),'I');
  await page.getByRole('button',{name:'Guardar cambios con respaldo',exact:true}).click();
  await page.getByText('A.dwg: Guardado',{exact:false}).waitFor();
  assert.deepEqual(saved.files,[{id:'a',changes:[{table:'T',row:0,column:0,value:'I'},{table:'T',row:1,column:5,value:'CORREGIDO'}]}]);assert(saved.confirm);
  assert.equal(await page.getByLabel('VIÑETA G130 fila 2 Revisión',{exact:true}).inputValue(),'G');
  assert(await page.getByRole('button',{name:'Guardar cambios con respaldo',exact:true}).isDisabled());
  await page.getByLabel('Común: Dibujante',{exact:true}).fill('COMUN');
  await page.getByRole('button',{name:'Ver / editar B.dwg',exact:true}).click();
  await page.getByLabel('VIÑETA G130 fila 1 Dibujante',{exact:true}).fill('EXCEPCION');
  await page.getByLabel('Seleccionar B.dwg',{exact:true}).uncheck();
  await page.getByRole('button',{name:'Guardar cambios con respaldo',exact:true}).click();
  await page.getByText('B.dwg: Guardado',{exact:false}).waitFor();
  assert.deepEqual(saved.files,[{id:'a',changes:[{table:'T',row:0,column:2,value:'COMUN'}]},{id:'b',changes:[{table:'T',row:0,column:2,value:'EXCEPCION'}]}]);
  assert(await page.getByRole('button',{name:'Guardar cambios con respaldo',exact:true}).isDisabled());
  await page.getByLabel('Seleccionar B.dwg',{exact:true}).check();
  await page.getByLabel('Común fila 2: Descripción',{exact:true}).fill('HISTORIAL COMUN');
  await page.getByRole('button',{name:'Ver / editar B.dwg',exact:true}).click();
  assert.equal(await page.getByLabel('VIÑETA G130 fila 2 Descripción',{exact:true}).inputValue(),'HISTORIAL COMUN');
  await page.getByLabel('VIÑETA G130 fila 2 Descripción',{exact:true}).fill('DIFERENTE');
  acceptDialog=false;await page.getByRole('button',{name:'Aplicar tabla base a seleccionados',exact:true}).click();
  assert.equal(await page.getByLabel('VIÑETA G130 fila 2 Descripción',{exact:true}).inputValue(),'DIFERENTE');acceptDialog=true;
  await page.getByLabel('Tabla base',{exact:true}).selectOption('0');
  await page.getByRole('button',{name:'Aplicar tabla base a seleccionados',exact:true}).click();
  assert.equal(await page.getByLabel('VIÑETA G130 fila 2 Descripción',{exact:true}).inputValue(),'HISTORIAL COMUN');
  assert.equal(await page.getByLabel('VIÑETA G130 fila 1 Dibujante',{exact:true}).inputValue(),'COMUN');
  await page.getByLabel('VIÑETA G130 fila 1 Dibujante',{exact:true}).fill('ESPECIAL');
  await page.getByRole('button',{name:'Guardar cambios con respaldo',exact:true}).click();
  await page.locator('#activity').waitFor({state:'hidden'});
  assert(saved.files.find(f=>f.id==='a').changes.some(c=>c.row===1&&c.column===5&&c.value==='HISTORIAL COMUN'));
  assert(saved.files.find(f=>f.id==='b').changes.some(c=>c.row===1&&c.column===5&&c.value==='HISTORIAL COMUN'));
  assert(saved.files.find(f=>f.id==='b').changes.some(c=>c.row===0&&c.column===2&&c.value==='ESPECIAL'));
  assert.equal(await page.locator('[data-page="revisions"]').count(),1);
  assert.deepEqual(errors,[]);
  console.log('OK: selection, per-file drafts, full common history, template confirmation/cancellation, individual exceptions and exact saved patches.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
