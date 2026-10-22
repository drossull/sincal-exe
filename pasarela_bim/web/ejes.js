/* Axes reference the topology; they never duplicate its coordinates. */
"use strict";
(function(root){
  const copy=v=>JSON.parse(JSON.stringify(v)), EPS=.001, NS="http://www.w3.org/2000/svg";
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
    return {nodes:ordered,edges:chain,stations,length:stations.at(-1)};
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
    const path=walk(model,axis),ids=connected?component(model,path.nodes.map(n=>n.id)):new Set(path.nodes.map(n=>n.id)),changed=Math.hypot(delta.x,delta.y)>EPS;
    const candidate=copy(model),warnings=[],nodos=[];
    for(const n of candidate.nodos)if(ids.has(n.id)&&changed){if(n.xy_fijo||n.posicion_fija)throw new Error(`${n.id}: su posición fija impide mover este eje.`);const before={x:n.x,y:n.y,z:n.z};n.x+=delta.x;n.y+=delta.y;nodos.push({id:n.id,before,after:{x:n.x,y:n.y,z:n.z},dz:0});}
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
  function elevation(m,axisId){const axis=(m.ejes||[]).find(a=>a.id===axisId);if(!axis||axis.tipo==="apoyo")throw new Error("Selecciona un eje del atravieso o de un recorrido.");const path=walk(m,axis),scale=14/1000,group=svg("g",{class:"axis-elevation"}),bounds=[],xy=(s,z)=>{const p=[s*scale,-z*scale];bounds.push(p);return p;},line=(a,b,attrs={})=>group.append(svg("line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:"#8b9aa4",...attrs})),label=(x,y,text,attrs={})=>{const size=attrs["font-size"]||9,width=String(text).length*size*.53,start=attrs["text-anchor"]==="middle"?x-width/2:x;bounds.push([start,y-size],[start+width,y+2]);group.append(svg("text",{x,y,"font-size":9,fill:"#334d60",...attrs},text));};
    const hatchId='axis-concrete-cut',defs=svg('defs'),pattern=svg('pattern',{id:hatchId,width:7,height:7,patternUnits:'userSpaceOnUse'});pattern.append(svg('rect',{width:7,height:7,fill:'#e5edf1'}),svg('path',{d:'M-2,2 L2,-2 M0,7 L7,0 M5,9 L9,5',stroke:'#9aafb9','stroke-width':.55}));defs.append(pattern);group.append(defs);
    const cutRect=(station,left,right,bottom,upper,kind)=>{if(!(right>left&&upper>bottom))return;const ps=[[station+left,bottom],[station+right,bottom],[station+right,upper],[station+left,upper]].map(([s,z])=>xy(s,z));group.append(svg('polygon',{class:kind,points:ps.map(p=>p.join(',')).join(' '),fill:`url(#${hatchId})`,stroke:'#486a7a','stroke-width':1}));};
    const terrain=path.nodes.flatMap((node,index)=>(m.soportes||[]).filter(s=>s.nodo===node.id&&Number.isFinite(s.cota_terreno_proyectado_mm)).map(s=>({node,support:s,station:path.stations[index],z:s.cota_terreno_proyectado_mm})));
    const minZ=Math.min(0,...path.nodes.map(n=>n.z),...terrain.map(t=>t.z),...(m.fundaciones||[]).map(f=>(f.cota_superior_mm||0)-(f.alto_mm||0)-Math.max(0,...(f.pilotes||[]).map(p=>p.longitud_mm||0)))),maxZ=Math.max(...path.nodes.map(n=>n.z),...terrain.map(t=>t.z)),base=-minZ*scale+30,top=-maxZ*scale-25;
    for(let i=0;i<path.edges.length;i++){const e=path.edges[i],a=m.nodos.find(n=>n.id===e.desde),b=m.nodos.find(n=>n.id===e.hasta),L=path.stations[i+1]-path.stations[i],forward=path.nodes[i].id===e.desde,p=e.rasante||[{t:0,f:0},{t:1,f:1}],family=root.VolumePreview?.sectionFamily(m,e)||m.familias?.[e.familia]||{},depth=family.perfil_canto||[{t:0,canto_mm:family.canto_mm||250},{t:1,canto_mm:family.canto_fin_mm||family.canto_mm||250}],lo=(e.retranqueo_inicio_mm||0)/L,hi=1-(e.retranqueo_fin_mm||0)/L;
      if(lo>=hi)continue;const ts=[...new Set([lo,hi,...p.map(v=>v.t),...depth.map(v=>v.t)])].filter(t=>t>=lo&&t<=hi).sort((x,y)=>x-y),upper=ts.map(t=>xy(path.stations[i]+L*(forward?t:1-t),a.z+(b.z-a.z)*interpolate(p,t,"f"))),lower=ts.map(t=>xy(path.stations[i]+L*(forward?t:1-t),a.z+(b.z-a.z)*interpolate(p,t,"f")-interpolate(depth,t,"canto_mm")));
      const cut=root.VolumePreview?.longitudinalSection(m,e);
      if(cut){const contour=pts=>pts.map(([s,z],index)=>{const pt=xy(path.stations[i]+(forward?s:L-s),z);return `${index?'L':'M'}${pt[0]},${pt[1]}`;}).join(' ')+' Z';const shape=svg('path',{class:'beam-longitudinal-cut','data-cut-edge':e.id,d:contour(cut.outer)+(cut.inner.length?' '+contour(cut.inner):''),'fill-rule':'evenodd',fill:`url(#${hatchId})`,stroke:'#377a9b','stroke-width':1.2});shape.append(svg('title',{},`Corte central de ${e.id}${cut.inner.length?': hueco interior y macizados de extremos':''}`));group.append(shape);}
      else group.append(svg("polygon",{points:[...upper,...lower.reverse()].map(p=>p.join(",")).join(" "),fill:"#dbe8ef",stroke:"#377a9b","stroke-width":1.2}));const mid=(path.stations[i]+path.stations[i+1])/2*scale;label(mid,Math.min(...upper.map(p=>p[1]))-10,e.id,{"text-anchor":"middle"});line([path.stations[i]*scale,base],[path.stations[i+1]*scale,base]);label(mid,base-5,`${(L/1000).toFixed(3)} m`,{"text-anchor":"middle"});
    }
    // Longitudinal section of the same conceptual caps used in the 3D preview.
    if(root.VolumePreview?.capitals)for(let i=0;i<path.nodes.length;i++){
      const n=path.nodes[i],support=m.soportes?.find(s=>s.nodo===n.id);if(!support)continue;
      for(const part of root.VolumePreview.capitals(m,support)){
        const edgeIndex=path.edges.findIndex(e=>e.id===part.edgeId);if(edgeIndex<0)continue;
        const direction=edgeIndex===i?1:-1,stations=part.stations.map(s=>path.stations[i]+direction*s);
        const polygon=svg("polygon",{class:"capital-elevation","data-capital-node":n.id,points:[xy(stations[0],part.base),xy(stations[1],part.base),xy(stations[1],part.tops[1]),xy(stations[0],part.tops[0])].map(p=>p.join(',')).join(' '),fill:"#dbc39b",stroke:"#9a7d52","stroke-width":1,"vector-effect":"non-scaling-stroke"});
        polygon.append(svg("title",{},`Cabezal conceptual de ${n.id}: unión aproximada entre columna e intradós de ${part.edgeId}`));group.append(polygon);
      }
    }
    for(let i=0;i<path.nodes.length;i++){
      const n=path.nodes[i],support=m.soportes?.find(s=>s.nodo===n.id),foundation=m.fundaciones?.find(f=>f.id===support?.fundacion);if(!support||!foundation)continue;
      const neighbor=path.nodes[i+1]||path.nodes[i-1],length=Math.hypot(neighbor.x-n.x,neighbor.y-n.y),sign=i+1<path.nodes.length?1:-1,ux=(neighbor.x-n.x)/length*sign,uy=(neighbor.y-n.y)/length*sign;
      const angle=(foundation.angulo_deg||0)*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle);
      // Exact intersection of the vertical axis plane with a rotated rectangle.
      const rectangle=(cx,cy,L,W)=>{const ox=(n.x-cx)*c+(n.y-cy)*s,oy=-(n.x-cx)*s+(n.y-cy)*c,dx=ux*c+uy*s,dy=-ux*s+uy*c;let lo=-Infinity,hi=Infinity;for(const [o,d,half] of [[ox,dx,L/2],[oy,dy,W/2]]){if(Math.abs(d)<1e-10){if(Math.abs(o)>half)return null;}else{const a=(-half-o)/d,b=(half-o)/d;lo=Math.max(lo,Math.min(a,b));hi=Math.min(hi,Math.max(a,b));}}return hi>lo?[lo,hi]:null;};
      const column=support.diametro_mm?[-support.diametro_mm/2,support.diametro_mm/2]:rectangle(n.x,n.y,support.largo_mm,support.ancho_mm);
      if(column)cutRect(path.stations[i],...column,foundation.cota_superior_mm,support.cota_superior_mm,'support-longitudinal-cut');
      const ns=(foundation.nodos||[]).map(id=>m.nodos.find(n=>n.id===id)).filter(Boolean);if(!ns.length)continue;
      const cx=ns.reduce((sum,n)=>sum+n.x,0)/ns.length,cy=ns.reduce((sum,n)=>sum+n.y,0)/ns.length,foot=rectangle(cx,cy,foundation.largo_mm,foundation.ancho_mm),bottom=foundation.cota_superior_mm-foundation.alto_mm;
      if(foot)cutRect(path.stations[i],...foot,bottom,foundation.cota_superior_mm,'foundation-longitudinal-cut');
      for(const pile of foundation.pilotes||[]){const px=cx+pile.dx_mm*c-pile.dy_mm*s,py=cy+pile.dx_mm*s+pile.dy_mm*c,along=(px-n.x)*ux+(py-n.y)*uy,offset=-(px-n.x)*uy+(py-n.y)*ux,r=pile.diametro_mm/2;if(Math.abs(offset)>=r)continue;const half=Math.sqrt(r*r-offset*offset);cutRect(path.stations[i],along-half,along+half,bottom-pile.longitud_mm,bottom,'pile-longitudinal-cut');}
    }
    for(let i=0;i<path.nodes.length;i++){const n=path.nodes[i],x=path.stations[i]*scale,supportAxis=m.ejes?.find(a=>a.tipo==="apoyo"&&a.nodo===n.id),s=m.soportes?.find(s=>s.nodo===n.id),f=m.fundaciones?.find(f=>f.id===s?.fundacion);if(supportAxis){line([x,top],[x,base+3],{stroke:"#94613f","stroke-dasharray":"8 3 2 3"});group.append(svg("circle",{cx:x,cy:top-10,r:12,fill:"#fffaf3",stroke:"#94613f"}));label(x,top-7,supportAxis.id,{"text-anchor":"middle","font-size":8});}
      label(x,base+15,n.id,{"text-anchor":"middle"});label(x,base+28,`s ${(path.stations[i]/1000).toFixed(3)}`,{"text-anchor":"middle"});label(x,base+41,`Z ${(n.z/1000).toFixed(3)}`,{"text-anchor":"middle"});line([x,base-3],[x,base+3]);
    }
    // Each level belongs to the centre of its support, even on a shared footing.
    // A short point marker is a datum, never an inferred terrain profile.
    for(const t of terrain){const [x,y]=xy(t.station,t.z),text=`Terreno proyectado ${(t.z/1000).toFixed(3)} m`,width=text.length*8*.53,marker=svg('g',{class:'projected-terrain-level','data-support-id':t.support.id,'data-node-id':t.node.id,'data-z-mm':t.z});
      marker.append(svg('line',{x1:x-11,y1:y,x2:x+11,y2:y,stroke:'#637847','stroke-width':1.2}),svg('circle',{cx:x,cy:y,r:2.5,fill:'#fff',stroke:'#637847','stroke-width':1.2}),svg('text',{x,y:y-8,'text-anchor':'middle','font-size':8,fill:'#52643e',stroke:'#f8fbfd','stroke-width':2,'stroke-linejoin':'round','paint-order':'stroke'},text),svg('title',{},`${t.support.id}: nivel proyectado en el centro del apoyo; no define una superficie de terreno.`));group.append(marker);bounds.push([x-Math.max(11,width/2),y-18],[x+Math.max(11,width/2),y+4]);
    }
    const a=path.nodes[0],b=path.nodes.at(-1),straight=Math.hypot(b.x-a.x,b.y-a.y),developed=Math.abs(straight-path.length)>EPS;
    label(0,top-38,`${axis.id} · ${axis.nombre||""} · Corte longitudinal central${developed?" desarrollado":""}`,{"font-size":12,"font-weight":600});label(0,base+67,"Distancias en planta y cotas locales en metros · misma escala horizontal y vertical.");label(0,base+82,"Rayado: material cortado. Huecos sin relleno. Cabezales ocres: aproximados. Pilotes: sólo los intersectados.");
    bounds.push([-25,top-50],[path.length*scale+25,base+95]);return {group,bounds,stations:path.stations,developed};
  }
  const api={walk,create,suggest,syncSupports,reconcile,renameReferences,movePreview,applyMove,renderPlan,elevation};root.AxisManager=api;if(typeof module!=="undefined")module.exports=api;
})(typeof window!=="undefined"?window:globalThis);
