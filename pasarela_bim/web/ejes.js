/* Axes reference the topology; they never duplicate its coordinates. */
"use strict";
(function(root){
  const copy=v=>JSON.parse(JSON.stringify(v)), EPS=.001, NS="http://www.w3.org/2000/svg";
  const dimensionStyle=root.DimensionStyle||(typeof module!=="undefined"?require("./cotas.js"):null);
  const uid=()=>root.ProjectIO?.uid?.()||root.crypto?.randomUUID?.()||`axis-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const structural=n=>["columna","estribo"].includes(n.tipo);
  const category=e=>e.funcion==="cruce"?"atravieso":"recorrido";
  const maps=m=>({nodes:new Map((m.nodos||[]).map(n=>[n.id,n])),edges:new Map((m.tramos||[]).map(e=>[e.id,e]))});
  const allEntities=m=>[...(m.nodos||[]),...(m.tramos||[]),...(m.soportes||[]),...(m.fundaciones||[]),...(m.ejes||[]),...(m.fundaciones||[]).flatMap(f=>f.pilotes||[])];
  function nextId(m,prefix){const used=new Set(allEntities(m).map(v=>v.id));let n=1;while(used.has(prefix+n))n++;return prefix+n;}
  function walk(m,axis){
    const {nodes,edges}=maps(m);
    if(axis.tipo==="apoyo"){if(Object.hasOwn(axis,"tramos"))throw new Error(`${axis.id}: un eje de apoyo sólo refiere su nodo, no tramos.`);const n=nodes.get(axis.nodo);if(!n||!structural(n))throw new Error(`${axis.id}: su eje debe pertenecer a una cepa o estribo.`);return {nodes:[n],edges:[],stations:[0],length:0};}
    if(!["atravieso","recorrido"].includes(axis.tipo))throw new Error(`${axis.id}: tipo de eje desconocido.`);
    if(Object.hasOwn(axis,"nodo"))throw new Error(`${axis.id}: un eje longitudinal sólo refiere sus tramos, no un nodo.`);
    const ids=axis.tramos;if(!Array.isArray(ids)||!ids.length||new Set(ids).size!==ids.length)throw new Error(`${axis.id}: selecciona tramos distintos en orden de recorrido.`);
    const chain=ids.map(id=>{const e=edges.get(id);if(!e||!nodes.has(e.desde)||!nodes.has(e.hasta))throw new Error(`${axis.id}: falta el tramo ${id} o alguno de sus nodos.`);if(e.funcion&&category(e)!==axis.tipo)throw new Error(`${axis.id}: ${id} no corresponde al tipo ${axis.tipo}.`);return e;});
    function orient(start){const result=[nodes.get(start)],seen=new Set([start]);for(const e of chain){const current=result.at(-1).id,next=e.desde===current?e.hasta:e.hasta===current?e.desde:null;if(!next||seen.has(next))return null;result.push(nodes.get(next));seen.add(next);}return result;}
    const ordered=orient(chain[0].desde)||orient(chain[0].hasta);if(!ordered)throw new Error(`${axis.id}: ordena una cadena continua sin bifurcaciones ni circuitos.`);
    const stations=[0];for(let i=1;i<ordered.length;i++){const a=ordered[i-1],b=ordered[i],L=Math.hypot(b.x-a.x,b.y-a.y);if(L<=EPS)throw new Error(`${axis.id}: dos estaciones coinciden en planta.`);stations.push(stations.at(-1)+L);}
    if(axis.tipo==="atravieso"){
      const a=ordered[0],b=ordered.at(-1),dx=b.x-a.x,dy=b.y-a.y,L=Math.hypot(dx,dy);let previous=-Infinity;
      for(const n of ordered){const s=((n.x-a.x)*dx+(n.y-a.y)*dy)/L;if(!L||Math.abs((n.x-a.x)*dy-(n.y-a.y)*dx)/L>EPS||s<=previous+EPS)throw new Error(`${axis.id}: el eje del atravieso debe permanecer recto y sin retrocesos.`);previous=s;}
    }
    // Interior columns are structural references. They do not split the
    // pedestrian chain or its physical return into artificial spans.
    const additionalNodes=[];
    for(const node of nodes.values())if(Object.hasOwn(node,"anclaje_tramo")){
      const anchor=node.anclaje_tramo;if(!anchor||typeof anchor!=="object"||Array.isArray(anchor)||typeof anchor.tramo!=="string"||!Number.isFinite(anchor.t)||!(anchor.t>0&&anchor.t<1))throw new Error(`${node.id}: anclaje interior inválido.`);
      const edge=edges.get(anchor.tramo);if(!edge||!(edge.tipo==="retorno"||edge.funcion==="retorno"))throw new Error(`${node.id}: el anclaje debe referir un retorno existente.`);
      if(node.tipo!=="columna"||(m.tramos||[]).some(e=>e.desde===node.id||e.hasta===node.id))throw new Error(`${node.id}: el apoyo interior debe ser columna y no puede ser un extremo peatonal.`);
      const edgeIndex=chain.findIndex(e=>e.id===anchor.tramo);if(edgeIndex<0)continue;
      const a=nodes.get(edge.desde),b=nodes.get(edge.hasta),t=anchor.t,f=interpolate(edge.rasante||[{t:0,f:0},{t:1,f:1}],t,"f");
      if(![a?.x,a?.y,a?.z,b?.x,b?.y,b?.z,node.x,node.y,node.z,f].every(Number.isFinite)||["x","y","z"].some(k=>Math.abs(node[k]-(a[k]+(b[k]-a[k])*(k==="z"?f:t)))>EPS))throw new Error(`${node.id}: sus coordenadas no coinciden con su anclaje al retorno.`);
      const fraction=ordered[edgeIndex].id===edge.desde?t:1-t;
      additionalNodes.push({node,station:stations[edgeIndex]+fraction*(stations[edgeIndex+1]-stations[edgeIndex]),edgeIndex,t});
    }
    additionalNodes.sort((a,b)=>a.station-b.station);
    return {nodes:ordered,edges:chain,stations,length:stations.at(-1),additionalNodes};
  }
  function create(m,params){
    const axis={...copy(params),id:params.id||nextId(m,params.tipo==="apoyo"?"EC":params.tipo==="atravieso"?"EA":"ER"),uuid:params.uuid||uid()};axis.nombre ||= axis.id;
    if(![axis.id,axis.nombre,axis.uuid].every(v=>typeof v==="string"&&v.trim()))throw new Error("El eje necesita identificador, nombre e identidad válidos.");
    if(Object.hasOwn(axis,"principal")&&typeof axis.principal!=="boolean")throw new Error("La condición de eje principal debe ser booleana.");
    if(allEntities(m).some(v=>v.id===axis.id))throw new Error(`El identificador ${axis.id} ya existe.`);
    if((m.ejes||[]).some(a=>a.uuid===axis.uuid))throw new Error("La identidad UUID del eje ya existe.");
    walk(m,axis);
    for(const other of m.ejes||[]){if(axis.tipo==="apoyo"&&other.tipo==="apoyo"&&axis.nodo===other.nodo)throw new Error(`${axis.nodo} ya tiene su eje ${other.id}.`);if(axis.tipo!=="apoyo"&&other.tipo!=="apoyo"&&(axis.tramos||[]).some(id=>(other.tramos||[]).includes(id)))throw new Error("Cada tramo pertenece a un único eje longitudinal.");if(axis.principal&&other.principal)throw new Error("Ya existe un atravieso principal.");}
    if(axis.principal&&axis.tipo!=="atravieso")throw new Error("Sólo el atravieso puede definir el origen principal.");
    (m.ejes ||= []).push(axis);return axis;
  }
  function syncSupports(m){
    const valid=new Set((m.nodos||[]).filter(structural).map(n=>n.id));m.ejes=(m.ejes||[]).filter(a=>a.tipo!=="apoyo"||valid.has(a.nodo));
    for(const n of (m.nodos||[]).filter(structural))if(!m.ejes.some(a=>a.tipo==="apoyo"&&a.nodo===n.id))create(m,{tipo:"apoyo",nodo:n.id,nombre:`${n.tipo==="estribo"?"Estribo":"Cepa"} ${n.id}`});return m.ejes;
  }
  function suggest(model){
    const m=copy(model);m.ejes ||= [];const {edges}=maps(m),covered=new Set(m.ejes.flatMap(a=>a.tramos||[]));
    // Preserve existing axes and extend only through unambiguous free endpoints.
    for(const axis of m.ejes.filter(a=>a.tipo!=="apoyo")){
      let progress=true;while(progress){progress=false;let path;try{path=walk(m,axis);}catch(_){break;}
        for(const [atStart,node] of [[true,path.nodes[0]],[false,path.nodes.at(-1)]]){
          const incident=(m.tramos||[]).filter(e=>category(e)===axis.tipo&&(e.desde===node.id||e.hasta===node.id));
          const fresh=incident.filter(e=>!covered.has(e.id));if(incident.length!==2||fresh.length!==1)continue;
          const trial={...axis,tramos:atStart?[fresh[0].id,...axis.tramos]:[...axis.tramos,fresh[0].id]};
          try{walk(m,trial);axis.tramos=trial.tramos;covered.add(fresh[0].id);progress=true;break;}catch(_){}
        }
      }
    }
    for(const type of ["atravieso","recorrido"]){
      const pending=new Set((m.tramos||[]).filter(e=>category(e)===type&&!covered.has(e.id)).map(e=>e.id));
      const adjacent=id=>(m.tramos||[]).filter(e=>category(e)===type&&(e.desde===id||e.hasta===id));
      while(pending.size){const first=[...pending].map(id=>edges.get(id)).find(e=>adjacent(e.desde).length!==2||adjacent(e.hasta).length!==2)||edges.get(pending.values().next().value);
        let current=adjacent(first.desde).length!==2?first.desde:adjacent(first.hasta).length!==2?first.hasta:first.desde,edge=first;const list=[],seen=new Set([current]);
        while(edge){const next=edge.desde===current?edge.hasta:edge.desde;if(seen.has(next))break;
          const trial={id:"propuesta",tipo:type,tramos:[...list,edge.id]};try{walk(m,trial);}catch(_){if(list.length)break;throw _;}
          list.push(edge.id);pending.delete(edge.id);covered.add(edge.id);seen.add(next);current=next;
          const incident=adjacent(current);edge=incident.length===2?incident.find(e=>pending.has(e.id)):null;
        }
        // A closing edge becomes its own axis, rather than a circular station chain.
        if(!list.length){list.push(first.id);pending.delete(first.id);covered.add(first.id);}
        create(m,{tipo:type,tramos:list,nombre:type==="atravieso"?"Atravieso":"Recorrido peatonal",...(type==="atravieso"&&!m.ejes.some(a=>a.tipo==="atravieso")?{principal:true}:{})});
      }
    }
    syncSupports(m);return m.ejes;
  }
  function reconcile(m){
    const {edges}=maps(m),kept=[];
    for(const axis of m.ejes||[]){if(axis.tipo==="apoyo"){kept.push(axis);continue;}const ids=(axis.tramos||[]).filter(id=>edges.has(id)&&(!edges.get(id).funcion||category(edges.get(id))===axis.tipo));let fragment=[],fragments=[];
      for(const id of ids){try{walk(m,{...axis,tramos:[...fragment,id]});fragment.push(id);}catch(_){if(fragment.length)fragments.push(fragment);fragment=[id];}}if(fragment.length)fragments.push(fragment);
      fragments.forEach((tramos,index)=>kept.push(index?{...axis,id:nextId({...m,ejes:[...(m.ejes||[]),...kept]},axis.tipo==="atravieso"?"EA":"ER"),uuid:uid(),nombre:`${axis.nombre||axis.id} · continuación`,principal:false,tramos}:{...axis,tramos}));
    }
    m.ejes=kept;syncSupports(m);m.ejes=suggest(m);return m.ejes;
  }
  function renameReferences(m,type,oldId,newId){for(const a of m.ejes||[]){if(type==="node"&&a.nodo===oldId)a.nodo=newId;if(type==="edge"&&Array.isArray(a.tramos))a.tramos=a.tramos.map(id=>id===oldId?newId:id);}}
  function component(m,initial){const ids=new Set(initial),queue=[...initial];while(queue.length){const id=queue.shift();for(const e of m.tramos||[]){const next=e.desde===id?e.hasta:e.hasta===id?e.desde:null;if(next&&!ids.has(next)){ids.add(next);queue.push(next);}}}return ids;}
  function foundationPosition(m,f){const ns=(f.nodos||[]).map(id=>(m.nodos||[]).find(n=>n.id===id)).filter(Boolean);if(!ns.length)return null;const centre={x:ns.reduce((s,n)=>s+n.x,0)/ns.length,y:ns.reduce((s,n)=>s+n.y,0)/ns.length};return {...centre,angle:Number.isFinite(f.angulo_deg)?f.angulo_deg*Math.PI/180:ns.length>1?Math.atan2(ns.at(-1).y-ns[0].y,ns.at(-1).x-ns[0].x):0};}
  function movePreview(model,axisId,delta,{connected=false}={}){
    if(!Number.isFinite(delta.x)||!Number.isFinite(delta.y))throw new Error("Introduce desplazamientos X e Y finitos.");
    const axis=(model.ejes||[]).find(a=>a.id===axisId);if(!axis)throw new Error("Selecciona un eje existente.");
    const path=walk(model,axis),initial=path.nodes.flatMap(n=>{const edge=n.anclaje_tramo&&(model.tramos||[]).find(e=>e.id===n.anclaje_tramo.tramo);return edge?[edge.desde,edge.hasta]:[n.id];}),ids=connected?component(model,initial):new Set(initial),changed=Math.hypot(delta.x,delta.y)>EPS;
    const candidate=copy(model),warnings=[],nodos=[];
    for(const n of candidate.nodos)if(ids.has(n.id)&&changed){if(n.xy_fijo||n.posicion_fija)throw new Error(`${n.id}: su posición fija impide mover este eje.`);const before={x:n.x,y:n.y,z:n.z};n.x+=delta.x;n.y+=delta.y;nodos.push({id:n.id,before,after:{x:n.x,y:n.y,z:n.z},dz:0});}
    if(changed&&candidate.nodos.some(n=>n.anclaje_tramo)){
      const returns=root.ReturnSupports||(typeof module!=="undefined"?require("./retornos.js"):null);
      if(!returns?.sync)throw new Error("El actualizador de apoyos de retornos no está disponible.");
      for(const movement of returns.sync(candidate)){
        const source=model.nodos.find(n=>n.id===movement.id);if(source?.xy_fijo||source?.posicion_fija)throw new Error(`${movement.id}: su posición fija impide mover el retorno vinculado.`);
        ids.add(movement.id);nodos.push(movement);
      }
    }
    const affected=new Set((candidate.tramos||[]).filter(e=>ids.has(e.desde)||ids.has(e.hasta)).map(e=>e.id));
    if(root.PasarelaEditing?.checkSlopeRules)root.PasarelaEditing.checkSlopeRules(candidate,affected);
    else if(changed)throw new Error("El comprobador de pendientes no está disponible.");
    const axes=(candidate.ejes||[]).filter(a=>a.tipo==="apoyo"?ids.has(a.nodo):(a.tramos||[]).some(id=>affected.has(id)));
    for(const a of axes)walk(candidate,a);
    const foundations=[];
    for(const f of candidate.fundaciones||[])if(changed&&(f.nodos||[]).some(id=>ids.has(id))){
      const before=foundationPosition(model,f),after=foundationPosition(candidate,f);foundations.push({id:f.id,before,after});
      if(!f.nodos.every(id=>ids.has(id))){warnings.push(`${f.id}: la fundación compartida cambia su centro y puede cambiar su orientación; revisa su planta.`);
        for(const id of f.nodos){const n=candidate.nodos.find(n=>n.id===id),support=candidate.soportes?.find(s=>s.nodo===id);if(!n||!after)continue;const dx=n.x-after.x,dy=n.y-after.y,c=Math.cos(after.angle),s=Math.sin(after.angle),x=dx*c+dy*s,y=-dx*s+dy*c,halfX=(support?.diametro_mm||support?.largo_mm||0)/2,halfY=(support?.diametro_mm||support?.ancho_mm||0)/2;
          if((f.largo_mm&&Math.abs(x)+halfX>f.largo_mm/2+EPS)||(f.ancho_mm&&Math.abs(y)+halfY>f.ancho_mm/2+EPS))throw new Error(`${f.id}: el movimiento deja ${id} fuera de la fundación compartida. Traslada el conjunto conectado o modifica primero la fundación.`);
        }
      }
    }
    let origin=null;const primary=candidate.ejes?.find(a=>a.tipo==="atravieso"&&a.principal)||candidate.ejes?.find(a=>a.tipo==="atravieso");
    const georef=candidate.proyecto?.georreferencia||candidate.georreferencia;
    if(changed&&primary&&georef&&root.ProjectIO){const pp=walk(candidate,primary),first=pp.nodes[0],last=pp.nodes.at(-1),x=(first.x+last.x)/2,y=(first.y+last.y)/2;
      if(candidate.proyecto?.georreferencia&&candidate.georreferencia){const a=candidate.proyecto.georreferencia,b=candidate.georreferencia;if(new Set([...Object.keys(a),...Object.keys(b)]).size!==Object.keys(a).length||Object.keys(a).some(k=>a[k]!==b[k]))throw new Error("Las dos georreferencias del archivo difieren. Define un único origen antes de mover el eje.");}
      if(Math.hypot(x,y)>EPS){const old=copy(georef),world=root.ProjectIO.localToWorld(candidate,x/1000,y/1000,0);georef.este_m=world[0];georef.norte_m=world[1];if(candidate.proyecto?.georreferencia&&candidate.georreferencia)candidate.georreferencia=copy(georef);for(const n of candidate.nodos){n.x-=x;n.y-=y;}origin={before:old,after:copy(georef),desplazamiento_local_mm:{x,y}};warnings.push("El origen local vuelve al punto medio del atravieso. Se actualizan Este/Norte y todas las coordenadas locales; los elementos fuera del alcance conservan su posición geográfica.");}
    }
    return {nodos,soportes:[],fundaciones:[],omitidos:[],ejes_afectados:axes.map(a=>a.id),advertencias:warnings,soportes_en_planta:(model.soportes||[]).filter(s=>ids.has(s.nodo)&&changed).map(s=>s.id),fundaciones_en_planta:foundations,origen:origin,modelo_resultante:candidate,marco_vista_previa:"Coordenadas respecto del origen anterior; la aplicación recentra después el origen si corresponde."};
  }
  function applyMove(m,plan){if(!plan?.modelo_resultante)throw new Error("No existe una vista previa válida.");for(const k of Object.keys(m))delete m[k];Object.assign(m,copy(plan.modelo_resultante));}
  function svg(name,attrs={},text){const e=root.document.createElementNS(NS,name);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;}
  function renderPlan(m,project,selected){const group=svg("g",{class:"axis-layer"});for(const axis of m.ejes||[]){let path;try{path=walk(m,axis);}catch(_){continue;}const active=axis.id===selected,color=active?"#d56e21":"#936345",g=svg("g",{"data-select-type":"axis","data-select-id":axis.id,class:"selectable axis-reference",role:"button",tabindex:0,"aria-label":`Eje ${axis.id}`}),pts=path.nodes.map(n=>project(n.x,n.y,n.z));
      if(axis.tipo!=="apoyo")g.append(svg("polyline",{points:pts.map(p=>p.join(",")).join(" "),fill:"none",stroke:color,"stroke-width":active?2.2:1.2,"stroke-dasharray":"12 3 2 3","vector-effect":"non-scaling-stroke","pointer-events":"none"}));
      const p=pts[0];let anchor=p,offset=[-22,-29];
      if(axis.tipo!=="apoyo"){const middle=path.length/2,index=Math.max(0,path.stations.findIndex(s=>s>=middle)-1),fraction=(middle-path.stations[index])/(path.stations[index+1]-path.stations[index]),a=pts[index],b=pts[index+1],dx=b[0]-a[0],dy=b[1]-a[1],L=Math.hypot(dx,dy)||1;anchor=[a[0]+fraction*dx,a[1]+fraction*dy];offset=[-dy/L*30,dx/L*30];if(offset[0]<-.01||(Math.abs(offset[0])<.01&&offset[1]<0))offset=offset.map(v=>-v);}
      const label=[anchor[0]+offset[0],anchor[1]+offset[1]],width=Math.max(34,axis.id.length*6+12);
      g.append(svg("line",{x1:anchor[0],y1:anchor[1],x2:label[0],y2:label[1],stroke:color,"stroke-dasharray":"3 2","pointer-events":"none"}));g.append(svg("rect",{x:label[0]-width/2,y:label[1]-9,width,height:18,rx:9,fill:active?"#fff0df":"#fffaf4",stroke:color,"stroke-width":1}));g.append(svg("text",{x:label[0],y:label[1]+3,"text-anchor":"middle","font-size":9,fill:color},axis.id));g.append(svg("title",{},`${axis.nombre||axis.id} · ${axis.tipo}`));group.append(g);
    }return group;}
  function interpolate(profile,t,key){for(let i=1;i<profile.length;i++)if(t<=profile[i].t){const a=profile[i-1],b=profile[i];return a[key]+(b[key]-a[key])*(t-a.t)/(b.t-a.t);}return profile.at(-1)[key];}
  function elevation(m,axisId,{dimensions=true,selected=null}={}){
    const axis=(m.ejes||[]).find(a=>a.id===axisId);
    if(!axis||axis.tipo==="apoyo")throw new Error("Selecciona un eje del atravieso o de un recorrido.");
    const path=walk(m,axis),scale=14/1000,group=svg("g",{class:"axis-elevation"}),bounds=[],geometry=[],dimensionSpecs=[],reservedLabels=[];
    const stationNodes=[...path.nodes.map((node,i)=>({node,station:path.stations[i],edgeIndex:Math.min(i,path.edges.length-1),chainIndex:i})),...path.additionalNodes].sort((a,b)=>a.station-b.station);
    const xy=(s,z)=>{const p=[s*scale,-z*scale];if(p.every(Number.isFinite)){bounds.push(p);geometry.push(p);}return p;};
    const line=(a,b,attrs={},target=group)=>{bounds.push(a,b);target.append(svg("line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:"#8b9aa4",...attrs}));};
    const textBounds=(x,y,text,attrs={})=>{const size=attrs["font-size"]||9,width=String(text).length*size*.55,start=attrs["text-anchor"]==="middle"?x-width/2:attrs["text-anchor"]==="end"?x-width:x;return [start,y-size,start+width,y+3];};
    const label=(x,y,text,attrs={},target=group)=>{const r=textBounds(x,y,text,attrs);bounds.push([r[0],r[1]],[r[2],r[3]]);if(target===group)reservedLabels.push(r);target.append(svg("text",{x,y,"font-size":9,fill:"#334d60",...attrs},text));};
    const selectable=(type,id,name,kind,pileId=null)=>{const active=selected?.type===type&&selected.id===id&&(type!=="foundation"||((selected.pileId||null)===pileId));return svg("g",{class:`selectable elevation-selectable ${kind}${active?" selected":""}`,"data-select-type":type,"data-select-id":id,...(pileId?{"data-select-pile-id":pileId}:{}),role:"button",tabindex:0,"aria-label":name,"aria-pressed":active?"true":"false"});};
    const hitLabel=(target,x,y,text,attrs={})=>{const r=textBounds(x,y,text,attrs);target.append(svg("rect",{class:"elevation-hit-area",x:r[0]-4,y:r[1]-3,width:r[2]-r[0]+8,height:r[3]-r[1]+6,fill:"transparent","pointer-events":"all"}));reservedLabels.push(r);label(x,y,text,attrs,target);};
    const metres=mm=>`${new Intl.NumberFormat("es-CL",{minimumFractionDigits:3,maximumFractionDigits:3,useGrouping:false}).format(Math.abs(mm)<.0005?0:mm/1000)} m`;
    const hatchId='axis-concrete-cut',defs=svg('defs'),pattern=svg('pattern',{id:hatchId,width:7,height:7,patternUnits:'userSpaceOnUse'});
    pattern.append(svg('rect',{width:7,height:7,fill:'#e5edf1'}),svg('path',{d:'M-2,2 L2,-2 M0,7 L7,0 M5,9 L9,5',stroke:'#9aafb9','stroke-width':.55}));defs.append(pattern);group.append(defs);
    const cutRect=(station,left,right,bottom,upper,kind,selection)=>{if(![station,left,right,bottom,upper].every(Number.isFinite)||!(right>left&&upper>bottom))return false;const ps=[[station+left,bottom],[station+right,bottom],[station+right,upper],[station+left,upper]].map(([s,z])=>xy(s,z)),points=ps.map(p=>p.join(',')).join(' '),target=selectable(...selection);target.append(svg('polygon',{class:'elevation-hit-area',points,fill:'transparent',stroke:'transparent','stroke-width':8,'pointer-events':'all'}),svg('polygon',{class:kind,points,fill:`url(#${hatchId})`,stroke:'#486a7a','stroke-width':1}));group.append(target);return true;};
    const terrain=stationNodes.flatMap(({node,station})=>(m.soportes||[]).filter(s=>s.nodo===node.id&&Number.isFinite(s.cota_terreno_proyectado_mm)).map(s=>({node,support:s,station,z:s.cota_terreno_proyectado_mm})));
    stationNodes.forEach(({node,station})=>xy(station,node.z));terrain.forEach(t=>xy(t.station,t.z));
    for(let i=0;i<path.edges.length;i++){
      const e=path.edges[i],a=m.nodos.find(n=>n.id===e.desde),b=m.nodos.find(n=>n.id===e.hasta),L=path.stations[i+1]-path.stations[i],forward=path.nodes[i].id===e.desde,p=e.rasante||[{t:0,f:0},{t:1,f:1}],family=root.VolumePreview?.sectionFamily(m,e)||m.familias?.[e.familia]||{},depth=family.perfil_canto||[{t:0,canto_mm:family.canto_mm||250},{t:1,canto_mm:family.canto_fin_mm||family.canto_mm||250}],lo=(e.retranqueo_inicio_mm||0)/L,hi=1-(e.retranqueo_fin_mm||0)/L;
      if(lo>=hi)continue;
      const station=t=>path.stations[i]+L*(forward?t:1-t),z=t=>a.z+(b.z-a.z)*interpolate(p,t,"f"),h=t=>interpolate(depth,t,"canto_mm");
      const ts=[...new Set([lo,hi,...p.map(v=>v.t),...depth.map(v=>v.t)])].filter(t=>t>=lo&&t<=hi).sort((x,y)=>x-y),upper=ts.map(t=>xy(station(t),z(t))),lower=ts.map(t=>xy(station(t),z(t)-h(t)));
      const cut=root.VolumePreview?.longitudinalSection(m,e);
      const element=selectable("edge",e.id,`Editar ${family.tipo==="escalera"?"escalera":"tramo"} ${e.id}`,"elevation-edge");
      if(cut){const contour=pts=>pts.map(([s,z],index)=>{const pt=xy(path.stations[i]+(forward?s:L-s),z);return `${index?'L':'M'}${pt[0]},${pt[1]}`;}).join(' ')+' Z',outer=contour(cut.outer);const shape=svg('path',{class:'beam-longitudinal-cut','data-cut-edge':e.id,d:outer+(cut.inner.length?' '+contour(cut.inner):''),'fill-rule':'evenodd',fill:`url(#${hatchId})`,stroke:'#377a9b','stroke-width':1.2});shape.append(svg('title',{},`Corte central de ${e.id}${cut.inner.length?': hueco interior y macizados de extremos':''}`));element.append(svg('path',{class:'elevation-hit-area',d:outer,fill:'transparent',stroke:'transparent','stroke-width':8,'pointer-events':'all'}),shape);}
      else{const points=[...upper,...lower.slice().reverse()].map(p=>p.join(",")).join(" ");element.append(svg("polygon",{class:"elevation-hit-area",points,fill:"transparent",stroke:"transparent","stroke-width":8,"pointer-events":"all"}),svg("polygon",{class:"beam-longitudinal-cut","data-cut-edge":e.id,points,fill:"#dbe8ef",stroke:"#377a9b","stroke-width":1.2}));}
      const mid=(path.stations[i]+path.stations[i+1])/2*scale;hitLabel(element,mid,Math.min(...upper.map(p=>p[1]))-10,e.id,{"text-anchor":"middle"});group.append(element);
      // Measure the actual trimmed ends using the same depth profile as the cut.
      if(family.tipo!=="escalera"&&Number.isFinite(family.canto_mm)&&family.canto_mm>0){
        const ends=Math.abs(h(lo)-h(hi))>EPS?[lo,hi]:[forward?lo:hi];
        for(const t of ends)dimensionSpecs.push({type:"vertical",kind:"beam-height",id:e.id,value:h(t),s:station(t),z0:z(t)-h(t),z1:z(t),side:station(t)<(path.stations[i]+path.stations[i+1])/2?-1:1,offset:20,prefix:"H ",title:`${e.id}: alto de viga en el extremo real ${t===lo?'inicial':'final'}, después del retranqueo.`});
      }
      for(let j=1;j<p.length;j++)if(p[j].t>p[j-1].t&&Math.abs(p[j].f-p[j-1].f)<1e-10&&p[j].f>0&&p[j].f<1){
        const t0=Math.max(lo,p[j-1].t),t1=Math.min(hi,p[j].t);if(t1<=t0)continue;
        dimensionSpecs.push({type:"horizontal",kind:"landing",id:e.id,value:(t1-t0)*L,s0:station(t0),s1:station(t1),z:z(t0),y:Math.min(...upper.map(p=>p[1]))-30,title:`${e.id}: longitud horizontal del descanso integrado, sin aumentar el largo de la viga.`});
      }
    }
    // Longitudinal section of the same conceptual caps used in the 3D preview.
    if(root.VolumePreview?.capitals)for(let i=0;i<path.nodes.length;i++){
      const n=path.nodes[i],support=m.soportes?.find(s=>s.nodo===n.id);if(!support)continue;
      for(const part of root.VolumePreview.capitals(m,support)){
        const edgeIndex=path.edges.findIndex(e=>e.id===part.edgeId);if(edgeIndex<0)continue;
        const direction=edgeIndex===i?1:-1,stations=part.stations.map(s=>path.stations[i]+direction*s);
        const polygon=svg("polygon",{class:"capital-elevation","data-capital-node":n.id,points:[xy(stations[0],part.base),xy(stations[1],part.base),xy(stations[1],part.tops[1]),xy(stations[0],part.tops[0])].map(p=>p.join(',')).join(' '),fill:"#dbc39b",stroke:"#9a7d52","stroke-width":1,"vector-effect":"non-scaling-stroke"});
        const element=selectable("node",n.id,`Editar cabezal del apoyo ${n.id}`,"elevation-capital");polygon.append(svg("title",{},`Cabezal conceptual de ${n.id}: unión aproximada entre columna e intradós de ${part.edgeId}`));element.append(polygon);group.append(element);
      }
    }
    const drawnFoundations=new Set(),drawnPiles=new Set();
    for(const entry of stationNodes){
      const n=entry.node,support=m.soportes?.find(s=>s.nodo===n.id),foundation=m.fundaciones?.find(f=>f.id===support?.fundacion);if(!support||!foundation)continue;
      const start=path.nodes[entry.edgeIndex],end=path.nodes[entry.edgeIndex+1],length=Math.hypot(end.x-start.x,end.y-start.y),ux=(end.x-start.x)/length,uy=(end.y-start.y)/length;
      const angle=foundationPosition(m,foundation)?.angle??0,c=Math.cos(angle),s=Math.sin(angle);
      // Exact intersection of the vertical axis plane with a rotated rectangle.
      const rectangle=(cx,cy,L,W)=>{if(![cx,cy,L,W].every(Number.isFinite)||L<=0||W<=0)return null;const ox=(n.x-cx)*c+(n.y-cy)*s,oy=-(n.x-cx)*s+(n.y-cy)*c,dx=ux*c+uy*s,dy=-ux*s+uy*c;let lo=-Infinity,hi=Infinity;for(const [o,d,half] of [[ox,dx,L/2],[oy,dy,W/2]]){if(Math.abs(d)<1e-10){if(Math.abs(o)>half)return null;}else{const a=(-half-o)/d,b=(half-o)/d;lo=Math.max(lo,Math.min(a,b));hi=Math.min(hi,Math.max(a,b));}}return hi>lo?[lo,hi]:null;};
      const station=entry.station,column=support.diametro_mm>0?[-support.diametro_mm/2,support.diametro_mm/2]:rectangle(n.x,n.y,support.largo_mm,support.ancho_mm);
      if(column&&cutRect(station,...column,foundation.cota_superior_mm,support.cota_superior_mm,'support-longitudinal-cut',["node",n.id,`Editar ${n.tipo==="estribo"?"estribo":"columna"} ${n.id}`,"elevation-support"]))dimensionSpecs.push({type:"vertical",kind:"support-height",id:support.id,value:support.cota_superior_mm-foundation.cota_superior_mm,s:station+column[1],z0:foundation.cota_superior_mm,z1:support.cota_superior_mm,side:1,offset:17,title:`${support.id}: altura del apoyo desde el tope de su fundación hasta el tope de la columna o estribo; excluye el cabezal.`});
      const ns=(foundation.nodos||[]).map(id=>m.nodos.find(n=>n.id===id)).filter(Boolean);if(!ns.length)continue;
      const cx=ns.reduce((sum,n)=>sum+n.x,0)/ns.length,cy=ns.reduce((sum,n)=>sum+n.y,0)/ns.length,foot=rectangle(cx,cy,foundation.largo_mm,foundation.ancho_mm),bottom=foundation.cota_superior_mm-foundation.alto_mm;
      const footprint=foot&&`${foundation.id}:${(station+foot[0]).toFixed(3)}:${(station+foot[1]).toFixed(3)}`;
      if(foot&&!drawnFoundations.has(footprint)&&cutRect(station,...foot,bottom,foundation.cota_superior_mm,'foundation-longitudinal-cut',["foundation",foundation.id,`Editar ${foundation.pilotes?.length?"dado":"fundación"} ${foundation.id}`,"elevation-foundation"])){drawnFoundations.add(footprint);dimensionSpecs.push({type:"vertical",kind:"foundation-thickness",id:foundation.id,value:foundation.alto_mm,s:station+foot[1],z0:bottom,z1:foundation.cota_superior_mm,side:1,offset:17,title:`${foundation.id}: espesor de la fundación intersectada por este corte.`});}
      for(const pile of foundation.pilotes||[]){const px=cx+pile.dx_mm*c-pile.dy_mm*s,py=cy+pile.dx_mm*s+pile.dy_mm*c,along=(px-n.x)*ux+(py-n.y)*uy,offset=-(px-n.x)*uy+(py-n.y)*ux,r=pile.diametro_mm/2;if(![along,offset,r].every(Number.isFinite)||r<=0||Math.abs(offset)>=r)continue;const half=Math.sqrt(r*r-offset*offset),key=`${foundation.id}:${pile.id}:${(station+along).toFixed(3)}`;
        if(!drawnPiles.has(key)&&cutRect(station,along-half,along+half,bottom-pile.longitud_mm,bottom,'pile-longitudinal-cut',["foundation",foundation.id,`Editar pilote ${pile.id} del dado ${foundation.id}`,"elevation-pile",pile.id])){drawnPiles.add(key);dimensionSpecs.push({type:"vertical",kind:"pile-length",id:pile.id,value:pile.longitud_mm,s:station+along+half,z0:bottom-pile.longitud_mm,z1:bottom,side:1,offset:17,title:`${pile.id}: longitud del pilote que intersecta el corte, desde la cara inferior del dado.`});}
      }
    }
    // Only visible geometry determines the frame: unrelated foundations cannot push it away.
    const base=Math.max(0,...geometry.map(p=>p[1]))+30,top=Math.min(...geometry.map(p=>p[1]))-25;
    // Keep dimension text clear of IDs, support-axis bubbles and point terrain labels.
    for(const {node:n,station} of stationNodes){
      const x=station*scale;reservedLabels.push(textBounds(x,base+15,n.id,{"text-anchor":"middle"}));
      if(m.ejes?.some(a=>a.tipo==="apoyo"&&a.nodo===n.id))reservedLabels.push([x-13,top-23,x+13,top+3]);
    }
    for(const t of terrain)reservedLabels.push(textBounds(t.station*scale,-t.z*scale-8,`Terreno proyectado ${(t.z/1000).toFixed(3)} m`,{"font-size":8,"text-anchor":"middle"}));
    const dimensionLayer=svg("g",{class:"elevation-dimensions","pointer-events":"none"}),occupied=reservedLabels.slice();
    const dimensionGroup=(kind,id,value,title)=>{const g=svg("g",{class:"elevation-dimension","data-dimension-kind":kind,"data-element-id":id,"data-value-mm":value});g.append(svg("title",{},title));dimensionLayer.append(g);return g;};
    const dimLabel=(g,x,y,text,anchor="middle")=>{const attrs={"text-anchor":anchor,"font-size":10,fill:"#496878",stroke:"#f8fbfd","stroke-width":3,"stroke-linejoin":"round","paint-order":"stroke"},originalX=x,originalY=y;
      const intersects=box=>occupied.some(r=>box[0]<r[2]+3&&box[2]>r[0]-3&&box[1]<r[3]+2&&box[3]>r[1]-2);
      let box=textBounds(x,y,text,attrs),steps=0;
      // Heights can move outward before moving up, keeping their labels near the measured interval.
      if(intersects(box)&&anchor!=="middle")for(let step=1;step<=8;step++){const nextX=originalX+(anchor==="end"?-1:1)*step*16,next=textBounds(nextX,y,text,attrs);if(!intersects(next)){x=nextX;box=next;break;}}
      while(intersects(box)&&steps++<24){y-=16;box=textBounds(x,y,text,attrs);}
      if(x!==originalX||y!==originalY)line([originalX,originalY-4],[x,y-4],{stroke:"#91a5b1","stroke-width":.65,"vector-effect":"non-scaling-stroke",class:"dimension-label-leader"},g);
      occupied.push(box);label(x,y,text,attrs,g);
    };
    const dimLine=(g,a,b,extension=false)=>line(a,b,{stroke:extension?"#afbdc6":"#738c9b","stroke-width":extension?.65:.85,"vector-effect":"non-scaling-stroke"},g);
    const arrows=(g,a,b)=>dimensionStyle.appendArrows(svg,g,a,b,{textSize:10,color:'#738c9b',onPoint:p=>bounds.push(p)});
    const horizontal=(kind,id,value,x1,x2,y,ref1,ref2,title)=>{if(!(value>EPS)||![x1,x2,y,ref1,ref2].every(Number.isFinite))return;const g=dimensionGroup(kind,id,value,title);if(x1>x2)[x1,x2,ref1,ref2]=[x2,x1,ref2,ref1];
      dimLine(g,[x1,ref1],[x1,y+4],true);dimLine(g,[x2,ref2],[x2,y+4],true);dimLine(g,[x1,y],[x2,y]);arrows(g,[x1,y],[x2,y]);
      const text=metres(value),width=text.length*10*.55,small=x2-x1<width+12;
      if(small){const tx=x2+7;dimLine(g,[(x1+x2)/2,y],[tx+width/2,y-14],true);dimLabel(g,tx,y-17,text,"start");}else dimLabel(g,(x1+x2)/2,y-5,text);
    };
    if(dimensions){
      for(const d of dimensionSpecs){
        if(!Number.isFinite(d.value)||d.value<=EPS)continue;
        if(d.type==="horizontal"){horizontal(d.kind,d.id,d.value,d.s0*scale,d.s1*scale,d.y,-d.z*scale,-d.z*scale,d.title);continue;}
        if(![d.s,d.z0,d.z1].every(Number.isFinite))continue;
        const g=dimensionGroup(d.kind,d.id,d.value,d.title),ref=d.s*scale,x=ref+d.side*d.offset,y0=-d.z0*scale,y1=-d.z1*scale;
        g.setAttribute("data-station-mm",d.s);g.setAttribute("data-bottom-mm",d.z0);g.setAttribute("data-top-mm",d.z1);
        dimLine(g,[ref,y0],[x+d.side*4,y0],true);dimLine(g,[ref,y1],[x+d.side*4,y1],true);dimLine(g,[x,y0],[x,y1]);arrows(g,[x,y0],[x,y1]);
        const short=Math.abs(y1-y0)<18,labelY=short?Math.max(y0,y1)+13:(y0+y1)/2+3;
        if(short)dimLine(g,[x,(y0+y1)/2],[x+d.side*5,labelY-4],true);
        dimLabel(g,x+d.side*5,labelY,`${d.prefix||""}${metres(d.value)}`,d.side<0?"end":"start");
      }
      for(let i=0;i<path.edges.length;i++)horizontal("span",path.edges[i].id,path.stations[i+1]-path.stations[i],path.stations[i]*scale,path.stations[i+1]*scale,base,base-10,base-10,`${path.edges[i].id}: distancia horizontal en planta entre los ejes de sus nodos; no es la longitud real recortada de la viga.`);
      if(path.edges.length>1)horizontal("total",axis.id,path.length,0,path.length*scale,base+78,base+58,base+58,"Longitud horizontal desarrollada entre el primer y el último nodo del eje; suma de las distancias en planta de sus tramos.");
    }
    for(const {node:n,station:nodeStation} of stationNodes){
      const x=nodeStation*scale,supportAxis=m.ejes?.find(a=>a.tipo==="apoyo"&&a.nodo===n.id);
      if(supportAxis){const axisElement=selectable("axis",supportAxis.id,`Editar eje ${supportAxis.id}`,"elevation-axis");line([x,top],[x,base+3],{stroke:"#94613f","stroke-dasharray":"8 3 2 3","pointer-events":"none"});axisElement.append(svg("circle",{class:"elevation-axis-bubble",cx:x,cy:top-10,r:12,fill:"#fffaf3",stroke:"#94613f"}));bounds.push([x-12,top-22],[x+12,top+2]);hitLabel(axisElement,x,top-7,supportAxis.id,{"text-anchor":"middle","font-size":8});group.append(axisElement);}
      const nodeElement=selectable("node",n.id,`Editar nodo ${n.id}`,"elevation-node"),y=-n.z*scale;nodeElement.append(svg("circle",{class:"elevation-hit-area",cx:x,cy:y,r:7,fill:"transparent","pointer-events":"all"}),svg("circle",{class:"elevation-node-marker",cx:x,cy:y,r:2.8,fill:"#fff",stroke:"#377a9b","stroke-width":1.2}));hitLabel(nodeElement,x,base+15,n.id,{"text-anchor":"middle"});group.append(nodeElement);
      if(dimensions){
        const station=dimensionGroup("station",n.id,nodeStation,`${n.id}: abscisa acumulada en planta desde el inicio de este eje.`),level=dimensionGroup("level",n.id,n.z,`${n.id}: cota local respecto del origen del proyecto (Z = 0).`);
        dimLabel(station,x,base+31,`s ${metres(nodeStation)}`);dimLabel(level,x,base+49,`Z ${metres(n.z)}`);
      }
    }
    if(dimensions)group.append(dimensionLayer);
    // Each level belongs to the centre of its support, even on a shared footing.
    // A short point marker is a datum, never an inferred terrain profile.
    for(const t of terrain){const [x,y]=xy(t.station,t.z),text=`Terreno proyectado ${(t.z/1000).toFixed(3)} m`,width=text.length*8*.55,marker=svg('g',{class:'projected-terrain-level','data-support-id':t.support.id,'data-node-id':t.node.id,'data-z-mm':t.z}),element=selectable("node",t.node.id,`Editar terreno proyectado del apoyo ${t.node.id}`,"elevation-terrain");
      element.append(svg('rect',{class:'elevation-hit-area',x:x-Math.max(15,width/2+3),y:y-20,width:Math.max(30,width+6),height:26,fill:'transparent','pointer-events':'all'}),svg('line',{x1:x-11,y1:y,x2:x+11,y2:y,stroke:'#637847','stroke-width':1.2}),svg('circle',{cx:x,cy:y,r:2.5,fill:'#fff',stroke:'#637847','stroke-width':1.2}),svg('text',{x,y:y-8,'text-anchor':'middle','font-size':8,fill:'#52643e',stroke:'#f8fbfd','stroke-width':2,'stroke-linejoin':'round','paint-order':'stroke'},text),svg('title',{},`${t.support.id}: nivel proyectado en el centro del apoyo; no define una superficie de terreno.`));marker.append(element);group.append(marker);bounds.push([x-Math.max(11,width/2),y-18],[x+Math.max(11,width/2),y+4]);
    }
    const a=path.nodes[0],b=path.nodes.at(-1),straight=Math.hypot(b.x-a.x,b.y-a.y),developed=Math.abs(straight-path.length)>EPS;
    const heading=Math.min(top-38,...bounds.map(p=>p[1]))-12,footer=dimensions?base+(path.edges.length>1?105:75):base+39;
    const titleElement=selectable("axis",axis.id,`Editar eje ${axis.id}`,"elevation-axis-title");hitLabel(titleElement,0,heading,`${axis.id} · ${axis.nombre||""} · Corte longitudinal central${developed?" desarrollado":""}`,{"font-size":12,"font-weight":600});group.append(titleElement);
    label(0,footer,"Distancias entre ejes en planta y cotas locales en metros · misma escala horizontal y vertical.");label(0,footer+15,"Rayado: material cortado. Huecos sin relleno. Cabezales ocres: aproximados. Pilotes: sólo los intersectados.");
    bounds.push([-25,heading-15],[path.length*scale+25,footer+28]);return {group,bounds,stations:path.stations,developed};
  }
  const api={walk,create,suggest,syncSupports,reconcile,renameReferences,movePreview,applyMove,renderPlan,elevation};root.AxisManager=api;if(typeof module!=="undefined")module.exports=api;
})(typeof window!=="undefined"?window:globalThis);
