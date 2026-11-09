// Exercise the real editor in a private browser; never attach to the user's open module.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100},hasTouch:true}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://pasarela.test/**',route=>{
   const pathname=new URL(route.request().url()).pathname;
   if(pathname.startsWith('/api/'))return route.fulfill({json:pathname==='/api/estado'?{guardado_local:true,freecad_disponible:false}:{valido:true,generable:false,errores:[],avisos:[],pendientes:[]}});
   const file=path.resolve('pasarela_bim/web',pathname==='/'?'index.html':pathname.slice(1));
   return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404,body:''});
  });
  const model={version:1,proyecto:{id:'navigation',nombre:'Navegación como Cadence',unidades:'mm',georreferencia:{este_m:187606,norte_m:2923164,cota_m:14.818,norte_desde_y_horario_deg:276}},
   nodos:[{id:'C1',tipo:'columna',x:-12000,y:0,z:0},{id:'C2',tipo:'columna',x:12000,y:0,z:0},{id:'N1',tipo:'encuentro',x:-12000,y:10000,z:-800},{id:'N2',tipo:'encuentro',x:12000,y:-10000,z:-800}],
   tramos:[{id:'V1',tipo:'viga',funcion:'cruce',desde:'C1',hasta:'C2',familia:'box',ancho_mm:2000},{id:'V2',tipo:'viga',funcion:'rampa',desde:'C1',hasta:'N1',familia:'box',ancho_mm:2000},{id:'V3',tipo:'viga',funcion:'rampa',desde:'C2',hasta:'N2',familia:'box',ancho_mm:2000}],
   familias:{box:{tipo:'cajon',canto_mm:1000,ancho_alma_superior_mm:1260,ancho_inferior_mm:1000,losa_superior_mm:150,losa_inferior_mm:140,alma_mm:140,macizado_mm:500}},
   soportes:['C1','C2'].map((id,i)=>({id,nodo:id,fundacion:'F'+(i+1),diametro_mm:1000,cota_superior_mm:-1500,cota_terreno_proyectado_mm:-5500})),
   fundaciones:['C1','C2'].map((id,i)=>({id:'F'+(i+1),nodos:[id],largo_mm:3000,ancho_mm:3000,alto_mm:1000,cota_superior_mm:-6000,pilotes:[]})),
   ejes:[{id:'EA1',tipo:'atravieso',nombre:'Atravieso',tramos:['V1']},{id:'ER1',tipo:'recorrido',nombre:'Acceso',tramos:['V2']},{id:'EC1',tipo:'apoyo',nodo:'C1'},{id:'EC2',tipo:'apoyo',nodo:'C2'}]};
  await page.goto('http://pasarela.test/');
  await page.locator('#file-input').setInputFiles({name:'navegacion.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(model))});
  await page.locator('#entity-list [data-select-id="C1"]').first().waitFor();
  await page.locator('#view-iso').click();
  const canvas=page.locator('#model-canvas'),north=()=>page.locator('#north-symbol').innerHTML();
  const view=()=>canvas.getAttribute('viewBox').then(value=>value.split(/\s+/).map(Number));
  const markers=()=>page.locator('#scene .node-marker').evaluateAll(items=>items.map(el=>[Number(el.getAttribute('cx')??el.dataset.x),Number(el.getAttribute('cy')??el.dataset.y)]));
  const nodePoint=id=>page.locator(`#scene [data-select-type="node"][data-select-id="${id}"] .node-marker`).evaluate(el=>{
   const p=new DOMPoint(Number(el.getAttribute('cx')??el.dataset.x),Number(el.getAttribute('cy')??el.dataset.y)).matrixTransform(el.getScreenCTM());return{x:p.x,y:p.y};
  });
  const dirty=()=>page.evaluate(()=>PasarelaIntegration.snapshot().dirty);
  const inspector=()=>page.locator('#inspector [data-field="id"]').inputValue();
  const near=(a,b,epsilon=1e-6,message='Values must match')=>assert(Math.abs(a-b)<epsilon,`${message}: ${a} versus ${b}`);
  const samePoint=(a,b,message)=>{near(a.x,b.x,1e-3,message);near(a.y,b.y,1e-3,message);};
  const center=async()=>{const b=await canvas.boundingBox();return{x:b.x+b.width*.55,y:b.y+b.height*.5};};
  const drag=async({start,dx=90,dy=35,button='middle',modifier}={})=>{
   const p=start||await center();if(modifier)await page.keyboard.down(modifier);
   await page.mouse.move(p.x,p.y);await page.mouse.down({button});
   await page.mouse.move(p.x+dx,p.y+dy,{steps:8});await page.mouse.up({button});
   if(modifier)await page.keyboard.up(modifier);
  };
  const finiteGeometry=async()=>{
   const values=await canvas.evaluate(el=>({view:el.getAttribute('viewBox'),shapes:[...el.querySelectorAll('[points],[d],line,circle')].map(x=>[x.getAttribute('points'),x.getAttribute('d'),x.getAttribute('x1'),x.getAttribute('y1'),x.getAttribute('x2'),x.getAttribute('y2'),x.getAttribute('cx'),x.getAttribute('cy')].filter(Boolean).join(' '))}));
   assert(!JSON.stringify(values).match(/NaN|Infinity/),'Navigation must keep every shape and viewport finite.');
   assert((await view()).every(Number.isFinite));assert((await view()).slice(2).every(v=>v>0));
  };
  const defaultMarkers=await markers(),defaultView=await view();
  // Left input selects only. Dragging the empty background must not orbit or pan.
  await drag({button:'left'});assert.deepEqual(await markers(),defaultMarkers);assert.deepEqual(await view(),defaultView);
  const c2=await nodePoint('C2');await page.mouse.click(c2.x,c2.y);assert.equal(await inspector(),'C2');
  const afterSelection=await view();near(afterSelection[2],defaultView[2]);near(afterSelection[3],defaultView[3]);
  const oldNorth=await north(),oldMarkers=await markers(),beforePan=await view(),beforeNode=await nodePoint('C2');
  // Panning works even if the central button starts on an editable element.
  await drag({start:await nodePoint('C1'),dx:70,dy:30});
  assert.equal(await inspector(),'C2','Middle input must not select the object underneath.');
  assert.deepEqual(await markers(),oldMarkers,'Panning must not alter the projection.');assert.equal(await north(),oldNorth);
  assert.notDeepEqual(await view(),beforePan);const afterNode=await nodePoint('C2');near(afterNode.x-beforeNode.x,70,1e-4);near(afterNode.y-beforeNode.y,30,1e-4);
  // Selection sets the orbit pivot but keeps its screen position and the current zoom.
  // Panning moves the camera target too, so select the object again before testing its pivot.
  await page.mouse.click(afterNode.x,afterNode.y);
  const pivot=await nodePoint('C2'),preOrbit=await view();
  await drag({start:await nodePoint('C1'),modifier:'Shift',dx:95,dy:55});
  assert.notDeepEqual(await markers(),oldMarkers);assert.notEqual(await north(),oldNorth);assert.equal(await inspector(),'C2');
  samePoint(await nodePoint('C2'),pivot,'The selected orbit center must stay fixed');near((await view())[2],preOrbit[2]);near((await view())[3],preOrbit[3]);
  const supports=await page.locator('#scene > line').evaluateAll(lines=>lines.map(line=>({x1:Number(line.getAttribute('x1')),x2:Number(line.getAttribute('x2')),y1:Number(line.getAttribute('y1')),y2:Number(line.getAttribute('y2'))})));
  assert.equal(supports.length,2);for(const line of supports)near(line.x1,line.x2,1e-8,'Z must remain vertical');
  // A vertical-only orbit changes the apparent height, not the horizontal projection.
  const beforeVertical=await markers();await drag({modifier:'Shift',dx:0,dy:45});const afterVertical=await markers();
  beforeVertical.forEach((p,i)=>near(p[0],afterVertical[i][0],1e-6));assert(beforeVertical.some((p,i)=>Math.abs(p[1]-afterVertical[i][1])>1e-3));
  for(const modifier of ['Control','Meta']){const before=await markers();await drag({modifier,dx:35,dy:5});assert.notDeepEqual(await markers(),before,`${modifier}+middle must orbit.`);}
  // Large vertical movements reach bounded top/bottom angles, never a singular camera.
  await drag({modifier:'Shift',dx:0,dy:10000});await finiteGeometry();
  await drag({modifier:'Shift',dx:0,dy:-20000});await finiteGeometry();
  await page.locator('#fit').click();assert.deepEqual(await markers(),defaultMarkers,'Fit restores the default viewing angle.');
  // Fit clears a selected orbit center and reframes the complete model, not only that item.
  assert.deepEqual(await view(),defaultView);

  // Wheel zoom follows the cursor and is reciprocal, with the Cadence 1.2 factor per 100px.
  const b=await canvas.boundingBox(),cursor={x:Math.round(b.x+b.width*.7),y:Math.round(b.y+b.height*.4)};
  const localAtCursor=()=>canvas.evaluate((el,p)=>{const q=new DOMPoint(p.x,p.y).matrixTransform(el.getScreenCTM().inverse());return{x:q.x,y:q.y};},cursor);
  await page.mouse.move(cursor.x,cursor.y);const zoomBefore=await view(),anchor=await localAtCursor();
  await page.mouse.wheel(0,100);await page.waitForTimeout(60);const zoomOut=await view();near(zoomOut[2]/zoomBefore[2],1.2);near(zoomOut[3]/zoomBefore[3],1.2);samePoint(await localAtCursor(),anchor,'Wheel zoom must preserve the cursor anchor');
  await page.mouse.wheel(0,-100);await page.waitForTimeout(60);(await view()).forEach((v,i)=>near(v,zoomBefore[i],1e-4,'Reverse wheel must restore the viewport'));
  await page.mouse.wheel(0,50);await page.waitForTimeout(60);near((await view())[2]/zoomBefore[2],Math.sqrt(1.2));
  const stopped=await view();await page.waitForTimeout(180);assert.deepEqual(await view(),stopped,'Navigation must not continue moving after the wheel stops.');
  // A cancelled gesture releases capture and cannot leave an active pan behind.
  const cancelStart=await center();await page.mouse.move(cancelStart.x,cancelStart.y);await page.mouse.down({button:'middle'});
  await canvas.dispatchEvent('pointercancel',{pointerId:1,pointerType:'mouse',button:1});const cancelled=await view();
  await page.mouse.move(cancelStart.x+30,cancelStart.y+20);await page.mouse.up({button:'middle'});assert.deepEqual(await view(),cancelled);
  await drag({dx:20,dy:10});assert.notDeepEqual(await view(),cancelled,'A new gesture must work after cancellation.');
  await page.locator('#fit').click();

  // Genuine touch input: one finger pans; two fingers pinch without changing orientation.
  const cdp=await page.context().newCDPSession(page),touch=(type,points)=>cdp.send('Input.dispatchTouchEvent',{type,touchPoints:points.map((p,i)=>({x:p.x,y:p.y,id:i+1,radiusX:2,radiusY:2,force:1}))});
  const tc=await center(),touchMarkers=await markers(),touchView=await view();
  await touch('touchStart',[tc]);await touch('touchMove',[{x:tc.x+40,y:tc.y+25}]);await touch('touchEnd',[]);
  assert.notDeepEqual(await view(),touchView);assert.deepEqual(await markers(),touchMarkers);
  const pinchBefore=await view();await touch('touchStart',[{x:tc.x-40,y:tc.y},{x:tc.x+40,y:tc.y}]);
  await touch('touchMove',[{x:tc.x-70,y:tc.y-10},{x:tc.x+70,y:tc.y+10}]);await touch('touchEnd',[]);
  assert((await view())[2]<pinchBefore[2],'Separating two fingers must zoom in.');assert.deepEqual(await markers(),touchMarkers,'Touch gestures must not orbit.');
  await cdp.detach();

  // The same middle-button navigation applies to both flat projections; modifiers do not orbit.
  for(const flat of ['plan','elevation']){
   await page.locator('#view-'+flat).click();
   const shape=()=>page.locator('#scene').evaluate(el=>[...el.querySelectorAll('.node-marker,.beam-longitudinal-cut')].map(x=>[x.getAttribute('cx'),x.getAttribute('cy'),x.getAttribute('d'),x.getAttribute('points')]));
   const beforeShape=await shape(),beforeView=await view();await drag({modifier:'Shift',dx:35,dy:20});
   assert.deepEqual(await shape(),beforeShape,`${flat} must remain a flat projection.`);assert.notDeepEqual(await view(),beforeView);
  }
  await page.locator('#fit').click();
  const support=page.locator('.elevation-support[data-select-id="C1"] .support-longitudinal-cut');
  await support.click();assert.equal(await inspector(),'C1','Elevation editing must remain available with left click.');
  assert.equal(await dirty(),false,'Navigating and selecting must not modify the project.');
  await page.locator('#view-iso').click();await page.locator('#fit').click();await drag({modifier:'Shift',dx:65,dy:30});
  fs.mkdirSync('tmp',{recursive:true});await page.screenshot({path:'tmp/navegacion-cadence-pasarela.png'});
  assert.deepEqual(errors,[]);await finiteGeometry();
  console.log('Cadence navigation UI: modified middle orbit, Z vertical, selected pivot, middle pan over geometry, selection-only left input, cursor zoom factor/reciprocity, bounds, cancellation, touch pan/pinch, flat views, elevation editing and clean project passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
