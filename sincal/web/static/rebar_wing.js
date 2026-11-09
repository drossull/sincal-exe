// The existing wing inspector edits a local draft. Python owns the geometry,
// quantities and detailing; this panel never requests a CAD operation.
import {mountAbutmentIsometric} from '/rebar_isometric.js';
import {mountRebarSplitter} from '/rebar_splitter.js';
import {openRebarDetail} from '/rebar.js';
import {mountWingSupplementControls} from '/rebar_wing_ranges.js';

const finite=value=>typeof value==='number'&&Number.isFinite(value);
const format=value=>finite(value)?value.toLocaleString('es-CL',{maximumFractionDigits:2}):'—';
const GEOMETRY_FIELDS=[
  ['thickness_cm','Espesor del ala'],['main_length_cm','Largo principal del ala'],
  ['extension_length_cm','Largo de la aleta'],['top_join_cm','Cota superior en el encuentro'],
  ['top_edge_cm','Cota superior en el borde del ala'],['top_tip_cm','Cota superior en la punta de la aleta'],
  ['tip_height_cm','Altura en la punta de la aleta'],['front_height_cm','Altura del muro frontal'],
  ['front_depth_cm','Profundidad del muro frontal'],['back_thickness_cm','Espesor del espaldar'],
];

export async function renderWingRebar(ctx,host,instanceKey,side){
  const {project,api,node,button,changed,current,notify}=ctx;
  if(!['entrada','salida'].includes(instanceKey)||!['left','right'].includes(side))return;
  const sourceProject=project.data,root=node('div',undefined,'rebar-wing');host.append(root);
  const label=side==='left'?'Ala izquierda':'Ala derecha';
  let state=null,disposed=false,revision=0,timer=null,viewer=null,rangeController=null,disposeSplitter=()=>{},observer=null;
  const alive=()=>!disposed&&root.isConnected&&current()&&project.data===sourceProject&&
    (!state||project.rebar?.[instanceKey]?.wings?.[side]===state);
  root.append(node('p','Preparando las mallas del ala…','muted'));
  let source;
  try{
    let abutment=project.rebar?.[instanceKey];
    if(!abutment){
      const defaults=await api('rebar/from-project',sourceProject);if(!alive())return;
      abutment=defaults[instanceKey];
    }
    source=await api('rebar/wing/from-project',{project:sourceProject,instance_key:instanceKey,side,abutment_state:structuredClone(abutment)});
    if(!alive())return;
    if(source.present!==true){
      root.replaceChildren(node('p','Este proyecto no contiene un muro ala compatible para esta configuración.','muted'));
      for(const issue of source.issues||[])root.append(node('p',issue.message||String(issue),'badge'));
      return;
    }
    project.rebar??={};project.rebar[instanceKey]??=structuredClone(abutment);
    project.rebar[instanceKey].wings??={};
    let draftChanged=false;
    if(!project.rebar[instanceKey].wings[side]){
      project.rebar[instanceKey].wings[side]=structuredClone(source.state);draftChanged=true;
    }
    if(source.normalized_state&&JSON.stringify(project.rebar[instanceKey].wings[side])!==JSON.stringify(source.normalized_state)){
      project.rebar[instanceKey].wings[side]=structuredClone(source.normalized_state);draftChanged=true;
    }
    state=project.rebar[instanceKey].wings[side];
    if(state.outer_family==null){state.outer_family='vertical';draftChanged=true;}
    if(state.horizontal_start==null){state.horizontal_start='wall';draftChanged=true;}
    if(!state.interior){
      state.interior=structuredClone(source.state.interior||{
        enabled:false,parameters_initialized:false,
        vertical:{diameter_mm:null,spacing_cm:null,hook_bottom_cm:40,hook_top_cm:40,mark_main:'',mark_extension:''},
        horizontal:{diameter_mm:null,spacing_cm:null,hook_ala_cm:40,hook_join_cm:40,mark_main:'',mark_upper:''},removed_pieces:[],
      });draftChanged=true;
    }else if(typeof state.interior.parameters_initialized!=='boolean'){
      state.interior.parameters_initialized=Boolean(state.interior.enabled||state.interior.removed_pieces?.length||
        ['vertical','horizontal'].some(group=>Object.entries(state.interior[group]||{}).some(([key,value])=>!key.startsWith('mark_')&&value!=null)));
      draftChanged=true;
    }
    if(!state.supplements){
      const emptyGroup=()=>({enabled:false,diameter_mm:null,spacing_cm:null,hook_cm:40,straight_cm:null,mark:'',removed_pieces:[]});
      state.supplements=structuredClone(source.state.supplements||{front:{...emptyGroup(),range_height_cm:null},back:emptyGroup()});draftChanged=true;
    }
    if(!state.edge_rebar){
      state.edge_rebar=structuredClone(source.state.edge_rebar||{quantity:null,diameter_mm:null,top_hook_enabled:true,top_hook_cm:20,total_cm:null,min_extension_cm:100,mark:'',removed_pieces:[]});draftChanged=true;
    }
    if(draftChanged)changed();
  }catch(error){
    if(alive()){root.replaceChildren(node('p','No se pudieron preparar las mallas del ala.','badge'));notify(error.message);}
    return;
  }

  root.replaceChildren(node('h3','Mallas del ala'));
  root.append(node('p','Revisa el perfil y sus cotas antes de calcular las mallas. Las otras armaduras del ala se incorporarán cuando estén definidas.','muted'));
  const shell=node('div',undefined,'rebar-live-shell'),editor=node('div',undefined,'rebar-live-editor'),previewHost=node('aside',undefined,'rebar-live-preview');
  previewHost.setAttribute('aria-label',`Vista previa de ${label.toLowerCase()}`);
  shell.append(editor,previewHost);root.append(shell);
  const messages=node('div',undefined,'rebar-wing-messages'),output=node('div',undefined,'rebar-wing-output');
  messages.setAttribute('aria-live','polite');output.setAttribute('aria-live','polite');
  let confirmation;

  function dispose(){
    if(disposed)return;disposed=true;revision++;clearTimeout(timer);observer?.disconnect();disposeSplitter();viewer?.dispose();rangeController?.dispose();
  }
  function requestPayload(){
    return structuredClone({project:sourceProject,instance_key:instanceKey,side,state,
      abutment_state:project.rebar[instanceKey]});
  }
  function showIssues(issues){
    messages.replaceChildren();
    for(const issue of issues||[])messages.append(node('p',issue.message||String(issue),issue.severity==='error'?'badge':'muted'));
  }
  function invalidate(geometryChanged=false){
    if(!alive())return;
    if(geometryChanged){state.geometry_confirmed=false;confirmation.checked=false;}
    revision++;changed();clearTimeout(timer);
    rangeController?.invalidate();
    output.replaceChildren(node('p','Actualizando las mallas del ala…','muted'));output.setAttribute('aria-busy','true');
    viewer?.update();timer=setTimeout(()=>{timer=null;refresh();},250);
  }
  function fieldset(title){
    const fieldset=node('fieldset'),grid=node('div',undefined,'fields');
    fieldset.append(node('legend',title),grid);editor.append(fieldset);return {fieldset,grid};
  }
  function numeric(label,object,key,{geometry=false,step=1}={}){
    const field=node('label',`${label} · ${key.endsWith('_mm')?'mm':'cm'}`),input=node('input');
    input.type='number';input.inputMode='decimal';input.min='0';input.step=String(step);input.value=object[key]??'';
    input.addEventListener('input',()=>{object[key]=input.value===''?null:Number(input.value);invalidate(geometry);});
    field.append(input);return field;
  }
  function markField(label,object,key){
    const field=node('label',label),input=node('input');input.value=object[key]??'';input.maxLength=32;
    input.addEventListener('input',()=>{object[key]=input.value;invalidate();});field.append(input);return field;
  }
  const geometry=fieldset('1. Geometría del ala · cm');
  for(const [key,text] of GEOMETRY_FIELDS)geometry.grid.append(numeric(text,state.geometry,key,{geometry:true}));
  geometry.fieldset.append(node('p','Las cotas superiores y la altura del muro frontal se miden desde la cara superior de la zapata. El perfil leído del JSON puede ser nominal: ajusta las medidas del proyecto y confírmalas.','muted'));
  const confirmLabel=node('label',undefined,'rebar-wing-confirmation');confirmation=node('input');confirmation.type='checkbox';confirmation.checked=state.geometry_confirmed===true;
  confirmation.addEventListener('change',()=>{state.geometry_confirmed=confirmation.checked;invalidate();});
  confirmLabel.append(confirmation,node('span','Confirmo las cotas y dimensiones del ala'));geometry.fieldset.append(confirmLabel);

  const covers=fieldset('2. Recubrimientos · cm');
  for(const [key,text] of [['outside_cm','Recubrimiento exterior'],['inside_cm','Recubrimiento interior'],['top_cm','Recubrimiento superior'],['end_cm','Recubrimiento en extremos'],['diagonal_cm','Recubrimiento en diagonal']]){
    covers.grid.append(numeric(text,state.cover,key,{step:.5}));
  }
  const arrangement=fieldset('3. Disposición de la malla exterior');
  arrangement.grid.remove();
  arrangement.fieldset.append(
    node('p','Los fierros verticales van por fuera; los horizontales quedan pegados por dentro.','muted'),
    node('p','Los horizontales comienzan en la base del muro, sobre la zapata.','muted'),
    node('p','Cuando el ala está girada, el fierro horizontal se dobla en el encuentro y continúa siguiendo ambas caras.','muted'),
  );
  const vertical=fieldset('4. Malla exterior · fierros verticales');
  vertical.grid.append(markField('Marca vertical del ala',state.vertical,'mark_main'),markField('Marca vertical de la aleta',state.vertical,'mark_extension'),
    numeric('Diámetro vertical',state.vertical,'diameter_mm'),numeric('Separación vertical',state.vertical,'spacing_cm'),
    numeric('Gancho inferior vertical',state.vertical,'hook_bottom_cm'),numeric('Gancho superior vertical',state.vertical,'hook_top_cm'));
  vertical.fieldset.append(node('p','Los ganchos ingresados son sus tramos rectos; el radio de doblez es 3 × Ø. Los fierros de la aleta se ajustan a su perfil.','muted'));
  const horizontal=fieldset('5. Malla exterior · fierros horizontales');
  horizontal.grid.append(markField('Marca horizontal principal',state.horizontal,'mark_main'),markField('Marca horizontal superior',state.horizontal,'mark_upper'),
    numeric('Diámetro horizontal',state.horizontal,'diameter_mm'),numeric('Separación horizontal',state.horizontal,'spacing_cm'),
    numeric('Gancho horizontal en el ala',state.horizontal,'hook_ala_cm'),numeric('Gancho horizontal en el encuentro',state.horizontal,'hook_join_cm'));
  horizontal.fieldset.append(node('p','Los dos largos de gancho se editan por separado. El fierro horizontal superior termina en el espaldar.','muted'));
  const interior=fieldset('6. Malla interior');interior.grid.remove();
  const interiorToggleLabel=node('label',undefined,'rebar-wing-confirmation'),interiorToggle=node('input'),interiorControls=node('div');
  interiorToggle.type='checkbox';interiorToggle.checked=state.interior.enabled===true;
  interiorToggleLabel.append(interiorToggle,node('span','Incluir malla interior'));interior.fieldset.append(interiorToggleLabel,interiorControls);
  function copyExteriorParameters(){
    for(const group of ['vertical','horizontal'])for(const [key,value] of Object.entries(state[group])){
      if(!key.startsWith('mark_'))state.interior[group][key]=value;
    }
    state.interior.parameters_initialized=true;
  }
  function renderInteriorControls(){
    interiorControls.replaceChildren();interiorControls.hidden=!state.interior.enabled;
    if(!state.interior.enabled)return;
    interiorControls.append(
      node('p','Los verticales quedan junto a la cara interior y los horizontales pegados por dentro de ellos.','muted'),
      node('p','En el ala principal, el gancho inferior vertical mantiene la dirección del exterior; el superior se invierte. En la aleta corta, ambos ganchos van hacia el espesor.','muted'),
      node('p','Los ganchos horizontales del ala van en sentido opuesto a los exteriores. En el frontal y el espaldar conservan la misma dirección.','muted'),
      button('Copiar parámetros de la malla exterior',()=>{copyExteriorParameters();renderInteriorControls();invalidate();}),
      node('p','La copia conserva las marcas y los fierros eliminados de la malla interior.','muted'),
    );
    const innerVertical=node('div',undefined,'fields'),innerHorizontal=node('div',undefined,'fields');
    const v=state.interior.vertical,h=state.interior.horizontal;
    innerVertical.append(markField('Marca interior vertical del ala',v,'mark_main'),markField('Marca interior vertical de la aleta',v,'mark_extension'),
      numeric('Diámetro interior vertical',v,'diameter_mm'),numeric('Separación interior vertical',v,'spacing_cm'),
      numeric('Gancho interior inferior vertical',v,'hook_bottom_cm'),numeric('Gancho interior superior vertical',v,'hook_top_cm'));
    innerHorizontal.append(markField('Marca interior horizontal principal',h,'mark_main'),markField('Marca interior horizontal superior',h,'mark_upper'),
      numeric('Diámetro interior horizontal',h,'diameter_mm'),numeric('Separación interior horizontal',h,'spacing_cm'),
      numeric('Gancho interior horizontal en el ala',h,'hook_ala_cm'),numeric('Gancho interior horizontal en el encuentro',h,'hook_join_cm'));
    interiorControls.append(node('h4','Fierros verticales interiores'),innerVertical,node('h4','Fierros horizontales interiores'),innerHorizontal);
  }
  interiorToggle.addEventListener('change',()=>{
    if(interiorToggle.checked&&!state.interior.parameters_initialized)copyExteriorParameters();
    state.interior.enabled=interiorToggle.checked;renderInteriorControls();invalidate();
  });
  renderInteriorControls();
  const supplements=fieldset('7. Suples de malla interior y fierro de canto');supplements.grid.remove();
  rangeController=mountWingSupplementControls(ctx,supplements.fieldset,state,source.range_preview,()=>invalidate());
  const calculate=button('Calcular marcas del ala',()=>refresh(),true);editor.append(calculate,messages,output);
  showIssues(source.issues);

  function detailFor(response,mark){
    return (response.details||[]).find(piece=>piece.mark===mark.mark&&(!piece.key||piece.key===mark.key));
  }
  function makeTable(response){
    const table=node('table'),head=node('thead'),headRow=node('tr'),body=node('tbody');
    table.setAttribute('aria-label',`Marcas de ${label.toLowerCase()}`);
    for(const text of ['Marca','Parte','Ubicación','Cantidad','Ø mm','@ cm','L unit. cm','L total cm','Área cm²','kg','Vistas','Rol'])headRow.append(node('th',text));
    head.append(headRow);table.append(head,body);
    for(const mark of response.marks||[]){
      const row=node('tr'),name=node('td'),lengths=(mark.length_variants||[]).map(item=>item.length_cm);
      name.append(button(mark.mark,()=>openRebarDetail(ctx,detailFor(response,mark),mark)));row.append(name);
      const length=lengths.length?`VAR ${format(Math.min(...lengths))}–${format(Math.max(...lengths))}`:format(mark.unit_length_cm);
      const area=finite(mark.area_cm2)?mark.area_cm2.toFixed(3):'—',weight=finite(mark.kg)?mark.kg.toFixed(1):'—';
      for(const value of [mark.element,mark.location,mark.quantity,mark.diameter_mm,mark.spacing_cm,length,mark.total_length_cm,area,weight,(mark.views||[]).join(', '),mark.piece_role])row.append(node('td',value===undefined?'—':String(value)));
      body.append(row);
    }
    return table;
  }
  function expandTable(response){
    if(!alive())return;
    const dialog=node('dialog',undefined,'rebar-marks-dialog'),header=node('div',undefined,'rebar-marks-header'),body=node('div',undefined,'table-wrap rebar-marks-scroll'),footer=node('div',undefined,'rebar-marks-footer');
    const title=`Marcas · ${label} · ${instanceKey}`;dialog.setAttribute('aria-label',title);dialog.tabIndex=-1;
    header.append(node('h2',title));body.append(makeTable(response));footer.append(button('Cerrar tabla',()=>dialog.close()));
    dialog.append(header,body,footer);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();dialog.focus({preventScroll:true});
  }
  async function refresh(){
    if(!alive())return;clearTimeout(timer);timer=null;
    const request=++revision,payload=requestPayload();
    output.replaceChildren(node('p','Calculando las mallas del ala…','muted'));output.setAttribute('aria-busy','true');
    try{
      const response=await api('rebar/wing/preview',payload);
      if(!alive()||request!==revision)return;
      if(Object.prototype.hasOwnProperty.call(response,'range_preview'))rangeController.update(response.range_preview,response);
      showIssues(response.issues);output.replaceChildren();
      if(!response.valid){
        output.append(node('p',(response.marks||[]).length?'Hay datos o armaduras pendientes. Se muestran sólo las marcas que pudieron calcularse.':'Completa y revisa los datos de las mallas para obtener sus marcas.','muted'));
        if(!(response.marks||[]).length)return;
      }
      output.append(node('h3',`${response.valid?'Marcas del ala':'Marcas calculadas del ala'}${finite(response.total_kg)?` · ${response.total_kg.toFixed(1)} kg`:''}`));
      if(!(response.marks||[]).length){output.append(node('p','No hay fierros calculados con estos parámetros.','muted'));return;}
      const wrap=node('div',undefined,'table-wrap');wrap.append(makeTable(response));output.append(wrap,
        node('p','Estas marcas corresponden al ala actual y pertenecen a la tabla compartida del estribo. Pulsa una marca para ver su despiece.','muted'),
        button('Ampliar tabla de marcas',()=>expandTable(response)));
    }catch(error){
      if(alive()&&request===revision){rangeController.update(null);output.replaceChildren(node('p','No se pudieron actualizar las mallas del ala. '+error.message,'badge'));}
    }finally{
      if(alive()&&request===revision)output.setAttribute('aria-busy','false');
    }
  }
  disposeSplitter=mountRebarSplitter(shell,editor,previewHost);
  viewer=mountAbutmentIsometric(ctx,instanceKey,previewHost,{onPiecesChanged:key=>{if(key===instanceKey&&alive())return refresh();}});
  observer=new MutationObserver(()=>{if(!alive())dispose();});observer.observe(document.body,{childList:true,subtree:true});
  await refresh();
  return {dispose,refresh};
}
