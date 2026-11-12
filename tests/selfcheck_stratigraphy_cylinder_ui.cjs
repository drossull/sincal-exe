// Real HTTP assets and preview API, private session. CAD is only a captured intent.
const {chromium}=require('playwright');
const {spawn,execFileSync}=require('node:child_process');
const assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
  const cwd=path.resolve(__dirname,'..'),env={...process.env,PYTHONUTF8:'1'},python=process.env.SINCAL_PYTHON||'python';
  const reports=JSON.parse(execFileSync(python,['-c',`import ast,json
from pathlib import Path
from sincal.stratigraphy_octay import parse_individual_report
fixture=ast.parse(Path('tests/test_stratigraphy_octay.py').read_text(encoding='utf-8'))
pages=ast.literal_eval(next(n.value for n in fixture.body if isinstance(n,ast.Assign) and any(getattr(t,'id',None)=='PAGES' for t in n.targets)))
reports=[parse_individual_report([p.replace('S-08',f'S-{i:02d}').replace('S-8 Fecha',f'S-{i} Fecha') for p in pages],f'S{i}.pdf',str(i)*64).to_dict() for i in (7,8)]
print(json.dumps(reports))`],{cwd,env,encoding:'utf8'}));
  const child=spawn(python,['-u','-c',`import sys,threading
from tempfile import TemporaryDirectory
from pathlib import Path
from sincal.web.server import Server
with TemporaryDirectory(prefix='sincal-cylinder-ui-') as folder:
 with Server(0,Path(folder)) as server:
  threading.Thread(target=server.serve_forever,daemon=True).start()
  print(server.origin+'/#token='+server.token,flush=True)
  sys.stdin.readline()
  server.shutdown()`],{cwd,env,stdio:['pipe','pipe','pipe']});
  let browser,stderr='';child.stderr.on('data',data=>{stderr=(stderr+data).slice(-8000);});
  try{
    const url=await new Promise((resolve,reject)=>{
      let output='';const timer=setTimeout(()=>reject(Error('Private server startup timed out: '+stderr)),20000);
      const fail=error=>{clearTimeout(timer);reject(error);};
      child.once('error',fail);child.once('exit',code=>fail(Error('Private server exit '+code+': '+stderr)));
      child.stdout.on('data',data=>{output+=data;if(output.includes('\n')){clearTimeout(timer);resolve(output.split('\n')[0].trim());}});
    });
    browser=await chromium.launch({channel:'msedge',headless:true});
    const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true}),errors=[],failed=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('response',response=>{if(response.status()>=400)failed.push([new URL(response.url()).pathname,response.status()]);});
    await page.goto(url);await page.locator('#sidebar button[data-page="project"]').waitFor();await page.locator('#main h2').first().waitFor();
    await page.evaluate(async reports=>{
      const {renderStratigraphy}=await import('/stratigraphy.js');
      const token=sessionStorage.getItem('sincal-local-token');
      window.cylinderQA={project:{stratigraphy:{report:reports[0],library:reports.slice(1)}},requests:[],jobs:[],notices:[],changes:0};
      const qa=window.cylinderQA,node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
      const button=(text,action)=>{const e=node('button',text);e.onclick=async()=>{try{await action();}catch(error){qa.notices.push(error.message);}};return e;};
      const section=(id,title)=>{const e=node('section');e.id=id;e.append(node('h2',title));document.querySelector('#main').append(e);return e;};
      window.mountCylinderQA=async()=>{
        document.querySelector('#main').replaceChildren();
        await renderStratigraphy({node,button,section,project:qa.project,current:()=>true,changed:()=>qa.changes++,notify:text=>qa.notices.push(text),
          api:async(route,payload)=>{
            if(route==='cad/status')return {status:'ready',instance:'qa-only',active:{name:'No-CAD-connection.dwg',insunits:6,annotation_scale:{name:'1:200 (m)',value:5}}};
            if(route==='files/choose')return [{id:'qa-report'}];
            if(route!=='stratigraphy/preview')throw Error('Unexpected API '+route);
            qa.requests.push(structuredClone(payload));
            const response=await fetch('/api/'+route,{method:'POST',headers:{'X-Sincal-Token':token,'Content-Type':'application/json'},body:JSON.stringify(payload)});
            const value=await response.json();if(!response.ok)throw Error(value.error);return value;
          },job:async(operation,payload)=>{
            if(operation==='stratigraphy')return {reports:structuredClone(reports)};
            if(operation!=='cad-stratigraphy')throw Error('Unexpected job '+operation);
            qa.jobs.push(structuredClone(payload));return {message:'Captured CAD intent only'};
          }});
      };
      await window.mountCylinderQA();
    },reports);
    const mode=page.getByRole('combobox',{name:'Salida de estratigrafía',exact:true});
    const tables=page.getByLabel('Incluir tablas de valores debajo del gráfico',{exact:true});
    const lastRequest=()=>page.evaluate(()=>window.cylinderQA.requests.at(-1));
    const waitPreview=async()=>page.waitForFunction(()=>{
      const qa=window.cylinderQA,request=qa.requests.at(-1),scene=qa.project.stratigraphy.checks?.[0]?.scene;
      return scene&&((request.output_mode==='isometric-cylinder')===scene.items.some(item=>item.kind==='ellipse'));
    });
    assert.equal(await mode.inputValue(),'full');assert.equal((await lastRequest()).output_mode,'full');
    await tables.check();
    await page.waitForFunction(()=>window.cylinderQA.requests.at(-1).table===true);
    await mode.selectOption('isometric-cylinder');await waitPreview();
    assert.equal(await tables.isDisabled(),true);assert.equal(await tables.isChecked(),false);
    assert.equal((await lastRequest()).table,false);
    assert.equal(await page.locator('.stratigraphy-preview clipPath').count()>0,true);
    assert.equal(await page.locator('.stratigraphy-preview path[clip-path]').count()>0,true);
    assert(!/NaN|undefined|Infinity/.test(await page.locator('.stratigraphy-preview').innerHTML()));
    await mode.selectOption('full');await waitPreview();
    assert.equal(await tables.isDisabled(),false);assert.equal(await tables.isChecked(),true);
    assert.equal((await lastRequest()).table,true);
    await mode.selectOption('isometric-cylinder');await waitPreview();
    await page.getByRole('combobox',{name:'Informe de estratigrafía',exact:true}).selectOption('1');
    await page.waitForFunction(()=>window.cylinderQA.project.stratigraphy.report.boreholes[0].name==='S-08'&&window.cylinderQA.project.stratigraphy.checks?.[0]?.scene);
    assert.equal(await mode.inputValue(),'isometric-cylinder');assert.equal((await lastRequest()).table,false);
    await page.getByRole('button',{name:'Añadir informes de Proyecto',exact:true}).click();
    await page.waitForFunction(()=>window.cylinderQA.project.stratigraphy.checks?.[0]?.scene);
    assert.equal(await mode.inputValue(),'isometric-cylinder');
    await page.evaluate(async()=>{
      window.cylinderQA.project=JSON.parse(JSON.stringify(window.cylinderQA.project));await window.mountCylinderQA();
    });
    assert.equal(await mode.inputValue(),'isometric-cylinder');await waitPreview();
    assert.equal(await page.evaluate(()=>Object.hasOwn(window.cylinderQA.project.stratigraphy.report,'output_mode')),false);
    const downloadEvent=page.waitForEvent('download');await page.getByRole('button',{name:'Guardar reconocimiento',exact:true}).click();
    const stream=await(await downloadEvent).createReadStream(),chunks=[];for await(const chunk of stream)chunks.push(chunk);
    const saved=JSON.parse(Buffer.concat(chunks));assert.equal(saved.schema,'sincal-stratigraphy-2');assert.equal(saved.output_mode,'isometric-cylinder');
    assert(saved.reports.every(report=>!Object.hasOwn(report,'output_mode')));
    await page.getByLabel('He cotejado',{exact:false}).check();
    page.once('dialog',async dialog=>{assert(dialog.message().includes('Salida: Solo cilindro isométrico'));assert(dialog.message().includes('1:200 (m)'));await dialog.accept();});
    await page.getByRole('button',{name:'Insertar este sondaje en AutoCAD / ZWCAD',exact:true}).click();
    await page.waitForFunction(()=>window.cylinderQA.jobs.length===1);
    const insertion=await page.evaluate(()=>window.cylinderQA.jobs[0]);
    assert.equal(insertion.output_mode,'isometric-cylinder');assert.equal(insertion.table,false);assert.equal(insertion.expected.active.annotation_scale.value,5);
    if(process.env.SINCAL_UI_SCREENSHOT){
      await page.locator('.stratigraphy-preview').evaluate(element=>element.scrollIntoView({block:'center'}));
      await page.locator('.stratigraphy-preview').screenshot({path:process.env.SINCAL_UI_SCREENSHOT});
    }
    assert.deepEqual(await page.evaluate(()=>window.cylinderQA.notices),['Captured CAD intent only']);
    assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
    console.log('OK: actual HTTP elliptical preview, default full mode, table restoration, mode across reports/navigation/JSON, and confirmed cylinder CAD payload without CAD access.');
  }finally{
    if(browser)await browser.close();
    if(child.exitCode===null){child.stdin.end('stop\n');await new Promise(resolve=>{const timer=setTimeout(()=>{child.kill();resolve();},5000);child.once('exit',()=>{clearTimeout(timer);resolve();});});}
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
