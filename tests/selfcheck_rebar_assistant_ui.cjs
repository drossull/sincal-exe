// Browser-only contract check. CAD, jobs and project files are mocked.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1360,height:900}}),errors=[],calls=[];
    const completed=new Map();let sequence=0,activeDrawing='Puente.dwg',cancelNextDetection=false;
    page.setDefaultTimeout(10000);
    page.on('pageerror',error=>errors.push(error.message));
    page.on('dialog',dialog=>dialog.accept());
    await page.route('**/*',async route=>{
      const request=route.request(),p=new URL(request.url()).pathname;
      if(p.startsWith('/api/')){
        let data={};
        if(p==='/api/preferences')data={theme:'dark',palette:'sincal',zoom:'100'};
        else if(p==='/api/palettes')data=[];
        else if(p==='/api/modules/pasarela/status')data={installed:false};
        else if(p==='/api/files/choose')data=[{id:'root',name:'Proyecto',path:'C:/Proyecto'}];
        else if(p==='/api/files/project')data={root:{id:'root',path:'C:/Proyecto'},warnings:[],entries:[{name:'puente.json',relative:'puente.json',path:'C:/Proyecto/puente.json',grants:{session:'bridge'}}]};
        else if(p==='/api/files/json')data={value:{bridge:'test'}};
        else if(p==='/api/project/preview')data={warnings:[],sections:[],text:'Proyecto de prueba'};
        else if(p==='/api/rebar/from-project'){
          const state={geometry:{largo_cm:900,ancho_cm:2000,alto_cm:200,esviaje_grados:0},cover:{inferior_cm:7.5,superior_cm:5,lateral_cm:5},rules:[]};
          data={entrada:state,salida:structuredClone(state)};
        }else if(p==='/api/rebar/catalog')data={structures:[
          {key:'abutment',label:'ESTRIBO',folder:'1-ESTRIBO',instances:[{key:'entrada',label:'Estribo de entrada',source_index:0,elements:[
            {key:'abutment.footing',label:'Zapata',folder_path:['1-ESTRIBO','1-1-ZAPATA'],optional:false,present:true,definition_pending:false,layers:['FR','AA','BB','CC','FF'].map(view=>({view,layer:view+'_ZAP',contour:'either',detail:false})),recipes:['orthogonal_mesh','face_bars','u_bars']},
            {key:'abutment.pile',label:'Pilote de estribo',folder_path:['1-ESTRIBO','1-6-PILOTE'],optional:true,present:false,definition_pending:false,layers:[{view:'FR',layer:'FR_PIL',contour:'either',detail:false}],recipes:['longitudinal_bars']},
          ]}]},
          {key:'pier',label:'CEPA',folder:'2-CEPA',instances:[]},
        ]};
        else if(p==='/api/cad/status')data={status:'ready',message:'CAD listo',product:'AutoCAD',version:'2025',active:{name:activeDrawing,path:'C:/Planos/'+activeDrawing,insunits:6}};
        else if(p==='/api/jobs'&&request.method()==='POST'){
          const call=request.postDataJSON(),id='job-'+(++sequence);calls.push(call);
          if(call.operation==='cad-prepare-layers')completed.set(id,{message:'Capas preparadas.',layers:['FR_ZAP','AA_ZAP','BB_ZAP','CC_ZAP','FF_ZAP']});
          else if(call.operation==='cad-detect-element'){
            if(cancelNextDetection){cancelNextDetection=false;completed.set(id,{detection:'cancelled',message:'Selección cancelada.',selection:'cancelled',uses_metres:true,insunits:6,detection_complete:false,generation_ready:false,assignments:{},missing_layers:[],ambiguous_layers:[],curved_layers:[],candidates:[]});}
            else completed.set(id,{detection:'contextual',message:'5 vista(s) asignadas al elemento.',selection:'ok',uses_metres:activeDrawing==='Puente.dwg'?true:undefined,insunits:activeDrawing==='Puente.dwg'?6:null,detection_complete:activeDrawing==='Puente.dwg',generation_ready:activeDrawing==='Puente.dwg',assignments:{FR_ZAP:'A1',AA_ZAP:'A2',BB_ZAP:'A3',CC_ZAP:'A4',FF_ZAP:'A5'},missing_layers:[],ambiguous_layers:[],curved_layers:[],candidates:['FR','AA','BB','CC','FF'].map((view,index)=>({layer:view+'_ZAP',handle:'A'+(index+1),status:'OK',vertex_count:4,area_m2:12,vertices:[[0,0],[1,0],[1,1],[0,1]],closed:true,has_arcs:false}))});
          }
          else if(call.operation==='cad-detect')completed.set(id,{detection:'legacy',candidates:[{layer:'FF_ZAP',handle:'A5',status:'OK',vertex_count:4,area_m2:12}]});
          data={id};
        }else if(/^\/api\/jobs\/job-\d+$/.test(p))data={state:'completed',message:'OK',progress:100,result:completed.get(p.split('/').pop())};
        await route.fulfill({json:data});return;
      }
      const name=p==='/'?'index.html':p.slice(1),file=path.resolve(__dirname,'../sincal/web/static',name);
      if(fs.existsSync(file)&&fs.statSync(file).isFile())await route.fulfill({body:fs.readFileSync(file),contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html'});
      else await route.fulfill({status:404,body:''});
    });

    await page.goto('http://sincal.test/#token=test');
    await page.locator('[data-page="project"]').click();
    await page.getByRole('button',{name:'Abrir carpeta de proyecto',exact:true}).click();
    await page.getByRole('button',{name:'Usar JSON',exact:true}).click();
    await page.locator('[data-page="rebar"]').click();
    await page.getByRole('heading',{name:'Asistente de armaduras',exact:true}).waitFor();
    await page.getByText('1-ESTRIBO · ESTRIBO',{exact:true}).waitFor();
    assert.equal(await page.getByText('2-CEPA · CEPA',{exact:true}).count(),1);
    assert.equal(await page.getByRole('button',{name:/Pilote de estribo.*No aplica/}).count(),1);
    assert.equal(await page.getByText('FF_ZAP',{exact:true}).count(),1);

    await page.getByRole('button',{name:'Preparar capas',exact:true}).click();
    await page.locator('.rebar-assistant-inspector .rebar-state').getByText('Capas listas',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Seleccionar y detectar moldajes',exact:true}).click();
    await page.locator('.rebar-assistant-inspector .rebar-state').getByText('Listo',{exact:true}).waitFor();
    await page.getByText('A5',{exact:true}).waitFor();
    assert.equal(calls[0].operation,'cad-prepare-layers');
    assert.deepEqual(Object.keys(calls[0].payload).sort(),['element_key','expected','instance_key','project','structure_key'].sort());
    assert.equal(calls[1].operation,'cad-detect-element');assert.equal(calls[1].payload.interactive,true);
    assert.equal(calls[1].payload.element_key,'abutment.footing');

    const screenshot=process.env.SINCAL_UI_SCREENSHOT;
    if(screenshot){
      await page.evaluate(()=>scrollTo(0,0));
      await page.screenshot({path:screenshot,fullPage:true});
      await page.setViewportSize({width:850,height:1000});
      await page.evaluate(()=>scrollTo(0,0));
      await page.screenshot({path:screenshot.replace(/\.png$/,'_850.png'),fullPage:true});
      await page.setViewportSize({width:1360,height:900});
    }

    await page.getByRole('button',{name:'Configurar y generar zapata',exact:true}).click();
    await page.getByRole('heading',{name:'Estribos',exact:true}).waitFor();
    const reusedFF=page.locator('label').filter({hasText:'F–F'}).locator('select');await reusedFF.waitFor();assert.equal(await reusedFF.inputValue(),'A5');
    assert.equal(calls.filter(call=>call.operation==='cad-detect').length,0);
    await page.locator('[data-page="rebar"]').click();
    await page.locator('.rebar-assistant-inspector .rebar-state').getByText('Listo',{exact:true}).waitFor();

    cancelNextDetection=true;
    await page.getByRole('button',{name:'Seleccionar y detectar moldajes',exact:true}).click();
    await page.locator('.rebar-assistant-inspector .rebar-state').getByText('Pendiente',{exact:true}).waitFor();
    assert.equal(await page.getByText('A5',{exact:true}).count(),0);
    await page.getByRole('button',{name:'Seleccionar y detectar moldajes',exact:true}).click();
    await page.locator('.rebar-assistant-inspector .rebar-state').getByText('Listo',{exact:true}).waitFor();

    activeDrawing='Otro.dwg';
    await page.getByRole('button',{name:'Preparar capas',exact:true}).click();
    await page.locator('.rebar-assistant-inspector .rebar-state').getByText('Capas listas',{exact:true}).waitFor();
    assert.equal(await page.getByText('A5',{exact:true}).count(),0);
    await page.getByRole('button',{name:'Seleccionar y detectar moldajes',exact:true}).click();
    await page.locator('.rebar-assistant-inspector .rebar-state').getByText('Revisar',{exact:true}).waitFor();
    await page.locator('.rebar-assistant-inspector').getByText('No se pudieron verificar las unidades del dibujo.',{exact:false}).waitFor();

    await page.locator('[data-page="project"]').click();
    await page.getByRole('button',{name:'Usar JSON',exact:true}).click();
    await page.locator('[data-page="rebar"]').click();
    await page.locator('.rebar-assistant-inspector .rebar-state').getByText('Pendiente',{exact:true}).waitFor();
    assert.equal(await page.getByText('A5',{exact:true}).count(),0);

    await page.getByRole('button',{name:/Pilote de estribo.*No aplica/}).click();
    assert(await page.getByRole('button',{name:'Preparar capas',exact:true}).isDisabled());
    await page.getByText('Elemento opcional no activado por el JSON.',{exact:true}).waitFor();
    await page.getByRole('button',{name:/Zapata.*Pendiente/}).click();
    await page.getByRole('button',{name:'Configurar y generar zapata',exact:true}).click();
    await page.getByRole('heading',{name:'Estribos',exact:true}).waitFor();
    await page.getByRole('button',{name:'Detectar moldajes',exact:true}).click();
    await page.locator('label').filter({hasText:'F–F'}).locator('select').waitFor();
    assert.equal(await page.locator('label').filter({hasText:'E–E'}).count(),0);
    assert.deepEqual(errors,[]);
    console.log('OK: catálogo dinámico, opcionales, capas, contexto CAD y vista FF_ZAP del asistente híbrido.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
