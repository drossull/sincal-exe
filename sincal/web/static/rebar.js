// UI only: all quantities and geometry are calculated by the Python domain model.
import {mountAbutmentIsometric} from '/rebar_isometric.js';
import {openSpliceEditor} from '/rebar_splices.js';
import {mountRebarSplitter} from '/rebar_splitter.js';
function lengthLabel(mark){
  const lengths=(mark.length_variants||[]).map(item=>item.length_cm);
  return lengths.length?`VAR ${Math.min(...lengths)}–${Math.max(...lengths)}`:mark.unit_length_cm;
}

// GSG_COTAS, read from FORMATOS ANOTATIVOS ACAD_2025.dwg:
// RomanD text, width factor .8; dimensions/text/arrows display in white by request.
// closed filled arrows 2.5, text 2.5, gap 1, DIMEXE 1.25, DIMEXO .625,
// fixed extensions 2.5. Values already arrive in cm; do not apply DIMLFAC .1 again.
function detailPreview(piece){
  const ns='http://www.w3.org/2000/svg',make=(tag,attrs={},text)=>{
    const el=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));
    if(text!==undefined)el.textContent=text;return el;
  };
  const svg=make('svg',{viewBox:'0 0 1000 420',role:'img',class:'rebar-detail-preview','data-dimstyle':'GSG_COTAS'});
  const points=piece.points_m,xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  const scale=Math.min(720/Math.max(maxX-minX,.01),180/Math.max(maxY-minY,.01));
  const convert=p=>[500+(p[0]-(minX+maxX)/2)*scale,150+(maxY-p[1])*scale];
  const center=convert([(minX+maxX)/2,(minY+maxY)/2]);
  const variants=piece.length_variants||[],format=value=>Number(value).toLocaleString('es-CL',{maximumFractionDigits:0,useGrouping:false});
  svg.setAttribute('aria-label',variants.length?`Serie variable de marca ${piece.mark}; representación de la pieza de mayor longitud: ${piece.total_cm} cm.`:`Fierro ${piece.mark}. Parciales ${piece.partials_cm.join(', ')} cm; longitud total ${piece.total_cm} cm.`);
  svg.append(make('polyline',{points:points.map(p=>convert(p).join(',')).join(' '),class:'rebar-line'}));
  const unit=7.2,textSize=2.5*unit,arrowSize=2.5*unit,offset=6*unit;
  const add=(p,u,f)=>[p[0]+u[0]*f,p[1]+u[1]*f];
  function line(group,a,b,cls='dimension-line'){
    group.append(make('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],class:cls}));
  }
  function arrow(group,tip,toward){
    const tail=add(tip,toward,arrowSize),normal=[-toward[1],toward[0]],a=add(tail,normal,arrowSize*.16),b=add(tail,normal,-arrowSize*.16);
    group.append(make('polygon',{points:[tip,a,b].map(p=>p.join(',')).join(' '),class:'dimension-arrow'}));
  }
  function text(group,point,label,angle=0){
    const holder=make('g',{transform:`translate(${point[0]} ${point[1]}) rotate(${angle})`});
    const labelNode=make('text',{x:0,y:0,'text-anchor':'middle','dominant-baseline':'central',transform:'scale(.8 1)',class:'dimension-text'},label);
    labelNode.style.fontSize=`${textSize}px`;holder.append(labelNode);
    group.append(holder);
  }
  piece.partial_segments_m.forEach((segment,index)=>{
    const a=convert(segment[0]),b=convert(segment[1]),length=Math.hypot(b[0]-a[0],b[1]-a[1]);
    if(length<1e-8)return;
    const u=[(b[0]-a[0])/length,(b[1]-a[1])/length],mid=[(a[0]+b[0])/2,(a[1]+b[1])/2];
    let normal=[-u[1],u[0]];
    if((mid[0]-center[0])*normal[0]+(mid[1]-center[1])*normal[1]<0)normal=normal.map(v=>-v);
    // A straight bar has no preferred outside; keep its dimension above it.
    if(piece.partial_segments_m.length===1&&normal[1]>0)normal=normal.map(v=>-v);
    const p=add(a,normal,offset),q=add(b,normal,offset),group=make('g',{'data-partial':index,class:'dimension'});
    for(const origin of [a,b])line(group,add(origin,normal,Math.max(.625*unit,offset-2.5*unit)),add(origin,normal,offset+1.25*unit),'dimension-extension');
    line(group,p,q);arrow(group,p,u);arrow(group,q,u.map(v=>-v));
    let angle=Math.atan2(u[1],u[0])*180/Math.PI;
    if(angle>90)angle-=180;if(angle<=-90)angle+=180;
    const range=piece.partial_ranges_cm?.[index];
    const variable=range&&range.min_cm!==range.max_cm;
    const label=variable?`VAR. L= ${format(range.min_cm)} - ${format(range.max_cm)}`:format(piece.partials_cm[index]);
    text(group,add(add(mid,normal,offset),normal,unit+textSize/2),label,angle);
    group.append(make('title',{},variable?`Parcial variable: ${format(range.min_cm)} a ${format(range.max_cm)} cm.`:`Parcial desarrollada: ${format(piece.partials_cm[index])} cm.`));
    svg.append(group);
  });
  for(const [index,bend] of (piece.bends||[]).entries()){
    if(!bend.skewed)continue;
    const vertex=convert(bend.vertex_m),first=[-bend.incoming_unit[0],bend.incoming_unit[1]],last=[bend.outgoing_unit[0],-bend.outgoing_unit[1]];
    const start=Math.atan2(first[1],first[0]);let turn=Math.atan2(last[1],last[0])-start;
    while(turn>Math.PI)turn-=2*Math.PI;while(turn<-Math.PI)turn+=2*Math.PI;
    const radius=52,a=add(vertex,first,radius),b=add(vertex,last,radius),group=make('g',{'data-bend':index,class:'dimension dimension-angular'});
    for(const direction of [first,last])line(group,add(vertex,direction,radius-2.5*unit),add(vertex,direction,radius+1.25*unit),'dimension-extension');
    group.append(make('path',{d:`M ${a.join(' ')} A ${radius} ${radius} 0 0 ${turn>0?1:0} ${b.join(' ')}`,class:'dimension-line'}));
    const sign=Math.sign(turn),tangent=v=>[-v[1]*sign,v[0]*sign];
    arrow(group,a,tangent(first));arrow(group,b,tangent(last).map(v=>-v));
    const mid=start+turn/2;
    text(group,add(vertex,[Math.cos(mid),Math.sin(mid)],radius+unit+textSize/2),`${format(bend.interior_degrees)}°`);
    group.append(make('title',{},`Ángulo interior entre tramos: ${format(bend.interior_degrees)}°. Giro de doblado: ${format(bend.bend_degrees)}°.`));
    svg.append(group);
  }
  return svg;
}

function fitDetailPreview(svg){
  if(!svg.isConnected)return;
  const box=svg.getBBox(),pad=28;
  if(box.width>0&&box.height>0)svg.setAttribute('viewBox',`${box.x-pad} ${box.y-pad} ${box.width+2*pad} ${box.height+2*pad}`);
}
export function openRebarDetail(ctx,piece,mark){
  const {node,button,notify}=ctx;
  if(!piece){notify('No existe geometría para esta marca.');return;}
  const dialog=node('dialog',undefined,'rebar-detail-dialog');dialog.append(node('h2',`Marca ${piece.mark} · ${mark.element}`));
  const variants=piece.length_variants||mark.length_variants||[];
  if(variants.length)dialog.append(node('p',`Serie de largos variables · ${lengthLabel(mark)} cm · Una misma marca para toda la serie.`),node('p','El dibujo representa la pieza de mayor longitud. La lista inferior indica los largos y las cantidades de toda la serie.','muted'));
  if(typeof piece.detail_note==='string'&&piece.detail_note.trim())dialog.append(node('p',piece.detail_note,'muted'));
  const svg=detailPreview(piece);
  dialog.append(node('p','Cotas en cm · GSG_COTAS','muted'));
  const spacingLabel=piece.detail_note&&Number.isFinite(piece.spacing_cm)?piece.spacing_cm.toLocaleString('es-CL',{maximumFractionDigits:2}):piece.spacing_cm;
  dialog.append(svg,node('p',`${variants.length?'Parciales de la pieza mayor':'Parciales desarrolladas'}: ${piece.partials_cm.join(' + ')} = ${piece.total_cm} cm`),node('p',`${piece.quantity} Ø${piece.diameter_mm} @${spacingLabel} · Radio ${mark.bend_radius_cm} cm · Longitud por eje${variants.length?' de la pieza mayor':''} ${piece.measured_cm.toFixed(2)} cm`));
  if(variants.length){
    const wrap=node('div',undefined,'table-wrap'),table=node('table'),head=node('thead'),row=node('tr'),body=node('tbody');
    for(const label of ['Largo desarrollado · cm','Cantidad','Largo total · cm'])row.append(node('th',label));head.append(row);table.append(head,body);
    for(const variant of variants){const row=node('tr');for(const value of [variant.length_cm,variant.quantity,variant.length_cm*variant.quantity])row.append(node('td',String(value)));body.append(row);}
    wrap.append(table);dialog.append(wrap,node('p',`Total de la serie: ${mark.quantity} piezas · ${mark.total_length_cm} cm · ${mark.kg.toFixed(1)} kg.`));
  }
  if((piece.bends||[]).some(bend=>bend.skewed))dialog.append(node('p','Las cotas angulares indican el ángulo interior entre los tramos del fierro.','muted'));
  dialog.append(button('Cerrar',()=>dialog.close()));dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.tabIndex=-1;dialog.showModal();fitDetailPreview(svg);document.fonts.ready.then(()=>fitDetailPreview(svg));dialog.scrollTop=0;dialog.focus({preventScroll:true});
}

export async function renderRebar(ctx){
  const {project,api,node,button,section,notify,job,changed,current}=ctx;
  const intro=section('armaduras','Estribos');
  if(!project?.data||!Object.keys(project.data).length){intro.append(node('p','Incorpora el JSON del puente en Proyecto para configurar sus armaduras.'));return;}
  intro.append(node('p',project.identification.structure_name||'Proyecto sin nombre'));
  intro.append(node('p','Las dimensiones disponibles vienen del JSON (mm → cm). Completa las ausentes y revisa el cálculo antes de dibujar. El programa documenta armaduras; no sustituye la revisión del ingeniero.','muted'));
  const defaults=await api('rebar/from-project',project.data);if(!current())return;
  intro.classList.add('rebar-live-page');
  project.rebar??={};project.rebarAssistant??={};let selected=['entrada','salida'].includes(project.rebarAssistant.legacyAbutment)?project.rebarAssistant.legacyAbutment:'entrada',revision=0,liveViewer=null;
  if(project.rebarAssistant){delete project.rebarAssistant.legacyDetection;delete project.rebarAssistant.cadContext;}
  if(!['auto','m','cm','mm'].includes(project.rebarAssistant.drawingUnits))project.rebarAssistant.drawingUnits='auto';
  const controls=node('div',undefined,'actions');intro.append(controls);
  const body=node('div');intro.append(body);
  for(const [key,label] of [['entrada','Estribo de entrada'],['salida','Estribo de salida']]){
    controls.append(button(label,()=>{selected=key;draw();}));
  }
  function draw(){
    revision++;liveViewer?.dispose();liveViewer=null;body.replaceChildren();
    if(!project.rebar[selected])project.rebar[selected]=structuredClone(defaults[selected]);
    const state=project.rebar[selected];
    // Migrate saved labels to the same mark syntax used by the CAD table.
    for(const rule of state.rules){
      for(const key of ['mark','continuation_mark','terminal_mark']){
        if(typeof rule[key]==='string')rule[key]=rule[key].replace(/^([0-9]+)-([A-Za-z]+)$/,'$1$2');
      }
      if(rule.key==='suple')rule.label=rule.label.replace('3-A','3A');
    }
    body.append(node('h3',selected==='entrada'?'Estribo de entrada':'Estribo de salida'));
    body.append(node('p','La vista previa se actualiza al cambiar los parámetros. Usa Calcular marcas para revisar la tabla antes de insertar.','muted rebar-live-help'));
    const shell=node('div',undefined,'rebar-live-shell'),editor=node('div',undefined,'rebar-live-editor'),previewHost=node('aside',undefined,'rebar-live-preview');
    previewHost.setAttribute('aria-label','Vista previa del estribo');
    shell.append(editor,previewHost);body.append(shell);
    const disposeSplitter=mountRebarSplitter(shell,editor,previewHost),viewer=mountAbutmentIsometric(ctx,selected,previewHost,{onPiecesChanged});
    liveViewer={...viewer,dispose(){disposeSplitter();viewer.dispose();}};
    const output=node('div'),insertionControls=[];let validCalculation=null;
    function refreshInsertionState(){for(const entry of insertionControls)entry.control.disabled=entry.busy||!validCalculation;}
    function calculationIsCurrent(ticket){return ticket===validCalculation&&ticket.generation===revision&&ticket.abutment===selected&&current();}
    function insertionButton(text,action,primary=false){
      const control=node('button',text,primary?'primary':'');control.type='button';const entry={control,busy:false};insertionControls.push(entry);
      control.addEventListener('click',async()=>{if(entry.busy||!validCalculation)return;const ticket=validCalculation;entry.busy=true;refreshInsertionState();try{await action(ticket);}catch(error){notify(error.message);}finally{entry.busy=false;refreshInsertionState();}});
      refreshInsertionState();return control;
    }
    function invalidate(){revision++;validCalculation=null;refreshInsertionState();changed();liveViewer?.update();output.replaceChildren(node('p','Parámetros modificados. Pulsa Calcular marcas para actualizar.','muted'));}
    async function onPiecesChanged(instanceKey){
      if(instanceKey!==selected||!current()||!shell.isConnected)return;
      // The viewer already saved the edit and called changed(). Invalidate
      // the CAD ticket synchronously, before recalculating the shared table.
      revision++;validCalculation=null;refreshInsertionState();
      await calculate();
    }
    function numeric(label,obj,key,step){
      const field=node('label',label),input=node('input');input.type=key==='esviaje_grados'?'text':'number';input.inputMode='decimal';input.step=String(step);input.value=obj[key];
      input.addEventListener('input',()=>{obj[key]=input.value===''?null:Number(input.value);invalidate();});field.append(input);return field;
    }
    const dimensions=node('fieldset');dimensions.append(node('legend','1. Dimensiones y recubrimientos · cm'));
    const grid=node('div',undefined,'fields');
    for(const [key,label,step] of [['largo_cm','Largo',100],['ancho_cm','Ancho',100],['alto_cm','Alto',50],['esviaje_grados','Esviaje · grados',1]])grid.append(numeric(label,state.geometry,key,step));
    for(const [key,label] of [['inferior_cm','Recubrimiento inferior'],['superior_cm','Recubrimiento superior'],['lateral_cm','Recubrimiento lateral']])grid.append(numeric(label,state.cover,key,.5));
    dimensions.append(grid);editor.append(dimensions);
    const rules=node('fieldset');rules.append(node('legend','2. Parámetros de armadura'));
    rules.append(node('p','El gancho es su largo recto, sin el doblez, y se aplica a ambos extremos. 0 = automático. Los valores son editables y sólo afectan al estribo seleccionado.','muted'));
    for(const rule of state.rules){
      const card=node('div',undefined,'rule-row');card.append(node('h3',rule.label));
      const inputs=node('div',undefined,'fields');
      const markLabel=node('label','Marca base'),markInput=node('input');markInput.value=rule.mark;markInput.maxLength=32;markInput.addEventListener('input',()=>{rule.mark=markInput.value;invalidate();});markLabel.append(markInput);inputs.append(markLabel);
      const diameter=node('label','Diámetro · mm'),select=node('select');
      for(const value of [12,16,18,22,25,28,32,36]){const option=node('option',String(value));option.value=value;select.append(option);}select.value=rule.diameter_mm;
      select.addEventListener('change',()=>{rule.diameter_mm=Number(select.value);invalidate();});diameter.append(select);
      inputs.append(diameter,numeric('Separación · cm',rule,'spacing_cm',1),numeric('Gancho de ambos extremos · cm',rule,'hook_cm',1));
      if(rule.continuation_mark){
        if(rule.first_piece_cm===undefined)rule.first_piece_cm=0;
        const first=numeric('Largo del primer fierro · cm',rule,'first_piece_cm',1),firstInput=first.querySelector('input');
        firstInput.min='0';firstInput.max='1200';inputs.append(first);
        const spliceActions=node('div',undefined,'rebar-splice-actions');
        spliceActions.append(button('Ver y ajustar empalme',()=>{
          const generation=revision,abutment=selected;
          openSpliceEditor({ctx,state,rule,isCurrent:()=>current()&&revision===generation&&selected===abutment&&body.isConnected,
            onApply:value=>{rule.first_piece_cm=value;firstInput.value=value;invalidate();}});
        }),node('small','0 = automático. Incluye gancho y doblez; máximo 1200 cm.','muted'));
        inputs.append(spliceActions);
      }
      const origin=node('label','Origen'),originSelect=node('select');
      for(const [value,label]of [['inicio','Inicio'],['final','Final']]){const option=node('option',label);option.value=value;originSelect.append(option);}originSelect.value=rule.origin;
      originSelect.addEventListener('change',()=>{rule.origin=originSelect.value;invalidate();});origin.append(originSelect);
      const enabled=node('label','Activo'),check=node('input');check.type='checkbox';check.checked=rule.enabled;check.addEventListener('change',()=>{rule.enabled=check.checked;invalidate();});enabled.append(check);inputs.append(origin,enabled);card.append(inputs);rules.append(card);
    }
    async function calculate(){
      const generation=++revision,request=structuredClone(state);validCalculation=null;refreshInsertionState();output.replaceChildren(node('p','Calculando armadura…','badge'));
      const response=await api('rebar/preview',request);
      if(generation!==revision||!current())return;
      output.replaceChildren();
      for(const issue of response.issues)output.append(node('p',issue.message,'badge'));
      if(!response.valid){output.append(node('p','Corrige los parámetros antes de obtener un detalle.'));return;}
      validCalculation={generation,state:request,abutment:selected};refreshInsertionState();
      output.append(node('h3',`3. Marcas · ${response.total_kg.toFixed(1)} kg provisionales`));
      const wrap=node('div',undefined,'table-wrap'),table=node('table');
      const head=node('tr');for(const label of ['Marca','Parte','Ubicación','Cantidad','Ø mm','@ cm','L unit. cm','L total cm','Área cm²','kg','Vistas','Rol'])head.append(node('th',label));const thead=node('thead');thead.append(head);table.append(thead);const tbody=node('tbody');
      for(const mark of response.marks){const row=node('tr'),cell=node('td');cell.append(button(mark.mark,()=>detail(response.details.find(d=>d.mark===mark.mark),mark)));row.append(cell);for(const value of [mark.element,mark.location,mark.quantity,mark.diameter_mm,mark.spacing_cm,lengthLabel(mark),mark.total_length_cm,mark.area_cm2.toFixed(3),mark.kg.toFixed(1),mark.views.join(', '),mark.piece_role])row.append(node('td',String(value)));tbody.append(row);}table.append(tbody);wrap.append(table);output.append(wrap,node('p','Pulsa una marca para ver el fierro y sus medidas.','muted'));
      output.append(button('Ampliar tabla de marcas',()=>{
        const dialog=node('dialog',undefined,'rebar-marks-dialog'),copy=table.cloneNode(true);
        const header=node('div',undefined,'rebar-marks-header'),container=node('div',undefined,'table-wrap rebar-marks-scroll'),footer=node('div',undefined,'rebar-marks-footer');
        const title='Marcas · '+selected;header.append(node('h2',title));
        dialog.setAttribute('aria-label',title);dialog.tabIndex=-1;
        copy.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
          const mark=response.marks.find(m=>m.mark===b.textContent);
          detail(response.details.find(d=>d.mark===mark.mark),mark);
        }));
        container.append(copy);footer.append(button('Cerrar tabla',()=>dialog.close()));
        dialog.append(header,container,footer);dialog.addEventListener('close',()=>dialog.remove());
        document.body.append(dialog);dialog.showModal();
        container.scrollLeft=0;container.scrollTop=0;dialog.focus({preventScroll:true});
      }));
    }
    editor.append(rules,button('Calcular marcas',calculate,true),output);
    const cad=node('fieldset');cad.append(node('legend','4. Insertar en CAD · ZAPATA'));
    cad.append(node('p','Calcula la armadura, elige una vista y pulsa su botón. CAD solicitará únicamente los puntos de la zapata: dos esquinas para las vistas rectangulares y tres puntos cuando la planta E–E sea romboide y tenga esviaje. Los demás elementos se incorporarán cuando sus armaduras estén implementadas. Las capas no importan y las dimensiones se validan contra el JSON antes de insertar. La primera vez selecciona la tabla MARCA-SC de todo este estribo o pulsa Enter para crearla. Todos sus elementos, vistas y despieces compartirán esa tabla. Para el despiece, selecciona allí el punto de inserción.'));
    const unitsLabel=node('label','Unidades del dibujo CAD'),drawingUnits=node('select');
    for(const [value,label] of [['auto','Automática'],['m','Metros'],['cm','Centímetros'],['mm','Milímetros']]){const option=node('option',label);option.value=value;drawingUnits.append(option);}
    drawingUnits.value=project.rebarAssistant.drawingUnits;drawingUnits.addEventListener('change',()=>{project.rebarAssistant.drawingUnits=drawingUnits.value;changed();});unitsLabel.append(drawingUnits);
    cad.append(unitsLabel,node('p','Automática usa la unidad declarada por el dibujo y valida el tamaño del rectángulo contra el cálculo. Una unidad explícita prevalece para esta operación sin modificar el DWG.','muted'));
    const viewActions=node('div',undefined,'actions');
    for(const [view,label] of [['FR','Frontal (FR)'],['AA','A–A'],['BB','B–B'],['CC','C–C'],['EE','planta (E–E)']]){
      viewActions.append(insertionButton(`Insertar ${label}`,async ticket=>{
        const expected=await api('cad/status');
        if(!calculationIsCurrent(ticket))throw Error('El cálculo cambió. Calcula nuevamente antes de insertar.');
        if(expected.status!=='ready')throw Error(expected.message);
        const abutments=project.data?.estribos||{},kind=abutments[`tipo_estribo_${ticket.abutment}`];
        const orientation=kind&&kind!=='transparente'?'romboide':abutments[`orientacion_dado_estribo_${ticket.abutment}`];
        const skewedPlan=view==='EE'&&orientation==='romboide'&&Math.abs(Number(ticket.state.geometry?.esviaje_grados)||0)>1e-9;
        notify(skewedPlan?`En CAD indica tres esquinas de la zapata en la planta E–E: superior izquierda, superior derecha e inferior derecha. SINCAL validará las dimensiones contra el JSON antes de insertar.`:`En CAD indica la esquina superior izquierda e inferior derecha de la zapata en la vista ${label}. SINCAL validará las dimensiones contra el JSON antes de insertar.`);
        const result=await job('cad-rebar',{state:ticket.state,project:project.data,abutment:ticket.abutment,view,expected,selection_mode:'geometry',drawing_units:drawingUnits.value});
        if(!calculationIsCurrent(ticket))return;
        if(result?.selection==='cancelled'){notify(`Selección cancelada para la vista ${label}. No se insertó armadura.`);return;}
        if(result?.references){project.rebarAssistant.references??={};project.rebarAssistant.references[`${ticket.abutment}:${view}`]=structuredClone(result.references);changed();}
        notify(`Armadura de zapata insertada en la vista ${label}. Comprueba geometría, marcas y cotas en CAD.`);
      }));
    }
    const detailAction=insertionButton('Generar despiece general',async ticket=>{
      const expected=await api('cad/status');
      if(!calculationIsCurrent(ticket))throw Error('El cálculo cambió. Calcula nuevamente antes de insertar.');
      if(expected.status!=='ready')throw Error(expected.message);
      if(!confirm(`¿Generar despiece de ${selected} en ${expected.active.name}? Selecciona el punto en CAD.`))return;
      const result=await job('cad-rebar',{state:ticket.state,project:project.data,abutment:ticket.abutment,view:'detail',expected,drawing_units:drawingUnits.value});
      if(result?.selection==='cancelled')notify('Selección cancelada. No se insertó el despiece.');
    },true);
    cad.append(viewActions,detailAction);
    cad.append(node('p','Muros y alas no tienen generador de zapata. No se inventa armadura para componentes todavía no definidos.','muted'));editor.append(cad);
  }
  const detail=(piece,mark)=>openRebarDetail(ctx,piece,mark);
  draw();
}
export async function renderCrossbeam(ctx){
  const {project,api,node,button,section,notify,job,changed}=ctx;
  const trav=section('travesanos','TRAVESAÑOS');
  if(!project){trav.append(node('p','Carga primero el JSON en la página inicial del Generador de armadura.'));return;}
  const types=node('div',undefined,'actions'),status=node('p');trav.append(types,status);
  for(const label of ['Sobre apoyos','Intermedio'])types.append(button(label,()=>{status.textContent=label+': configuración específica pendiente de desarrollo. Las herramientas existentes de cuadrantes se mantienen debajo; no distinguen automáticamente esta tipología.';}));
  status.textContent='Sobre apoyos e intermedio: la configuración específica de estas tipologías está pendiente. Se conservan las herramientas existentes de cuadrantes.';
  trav.append(node('p','Generadores existentes de cuadrantes y despieces, con selección de polilínea en CAD. Antes del despiece genera el mismo cuadrante en el mismo dibujo; el núcleo conserva su referencia.'));
  const saved=project.legacy_snapshot?.workspace?.crossbeam||{};
  project.crossbeam??={recub:Number(saved.ent_t_rec??2.5),espesor:Number(saved.ent_t_espesor??25),esviaje:Number(saved.ent_t_esviaje??0),phi_ext:Number(saved.ent_t_phi_ext??22),phi_horiz:Number(saved.ent_t_phi_horiz??12),phi_estr:Number(saved.ent_t_phi_estr??12),largo_viga:Number(saved.ent_viga_largo??200),cant_trav:Number(saved.ent_t_cantidad??1)};
  const fields=node('div',undefined,'fields');trav.append(fields);
  for(const [key,label]of [['recub','Recubrimiento · cm'],['espesor','Espesor · cm'],['esviaje','Esviaje · grados'],['phi_ext','Ø exteriores · mm'],['phi_horiz','Ø horizontales · mm'],['phi_estr','Ø estribos · mm'],['largo_viga','Largo fierros viga · cm'],['cant_trav','Cantidad de travesaños']]){
    const field=node('label',label),input=node(key.startsWith('phi_')?'select':'input');
    if(key.startsWith('phi_'))for(const value of [12,16,18,22,25,28,32,36]){const option=node('option',value);option.value=value;input.append(option);}else{input.type=key==='esviaje'?'text':'number';input.step=key==='recub'?'.5':'1';}
    input.value=project.crossbeam[key];input.addEventListener('change',()=>{project.crossbeam[key]=input.value===''?null:Number(input.value);changed();});field.append(input);fields.append(field);
  }
  const actions=node('div',undefined,'grid');trav.append(actions);
  for(const [quadrant,title]of [['EXT_IZQ','Extremo izquierdo'],['EXT_DER','Extremo derecho'],['INT_TOPE','Sobre tope'],['INT_MACIZO','Macizo'],['INT_VIGA','Viga']]){
    const card=node('article',undefined,'card');card.append(node('h3',title));
    for(const detail of [false,true])card.append(button(detail?'Despiece':'Generar cuadrante',async()=>{const expected=await api('cad/status');if(expected.status!=='ready')throw Error(expected.message);if(confirm(`${detail?'Despiece':'Cuadrante'} ${title} en ${expected.active.name}. Continúa la selección en CAD.`))await job('cad-crossbeam',{state:project.crossbeam,quadrant,detail,expected});}));actions.append(card);
  }
}
