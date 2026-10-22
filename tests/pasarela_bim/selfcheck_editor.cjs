// End-to-end workflow against the dedicated local development server.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const output=path.resolve('pasarela_bim/generados/prueba_editor');fs.mkdirSync(output,{recursive:true});
function equivalent(actual,expected){
 if(typeof expected==='number'){assert.ok(Math.abs(actual-expected)<=1e-10,`${actual} differs from ${expected}`);return;}
 if(expected&&typeof expected==='object'){assert.deepEqual(Object.keys(actual),Object.keys(expected));for(const key of Object.keys(expected))equivalent(actual[key],expected[key]);return;}
 assert.equal(actual,expected);
}
function verifyPersistedAxes(model,report){
 const code=`import json,sys,zipfile,xml.etree.ElementTree as E
with zipfile.ZipFile(sys.argv[1]) as z:
 root=E.fromstring(z.read('Document.xml'))
 result={}
 for o in root.findall('.//ObjectData/Object'):
  values={p.get('name'):p.find('String').get('value') for p in o.findall('Properties/Property') if p.find('String') is not None}
  if values.get('RolBIM')=='eje': result[o.get('name')]=values
 print(json.dumps(result))`;
 const persisted=JSON.parse(execFileSync('python',['-c',code,report.archivo_fcstd],{encoding:'utf8'}));
 assert.equal(Object.keys(persisted).length,model.ejes.length);
 for(const axis of model.ejes){const saved=report.ejes.find(e=>e.id===axis.id);assert.ok(saved);assert.equal(saved.tipo,axis.tipo);const object=persisted[saved.objeto_freecad];assert.ok(object);assert.equal(object.UUIDOrigen,axis.uuid);assert.equal(object.UUIDBIM,saved.uuid);assert.equal(object.IDTopologico,axis.id);assert.equal(object.TipoEje,axis.tipo);}
}
(async()=>{
 const existing=process.argv.indexOf('--verify-existing');
 if(existing!==-1){
  const folder=path.resolve(process.argv[existing+1]),model=JSON.parse(fs.readFileSync(path.join(folder,'topologia.json'),'utf8')),report=JSON.parse(fs.readFileSync(path.join(folder,'reporte_generacion.json'),'utf8'));
  verifyPersistedAxes(model,report);assert.equal(report.valido,true);assert.equal(report.verificacion.guardado_y_reabierto,true);assert.equal(report.ejes.length,model.ejes.length);assert.equal(report.verificacion.ejes_referencia_conservados,model.ejes.length);
  assert.ok(model.ejes.filter(e=>e.tipo==='atravieso').length>=1);assert.ok(model.ejes.filter(e=>e.tipo==='recorrido').length>=2);assert.ok(model.ejes.filter(e=>e.tipo==='apoyo').length>=5);
  assert.ok(report.archivos_elevaciones.length>=3);for(const file of report.archivos_elevaciones)assert.match(fs.readFileSync(file,'utf8'),/<svg\b/);
  const result={ok:true,carpeta:folder,archivo_fcstd:report.archivo_fcstd,ejes:report.ejes.length,elevaciones:report.archivos_elevaciones.map(f=>path.basename(f)),uuid_origen_y_bim_verificados:true,verificacion:report.verificacion};
  fs.writeFileSync(path.join(output,'resultado_comprobacion_ejes.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));return;
 }
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const select=async(type,id)=>page.locator(`#entity-list [data-select-type="${type}"][data-select-id="${id}"]`).click();
 const dump=async(name)=>{const event=page.waitForEvent('download');await page.locator('#export-json').click();const file=await event;const target=path.join(output,name);await file.saveAs(target);return JSON.parse(fs.readFileSync(target,'utf8'));};
 try{
  await page.goto('http://127.0.0.1:8767/');await page.locator('#new-project').click();
  await page.locator('[name="nombre"]').fill('Ensayo de pasarela desde cero');
  for(const [key,value] of Object.entries({este_m:350000,norte_m:6000000,cota_m:120,norte_desde_y_horario_deg:0}))await page.locator(`[name="${key}"]`).fill(String(value));
  await page.getByRole('button',{name:'Crear proyecto',exact:true}).click();
  await page.locator('[name="vanos"]').selectOption('2');
  await page.screenshot({path:path.join(output,'01_atravieso.png')});
  await page.getByRole('dialog').getByRole('button',{name:'Instalar atravieso',exact:true}).click();
  assert.equal(await page.locator('[data-node-add]').count(),3);
  assert.ok(await page.locator('#north-symbol').innerText());
  await page.locator('[data-node-add="C1"]').click();
  await page.locator('[name="direccion"]').selectOption('Y+');await page.locator('[name="longitud"]').fill('20');
  if(await page.locator('[name="sentido"]').count())await page.locator('[name="sentido"]').selectOption('bajar');
  else await page.locator('[name="desnivel"]').fill('-1.6');
  await page.getByRole('button',{name:'Añadir conexión',exact:true}).click();
  await page.locator('[data-node-add="C3"]').click();
  await page.locator('[name="direccion"]').selectOption('Y-');await page.locator('[name="longitud"]').fill('8');
  await page.locator('[name="funcion"]').selectOption('escalera');await page.locator('[name="familia"]').selectOption('escalera');
  await page.locator('[name="desnivel"]').fill('-2.4');await page.getByRole('button',{name:'Añadir conexión',exact:true}).click();
  let model=await dump('borrador.json');assert.equal(model.version,2);assert.equal(model.proyecto.unidades,'m');assert.equal(model.nodos.length,5);
  const ramp=model.tramos.find(e=>e.funcion==='rampa'), a=model.nodos.find(n=>n.id===ramp.desde),b=model.nodos.find(n=>n.id===ramp.hasta);
  assert.ok(Math.abs(Math.abs(b.z-a.z)/Math.hypot(b.x-a.x,b.y-a.y)-.08)<1e-10);
  await select('edge','V1');await page.locator('[data-section-action="type"]').selectOption('cajon');
  await page.locator('[data-section-field="canto_mm"]').fill('1');await page.locator('[data-section-action="apply"]').click();
  assert.ok(await page.locator('.sections-svg').count());
  await page.locator('#view-iso').click();await page.screenshot({path:path.join(output,'02_seccion.png')});
  await select('node','N1');await page.locator('[data-field="z"]').fill('4.5');await page.locator('[data-field="z"]').press('Tab');
  await page.locator('dialog[open] #move-preview').waitFor();await page.screenshot({path:path.join(output,'03_cambio_cota.png')});
  await page.getByRole('button',{name:'Aplicar cambio',exact:true}).click();
  for(const id of ['C1','C2','C3','N1','N2']){
   await select('node',id);await page.locator('[data-action="create-support"]').click();
   await page.getByRole('button',{name:'Crear apoyo',exact:true}).click();
  }
  const dxf=['0','SECTION','2','HEADER','9','$INSUNITS','70','6','0','ENDSEC','0','SECTION','2','ENTITIES'];
  for(const x of [349990,350010])dxf.push('0','LINE','8','BORDES','10',String(x),'20','5999980','11',String(x),'21','6000030');
  dxf.push('0','LINE','8','MEDIANA','10','350000','20','5999980','11','350000','21','6000030','0','ENDSEC','0','EOF');
  await page.locator('#planta-input').setInputFiles({name:'planta_ensayo.dxf',mimeType:'application/octet-stream',buffer:Buffer.from(dxf.join('\n')+'\n')});
  await page.locator('#site-visible').waitFor();assert.equal(await page.locator('.site-plan polyline').count(),3);
  model=await dump('proyecto_metros.json');assert.equal(model.emplazamiento.planta.entidades.length,3);
  const originalRevision=model.proyecto.revision;
  await page.locator('#file-input').setInputFiles(path.join(output,'proyecto_metros.json'));
  await page.waitForFunction(()=>document.querySelector('#toast')?.textContent.includes('importada'));
  const reopened=await dump('reabierto.json');assert.equal(reopened.proyecto.revision,originalRevision);
  for(const key of ['nodos','tramos','familias','soportes','fundaciones','emplazamiento','ejes'])equivalent(reopened[key],model[key]);
  assert.ok(model.ejes.filter(e=>e.tipo==='atravieso').length>=1);
  assert.ok(model.ejes.filter(e=>e.tipo==='recorrido').length>=2);
  assert.ok(model.ejes.filter(e=>e.tipo==='apoyo').length>=5);
  await page.locator('#view-iso').click();await select('edge','V4');await page.screenshot({path:path.join(output,'04_modelo.png')});
  const check=page.waitForResponse(r=>r.url().endsWith('/api/validar'));await page.locator('#validate').click();const validation=await(await check).json();
  assert.equal(validation.generable,true,JSON.stringify(validation.errores));
  let generation;
  if(process.argv.includes('--generate')){
   const dispatch=page.waitForResponse(r=>r.url().endsWith('/api/generar'));
   await page.locator('#generate').click();const started=await(await dispatch).json();assert.ok(started.trabajo_id);
   await page.waitForFunction(()=>['DISPONIBLE','CON AVISOS','ERROR'].includes(document.querySelector('#delivery-status').textContent),{},{timeout:240000});
   assert.notEqual(await page.locator('#delivery-status').innerText(),'ERROR',await page.locator('#delivery-content').innerText());
   const result=await(await page.request.get(`http://127.0.0.1:8767/api/trabajos/${encodeURIComponent(started.trabajo_id)}`)).json();
   assert.equal(result.estado,'completado');assert.equal(result.resultado.valido,true);
   const elevations=result.archivos.filter(f=>/^elevacion_.*\.svg$/i.test(f.nombre));
   assert.ok(elevations.length>=3,JSON.stringify(result.archivos));
   for(const file of elevations){assert.equal(await page.locator('.download-link').filter({hasText:file.nombre}).count(),1);const response=await page.request.get(new URL(file.url,'http://127.0.0.1:8767').href);assert.equal(response.status(),200);assert.match(await response.text(),/<svg\b/);}
   assert.equal(result.resultado.ejes.length,model.ejes.length);assert.equal(result.resultado.verificacion.ejes_referencia_conservados,model.ejes.length);
   assert.equal(result.resultado.verificacion.elevaciones_derivadas,elevations.length);assert.equal(result.resultado.verificacion.guardado_y_reabierto,true);
   verifyPersistedAxes(model,result.resultado);
   generation={trabajo_id:started.trabajo_id,carpeta:path.dirname(result.resultado.archivo_fcstd),archivo_fcstd:result.resultado.archivo_fcstd,ejes:result.resultado.ejes.length,elevaciones:elevations.map(f=>f.nombre),verificacion:result.resultado.verificacion};
   fs.writeFileSync(path.join(output,'resultado_comprobacion_ejes.json'),JSON.stringify(generation,null,2)+'\n');
   await page.screenshot({path:path.join(output,'05_generado.png')});
  }
  assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,nodos:model.nodos.length,tramos:model.tramos.length,fundaciones:model.fundaciones.length,ejes:model.ejes.length,generation,validation,errors},null,2));
 }catch(e){await page.screenshot({path:path.join(output,'error.png')});console.error(e);console.error('Page errors:',errors);process.exitCode=1;}
 finally{await browser.close();}
})();
