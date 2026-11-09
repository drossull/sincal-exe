// Wing removals are stored per side, while footing removals stay per rule.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const bars=[
 {id:'mesh_x:superior:0:0',key:'mesh_x',signature:'a'.repeat(64),mark:'1',element_key:'abutment.footing',points:[[-2,-2,0],[2,-2,0]]},
 {id:'wing:left:vertical_main:0',key:'wing_left_vertical_main',signature:'b'.repeat(64),mark:'11',element_key:'abutment.left_wing',points:[[-2,0,0],[-2,0,3]]},
 {id:'wing:left:horizontal_main:0',key:'wing_left_horizontal_main',signature:'c'.repeat(64),mark:'13',element_key:'abutment.left_wing',points:[[-2,0,1],[-2,2,1]]},
 {id:'wing:right:vertical_main:0',key:'wing_right_vertical_main',signature:'d'.repeat(64),mark:'21',element_key:'abutment.right_wing',points:[[2,0,0],[2,0,3]]},
 {id:'wing:left:inner_vertical_main:0',key:'wing_left_inner_vertical_main',signature:'e'.repeat(64),mark:'31',element_key:'abutment.left_wing',points:[[-1.7,0,0],[-1.7,0,3]]},
 {id:'wing:right:inner_horizontal_main:0',key:'wing_right_inner_horizontal_main',signature:'f'.repeat(64),mark:'43',element_key:'abutment.right_wing',points:[[1.7,0,1.4],[1.7,2,1.4]]},
 {id:'wing:left:inner_supplement_front:0',key:'wing_left_inner_supplement_front',signature:'1'.repeat(64),mark:'51',element_key:'abutment.left_wing',points:[[-1.6,0,2],[-1.6,2,2]]},
 {id:'wing:right:inner_supplement_back:0',key:'wing_right_inner_supplement_back',signature:'2'.repeat(64),mark:'52',element_key:'abutment.right_wing',points:[[1.6,0,2.4],[1.6,2,2.4]]},
 {id:'wing:left:edge:0',key:'wing_left_edge',signature:'3'.repeat(64),mark:'53',element_key:'abutment.left_wing',points:[[-2,2,3],[-2,4,4]]},
].map(bar=>({...bar,diameter_mm:16,length_cm:300,piece_role:'completa',placement_id:bar.id}));
const scene={units:'m',bars,issues:[],elements:[
 {key:'abutment.footing',label:'Fundación',meshes:[{vertices:[[-3,-3,-1],[3,-3,-1],[3,3,-1],[-3,3,-1]],faces:[[0,1,2,3]]}]},
 {key:'abutment.left_wing',label:'Ala izquierda',meshes:[]},
 {key:'abutment.right_wing',label:'Ala derecha',meshes:[]},
]};
const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8"><link rel="stylesheet" href="/app.css"><link rel="stylesheet" href="/fixture.css"></head><body><div id="host"></div><script nonce="fixture" type="module">
import {mountAbutmentIsometric} from '/rebar_isometric.js';
const wing=()=>({geometry:{thickness_cm:100},outer_family:'vertical',horizontal_start:'wall',removed_pieces:[],interior:{enabled:true,parameters_initialized:true,removed_pieces:[]},supplements:{front:{removed_pieces:[]},back:{removed_pieces:[]}},edge_rebar:{removed_pieces:[]}});
const state=()=>({geometry:{alto_cm:150},rules:[{key:'mesh_x',label:'Malla 1',removed_pieces:[]}],wings:{left:wing(),right:wing()}});
const project={data:{estribos:{}},rebar:{entrada:state(),salida:state()}};
const scene=${JSON.stringify(scene)};
const fixture=window.fixture={project,current:true,changes:0,edits:[],calls:[],errors:[],failNext:false,unresolved:false};
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
const allRecords=state=>[...state.rules.flatMap(rule=>rule.removed_pieces||[]),...Object.values(state.wings).flatMap(wing=>[...(wing.removed_pieces||[]),...(wing.interior.removed_pieces||[]),...wing.supplements.front.removed_pieces,...wing.supplements.back.removed_pieces,...wing.edge_rebar.removed_pieces])];
const ctx={project,node,current:()=>fixture.current,changed:()=>fixture.changes++,notify:message=>fixture.errors.push(message),api:async(route,payload)=>{
 if(route!=='rebar/abutment/scene')throw Error('Unexpected/CAD route '+route);fixture.calls.push(structuredClone(payload));
 if(fixture.failNext){fixture.failNext=false;throw Error('Fallo recuperable');}
 const records=allRecords(payload.state),ids=new Set(records.map(piece=>piece.id+':'+piece.signature));
 return {...structuredClone(scene),bars:scene.bars.filter(bar=>!ids.has(bar.id+':'+bar.signature)),removed_bars:records.map(piece=>{
  const bar=scene.bars.find(bar=>bar.id===piece.id&&bar.signature===piece.signature);
  return fixture.unresolved?{...piece,status:'unresolved'}:{...piece,key:bar?.key,mark:bar?.mark,status:bar?'removed':'unresolved'};
 })};}};
fixture.mount=async()=>{fixture.viewer?.dispose();fixture.viewer=mountAbutmentIsometric(ctx,'entrada',document.getElementById('host'),{onPiecesChanged:key=>fixture.edits.push({key,changes:fixture.changes,state:structuredClone(project.rebar[key]),quantity:scene.bars.length-allRecords(project.rebar[key]).length})});await fixture.viewer.ready;};
await fixture.mount();window.ready=true;
</script></body></html>`;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1360,height:1000}}),errors=[],csp=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.text().includes('Content Security Policy'))csp.push(m.text());});
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({body:harness,contentType:'text/html',headers:{'Content-Security-Policy':"default-src 'self'; script-src 'self' 'nonce-fixture'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'"}});
   if(name==='fixture.css')return route.fulfill({body:'body{padding:20px}#host{max-width:1050px;margin:auto}',contentType:'text/css'});
   if(['rebar_isometric.js','app.css'].includes(name)||name.endsWith('.ttf'))return route.fulfill({body:fs.readFileSync(path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-wing-pieces.test');await page.waitForFunction(()=>window.ready);
  const embedded=page.getByRole('region',{name:'Vista isométrica del estribo',exact:true});
  const dialog=page.getByRole('dialog',{name:'Vista isométrica del estribo',exact:true});
  const ready=async(scope=embedded)=>{await scope.locator('svg').waitFor();await page.waitForFunction(()=>[...document.querySelectorAll('.rebar-isometric')].every(el=>el.getAttribute('aria-busy')!=='true'));};
  const camera=()=>embedded.locator('svg').evaluate(el=>Object.fromEntries(['yaw','pitch','zoom','scale','target'].map(key=>[key,el.dataset[key]])));
  const select=async(index,scope=embedded)=>{
   const p=await scope.locator(`[data-layer="armaduras"] polyline[data-piece="${bars[index].id}"]`).evaluate(el=>{const a=el.points[0],b=el.points[1];return new DOMPoint(a.x+(b.x-a.x)*.23,a.y+(b.y-a.y)*.23).matrixTransform(el.getScreenCTM()).toJSON();});
   await page.mouse.click(p.x,p.y);await scope.getByRole('button',{name:'Eliminar este fierro',exact:true}).waitFor();
   const chooser=scope.getByRole('combobox',{name:'Elegir fierro superpuesto'});
   if(await chooser.isVisible())await chooser.selectOption(await chooser.locator('option').evaluateAll((items,mark)=>items.find(item=>item.textContent.includes('Marca '+mark+' ·')).value,bars[index].mark));
   assert.equal(await scope.locator('.iso-piece-panel').getAttribute('data-piece'),bars[index].id);
  };
  const remove=async(index,scope=embedded)=>{await select(index,scope);await scope.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();await ready(scope);};
  const records=()=>page.evaluate(()=>({rules:fixture.project.rebar.entrada.rules.map(rule=>rule.removed_pieces),left:fixture.project.rebar.entrada.wings.left.removed_pieces,right:fixture.project.rebar.entrada.wings.right.removed_pieces}));
  const record=index=>({id:bars[index].id,signature:bars[index].signature});
  await ready();const originalCamera=await camera(),originalState=await page.evaluate(()=>structuredClone(fixture.project));
  // Exact wing piece only: a same-side different family remains visible.
  await remove(1);
  assert.deepEqual(await records(),{rules:[[]],left:[record(1)],right:[]});
  assert.equal(await embedded.locator(`[data-piece="${bars[2].id}"]`).count(),1);
  assert.deepEqual(await camera(),originalCamera);
  assert.equal(await page.evaluate(()=>fixture.edits[0].changes),1);
  assert.equal(await page.evaluate(()=>fixture.edits[0].quantity),bars.length-1);
  assert.deepEqual(await page.evaluate(()=>fixture.edits[0].state.wings.left.removed_pieces),[record(1)]);
  await remove(3);await remove(0);
  assert.deepEqual(await records(),{rules:[[record(0)]],left:[record(1)],right:[record(3)]});
  // Undo resolves each owner in reverse order across footing and both wings.
  for(const expected of [
   {rules:[[]],left:[record(1)],right:[record(3)]},
   {rules:[[]],left:[record(1)],right:[]},
   {rules:[[]],left:[],right:[]},
  ]){await embedded.getByRole('button',{name:'Deshacer eliminación',exact:true}).click();await ready();assert.deepEqual(await records(),expected);}
  // A lost scene response still offers undo for a wing collection.
  await select(2);await page.evaluate(()=>{fixture.failNext=true;});await embedded.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();
  await embedded.getByRole('button',{name:'Volver a intentar',exact:true}).waitFor();
  await embedded.getByRole('button',{name:'Deshacer eliminación',exact:true}).click();await ready();assert.deepEqual((await records()).left,[]);
  // Reopening restores persisted exact records, not whole families or sides.
  await remove(1);await remove(3);await page.evaluate(()=>fixture.mount());await ready();
  await embedded.getByRole('button',{name:'Ver eliminados',exact:true}).click();await ready(dialog);
  await dialog.getByText('Fierros eliminados · 2',{exact:true}).click();
  await dialog.getByRole('button',{name:/^Restaurar Marca 11/}).click();await ready(dialog);
  assert.deepEqual(await records(),{rules:[[]],left:[],right:[record(3)]});
  await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await dialog.waitFor({state:'detached'});await ready();
  // Unresolved backend records may omit key and metadata. They still restore
  // from id/side/group after remount, with a readable label.
  await page.evaluate(()=>{fixture.unresolved=true;return fixture.mount();});await ready();
  await embedded.getByRole('button',{name:'Ver eliminados',exact:true}).click();await ready(dialog);
  await dialog.getByText('Fierros eliminados · 1',{exact:true}).click();
  assert.match(await dialog.locator('.iso-removed-piece').textContent(),/Ala derecha.*Revisar/);
  assert.doesNotMatch(await dialog.locator('.iso-removed-piece').textContent(),/undefined|NaN/);
  await dialog.getByRole('button',{name:/^Restaurar Ala derecha/}).click();await ready(dialog);
  assert.deepEqual(await records(),{rules:[[]],left:[],right:[]});
  await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await dialog.waitFor({state:'detached'});await ready();
  // Stale wing geometry cannot delete an old selection.
  await select(1);await page.evaluate(()=>{fixture.project.rebar.entrada.wings.left.geometry.thickness_cm=120;});
  await embedded.getByRole('button',{name:'Eliminar este fierro',exact:true}).click();await ready();
  assert.deepEqual((await records()).left,[]);assert.match(await page.evaluate(()=>fixture.errors.at(-1)),/armadura cambió/);
  // Interior IDs resolve to their own collection, independently of an exterior
  // bar with the same side/index, and survive closing/reopening the viewer.
  await page.evaluate(()=>{fixture.unresolved=false;});
  await remove(4);await remove(1);await remove(5);
  assert.deepEqual(await records(),{rules:[[]],left:[record(1)],right:[]});
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left.interior.removed_pieces),[record(4)]);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.right.interior.removed_pieces),[record(5)]);
  await embedded.getByRole('button',{name:'Deshacer eliminación',exact:true}).click();await ready();
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.right.interior.removed_pieces),[]);
  assert.deepEqual((await records()).left,[record(1)]);
  await page.evaluate(()=>fixture.mount());await ready();
  await embedded.getByRole('button',{name:'Ver eliminados',exact:true}).click();await ready(dialog);
  await dialog.getByText('Fierros eliminados · 2',{exact:true}).click();
  await dialog.getByRole('button',{name:/^Restaurar Marca 31/}).click();await ready(dialog);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left.interior.removed_pieces),[]);
  assert.deepEqual((await records()).left,[record(1)]);
  await dialog.getByText('Fierros eliminados · 1',{exact:true}).click();
  await dialog.getByRole('button',{name:/^Restaurar Marca 11/}).click();await ready(dialog);
  assert.deepEqual((await records()).left,[]);
  await dialog.getByRole('button',{name:'Cerrar visor',exact:true}).click();await dialog.waitFor({state:'detached'});await ready();
  // Supplement and edge IDs resolve before the general inner/outer fallback.
  for(const index of [6,7,8])await remove(index);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left.supplements.front.removed_pieces),[record(6)]);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.right.supplements.back.removed_pieces),[record(7)]);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left.edge_rebar.removed_pieces),[record(8)]);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left.interior.removed_pieces),[]);assert.deepEqual((await records()).left,[]);
  await page.evaluate(()=>fixture.mount());await ready();await embedded.getByRole('button',{name:'Ver eliminados',exact:true}).click();await ready(dialog);
  for(const [index,mark] of ['51','52','53'].entries()){
   await dialog.getByText('Fierros eliminados · '+(3-index),{exact:true}).click();await dialog.getByRole('button',{name:new RegExp('^Restaurar Marca '+mark)}).click();await ready(dialog);
  }
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left.edge_rebar.removed_pieces),[]);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.left.supplements.front.removed_pieces),[]);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.entrada.wings.right.supplements.back.removed_pieces),[]);
  assert.deepEqual(await page.evaluate(()=>fixture.project.rebar.salida),originalState.rebar.salida);
  assert.deepEqual(await page.evaluate(()=>fixture.project.data),originalState.data);
  assert.equal(await page.evaluate(()=>fixture.changes),24);assert.equal(await page.evaluate(()=>fixture.edits.length),24);
  assert.deepEqual(errors,[]);assert.deepEqual(csp,[]);
  console.log('OK: bajas individuales de alas por lado y malla exterior/interior; zapata intacta; deshacer mixto, restauración persistente y registros sin key; callback, cámara, firmas y CSP.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
