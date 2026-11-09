// Isolated browser checks: no CAD connection, no changes to project inputs.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

const mesh=(x0,x1,y0,y1,z0,z1)=>({
  vertices:[[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]],
  faces:[[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]],
});
const scene={units:'m',elements:[
  {key:'abutment.footing',label:'Fundación',meshes:[mesh(-4,4,-2,2,0,1.5)]},
  {key:'abutment.front_wall',label:'Muro frontal',meshes:[mesh(-3,3,-.5,.5,1.5,5)]},
],bars:[{key:'main',element_key:'abutment.footing',mark:'1',diameter_mm:22,points:[[-3.8,-1.8,.2],[3.8,-1.8,.2]]}],issues:['Armadura de muros pendiente.']};

const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8">
<link rel="stylesheet" href="/app.css"></head><body>
<main><button id="open">Abrir isométrica</button><div id="host"></div></main>
<script type="module">
import {openAbutmentIsometric,mountAbutmentIsometric} from '/rebar_isometric.js';
const project={data:{estribos:{tipo_estribo_entrada:'muro_lleno',tipo_estribo_salida:'muro_lleno'}},identification:{structure_name:'Puente de prueba'},rebar:{entrada:{geometry:{alto_cm:150},custom:'entrada'},salida:{geometry:{alto_cm:180},custom:'salida'}}};
const fixture=window.fixture={project,calls:[],errors:[],delayNext:0,errorNext:false,current:true,changes:0,scene:${JSON.stringify(scene)}};
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const ctx={project,node,current:()=>fixture.current,changed:()=>fixture.changes++,notify:message=>fixture.errors.push(message),
  api:async(route,payload)=>{fixture.calls.push({route,payload:structuredClone(payload)});if(route!=='rebar/abutment/scene')throw Error('Unexpected API call: '+route);
    const delay=fixture.delayNext,error=fixture.errorNext;fixture.delayNext=0;fixture.errorNext=false;const result=structuredClone(fixture.scene);result.instance_key=payload.instance_key;
    if(delay)await new Promise(resolve=>setTimeout(resolve,delay));if(error)throw Error('Escena de prueba no disponible');return result;},
};
fixture.open=(instance='entrada',element=null)=>openAbutmentIsometric(ctx,instance,element);
fixture.mount=()=>{fixture.inline=mountAbutmentIsometric(ctx,'entrada',document.getElementById('host'));return fixture.inline.ready;};
document.getElementById('open').addEventListener('click',()=>fixture.open());
window.ready=true;
</script></body></html>`;

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1360,height:900},hasTouch:true}),errors=[];
    page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',async route=>{
      const name=new URL(route.request().url()).pathname.slice(1);
      if(!name)return route.fulfill({body:harness,contentType:'text/html'});
      const file=path.resolve(__dirname,name.endsWith('.ttf')?'../assets/fonts':'../sincal/web/static',name);
      if(name==='rebar_isometric.js'||name==='app.css'||name.endsWith('.ttf'))
        return route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
      return route.fulfill({status:404,body:''});
    });
    await page.goto('http://sincal-isometric.test/');await page.waitForFunction(()=>window.ready);
    const initial=await page.evaluate(()=>structuredClone(fixture.project));
    await page.getByRole('button',{name:'Abrir isométrica',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'Vista isométrica del estribo'});
    const drawing=dialog.getByRole('img');
    await drawing.waitFor();
    assert.equal(await page.evaluate(()=>fixture.calls.length),1);
    assert.equal(await page.evaluate(()=>fixture.calls[0].route),'rebar/abutment/scene');
    assert.equal(await dialog.getByRole('heading',{name:'Estribo de entrada · Isométrica'}).count(),1);
    assert.equal(await drawing.locator('[data-layer="moldajes"] polygon').count(),12);
    assert.equal(await drawing.locator('[data-layer="armaduras"] polyline').count(),1);
    const steel=drawing.locator('[data-layer="armaduras"] polyline');
    const originalPoints=await steel.getAttribute('points');
    const camera=()=>drawing.evaluate(el=>({yaw:Number(el.dataset.yaw),pitch:Number(el.dataset.pitch),zoom:Number(el.dataset.zoom),scale:Number(el.dataset.scale),target:JSON.parse(el.dataset.target)}));
    const near=(actual,expected,label,tolerance=1e-7)=>assert(Math.abs(actual-expected)<=tolerance,`${label}: ${actual} != ${expected}`);
    const vertical=async()=>{
      const z=await drawing.locator('line[data-axis="Z"]').evaluate(el=>({x1:Number(el.getAttribute('x1')),x2:Number(el.getAttribute('x2')),y1:Number(el.getAttribute('y1')),y2:Number(el.getAttribute('y2'))}));
      near(z.x1,z.x2,'Z remains vertical');assert(z.y2<z.y1,'Positive Z always points up');
      const verticalEdges=await drawing.locator('[data-layer="moldajes"] line').evaluateAll(lines=>lines.filter(el=>Math.abs(Number(el.getAttribute('x1'))-Number(el.getAttribute('x2')))<1e-8).length);
      assert(verticalEdges>=8,'Both concrete meshes retain their vertical edges');
    };
    const drag=async(dx,dy,{button='middle',shift=false}={})=>{
      const box=await drawing.boundingBox(),x=box.x+box.width*.5,y=box.y+box.height*.5;
      if(shift)await page.keyboard.down('Shift');
      try{
        await page.mouse.move(x,y);await page.mouse.down({button});
        await page.mouse.move(x+dx,y+dy,{steps:6});await page.mouse.up({button});
      }finally{if(shift)await page.keyboard.up('Shift');}
    };
    const screenPoints=()=>steel.evaluate(el=>Array.from(el.points,p=>{const q=new DOMPoint(p.x,p.y).matrixTransform(el.getScreenCTM());return [q.x,q.y];}));
    const originalCamera=await camera();
    assert(Number.isFinite(originalCamera.scale)&&originalCamera.scale>0);
    await vertical();
    await dialog.getByRole('button',{name:'Acercar',exact:true}).click();
    assert.notEqual(await steel.getAttribute('points'),originalPoints);
    await dialog.getByRole('button',{name:'Ajustar',exact:true}).click();
    assert.equal(await steel.getAttribute('points'),originalPoints);
    assert.equal(await dialog.getByRole('button',{name:/Girar/}).count(),0);
    for(let i=0;i<25;i++)await dialog.getByRole('button',{name:'Acercar',exact:true}).click();
    near((await camera()).zoom,40,'Close inspection zoom limit');
    for(let i=0;i<40;i++)await dialog.getByRole('button',{name:'Alejar',exact:true}).click();
    near((await camera()).zoom,.1,'Wide zoom limit');
    await dialog.getByRole('button',{name:'Isométrica',exact:true}).click();
    await drawing.focus();await page.keyboard.press('ArrowRight');
    assert.notEqual(await steel.getAttribute('points'),originalPoints);
    await dialog.getByRole('button',{name:'Isométrica',exact:true}).click();

    const beforeSelection=await camera();
    await dialog.getByRole('button',{name:'Muro frontal',exact:true}).click();
    assert.equal(await dialog.getByRole('button',{name:'Muro frontal',exact:true}).getAttribute('aria-pressed'),'true');
    assert(Number(await steel.getAttribute('stroke-opacity'))<.5);
    const selectedCamera=await camera();
    assert.deepEqual(selectedCamera.target,[0,0,3.25],'Selection supplies the orbit pivot');
    for(const key of ['yaw','pitch','zoom','scale'])near(selectedCamera[key],beforeSelection[key],`Selection preserves ${key}`);
    const beforeHide=await steel.getAttribute('points');
    await dialog.getByRole('checkbox',{name:'Mostrar Muro frontal',exact:true}).uncheck();
    assert.equal(await drawing.locator('polygon[data-element="abutment.front_wall"]').count(),0);
    assert.equal(await steel.getAttribute('points'),beforeHide,'Hiding an element must not recenter or resize the remainder');
    assert.deepEqual(await camera(),selectedCamera);
    await dialog.getByRole('checkbox',{name:'Mostrar Fundación',exact:true}).uncheck();
    await drawing.getByText('No hay elementos visibles con geometría disponible.').waitFor();
    await dialog.getByRole('button',{name:'Ver conjunto',exact:true}).click();
    assert.equal(await steel.count(),1);
    assert(await dialog.getByRole('checkbox',{name:'Mostrar Fundación',exact:true}).isChecked());
    assert.equal(await dialog.getByRole('button',{name:'Muro frontal',exact:true}).getAttribute('aria-pressed'),'false');
    await dialog.getByRole('checkbox',{name:'Mostrar armaduras',exact:true}).uncheck();
    assert.equal(await steel.count(),0);
    await dialog.getByRole('checkbox',{name:'Mostrar armaduras',exact:true}).check();
    assert.equal(await steel.count(),1);
    await dialog.getByRole('slider',{name:'Intensidad del moldaje',exact:true}).fill('0');
    assert.equal(await drawing.locator('[data-layer="moldajes"] polygon').first().getAttribute('fill-opacity'),'0');
    assert.equal(await steel.getAttribute('stroke-opacity'),'0.92');
    await dialog.getByRole('slider',{name:'Intensidad del moldaje',exact:true}).fill('8');
    await dialog.locator('summary').click();
    await dialog.getByText('Armadura de muros pendiente.',{exact:true}).waitFor();

    // Cadence navigation: middle pan, Shift + middle orbit, no left/right camera drag.
    await dialog.getByRole('button',{name:'Isométrica',exact:true}).click();
    await drag(55,20,{button:'left'});assert.deepEqual(await camera(),originalCamera);
    await drag(55,20,{button:'right'});assert.deepEqual(await camera(),originalCamera);
    await drag(85,25,{shift:true});
    const orbited=await camera();
    assert.notEqual(orbited.yaw,originalCamera.yaw);assert.notEqual(orbited.pitch,originalCamera.pitch);
    near(orbited.scale,originalCamera.scale,'Orbit preserves scale');near(orbited.zoom,originalCamera.zoom,'Orbit preserves zoom');
    assert.deepEqual(orbited.target,originalCamera.target,'Orbit preserves pivot');await vertical();
    const beforePan=await screenPoints();
    await drag(65,-35);
    const panned=await camera(),afterPan=await screenPoints();
    for(const key of ['yaw','pitch','zoom','scale'])near(panned[key],orbited[key],`Pan preserves ${key}`);
    assert.notDeepEqual(panned.target,orbited.target);
    for(let i=0;i<beforePan.length;i++){
      near(afterPan[i][0]-beforePan[i][0],65,'Pan follows horizontal pixels',1e-3);
      near(afterPan[i][1]-beforePan[i][1],-35,'Pan follows vertical pixels',1e-3);
    }
    await vertical();
    await dialog.getByRole('button',{name:'Ajustar',exact:true}).click();
    const fitted=await camera();
    near(fitted.yaw,orbited.yaw,'Fit preserves azimuth');near(fitted.pitch,orbited.pitch,'Fit preserves elevation');
    assert.deepEqual(fitted.target,originalCamera.target,'Fit restores the visible model center');
    await dialog.getByRole('button',{name:'Isométrica',exact:true}).click();
    assert.deepEqual(await camera(),originalCamera);assert.equal(await steel.getAttribute('points'),originalPoints);

    // Zoom stays anchored to the pointer even in the SVG letterboxed viewport.
    const anchor=(await screenPoints())[0],beforeZoom=await camera();
    await drawing.evaluate(el=>el.addEventListener('wheel',event=>{window.fixture.lastWheel=[event.clientX,event.clientY];},{once:true}));
    await page.mouse.move(...anchor);await page.mouse.wheel(0,-100);
    await page.waitForFunction(zoom=>Number(document.querySelector('.iso-viewport svg').dataset.zoom)>zoom,beforeZoom.zoom);
    const zoomed=await camera(),zoomAnchor=(await screenPoints())[0];
    near(zoomed.zoom/beforeZoom.zoom,1.2,'Wheel step matches Cadence');
    const cursor=await page.evaluate(()=>fixture.lastWheel);
    for(let i=0;i<2;i++)near(zoomAnchor[i],cursor[i]+(anchor[i]-cursor[i])*1.2,'Cursor zoom anchor',1e-3);
    await page.mouse.wheel(0,100);await page.waitForFunction(zoom=>Number(document.querySelector('.iso-viewport svg').dataset.zoom)<zoom,zoomed.zoom);
    near((await camera()).zoom,beforeZoom.zoom,'Opposite wheel step reverses zoom');

    // Large vertical drags stop short of both poles and never roll the model.
    await drag(0,3000,{shift:true});near((await camera()).pitch,Math.PI/2-.01,'Upper orbit limit');await vertical();
    await drag(0,-6000,{shift:true});near((await camera()).pitch,-Math.PI/2+.01,'Lower orbit limit');await vertical();
    await dialog.getByRole('button',{name:'Isométrica',exact:true}).click();
    await drawing.focus();
    for(let i=0;i<10;i++){await page.keyboard.press('ArrowRight');await vertical();}
    near((await camera()).scale,originalCamera.scale,'Repeated azimuth turns do not reframe');

    // Cancellation ends the gesture; later mouse motion cannot keep rotating.
    await dialog.getByRole('button',{name:'Isométrica',exact:true}).click();
    const box=await drawing.boundingBox(),cx=box.x+box.width/2,cy=box.y+box.height/2;
    await page.keyboard.down('Shift');
    try{
      await page.mouse.move(cx,cy);await page.mouse.down({button:'middle'});await page.mouse.move(cx+30,cy+15);
      await drawing.dispatchEvent('pointercancel',{pointerId:1,pointerType:'mouse',button:1});
      const cancelled=await camera();await page.mouse.move(cx+90,cy+60);await page.mouse.up({button:'middle'});
      assert.deepEqual(await camera(),cancelled,'Cancelled orbit must release the gesture');
    }finally{await page.keyboard.up('Shift');}

    // Touch uses one-finger pan and two-finger pan/zoom without changing orientation.
    await dialog.getByRole('button',{name:'Isométrica',exact:true}).click();
    const touch=await page.context().newCDPSession(page),touchStart=await camera();
    await touch.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:cx,y:cy,id:0}]});
    await touch.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:cx+45,y:cy+20,id:0}]});
    await touch.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    const oneFinger=await camera();assert.notDeepEqual(oneFinger.target,touchStart.target);
    for(const key of ['yaw','pitch','zoom','scale'])near(oneFinger[key],touchStart[key],`One finger preserves ${key}`);
    await touch.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:cx-45,y:cy,id:0},{x:cx+45,y:cy,id:1}]});
    await touch.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:cx-70,y:cy+20,id:0},{x:cx+90,y:cy+20,id:1}]});
    await touch.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    const twoFingers=await camera();assert(twoFingers.zoom>oneFinger.zoom);
    near(twoFingers.yaw,oneFinger.yaw,'Touch pinch preserves azimuth');near(twoFingers.pitch,oneFinger.pitch,'Touch pinch preserves elevation');
    await touch.detach();
    await dialog.getByRole('button',{name:'Isométrica',exact:true}).click();
    const screenshot=process.env.SINCAL_ISOMETRIC_UI_SCREENSHOT||path.resolve(__dirname,'../tmp/isometric-ui.png');
    fs.mkdirSync(path.dirname(screenshot),{recursive:true});await dialog.screenshot({path:screenshot});
    await page.setViewportSize({width:440,height:950});
    assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await dialog.screenshot({path:screenshot.replace(/\.png$/,'-narrow.png')});
    await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
    assert.equal(await page.locator('#open').evaluate(el=>document.activeElement===el),true);
    await page.setViewportSize({width:1360,height:900});

    // A slow response to a closed viewer cannot overwrite a newly opened instance.
    await page.evaluate(()=>{fixture.delayNext=650;fixture.open('entrada');});
    await dialog.getByText('Preparando moldajes y armaduras…',{exact:true}).waitFor();
    await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();
    await dialog.waitFor({state:'detached'});
    await page.evaluate(()=>{fixture.open('salida','abutment.front_wall');});
    await dialog.getByRole('heading',{name:'Estribo de salida · Isométrica',exact:true}).waitFor();
    await drawing.waitFor();
    assert.equal(await dialog.getByRole('button',{name:'Muro frontal',exact:true}).getAttribute('aria-pressed'),'true');
    await page.waitForTimeout(700);
    assert.equal(await page.getByRole('dialog').count(),1);
    assert.equal(await dialog.getByRole('heading',{name:'Estribo de salida · Isométrica',exact:true}).count(),1);
    assert.equal(await page.evaluate(()=>fixture.calls.at(-1).payload.instance_key),'salida');
    assert.equal(await page.evaluate(()=>fixture.calls.at(-1).payload.state.custom),'salida');
    await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await dialog.waitFor({state:'detached'});

    // Leaving the source page or replacing its JSON closes the viewer.
    await page.evaluate(()=>{fixture.open();});await drawing.waitFor();
    await page.evaluate(()=>{fixture.current=false;});await dialog.waitFor({state:'detached'});
    await page.evaluate(()=>{fixture.current=true;fixture.open();});await drawing.waitFor();
    await page.evaluate(()=>{fixture.project.data=structuredClone(fixture.project.data);});await dialog.waitFor({state:'detached'});

    // Failed scene requests can be retried without changing any project value.
    await page.evaluate(()=>{fixture.errorNext=true;fixture.open();});
    await dialog.getByText('No se pudo preparar la isométrica. Escena de prueba no disponible',{exact:true}).waitFor();
    await dialog.getByRole('button',{name:'Volver a intentar',exact:true}).click();await drawing.waitFor();
    await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});

    // Every physical piece and every sampled bend is rendered independently;
    // the viewer must not collapse laps into a single straight family axis.
    await page.evaluate(()=>{
      const points=[[-3.8,-1.8,.8],[-3.8,-1.8,.266],[-3.7807,-1.8,.2193],[-3.734,-1.8,.2],[3.2,-1.8,.2]];
      const families=['mesh_x','mesh_y','suple','lateral_x','lateral_y'];
      fixture.scene.reinforcement_note='Piezas de zapata con ganchos, radios y empalmes, compartidas con CAD y despiece.';
      fixture.scene.bars=families.map((key,i)=>({id:`${key}:0`,key,placement_id:key,label:`Familia ${i+1}`,element_key:'abutment.footing',
        mark:String(i+1),diameter_mm:22,piece_role:'inicial',length_cm:1200,bend_radius_cm:6.6,lap_cm:150,
        points:points.map(p=>[p[0],p[1]+i*.2,p[2]])}));
      fixture.scene.bars.push({...fixture.scene.bars[0],id:'mesh_x:1',mark:'2',piece_role:'terminal',length_cm:475,
        points:[[1.7,-1.778,.2],[3.734,-1.778,.2],[3.7807,-1.778,.2193],[3.8,-1.778,.266],[3.8,-1.778,.8]],
        lap_segments:[[[1.7,-1.778,.2],[3.2,-1.778,.2]]],
        lap_partners:[{piece_id:'mesh_x:0',axis_distance_m:.022,segment:[[1.7,-1.8,.2],[3.2,-1.8,.2]]}]});
      fixture.open();
    });
    await drawing.waitFor();
    const completeSteel=drawing.locator('[data-layer="armaduras"] polyline');
    assert.equal(await completeSteel.count(),6);
    assert.equal(new Set(await completeSteel.evaluateAll(lines=>lines.map(el=>el.dataset.family))).size,5);
    assert(await completeSteel.evaluateAll(lines=>lines.every(el=>el.points.numberOfItems===5)));
    const initialTitle=await drawing.locator('[data-piece="mesh_x:0"] title').textContent();
    for(const text of ['Marca 1','Pieza inicial','L=1.200 cm','Radio 6,6 cm','Traslapo 150 cm'])assert(initialTitle.includes(text),initialTitle);
    const terminalTitle=await drawing.locator('[data-piece="mesh_x:1"] title').textContent();
    assert(terminalTitle.includes('Pieza terminal')&&terminalTitle.includes('L=475 cm'));
    const lap=drawing.locator('line[data-lap]');
    assert.equal(await lap.count(),1);
    assert.equal(Number(await lap.getAttribute('stroke-width')),Number(await completeSteel.first().getAttribute('stroke-width')));
    assert(await lap.evaluate(el=>{
      const terminal=document.querySelector('[data-piece="mesh_x:1"]').getAttribute('points').split(' ').map(value=>{const [x,y]=value.split(',').map(Number);return {x,y};});
      const a=terminal[0],b=terminal[1];
      const cross=(x,y)=>(x-a.x)*(b.y-a.y)-(y-a.y)*(b.x-a.x);
      return Math.abs(cross(Number(el.getAttribute('x1')),Number(el.getAttribute('y1'))))<1e-6&&Math.abs(cross(Number(el.getAttribute('x2')),Number(el.getAttribute('y2'))))<1e-6;
    }),'The lap interval stays on its physical continuation axis without thickening');
    assert.equal(await dialog.getByText('Piezas de zapata con ganchos, radios y empalmes, compartidas con CAD y despiece.',{exact:true}).count(),0);
    assert.equal(await dialog.locator('.iso-legend,.iso-stage .iso-note').count(),0);
    assert.equal(await dialog.getByText('La vista no representa todavía',{exact:false}).count(),0);
    const mark1=dialog.getByRole('button',{name:'Mostrar marca 1 · Fundación',exact:true});
    const mark2=dialog.getByRole('button',{name:'Mostrar marca 2 · Fundación',exact:true});
    assert.equal(await mark1.getAttribute('aria-pressed'),'true');
    const elementBox=await dialog.getByRole('button',{name:'Fundación',exact:true}).boundingBox(),markBox=await mark1.boundingBox();
    assert(markBox.x>elementBox.x+elementBox.width,'Marks sit to the right of their element');
    const beforeFilter=await camera();
    await mark1.click();assert.equal(await drawing.locator('polyline[data-mark="1"]').count(),0);assert.equal(await lap.count(),0);
    assert.equal(await completeSteel.count(),5);assert.deepEqual(await camera(),beforeFilter,'Filtering a mark preserves camera');
    await mark1.click();assert.equal(await lap.count(),1);
    await mark2.click();assert.equal(await drawing.locator('polyline[data-mark="2"]').count(),0);assert.equal(await lap.count(),0);
    await dialog.getByRole('checkbox',{name:'Mostrar armaduras',exact:true}).uncheck();assert.equal(await completeSteel.count(),0);
    await dialog.getByRole('checkbox',{name:'Mostrar armaduras',exact:true}).check();
    assert.equal(await mark2.getAttribute('aria-pressed'),'false');assert.equal(await drawing.locator('polyline[data-mark="2"]').count(),0);
    await mark2.click();assert.equal(await lap.count(),1);
    // A lit mark means its steel is actually visible, including the element
    // and global switches. Clicking a hidden mark restores those switches.
    await dialog.getByRole('checkbox',{name:'Mostrar Fundación',exact:true}).uncheck();
    assert.equal(await mark1.getAttribute('aria-pressed'),'false');
    assert.equal(await mark1.getAttribute('data-visible'),'false');
    await mark1.click();
    assert(await dialog.getByRole('checkbox',{name:'Mostrar Fundación',exact:true}).isChecked());
    assert.equal(await mark1.getAttribute('aria-pressed'),'true');assert.equal(await lap.count(),1);
    await dialog.getByRole('checkbox',{name:'Mostrar armaduras',exact:true}).uncheck();
    assert.equal(await mark1.getAttribute('aria-pressed'),'false');
    await mark1.click();
    assert(await dialog.getByRole('checkbox',{name:'Mostrar armaduras',exact:true}).isChecked());
    assert.equal(await mark1.getAttribute('aria-pressed'),'true');assert.equal(await lap.count(),1);
    await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});

    // Filters live only in the expanded view. Closing it returns their state
    // and camera to the compact preview, including temporarily absent marks.
    await page.evaluate(()=>fixture.mount());
    const inline=page.getByRole('region',{name:'Vista isométrica del estribo'}),inlineDrawing=inline.getByRole('img');
    assert.equal(await inline.locator('details,aside,.iso-mark,.iso-legend').count(),0);
    await inline.getByRole('button',{name:'Acercar',exact:true}).click();
    const beforeExpand=await inlineDrawing.evaluate(el=>({zoom:el.dataset.zoom,target:el.dataset.target}));
    await inline.getByRole('button',{name:'Ampliar visor',exact:true}).click();await drawing.waitFor();
    assert.deepEqual(await drawing.evaluate(el=>({zoom:el.dataset.zoom,target:el.dataset.target})),beforeExpand);
    await mark1.click();await dialog.getByRole('button',{name:'Acercar',exact:true}).click();
    const inlineCamera=await drawing.evaluate(el=>({zoom:el.dataset.zoom,target:el.dataset.target}));
    await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();
    // A closed dialog leaves the accessibility tree before its native close
    // event returns the view state; wait for removal from the DOM as well.
    await page.locator('dialog.rebar-isometric').waitFor({state:'detached'});
    assert.deepEqual(await inlineDrawing.evaluate(el=>({zoom:el.dataset.zoom,target:el.dataset.target})),inlineCamera);
    assert.equal(await inlineDrawing.locator('polyline[data-mark="1"]').count(),0);
    await page.evaluate(()=>{fixture.savedBars=fixture.scene.bars;fixture.scene.bars=[];fixture.inline.update();});
    await inline.getByRole('status').filter({hasText:'Sin armadura representable con los parámetros actuales.'}).waitFor();
    await page.evaluate(()=>{
      fixture.scene.bars=[...fixture.savedBars,{...fixture.savedBars[0],id:'wall:0',placement_id:'wall',element_key:'abutment.front_wall'}];fixture.inline.update();
    });
    await inlineDrawing.locator('polyline[data-mark="1"][data-element="abutment.front_wall"]').waitFor();
    assert.equal(await inlineDrawing.locator('polyline[data-mark="1"][data-element="abutment.footing"]').count(),0);
    assert.equal(await inlineDrawing.locator('polyline[data-mark="1"][data-element="abutment.front_wall"]').count(),1,'Same mark in another element has an independent filter');
    assert.deepEqual(await inlineDrawing.evaluate(el=>({zoom:el.dataset.zoom,target:el.dataset.target})),inlineCamera);
    await inline.getByRole('button',{name:'Ampliar visor',exact:true}).click();await drawing.waitFor();
    assert.equal(await dialog.getByRole('button',{name:'Mostrar marca 1 · Fundación',exact:true}).getAttribute('aria-pressed'),'false');
    assert.equal(await drawing.locator('polyline[data-mark="1"][data-element="abutment.footing"]').count(),0);
    assert.equal(await drawing.locator('polyline[data-mark="1"][data-element="abutment.front_wall"]').count(),1);
    assert.deepEqual(await drawing.evaluate(el=>({zoom:el.dataset.zoom,target:el.dataset.target})),inlineCamera);
    await dialog.screenshot({path:path.resolve(__dirname,'../tmp/isometric-mark-controls.png')});
    await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
    await page.evaluate(()=>fixture.inline.dispose());
    assert.deepEqual(await page.evaluate(()=>fixture.errors),['Escena de prueba no disponible']);
    assert.deepEqual(await page.evaluate(()=>fixture.project),initial);
    assert.equal(await page.evaluate(()=>fixture.changes),0);
    assert(await page.evaluate(()=>fixture.calls.every(call=>call.route==='rebar/abutment/scene')));
    assert.deepEqual(errors,[]);
    console.log('OK: visor isométrico accesible y responsive; navegación Cadence, Z vertical, zoom 0.1–40 al cursor sin botones Girar; piezas, curvas y empalmes sólo entre barras visibles; marcas junto a elementos, filtros independientes persistentes al actualizar/ampliar; cierre, errores e instancias aisladas; sin CAD ni mutaciones del proyecto.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
