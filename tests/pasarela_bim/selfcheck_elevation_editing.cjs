// All interactions use a fresh, isolated browser page. Never attach to the user's editor.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('http://pasarela.test/**',route=>{
   const pathname=new URL(route.request().url()).pathname;
   if(pathname.startsWith('/api/'))return route.fulfill({json:pathname==='/api/estado'?{guardado_local:true,freecad_disponible:false}:{valido:true,generable:false,errores:[],avisos:[],pendientes:[]}});
   return route.fulfill({path:path.resolve('pasarela_bim/web',pathname==='/'?'index.html':pathname.slice(1))});
  });
  const model={version:1,proyecto:{id:'editing',nombre:'Edición desde elevaciones',unidades:'mm'},
   nodos:[{id:'C1',tipo:'columna',x:0,y:0,z:0},{id:'C2',tipo:'columna',x:10000,y:0,z:-680},{id:'E1',tipo:'estribo',x:10000,y:10000,z:-1480},{id:'D',tipo:'encuentro',x:50000,y:0,z:0},{id:'E',tipo:'encuentro',x:82500,y:0,z:0}],
   tramos:[{id:'V1',tipo:'viga',funcion:'rampa',desde:'C1',hasta:'C2',familia:'box',ancho_mm:2000,descanso_central_mm:1500},{id:'V2',tipo:'viga',funcion:'rampa',desde:'E1',hasta:'C2',familia:'box',ancho_mm:2000,retranqueo_inicio_mm:200,retranqueo_fin_mm:400},{id:'V3',tipo:'viga',funcion:'cruce',desde:'D',hasta:'E',familia:'box',ancho_mm:2000}],
   familias:{box:{tipo:'cajon',canto_mm:1000,ancho_alma_superior_mm:1260,ancho_inferior_mm:1000,losa_superior_mm:150,losa_inferior_mm:140,alma_mm:140,macizado_mm:500}},
   soportes:[{id:'C1',nodo:'C1',fundacion:'F1',diametro_mm:1000,cota_superior_mm:-1500,cota_terreno_proyectado_mm:-5000},{id:'C2',nodo:'C2',fundacion:'F2',diametro_mm:1000,cota_superior_mm:-2300,cota_terreno_proyectado_mm:-5100},{id:'E1',nodo:'E1',fundacion:'F3',largo_mm:1200,ancho_mm:1600,cota_superior_mm:-3100}],
   fundaciones:['C1','C2','E1'].map((id,i)=>({id:'F'+(i+1),nodos:[id],largo_mm:3000,ancho_mm:3000,alto_mm:1000,cota_superior_mm:-6000,pilotes:i===0?[{id:'P1',dx_mm:0,dy_mm:0,diametro_mm:1200,longitud_mm:8000}]:[]})),
   ejes:[{id:'ER1',tipo:'recorrido',nombre:'Acceso con descanso',tramos:['V1','V2']},{id:'EA1',tipo:'atravieso',nombre:'Atravieso',tramos:['V3']},...['C1','C2','E1'].map((id,i)=>({id:'EC'+(i+1),tipo:'apoyo',nodo:id}))]};
  await page.goto('http://pasarela.test/');
  await page.locator('#file-input').setInputFiles({name:'edicion-elevacion.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(model))});
  await page.locator('#entity-list [data-select-id="C1"]').first().waitFor();
  await page.locator('#view-elevation').click();
  const group=(kind,id)=>page.locator(`#scene .elevation-${kind}[data-select-id="${id}"]`).first();
  const dirty=()=>page.evaluate(()=>PasarelaIntegration.snapshot().dirty);
  const viewport=()=>page.locator('#model-canvas').getAttribute('viewBox');
  const dimensionValues=kind=>page.locator(`[data-dimension-kind="${kind}"]`).evaluateAll(items=>items.map(el=>Number(el.getAttribute('data-value-mm'))));
  const selected=async(type,id,axis='ER1')=>{
   assert.equal(await page.locator('#inspector [data-field="id"]').inputValue(),id,`El panel debe editar ${id}.`);
   assert.equal(await page.locator('#elevation-axis').inputValue(),axis,'Seleccionar no debe cambiar el eje mostrado.');
   assert(await page.locator('#view-elevation').getAttribute('class').then(value=>value.includes('active')));
   assert(await page.locator(`#scene .elevation-selectable.selected[data-select-type="${type}"][data-select-id="${id}"]`).count()>0,'La selección debe destacarse en la elevación.');
  };
  // Locate a real screen point in the hollow section, not in the concrete or an overlay.
  const clickHollow=async id=>{
   const point=await group('edge',id).evaluate(wrapper=>{
    const shape=wrapper.querySelector('.beam-longitudinal-cut'),hit=wrapper.querySelector('path.elevation-hit-area'),box=shape.getBBox(),matrix=shape.getScreenCTM();
    for(let ix=2;ix<=8;ix++)for(let iy=1;iy<=9;iy++){
     const local=new DOMPoint(box.x+box.width*ix/10,box.y+box.height*iy/10),screen=local.matrixTransform(matrix);
     if(hit.isPointInFill(local)&&!shape.isPointInFill(local)&&document.elementFromPoint(screen.x,screen.y)?.closest('.elevation-selectable')===wrapper)return{x:screen.x,y:screen.y};
    }
    throw new Error('No se encontró un punto de clic en el hueco central de la viga.');
   });
   await page.mouse.click(point.x,point.y);
  };
  // Text itself has pointer-events:none; the surrounding hit target must remain clickable.
  const clickLabel=async(kind,id)=>{
   const box=await group(kind,id).locator('text').first().boundingBox();
   assert(box&&box.width>0);await page.mouse.click(box.x+box.width/2,box.y+box.height/2);
  };
  const clickGeometry=async(kind,id,selector)=>{
   const point=await group(kind,id).locator(selector).first().evaluate(shape=>{
    const wrapper=shape.closest('.elevation-selectable'),box=shape.getBBox(),matrix=shape.getScreenCTM();
    for(const xf of [.5,.25,.75,.1,.9])for(const yf of [.5,.25,.75,.1,.9]){
     const local=new DOMPoint(box.x+box.width*xf,box.y+box.height*yf),screen=local.matrixTransform(matrix);
     const target=document.elementFromPoint(screen.x,screen.y)?.closest('.elevation-selectable');
     if(shape.isPointInFill(local)&&target?.dataset.selectType===wrapper.dataset.selectType&&target.dataset.selectId===wrapper.dataset.selectId&&target.dataset.selectPileId===wrapper.dataset.selectPileId)return{x:screen.x,y:screen.y};
    }
    const center=new DOMPoint(box.x+box.width/2,box.y+box.height/2).matrixTransform(matrix),target=document.elementFromPoint(center.x,center.y);
    throw new Error(`No se encontró una porción visible de ${shape.getAttribute('class')}: ${shape.getAttribute('points')}. Centro: ${target?.outerHTML.slice(0,200)}`);
   });
   await page.mouse.click(point.x,point.y);
  };
  const editField=async(field,value)=>{const input=page.locator(`#inspector [data-field="${field}"]`);await input.fill(value);await input.press('Tab');};

  const initialView=await viewport();
  await clickHollow('V1');await selected('edge','V1');assert.equal(await viewport(),initialView,'Un clic en una viga no debe desplazar la vista.');
  await clickLabel('edge','V2');await selected('edge','V2');assert.equal(await viewport(),initialView);
  await clickGeometry('support','C1','.support-longitudinal-cut');await selected('node','C1');
  await clickGeometry('capital','C2','.capital-elevation');await selected('node','C2');
  await clickGeometry('support','E1','.support-longitudinal-cut');await selected('node','E1');assert.equal(await page.locator('#inspector [data-field="tipo"]').inputValue(),'estribo');
  await clickGeometry('foundation','F1','.foundation-longitudinal-cut');await selected('foundation','F1');assert.equal(await page.locator('#selection-kind').textContent(),'DADO');
  await clickGeometry('foundation','F2','.foundation-longitudinal-cut');await selected('foundation','F2');assert.equal(await page.locator('#selection-kind').textContent(),'FUNDACIÓN');
  await clickGeometry('pile','F1','.pile-longitudinal-cut');await selected('foundation','F1');
  assert(await page.locator('#inspector [data-pile-id="P1"].selected-pile').count()===1,'Seleccionar el pilote debe localizar su sección del panel.');
  await clickLabel('node','C2');await selected('node','C2');
  await clickGeometry('axis','EC1','circle');await selected('axis','EC1');
  await group('edge','V2').focus();await page.keyboard.press('Enter');await selected('edge','V2');
  assert(await group('edge','V2').evaluate(el=>document.activeElement===el),'La selección con teclado debe conservar el foco.');
  await group('axis','EC2').focus();await page.keyboard.press('Space');await selected('axis','EC2');
  assert.equal(await dirty(),false,'Seleccionar geometría, rótulos o ejes no debe marcar cambios sin guardar.');

  // Unsupported nodes are still selectable, and retain the normal node editing workflow.
  await page.locator('#elevation-axis').selectOption('EA1');
  await clickGeometry('node','D','.elevation-node-marker');await selected('node','D','EA1');
  assert(await page.locator('#inspector [data-field="z"]').isEditable());
  assert(await page.locator('#inspector [data-action="create-support"]').isVisible());
  await page.locator('#elevation-axis').selectOption('ER1');
  assert.equal(await dirty(),false);

  // The middle mouse button pans; dimension labels and arrowheads do not intercept shapes.
  assert.equal(await page.locator('.elevation-dimensions').evaluate(el=>getComputedStyle(el).pointerEvents),'none');
  const background=await page.locator('#model-canvas').evaluate(canvas=>{
   const box=canvas.getBoundingClientRect();
   for(let y=box.top+35;y<box.bottom-35;y+=30)for(let x=box.left+35;x<box.right-35;x+=30){
    const target=document.elementFromPoint(x,y);
    if(target&&canvas.contains(target)&&!target.closest('.elevation-selectable'))return{x,y};
   }
   throw new Error('No se encontró fondo libre para comprobar el desplazamiento.');
  });
  const beforePan=await viewport();await page.mouse.move(background.x,background.y);await page.mouse.down({button:'middle'});await page.mouse.move(background.x+30,background.y+20,{steps:4});await page.mouse.up({button:'middle'});
  assert.notEqual(await viewport(),beforePan,'El botón central debe permitir desplazar la elevación.');
  await page.locator('#fit').click();
  await page.locator('#show-elevation-dimensions').uncheck();await clickHollow('V1');await selected('edge','V1');
  await page.locator('#show-elevation-dimensions').check();assert.equal(await dirty(),false);

  // Each edit uses the existing inspector and updates the model-derived cut and dimensions.
  const originalCut=await group('edge','V1').locator('.beam-longitudinal-cut').getAttribute('d');
  const depth=page.locator('#inspector [data-section-field="canto_mm"]');await depth.fill('1.1');
  await page.locator('#inspector [data-section-action="apply"]').click();await selected('edge','V1');
  assert((await dimensionValues('beam-height')).some(value=>Math.abs(value-1220)<1e-6));
  assert.notEqual(await group('edge','V1').locator('.beam-longitudinal-cut').getAttribute('d'),originalCut);
  assert.equal(await dirty(),true,'Una edición sí debe marcar el proyecto como modificado.');
  await page.locator('#undo').click();assert.equal(await group('edge','V1').locator('.beam-longitudinal-cut').getAttribute('d'),originalCut,'Deshacer debe restaurar la geometría.');
  await clickHollow('V1');await editField('retranqueo_inicio_mm','0.25');await selected('edge','V1');
  assert.notEqual(await group('edge','V1').locator('.beam-longitudinal-cut').getAttribute('d'),originalCut);

  await clickGeometry('support','C1','.support-longitudinal-cut');await editField('support:0:height','5');await selected('node','C1');
  assert((await dimensionValues('support-height')).includes(5000));
  await clickGeometry('support','E1','.support-longitudinal-cut');
  const oldAbutment=await group('support','E1').locator('.support-longitudinal-cut').getAttribute('points');
  await editField('support:0:ancho_mm','2');await selected('node','E1');
  assert.notEqual(await group('support','E1').locator('.support-longitudinal-cut').getAttribute('points'),oldAbutment);
  await clickGeometry('foundation','F2','.foundation-longitudinal-cut');await editField('alto_mm','1.25');await selected('foundation','F2');
  assert((await dimensionValues('foundation-thickness')).includes(1250));
  await clickGeometry('pile','F1','.pile-longitudinal-cut');
  await page.locator('#inspector [data-pile-id="P1"] [data-action="edit-pile"]').click();
  await page.locator('dialog[open] [name="longitud"]').fill('9');await page.locator('dialog[open] button[type="submit"]').click();
  await selected('foundation','F1');assert((await dimensionValues('pile-length')).includes(9000));
  assert.equal(await page.locator('dialog[open]').count(),0);
  await page.locator('#fit').click();fs.mkdirSync('tmp',{recursive:true});
  await page.screenshot({path:'tmp/edicion-elevacion-eje.png'});
  assert.deepEqual(errors,[]);
  console.log('Axis elevation editing UI: real clicks in hollow beams and labels, supports, caps, foundations, piles, free nodes, keyboard selection, unchanged view, clean selection, panning, undo and live edits passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
