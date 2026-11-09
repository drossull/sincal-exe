// Local beam views. Definition samples never imply a steel distribution or CAD job.
const NS='http://www.w3.org/2000/svg';
const selections=new WeakMap();
const format=(value,digits=3)=>Number(value).toLocaleString('es-CL',{maximumFractionDigits:digits});
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const validPoint=p=>Array.isArray(p)&&p.length===2&&p.every(finite);
const valid3=p=>Array.isArray(p)&&p.length===3&&p.every(finite);
const labels={front:'Frontal',plan:'Planta',elevation:'Elevación',isometric:'Isométrica'};
const ariaLabels={front:'Vista frontal de la viga',plan:'Vista en planta de la viga',elevation:'Vista en elevación de la viga',isometric:'Vista isométrica de la viga'};
const defaultYaw=Math.PI/4,defaultPitch=Math.atan(1/Math.sqrt(2));
function svgNode(tag,attributes,text){
  const element=document.createElementNS(NS,tag);
  for(const [key,value]of Object.entries(attributes||{}))element.setAttribute(key,String(value));
  if(text!==undefined)element.textContent=text;
  return element;
}

export async function renderBeamPreview(ctx){
  const {project,api,node,section,notify,current}=ctx;
  const root=section('estructura','Viga');root.classList.add('rebar-beam-page');
  if(!project?.data||!Object.keys(project.data).length){
    root.append(node('p','Incorpora el JSON del puente en Proyecto para ver la viga.','muted'));return;
  }
  const sourceData=project.data;
  const selected={board_index:0,beam_index:0,...selections.get(project)};
  let revision=0,disposed=false,data=null,dialog=null,active='isometric',scope='sample',metrics=null,drag=null,issuesSignature=null;
  const cameras=new Map();
  const camera=()=>{
    const key=`${scope}:${active}`;
    if(!cameras.has(key))cameras.set(key,{zoom:1,pan:0,vertical:0,yaw:defaultYaw,pitch:defaultPitch});
    return cameras.get(key);
  };
  const alive=()=>!disposed&&root.isConnected&&current()&&project.data===sourceData;
  const intro=node('p','Vistas del moldaje y de la sección de armaduras en definición.','rebar-beam-intro');
  const selectors=node('div',undefined,'rebar-beam-selectors');
  const boardLabel=node('label','Tablero'),boardSelect=node('select');boardSelect.setAttribute('aria-label','Tablero de la viga');boardLabel.append(boardSelect);
  const beamLabel=node('label','Viga'),beamSelect=node('select');beamSelect.setAttribute('aria-label','Viga del tablero');beamLabel.append(beamSelect);selectors.append(boardLabel,beamLabel);
  const summary=node('p','','rebar-beam-summary');
  const status=node('p','Leyendo la geometría de la viga…','rebar-beam-status');status.setAttribute('role','status');
  const messages=node('div',undefined,'rebar-beam-messages');
  const viewer=node('div',undefined,'rebar-beam-viewer');
  const viewsToolbar=node('div',undefined,'rebar-beam-view-buttons');viewsToolbar.setAttribute('aria-label','Elegir vista de la viga');
  const toolbar=node('div',undefined,'rebar-beam-toolbar');toolbar.setAttribute('aria-label','Controles de las vistas de la viga');
  const scopeLabel=node('label','Mostrar','rebar-beam-scope'),scopeSelect=node('select');scopeSelect.setAttribute('aria-label','Alcance de la vista de viga');
  const sampleOption=node('option','Tramo de muestra');sampleOption.value='sample';
  const fullOption=node('option','Viga completa');fullOption.value='full';scopeSelect.append(sampleOption,fullOption);scopeLabel.append(scopeSelect);
  const zoomLabel=node('span','100 %','rebar-beam-zoom');
  function button(label,action,aria){const b=node('button',label);b.type='button';if(aria)b.setAttribute('aria-label',aria);b.addEventListener('click',action);return b;}
  const viewButtons=Object.entries(labels).map(([key,label])=>{
    const b=button(label,()=>{endDrag();active=key;redraw();});b.setAttribute('aria-pressed',String(key===active));b.dataset.viewButton=key;viewsToolbar.append(b);return b;
  });
  const zoomOut=button('−',()=>changeZoom(1/1.4),'Alejar vistas de la viga');
  const zoomIn=button('+',()=>changeZoom(1.4),'Acercar vistas de la viga');
  function resetCamera(){Object.assign(camera(),{zoom:1,pan:0,vertical:0,yaw:defaultYaw,pitch:defaultPitch});}
  const fit=button('Ajustar',()=>{resetCamera();redraw();});
  const expand=button('Ampliar vistas',()=>openExpanded());expand.classList.add('rebar-beam-expand');
  toolbar.append(scopeLabel,zoomOut,zoomIn,fit,zoomLabel,expand);
  const drawings=node('div',undefined,'rebar-beam-drawings');
  const card=node('div',undefined,'rebar-beam-view'),title=node('h3','Isométrica');
  const svg=svgNode('svg',{class:'rebar-beam-svg',role:'img','aria-label':ariaLabels.isometric,tabindex:0});
  card.append(title,svg);drawings.append(card);
  const help=node('p','','rebar-beam-help');
  viewer.append(viewsToolbar,toolbar,drawings,help);viewer.hidden=true;selectors.hidden=true;
  root.append(intro,selectors,summary,status,messages,viewer);

  function projectPoint([x,y,z]){
    if(active==='front')return [x,z,y];
    if(active==='plan')return [y,x,z];
    if(active==='elevation')return [y,z,x];
    const c=camera(),co=Math.cos(c.yaw),si=Math.sin(c.yaw),sp=Math.sin(c.pitch),cp=Math.cos(c.pitch);
    return [x*co+y*si,(-x*si+y*co)*sp+z*cp,(x*si-y*co)*cp+z*sp];
  }
  function sceneData(){
    const scene=scope==='full'?data?.full_scene:data?.scene;
    if(!Array.isArray(scene?.vertices)||!scene.vertices.length||!scene.vertices.every(valid3))return null;
    const points=scene.vertices.map(projectPoint);
    const faces=(scene.faces||[]).filter(face=>Array.isArray(face)&&face.length>=3&&face.every(i=>Number.isInteger(i)&&i>=0&&i<points.length));
    const edges=(scene.edges||[]).filter(edge=>Array.isArray(edge)&&edge.length===2&&edge.every(i=>Number.isInteger(i)&&i>=0&&i<points.length));
    const bars=scope==='sample'&&data.definition?.available?(data.definition.bars||[]).filter(b=>Array.isArray(b.points)&&b.points.length>=2&&b.points.every(valid3)):[];
    return {scene,points,faces,edges,bars};
  }
  function draw(){
    if(!data?.valid){svg.replaceChildren();metrics=null;return;}
    const c=camera(),scene=sceneData();
    const flat=scope==='full'&&(active==='plan'||active==='elevation')?data.views?.[active]:null;
    const hasFlat=flat&&Array.isArray(flat.outline)&&flat.outline.length>=3&&flat.outline.every(validPoint);
    if(!scene&&!hasFlat){svg.replaceChildren();metrics=null;return;}
    const width=Math.max(240,svg.clientWidth),height=Math.max(240,svg.clientHeight);
    const bars=scene?.bars.map(bar=>({bar,points:bar.points.map(projectPoint)}))||[];
    const points=hasFlat?flat.outline:scene.points.concat(bars.flatMap(b=>b.points));
    const lo=[0,1].map(i=>Math.min(...points.map(p=>p[i]))),hi=[0,1].map(i=>Math.max(...points.map(p=>p[i])));
    if(hasFlat){lo[0]=Math.min(lo[0],0);hi[0]=Math.max(hi[0],data.geometry.length_projected_m);}
    let center=(lo[0]+hi[0])/2,centerY=(lo[1]+hi[1])/2;
    let baseScale=Math.min((width-72)/Math.max(.01,hi[0]-lo[0]),(height-90)/Math.max(.01,hi[1]-lo[1]));
    if(active==='isometric'&&scene){
      // Fit the fixed 3D bounding sphere so orbiting never pumps the scale.
      const world=scene.scene.vertices.concat(scene.bars.flatMap(bar=>bar.points));
      const min=[0,1,2].map(i=>Math.min(...world.map(p=>p[i]))),max=[0,1,2].map(i=>Math.max(...world.map(p=>p[i])));
      [center,centerY]=projectPoint(min.map((v,i)=>(v+max[i])/2));
      const diameter=Math.hypot(...max.map((v,i)=>v-min[i]));
      baseScale=Math.min(width-72,height-90)/Math.max(.01,diameter);
    }
    center+=c.pan;centerY+=c.vertical;
    const scale=baseScale*c.zoom,screenCenterY=height/2-10;
    const x=u=>width/2+(u-center)*scale,y=v=>screenCenterY-(v-centerY)*scale;
    metrics={width,height,scale,baseScale,span:Math.max(.01,hi[0]-lo[0]),center,centerY,screenCenterY};
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('data-uniform-scale',String(scale));svg.setAttribute('data-view',active);svg.setAttribute('data-scope',scope);
    svg.setAttribute('data-camera-yaw',String(c.yaw));svg.setAttribute('data-camera-pitch',String(c.pitch));svg.setAttribute('data-z-vertical','true');
    svg.setAttribute('data-rebar-count',String(bars.length));
    const shapes=[];
    const polyline=(ps,cls,closed=false,extra={})=>svgNode(closed?'polygon':'polyline',{class:cls,points:ps.map(([u,v])=>`${x(u)},${y(v)}`).join(' '),...extra});
    if(hasFlat){
      shapes.push(polyline(flat.outline,'rebar-beam-outline',true));
      for(const edge of flat.lines||[])if(Array.isArray(edge)&&edge.length>1&&edge.every(validPoint))shapes.push(polyline(edge,'rebar-beam-edge'));
      const length=data.geometry.length_projected_m,dimY=Math.max(50,Math.min(height-29,y(lo[1])+25)),start=x(0),end=x(length),arrow=5;
      shapes.push(svgNode('line',{class:'rebar-beam-dimension',x1:start,y1:dimY,x2:end,y2:dimY}));
      for(const [at,sign]of [[start,1],[end,-1]]){
        shapes.push(svgNode('line',{class:'rebar-beam-extension',x1:at,y1:dimY-10,x2:at,y2:dimY+8}));
        shapes.push(svgNode('polygon',{class:'rebar-beam-arrow',points:`${at},${dimY} ${at+sign*arrow},${dimY-3} ${at+sign*arrow},${dimY+3}`}));
      }
      shapes.push(svgNode('text',{class:'rebar-beam-dimension-text',x:(start+end)/2,y:dimY-8,'text-anchor':'middle'},`${format(length)} m · largo proyectado`));
    }else{
      const faces=scene.faces.map(face=>face.map(i=>scene.points[i]));
      faces.sort((a,b)=>a.reduce((s,p)=>s+p[2],0)/a.length-b.reduce((s,p)=>s+p[2],0)/b.length);
      for(const face of faces)shapes.push(polyline(face,'rebar-beam-face',true));
      for(const edge of scene.edges)shapes.push(polyline(edge.map(i=>scene.points[i]),'rebar-beam-scene-edge'));
      bars.sort((a,b)=>a.points.reduce((s,p)=>s+p[2],0)/a.points.length-b.points.reduce((s,p)=>s+p[2],0)/b.points.length);
      for(const {bar,points:ps}of bars){
        const mark=String(bar.mark),known=['1','2','3','6','7','11'].includes(mark),diameter=finite(bar.diameter_mm)?bar.diameter_mm/1000:0;
        const path=polyline(ps,`rebar-beam-bar${known?` rebar-beam-mark-${mark}`:''}`,false,{'stroke-width':Math.max(1.4,diameter*scale),'data-mark':mark});
        path.append(svgNode('title',{},`Marca ${mark}${bar.partial_geometry?' · geometría parcial en definición':''}`));shapes.push(path);
      }
    }
    svg.replaceChildren(...shapes);
  }
  function redraw(){
    if(!alive())return;
    const c=camera();zoomLabel.textContent=`${Math.round(c.zoom*100)} %`;
    zoomOut.disabled=!data?.valid||c.zoom<=1;zoomIn.disabled=!data?.valid||c.zoom>=24;
    for(const b of viewButtons){b.setAttribute('aria-pressed',String(b.dataset.viewButton===active));b.disabled=!data?.valid;}
    scopeSelect.value=scope;title.textContent=labels[active];svg.setAttribute('aria-label',ariaLabels[active]);
    help.textContent=active==='isometric'?'Rueda: zoom al cursor · Central: desplazar · Mayús + central: orbitar · Z vertical.':'Rueda: zoom al cursor · Central: desplazar · Misma escala horizontal y vertical.';
    if(data?.valid){
      status.textContent=scope==='sample'?(data.definition?.available?'Tramo de muestra · familias alineadas en una sección; encuentros y reparto pendientes.':'Tramo de muestra del moldaje · armaduras pendientes para este perfil.'):'Viga completa · moldaje del proyecto, sin reparto de armaduras.';
      showIssues([...(data.issues||[]),...(scope==='sample'?(data.definition?.issues||[]):[])]);
    }
    draw();
  }
  function changeZoom(factor,anchor){
    if(!data?.valid)return;
    const c=camera(),previous=c.zoom,next=Math.max(1,Math.min(24,previous*factor));
    if(metrics&&validPoint(anchor)){
      const m=metrics,at=m.center+(anchor[0]-m.width/2)/m.scale,atY=m.centerY-(anchor[1]-m.screenCenterY)/m.scale;
      c.pan+=(at-m.center)*(1-previous/next);c.vertical+=(atY-m.centerY)*(1-previous/next);
    }
    c.zoom=next;if(next===1){c.pan=0;c.vertical=0;}redraw();
  }
  svg.addEventListener('wheel',event=>{if(!data?.valid)return;event.preventDefault();const box=svg.getBoundingClientRect();changeZoom(event.deltaY<0?1.15:1/1.15,[event.clientX-box.left,event.clientY-box.top]);},{passive:false});
  function endDrag(){
    if(!drag)return;const pointer=drag.pointer;drag=null;svg.classList.remove('rebar-beam-panning');
    if(svg.hasPointerCapture(pointer))svg.releasePointerCapture(pointer);
  }
  svg.addEventListener('pointerdown',event=>{
    if(event.button!==1||!data?.valid||!metrics)return;event.preventDefault();const c=camera();
    drag={pointer:event.pointerId,x:event.clientX,y:event.clientY,pan:c.pan,vertical:c.vertical,scale:metrics.scale,yaw:c.yaw,pitch:c.pitch,orbit:active==='isometric'&&event.shiftKey};
    svg.setPointerCapture(event.pointerId);svg.classList.add('rebar-beam-panning');
  });
  svg.addEventListener('pointermove',event=>{
    if(!drag||drag.pointer!==event.pointerId)return;const c=camera(),dx=event.clientX-drag.x,dy=event.clientY-drag.y;
    if(drag.orbit){c.yaw=drag.yaw+dx*.008;c.pitch=Math.max(Math.PI/36,Math.min(Math.PI*17/36,drag.pitch+dy*.008));}
    else{c.pan=drag.pan-dx/drag.scale;c.vertical=drag.vertical+dy/drag.scale;}redraw();
  });
  for(const name of ['pointerup','pointercancel'])svg.addEventListener(name,event=>{if(drag?.pointer===event.pointerId)endDrag();});
  svg.addEventListener('lostpointercapture',()=>{drag=null;svg.classList.remove('rebar-beam-panning');});
  svg.addEventListener('auxclick',event=>{if(event.button===1)event.preventDefault();});
  svg.addEventListener('keydown',event=>{
    if(!data?.valid||!metrics)return;const c=camera();
    if(event.key==='+'||event.key==='='){event.preventDefault();changeZoom(1.4);}
    else if(event.key==='-'){event.preventDefault();changeZoom(1/1.4);}
    else if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();c.pan+=(event.key==='ArrowRight'?1:-1)*metrics.span/c.zoom/8;redraw();}
    else if(event.key==='ArrowUp'||event.key==='ArrowDown'){event.preventDefault();c.vertical+=(event.key==='ArrowUp'?1:-1)*metrics.height/metrics.scale/8;redraw();}
    else if(event.key==='Home'){event.preventDefault();resetCamera();redraw();}
  });
  scopeSelect.addEventListener('change',()=>{endDrag();scope=scopeSelect.value;redraw();});
  const resize=new ResizeObserver(redraw);resize.observe(svg);
  function openExpanded(){
    if(!alive()||dialog||!data?.valid)return;
    dialog=node('dialog',undefined,'rebar-beam-dialog');dialog.setAttribute('aria-label','Viga · visor ampliado');
    const heading=node('div',undefined,'rebar-beam-dialog-heading'),close=button('Cerrar vistas',()=>dialog?.close());
    heading.append(node('h2',`${data.profile?.name||'Viga'} · visor ampliado`),close);dialog.append(heading,status,messages,viewer);document.body.append(dialog);expand.hidden=true;
    dialog.addEventListener('close',()=>{const previous=dialog;dialog=null;if(root.isConnected)root.append(status,messages,viewer);expand.hidden=false;previous.remove();redraw();},{once:true});
    dialog.showModal();redraw();
  }
  function options(select,items,selectedValue){select.replaceChildren(...items.map(([value,label])=>{const option=node('option',label);option.value=String(value);return option;}));select.value=String(selectedValue);}
  function updateSelectors(result){
    const boards=Array.isArray(result.boards)?result.boards:[];
    options(boardSelect,boards.map(board=>[board.index,board.label]),result.board_index??selected.board_index);
    const board=boards.find(item=>item.index===(result.board_index??selected.board_index)),count=Math.max(0,Math.min(1000,Number(board?.beam_count)||0));
    options(beamSelect,Array.from({length:count},(_,i)=>[i,`Viga ${i+1}`]),result.beam_index??selected.beam_index);
    selectors.hidden=!boards.length;boardSelect.disabled=!boards.length;beamSelect.disabled=!count;
  }
  function showIssues(issues){
    const values=Array.isArray(issues)?issues.map(issue=>typeof issue==='string'?issue:issue?.message||String(issue)):[];
    const signature=JSON.stringify(values);if(signature===issuesSignature)return;issuesSignature=signature;
    messages.replaceChildren();if(!values.length)return;
    const list=node('ul');for(const issue of values)list.append(node('li',issue));messages.append(list);
  }
  async function refresh(){
    endDrag();const request=++revision;data=null;viewer.hidden=true;svg.replaceChildren();metrics=null;summary.textContent='';status.textContent='Actualizando las vistas de la viga…';root.setAttribute('aria-busy','true');messages.replaceChildren();issuesSignature=null;
    try{
      const result=await api('rebar/beam/preview',{project:sourceData,board_index:selected.board_index,beam_index:selected.beam_index});
      if(!alive()||request!==revision)return;
      data=result;updateSelectors(result);showIssues(result.issues);
      if(!result.valid||!result.geometry){status.textContent='No se pudo reconstruir el moldaje con estos datos.';return;}
      selected.board_index=result.board_index;selected.beam_index=result.beam_index;selections.set(project,{...selected});
      const geometry=result.geometry;
      summary.textContent=`${result.profile?.name||'Viga'} · largo proyectado ${format(geometry.length_projected_m)} m · esviaje ${format(geometry.skew_degrees,2)}° · pendiente ${format(geometry.slope*100,2)} %`;
      sampleOption.disabled=!result.scene;if(scope==='sample'&&!result.scene)scope='full';viewer.hidden=false;redraw();
    }catch(error){if(alive()&&request===revision){status.textContent='No se pudo cargar la vista previa de la viga.';notify(error.message);}}
    finally{if(alive()&&request===revision)root.setAttribute('aria-busy','false');}
  }
  boardSelect.addEventListener('change',()=>{selected.board_index=Number(boardSelect.value);selected.beam_index=0;cameras.clear();refresh();});
  beamSelect.addEventListener('change',()=>{selected.beam_index=Number(beamSelect.value);refresh();});
  function dispose(){if(disposed)return;disposed=true;revision++;endDrag();resize.disconnect();removal.disconnect();if(dialog)dialog.close();}
  const removal=new MutationObserver(()=>{if(!root.isConnected)dispose();});removal.observe(root.parentElement,{childList:true});
  await refresh();return {dispose};
}
