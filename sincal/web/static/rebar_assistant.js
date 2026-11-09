// Project-aware entry point for reinforcement calculations.
// The catalog organizes the bridge; CAD geometry is selected only when the
// user inserts one calculated view. No CAD layer name identifies an element.
import {renderPilePreview} from '/rebar_pile.js';
import {renderWingRebar} from '/rebar_wing.js';
import {openAbutmentIsometric} from '/rebar_isometric.js';

const STATUS_LABELS={
  available:'Configurable',
  pending:'Cálculo pendiente',
  not_applicable:'No aplica',
  preview:'Vista previa',
  exterior:'Mallas del ala',
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

const VIEW_LABELS={FR:'Frontal',AA:'A–A',BB:'B–B',CC:'C–C',DD:'D–D',EE:'Planta E–E',FF:'F–F',EL:'Elevación',PLAN:'Planta',SECC:'Sección',DET:'Detalle'};

function array(value){return Array.isArray(value)?value:[];}
function elementId(structure,instance,element){return `${structure.key}:${instance.key}:${element.key}`;}
function isFooting(element){return element.key==='abutment.footing';}
function isPile(element){return element.key==='abutment.pile';}
function isWing(element){return ['abutment.left_wing','abutment.right_wing'].includes(element.key);}
function initialState(element){
  if(element.present===false)return {status:'not_applicable',message:'El JSON no activa este elemento opcional.'};
  if(isFooting(element))return {status:'available',message:'Configura y calcula la zapata; después podrás insertar cada vista por separado.'};
  if(isPile(element))return {status:'preview',message:'Define los parámetros, los tramos de separación y la penetración en la zapata. El cálculo y la inserción del pilote siguen pendientes.'};
  if(isWing(element))return {status:'exterior',message:'Configura la malla exterior y, cuando corresponda, la interior. Revisa las cotas del ala; las demás armaduras del elemento siguen pendientes.'};
  return {status:'pending',message:'El cálculo de armadura para este elemento aún está pendiente de implementación.'};
}
function viewCodes(element){
  const declared=array(element.views),source=declared.length?declared:array(element.layers);
  return [...new Set(source.map(item=>String(typeof item==='string'?item:(item?.view||item?.code||'')).trim().toUpperCase()).filter(Boolean))];
}

export async function renderRebarAssistant(ctx){
  const {project,api,node,section,notify,current}=ctx;
  const dashboard=section('asistente-armaduras','Asistente de armaduras');
  dashboard.append(node('p','Carga el JSON y selecciona un elemento para configurar su armadura o consultar su estado. Al insertar, CAD solicitará dos esquinas para las referencias rectangulares y tres puntos guiados sólo cuando la planta E–E sea romboide y tenga esviaje.'));
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
  project.rebarAssistant.elements={};
  delete project.rebarAssistant.legacyDetection;
  delete project.rebarAssistant.cadContext;
  const records=[];
  for(const structure of structures)for(const instance of array(structure.instances))for(const element of array(instance.elements)){
    records.push({id:elementId(structure,instance,element),structure,instance,element,state:initialState(element)});
  }

  const applicable=records.filter(item=>item.element.present!==false);
  const configurable=applicable.filter(item=>isFooting(item.element)).length,wingCount=applicable.filter(item=>isWing(item.element)).length;
  const summary=node('p',`${applicable.length} elementos activos · ${configurable} con cálculo disponible${wingCount?` · ${wingCount} alas con mallas configurables`:''} · ${applicable.length-configurable-wingCount} con cálculo pendiente`,'rebar-assistant-summary');
  const shell=node('div',undefined,'rebar-assistant-shell');
  const tree=node('div',undefined,'rebar-assistant-tree');tree.setAttribute('aria-label','Estructura del puente');
  const inspector=node('div',undefined,'rebar-assistant-inspector');shell.append(tree,inspector);dashboard.append(summary,shell);
  let selected=records.find(item=>item.element.present!==false)||records[0]||null,wingController=null;

  function stateBadge(record){
    const badge=node('span',STATUS_LABELS[record.state.status]||record.state.status,'rebar-state');badge.dataset.state=record.state.status;return badge;
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
        const elements=array(instance.elements),present=elements.filter(element=>element.present!==false).length;
        group.append(node('summary',`${instance.label||instance.key} · ${present} elemento${present===1?'':'s'}`));
        const list=node('div',undefined,'rebar-element-list');
        for(const element of elements){
          const record=records.find(item=>item.structure===structure&&item.instance===instance&&item.element===element);if(!record)continue;
          const choose=node('button',undefined,'rebar-element-button');choose.type='button';choose.setAttribute('aria-current',String(record===selected));
          const title=node('span',element.label||element.key);if(element.optional)title.append(node('small',' · Opcional'));
          choose.append(title,stateBadge(record));choose.addEventListener('click',()=>{selected=record;drawTree();drawInspector();});list.append(choose);
        }
        group.append(list);block.append(group);
      }
      tree.append(block);
    }
  }

  function drawInspector(){
    wingController?.dispose();wingController=null;
    inspector.replaceChildren();
    if(!selected){inspector.append(node('p','El JSON no declaró instancias estructurales para configurar.','muted'));return;}
    const {structure,instance,element,state}=selected;
    const heading=node('div',undefined,'rebar-inspector-heading');heading.append(node('div',undefined,'rebar-inspector-title'),stateBadge(selected));
    heading.firstElementChild.append(node('small',`${structure.label} › ${instance.label}`),node('h3',element.label));inspector.append(heading);
    inspector.append(node('p',array(element.folder_path).join(' › ')||'Elemento estructural','muted'));
    if(element.optional)inspector.append(node('p',element.present===false?'Elemento opcional no activado por el JSON.':'Elemento opcional activado para esta instancia.','rebar-optional-note'));
    inspector.append(node('p',state.message));
    if(structure.key==='abutment'&&!isWing(element)){
      const preview=node('button','Abrir isométrica del estribo');preview.type='button';
      preview.addEventListener('click',()=>openAbutmentIsometric(ctx,instance.key));inspector.append(preview);
    }

    const views=viewCodes(element);inspector.append(node('h3','Vistas de referencia'));
    const viewList=node('div',undefined,'rebar-recipes');
    for(const code of views)viewList.append(node('span',`${VIEW_LABELS[code]||code} · ${code}`,'rebar-recipe'));
    if(!views.length)viewList.append(node('span','Vistas pendientes de definición','muted'));
    inspector.append(viewList,node('p','Por ahora se solicitan únicamente los puntos de la zapata: dos esquinas para una vista rectangular y tres puntos para la planta E–E romboide con esviaje. SINCAL valida esas referencias contra las dimensiones del JSON antes de insertar. Los demás elementos se incorporarán cuando sus armaduras estén implementadas.','muted'));

    if(isFooting(element)){
      const recipes=array(element.recipes);inspector.append(node('h3','Armaduras previstas'));
      const recipeList=node('div',undefined,'rebar-recipes');for(const recipe of recipes)recipeList.append(node('span',RECIPE_LABELS[recipe]||recipe,'rebar-recipe'));
      if(!recipes.length)recipeList.append(node('span','Pendientes de definición','muted'));inspector.append(recipeList);
    }else if(!isPile(element)&&!isWing(element))inspector.append(node('h3','Armadura'),node('p','Naturaleza y distribución pendientes de definición.','muted'));

    if(isFooting(element)&&element.present!==false){
      const actions=node('div',undefined,'actions'),configure=node('button','Configurar y calcular zapata','primary');configure.type='button';configure.dataset.page='rebar-abutments';
      configure.addEventListener('click',()=>{project.rebarAssistant.legacyAbutment=instance.key;delete project.rebarAssistant.legacyDetection;});actions.append(configure);inspector.append(actions);
    }else if(isPile(element)&&element.present!==false){
      const pileHost=node('div',undefined,'rebar-pile-host');inspector.append(pileHost);
      renderPilePreview(ctx,pileHost,instance.key).catch(error=>{if(current()&&pileHost.isConnected){pileHost.replaceChildren(node('p','No se pudo abrir la vista previa del pilote.','badge'));notify(error.message);}});
    }else if(isWing(element)&&element.present!==false){
      const wingHost=node('div',undefined,'rebar-wing-host');inspector.append(wingHost);
      renderWingRebar(ctx,wingHost,instance.key,element.key==='abutment.left_wing'?'left':'right').then(controller=>{
        if(!current()||!wingHost.isConnected)controller?.dispose();else wingController=controller;
      }).catch(error=>{if(current()&&wingHost.isConnected){wingHost.replaceChildren(node('p','No se pudieron abrir las mallas del ala.','badge'));notify(error.message);}});
    }else if(element.present!==false){
      inspector.append(node('p','La estructura está identificada desde el JSON, pero su cálculo y sus controles de inserción aún no están disponibles.','muted'));
    }
  }

  drawTree();drawInspector();
}
