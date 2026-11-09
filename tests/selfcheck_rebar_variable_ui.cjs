// Isolated UI contract check with a real Python calculation as its API fixture.
// No files from a user's project are opened and no CAD route is allowed.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const fixture=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',`
import json
from sincal.web.rebar import defaults, preview
state=defaults()
state['geometry']['esviaje_grados']=-12
print(json.dumps({'state':state,'response':preview(state)}))
`],{cwd:root,encoding:'utf8'}));
assert(fixture.response.valid,'The real calculation fixture must be valid.');
const variable=fixture.response.marks.find(mark=>mark.key==='mesh_y');
assert(variable.length_variants.length>1,'The fixture must contain a variable series.');
const lengths=variable.length_variants.map(item=>item.length_cm);
const range=`VAR ${Math.min(...lengths)}–${Math.max(...lengths)}`;
const variablePiece=fixture.response.details.find(piece=>piece.mark===variable.mark);
const partialRange=variablePiece.partial_ranges_cm[variablePiece.variable_partial_index];
const partialLabel=`VAR. L= ${partialRange.min_cm} - ${partialRange.max_cm}`;
assert.equal(partialLabel,'VAR. L= 21 - 743','The label ranges over the main partial, excluding both 100 cm hooks.');
const harness=`<!doctype html><html lang="es" data-theme="dark"><head><meta charset="utf-8">
<link rel="stylesheet" href="/app.css"></head><body><main id="host"></main>
<script type="module">
import {renderRebar} from '/rebar.js';
const response=${JSON.stringify(fixture.response)},state=${JSON.stringify(fixture.state)};
const project={data:{test:true},identification:{structure_name:'Prueba de serie variable'}};
const fixture=window.fixture={project,calls:[],errors:[],changes:0};
const node=(tag,text,cls)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
const button=(label,fn,primary=false)=>{const element=node('button',label,primary?'primary':'');element.type='button';element.addEventListener('click',async()=>{try{await fn();}catch(error){fixture.errors.push(error.message);}});return element;};
const section=(id,label)=>{const element=node('section');element.id=id;element.append(node('h2',label));document.getElementById('host').append(element);return element;};
const api=async(route,payload)=>{fixture.calls.push({route,payload:structuredClone(payload)});
  if(route==='rebar/from-project')return {entrada:structuredClone(state),salida:structuredClone(state)};
  if(route==='rebar/abutment/scene')return {elements:[],bars:[],issues:[],instance_key:payload.instance_key};
  if(route==='rebar/preview')return structuredClone(response);
  throw Error('Unexpected route: '+route);};
await renderRebar({project,api,node,button,section,current:()=>true,notify:message=>fixture.errors.push(message),changed:()=>fixture.changes++,job:()=>{throw Error('CAD is forbidden in this check.');}});
window.ready=true;
</script></body></html>`;

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1360,height:950}}),errors=[];
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
    await page.goto('http://sincal-variable-series.test/');await page.waitForFunction(()=>window.ready);
    const initial=await page.evaluate(()=>structuredClone(fixture.project));
    await page.getByRole('button',{name:'Calcular marcas',exact:true}).click();
    await page.getByRole('button',{name:'Ampliar tabla de marcas',exact:true}).waitFor();
    const mainTable=page.getByRole('table').first();
    assert.equal(await mainTable.locator('tbody tr').count(),fixture.response.marks.length);
    const markButton=mainTable.getByRole('button',{name:variable.mark,exact:true});
    assert.equal(await markButton.count(),1,'The series must keep one mark row.');
    const row=mainTable.locator('tbody tr').filter({has:page.getByRole('button',{name:variable.mark,exact:true})});
    assert.equal(await row.getByRole('cell',{name:range,exact:true}).count(),1);
    assert.equal(await row.getByRole('cell',{name:String(variable.quantity),exact:true}).count(),1);
    assert.equal(await row.getByRole('cell',{name:String(variable.total_length_cm),exact:true}).count(),1);
    assert.notEqual(variable.total_length_cm,variable.quantity*variable.unit_length_cm,
      'Fixture must detect incorrectly treating every piece as the maximum length.');

    async function checkSeriesDialog(dialog){
      await dialog.getByRole('heading',{name:`Marca ${variable.mark} · Zapata`,exact:true}).waitFor();
      assert.equal(await dialog.getByText(`Serie de largos variables · ${range} cm · Una misma marca para toda la serie.`,{exact:true}).count(),1);
      await dialog.getByText('El dibujo representa la pieza de mayor longitud. La lista inferior indica los largos y las cantidades de toda la serie.',{exact:true}).waitFor();
      const image=dialog.getByRole('img',{name:`Serie variable de marca ${variable.mark}; representación de la pieza de mayor longitud: ${Math.max(...lengths)} cm.`,exact:true});
      assert.equal(await image.count(),1);
      assert.equal(await image.getAttribute('data-dimstyle'),'GSG_COTAS');
      const variableDimension=image.locator(`[data-partial="${variablePiece.variable_partial_index}"]`);
      assert.equal(await variableDimension.getByText(partialLabel,{exact:true}).count(),1);
      assert.equal(await image.locator('text').filter({hasText:/^VAR$/}).count(),0);
      const series=dialog.getByRole('table');
      assert.equal(await series.locator('tbody tr').count(),variable.length_variants.length);
      for(let index=0;index<variable.length_variants.length;index++){
        const item=variable.length_variants[index];
        assert.deepEqual(await series.locator('tbody tr').nth(index).getByRole('cell').allTextContents(),
          [String(item.length_cm),String(item.quantity),String(item.length_cm*item.quantity)]);
      }
      await dialog.getByText(`Total de la serie: ${variable.quantity} piezas · ${variable.total_length_cm} cm · ${variable.kg.toFixed(1)} kg.`,{exact:true}).waitFor();
    }

    await markButton.click();await checkSeriesDialog(page.getByRole('dialog'));
    await page.getByRole('dialog').getByRole('button',{name:'Cerrar',exact:true}).click();
    assert.equal(await page.getByRole('dialog').count(),0);
    // A copied table must still open the complete series, not just the scalar.
    await page.getByRole('button',{name:'Ampliar tabla de marcas',exact:true}).click();
    const expanded=page.getByRole('dialog');
    await expanded.getByRole('button',{name:variable.mark,exact:true}).click();
    assert.equal(await page.getByRole('dialog').count(),2);
    await checkSeriesDialog(page.getByRole('dialog').last());
    await page.getByRole('dialog').last().getByRole('button',{name:'Cerrar',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Cerrar tabla',exact:true}).click();
    assert.deepEqual(await page.evaluate(()=>fixture.project),initial,'Viewing a series must not change project data.');
    assert.deepEqual(await page.evaluate(()=>fixture.calls.filter(call=>call.route!=='rebar/abutment/scene').map(call=>call.route)),['rebar/from-project','rebar/preview']);
    const sceneCalls=await page.evaluate(()=>fixture.calls.filter(call=>call.route==='rebar/abutment/scene'));
    assert.equal(sceneCalls.length,1,'The embedded viewer loads automatically without additional calculations.');
    assert.equal(sceneCalls[0].payload.instance_key,'entrada');
    assert.equal(sceneCalls[0].payload.use_state_geometry,true);
    assert.deepEqual(await page.evaluate(()=>fixture.errors),[]);assert.deepEqual(errors,[]);
    console.log('OK: serie variable en una fila y marca; rango, cantidades y largos completos en tabla y despiece; sin CAD ni mutaciones.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
