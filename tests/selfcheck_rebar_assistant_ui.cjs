// Browser-only contract check. CAD, jobs and project files are mocked.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1360,height:900}}),errors=[],calls=[];
    const jobPolls=new Map(),jobResults=new Map();let sequence=0,cadStatusCalls=0,previewDelay=0,nextJobResult={selection:'ok',references_count:3,references:[{element:'footing',corners:[[0,1],[2,0]]}]};
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
        else if(p==='/api/files/json')data={value:{bridge:'test',abutments:[{name:'entrada'}],estribos:{tipo_estribo_entrada:'muro_lleno',orientacion_dado_estribo_entrada:'rectangular_rotado',tipo_estribo_salida:'transparente',orientacion_dado_estribo_salida:'rectangular'}}};
        else if(p==='/api/project/preview')data={warnings:[],sections:[],text:'Proyecto de prueba'};
        else if(p==='/api/rebar/from-project'){
          const state={geometry:{largo_cm:900,ancho_cm:2000,alto_cm:200,esviaje_grados:10},cover:{inferior_cm:7.5,superior_cm:5,lateral_cm:5},rules:[]};
          data={entrada:state,salida:structuredClone(state)};
        }else if(p==='/api/rebar/catalog')data={structures:[
          {key:'abutment',label:'ESTRIBO',folder:'1-ESTRIBO',instances:[{key:'entrada',label:'Estribo de entrada',source_index:0,elements:[
            {key:'abutment.footing',label:'Zapata',folder_path:['1-ESTRIBO','1-1-ZAPATA'],optional:false,present:true,views:['FR','AA','BB','CC','EE'],layers:[{view:'FF',layer:'FF_ZAP'}],recipes:['orthogonal_mesh','face_bars','u_bars']},
            {key:'abutment.front_wall',label:'Muro frontal',folder_path:['1-ESTRIBO','1-2-MFRONTAL'],optional:false,present:true,views:['FR'],layers:[{view:'FR',layer:'FR_MFR'}],recipes:['face_bars']},
            {key:'abutment.pile',label:'Pilote de estribo',folder_path:['1-ESTRIBO','1-6-PILOTE'],optional:true,present:false,layers:[{view:'FR',layer:'FR_PIL'}],recipes:['longitudinal_bars']},
          ]}]},
          {key:'pier',label:'CEPA',folder:'2-CEPA',instances:[{key:'cepa-1',label:'Cepa 1',elements:[{key:'pier.cap',label:'Cabezal',present:true,layers:[{view:'FR',layer:'FR_CAB'}],recipes:[]}]}]},
          {key:'beam',label:'VIGA',folder:'3-VIGA',instances:[{key:'viga-1',label:'Viga 1',elements:[{key:'beam.main',label:'Viga',present:true,layers:[{view:'EL',layer:'EL_VIG'}],recipes:[]}]}]},
          {key:'crossbeam',label:'TRAVESAÑO',folder:'4-TRAVESAÑO',instances:[{key:'apoyo-1',label:'Sobre apoyos',elements:[{key:'crossbeam.support',label:'Travesaño sobre apoyos',present:true,layers:[{view:'FR',layer:'FR_TRAV'}],recipes:[]}]}]},
          {key:'slab',label:'LOSA',folder:'5-LOSA',instances:[{key:'losa-1',label:'Losa',elements:[{key:'slab.main',label:'Losa',present:true,layers:[{view:'PLAN',layer:'PLAN_LOS'}],recipes:[]}]}]},
        ]};
        else if(p==='/api/rebar/preview'){
          if(previewDelay)await new Promise(resolve=>setTimeout(resolve,previewDelay));
          data={issues:[],valid:true,total_kg:0,marks:[],details:[]};
        }else if(p==='/api/cad/status'){
          cadStatusCalls++;
          data={status:'ready',message:'CAD listo',product:'AutoCAD',version:'2025',active:{name:'Puente.dwg',path:'C:/Planos/Puente.dwg',insunits:6}};
        }else if(p==='/api/jobs'&&request.method()==='POST'){
          const call=request.postDataJSON(),id='job-'+(++sequence);calls.push(call);jobPolls.set(id,0);jobResults.set(id,nextJobResult);nextJobResult={selection:'ok',references_count:1};data={id};
        }else if(/^\/api\/jobs\/job-\d+$/.test(p)){
          const id=p.split('/').pop(),polls=jobPolls.get(id)||0;jobPolls.set(id,polls+1);
          data=polls===0?{state:'running',message:'Selecciona las referencias en CAD',progress:null}:{state:'completed',message:'OK',progress:100,result:jobResults.get(id)};
        }
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
    for(const heading of ['1-ESTRIBO · ESTRIBO','2-CEPA · CEPA','3-VIGA · VIGA','4-TRAVESAÑO · TRAVESAÑO','5-LOSA · LOSA'])assert.equal(await page.getByText(heading,{exact:true}).count(),1);
    assert.equal(await page.getByRole('button',{name:/Pilote de estribo.*No aplica/}).count(),1);
    assert.equal(await page.getByRole('button',{name:/Muro frontal.*Cálculo pendiente/}).count(),1);
    await page.getByText('Planta E–E · EE',{exact:true}).waitFor();
    await page.getByText('El JSON define qué elementos pedir en cada vista. CAD solicita dos esquinas para una referencia rectangular y tres puntos sólo para una planta E–E romboide con esviaje; SINCAL valida esas referencias contra las dimensiones del JSON antes de insertar.',{exact:true}).waitFor();
    assert.equal(await page.getByText('F–F · FF',{exact:true}).count(),0);
    for(const forbidden of ['FR_ZAP','Capas esperadas','Preparar capas','Detectar moldajes','Seleccionar y detectar moldajes'])assert.equal(await page.getByText(forbidden,{exact:true}).count(),0);

    await page.getByRole('button',{name:/Muro frontal.*Cálculo pendiente/}).click();
    await page.getByText('La estructura está identificada desde el JSON, pero su cálculo y sus controles de inserción aún no están disponibles.',{exact:true}).waitFor();
    await page.getByText('Naturaleza y distribución pendientes de definición.',{exact:true}).waitFor();
    assert.equal(await page.locator('.rebar-assistant-inspector').getByText('Barras de cara',{exact:true}).count(),0);
    assert.equal(await page.locator('.rebar-assistant-inspector').getByText('Armaduras previstas',{exact:true}).count(),0);
    await page.getByRole('button',{name:/Zapata.*Configurable/}).click();
    await page.locator('.rebar-assistant-inspector').getByText('Barras de cara',{exact:true}).waitFor();

    const screenshot=process.env.SINCAL_UI_SCREENSHOT;
    if(screenshot){
      await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:screenshot,fullPage:true});
      await page.setViewportSize({width:850,height:1000});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:screenshot.replace(/\.png$/,'_850.png'),fullPage:true});
      await page.setViewportSize({width:1360,height:900});
    }

    await page.getByRole('button',{name:'Configurar y calcular zapata',exact:true}).click();
    await page.getByRole('heading',{name:'Estribos',exact:true}).waitFor();
    await page.getByRole('button',{name:'Calcular marcas',exact:true}).waitFor();
    const viewButtons=['Insertar Frontal (FR)','Insertar A–A','Insertar B–B','Insertar C–C','Insertar planta (E–E)'].map(name=>page.getByRole('button',{name,exact:true}));
    for(const control of viewButtons){assert.equal(await control.count(),1);assert(await control.isDisabled());}
    assert(await page.getByRole('button',{name:'Generar despiece general',exact:true}).isDisabled());
    assert.equal(cadStatusCalls,0);
    const drawingUnits=page.locator('label').filter({hasText:'Unidades del dibujo CAD'}).locator('select');assert.equal(await drawingUnits.inputValue(),'auto');await drawingUnits.selectOption('mm');

    previewDelay=200;
    await page.getByRole('button',{name:'Calcular marcas',exact:true}).click();
    await page.getByLabel('Largo',{exact:true}).fill('950');
    await page.getByText('Parámetros modificados. Pulsa Calcular marcas para actualizar.',{exact:true}).waitFor();
    await page.waitForTimeout(300);
    assert(await page.getByRole('button',{name:'Insertar planta (E–E)',exact:true}).isDisabled());
    assert.equal(await page.getByRole('heading',{name:/^3\. Marcas/}).count(),0);

    previewDelay=0;
    await page.getByRole('button',{name:'Calcular marcas',exact:true}).click();
    await page.getByRole('heading',{name:/^3\. Marcas/}).waitFor();
    assert(await page.getByRole('button',{name:'Insertar planta (E–E)',exact:true}).isEnabled());
    assert(await page.getByRole('button',{name:'Generar despiece general',exact:true}).isEnabled());
    assert.equal(cadStatusCalls,0);

    await page.getByLabel('Largo',{exact:true}).fill('960');
    assert(await page.getByRole('button',{name:'Insertar planta (E–E)',exact:true}).isDisabled());
    await page.getByRole('button',{name:'Calcular marcas',exact:true}).click();
    await page.getByRole('heading',{name:/^3\. Marcas/}).waitFor();
    await page.getByRole('button',{name:'Insertar planta (E–E)',exact:true}).click();
    await page.locator('#notice').getByText('En CAD sigue la guía para indicar tres puntos por cada elemento de la planta E–E romboide. SINCAL validará las dimensiones contra el JSON antes de insertar.',{exact:true}).waitFor();
    await page.locator('#activity').waitFor({state:'hidden'});
    await page.locator('#notice').getByText('Vista planta (E–E) insertada. Se seleccionaron 3 referencias; sólo la zapata se generó y las demás armaduras siguen pendientes.',{exact:true}).waitFor();

    assert.equal(cadStatusCalls,1);
    assert.equal(calls.length,1);
    assert.equal(calls[0].operation,'cad-rebar');
    assert.deepEqual(Object.keys(calls[0].payload).sort(),['abutment','drawing_units','expected','project','selection_mode','state','view'].sort());
    assert.equal(calls[0].payload.abutment,'entrada');
    assert.equal(calls[0].payload.view,'EE');
    assert.equal(calls[0].payload.selection_mode,'geometry');
    assert.equal(calls[0].payload.drawing_units,'mm');
    assert.deepEqual(calls[0].payload.project,{bridge:'test',abutments:[{name:'entrada'}],estribos:{tipo_estribo_entrada:'muro_lleno',orientacion_dado_estribo_entrada:'rectangular_rotado',tipo_estribo_salida:'transparente',orientacion_dado_estribo_salida:'rectangular'}});
    assert.equal('handle' in calls[0].payload,false);
    assert.equal('detection' in calls[0].payload,false);
    assert.equal(calls.some(call=>call.operation.includes('detect')),false);
    assert(await page.getByRole('button',{name:'Generar despiece general',exact:true}).isEnabled());

    nextJobResult={selection:'cancelled',references_count:0};
    await page.getByRole('button',{name:'Insertar A–A',exact:true}).click();
    await page.locator('#notice').getByText('En CAD indica la esquina superior izquierda e inferior derecha de cada elemento solicitado para la vista A–A. SINCAL validará las dimensiones contra el JSON antes de insertar.',{exact:true}).waitFor();
    await page.locator('#activity').waitFor({state:'hidden'});
    await page.locator('#notice').getByText('Selección cancelada para la vista A–A. No se insertó armadura.',{exact:true}).waitFor();
    assert.equal(cadStatusCalls,2);assert.equal(calls.length,2);

    await page.getByRole('button',{name:'Estribo de salida',exact:true}).click();
    await page.getByRole('heading',{name:'Estribo de salida',exact:true}).waitFor();
    await page.getByRole('button',{name:'Calcular marcas',exact:true}).click();
    await page.getByRole('heading',{name:/^3\. Marcas/}).waitFor();
    await page.getByRole('button',{name:'Insertar planta (E–E)',exact:true}).click();
    await page.locator('#notice').getByText('En CAD indica la esquina superior izquierda e inferior derecha de cada elemento solicitado para la vista planta (E–E). SINCAL validará las dimensiones contra el JSON antes de insertar.',{exact:true}).waitFor();
    await page.locator('#activity').waitFor({state:'hidden'});
    assert.equal(cadStatusCalls,3);assert.equal(calls.length,3);
    assert.equal(calls[2].payload.abutment,'salida');assert.equal(calls[2].payload.view,'EE');
    assert.deepEqual(errors,[]);
    console.log('OK: catálogo sin capas, cálculo vigente y referencias de 2/3 puntos independientes por vista.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
