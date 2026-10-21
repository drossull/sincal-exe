// Run against the dedicated development server; screenshots only, no FreeCAD job.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const output=path.resolve('pasarela_bim/generados/prueba_ejes');fs.mkdirSync(output,{recursive:true});
  const select=async(type,id)=>page.locator(`#entity-list [data-select-type="${type}"][data-select-id="${id}"]`).click();
  const dump=async()=>{const waiting=page.waitForEvent('download');await page.locator('#export-json').click();const d=await waiting,stream=await d.createReadStream(),chunks=[];for await(const c of stream)chunks.push(c);return JSON.parse(Buffer.concat(chunks).toString('utf8'));};
  try{
    await page.goto('http://127.0.0.1:8767/');await page.locator('#new-project').click();
    await page.locator('[name="nombre"]').fill('Ensayo independiente de ejes');
    await page.getByRole('button',{name:'Crear proyecto',exact:true}).click();await page.locator('[name="vanos"]').selectOption('2');
    await page.getByRole('dialog').getByRole('button',{name:'Instalar atravieso',exact:true}).click();
    let m=await dump();assert.equal(m.ejes.filter(a=>a.tipo==='atravieso').length,1);assert.equal(m.ejes.filter(a=>a.tipo==='apoyo').length,3);
    for(const start of ['C1','N1']){await page.locator(`[data-node-add="${start}"]`).click();await page.locator('[name="direccion"]').selectOption('Y+');await page.locator('[name="longitud"]').fill('10');await page.getByRole('button',{name:'Añadir conexión',exact:true}).click();}
    m=await dump();let er=m.ejes.find(a=>a.tipo==='recorrido');assert.equal(er.tramos.length,2);const erId=er.id,erUuid=er.uuid,ea=m.ejes.find(a=>a.tipo==='atravieso');
    await select('axis',erId);await page.locator('[data-action="edit-axis"]').click();await page.locator('[name="tramos"]').fill('V3');await page.getByRole('button',{name:'Actualizar eje',exact:true}).click();
    await page.locator('#add-axis').click();await page.locator('[name="nombre"]').fill('Tramo final del acceso');await page.locator('[data-axis-member="V4"]').click();await page.getByRole('button',{name:'Crear eje',exact:true}).click();
    m=await dump();assert.equal(m.ejes.filter(a=>a.tipo==='recorrido').length,2);assert.equal(m.ejes.find(a=>a.id===erId).uuid,erUuid);
    await select('axis',ea.id);await page.locator('[data-action="axis-elevation"]').click();assert.equal(await page.locator('.axis-elevation').count(),1);assert.match(await page.locator('#scene').textContent(),/EC1/);await page.screenshot({path:path.join(output,'01_elevacion.png')});
    await page.locator('#view-plan').click();await select('axis',erId);await page.locator('[data-action="move-axis"]').click();await page.locator('[name="dy"]').fill('1');
    assert.equal(await page.getByRole('button',{name:'Aplicar desplazamiento',exact:true}).isDisabled(),true);
    await page.locator('[name="connected"]').check();assert.equal(await page.getByRole('button',{name:'Aplicar desplazamiento',exact:true}).isDisabled(),false);
    assert.match(await page.locator('#axis-move-preview').textContent(),/Origen actualizado/);await page.screenshot({path:path.join(output,'02_movimiento.png')});await page.getByRole('button',{name:'Aplicar desplazamiento',exact:true}).click();
    m=await dump();assert.equal(m.proyecto.georreferencia.norte_m,1);assert.equal(m.ejes.find(a=>a.id===erId).uuid,erUuid);await page.screenshot({path:path.join(output,'03_planta.png')});
    await select('axis',ea.id);await page.locator('[data-field="id"]').fill('PRINCIPAL');await page.locator('[data-field="id"]').press('Tab');
    await select('edge','V1');await page.locator('[data-field="id"]').fill('TRAMO_1');await page.locator('[data-field="id"]').press('Tab');
    await select('node','C1');await page.locator('[data-field="id"]').fill('CEPA_1');await page.locator('[data-field="id"]').press('Tab');
    m=await dump();assert.ok(m.ejes.find(a=>a.id==='PRINCIPAL').tramos.includes('TRAMO_1'));assert.ok(m.ejes.some(a=>a.tipo==='apoyo'&&a.nodo==='CEPA_1'));
    await select('edge','V3');await page.locator('[data-action="delete"]').click();m=await dump();assert.ok(m.ejes.every(a=>(a.tramos||[]).every(id=>m.tramos.some(e=>e.id===id))));
    const existing=structuredClone(m);existing.ejes=[];existing.proyecto.revision=87;await page.locator('#file-input').setInputFiles({name:'legado_ejes.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(existing))});
    await page.waitForFunction(()=>document.querySelector('#toast')?.textContent.includes('importada'));m=await dump();assert.equal(m.ejes.length,0);assert.equal(m.proyecto.revision,87);
    await page.locator('#suggest-axes').click();await page.getByRole('button',{name:'Aplicar propuesta',exact:true}).click();m=await dump();assert.ok(m.ejes.length);assert.deepEqual(errors,[]);await page.screenshot({path:path.join(output,'04_propuesta_aplicada.png')});
    console.log(JSON.stringify({ok:true,ejes:m.ejes.length,errors}));
  }catch(error){await page.screenshot({path:path.join(output,'error.png')});console.error(error);console.error('Page errors:',errors);process.exitCode=1;}
  finally{await browser.close();}
})();
