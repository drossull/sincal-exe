// Expanded mark table under the installed desktop CSP; no CAD or installed app.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const server=fs.readFileSync(path.join(root,'sincal/web/server.py'),'utf8');
const csp=server.match(/self\.send_header\("Content-Security-Policy", "([^"]+)"\)/)?.[1];
assert(csp&&csp.includes("style-src 'self'")&&!csp.includes('unsafe-inline'));
const calculation=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',`
import json
from sincal.web.rebar import defaults, preview
state=defaults()
state['geometry']['esviaje_grados']=-12
print(json.dumps({'state':state,'response':preview(state)}))
`],{cwd:root,encoding:'utf8'}));
assert(calculation.response.valid);
assert.equal(calculation.response.marks.length,6);
const html='<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8">'+
 '<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css">'+
 '<link rel="stylesheet" href="/fixture.css"></head><body><main id="host"></main>'+
 '<script type="module" src="/fixture.js"></script></body></html>';
const fixtureCss='#host{max-width:1480px;margin:auto;padding:24px}';
const fixtureJs=`
import {renderRebar} from '/rebar.js';
window.violations=[];
document.addEventListener('securitypolicyviolation',event=>violations.push({directive:event.effectiveDirective,blocked:event.blockedURI}));
const state=${JSON.stringify(calculation.state)};
const project={data:{test:'mark table fixture'},identification:{structure_name:'Tabla de zapata · prueba local'}};
const fixture=window.fixture={project,response:${JSON.stringify(calculation.response)},calls:[],errors:[],changes:0};
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const button=(text,action,primary=false)=>{const e=node('button',text,primary?'primary':'');e.type='button';e.addEventListener('click',async()=>{try{await action();}catch(error){fixture.errors.push(error.message);}});return e;};
const section=(id,title)=>{const e=node('section');e.id=id;e.append(node('h2',title));document.getElementById('host').append(e);return e;};
const api=async(route,payload)=>{fixture.calls.push({route,payload:structuredClone(payload)});
 if(route==='rebar/from-project')return {entrada:structuredClone(state),salida:structuredClone(state)};
 if(route==='rebar/abutment/scene')return {elements:[],bars:[],issues:[],instance_key:payload.instance_key};
 if(route==='rebar/preview')return structuredClone(fixture.response);
 throw Error('CAD and other routes forbidden: '+route);};
await renderRebar({project,node,button,section,api,current:()=>true,changed:()=>fixture.changes++,notify:message=>fixture.errors.push(message),job:()=>{throw Error('CAD forbidden');}});
window.ready=true;
`;

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1366,height:900}}),errors=[];
  page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1),headers={'Content-Security-Policy':csp,'X-Content-Type-Options':'nosniff'};
   if(!name)return route.fulfill({body:html,contentType:'text/html',headers});
   if(name==='fixture.js')return route.fulfill({body:fixtureJs,contentType:'text/javascript',headers});
   if(name==='fixture.css')return route.fulfill({body:fixtureCss,contentType:'text/css',headers});
   if(['app.css','rebar.js','rebar_isometric.js','rebar_splitter.js','rebar_splices.js'].includes(name)||name.endsWith('.ttf')){
    const file=path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name);
    return route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf',headers});
   }
   return route.fulfill({status:404,body:'',headers});
  });
  await page.goto('http://sincal-marks-layout.test/');await page.waitForFunction(()=>window.ready);
  await page.evaluate(()=>document.fonts.ready);
  await page.getByRole('button',{name:'Calcular marcas',exact:true}).click();
  const opener=page.getByRole('button',{name:'Ampliar tabla de marcas',exact:true});await opener.waitFor();
  const originalProject=await page.evaluate(()=>structuredClone(fixture.project));
  const originalChanges=await page.evaluate(()=>fixture.changes);
  const sourceRows=await page.locator('#host table').first().locator('tbody tr').evaluateAll(rows=>rows.map(row=>Array.from(row.cells,cell=>cell.textContent)));
  const sourceHeaders=await page.locator('#host table').first().locator('th').allTextContents();
  assert.equal(sourceHeaders.length,12);assert.deepEqual(sourceHeaders.slice(-2),['Vistas','Rol']);
  const dialog=page.locator('dialog.rebar-marks-dialog'),scroll=dialog.locator('.rebar-marks-scroll');
  const table=dialog.getByRole('table');
  const close=async()=>{await dialog.getByRole('button',{name:'Cerrar tabla',exact:true}).click();await dialog.waitFor({state:'detached'});};
  const inside=async(child,parent,message)=>{
   const [a,b]=await Promise.all([child.boundingBox(),parent.boundingBox()]);assert(a&&b,message);
   assert(a.x>=b.x-1&&a.y>=b.y-1&&a.x+a.width<=b.x+b.width+1&&a.y+a.height<=b.y+b.height+1,message);
  };
  fs.mkdirSync(path.join(root,'tmp'),{recursive:true});
  for(const [width,height] of [[992,768],[1366,900],[1920,1080]]){
   await page.setViewportSize({width,height});await opener.click();await dialog.waitFor();
   const box=await dialog.boundingBox();assert(box.width>=width-65,'Expansion uses the available screen width.');
   assert(box.x>=0&&box.x+box.width<=width+1&&box.y>=0&&box.y+box.height<=height+1,'Dialog fits the viewport.');
   assert.equal(await scroll.evaluate(el=>el.scrollLeft),0,'The first mark is visible on opening.');
   assert(await scroll.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'All columns fit without horizontal scrolling on desktop.');
   assert(await scroll.evaluate(el=>el.scrollHeight<=el.clientHeight+1),'All six rows fit without vertical scrolling.');
   assert.equal(await table.locator('th').count(),12);assert.equal(await table.locator('tbody tr').count(),6);
   assert.deepEqual(await table.locator('th').allTextContents(),sourceHeaders);
   assert.deepEqual(await table.locator('tbody tr').evaluateAll(rows=>rows.map(row=>Array.from(row.cells,cell=>cell.textContent))),sourceRows);
   for(const cell of await table.locator('th,td').all())await inside(cell,scroll,'Every cell is fully inside the scroll viewport.');
   const cellsFit=await table.locator('th,td').evaluateAll(cells=>cells.every(cell=>cell.scrollWidth<=cell.clientWidth+1));
   assert(cellsFit,'Wrapped text and numbers fit their own cells without clipping.');
   assert.equal(await table.locator('th').first().evaluate(el=>{const range=document.createRange();range.selectNodeContents(el);return range.getClientRects().length;}),1,'The short Marca heading stays on one readable line.');
   await inside(dialog.getByRole('button',{name:'Cerrar tabla',exact:true}),dialog,'Close remains visible.');
   assert(await dialog.evaluate(el=>el.contains(document.activeElement)),'Focus stays in the expanded table.');
   if(width!==1920)await dialog.screenshot({path:path.join(root,`tmp/rebar-marks-expanded-${width}.png`)});
   await close();assert(await opener.evaluate(el=>document.activeElement===el),'Closing restores focus to the expansion button.');
  }

  // Mark actions still open the real detail, with the table intact underneath.
  await page.setViewportSize({width:1366,height:900});await opener.click();
  const variable=calculation.response.marks.find(mark=>mark.key==='mesh_y');
  await table.getByRole('button',{name:variable.mark,exact:true}).click();
  const detail=page.locator('dialog.rebar-detail-dialog');
  await detail.getByRole('heading',{name:`Marca ${variable.mark} · Zapata`,exact:true}).waitFor();
  assert.equal(await page.locator('dialog[open]').count(),2);
  await detail.getByRole('button',{name:'Cerrar',exact:true}).click();await detail.waitFor({state:'detached'});
  assert.deepEqual(await table.locator('tbody tr').evaluateAll(rows=>rows.map(row=>Array.from(row.cells,cell=>cell.textContent))),sourceRows);
  await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
  assert(await opener.evaluate(el=>document.activeElement===el));

  // More rows need scrolling, but neither headings nor closing controls disappear.
  await page.evaluate(()=>{
   const response=fixture.response,example=response.marks[0],piece=response.details[0];
   for(let i=response.marks.length;i<50;i++){
    const mark=String(i+10);response.marks.push({...structuredClone(example),mark});response.details.push({...structuredClone(piece),mark});
   }
  });
  await page.getByRole('button',{name:'Calcular marcas',exact:true}).click();await opener.click();
  assert.equal(await table.locator('tbody tr').count(),50);
  assert(await scroll.evaluate(el=>el.scrollHeight>el.clientHeight),'Rows scroll when their total height exceeds the screen.');
  await scroll.evaluate(el=>{el.scrollTop=el.scrollHeight;});
  await inside(dialog.getByRole('heading',{name:'Marcas · entrada',exact:true}),dialog,'Heading remains visible with many rows.');
  await inside(dialog.getByRole('button',{name:'Cerrar tabla',exact:true}),dialog,'Closing remains visible with many rows.');
  await inside(table.locator('tbody tr').last(),scroll,'Last row is accessible.');

  // A phone cannot fit twelve readable columns; every column remains reachable.
  await page.setViewportSize({width:410,height:850});
  assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Only the table scrolls horizontally.');
  await scroll.evaluate(el=>{el.scrollTop=0;el.scrollLeft=0;});
  await inside(table.locator('tbody tr').first().getByRole('cell').first(),scroll,'First mark reachable at the left edge.');
  await scroll.evaluate(el=>{el.scrollLeft=el.scrollWidth;});
  await inside(table.locator('tbody tr').first().getByRole('cell').last(),scroll,'Last role reachable at the right edge.');
  await scroll.evaluate(el=>{el.scrollLeft=0;});
  await inside(dialog.getByRole('heading',{name:'Marcas · entrada',exact:true}),dialog,'Narrow heading remains visible.');
  await inside(dialog.getByRole('button',{name:'Cerrar tabla',exact:true}),dialog,'Narrow close remains visible.');
  await dialog.screenshot({path:path.join(root,'tmp/rebar-marks-expanded-narrow.png')});
  await close();
  assert.deepEqual(await page.evaluate(()=>fixture.project),originalProject,'Display and detail do not mutate parameters.');
  assert.equal(await page.evaluate(()=>fixture.changes),originalChanges);
  assert(await page.evaluate(()=>fixture.calls.every(call=>['rebar/from-project','rebar/abutment/scene','rebar/preview'].includes(call.route))));
  assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);assert.deepEqual(errors,[]);
  assert.deepEqual(await page.evaluate(()=>violations),[],'Real app CSP remains enforced with no exceptions.');
  console.log('OK: expanded mark table shows all 12 columns and 6 rows at 992/1366/1920; 50-row and narrow scrolling, details, focus, CSP and no CAD or parameter mutations.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
