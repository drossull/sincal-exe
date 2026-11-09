// Isolated splice editor fed by real Python removal cases; no CAD or desktop UI.
const {chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const cases=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',`
import json
from tests.test_web_bar_removal import state_and_assembly, remove
from sincal.rebar.assembly import build_footing_assembly
from sincal.web.rebar import domain, preview
cases=[]
for role in ('inicial','terminal','intermedia','all'):
    state, assembly=state_and_assembly()
    if role=='intermedia':
        state['geometry']['ancho_cm']=2300
        assembly=build_footing_assembly(*domain(state))
    first=next(bar for bar in assembly.bars if bar.key=='mesh_x' and bar.piece_role=='inicial')
    selected=[bar for bar in assembly.bars if bar.key=='mesh_x' and
              ((role=='intermedia' and bar.piece_role==role) or
               (bar.placement_id==first.placement_id and (role=='all' or bar.piece_role==role)))]
    remove(state,*selected)
    cases.append({'role':role,'state':state,'response':preview(state)})
print(json.dumps(cases))
`],{cwd:root,encoding:'utf8',maxBuffer:8*1024*1024}));
const fixture=`
import {openSpliceEditor} from '/rebar_splices.js';
const cases=${JSON.stringify(cases)},fixture=window.fixture={errors:[],applied:[]};
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const button=(text,fn)=>{const e=node('button',text);e.onclick=fn;return e;};
for(const test of cases){document.body.append(button(test.role,()=>openSpliceEditor({
 ctx:{node,button,api:async(route)=>{if(route!=='rebar/preview')throw Error('Forbidden route');return structuredClone(test.response);}},
 state:test.state,rule:test.state.rules[0],onApply:value=>fixture.applied.push(value)
})));}
window.ready=true;
`;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1366,height:950}}),errors=[];
  page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.slice(1);
   if(!name)return route.fulfill({contentType:'text/html',body:'<!doctype html><html lang="es"><head><meta charset="utf-8"><link rel="stylesheet" href="/app.css"></head><body><script type="module" src="/fixture.js"></script></body></html>'});
   if(name==='fixture.js')return route.fulfill({contentType:'text/javascript',body:fixture});
   if(name==='rebar_splices.js'||name==='app.css'||name.endsWith('.ttf'))return route.fulfill({body:fs.readFileSync(path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name)),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://sincal-removed-splices.test/');await page.waitForFunction(()=>window.ready);
  const dialog=page.getByRole('dialog');
  for(const role of ['inicial','terminal','intermedia','all']){
   await page.getByRole('button',{name:role,exact:true}).click();
   await page.waitForFunction(()=>document.querySelector('.rebar-splice-dialog')?.getAttribute('aria-busy')==='false');
   assert.equal(await dialog.locator('[data-splice-lap],[data-splice-dimension]').count(),0,'No physical lap line or dimension remains without its partner');
   assert.equal(await dialog.locator('[data-splice-mark]').count(),role==='all'?0:role==='intermedia'?2:1);
   const status=await dialog.getByRole('status').textContent();
   if(role==='all'){
    assert.match(status,/No hay un empalme disponible.*fierros eliminados/);
    assert.equal(await dialog.getByRole('button',{name:'Aplicar largo',exact:true}).isDisabled(),true);
   }else{
    assert.match(status,/no tiene traslapos físicos/);
    assert.match(await dialog.textContent(),/eliminada.*posiciones reales/);
   }
   assert.doesNotMatch(status,/cabe en piezas completas/);
   await dialog.getByRole('button',{name:'Cerrar',exact:true}).click();await dialog.waitFor({state:'detached'});
  }
  assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>fixture.applied),[]);
  console.log('OK: empalme sin pareja → sin cota ni engrosamiento; inicial, continuación, intermedias y recorrido completo eliminados.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
