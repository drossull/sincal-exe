// Exercise the real editor in a separate browser; never attach to the user's session.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const io=require('../../pasarela_bim/web/proyecto.js');

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  let savedModel;
  await page.route('http://pasarela.test/**',route=>{
   const pathname=new URL(route.request().url()).pathname;
   if(pathname==='/api/proyecto/guardar'){
    savedModel=route.request().postDataJSON().modelo;
    return route.fulfill({json:{guardado:true,documento:{id:'return-ui',nombre:'retorno.json',ruta:'C:/prueba/retorno.json'}}});
   }
   if(pathname.startsWith('/api/'))return route.fulfill({json:pathname==='/api/estado'?{guardado_local:true,freecad_disponible:false}:{valido:true,generable:false,errores:[],avisos:[],pendientes:[]}});
   return route.fulfill({path:path.resolve('pasarela_bim/web',pathname==='/'?'index.html':pathname.slice(1))});
  });
  const dialog=()=>page.locator('dialog[open]');
  const select=async(type,id)=>page.locator(`#entity-list [data-select-type="${type}"][data-select-id="${id}"]`).click();
  const model=async()=>{
   const request=page.waitForRequest(r=>new URL(r.url()).pathname==='/api/validar'&&r.method()==='POST');
   await page.locator('#validate').click();return structuredClone((await request).postDataJSON());
  };
  const save=async()=>{
   const response=page.waitForResponse('**/api/proyecto/guardar');await page.locator('#export-json').click();await response;
   await page.waitForFunction(()=>document.querySelector('#export-json').textContent==='Guardar cambios');return structuredClone(savedModel);
  };
  const blank=()=>{const m=io.newProject({nombre:'Retornos editables'});m.nodos=[{id:'N1',uuid:'start-node',tipo:'encuentro',x:0,y:0,z:0}];return m;};
  const load=async data=>{
   await page.locator('#file-input').setInputFiles({name:'retorno-prueba.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(data))});
   await page.locator('#entity-list [data-select-id="N1"]').first().waitFor();return model();
  };
  const createReturn=async({layout='central',shared=true}={})=>{
   await select('node','N1');await page.locator('#inspector [data-action="connect"]').click();
   assert.equal(await dialog().locator('[name="return_layout"]').isVisible(),false,'Las opciones de retorno sólo aparecen al elegir su función.');
   await dialog().locator('[name="funcion"]').selectOption('retorno');await dialog().locator('[name="direccion"]').selectOption('Y+');
   await dialog().locator('[name="longitud"]').fill('5');await dialog().locator('[name="return_layout"]').selectOption(layout);
   if(layout==='ends')await dialog().locator('[name="return_shared"]').setChecked(shared);
   else assert.equal(await dialog().locator('[name="return_shared"]').isVisible(),false);
   await dialog().locator('[type="submit"]').click();await dialog().waitFor({state:'hidden'});return model();
  };
  const configure=async(edgeId,layout,shared)=>{
   await select('edge',edgeId);await page.locator('#inspector [data-action="return-supports"]').click();
   await dialog().locator('[name="layout"]').selectOption(layout);
   if(layout==='ends')await dialog().locator('[name="shared"]').setChecked(shared);
   assert(await dialog().locator('[data-return-preview] svg').isVisible());
   await dialog().locator('[type="submit"]').click();await dialog().waitFor({state:'hidden'});return model();
  };
  const edit=async(field,value)=>{const input=page.locator(`#inspector [data-field="${field}"]`);await input.fill(value);await input.press('Tab');};
  const node=(m,id)=>m.nodos.find(n=>n.id===id);
  const centre=m=>m.nodos.find(n=>n.anclaje_tramo);
  const structural=m=>({nodos:m.nodos,tramos:m.tramos,soportes:m.soportes,fundaciones:m.fundaciones,ejes:m.ejes});

  await page.goto('http://pasarela.test/');await load(blank());
  let m=await createReturn();const edgeId=m.tramos[0].id,centreId=centre(m).id;
  assert.equal(m.tramos.length,1,'Una columna central no divide el retorno en dos tramos.');
  assert.equal(m.nodos.length,3);assert.equal(m.soportes.length,1);assert.equal(m.fundaciones.length,1);
  assert.deepEqual(centre(m).anclaje_tramo,{tramo:edgeId,t:.5});assert.deepEqual([centre(m).x,centre(m).y,centre(m).z],[0,2500,0]);
  assert.equal(m.soportes[0].cota_superior_mm,-250);assert.equal(m.soportes[0].nodo,centreId);
  assert(m.ejes.some(a=>a.tipo==='apoyo'&&a.nodo===centreId),'La columna central debe tener su propio eje.');
  await select('node',centreId);
  for(const field of ['x','y','z'])assert.equal(await page.locator(`#inspector [data-field="${field}"]`).isEditable(),false);
  assert(await page.locator('#inspector [data-field="tipo"]').isDisabled());assert.equal(await page.locator('#inspector [data-action="connect"]').isVisible(),false);
  assert(await page.locator('#inspector [data-field="support:0:diametro_mm"]').isEditable());
  assert(await page.locator('#inspector [data-action="pile-plan"]').isVisible(),'Desde la columna se debe poder abrir la planta de su fundación.');
  const repeated=await configure(edgeId,'central',false);assert.deepEqual(structural(repeated),structural(m),'Aplicar la misma disposición debe conservar sus identidades y geometría.');

  await select('edge',edgeId);await edit('id','RETORNO_A');m=await model();
  assert.equal(m.tramos[0].id,'RETORNO_A');assert.equal(centre(m).anclaje_tramo.tramo,'RETORNO_A');
  for(const item of [centre(m),...m.soportes,...m.fundaciones])assert.equal(item.origen_retorno.tramo,'RETORNO_A');
  assert.equal(centre(m).id,centreId,'Cambiar el nombre del retorno no debe cambiar la identidad de su columna.');

  await page.locator('#inspector [data-action="direction"]').click();await dialog().locator('[name="direccion"]').selectOption('X+');await dialog().locator('[name="longitud"]').fill('6');
  assert((await dialog().locator('#direction-preview').textContent()).includes(centreId),'La vista previa de movimiento debe incluir la columna central.');
  await dialog().locator('[type="submit"]').click();m=await model();
  assert.deepEqual([centre(m).x,centre(m).y,centre(m).z],[3000,0,0]);assert.equal(m.soportes[0].cota_superior_mm,-250);
  const baseBefore=structuredClone(m.fundaciones[0]);
  await select('node','N1');await edit('z','0.8');
  assert((await dialog().locator('#move-preview').textContent()).includes(centreId));
  await dialog().locator('[type="submit"]').click();m=await model();
  assert.equal(node(m,'N1').z,800);assert.equal(node(m,'N2').z,800);assert.equal(centre(m).z,800);
  assert.equal(m.soportes[0].cota_superior_mm,550);assert.deepEqual(m.fundaciones[0],baseBefore,'Cambiar la cota del retorno no debe mover en Z su fundación sin solicitarlo.');
  await page.locator('#undo').click();m=await model();assert.equal(centre(m).z,0);assert.equal(m.soportes[0].cota_superior_mm,-250);assert.equal(centre(m).x,3000);

  const portable=await save();assert.equal(portable.version,2);assert.equal(portable.proyecto.unidades,'m');
  assert.equal(centre(portable).x,3);assert.equal(portable.soportes[0].diametro_m,1);assert.deepEqual(centre(portable).anclaje_tramo,{tramo:'RETORNO_A',t:.5});
  assert.equal(Object.hasOwn(portable.soportes[0],'diametro_mm'),false);assert.equal(portable.tramos.length,1);
  await load(portable);assert.deepEqual(structural(await model()),structural(io.toInternal(portable)),'Reabrir el JSON debe preservar el apoyo central y sus referencias.');

  const beforeEnds=await model();m=await configure('RETORNO_A','ends',true);
  assert.equal(m.tramos.length,1);assert.equal(m.nodos.length,2);assert.equal(m.soportes.length,2);assert.equal(m.fundaciones.length,1);
  assert.deepEqual(m.fundaciones[0].nodos,['N1','N2']);assert.equal(m.fundaciones[0].largo_mm,9000);
  assert.equal(m.nodos.some(n=>n.anclaje_tramo),false);assert.equal(m.ejes.filter(a=>a.tipo==='apoyo').length,2);
  await page.locator('#undo').click();assert.deepEqual(structural(await model()),structural(beforeEnds),'Deshacer una nueva disposición debe restaurar la columna central y su fundación.');
  m=await configure('RETORNO_A','ends',true);assert.deepEqual(structural(await configure('RETORNO_A','ends',true)),structural(m));
  await page.locator('#view-iso').click();await select('node','N1');await page.locator('#fit').click();fs.mkdirSync('tmp',{recursive:true});
  await page.screenshot({path:'tmp/retorno-columnas.png'});
  m=await configure('RETORNO_A','central',false);assert.equal(m.soportes.length,1);assert.equal(m.fundaciones.length,1);assert.equal(m.tramos.length,1);

  // Both creation choices work from a fresh project, not only by reconfiguring an example.
  await load(blank());m=await createReturn({layout:'ends',shared:true});assert.equal(m.soportes.length,2);assert.equal(m.fundaciones.length,1);
  assert.equal(m.fundaciones[0].angulo_deg,90);assert.equal(m.fundaciones[0].largo_mm,8000);
  await load(blank());m=await createReturn({layout:'ends',shared:false});assert.equal(m.soportes.length,2);assert.equal(m.fundaciones.length,2);
  assert.notEqual(m.soportes[0].fundacion,m.soportes[1].fundacion);assert(m.fundaciones.every(f=>f.nodos.length===1&&f.largo_mm===3000));
  assert.deepEqual(errors,[]);
  console.log('Return supports UI: central/end creation, individual/shared bases, preserved identity, configuration preview, undo, anchored read-only coordinates, rename, direction/elevation movement, axes and metre JSON roundtrip passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
