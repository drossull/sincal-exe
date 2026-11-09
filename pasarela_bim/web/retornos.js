/* Return supports reference one continuous deck; a centre column is not a split. */
"use strict";
(function(root){
  const copy=value=>JSON.parse(JSON.stringify(value)), EPS=.001;
  const uid=()=>root.ProjectIO?.uid?.()||root.crypto?.randomUUID?.()||`return-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const entities=m=>[...(m.nodos||[]),...(m.tramos||[]),...(m.soportes||[]),...(m.fundaciones||[]),...(m.ejes||[]),...(m.fundaciones||[]).flatMap(f=>f.pilotes||[])];
  function nextId(m,prefix,reserved=[]){const used=new Set([...reserved,...entities(m).map(e=>e.id)]);let i=1;while(used.has(prefix+i))i++;return prefix+i;}
  function interpolate(points,t,key){if(t<=points[0].t)return points[0][key];for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(t<=b.t)return a[key]+(b[key]-a[key])*(t-a.t)/(b.t-a.t);}return points.at(-1)[key];}
  function context(m,id){
    const edge=(m.tramos||[]).find(e=>e.id===id);
    if(!edge||!(edge.funcion==='retorno'||(!edge.funcion&&edge.tipo==='retorno')))throw new Error("Selecciona un tramo de retorno.");
    const a=m.nodos.find(n=>n.id===edge.desde),b=m.nodos.find(n=>n.id===edge.hasta);
    if(!a||!b||![a.x,a.y,a.z,b.x,b.y,b.z].every(Number.isFinite)||Math.hypot(b.x-a.x,b.y-a.y)<=EPS)throw new Error("El retorno necesita dos extremos con coordenadas y longitud válidas.");
    return {edge,a,b};
  }
  function position(m,edge,t){
    const a=m.nodos.find(n=>n.id===edge.desde),b=m.nodos.find(n=>n.id===edge.hasta),grade=edge.rasante||[{t:0,f:0},{t:1,f:1}];
    return {x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t,z:a.z+(b.z-a.z)*interpolate(grade,t,'f')};
  }
  function depth(m,edge,t){
    const source=m.familias?.[edge.familia];
    if(!source)return 1000;
    const volume=root.VolumePreview||(typeof module!=='undefined'?require('./volumen.js'):null),family=volume?.sectionFamily(m,edge,source)||source;
    if(!family)return 1000;
    const points=family.perfil_canto||[{t:0,canto_mm:family.canto_mm},{t:1,canto_mm:family.canto_fin_mm??family.canto_mm}];
    const h=interpolate(points,t,'canto_mm');return Number.isFinite(h)&&h>0?h:1000;
  }
  function supportTop(m,node,edge,central){
    if(central)return node.z-depth(m,edge,.5);
    const heights=m.tramos.filter(e=>e.desde===node.id||e.hasta===node.id).map(e=>depth(m,e,e.desde===node.id?0:1));
    return node.z-Math.max(...heights,heights.length?0:1000)-300;
  }
  function sync(m){
    const changes=[];
    for(const n of m.nodos||[]){
      const anchor=n.anclaje_tramo;if(!anchor)continue;
      const edge=(m.tramos||[]).find(e=>e.id===anchor.tramo);
      if(!edge||!Number.isFinite(anchor.t)||anchor.t<=0||anchor.t>=1||[edge.desde,edge.hasta].includes(n.id)||!m.nodos.some(v=>v.id===edge.desde)||!m.nodos.some(v=>v.id===edge.hasta))continue;
      const after=position(m,edge,anchor.t),before={x:n.x,y:n.y,z:n.z};
      if(!Object.values(after).every(Number.isFinite))continue;
      const dx=after.x-before.x,dy=after.y-before.y,dz=after.z-before.z;
      if(Math.max(Math.abs(dx),Math.abs(dy),Math.abs(dz))<1e-8)continue;
      Object.assign(n,after);
      if(Number.isFinite(dz))for(const s of m.soportes||[])if(s.nodo===n.id&&Number.isFinite(s.cota_superior_mm))s.cota_superior_mm+=dz;
      changes.push({id:n.id,before,after,dx,dy,dz});
    }
    return changes;
  }
  function describe(m,edgeId){
    const {edge}=context(m,edgeId),centreNodes=m.nodos.filter(n=>n.anclaje_tramo?.tramo===edgeId&&Math.abs(n.anclaje_tramo.t-.5)<1e-8);
    const items=ids=>ids.flatMap(id=>(m.soportes||[]).filter(s=>s.nodo===id).map(s=>({nodeId:id,supportId:s.id,foundationId:s.fundacion})));
    const central=items(centreNodes.map(n=>n.id)),ends=items([edge.desde,edge.hasta]);
    const all=[...central,...ends],nodeIds=[...new Set(all.map(s=>s.nodeId))],foundationIds=[...new Set(all.map(s=>s.foundationId).filter(Boolean))];
    return {edgeId,layout:central.length?(ends.length?'mixed':'central'):ends.length===2?'ends':ends.length?'partial':'none',shared:all.length>1&&foundationIds.length===1,centralNodeIds:centreNodes.map(n=>n.id),endNodeIds:[edge.desde,edge.hasta],nodeIds,foundationIds,central,ends};
  }
  function preview(input,edgeId,{layout='central',shared=false,terrainMm}={}){
    if(!['central','ends'].includes(layout))throw new Error("Selecciona una columna central o dos columnas en los extremos.");
    if(terrainMm!==undefined&&!Number.isFinite(terrainMm))throw new Error("Introduce una cota de terreno válida o déjala por definir.");
    const m=copy(input);m.nodos||=[];m.tramos||=[];m.soportes||=[];m.fundaciones||=[];m.ejes||=[];
    const reservedIds=new Set(entities(m).map(e=>e.id));
    const {edge,a,b}=context(m,edgeId);
    if(Math.abs(a.z-b.z)>EPS)throw new Error("El retorno debe permanecer horizontal antes de disponer sus apoyos.");
    sync(m);
    const summary={layout,shared:!!shared&&layout==='ends',createdNodes:[],createdSupports:[],createdFoundations:[],removedNodes:[],removedSupports:[],removedFoundations:[],preservedSupports:[],warnings:[]};
    const warn=message=>{if(!summary.warnings.includes(message))summary.warnings.push(message);};
    const old=describe(m,edgeId),wantedPositions=layout==='central'?['central']:['inicio','fin'];
    const unwanted=m.soportes.filter(s=>s.origen_retorno?.tramo===edgeId&&!wantedPositions.includes(s.origen_retorno.posicion));
    const unwantedIds=new Set(unwanted.map(s=>s.id));
    const canRemoveNode=s=>{
      const n=m.nodos.find(n=>n.id===s.nodo);
      return !!n&&!m.tramos.some(e=>e.id!==edgeId&&(e.desde===n.id||e.hasta===n.id))&&!m.soportes.some(other=>other!==s&&other.nodo===n.id);
    };
    // A shared base must be retired as a whole. Removing only one association
    // would move its derived centre under the support that remains.
    const removableFoundations=new Set(m.fundaciones.filter(f=>
      f.origen_retorno?.tramo===edgeId&&!f.pilotes?.length&&(f.nodos||[]).every(id=>unwanted.some(s=>s.nodo===id))&&
      m.soportes.filter(s=>s.fundacion===f.id).every(s=>unwantedIds.has(s.id)&&canRemoveNode(s))
    ).map(f=>f.id));
    for(const support of unwanted){
      const node=m.nodos.find(n=>n.id===support.nodo),foundation=m.fundaciones.find(f=>f.id===support.fundacion);
      if(!canRemoveNode(support)||!foundation||!removableFoundations.has(foundation.id)){
        summary.preservedSupports.push(support.id);warn(`Se conserva el apoyo ${support.id}: tiene conexiones, fundación o pilotes que requieren revisión independiente.`);continue;
      }
      m.soportes=m.soportes.filter(s=>s!==support);summary.removedSupports.push(support.id);
      foundation.nodos=(foundation.nodos||[]).filter(id=>id!==node.id);
      if(node.anclaje_tramo?.tramo===edgeId&&node.origen_retorno?.tramo===edgeId){m.nodos=m.nodos.filter(n=>n!==node);summary.removedNodes.push(node.id);}
      else node.tipo=support.origen_retorno.tipo_anterior||'encuentro';
      m.ejes=m.ejes.filter(axis=>axis.tipo!=='apoyo'||axis.nodo!==node.id);
      if(!foundation.nodos.length&&!m.soportes.some(s=>s.fundacion===foundation.id)){m.fundaciones=m.fundaciones.filter(f=>f!==foundation);summary.removedFoundations.push(foundation.id);}
    }
    // Unmanaged supports are always retained; changing a layout cannot silently erase work.
    for(const item of layout==='central'?old.ends:old.central)if(m.soportes.some(s=>s.id===item.supportId)&&!summary.preservedSupports.includes(item.supportId)){
      summary.preservedSupports.push(item.supportId);warn(`Se conserva el apoyo existente ${item.supportId}; la disposición añadirá los apoyos solicitados.`);
    }
    let targets;
    if(layout==='central'){
      const centres=m.nodos.filter(n=>n.anclaje_tramo?.tramo===edgeId&&Math.abs(n.anclaje_tramo.t-.5)<1e-8);
      if(centres.length>1)throw new Error("El retorno tiene más de un nodo central anclado. Revisa sus apoyos antes de añadir otro.");
      let node=centres[0];
      if(!node){node={id:nextId(m,'C',reservedIds),uuid:uid(),tipo:'columna',...position(m,edge,.5),anclaje_tramo:{tramo:edgeId,t:.5},origen_retorno:{tramo:edgeId,posicion:'central'}};m.nodos.push(node);summary.createdNodes.push(node.id);}
      targets=[{node,posicion:'central'}];
    }else targets=[{node:a,posicion:'inicio'},{node:b,posicion:'fin'}];
    const fresh=[];
    for(const item of targets){
      const existing=m.soportes.filter(s=>s.nodo===item.node.id);
      if(existing.length){
        if(existing.some(s=>!m.fundaciones.some(f=>f.id===s.fundacion)))throw new Error(`El apoyo ${item.node.id} tiene una fundación pendiente o inexistente. Completa su asociación antes de aplicar la disposición.`);
        if(terrainMm!==undefined)warn(`Se conserva la cota de terreno del apoyo existente ${item.node.id}; edítala en sus propiedades.`);
        item.supports=existing;continue;
      }
      const tipoAnterior=item.node.tipo;item.node.tipo='columna';
      const support={id:item.node.id,uuid:uid(),nodo:item.node.id,cota_superior_mm:supportTop(m,item.node,edge,item.posicion==='central'),diametro_mm:1000,origen_retorno:{tramo:edgeId,posicion:item.posicion,tipo_anterior:tipoAnterior}};
      if(terrainMm!==undefined)support.cota_terreno_proyectado_mm=terrainMm;
      item.supports=[support];fresh.push(item);
    }
    function createFoundation(items,combined){
      const tops=items.map(item=>item.supports[0].cota_superior_mm-1000),id=nextId(m,'F',reservedIds);
      const foundation={id,uuid:uid(),nodos:items.map(item=>item.node.id),largo_mm:combined?Math.hypot(b.x-a.x,b.y-a.y)+3000:3000,ancho_mm:3000,alto_mm:1000,cota_superior_mm:Math.min(...tops,...(terrainMm===undefined?[]:[terrainMm])),angulo_deg:combined?Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI:0,pilotes:[],origen_retorno:{tramo:edgeId}};
      m.fundaciones.push(foundation);summary.createdFoundations.push(id);
      for(const item of items){item.supports[0].fundacion=id;m.soportes.push(item.supports[0]);summary.createdSupports.push(item.supports[0].id);}
    }
    if(layout==='ends'&&shared&&fresh.length===2)createFoundation(fresh,true);
    else{
      fresh.forEach(item=>createFoundation([item],false));
      const ids=new Set(targets.flatMap(item=>item.supports.map(s=>s.fundacion)));
      if(layout==='ends'&&shared&&ids.size!==1)warn("Se conservan las fundaciones existentes. Para compartirlas, utiliza la asociación de fundaciones y revisa sus pilotes y dimensiones.");
      if(layout==='ends'&&!shared&&ids.size===1)warn("Se conserva la fundación compartida existente; no se separa automáticamente.");
    }
    if(terrainMm===undefined&&fresh.length)warn("La cota de terreno proyectado queda por definir en cada apoyo nuevo. Las dimensiones iniciales y cotas de fundación son editables.");
    const nodeIds=targets.map(item=>item.node.id),foundationIds=[...new Set(targets.flatMap(item=>item.supports.map(s=>s.fundacion)))];
    summary.shared=layout==='ends'&&foundationIds.length===1;
    return {model:m,summary,nodeIds,foundationIds};
  }
  root.ReturnSupports={preview,sync,describe};if(typeof module!=='undefined')module.exports=root.ReturnSupports;
})(typeof window!=='undefined'?window:globalThis);
