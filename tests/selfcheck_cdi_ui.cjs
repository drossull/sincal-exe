// Integration check against the real HTTP static allowlist and preview API.
// Uses only a private temporary server/session, never the installed app or CAD.
// Set SINCAL_TEST_RUTA29_FOLDER to the folder containing the two private PDFs.
const {chromium}=require('playwright');
const {spawn,execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const path=require('node:path');

(async()=>{
  if(!process.env.SINCAL_TEST_RUTA29_FOLDER){
    console.log('SKIP: set SINCAL_TEST_RUTA29_FOLDER for the private CDI S-1/S-2 PDF integration check.');
    return;
  }
  const cwd=path.resolve(__dirname,'..'),python=process.env.SINCAL_PYTHON||'python';
  const env={...process.env,PYTHONUTF8:'1'};
  const fixture=JSON.parse(execFileSync(python,['-c',`import json,os
from pathlib import Path
from sincal.stratigraphy import read_report
folder=Path(os.environ['SINCAL_TEST_RUTA29_FOLDER'])
reports=[read_report(folder/f'ITS Enlace Ruta 29 S-{n} def.pdf').to_dict() for n in (1,2)]
print(json.dumps(reports,ensure_ascii=False))`],{cwd,env,encoding:'utf8',maxBuffer:128*1024*1024}));
  assert.equal(fixture.length,2);
  for(const [i,report]of fixture.entries()){
    assert.equal(report.boreholes.length,1);
    const hole=report.boreholes[0];
    assert.equal(hole.name,`S-${i+1}`);
    assert.equal(hole.horizons.length,15);
    assert.equal(hole.drilling_records.length,[40,79][i]);
    assert.equal(hole.tests.length,[37,39][i]);
  }
  const child=spawn(python,['-u','-c',`import sys,threading
from tempfile import TemporaryDirectory
from pathlib import Path
from sincal.web.server import Server
with TemporaryDirectory(prefix='sincal-cdi-ui-') as folder:
 with Server(0,Path(folder)) as server:
  threading.Thread(target=server.serve_forever,daemon=True).start()
  print(server.origin+'/#token='+server.token,flush=True)
  sys.stdin.readline()
  server.shutdown()`],{cwd,env,stdio:['pipe','pipe','pipe']});
  let browser,stderr='';
  child.stderr.on('data',data=>{stderr=(stderr+data.toString()).slice(-12000);});
  try{
    const url=await new Promise((resolve,reject)=>{
      let output='';
      const timer=setTimeout(()=>reject(Error('Private HTTP server startup timed out. '+stderr)),20000);
      const fail=error=>{clearTimeout(timer);reject(error);};
      child.once('error',fail);
      child.once('exit',code=>fail(Error('Private HTTP server exited '+code+'. '+stderr)));
      child.stdout.on('data',data=>{
        output+=data.toString();
        if(output.includes('\n')){clearTimeout(timer);resolve(output.split('\n')[0].trim());}
      });
    });
    browser=await chromium.launch({channel:'msedge',headless:true});
    const page=await browser.newPage({viewport:{width:1440,height:1100}});
    const errors=[],failed=[],requests=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('response',response=>{
      if(response.status()>=400)failed.push([new URL(response.url()).pathname,response.status()]);
    });
    page.on('request',request=>requests.push({path:new URL(request.url()).pathname,method:request.method()}));
    // No page.route(): imports, styles and API responses all come from the server.
    await page.goto(url);
    await page.locator('#sidebar button[data-page="project"]').waitFor();
    await page.locator('#main h2').first().waitFor();
    await page.evaluate(async reports=>{
      const {renderStratigraphy}=await import('/stratigraphy.js');
      const main=document.querySelector('#main');main.replaceChildren();
      const token=sessionStorage.getItem('sincal-local-token');
      const node=(tag,text,cls)=>{
        const element=document.createElement(tag);
        if(text!==undefined)element.textContent=text;
        if(cls)element.className=cls;
        return element;
      };
      window.cdiQa={project:{stratigraphy:{report:reports[0],library:reports.slice(1)}},notifications:[],changes:0,previewCalls:0,jobs:[]};
      const qa=window.cdiQa;
      const button=(text,action)=>{
        const element=node('button',text);
        element.onclick=async()=>{try{await action();}catch(error){qa.notifications.push(error.message);}};
        return element;
      };
      const section=(id,title)=>{
        const element=node('section');element.id=id;element.append(node('h2',title));main.append(element);return element;
      };
      await renderStratigraphy({node,button,section,project:qa.project,current:()=>true,
        changed:()=>{qa.changes++;},notify:text=>qa.notifications.push(text),
        api:async(route,payload)=>{
          if(route!=='stratigraphy/preview')throw Error('No CAD or installed-session access is allowed in this test: '+route);
          qa.previewCalls++;
          const response=await fetch('/api/'+route,{method:'POST',headers:{'X-Sincal-Token':token,'Content-Type':'application/json'},body:JSON.stringify(payload)});
          const result=await response.json();
          if(!response.ok)throw Error(result.error||'Preview failed');
          return result;
        },
        job:async(op,payload)=>{qa.jobs.push(op);throw Error('No jobs may run in this read-only UI check.');}
      });
    },fixture);

    const reportSelect=page.getByRole('combobox',{name:'Informe de estratigrafía',exact:true});
    const details=label=>page.getByText(label,{exact:true}).locator('..');
    async function verifySelected(name,recoveryCount,sptCount){
      await page.waitForFunction(name=>{
        const state=window.cdiQa?.project.stratigraphy;
        return state?.report.boreholes[0].name===name&&state.checks?.[0]?.scene?.format==='cdi-spt-v1';
      },name);
      assert.equal(await reportSelect.locator('option').count(),2);
      const company=page.locator('.study-information');
      assert.equal(await company.count(),1);
      assert.match(await company.innerText(),/CDI/);
      assert.match(await company.innerText(),/no se inserta en AutoCAD \/ ZWCAD/);
      assert.equal(await company.locator('input,textarea,button,select,[contenteditable="true"]').count(),0);
      const horizons=details('Intervalos de perforación y asignación de hatch (revisar)');
      const recovery=details('Pasadas y recuperación — no son los límites de los estratos');
      const spt=details('Tabla oficial NSPT — no es la recuperación');
      assert.equal(await horizons.locator('tbody tr').count(),15);
      assert.equal(await recovery.locator('tbody tr').count(),recoveryCount);
      assert.equal(await spt.locator('tbody tr').count(),sptCount);
      assert((await recovery.locator('th').allTextContents()).includes('Recuperado m'));
      assert((await spt.locator('th').allTextContents()).includes('Long. muestra cm'));
      assert(!(await spt.locator('th').allTextContents()).some(text=>/^Recuperado/.test(text)));
      assert.equal(await page.locator('.stratigraphy-preview').count(),1);
      assert.equal(await page.getByRole('button',{name:'Insertar este sondaje en AutoCAD / ZWCAD',exact:true}).isDisabled(),true);
      const state=await page.evaluate(()=>{
        const current=window.cdiQa.project.stratigraphy,hole=current.report.boreholes[0],check=current.checks[0];
        return {warnings:check.warnings,errors:check.errors,scene:check.scene,study:hole.study_info,
          svg:document.querySelector('.stratigraphy-preview').outerHTML};
      });
      assert.deepEqual(state.errors,[]);
      assert.equal(state.scene.depth,40);
      assert(!/NaN|undefined|Infinity/.test(state.svg));
      const labels=state.scene.items.filter(item=>item.kind==='text').map(item=>item.text).join('\n');
      for(const key of ['company','email','address','phone','website']){
        if(state.study[key])assert(!labels.includes(state.study[key]),'Consultation-only '+key+' leaked into CAD scene labels');
      }
      return state;
    }

    await verifySelected('S-1',40,37);
    await reportSelect.selectOption('1');
    const second=await verifySelected('S-2',79,39);
    assert(second.warnings.some(text=>/35(?:\.00)?\s*m/.test(text)&&/40\s*m/.test(text)&&/no se extrapola/i.test(text)));
    const secondSpt=details('Tabla oficial NSPT — no es la recuperación');
    const reject20=secondSpt.locator('tbody tr').filter({has:page.getByText('59R',{exact:true})});
    assert.equal(await reject20.count(),1);
    assert((await reject20.locator('td').allTextContents()).includes('20.00'));
    assert((await reject20.locator('td').allTextContents()).includes('R'));
    // Exercise the real endpoint with optional documentary tables as well.
    await page.getByLabel('Incluir tablas de valores debajo del gráfico',{exact:true}).check();
    await page.waitForFunction(()=>window.cdiQa.project.stratigraphy.checks[0].scene.items.some(item=>item.kind==='text'&&item.text==='LONG. CM'));
    const withTables=await verifySelected('S-2',79,39);
    assert(withTables.scene.items.some(item=>item.kind==='text'&&item.text==='PRESIÓN PSI'));
    await page.getByLabel('Incluir tablas de valores debajo del gráfico',{exact:true}).uncheck();
    await page.waitForFunction(()=>!window.cdiQa.project.stratigraphy.checks[0].scene.items.some(item=>item.kind==='text'&&item.text==='LONG. CM'));
    if(process.env.SINCAL_UI_SCREENSHOT){
      await page.evaluate(()=>new Promise(resolve=>{
        window.scrollTo(0,0);requestAnimationFrame(()=>requestAnimationFrame(resolve));
      }));
      await page.screenshot({path:process.env.SINCAL_UI_SCREENSHOT,fullPage:true});
    }
    // Switching back must retain both reports, including their separate provenance.
    await reportSelect.selectOption('1');
    await verifySelected('S-1',40,37);
    assert.deepEqual(await page.evaluate(()=>window.cdiQa.notifications),[]);
    assert.deepEqual(await page.evaluate(()=>window.cdiQa.jobs),[]);
    assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
    assert(requests.some(request=>request.path==='/stratigraphy.js'));
    assert(requests.some(request=>request.path==='/study_info.js'));
    assert(requests.filter(request=>request.path==='/api/stratigraphy/preview').length>=5);
    assert(!requests.some(request=>request.path==='/api/jobs'&&request.method==='POST'));
    console.log('OK: real HTTP CDI S-1/S-2, report selector, 15 horizons each, 40/79 recovery rows, 37/39 SPT, read-only company metadata excluded from CAD scenes, 35–40 m warning, and no JS/HTTP errors.');
  }finally{
    if(browser)await browser.close();
    if(child.exitCode===null){
      child.stdin.end('stop\n');
      await new Promise(resolve=>{
        const timer=setTimeout(()=>{child.kill();resolve();},5000);
        child.once('exit',()=>{clearTimeout(timer);resolve();});
      });
    }
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
