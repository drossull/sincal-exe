// Guided, project-aware entry point for the hybrid reinforcement workflow.
// CAD commands and catalog resolution remain in Python; this module only
// presents their state and sends an explicit structural context with each job.

const STATUS_LABELS={
  pending:'Pendiente',
  prepared:'Capas listas',
  detected:'Detectado',
  ready:'Listo',
  needs_input:'Revisar',
  not_applicable:'No aplica',
  error:'Error',
};

const RECIPE_LABELS={
  parallel_bars:'Barras paralelas',
  orthogonal_mesh:'Malla ortogonal',
  u_bars:'Barras en U',
  longitudinal_bars:'Barras longitudinales',
  closed_stirrups:'Estribos cerrados',
  transverse_ties:'Amarras transversales',
  face_bars:'Barras de cara',
  edge_bars:'Barras de borde',
  additional_bars:'Refuerzos adicionales',
};

const CONTOUR_LABELS={open:'Abierta',closed:'Cerrada',either:'Abierta o cerrada'};

function array(value){return Array.isArray(value)?value:[];}
function elementId(structure,instance,element){return `${structure.key}:${instance.key}:${element.key}`;}
function assignmentHandle(value){return typeof value==='string'?value:String(value?.handle||'');}

function initialState(element){
  if(element.present===false)return {status:'not_applicable',message:'El JSON no activa este elemento opcional.'};
  if(element.definition_pending||!array(element.layers).length)return {status:'needs_input',message:'Falta definir las capas de moldaje de este elemento.'};
  return {status:'pending',message:'Pendiente de analizar en el dibujo activo.'};
}

function describeCandidate(candidate){
  const vertices=Number(candidate.vertex_count)||array(candidate.vertices).length;
  const area=Number(candidate.area_m2)||0;
  const shape=candidate.closed===true?'cerrada':candidate.closed===false?'abierta':'cierre sin informar';
  const curve=candidate.has_arcs?' · contiene arcos':'';
  return `${candidate.handle||'Sin handle'} · ${vertices} vértices · ${area.toFixed(2)} m² · ${shape}${curve} · ${candidate.status||'sin estado'}`;
}

export async function renderRebarAssistant(ctx){
  const {project,api,node,button,section,notify,job,current}=ctx;
  const dashboard=section('asistente-armaduras','Asistente de armaduras');
  dashboard.append(node('p','Selecciona un elemento del puente. SINCAL propone sus capas por nombre y tú confirmas los moldajes directamente en CAD.'));
  if(!project?.data||!Object.keys(project.data).length){
    dashboard.append(node('p','Incorpora el JSON del puente para construir la lista real de estribos, cepas, vigas, travesaños y losas.','badge'));
    return;
  }

  const loading=node('p','Leyendo la estructura del proyecto…','badge');dashboard.append(loading);
  let catalog;
  try{catalog=await api('rebar/catalog',project.data);}
  catch(error){
    if(current()){loading.textContent='No se pudo construir el catálogo de armaduras.';notify(error.message);}
    return;
  }
  if(!current())return;
  loading.remove();
  const structures=array(catalog?.structures);
  if(!structures.length){
    dashboard.append(node('p','El JSON no contiene estructuras compatibles con el catálogo de armaduras.','badge'));
    return;
  }

  project.rebarAssistant??={};
  project.rebarAssistant.elements??={};
  const stored=project.rebarAssistant.elements;
  const records=[];
  for(const structure of structures)for(const instance of array(structure.instances))for(const element of array(instance.elements)){
    const id=elementId(structure,instance,element);
    stored[id]??=initialState(element);
    records.push({id,structure,instance,element,state:stored[id]});
  }

  const summary=node('p',undefined,'rebar-assistant-summary');
  const shell=node('div',undefined,'rebar-assistant-shell');
  const tree=node('div',undefined,'rebar-assistant-tree');
  tree.setAttribute('aria-label','Estructura del puente');
  const inspector=node('div',undefined,'rebar-assistant-inspector');
  shell.append(tree,inspector);dashboard.append(summary,shell);
  let selected=records.find(item=>item.element.present!==false)||records[0]||null;

  function refreshSummary(){
    const applicable=records.filter(item=>item.element.present!==false);
    const ready=applicable.filter(item=>item.state.status==='ready').length;
    const detected=applicable.filter(item=>item.state.status==='detected').length;
    const review=applicable.filter(item=>['needs_input','error'].includes(item.state.status)).length;
    summary.textContent=`${applicable.length} elementos activos · ${ready} listos para generar · ${detected} detectados · ${review} por revisar`;
  }

  function stateBadge(record){
    const badge=node('span',STATUS_LABELS[record.state.status]||record.state.status,'rebar-state');
    badge.dataset.state=record.state.status;
    return badge;
  }

  function drawTree(){
    tree.replaceChildren();
    for(const structure of structures){
      const block=node('section',undefined,'rebar-structure');
      block.append(node('h3',`${structure.folder||''} · ${structure.label||structure.key}`.replace(/^ · /,'')));
      const instances=array(structure.instances);
      if(!instances.length)block.append(node('p','Sin instancias declaradas en el JSON.','muted'));
      for(const instance of instances){
        const group=node('details',undefined,'rebar-instance');group.open=true;
        const elements=array(instance.elements);
        const present=elements.filter(element=>element.present!==false).length;
        group.append(node('summary',`${instance.label||instance.key} · ${present} elemento${present===1?'':'s'}`));
        const list=node('div',undefined,'rebar-element-list');
        for(const element of elements){
          const record=records.find(item=>item.structure===structure&&item.instance===instance&&item.element===element);
          if(!record)continue;
          const choose=node('button',undefined,'rebar-element-button');choose.type='button';
          choose.setAttribute('aria-current',String(record===selected));
          const title=node('span',element.label||element.key);
          if(element.optional)title.append(node('small',' · Opcional'));
          choose.append(title,stateBadge(record));
          choose.addEventListener('click',()=>{selected=record;drawTree();drawInspector();});
          list.append(choose);
        }
        group.append(list);block.append(group);
      }
      tree.append(block);
    }
  }

  async function cadSnapshot(){
    const expected=await api('cad/status');
    if(expected.status!=='ready')throw Error(expected.message||'No hay una conexión CAD disponible.');
    return expected;
  }

  function cadFingerprint(expected){
    const active=expected?.active||{};
    return JSON.stringify({product:expected?.product||'',version:expected?.version||'',name:active.name||'',path:active.path||''});
  }

  function reconcileCadContext(expected){
    const next=cadFingerprint(expected),previous=project.rebarAssistant.cadContext;
    project.rebarAssistant.cadContext=next;
    if(!previous||previous===next)return;
    for(const record of records){
      Object.assign(record.state,initialState(record.element));
      delete record.state.detection;
    }
    delete project.rebarAssistant.legacyDetection;
    refreshSummary();drawTree();drawInspector();
    notify('Cambió el dibujo activo. Se descartaron las confirmaciones anteriores.');
  }

  function contextPayload(record,expected){
    return {
      project:project.data,
      structure_key:record.structure.key,
      instance_key:record.instance.key,
      element_key:record.element.key,
      expected,
    };
  }

  function updateRecord(record,changes){
    Object.assign(record.state,changes);refreshSummary();drawTree();drawInspector();
  }

  function detectionPanel(record){
    const result=record.state.detection;
    if(!result)return null;
    const panel=node('div',undefined,'rebar-detection');
    panel.append(node('h3','Resultado en CAD'));
    if(result.selection==='cancelled'){
      panel.append(node('p','Selección cancelada. No se cambió la asignación de moldajes.','muted'));return panel;
    }
    panel.append(node('p',`INSUNITS: ${result.insunits??'sin informar'}${result.uses_metres===true?' · metros verificados':result.uses_metres===false?' · debe ser 6 (metros)':''}`,result.uses_metres===false?'badge':'muted'));
    const assignments=result.assignments&&typeof result.assignments==='object'?result.assignments:{};
    const assigned=node('dl',undefined,'rows');
    for(const layer of array(record.element.layers)){
      const handle=assignmentHandle(assignments[layer.layer]);
      assigned.append(node('dt',layer.layer),node('dd',handle||'Sin contorno confirmado'));
    }
    panel.append(assigned);
    const missing=array(result.missing_layers),ambiguous=array(result.ambiguous_layers);
    if(missing.length)panel.append(node('p','Faltan: '+missing.join(', '),'badge'));
    if(ambiguous.length)panel.append(node('p','Hay más de un candidato utilizable en: '+ambiguous.join(', '),'badge'));
    const curved=array(result.curved_layers);if(curved.length)panel.append(node('p','Revisa las vistas con arcos: '+curved.join(', '),'badge'));
    const candidates=array(result.candidates);
    if(candidates.length){
      const details=node('details');details.append(node('summary',`${candidates.length} polilínea${candidates.length===1?'':'s'} leída${candidates.length===1?'':'s'}`));
      const list=node('ul',undefined,'rebar-candidates');for(const candidate of candidates)list.append(node('li',`${candidate.layer} · ${describeCandidate(candidate)}`));details.append(list);panel.append(details);
    }
    return panel;
  }

  function drawInspector(){
    inspector.replaceChildren();
    if(!selected){inspector.append(node('p','El JSON no declaró instancias estructurales para preparar.','muted'));return;}
    const {structure,instance,element,state}=selected;
    const heading=node('div',undefined,'rebar-inspector-heading');
    heading.append(node('div',undefined,'rebar-inspector-title'),stateBadge(selected));
    heading.firstElementChild.append(node('small',`${structure.label} › ${instance.label}`),node('h3',element.label));
    inspector.append(heading);
    inspector.append(node('p',array(element.folder_path).join(' › ')||'Carpeta estructural sin definir','muted'));
    if(element.optional)inspector.append(node('p',element.present===false?'Elemento opcional no activado por el JSON.':'Elemento opcional activado para esta instancia.','rebar-optional-note'));
    inspector.append(node('p',state.message||''));

    const layers=array(element.layers);
    inspector.append(node('h3','Capas esperadas'));
    if(layers.length){
      const wrap=node('div',undefined,'table-wrap'),table=node('table'),head=node('tr');
      for(const text of ['Vista','Capa','Contorno','Uso'])head.append(node('th',text));
      const thead=node('thead');thead.append(head);table.append(thead);const tbody=node('tbody');
      for(const layer of layers){const row=node('tr');for(const value of [layer.view,layer.layer,CONTOUR_LABELS[layer.contour]||layer.contour,layer.detail?'Detalle':'Moldaje'])row.append(node('td',String(value||'')));tbody.append(row);}table.append(tbody);wrap.append(table);inspector.append(wrap);
    }else inspector.append(node('p','Las capas de este elemento todavía no están definidas.','badge'));

    const recipes=array(element.recipes);inspector.append(node('h3','Recetas previstas'));
    const recipeList=node('div',undefined,'rebar-recipes');
    for(const recipe of recipes)recipeList.append(node('span',RECIPE_LABELS[recipe]||recipe,'rebar-recipe'));
    if(!recipes.length)recipeList.append(node('span','Pendientes de definición','muted'));
    inspector.append(recipeList);

    const actions=node('div',undefined,'actions');
    const prepare=button('Preparar capas',async()=>{
      const record=selected;
      const expected=await cadSnapshot();reconcileCadContext(expected);
      const result=await job('cad-prepare-layers',contextPayload(record,expected));
      if(!current())return;
      updateRecord(record,{status:record.state.status==='ready'?'ready':'prepared',message:result?.message||'Las capas esperadas están disponibles en el dibujo.'});
      notify(result?.message||'Capas de moldaje preparadas.');
    });
    const detect=button('Seleccionar y detectar moldajes',async()=>{
      const record=selected;
      const expected=await cadSnapshot();reconcileCadContext(expected);notify('Continúa la selección del elemento en CAD y presiona Enter.');
      const result=await job('cad-detect-element',{...contextPayload(record,expected),interactive:true});
      if(!current())return;
      if(String(result?.selection||'').toLowerCase()==='cancelled'){
        delete record.state.detection;delete project.rebarAssistant.legacyDetection;
        updateRecord(record,{...initialState(record.element),message:'Selección cancelada; el elemento vuelve a quedar pendiente.'});notify('Selección cancelada en CAD.');return;
      }
      const assignments=result?.assignments&&typeof result.assignments==='object'?result.assignments:{};
      const missing=array(result?.missing_layers).length?array(result.missing_layers):layers.map(layer=>layer.layer).filter(layer=>!assignmentHandle(assignments[layer]));
      const ambiguous=array(result?.ambiguous_layers),curved=array(result?.curved_layers);
      let status='needs_input',message=result?.message||'La detección requiere revisión.';
      if(result?.uses_metres===false){status='error';message='El dibujo debe declarar INSUNITS = 6 (metros). No se aceptó la detección.';}
      else if(result?.uses_metres!==true){status='needs_input';message='No se pudieron verificar las unidades del dibujo. Comprueba INSUNITS = 6 antes de generar.';}
      else if(missing.length||ambiguous.length||curved.length){status='needs_input';message=result?.message||'Revisa las capas faltantes, ambiguas o con arcos.';}
      else if(element.key==='abutment.footing'&&result?.generation_ready===true){status='ready';message=result?.message||'Moldajes confirmados y aptos para generar la zapata.';}
      else if(element.key==='abutment.footing'){status='needs_input';message='La zapata requiere una selección completa de contornos cerrados y sin arcos.';}
      else if(result?.detection_complete===true){status='detected';message=result?.message||'Moldajes detectados; la receta de generación aún está pendiente.';}
      updateRecord(record,{status,message,detection:{...result,missing_layers:missing,ambiguous_layers:ambiguous,curved_layers:curved}});
      notify(message);
    });
    const actionable=element.present!==false&&!element.definition_pending&&layers.length>0;
    prepare.disabled=!actionable;detect.disabled=!actionable;actions.append(prepare,detect);
    if(element.key==='abutment.footing'&&element.present!==false){
      const generate=node('button','Configurar y generar zapata','primary');generate.type='button';generate.dataset.page='rebar-abutments';
      generate.addEventListener('click',()=>{
        project.rebarAssistant.legacyAbutment=instance.key;
        if(state.status==='ready'&&state.detection?.detection&&state.detection.uses_metres===true)project.rebarAssistant.legacyDetection={instance_key:instance.key,detection:state.detection};
        else delete project.rebarAssistant.legacyDetection;
      });actions.append(generate);
    }
    inspector.append(actions);
    if(element.key!=='abutment.footing'&&element.present!==false)inspector.append(node('p','La identificación de moldajes ya está disponible. La receta para generar esta armadura aún está pendiente; SINCAL no inventará fierros ni geometría.','muted'));
    const detected=detectionPanel(selected);if(detected)inspector.append(detected);
  }

  refreshSummary();drawTree();drawInspector();
}
