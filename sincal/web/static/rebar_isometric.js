// Local viewer and explicit piece edits. It never requests CAD operations.
const NS='http://www.w3.org/2000/svg';
const COLORS=['#ffc34d','#56c9f2','#db9aff','#69d9b1','#ff8c77'];
const ISO_YAW=-Math.PI/4,ISO_PITCH=Math.atan(1/Math.sqrt(2)),PITCH_LIMIT=Math.PI/2-.01;
const clampPitch=value=>Math.max(-PITCH_LIMIT,Math.min(PITCH_LIMIT,value));
let activeViewer=null;

function svgNode(tag,attributes={},text){
  const el=document.createElementNS(NS,tag);
  for(const [name,value] of Object.entries(attributes))el.setAttribute(name,String(value));
  if(text!==undefined)el.textContent=text;
  return el;
}
function barDescription(bar){
  const number=value=>Number(value).toLocaleString('es-CL',{maximumFractionDigits:2});
  const parts=[bar.label||'Armadura',`Marca ${bar.mark||''}`,`Ø${number(bar.diameter_mm)} mm`];
  const roles={completa:'Pieza completa',inicial:'Pieza inicial',intermedia:'Pieza intermedia',terminal:'Pieza terminal'};
  if(roles[bar.piece_role])parts.push(roles[bar.piece_role]);
  if(Number.isFinite(bar.length_cm))parts.push(`L=${number(bar.length_cm)} cm`);
  if(Number.isFinite(bar.bend_radius_cm)&&bar.bend_radius_cm>0)parts.push(`Radio ${number(bar.bend_radius_cm)} cm`);
  if(Number.isFinite(bar.lap_cm)&&bar.lap_cm>0)parts.push(`Traslapo ${number(bar.lap_cm)} cm`);
  return parts.join(' · ');
}
export async function openAbutmentIsometric(ctx,instanceKey,selectedElementKey=null,options={}){
  const viewer=createAbutmentIsometric(ctx,instanceKey,selectedElementKey,null,options);
  if(viewer)await viewer.ready;
}

export function mountAbutmentIsometric(ctx,instanceKey,host,options={}){
  return createAbutmentIsometric(ctx,instanceKey,null,host,{...options,useStateGeometry:true});
}

function createAbutmentIsometric(ctx,instanceKey,selectedElementKey,host,options){
  const {project,api,node,current,notify}=ctx;
  if(!['entrada','salida'].includes(instanceKey))return;
  const embedded=Boolean(host);
  const pieceSession=options.pieceSession||{undo:[],labels:new Map(),revision:0};
  if(!embedded)activeViewer?.close();
  const sourceData=project.data,dialog=node(embedded?'div':'dialog',undefined,embedded?'rebar-isometric iso-embedded':'rebar-isometric');
  if(!embedded)activeViewer=dialog;
  dialog.setAttribute('aria-label','Vista isométrica del estribo');
  if(embedded)dialog.setAttribute('role','region');
  const title=instanceKey==='entrada'?'Estribo de entrada':'Estribo de salida';
  const header=node('div',undefined,'iso-header'),heading=node('div',undefined,'iso-heading');
  heading.append(node('h2',`${title} · Isométrica`));
  if(!embedded)heading.append(node('p',project.identification?.structure_name||'Vista del conjunto','muted'));
  const actions=node('div',undefined,'iso-actions'),toolbar=node('div',undefined,'iso-toolbar');
  toolbar.setAttribute('role','group');toolbar.setAttribute('aria-label','Controles de la vista');
  const close=node('button',embedded?'Ampliar visor':'Cerrar visor',embedded?'iso-expand':'iso-close');close.type='button';
  function expand(){
    const before=pieceSession.revision;
    return openAbutmentIsometric(ctx,instanceKey,null,{useStateGeometry:true,camera:captureView(),pieceSession,onPiecesChanged:options.onPiecesChanged,onViewChange:next=>{
    if(!alive()||!latestScene||!next)return;
    viewState=next;
    if(pieceSession.revision!==before)update();
    else{disposeScene();drawScene(latestScene);}
  }});
  }
  close.onclick=()=>embedded?expand():closeViewer();
  actions.append(toolbar,close);header.append(heading,actions);dialog.append(header);
  const status=node('p',embedded?'Actualización automática al editar parámetros.':'','iso-live-status');
  status.setAttribute('role','status');
  const content=node('div',undefined,'iso-content');content.append(node('p','Preparando moldajes y armaduras…','muted'));
  const footer=node('div',undefined,'iso-footer');
  footer.append(status,node('p','Clic: seleccionar fierro · Central: desplazar · Mayús + central: orbitar · Rueda: zoom · Z vertical.','iso-help muted'));
  dialog.append(content,footer);
  let requestRevision=0,timer=null,disposed=false,loading=false,queued=false,viewReturned=false;
  let latestScene=null,sceneStateSignature=null,viewState=options.camera||null,captureView=()=>viewState,disposeScene=()=>{},refreshEditControls=()=>{},restoreLastDeletion=null;
  const currentStateSignature=()=>JSON.stringify(project.rebar?.[instanceKey]??null);
  const wingIdentity=piece=>/^wing:(left|right):([a-z_]+):([0-9]+)$/.exec(piece?.id||'');
  const wingGroupLabel=group=>group==='edge'?'fierro de canto':group==='inner_supplement_front'?'suples hacia el frontal':group==='inner_supplement_back'?'suples hacia el espaldar':`malla ${group.startsWith('inner_')?'interior':'exterior'}`;
  const resolvedKey=piece=>{const match=wingIdentity(piece);return piece.key||(match?`wing_${match[1]}_${match[2]}`:undefined);};
  const pieceKey=piece=>JSON.stringify([resolvedKey(piece),piece.id,piece.signature]);
  function pieceOwner(piece){
    const state=project.rebar?.[instanceKey],wing=wingIdentity(piece);
    if(wing){
      if(resolvedKey(piece)!==`wing_${wing[1]}_${wing[2]}`)return null;
      const owner=state?.wings?.[wing[1]],group=wing[2];
      if(group==='edge')return owner?.edge_rebar;
      if(group==='inner_supplement_front')return owner?.supplements?.front;
      if(group==='inner_supplement_back')return owner?.supplements?.back;
      return group.startsWith('inner_')?owner?.interior:owner;
    }
    return state?.rules?.find(rule=>rule.key===piece.key);
  }
  function removedEntries(){
    const state=project.rebar?.[instanceKey];
    const entries=(state?.rules||[]).flatMap(rule=>(rule.removed_pieces||[]).map(piece=>({...piece,key:rule.key,rule})));
    for(const side of ['left','right']){
      const wing=state?.wings?.[side];
      for(const owner of [wing,wing?.interior,wing?.supplements?.front,wing?.supplements?.back,wing?.edge_rebar])for(const piece of owner?.removed_pieces||[]){
        const match=wingIdentity(piece);if(!match||match[1]!==side||pieceOwner(piece)!==owner)continue;
        entries.push({...piece,key:resolvedKey(piece),rule:owner});
      }
    }
    return entries;
  }
  const alive=()=>!disposed&&dialog.isConnected&&(embedded||dialog.open)&&current()&&project.data===sourceData;
  const monitor=setInterval(()=>{if(!alive())dispose();},500);
  function returnView(){
    if(embedded||viewReturned||disposed||!current()||project.data!==sourceData)return;
    viewReturned=true;options.onViewChange?.(captureView());
  }
  function closeViewer(){returnView();dialog.close();}
  function dispose(){
    if(disposed)return;
    returnView();
    disposed=true;requestRevision++;clearInterval(monitor);clearTimeout(timer);disposeScene();
    if(!embedded&&dialog.open)dialog.close();dialog.remove();
    if(activeViewer===dialog)activeViewer=null;
  }
  dialog.addEventListener('cancel',returnView);
  dialog.addEventListener('close',dispose,{once:true});
  (host||document.body).append(dialog);if(!embedded)dialog.showModal();

  function update(){
    if(!alive())return;
    requestRevision++;clearTimeout(timer);
    dialog.classList.add('iso-pending');dialog.setAttribute('aria-busy','true');
    refreshEditControls();
    status.textContent='Actualizando vista…';
    timer=setTimeout(()=>{timer=null;load();},300);
  }

  async function load(){
    if(!alive())return;
    if(loading){queued=true;return;}
    clearTimeout(timer);timer=null;
    loading=true;
    const revision=++requestRevision;
    const snapshot=structuredClone({project:sourceData,instance_key:instanceKey,state:project.rebar?.[instanceKey]??null});
    if(options.useStateGeometry)snapshot.use_state_geometry=true;
    try{
      const scene=await api('rebar/abutment/scene',snapshot);
      if(!alive()||revision!==requestRevision)return;
      viewState=captureView();disposeScene();
      sceneStateSignature=JSON.stringify(snapshot.state);
      latestScene=scene;drawScene(scene);
      dialog.classList.remove('iso-pending');dialog.setAttribute('aria-busy','false');
      refreshEditControls();
      const hasElements=(scene.elements||[]).length,hasBars=(scene.bars||[]).length,issues=(scene.issues||[]).length;
      status.textContent=!hasElements?'Completa o corrige los parámetros para ver la estructura.':!hasBars?'Sin armadura representable con los parámetros actuales.':'Vista actualizada.';
      if(embedded&&issues)status.textContent+=' Revisa los avisos en el visor ampliado.';
    }catch(error){
      if(!alive()||revision!==requestRevision)return;
      viewState=captureView();disposeScene();
      toolbar.replaceChildren();
      content.replaceChildren(node('p','No se pudo preparar la isométrica. '+error.message,'badge'));
      dialog.classList.remove('iso-pending');dialog.setAttribute('aria-busy','false');status.textContent='Vista sin actualizar.';
      const retry=node('button','Volver a intentar');retry.onclick=load;content.append(retry);if(!embedded)notify(error.message);
      const canUndo=pieceSession.undo.some(entry=>removedEntries().some(piece=>pieceKey(piece)===pieceKey(entry)));
      if(canUndo&&restoreLastDeletion){const undo=node('button','Deshacer eliminación');undo.type='button';undo.onclick=restoreLastDeletion;content.append(undo);}
    }finally{
      loading=false;
      if(queued&&alive()){queued=false;load();}
    }
  }

  function drawScene(scene){
    content.replaceChildren();toolbar.replaceChildren();
    const elements=Array.isArray(scene.elements)?scene.elements:[],bars=Array.isArray(scene.bars)?scene.bars:[];
    const editable=bar=>Boolean(bar?.id&&bar?.signature&&pieceOwner(bar));
    const isRemoved=bar=>removedEntries().some(piece=>piece.key===bar.key&&piece.id===bar.id&&piece.signature===bar.signature);
    const shortDescription=bar=>{
      const roles={completa:'completo',inicial:'pieza inicial',intermedia:'pieza intermedia',terminal:'pieza terminal'};
      const levels={superior:'superior',inferior:'inferior',lateral:'lateral'};
      const wing=wingIdentity(bar),fallback=wing?`Ala ${wing[1]==='left'?'izquierda':'derecha'} · ${wingGroupLabel(wing[2])} · posición ${Number(wing[3])+1}`:'Armadura';
      return [bar.mark?`Marca ${bar.mark}`:bar.label||fallback,Number.isFinite(bar.diameter_mm)?`Ø${bar.diameter_mm} mm`:null,Number.isFinite(bar.length_cm)?`L=${bar.length_cm.toLocaleString('es-CL')} cm`:null,roles[bar.piece_role],levels[bar.level]].filter(Boolean).join(' · ');
    };
    for(const bar of [...bars,...(scene.removed_bars||[])])if(bar.id&&bar.signature){
      const key=pieceKey(bar),previous=pieceSession.labels.get(key);
      const description=bar.status==='unresolved'&&previous?previous.replace(/ · Revisar$/,''):shortDescription(bar);
      pieceSession.labels.set(key,description+(bar.status==='unresolved'?' · Revisar':''));
    }
    const saved=viewState;
    let selectedPiece=saved?.selectedPiece?bars.find(bar=>editable(bar)&&bar.id===saved.selectedPiece.id&&bar.signature===saved.selectedPiece.signature)||null:null;
    let candidateBars=selectedPiece?[selectedPiece]:[],hitItems=[];
    const known=new Set(saved?.known||[]),visible=new Set(saved?.visible||[]);
    for(const element of elements){if(!known.has(element.key))visible.add(element.key);known.add(element.key);}
    const markKey=bar=>JSON.stringify([bar.element_key||'abutment.footing',String(bar.mark||'')]);
    const knownMarks=new Set(saved?.knownMarks||[]),visibleMarks=new Set(saved?.visibleMarks||[]);
    for(const bar of bars){const key=markKey(bar);if(!knownMarks.has(key))visibleMarks.add(key);knownMarks.add(key);}
    const families=[...new Set(bars.map(bar=>bar.key||bar.mark||'Armadura'))];
    const color=bar=>COLORS[families.indexOf(bar.key||bar.mark||'Armadura')%COLORS.length];
    const runKey=bar=>JSON.stringify([bar.element_key||'abutment.footing',bar.placement_id||bar.key]);
    const runs=new Map();
    for(const bar of bars){const key=runKey(bar);if(!runs.has(key))runs.set(key,[]);runs.get(key).push(bar);}
    let selectionKey=saved?.selected??selectedElementKey;
    let selected=elements.some(item=>item.key===selectionKey)?selectionKey:null;
    let yaw=saved?.yaw??ISO_YAW,pitch=saved?.pitch??ISO_PITCH,zoom=saved?.zoom??1,opacity=saved?.opacity??.08,showBars=saved?.showBars??true;
    let target=saved?.target?.slice()||[0,0,0],baseScale=saved?.baseScale??1,frame=null;
    const layout=node('div',undefined,'iso-layout'),stage=node('div',undefined,'iso-stage');
    const viewport=node('div',undefined,'iso-viewport');
    const svg=svgNode('svg',{viewBox:'0 0 1000 700',role:'img','aria-label':`Isométrica de ${title.toLowerCase()} con moldajes atenuados y armaduras`,tabindex:0});
    viewport.append(svg);stage.append(viewport);layout.append(stage);
    const piecePanel=node('div',undefined,'iso-piece-panel');piecePanel.hidden=true;piecePanel.setAttribute('aria-label','Fierro seleccionado');stage.append(piecePanel);
    const history=node('div',undefined,'iso-piece-history'),undo=node('button','Deshacer eliminación');undo.type='button';
    const removedSummary=node('span'),restoreLink=node('button','Ver eliminados');restoreLink.type='button';restoreLink.onclick=expand;
    history.append(removedSummary,undo);if(embedded)history.append(restoreLink);stage.append(history);
    content.append(layout);
    captureView=()=>elements.length?{yaw,pitch,zoom,opacity,showBars,target:target.slice(),baseScale,selected:selectionKey,selectedPiece:selectedPiece?{id:selectedPiece.id,signature:selectedPiece.signature}:null,visible:[...visible],known:[...known],visibleMarks:[...visibleMarks],knownMarks:[...knownMarks],hasGeometry:true}:saved;
    function action(label,fn){const button=node('button',label);button.type='button';button.onclick=fn;toolbar.append(button);return button;}
    action('−',()=>{zoomAt(1/1.2);render();}).setAttribute('aria-label','Alejar');
    action('+',()=>{zoomAt(1.2);render();}).setAttribute('aria-label','Acercar');
    action('Ajustar',()=>{fit();render();});
    action('Isométrica',()=>{yaw=ISO_YAW;pitch=ISO_PITCH;fit();render();});
    const checks=[],selectionButtons=[],markButtons=[];
    let removedList=null;
    let barsToggle=null,selectionNote=null;
    if(!embedded){
    const aside=node('aside',undefined,'iso-aside');aside.setAttribute('aria-label','Elementos y moldajes');layout.prepend(aside);
    aside.append(node('h3','Elementos y marcas'),node('p','Pulsa una marca para mostrar u ocultar sus fierros.','muted'));
    const all=node('button','Ver conjunto');all.type='button';all.onclick=()=>{selected=null;selectionKey=null;visible.clear();known.clear();elements.forEach(item=>{visible.add(item.key);known.add(item.key);});checks.forEach(check=>check.checked=true);setTarget();updateSelection();render();};aside.append(all);
    const list=node('div',undefined,'iso-element-list');aside.append(list);
    for(const element of elements){
      const row=node('div',undefined,'iso-element'),name=node('div',undefined,'iso-element-name'),check=node('input');check.type='checkbox';check.checked=visible.has(element.key);check.setAttribute('aria-label',`Mostrar ${element.label}`);checks.push(check);
      check.onchange=()=>{check.checked?visible.add(element.key):visible.delete(element.key);render();};
      const choose=node('button',element.label,'iso-element-focus');choose.type='button';choose.onclick=()=>{selected=selected===element.key?null:element.key;selectionKey=selected;setTarget(selected);updateSelection();render();};selectionButtons.push({choose,element});name.append(check,choose);row.append(name);
      const marks=node('div',undefined,'iso-marks');marks.setAttribute('role','group');marks.setAttribute('aria-label',`Marcas de ${element.label}`);
      const seen=new Set();
      for(const bar of bars.filter(item=>(item.element_key||'abutment.footing')===element.key)){
        const key=markKey(bar);if(!bar.mark||seen.has(key))continue;seen.add(key);
        const toggle=node('button',String(bar.mark),'iso-mark');toggle.type='button';toggle.style.setProperty('--mark-color',color(bar));
        toggle.setAttribute('aria-label',`Mostrar marca ${bar.mark} · ${element.label}`);toggle.title=barDescription(bar);
        markButtons.push({toggle,key,elementKey:element.key});
        toggle.onclick=()=>{
          if(showBars&&visible.has(element.key)&&visibleMarks.has(key))visibleMarks.delete(key);
          else{visibleMarks.add(key);visible.add(element.key);check.checked=true;showBars=true;barsToggle.checked=true;}
          render();
        };marks.append(toggle);
      }
      if(seen.size)row.append(marks);list.append(row);
    }
    const opacityLabel=node('label',undefined,'iso-opacity'),opacityText=node('span',`Intensidad del moldaje · ${Math.round(opacity*100)} %`),opacityInput=node('input');
    opacityInput.type='range';opacityInput.min='0';opacityInput.max='30';opacityInput.value=String(Math.round(opacity*100));opacityInput.setAttribute('aria-label','Intensidad del moldaje');
    opacityInput.oninput=()=>{opacity=Number(opacityInput.value)/100;opacityText.textContent=`Intensidad del moldaje · ${opacityInput.value} %`;render();};opacityLabel.append(opacityText,opacityInput);aside.append(opacityLabel);
    const barsLabel=node('label',undefined,'iso-setting');barsToggle=node('input');barsToggle.type='checkbox';barsToggle.checked=showBars;barsToggle.onchange=()=>{showBars=barsToggle.checked;render();};barsLabel.append(barsToggle,node('span','Mostrar armaduras'));aside.append(barsLabel);
    selectionNote=node('p',undefined,'iso-note');aside.append(selectionNote);
    removedList=node('details',undefined,'iso-removed-pieces');aside.append(removedList);
    const issues=Array.isArray(scene.issues)?scene.issues:[];
    if(issues.length){const details=node('details',undefined,'iso-issues');details.append(node('summary',`Datos y alcance de la vista · ${issues.length}`));for(const issue of issues)details.append(node('p',typeof issue==='string'?issue:issue.message));aside.append(details);}
    }
    function changedPieces(){
      pieceSession.revision++;ctx.changed?.();
      selectedPiece=null;candidateBars=[];refreshPieceControls();render();
      try{Promise.resolve(options.onPiecesChanged?.(instanceKey)).catch(error=>notify(error.message));}
      catch(error){notify(error.message);}
      update();
    }
    function restorePiece(entry){
      if(!alive())return;
      const rule=pieceOwner(entry);
      if(!rule)return;
      const entries=rule.removed_pieces||[];
      const next=entries.filter(piece=>piece.id!==entry.id||piece.signature!==entry.signature);
      if(next.length===entries.length)return;
      rule.removed_pieces=next;
      pieceSession.undo=pieceSession.undo.filter(piece=>pieceKey(piece)!==pieceKey(entry));
      changedPieces();
    }
    undo.onclick=()=>{
      const removed=removedEntries();
      const last=[...pieceSession.undo].reverse().find(entry=>removed.some(piece=>pieceKey(piece)===pieceKey(entry)));
      if(last)restorePiece(last);
    };
    restoreLastDeletion=undo.onclick;
    function removePiece(bar){
      if(!alive()||!editable(bar))return;
      if(dialog.getAttribute('aria-busy')==='true'||sceneStateSignature!==currentStateSignature()){
        notify('La armadura cambió. Espera la vista actualizada y selecciona nuevamente el fierro.');update();return;
      }
      const rule=pieceOwner(bar);
      rule.removed_pieces??=[];
      if(isRemoved(bar))return;
      rule.removed_pieces.push({id:bar.id,signature:bar.signature});
      pieceSession.undo.push({key:bar.key,id:bar.id,signature:bar.signature});
      changedPieces();
    }
    function removedLabel(entry){
      if(pieceSession.labels.has(pieceKey(entry)))return pieceSession.labels.get(pieceKey(entry));
      const wing=wingIdentity(entry);
      if(wing){
        const groups={vertical_main:'Vertical del ala',vertical_extension:'Vertical de la aleta',horizontal_main:'Horizontal principal',horizontal_upper:'Horizontal superior',supplement_front:'Suples hacia el frontal',supplement_back:'Suples hacia el espaldar',edge:'Fierro de canto'};
        return `Ala ${wing[1]==='left'?'izquierda':'derecha'} · ${wingGroupLabel(wing[2])} · ${groups[wing[2].replace(/^inner_/,'')]||'Armadura'} · posición ${Number(wing[3])+1}`;
      }
      const parts=entry.id.split(':'),level={superior:'superior',inferior:'inferior','-1':'cara 1','1':'cara 2'}[parts[1]]||'';
      return `${entry.rule.label||'Armadura'} · ${level} · posición ${Number(parts[2])+1} · pieza ${Number(parts[3])+1}`;
    }
    function refreshPieceControls(){
      const removed=removedEntries();
      history.hidden=!removed.length;
      removedSummary.textContent=`${removed.length} ${removed.length===1?'fierro eliminado':'fierros eliminados'}`;
      undo.hidden=!pieceSession.undo.some(entry=>removed.some(piece=>pieceKey(piece)===pieceKey(entry)));
      if(removedList){
        const open=removedList.open;removedList.replaceChildren();removedList.hidden=!removed.length;
        if(removed.length)removedList.append(node('summary',`Fierros eliminados · ${removed.length}`));removedList.open=open;
        for(const entry of removed){
          const row=node('div',undefined,'iso-removed-piece'),restore=node('button','Restaurar');restore.type='button';
          restore.setAttribute('aria-label',`Restaurar ${removedLabel(entry)}`);restore.onclick=()=>restorePiece(entry);
          row.append(node('span',removedLabel(entry)),restore);removedList.append(row);
        }
      }
      piecePanel.replaceChildren();piecePanel.hidden=!selectedPiece;
      if(!selectedPiece)return;
      piecePanel.dataset.piece=selectedPiece.id;piecePanel.append(node('strong',shortDescription(selectedPiece)));
      if(candidateBars.length>1){
        const label=node('label',`Fierros bajo el cursor · ${candidateBars.length}`),select=node('select');
        select.setAttribute('aria-label','Elegir fierro superpuesto');
        candidateBars.forEach((bar,index)=>{const option=node('option',`${index+1}. ${shortDescription(bar)}`);option.value=String(index);select.append(option);});
        select.value=String(candidateBars.indexOf(selectedPiece));select.onchange=()=>{selectedPiece=candidateBars[Number(select.value)];refreshPieceControls();render();};
        label.append(select);piecePanel.append(label);
      }
      const actions=node('div',undefined,'iso-piece-actions'),remove=node('button','Eliminar este fierro','iso-piece-delete'),clear=node('button','Cancelar selección');
      remove.type=clear.type='button';const captured=selectedPiece;remove.onclick=()=>removePiece(captured);
      remove.disabled=!editable(captured)||dialog.getAttribute('aria-busy')==='true';
      clear.onclick=()=>{selectedPiece=null;candidateBars=[];refreshPieceControls();render();};
      actions.append(remove,clear);piecePanel.append(actions);
    }
    refreshEditControls=refreshPieceControls;
    function updateSelection(){
      for(const {choose,element} of selectionButtons)choose.setAttribute('aria-pressed',String(element.key===selected));
      const element=elements.find(item=>item.key===selected);
      if(selectionNote)selectionNote.textContent=element?`${element.label}${element.quality==='schematic'?' · Perfil esquemático':''}. ${element.note||'Elemento resaltado dentro del conjunto.'}`:'Selecciona un elemento para centrar la órbita. Su casilla muestra u oculta el elemento.';
    }
    function geometryPoints(key=null){
      const points=elements.filter(item=>key?item.key===key:visible.has(item.key)).flatMap(item=>(item.meshes||[]).flatMap(mesh=>mesh.vertices));
      if(showBars)for(const bar of bars)if(!isRemoved(bar)&&visibleMarks.has(markKey(bar))&&(key?(bar.element_key||'abutment.footing')===key:visible.has(bar.element_key||'abutment.footing')))points.push(...bar.points);
      return points;
    }
    function boundsOf(points){
      if(!points.length)return null;
      const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
      for(const point of points)for(let i=0;i<3;i++){min[i]=Math.min(min[i],point[i]);max[i]=Math.max(max[i],point[i]);}
      return {center:min.map((value,i)=>(value+max[i])/2),diameter:Math.hypot(...min.map((value,i)=>max[i]-value))};
    }
    function setTarget(key=null){const bounds=boundsOf(geometryPoints(key));if(bounds)target=bounds.center;}
    function fit(){
      const bounds=boundsOf(geometryPoints());
      if(!bounds)return;
      target=bounds.center;zoom=1;
      // Like Cadence's orthographic camera, fit once to a bounding sphere.
      // Orbiting, hiding elements and changing opacity must never refit it.
      baseScale=550/Math.max(bounds.diameter*1.15,.01);
    }
    function rotate(point){
      const [x,y,z]=point.map((value,i)=>value-target[i]),u=Math.cos(yaw)*x-Math.sin(yaw)*y,v=Math.sin(yaw)*x+Math.cos(yaw)*y;
      // No roll: world Z always projects vertically upwards, even below the model.
      return [u,Math.sin(pitch)*v-Math.cos(pitch)*z,Math.cos(pitch)*v+Math.sin(pitch)*z];
    }
    function shiftTarget(x,y){
      const right=[Math.cos(yaw),-Math.sin(yaw),0],down=[Math.sin(pitch)*Math.sin(yaw),Math.sin(pitch)*Math.cos(yaw),-Math.cos(pitch)];
      target=target.map((value,i)=>value+right[i]*x+down[i]*y);
    }
    function zoomAt(factor,anchor={x:500,y:340}){
      const next=Math.max(.1,Math.min(40,zoom*factor)),delta=1/(baseScale*zoom)-1/(baseScale*next);
      shiftTarget((anchor.x-500)*delta,(anchor.y-340)*delta);zoom=next;
    }
    function localPoint(event){return new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse());}
    function scheduleRender(){if(frame===null)frame=requestAnimationFrame(()=>{frame=null;if(alive())render();});}
    function render(){
      if(frame!==null){cancelAnimationFrame(frame);frame=null;}
      for(const {toggle,key,elementKey} of markButtons){
        const shown=showBars&&visible.has(elementKey)&&visibleMarks.has(key);
        toggle.setAttribute('aria-pressed',String(shown));toggle.dataset.visible=String(shown);
      }
      svg.replaceChildren();
      svg.dataset.zoom=String(zoom);svg.dataset.yaw=String(yaw);svg.dataset.pitch=String(pitch);
      svg.dataset.scale=String(baseScale*zoom);svg.dataset.target=JSON.stringify(target);
      const active=elements.filter(item=>visible.has(item.key)),allPoints=active.flatMap(item=>(item.meshes||[]).flatMap(mesh=>mesh.vertices));
      const removedKeys=new Set(removedEntries().map(pieceKey));
      const activeBars=showBars?bars.filter(bar=>!removedKeys.has(pieceKey(bar))&&visible.has(bar.element_key||'abutment.footing')&&visibleMarks.has(markKey(bar))):[];
      if(selectedPiece&&!activeBars.includes(selectedPiece)){selectedPiece=null;candidateBars=[];refreshPieceControls();}
      hitItems=[];
      for(const bar of activeBars)allPoints.push(...bar.points);
      if(!allPoints.length){svg.append(svgNode('text',{x:500,y:350,'text-anchor':'middle'},'No hay elementos visibles con geometría disponible.'));return;}
      const scale=baseScale*zoom;
      const screen=point=>{const [u,v,d]=rotate(point);return [500+u*scale,340+v*scale,d];};
      const faces=[],edges=[];
      for(const element of active)for(const mesh of element.meshes||[]){
        const projected=mesh.vertices.map(screen),seen=new Set();
        for(const face of mesh.faces){
          const pts=face.map(index=>projected[index]);faces.push({element,pts,depth:pts.reduce((sum,p)=>sum+p[2],0)/pts.length});
          for(let i=0;i<face.length;i++){const a=face[i],b=face[(i+1)%face.length],key=[Math.min(a,b),Math.max(a,b)].join(':');if(!seen.has(key)){seen.add(key);edges.push({element,a:projected[a],b:projected[b]});}}
        }
      }
      const faceGroup=svgNode('g',{'data-layer':'moldajes'});
      faces.sort((a,b)=>a.depth-b.depth);
      for(const {element,pts} of faces){const focused=selected===element.key;faceGroup.append(svgNode('polygon',{points:pts.map(p=>p.slice(0,2).join(',')).join(' '),fill:focused?'var(--accent)':'#aab6c6','fill-opacity':opacity*(selected&&!focused ? .3 : 1),'data-element':element.key}));}
      for(const {element,a,b} of edges){const focused=selected===element.key;faceGroup.append(svgNode('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:focused?'var(--accent)':'#aab6c6','stroke-opacity':opacity===0?0:Math.min(.7,opacity*3)*(selected&&!focused ? .35 : 1),'stroke-width':focused?1.4:1}));}
      svg.append(faceGroup);
      const steelGroup=svgNode('g',{'data-layer':'armaduras',fill:'none','stroke-linejoin':'round','stroke-linecap':'round'});
      for(const bar of activeBars){
        const points=bar.points.map(screen),picked=bar===selectedPiece;
        if(editable(bar))hitItems.push({bar,points});
        const line=svgNode('polyline',{points:points.map(p=>p.slice(0,2).join(',')).join(' '),stroke:picked?'#ffffff':color(bar),'stroke-width':picked?4.2:1.8,'stroke-opacity':picked?1:selected&&selected!==(bar.element_key||'abutment.footing') ? .2 : .92,'data-mark':bar.mark||'','data-family':bar.key||'','data-piece':bar.id||'','data-selected-piece':String(picked),'data-role':bar.piece_role||'', 'data-element':bar.element_key||'abutment.footing'});
        line.append(svgNode('title',{},barDescription(bar)));steelGroup.append(line);
      }
      // Real lap partners touch on parallel axes. Keep the ordinary line
      // weight: their physical separation already comes from the assembly.
      const activeBarSet=new Set(activeBars);
      for(const bar of activeBars)for(const [index,segment] of (bar.lap_segments||[]).entries()){
        const partner=bar.lap_partners?.[index];
        if(!runs.get(runKey(bar)).some(other=>other!==bar&&activeBarSet.has(other)&&
          (partner?other.id===partner.piece_id&&containsLap(other,partner.segment):containsLap(other,segment))))continue;
        const [first,last]=segment.map(screen);
        const line=svgNode('line',{x1:first[0],y1:first[1],x2:last[0],y2:last[1],stroke:color(bar),'stroke-width':1.8,'stroke-opacity':selected&&selected!==(bar.element_key||'abutment.footing') ? .2 : .92,'data-lap':`${bar.id||bar.mark||''}:${index}`,'data-mark':bar.mark||'','data-element':bar.element_key||'abutment.footing'});
        line.append(svgNode('title',{},`${barDescription(bar)} · Zona de traslapo`));steelGroup.append(line);
      }
      svg.append(steelGroup);
      // Keep a selected piece legible beside its contacting lap partner.
      // This overlay changes only selection emphasis, not geometry.
      if(selectedPiece&&activeBars.includes(selectedPiece)){
        svg.append(svgNode('polyline',{points:selectedPiece.points.map(p=>screen(p).slice(0,2).join(',')).join(' '),fill:'none',stroke:'#ffffff','stroke-width':4.2,'stroke-linejoin':'round','stroke-linecap':'round','pointer-events':'none','data-piece-highlight':selectedPiece.id}));
      }
      const axes=svgNode('g',{'aria-hidden':true});
      for(const [label,point,tint] of [['X',[1,0,0],'#ff8c77'],['Y',[0,1,0],'#69d9b1'],['Z',[0,0,1],'#56c9f2']]){
        const end=rotate(point.map((value,i)=>value+target[i])),x=65+end[0]*34,y=640+end[1]*34;
        axes.append(svgNode('line',{x1:65,y1:640,x2:x,y2:y,stroke:tint,'stroke-width':2,'data-axis':label}),svgNode('text',{x:x+5,y:y+4,fill:tint},label));
      }
      axes.append(svgNode('text',{x:900,y:660,'text-anchor':'end'},'Vista local · m'));svg.append(axes);
    }
    function containsLap(bar,segment){
      const points=bar.main_start&&bar.main_end?[bar.main_start,bar.main_end]:bar.points;
      const onSegment=(point,a,b)=>{
        const axis=b.map((value,i)=>value-a[i]),length2=axis.reduce((sum,value)=>sum+value*value,0);
        if(length2<1e-16)return false;
        const t=point.reduce((sum,value,i)=>sum+(value-a[i])*axis[i],0)/length2;
        return t>=-1e-8&&t<=1+1e-8&&Math.hypot(...point.map((value,i)=>value-a[i]-t*axis[i]))<1e-7;
      };
      return points.some((point,i)=>i>0&&segment.every(end=>onSegment(end,points[i-1],point)));
    }
    function pickPiece(clientX,clientY){
      if(dialog.getAttribute('aria-busy')==='true'||sceneStateSignature!==currentStateSignature())return;
      const matrix=svg.getScreenCTM();if(!matrix)return;
      const hits=[];
      for(const {bar,points} of hitItems){
        let distance=Infinity,depth=-Infinity;
        for(let i=1;i<points.length;i++){
          const a=new DOMPoint(points[i-1][0],points[i-1][1]).matrixTransform(matrix),b=new DOMPoint(points[i][0],points[i][1]).matrixTransform(matrix);
          const dx=b.x-a.x,dy=b.y-a.y,length2=dx*dx+dy*dy;
          const t=length2?Math.max(0,Math.min(1,((clientX-a.x)*dx+(clientY-a.y)*dy)/length2)):0;
          const next=Math.hypot(clientX-a.x-t*dx,clientY-a.y-t*dy);
          if(next<distance){distance=next;depth=points[i-1][2]+t*(points[i][2]-points[i-1][2]);}
        }
        if(distance<=6)hits.push({bar,distance,depth});
      }
      hits.sort((a,b)=>Math.abs(a.distance-b.distance)>.5?a.distance-b.distance:b.depth-a.depth);
      candidateBars=hits.map(hit=>hit.bar);selectedPiece=candidateBars[0]||null;
      refreshPieceControls();render();
    }
    let drag=null,pickGesture=null;
    const touches=new Map();
    function touchState(){
      const points=[...touches.values()];
      return {center:{x:points.reduce((sum,p)=>sum+p.x,0)/points.length,y:points.reduce((sum,p)=>sum+p.y,0)/points.length},distance:points.length===2?Math.hypot(points[1].x-points[0].x,points[1].y-points[0].y):0};
    }
    function pan(from,to){shiftTarget((from.x-to.x)/(baseScale*zoom),(from.y-to.y)/(baseScale*zoom));}
    svg.addEventListener('pointerdown',event=>{
      const touch=event.pointerType==='touch';
      if((touch&&!touches.size&&!drag)||(!touch&&event.button===0&&!drag&&!touches.size))pickGesture={id:event.pointerId,x:event.clientX,y:event.clientY,moved:false};
      else pickGesture=null;
      if(touch?(drag||touches.size>=2):(event.button!==1||drag||touches.size))return;
      event.preventDefault();svg.focus({preventScroll:true});svg.setPointerCapture(event.pointerId);
      if(touch)touches.set(event.pointerId,localPoint(event));
      else drag={id:event.pointerId,orbit:event.shiftKey||event.ctrlKey,x:event.clientX,y:event.clientY,point:localPoint(event)};
      svg.style.cursor='grabbing';
    });
    svg.addEventListener('pointermove',event=>{
      if(pickGesture?.id===event.pointerId&&Math.hypot(event.clientX-pickGesture.x,event.clientY-pickGesture.y)>4)pickGesture.moved=true;
      if(touches.has(event.pointerId)){
        const before=touchState();touches.set(event.pointerId,localPoint(event));const after=touchState();
        pan(before.center,after.center);
        if(before.distance>0&&after.distance>0)zoomAt(after.distance/before.distance,after.center);
      }else if(drag?.id===event.pointerId){
        if(!(event.buttons&4)){endGesture(event);return;}
        const point=localPoint(event);
        if(drag.orbit){const sensitivity=2*Math.PI/Math.max(svg.getBoundingClientRect().height,1);yaw-=(event.clientX-drag.x)*sensitivity;pitch=clampPitch(pitch+(event.clientY-drag.y)*sensitivity);}
        else pan(drag.point,point);
        drag={...drag,x:event.clientX,y:event.clientY,point};
      }else return;
      event.preventDefault();scheduleRender();
    });
    function endGesture(event){
      const pick=pickGesture?.id===event.pointerId?pickGesture:null;
      if(pick)pickGesture=null;
      if(drag?.id===event.pointerId)drag=null;
      touches.delete(event.pointerId);
      if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId);
      if(!drag&&!touches.size)svg.style.cursor='';
      if(event.type==='pointerup'&&pick&&!pick.moved)pickPiece(event.clientX,event.clientY);
    }
    function cancelGestures(){
      const ids=[...touches.keys(),...(drag?[drag.id]:[])];drag=null;pickGesture=null;touches.clear();svg.style.cursor='';
      for(const id of ids)if(svg.hasPointerCapture(id))svg.releasePointerCapture(id);
    }
    for(const eventName of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(eventName,endGesture);
    window.addEventListener('blur',cancelGestures);
    disposeScene=()=>{cancelGestures();window.removeEventListener('blur',cancelGestures);if(frame!==null)cancelAnimationFrame(frame);};
    svg.addEventListener('auxclick',event=>{if(event.button===1)event.preventDefault();});
    svg.addEventListener('wheel',event=>{
      event.preventDefault();if(!event.deltaY)return;
      const delta=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?svg.clientHeight:1);
      zoomAt(Math.pow(1.2,-delta/100),localPoint(event));scheduleRender();
    },{passive:false});
    svg.addEventListener('keydown',event=>{
      if(event.key==='ArrowLeft')yaw-=.15;else if(event.key==='ArrowRight')yaw+=.15;
      else if(event.key==='ArrowUp')pitch=clampPitch(pitch+.15);else if(event.key==='ArrowDown')pitch=clampPitch(pitch-.15);
      else if(event.key==='+')zoomAt(1.2);else if(event.key==='-')zoomAt(1/1.2);else return;
      event.preventDefault();render();
    });
    if(!saved?.hasGeometry){fit();if(selected)setTarget(selected);}updateSelection();refreshPieceControls();render();
  }
  return {update,dispose,ready:load()};
}
