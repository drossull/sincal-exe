// Real host/editor scripts in two origins. Native launch/install and validation APIs are simulated.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const host='http://127.0.0.1:48031',editor='http://127.0.0.1:48032';
const output=path.resolve('tmp/prueba_pasarela_integrada');fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1360,height:900},acceptDownloads:true}),errors=[],calls=[];
    page.setDefaultTimeout(15000);
    let status={installed:true,source:'user',version:'0.3.0',embedded_supported:false,running:false,online_install_available:true},badAddress=true,closeFails=false,acceptClose=false;
    page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>acceptClose?d.accept():d.dismiss());
    await page.route('**/*',async route=>{
      const request=route.request(),url=new URL(request.url()),p=url.pathname,module=url.origin===editor;
      if(p.startsWith('/api/')){
        let data={},code=200;
        if(module){
          if(p==='/api/estado')data={freecad_disponible:false};
          else if(p==='/api/validar')data={valido:true,generable:false,errores:[],avisos:[],pendientes:[{codigo:'SOPORTE',elemento:'C1',mensaje:'Completa los apoyos.'}],resumen:{nodos:3,tramos:2,vigas:2,retornos:0,fustes:0,estribos:0,dados:0,pilotes:0}};
        }else{
          if(p==='/api/preferences')data={theme:'dark',palette:'sincal',zoom:'100'};
          else if(['/api/palettes','/api/jobs','/api/maps','/api/dwgprops/engines'].includes(p))data=[];
          else if(p==='/api/shell-selection')data={selection:null};
          else if(p==='/api/modules/pasarela/status')data=status;
          else if(p==='/api/modules/pasarela/install-online'){calls.push('install');status={...status,version:'0.3.1',embedded_supported:true};data=status;}
          else if(p==='/api/modules/pasarela/open'){calls.push('open');status={...status,running:true};data={url:badAddress?'http://127.0.0.1:48032/?unsafe=1':editor+'/',embedding:1,parent_origin:host};}
          else if(p==='/api/modules/pasarela/close'){calls.push('close');if(closeFails){code=409;data={error:'Hay una generación en curso.'};}else{status={...status,running:false};data=status;}}
        }
        await route.fulfill({status:code,json:data});return;
      }
      if(!module&&p==='/logo.ico'){await route.fulfill({body:fs.readFileSync(path.resolve(__dirname,'../assets/icons/logo.ico')),contentType:'image/x-icon'});return;}
      const name=p==='/'?'index.html':p.slice(1),file=path.resolve(__dirname,module?'../pasarela_bim/web':'../sincal/web/static',name);
      if(!fs.existsSync(file)||!fs.statSync(file).isFile()){await route.fulfill({status:404,body:''});return;}
      let body=fs.readFileSync(file);
      if(module&&name==='index.html')body=Buffer.from(body.toString().replace('__PASARELA_TOKEN__','test').replace('__PASARELA_PARENT_ORIGIN__',host));
      await route.fulfill({body,contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto(host+'/#token=test');await page.locator('[data-page="pasarela"]').click();
    await page.getByText('Actualización necesaria',{exact:true}).waitFor();
    assert(await page.getByRole('button',{name:'Abrir editor',exact:true,includeHidden:true}).isHidden());
    await page.getByRole('button',{name:'Actualizar Pasarela BIM',exact:true}).click();
    await page.getByRole('button',{name:'Abrir editor',exact:true}).click();
    await page.getByText('El módulo no proporcionó una dirección local compatible. Actualiza Pasarela BIM y vuelve a intentarlo.',{exact:true}).first().waitFor();
    assert.equal(await page.locator('iframe').count(),0);
    badAddress=false;await page.getByRole('button',{name:'Abrir editor',exact:true}).click();
    const frameElement=page.locator('#pasarela-editor-frame');await frameElement.waitFor();
    const frame=await frameElement.elementHandle().then(el=>el.contentFrame());
    await page.locator('#pasarela-editor-status').getByText('Editor listo',{exact:true}).waitFor();
    assert.equal(page.context().pages().length,1);assert.equal(page.url(),host+'/');
    const bounds=await frameElement.boundingBox();assert.ok(bounds.width>=1000&&bounds.height>=650,JSON.stringify(bounds));
    assert(await page.locator('#outline').isHidden());
    await frame.locator('#new-project').click();await frame.locator('[name="nombre"]').fill('Proyecto integrado');
    await frame.getByRole('button',{name:'Crear proyecto',exact:true}).click();
    await frame.locator('[name="vanos"]').selectOption('2');await frame.getByRole('dialog').getByRole('button',{name:'Instalar atravieso',exact:true}).click();
    await frame.locator('[data-node-add="C1"]').click();await frame.locator('[name="direccion"]').selectOption('Y+');
    await frame.locator('[name="longitud"]').fill('20');await frame.getByRole('button',{name:'Añadir conexión',exact:true}).click();
    await frame.locator('#entity-list [data-select-type="edge"][data-select-id="V3"]').click();
    await page.locator('#pasarela-editor-status').getByText('Cambios sin guardar en JSON',{exact:true}).waitFor();
    const guarded=()=>page.evaluate(()=>{const e=new Event('beforeunload',{cancelable:true});window.dispatchEvent(e);return e.defaultPrevented;});
    assert.equal(await guarded(),true);
    // Same-source/wrong-origin and same-origin/wrong-source cannot clear the dirty guard.
    await page.evaluate(origin=>{const frame=document.querySelector('iframe');for(const [source,o]of [[frame.contentWindow,'http://127.0.0.1:1'],[window,origin]])window.dispatchEvent(new MessageEvent('message',{source,origin:o,data:{type:'pasarela:state',dirty:false,busy:false}}));},editor);
    assert.equal(await guarded(),true);
    await page.evaluate(()=>{window.savedPasarelaFrame=document.querySelector('iframe');window.removedPasarelaFrames=0;new MutationObserver(records=>{for(const r of records)for(const el of r.removedNodes)if(el===window.savedPasarelaFrame||el.contains?.(window.savedPasarelaFrame))window.removedPasarelaFrames++;}).observe(document.body,{subtree:true,childList:true});});
    await frame.evaluate(()=>window.navigationSentinel=crypto.randomUUID());const sentinel=await frame.evaluate(()=>window.navigationSentinel);
    const selected=await frame.locator('#inspector').innerText();assert(await frame.locator('#undo').isEnabled());
    await page.screenshot({path:path.join(output,'01_editor_1360x900.png')});
    await page.locator('[data-page="home"]').click();assert(await frameElement.isHidden());assert.equal(await guarded(),true);assert(await page.locator('#outline').isVisible());
    await page.locator('[data-page="rebar"]').click();await page.getByRole('heading',{name:'Generador de armadura',exact:true}).waitFor();
    await page.locator('[data-page="pasarela"]').click();assert(await frameElement.isVisible());
    assert.equal(await frame.evaluate(()=>window.navigationSentinel),sentinel);assert.equal(await frame.locator('#inspector').innerText(),selected);
    assert(await frame.locator('#undo').isEnabled());assert.equal(await page.evaluate(()=>window.removedPasarelaFrames),0);
    assert.equal(await page.evaluate(()=>document.querySelector('iframe')===window.savedPasarelaFrame),true);
    const save=async name=>{const download=page.waitForEvent('download');await frame.locator('#export-json').click();const file=await download,target=path.join(output,name);await file.saveAs(target);return JSON.parse(fs.readFileSync(target,'utf8'));};
    const saved=await save('proyecto.json');assert.equal(saved.version,2);assert.equal(saved.nodos.length,4);assert.equal(saved.tramos.length,3);
    // A blob download cannot confirm that a native Save dialog actually wrote the file.
    await page.locator('#pasarela-editor-status').getByText('Cambios sin guardar en JSON',{exact:true}).waitFor();assert.equal(await guarded(),true);
    await frame.locator('#file-input').setInputFiles(path.join(output,'proyecto.json'));await frame.locator('#toast').filter({hasText:'Configuración importada.'}).waitFor();
    await page.locator('#pasarela-editor-status').getByText('Editor listo',{exact:true}).waitFor();assert.equal(await guarded(),false);
    const reopened=await save('reabierto.json');for(const key of ['nodos','tramos','familias','ejes'])assert.deepEqual(reopened[key],saved[key]);
    // Busy state blocks destructive close and stays guarded even while the editor is hidden.
    await frame.evaluate(()=>PasarelaIntegration.setBusy('smoke',true));await page.getByRole('button',{name:'Cerrar editor',exact:true,disabled:true}).waitFor();
    assert.equal(await guarded(),true);await frame.evaluate(()=>PasarelaIntegration.setBusy('smoke',false));
    await page.getByRole('button',{name:'Ajustes',exact:true}).click();await page.getByRole('button',{name:'Volver al editor',exact:true}).waitFor();
    assert.equal(await frame.evaluate(()=>window.navigationSentinel),sentinel);
    await page.getByRole('button',{name:'Volver al editor',exact:true}).click();
    await page.getByRole('button',{name:'Cerrar editor',exact:true}).click();assert.equal(calls.filter(v=>v==='close').length,0);
    acceptClose=true;closeFails=true;await page.getByRole('button',{name:'Cerrar editor',exact:true}).click();
    await page.locator('#notice').getByText('Hay una generación en curso.',{exact:true}).waitFor();assert.equal(await frame.evaluate(()=>window.navigationSentinel),sentinel);
    closeFails=false;await page.getByRole('button',{name:'Cerrar editor',exact:true}).click();await frameElement.waitFor({state:'detached'});
    await page.getByRole('button',{name:'Abrir editor',exact:true}).waitFor();assert.equal(await guarded(),false);
    assert.deepEqual(errors,[]);assert.equal(calls.filter(v=>v==='open').length,2);assert.equal(calls.filter(v=>v==='install').length,1);
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({ok:true,bounds,iframePersistent:true,selectionAndUndoPreserved:true,jsonRoundtrip:true,messageOriginAndSourceVerified:true,errors},null,2));
    console.log('OK: embedded editor, update, URL guards, persistence, real JSON download/import, dirty/busy and safe close. Evidence: '+output);
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
