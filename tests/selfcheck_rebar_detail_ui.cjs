// Browser checks of the actual Python detail and its GSG_COTAS presentation.
// All routes are local fixtures; no user session or CAD connection is used.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const fixtures=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',`
import json
from sincal.web.rebar import defaults, preview
cases={}
for name,skew,hook,width in [('negative',-12,0,1159.6),('positive',12,0,1159.6),('square',0,0,1159.6),('manual',-12,140,1159.6),('three',-12,0,2300)]:
    state=defaults()
    state['geometry'].update(esviaje_grados=skew,ancho_cm=width)
    if hook:
        state['geometry']['alto_cm']=180
        for rule in state['rules']:rule['hook_cm']=hook
    result=preview(state)
    assert result['valid'],(name,result['issues'])
    cases[name]={'state':state,'response':result}
print(json.dumps(cases))
`],{cwd:root,encoding:'utf8'}));
const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/app.css"></head><body><main id="host"></main>
<script type="module">
import {renderRebar,openRebarDetail} from '/rebar.js';
const cases=${JSON.stringify(fixtures)};
const fixture=window.fixture={calls:[],errors:[],changes:0,project:null};
const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
const button=(text,action,primary=false)=>{const el=node('button',text,primary?'primary':'');el.type='button';el.onclick=async()=>{try{await action();}catch(error){fixture.errors.push(error.message);}};return el;};
const section=(id,title)=>{const el=node('section');el.id=id;el.append(node('h2',title));document.getElementById('host').append(el);return el;};
fixture.openDetail=(piece,mark)=>openRebarDetail({node,button,notify:text=>fixture.errors.push(text)},piece,mark);
fixture.openCase=async name=>{
  document.getElementById('host').replaceChildren();
  const sample=cases[name],project={data:{fixture:name},identification:{structure_name:'Detalle de prueba '+name}};
  fixture.project=project;
  const api=async(route,payload)=>{fixture.calls.push({route,payload:structuredClone(payload)});
    if(route==='rebar/from-project')return {entrada:structuredClone(sample.state),salida:structuredClone(sample.state)};
    if(route==='rebar/preview')return structuredClone(sample.response);
    if(route==='rebar/abutment/scene')return {elements:[],bars:[],issues:[]};
    throw Error('Forbidden route '+route);};
  await renderRebar({project,api,node,button,section,current:()=>fixture.project===project,notify:text=>fixture.errors.push(text),changed:()=>fixture.changes++,job:()=>{throw Error('CAD is forbidden');}});
};
await fixture.openCase('negative');window.ready=true;
</script></body></html>`;

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',async route=>{
      const name=new URL(route.request().url()).pathname.slice(1);
      if(!name)return route.fulfill({body:harness,contentType:'text/html'});
      if(['app.css','rebar.js','rebar_isometric.js','rebar_splitter.js','rebar_splices.js'].includes(name)||name.endsWith('.ttf')){
        const file=path.join(root,name.endsWith('.ttf')?'assets/fonts':'sincal/web/static',name);
        return route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'font/ttf'});
      }
      return route.fulfill({status:404,body:''});
    });
    await page.goto('http://sincal-detail.test/');await page.waitForFunction(()=>window.ready);
    const output=path.join(root,'tmp','rebar-detail-preview');fs.mkdirSync(output,{recursive:true});
    const fmt=value=>String(Number(value.toFixed(4)));
    async function checkDrawing(piece){
      const dialog=page.getByRole('dialog'),drawing=dialog.locator('svg.rebar-detail-preview');
      await drawing.waitFor();
      await page.evaluate(()=>document.fonts.ready);
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(resolve)));
      assert.equal(await drawing.getAttribute('data-dimstyle'),'GSG_COTAS');
      for(const [selector,property] of [
        ['.dimension-text','fill'],['.dimension-line,.dimension-extension','stroke'],['.dimension-arrow','fill'],
      ]){
        const colors=await drawing.locator(selector).evaluateAll((elements,property)=>elements.map(el=>getComputedStyle(el)[property]),property);
        assert(colors.length>0,`The detail includes ${selector}`);
        assert(colors.every(color=>color==='rgb(255, 255, 255)'),`All ${selector} remain white`);
      }
      assert.equal(await drawing.locator('[data-partial]').count(),piece.partials_cm.length);
      for(let index=0;index<piece.partials_cm.length;index++){
        const dim=drawing.locator(`[data-partial="${index}"]`),range=piece.partial_ranges_cm[index];
        const label=range.min_cm!==range.max_cm?`VAR. L= ${fmt(range.min_cm)} - ${fmt(range.max_cm)}`:fmt(piece.partials_cm[index]);
        assert.equal(await dim.getByText(label,{exact:true}).count(),1,`Correct dimension for partial ${index}`);
        assert(await dim.locator('line,path').count()>=3,'Aligned dimension includes dimension line and witness lines');
      }
      const bends=piece.bends.filter(bend=>bend.skewed);
      if(['mesh_x','mesh_y','suple'].includes(piece.key))
        assert(piece.bends.every(bend=>bend.bend_degrees===90&&!bend.skewed),'Mesh hooks stay vertical at 90 degrees');
      const angularLabels=(await drawing.locator('text').allTextContents()).filter(text=>/°$/.test(text));
      assert.deepEqual(angularLabels.sort(),bends.map(bend=>`${fmt(bend.interior_degrees)}°`).sort(),'Only actual skewed angles are dimensioned');
      // The renderer must fit both the geometry and all labels into its viewBox.
      const clipping=await drawing.evaluate(svg=>{
        const box=svg.viewBox.baseVal,tolerance=2;
        return [...svg.querySelectorAll('text')].filter(el=>{
          const b=el.getBBox(),matrix=el.getCTM(),inverse=svg.getCTM().inverse();
          return [[b.x,b.y],[b.x+b.width,b.y],[b.x+b.width,b.y+b.height],[b.x,b.y+b.height]].some(([x,y])=>{
            const p=new DOMPoint(x,y).matrixTransform(matrix).matrixTransform(inverse);
            return p.x<box.x-tolerance||p.y<box.y-tolerance||p.x>box.x+box.width+tolerance||p.y>box.y+box.height+tolerance;
          });
        }).map(el=>el.textContent);
      });
      assert.deepEqual(clipping,[],'Dimension labels remain inside the image');
      const labels=await drawing.locator('text').evaluateAll(elements=>elements.map(el=>{
        const b=el.getBoundingClientRect();return {text:el.textContent,x:b.x,y:b.y,right:b.right,bottom:b.bottom};
      }));
      for(let a=0;a<labels.length;a++)for(let b=a+1;b<labels.length;b++){
        const p=labels[a],q=labels[b],overlapX=Math.min(p.right,q.right)-Math.max(p.x,q.x),overlapY=Math.min(p.bottom,q.bottom)-Math.max(p.y,q.y);
        assert(!(overlapX>1&&overlapY>1),`Labels overlap: ${p.text} / ${q.text}`);
      }
      assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Dialog has no horizontal overflow');
      return dialog;
    }
    for(const name of Object.keys(fixtures)){
      if(name!=='negative')await page.evaluate(name=>fixture.openCase(name),name);
      const initial=await page.evaluate(()=>structuredClone(fixture.project));
      await page.getByRole('button',{name:'Calcular marcas',exact:true}).click();
      await page.getByRole('button',{name:'Ampliar tabla de marcas',exact:true}).waitFor();
      const table=page.getByRole('table').first();
      for(const piece of fixtures[name].response.details){
        if(['lateral_x','lateral_y'].includes(piece.key)){
          const skew=fixtures[name].state.geometry.esviaje_grados;
          assert(piece.bends.every(bend=>bend.skewed===(skew!==0)&&
            [90-skew,90+skew].some(angle=>Math.abs(bend.bend_degrees-angle)<1e-8)),
            'Lateral hooks retain the real skew angles in their own plane');
        }
        await table.getByRole('button',{name:piece.mark,exact:true}).click();
        const dialog=await checkDrawing(piece);
        if((name==='negative'&&['1','2','3','4','5','6'].includes(piece.mark))||(name==='positive'&&piece.mark==='5')||(name==='manual'&&piece.mark==='1'))
          await dialog.screenshot({path:path.join(output,`${name}-${piece.mark}.png`)});
        if(name==='negative'&&['4','3'].includes(piece.mark)){
          assert(await page.evaluate(()=>document.fonts.check('22px GSGRomanD')),'RomanD is ready for the dimension preview');
          await dialog.locator('svg.rebar-detail-preview').screenshot({path:path.join(output,piece.mark==='4'?'angular-cotas.png':'variable-cotas.png')});
        }
        if(name==='negative'&&piece.mark==='3'){
          await page.setViewportSize({width:440,height:950});await checkDrawing(piece);
          await dialog.screenshot({path:path.join(output,'variable-narrow.png')});
          await page.setViewportSize({width:1440,height:1000});
        }
        await dialog.getByRole('button',{name:'Cerrar',exact:true}).click();
      }
      assert.deepEqual(await page.evaluate(()=>fixture.project),initial,'Detail display never changes geometry, marks or quantities');
    }
    const fixed=structuredClone(fixtures.square.response.details[0]),fixedMark=structuredClone(fixtures.square.response.marks[0]);
    fixed.length_variants=[];fixed.variable_partial_index=null;fixedMark.length_variants=[];
    fixed.partial_ranges_cm=fixed.partials_cm.map((value,index)=>({min_cm:value-(index<2?10:0),max_cm:value+(index<2?10:0)}));
    fixed.detail_note='Largo total fijo; las parciales varían según la posición en el espesor.';
    await page.evaluate(({piece,mark})=>fixture.openDetail(piece,mark),{piece:fixed,mark:fixedMark});
    const fixedDialog=await checkDrawing(fixed);
    assert.equal(await fixedDialog.getByText(fixed.detail_note,{exact:true}).count(),1);
    assert.equal(await fixedDialog.getByText(/^Serie de largos variables/).count(),0);
    assert.equal(await fixedDialog.locator('svg .dimension-text').filter({hasText:'VAR. L='}).count(),2);
    assert(await fixedDialog.evaluate((dialog,note)=>Boolean([...dialog.querySelectorAll('p')].find(p=>p.textContent===note).compareDocumentPosition(dialog.querySelector('svg'))&Node.DOCUMENT_POSITION_FOLLOWING),fixed.detail_note));
    await fixedDialog.getByRole('button',{name:'Cerrar',exact:true}).click();
    assert.equal(await page.evaluate(()=>fixture.changes),0);
    assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);assert.deepEqual(errors,[]);
    assert(await page.evaluate(()=>fixture.calls.every(call=>['rebar/from-project','rebar/preview','rebar/abutment/scene'].includes(call.route))));
    console.log('OK: GSG_COTAS detail preview; linear/angular dimensions, variable partial ranges, positive/negative/zero skew, manual hooks, straight continuations, fit and responsive labels; no CAD or mutations.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
