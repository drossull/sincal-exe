// The preview uses assembled pieces returned by the same engine as CAD.
const NS='http://www.w3.org/2000/svg';
const format=value=>Number(value).toLocaleString('es-CL',{maximumFractionDigits:1,useGrouping:false});
const COLORS=['#ffb300','#70d7eb','#cba1ff'];
function svgNode(tag,attrs={},text){
  const el=document.createElementNS(NS,tag);
  for(const [key,value] of Object.entries(attrs))el.setAttribute(key,String(value));
  if(text!==undefined)el.textContent=text;
  return el;
}

export function splicePreview(group){
  // One orthographic camera for every piece preserves the actual transverse
  // contact. Flattening each piece into its own plane would collapse the lap.
  const project=p=>[p[0],p.length>2?(p[1]+p[2])/Math.SQRT2:p[1]];
  const points=group.pieces.flatMap(piece=>piece.points_m).map(project),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  const laps=group.pieces.flatMap(piece=>piece.lap_segments_m||[]);
  const scale=Math.min(820/Math.max(maxX-minX,.01),170/Math.max(maxY-minY,.01));
  const top=80+laps.length*55,bottom=top+(maxY-minY)*scale+60;
  const convert=p=>{const q=project(p);return [500+(q[0]-(minX+maxX)/2)*scale,top+(maxY-q[1])*scale];};
  const svg=svgNode('svg',{viewBox:`0 0 1000 ${bottom+laps.length*108-30}`,class:'rebar-splice-preview rebar-detail-preview',role:'img','data-dimstyle':'GSG_COTAS','aria-label':`${laps.length?'Empalmes':'Piezas restantes'} de ${group.label}. Piezas reales lado a lado en contacto.`});
  const line=(a,b,attrs={})=>svgNode('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],...attrs});
  for(const [index,piece] of group.pieces.entries()){
    const polyline=svgNode('polyline',{points:piece.points_m.map(p=>convert(p).join(',')).join(' '),fill:'none',stroke:COLORS[index%COLORS.length],'stroke-width':Math.max(.65,(piece.diameter_mm||group.diameter_mm)/1000*scale),'data-splice-mark':piece.mark,'data-role':piece.piece_role});
    polyline.append(svgNode('title',{},`Marca ${piece.mark} · Largo desarrollado ${format(piece.length_cm)} cm`));svg.append(polyline);
  }
  function dimension(a,b,y,label,tag){
    const pa=convert(a),pb=convert(b),group=svgNode('g',{class:'dimension','data-splice-dimension':tag});
    for(const p of [pa,pb])group.append(line([p[0],y-18],[p[0],y+9],{class:'dimension-extension'}));
    group.append(line([pa[0],y],[pb[0],y],{class:'dimension-line'}));
    const length=Math.abs(pb[0]-pa[0]),size=Math.min(14,length/3);
    if(size>0)for(const [tip,sign] of [[pa[0],1],[pb[0],-1]])group.append(svgNode('polygon',{points:`${tip},${y} ${tip+size*sign},${y-2.5} ${tip+size*sign},${y+2.5}`,class:'dimension-arrow'}));
    const halfWidth=Math.min(470,label.length*6.5);
    const labelX=Math.max(halfWidth+15,Math.min(985-halfWidth,(pa[0]+pb[0])/2));
    group.append(svgNode('text',{x:labelX,y:y-23,'text-anchor':'middle',class:'dimension-text'},label));
    svg.append(group);
  }
  laps.forEach(([start,end],index)=>{
    const a=convert(start),b=convert(end),y=bottom+index*108;
    svg.append(line(a,b,{stroke:'#fff','stroke-width':.65,'data-splice-lap':index}));
    const distance=(p,q)=>Math.abs(p[0]-q[0])*100;
    dimension(start,end,65+index*55,`${format(distance(start,end))} cm · traslapo ${index+1}`,`lap-${index}`);
    // Two levels keep short end clearances readable beside long dimensions.
    dimension(group.main_start_m,start,y,`${format(distance(group.main_start_m,start))} cm · desde inicio`,`start-${index}`);
    dimension(end,group.main_end_m,y+48,`${format(distance(end,group.main_end_m))} cm · hasta final`,`end-${index}`);
  });
  return svg;
}

export function openSpliceEditor({ctx,state,rule,onApply,isCurrent=()=>true}){
  const {node,button,api}=ctx,dialog=node('dialog',undefined,'rebar-detail-dialog rebar-splice-dialog');
  const title=node('h2',`Empalmes · ${rule.label}`);title.id='rebar-splice-title';dialog.setAttribute('aria-labelledby',title.id);
  const label=node('label','Largo del primer fierro · cm'),input=node('input');
  input.type='number';input.min='0';input.max='1200';input.step='1';input.value=rule.first_piece_cm===null?'':rule.first_piece_cm??0;input.inputMode='decimal';label.append(input);
  const content=node('div',undefined,'rebar-splice-content'),status=node('p','Calculando empalmes…','muted');status.setAttribute('role','status');
  const actions=node('div',undefined,'actions');let sequence=0,timer=null,closed=false,accepted=null;
  const apply=button('Aplicar largo',()=>{
    if(!accepted||!isCurrent())return;
    onApply(accepted.value);dialog.close();
  },true);apply.disabled=true;
  const auto=button('Automático',()=>{input.value='0';queue();});
  actions.append(apply,button('Cerrar',()=>dialog.close()));
  const assemblyNote=node('p','Las piezas van lado a lado y en contacto durante el traslapo. La vista muestra su posición física.','muted');
  dialog.append(title,assemblyNote,label,auto,
    node('p','0 = automático. El largo incluye gancho y arco de doblez; máximo 1200 cm. La continuación se recalcula conservando el traslapo según diámetro.','muted'),status,content,actions);
  function queue(){
    const request=++sequence;accepted=null;apply.disabled=true;clearTimeout(timer);
    content.replaceChildren();status.textContent='Calculando empalmes…';dialog.setAttribute('aria-busy','true');
    timer=setTimeout(()=>refresh(request),250);
  }
  async function refresh(request){
    const value=input.value===''?null:Number(input.value),draft=structuredClone(state);
    draft.rules.find(item=>item.key===rule.key).first_piece_cm=value;
    try{
      const response=await api('rebar/preview',draft);
      if(closed||request!==sequence||!isCurrent())return;
      content.replaceChildren();
      if(!response.valid){status.textContent=response.issues.map(issue=>issue.message).join(' ');return;}
      const group=(response.splice_groups||[]).find(item=>item.key===rule.key);
      if(!group){status.textContent=!rule.enabled?'Activa este grupo para revisar sus empalmes.':rule.removed_pieces?.length?'No hay un empalme disponible en el recorrido de referencia. Esta familia tiene fierros eliminados; puedes restaurarlos en el visor.':'Este grupo cabe en piezas completas y no necesita empalmes.';return;}
      const hasLaps=group.pieces.some(piece=>(piece.lap_segments_m||[]).length);
      assemblyNote.textContent=group.removed_piece_count?`${group.removed_piece_count} ${group.removed_piece_count===1?'pieza eliminada':'piezas eliminadas'} en este recorrido. Se conservan las posiciones reales; sólo hay traslapo donde quedan ambas piezas.`:'Las piezas van lado a lado y en contacto durante el traslapo. La vista muestra su posición física.';
      const svg=splicePreview(group);
      const legend=node('div',undefined,'rebar-splice-legend');
      for(const [index,piece] of group.pieces.entries()){
        const item=node('span',`Marca ${piece.mark} · ${format(piece.length_cm)} cm`);item.style.setProperty('--piece-color',COLORS[index%COLORS.length]);legend.append(item);
      }
      content.append(legend,svg);
      if(hasLaps)content.append(node('p','Las distancias «desde inicio» y «hasta final» se miden sobre el tramo recto, desde las tangencias de los dobleces.','muted'));
      const summary=node('ul');
      let index=0;
      for(const piece of group.pieces)for(const [start,end] of piece.lap_segments_m||[]){
        const distance=(p,q)=>Math.abs(p[0]-q[0])*100;
        summary.append(node('li',`Empalme ${++index}: ${format(distance(start,end))} cm de traslapo · ${format(distance(group.main_start_m,start))} cm desde inicio · ${format(distance(end,group.main_end_m))} cm hasta final.`));
      }
      content.append(summary);status.textContent=hasLaps?'Vista actualizada. Aplica el largo para actualizar el estribo.':`Este recorrido conserva ${group.pieces.length} ${group.pieces.length===1?'pieza':'piezas'} y no tiene traslapos físicos entre ellas.`;
      accepted={value};apply.disabled=false;
    }catch(error){if(!closed&&request===sequence){content.replaceChildren();status.textContent=error.message;}}
    finally{if(!closed&&request===sequence)dialog.setAttribute('aria-busy','false');}
  }
  function dispose(){closed=true;sequence++;clearTimeout(timer);observer.disconnect();dialog.remove();}
  const observer=new MutationObserver(()=>{if(!isCurrent()||!dialog.isConnected)dispose();});
  input.addEventListener('input',queue);dialog.addEventListener('close',dispose,{once:true});
  document.body.append(dialog);observer.observe(document.body,{childList:true,subtree:true});dialog.showModal();queue();
  return {close:()=>dialog.close()};
}
