// Exercise the real viewer assets under the installed app's exact CSP.
// Only a headless browser and deterministic geometry are used; no CAD or app process.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const server=fs.readFileSync(path.join(root,'sincal/web/server.py'),'utf8');
const csp=server.match(/self\.send_header\("Content-Security-Policy", "([^"]+)"\)/)?.[1];
assert(csp,"Read the actual server's security policy instead of a permissive approximation.");
assert(csp.includes("style-src 'self'")&&!csp.includes('unsafe-inline'));

const mesh=(x0,x1,y0,y1,z0,z1)=>({vertices:[[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],
  [x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]],faces:[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]]});
const scene={units:'m',elements:[
  {key:'abutment.footing',label:'Fundación / zapata',meshes:[mesh(-5,5,-3,3,0,1.5)]},
  {key:'abutment.front_wall',label:'Muro frontal',meshes:[mesh(-4.8,4.8,-.7,.1,1.5,5)]},
  {key:'abutment.back_wall',label:'Muro espaldar',meshes:[mesh(-4.8,4.8,.1,.4,5,5.7)]},
  {key:'abutment.left_wing',label:'Ala izquierda',meshes:[mesh(-4.8,-4.4,.4,3,1.5,5.7)]},
  {key:'abutment.right_wing',label:'Ala derecha',meshes:[mesh(4.4,4.8,.4,3,1.5,5.7)]},
  {key:'abutment.stops',label:'Topes sísmicos',quality:'schematic',note:'Perfil nominal de los topes.',meshes:[mesh(-1,1,-.7,.1,5,5.5)]},
],bars:Array.from({length:8},(_,i)=>({key:['mesh_x','mesh_y','suple','lateral_x','lateral_y'][i%5],
  id:`piece:${i}`,placement_id:`placement:${i}`,element_key:'abutment.footing',mark:String(i+1),
  label:`Descripción extensa de familia de fierros ${i+1}`,diameter_mm:22,length_cm:1200,bend_radius_cm:6.6,
  points:[[-4.85,-2.7+i*.7,.95],[-4.85,-2.7+i*.7,.15],[4.85,-2.7+i*.7,.15],[4.85,-2.7+i*.7,.95]]})),
  reinforcement_note:'DESCRIPCIÓN EXTENSA DEL ACERO QUE NO DEBE OCUPAR EL PIE DEL VISOR.',
  issues:['Armadura de muros pendiente de definición.','Los topes se muestran con su perfil nominal.']};

const html='<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8">'+
  '<meta name="viewport" content="width=device-width,initial-scale=1">'+
  '<link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/fixture.css"></head>'+
  '<body><main id="host"></main><script type="module" src="/fixture.js"></script></body></html>';
const fixtureCss='#host{max-width:680px;margin:20px auto;padding:0 12px}';
const fixtureJs=`
import {mountAbutmentIsometric} from '/rebar_isometric.js';
window.violations=[];
document.addEventListener('securitypolicyviolation',e=>violations.push({directive:e.effectiveDirective,blocked:e.blockedURI}));
const project={data:{fixture:'unchanged JSON'},identification:{structure_name:'Puente Aconcagua · prueba local'},rebar:{entrada:{geometry:{alto_cm:150}}}};
const fixture=window.fixture={project,calls:[],errors:[],changes:0,scene:${JSON.stringify(scene)}};
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
const ctx={project,node,current:()=>true,changed:()=>fixture.changes++,notify:message=>fixture.errors.push(message),
 api:async(route,payload)=>{fixture.calls.push({route,payload:structuredClone(payload)});if(route!=='rebar/abutment/scene')throw Error('CAD and other routes forbidden');return structuredClone(fixture.scene);}};
fixture.inline=mountAbutmentIsometric(ctx,'entrada',document.getElementById('host'));
await fixture.inline.ready;window.ready=true;
`;

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1360,height:900}}),errors=[];
    page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',async route=>{
      const name=new URL(route.request().url()).pathname.slice(1);
      const headers={'Content-Security-Policy':csp,'X-Content-Type-Options':'nosniff'};
      if(!name)return route.fulfill({body:html,contentType:'text/html',headers});
      if(name==='fixture.js')return route.fulfill({body:fixtureJs,contentType:'text/javascript',headers});
      if(name==='fixture.css')return route.fulfill({body:fixtureCss,contentType:'text/css',headers});
      if(['app.css','rebar_isometric.js'].includes(name)||name.endsWith('.ttf')){
        const file=path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name);
        return route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf',headers});
      }
      return route.fulfill({status:404,body:'',headers});
    });
    await page.goto('http://sincal-viewer-layout.test/');await page.waitForFunction(()=>window.ready);
    await page.evaluate(()=>document.fonts.ready);
    const inline=page.getByRole('region',{name:'Vista isométrica del estribo',exact:true});
    const dialog=page.getByRole('dialog',{name:'Vista isométrica del estribo',exact:true});
    const canvas=container=>container.locator('.iso-viewport');
    const steel=container=>container.locator('[data-layer="armaduras"] polyline');
    const camera=container=>container.getByRole('img').evaluate(el=>Object.fromEntries(['yaw','pitch','zoom','scale','target'].map(key=>[key,el.dataset[key]])));
    const initial=await page.evaluate(()=>structuredClone(fixture.project));
    const assertInside=async(child,parent,message)=>{
      const [a,b]=await Promise.all([child.boundingBox(),parent.boundingBox()]);assert(a&&b,message);
      assert(a.x>=b.x-1&&a.y>=b.y-1&&a.x+a.width<=b.x+b.width+1&&a.y+a.height<=b.y+b.height+1,message);
    };
    const open=async()=>{await inline.getByRole('button',{name:'Ampliar visor',exact:true}).click();await dialog.getByRole('img').waitFor();};
    const close=async()=>{await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await page.locator('dialog.rebar-isometric').waitFor({state:'detached'});};
    const mark1=()=>dialog.getByRole('button',{name:'Mostrar marca 1 · Fundación / zapata',exact:true});
    const mark2=()=>dialog.getByRole('button',{name:'Mostrar marca 2 · Fundación / zapata',exact:true});
    const color=locator=>locator.evaluate(el=>({background:getComputedStyle(el).backgroundColor,text:getComputedStyle(el).color,opacity:getComputedStyle(el).opacity}));
    const settled=locator=>locator.evaluate(async el=>{getComputedStyle(el).backgroundColor;await Promise.all(el.getAnimations().map(animation=>animation.finished.catch(()=>{})));});
    fs.mkdirSync(path.join(root,'tmp'),{recursive:true});

    // Compact panel: controls form one ordered group; explanatory lists live only in the expansion.
    assert.equal(await inline.locator('.iso-aside,details,.iso-legend').count(),0);
    assert.equal(await inline.getByText(scene.reinforcement_note,{exact:true}).count(),0);
    assert.equal(await inline.locator('style').count(),0,'CSP forbids the former injected stylesheet.');
    assert.equal(await inline.getByRole('button').count(),5);
    for(const name of ['Alejar','Acercar','Ajustar','Isométrica','Ampliar visor'])
      await assertInside(inline.getByRole('button',{name,exact:true}),inline.locator('.iso-header'),`${name} stays in the header`);
    const compactViewport=await canvas(inline).boundingBox(),compactFooter=await inline.locator('.iso-footer').boundingBox();
    assert(compactFooter.y>=compactViewport.y+compactViewport.height-1,'Brief text is below the preview.');
    assert((await inline.locator('.iso-footer').innerText()).length<300,'The compact footer never enumerates all bar families.');
    assert.equal(await steel(inline).count(),8);
    await inline.screenshot({path:path.join(root,'tmp/rebar-viewer-compact.png')});
    assert.deepEqual(await page.evaluate(()=>violations),[],'Real server CSP is respected.');

    // Desktop expansion shows the element/mark controls and the canvas simultaneously.
    await open();
    const [asideBox,viewBox]=await Promise.all([dialog.locator('.iso-aside').boundingBox(),canvas(dialog).boundingBox()]);
    assert(asideBox.x+asideBox.width<viewBox.x,'Expanded controls are beside the canvas on the left.');
    assert(viewBox.width>=500&&viewBox.height>=400,'The canvas has useful room on a desktop.');
    await assertInside(dialog.locator('.iso-aside'),dialog,'Aside stays visible in dialog');
    await assertInside(canvas(dialog),dialog,'Canvas stays visible in dialog');
    assert.equal(await dialog.locator('.iso-element').count(),6);
    const [elementBox,markBox]=await Promise.all([dialog.getByRole('button',{name:'Fundación / zapata',exact:true}).boundingBox(),mark1().boundingBox()]);
    assert(markBox.x>elementBox.x+elementBox.width,'Marks sit next to their element.');
    assert.equal(await dialog.locator('.iso-legend').count(),0);
    assert.equal(await dialog.getByText(scene.reinforcement_note,{exact:true}).count(),0);
    assert.equal(await mark1().getAttribute('aria-pressed'),'true');
    assert.equal(await mark1().getAttribute('data-visible'),'true');
    const lit=await color(mark1());
    assert(!['rgba(0, 0, 0, 0)','transparent'].includes(lit.background));
    await mark1().click();
    await settled(mark1());
    assert.equal(await mark1().getAttribute('aria-pressed'),'false');
    assert.equal(await mark1().getAttribute('data-visible'),'false');
    assert.notEqual((await color(mark1())).background,lit.background,'Inactive marks lose their illuminated background.');
    assert.equal(await steel(dialog).filter({has:page.locator('title')}).count(),7);
    assert.equal(await dialog.locator('polyline[data-mark="1"]').count(),0);
    await mark1().click();assert.equal(await dialog.locator('polyline[data-mark="1"]').count(),1);
    await dialog.getByRole('checkbox',{name:'Mostrar armaduras',exact:true}).uncheck();
    await settled(mark1());
    assert.equal(await steel(dialog).count(),0);
    assert.equal(await mark1().getAttribute('aria-pressed'),'false','Pressed state follows actually visible steel.');
    assert.equal(await mark1().getAttribute('data-visible'),'false');
    assert.notEqual((await color(mark1())).background,lit.background,'Global hide also extinguishes the mark.');
    await mark1().click();
    assert.equal(await dialog.getByRole('checkbox',{name:'Mostrar armaduras',exact:true}).isChecked(),true);
    assert.equal(await dialog.locator('polyline[data-mark="1"]').count(),1,'Clicking a dark mark makes its bars visible.');
    await dialog.getByRole('checkbox',{name:'Mostrar armaduras',exact:true}).check();
    await dialog.getByRole('checkbox',{name:'Mostrar Fundación / zapata',exact:true}).uncheck();
    assert.equal(await steel(dialog).count(),0);assert.equal(await mark1().getAttribute('data-visible'),'false');
    await dialog.getByRole('checkbox',{name:'Mostrar Fundación / zapata',exact:true}).check();
    assert.equal(await mark1().getAttribute('data-visible'),'true');
    await dialog.locator('.iso-issues > summary').click();
    await dialog.getByText(scene.issues[0],{exact:true}).waitFor();
    await dialog.screenshot({path:path.join(root,'tmp/rebar-viewer-expanded.png')});

    // Changes made in the expanded controls become the compact preview state on close.
    await mark2().click();
    await dialog.getByRole('checkbox',{name:'Mostrar Muro frontal',exact:true}).uncheck();
    await dialog.getByRole('slider',{name:'Intensidad del moldaje',exact:true}).fill('14');
    await dialog.getByRole('button',{name:'Acercar',exact:true}).click();
    await dialog.getByRole('img').focus();await dialog.getByRole('img').press('ArrowRight');
    const editedCamera=await camera(dialog);
    await close();
    assert.deepEqual(await camera(inline),editedCamera);
    assert.equal(await inline.locator('polyline[data-mark="2"]').count(),0);
    assert.equal(await inline.locator('polygon[data-element="abutment.front_wall"]').count(),0);
    await page.evaluate(()=>fixture.inline.update());
    await page.waitForFunction(()=>document.querySelector('.iso-embedded')?.getAttribute('aria-busy')==='false');
    assert.deepEqual(await camera(inline),editedCamera);
    assert.equal(await inline.locator('polyline[data-mark="2"]').count(),0,'Live refresh preserves expanded filters.');
    await open();
    assert.equal(await mark2().getAttribute('aria-pressed'),'false');
    assert.equal(await dialog.getByRole('checkbox',{name:'Mostrar Muro frontal',exact:true}).isChecked(),false);
    assert.equal(await dialog.getByRole('slider',{name:'Intensidad del moldaje',exact:true}).inputValue(),'14');
    await dialog.getByRole('button',{name:'Acercar',exact:true}).click();
    const escapeCamera=await camera(dialog);
    await page.keyboard.press('Escape');await page.locator('dialog.rebar-isometric').waitFor({state:'detached'});
    assert.deepEqual(await camera(inline),escapeCamera,'Escape also transfers the expanded state.');

    // Many marks may scroll the controls, but cannot displace or hide the model.
    await page.evaluate(()=>{
      const example=fixture.scene.bars[0];
      fixture.scene.bars.push(...Array.from({length:72},(_,i)=>({...example,id:'extra:'+i,mark:String(i+9),placement_id:'extra:'+i})));
      fixture.inline.update();
    });
    await page.waitForFunction(()=>document.querySelector('.iso-embedded')?.getAttribute('aria-busy')==='false');
    await open();
    const beforeScroll=await canvas(dialog).boundingBox();
    assert(await dialog.locator('.iso-aside').evaluate(el=>el.scrollHeight>el.clientHeight),'Large control lists scroll independently.');
    await dialog.locator('.iso-aside').evaluate(el=>{el.scrollTop=el.scrollHeight;});
    assert.deepEqual(await canvas(dialog).boundingBox(),beforeScroll,'Sidebar scrolling leaves the canvas in place.');
    await assertInside(canvas(dialog),dialog,'Stress scene canvas remains visible');
    assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'No dialog horizontal overflow.');
    await dialog.locator('.iso-aside').evaluate(el=>{el.scrollTop=0;});
    await dialog.screenshot({path:path.join(root,'tmp/rebar-viewer-many-marks.png')});

    // Narrow screens retain a visible viewport while the controls scroll below it.
    await page.setViewportSize({width:410,height:850});
    const narrowView=await canvas(dialog).boundingBox();
    assert(narrowView.height>=240&&narrowView.width>=300);
    await assertInside(canvas(dialog),dialog,'Narrow canvas stays visible');
    await assertInside(dialog.locator('.iso-aside'),dialog,'Narrow controls stay visible');
    const narrowAside=await dialog.locator('.iso-aside').boundingBox();
    assert(narrowAside.y>=narrowView.y+narrowView.height-1,'Narrow controls move beneath the model.');
    await dialog.locator('.iso-aside').evaluate(el=>{el.scrollTop=el.scrollHeight;});
    assert.deepEqual(await canvas(dialog).boundingBox(),narrowView);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
    await dialog.locator('.iso-aside').evaluate(el=>{el.scrollTop=0;});
    await dialog.screenshot({path:path.join(root,'tmp/rebar-viewer-narrow.png')});
    await close();
    assert.equal(await inline.locator('.iso-aside,details,.iso-legend').count(),0);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await inline.screenshot({path:path.join(root,'tmp/rebar-viewer-compact-narrow.png')});
    assert.deepEqual(await page.evaluate(()=>fixture.project),initial,'View controls never modify project inputs.');
    assert.equal(await page.evaluate(()=>fixture.changes),0);
    assert(await page.evaluate(()=>fixture.calls.every(call=>call.route==='rebar/abutment/scene')));
    assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);
    assert.deepEqual(await page.evaluate(()=>violations),[],'No inline styles or other violations under the real app CSP.');
    assert.deepEqual(errors,[]);
    console.log('OK: real CSP, compact preview, adjacent illuminated marks, independent scroll, modal/inline state, wide/narrow layouts, no CAD or project mutations.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
