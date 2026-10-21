// UI contract check: local APIs are mocked; no actual installation or browser launch.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],calls=[];
    let status={id:'pasarela-bim',nombre:'Pasarela BIM',installed:false,source:null,version:null,embedded_supported:false,freecad_available:false,running:false,message:'Módulo no instalado.',online_install_available:true,release_url:'https://github.com/drossull/sincal-updates/releases/tag/v3.0.25',install_message:'Instala la versión compatible con SINCAL 3.0.25.'};
    let installFailure=false,onlineFailure=false,closeFailure=false,confirmClose=false;
    page.on('pageerror',e=>errors.push(e.message));
    page.on('dialog',d=>confirmClose?d.accept():d.dismiss());
    await page.route('**/*',async route=>{
      const request=route.request(),url=new URL(request.url()),p=url.pathname;
      if(url.port==='8766'){await route.fulfill({contentType:'text/html',body:`<html><body>Editor de prueba<script>parent.postMessage({type:'pasarela:ready',dirty:false,busy:false},'http://sincal.test')</script></body></html>`});return;}
      if(p.startsWith('/api/')){
        let data={},code=200;
        if(p==='/api/preferences')data={theme:'dark',palette:'sincal',zoom:'100'};
        else if(['/api/palettes','/api/jobs','/api/maps','/api/dwgprops/engines'].includes(p))data=[];
        else if(p==='/api/shell-selection')data={selection:null};
        else if(p==='/api/modules/pasarela/status')data=status;
        else if(p==='/api/modules/pasarela/install-online'){
          calls.push('online');assert.deepEqual(request.postDataJSON(),{});
          if(onlineFailure){code=502;data={error:'No se pudo descargar el módulo. Comprueba la conexión.'};}
          else{status={...status,installed:true,source:'user',version:'0.3.1',embedded_supported:true,message:'Módulo instalado.'};data=status;}
        }else if(p==='/api/modules/pasarela/release'){calls.push('release');data={url:status.release_url};}
        else if(p==='/api/modules/pasarela/install'){
          calls.push('install');assert.equal(request.headers()['x-sincal-token'],'test-token');
          assert.equal(request.headers()['content-type'],'application/zip');
          assert.equal(decodeURIComponent(request.headers()['x-file-name']),'Pasarela revisión.zip');
          assert.deepEqual(request.postDataBuffer(),Buffer.from('zip-placeholder'));
          if(installFailure){code=400;data={error:'El manifiesto del paquete no es válido.'};}
          else{status={...status,installed:true,source:'user',version:'0.3.1',embedded_supported:true,message:'Módulo instalado.'};data=status;}
        }else if(p==='/api/modules/pasarela/open'){
          calls.push('open');assert.deepEqual(request.postDataJSON(),{});
          status={...status,running:true};data={url:'http://127.0.0.1:8766/',embedding:1,parent_origin:'http://sincal.test'};
        }else if(p==='/api/modules/pasarela/close'){
          calls.push('close');
          if(closeFailure){code=409;data={error:'Hay una generación en curso.'};}
          else{status={...status,running:false};data=status;}
        }
        await route.fulfill({status:code,json:data});return;
      }
      if(p==='/logo.ico'){await route.fulfill({body:fs.readFileSync(path.resolve(__dirname,'../assets/icons/logo.ico')),contentType:'image/x-icon'});return;}
      const name=p==='/'?'index.html':p.slice(1),file=path.resolve(__dirname,'../sincal/web/static',name);
      if(fs.existsSync(file)&&fs.statSync(file).isFile())await route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
      else await route.fulfill({status:404,body:''});
    });
    await page.goto('http://sincal.test/#token=test-token');
    await page.getByRole('button',{name:'Pasarela BIM · No instalado',exact:true}).waitFor();
    const menu=await page.locator('#sidebar nav button span').allTextContents();
    assert.equal(menu[menu.indexOf('Generador de armadura')-1],'Pasarela BIM · No instalado');
    await page.locator('[data-page="pasarela"]').click();
    await page.getByText('Módulo no instalado',{exact:true}).waitFor();
    const open=page.getByRole('button',{name:'Abrir editor',exact:true,includeHidden:true}),file=page.getByLabel('Paquete de Pasarela BIM (.zip)',{exact:true});
    const online=page.getByRole('button',{name:'Instalar Pasarela BIM',exact:true,includeHidden:true});
    assert(await online.isEnabled());assert(await online.isVisible());
    assert(!(await page.locator('#pasarela-instalar details').evaluate(el=>el.open)));
    if(process.env.SINCAL_UI_SCREENSHOT)await page.screenshot({path:process.env.SINCAL_UI_SCREENSHOT.replace(/\.png$/,'_no_instalado.png'),fullPage:true});
    await page.getByText('Instalar o actualizar desde un ZIP local',{exact:true}).click();
    assert(await open.isDisabled());assert(await page.getByRole('button',{name:'Instalar paquete',exact:true}).isDisabled());
    const release=page.getByRole('button',{name:'Datos de publicación',exact:true});
    await release.click();await page.locator('#pasarela-release-info').waitFor();assert.equal(calls.filter(v=>v==='release').length,1);
    assert.equal(await page.getByLabel('Dirección de publicación',{exact:true}).inputValue(),status.release_url);
    assert(await page.getByLabel('Dirección de publicación',{exact:true}).getAttribute('readonly')!==null);
    assert.equal(await page.locator('a[target="_blank"]').count(),0);assert.equal(page.context().pages().length,1);assert.equal(page.url(),'http://sincal.test/');
    await file.setInputFiles({name:'invalido.txt',mimeType:'text/plain',buffer:Buffer.from('x')});
    await page.locator('#pasarela-module-message').getByText('Selecciona un ZIP no vacío de hasta 150 MiB.',{exact:true}).waitFor();
    assert(await page.getByRole('button',{name:'Instalar paquete',exact:true}).isDisabled());
    // Verify the size guard without allocating a 150 MiB test artifact.
    await file.evaluate(input=>{const item=new File(['x'],'grande.zip');Object.defineProperty(item,'size',{value:150*1024*1024+1});Object.defineProperty(input,'files',{configurable:true,value:[item]});input.dispatchEvent(new Event('change'));delete input.files;});
    assert(await page.getByRole('button',{name:'Instalar paquete',exact:true}).isDisabled());
    const packageFile={name:'Pasarela revisión.zip',mimeType:'application/zip',buffer:Buffer.from('zip-placeholder')};
    await file.setInputFiles(packageFile);installFailure=true;
    await page.getByRole('button',{name:'Instalar paquete',exact:true}).click();
    await page.locator('#pasarela-module-message').getByText('El manifiesto del paquete no es válido.',{exact:true}).waitFor();
    assert(await open.isDisabled());assert.equal(await page.locator('#pasarela-module-state').textContent(),'Módulo no instalado');
    onlineFailure=true;await online.click();
    await page.locator('#pasarela-module-message').getByText('No se pudo descargar el módulo. Comprueba la conexión.',{exact:true}).waitFor();
    assert.equal(await page.locator('#sidebar [data-page="pasarela"] span').textContent(),'Pasarela BIM · No instalado');
    onlineFailure=false;await online.click();await page.getByText('Módulo instalado',{exact:true}).waitFor();
    assert.equal(await page.locator('#sidebar [data-page="pasarela"] span').textContent(),'Pasarela BIM');assert(await online.isHidden());
    installFailure=false;await page.getByRole('button',{name:'Actualizar desde paquete',exact:true}).click();
    await page.getByRole('button',{name:'Abrir editor',exact:true,disabled:false}).waitFor();assert(await open.isEnabled());
    await page.getByText('No detectado: necesario para generar el modelo BIM',{exact:true}).waitFor();
    assert(await page.getByRole('button',{name:'Actualizar desde paquete',exact:true}).isDisabled());
    await open.click();await page.locator('#pasarela-editor-frame').waitFor();await page.getByRole('button',{name:'Ajustes',exact:true}).click();await page.getByText('Instalar o actualizar desde un ZIP local',{exact:true}).click();
    await file.setInputFiles(packageFile);assert(await page.getByRole('button',{name:'Actualizar desde paquete',exact:true}).isDisabled());
    const close=page.getByRole('button',{name:'Cerrar módulo',exact:true});
    await close.click();assert.equal(calls.filter(v=>v==='close').length,0);
    confirmClose=true;closeFailure=true;await close.click();
    await page.locator('#pasarela-module-message').getByText('Hay una generación en curso.',{exact:true}).waitFor();
    assert(await page.getByRole('button',{name:'Actualizar desde paquete',exact:true}).isDisabled());
    closeFailure=false;await close.click();await close.waitFor({state:'hidden'});
    assert(await page.getByRole('button',{name:'Actualizar desde paquete',exact:true}).isEnabled());
    status={...status,source:'development',freecad_available:true,message:'Disponible desde el código de desarrollo.'};
    await page.getByRole('button',{name:'Actualizar estado',exact:true}).click();await page.getByText('Disponible en desarrollo',{exact:true}).waitFor();
    assert(await page.getByRole('button',{name:'Abrir editor',exact:true}).isEnabled());
    assert.equal(await page.locator('#notice').textContent(),'');
    if(process.env.SINCAL_UI_SCREENSHOT)await page.screenshot({path:process.env.SINCAL_UI_SCREENSHOT,fullPage:true});
    await page.locator('[data-page="rebar"]').click();await page.getByRole('heading',{name:'Generador de armadura',exact:true}).waitFor();
    assert.deepEqual(errors,[]);assert.equal(calls.filter(v=>v==='open').length,1);assert.equal(calls.filter(v=>v==='online').length,2);
    console.log('OK: initial missing badge, online failure/success, source link, updated menu, secondary ZIP, binary auth/upload, launch and safe close/update.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
