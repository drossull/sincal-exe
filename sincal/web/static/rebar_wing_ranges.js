// Supplementary parameter drafts; only the lower front boundary is editable.
// No placement, bar geometry or quantity is inferred here.
const NS='http://www.w3.org/2000/svg';
const GROUPS=[['back','Grupo superior · gancho en espaldar','espaldar'],['front','Grupo inferior · gancho en frontal','frontal']];
const finite=value=>typeof value==='number'&&Number.isFinite(value);
let nextProfile=0;
function svgNode(tag,attributes={},text){
  const element=document.createElementNS(NS,tag);
  for(const [key,value] of Object.entries(attributes))element.setAttribute(key,String(value));
  if(text!==undefined)element.textContent=text;
  return element;
}

export function mountWingSupplementControls(ctx,host,state,preview,onChange){
  const {node}=ctx,root=node('div',undefined,'rebar-wing-supplements');host.append(root);
  const inputs=[],groups=new Map(),clipId=`wing-supplement-${++nextProfile}`;let metadata=preview,disposed=false,frame=null,selecting=false,dragging=null,dragMoved=false,chooseLower=null,extensions=[];
  root.append(node('p','Suples en la cara interior, intercalados entre los horizontales de la malla interior. El grupo superior llega al espaldar y el inferior al frontal. En alas giradas, el tramo desde el gancho al extremo libre sigue ambas caras.','muted'));
  const panel=node('div',undefined,'wing-supplement-fields');root.append(panel);
  const hint=node('p',undefined,'wing-supplement-hint');hint.setAttribute('aria-live','polite');root.append(hint);
  const svg=svgNode('svg',{viewBox:'0 0 1000 600',role:'group','aria-label':'Perfil de suples del ala, frontal y espaldar',tabindex:0});root.append(svg);
  root.append(node('p','La unión de los grupos queda en la coronación del frontal y el grupo superior alcanza el techo. El salto entre los últimos vecinos no debe superar 20 cm. Las bandas son zonas de referencia; no representan fierros ni añaden cantidades.','muted'));
  function publish(){if(!disposed){refresh();onChange();}}
  function field(owner,key,label,unit){
    const wrapper=node('label',unit?`${label} · ${unit}`:label),input=node('input');
    if(key==='mark'){input.maxLength=32;input.value=owner[key]??'';}
    else{input.type='number';input.step=key==='quantity'?'1':'any';if(key==='quantity')input.min='2';if(key==='min_extension_cm')input.min='100';input.inputMode='decimal';input.value=owner[key]??'';}
    input.addEventListener('input',()=>{owner[key]=key==='mark'?input.value:input.value===''?null:Number(input.value);publish();});
    wrapper.append(input);inputs.push({input,owner,key});return wrapper;
  }
  for(const [key,label,short] of GROUPS){
    const values=state.supplements[key],fieldset=node('fieldset'),toggleLabel=node('label',undefined,'rebar-wing-confirmation'),toggle=node('input');
    toggle.type='checkbox';toggleLabel.append(toggle,node('span',`Incluir grupo hacia el ${short}`));
    const fields=node('div',undefined,'fields');fields.append(field(values,'mark',`Marca del grupo hacia el ${short}`),
      field(values,'diameter_mm',`Diámetro del grupo hacia el ${short}`,'mm'),field(values,'spacing_cm',`Separación del grupo hacia el ${short}`,'cm'),
      field(values,'hook_cm',`Gancho hacia el ${short}`,'cm'),field(values,'straight_cm',`Tramo desde el gancho al extremo libre · ${short}`,'cm'));
    if(key==='front')fields.append(field(values,'range_height_cm','Altura del grupo frontal hacia abajo desde su coronación','cm'));
    const issues=node('p',undefined,'wing-supplement-validation');issues.setAttribute('aria-live','polite');
    toggle.onchange=()=>{values.enabled=toggle.checked;if(key==='front'&&!values.enabled)selecting=false;publish();};fieldset.append(node('legend',label),toggleLabel,fields,issues);
    if(key==='front'){
      chooseLower=node('button','Elegir límite inferior en el perfil');chooseLower.type='button';
      chooseLower.onclick=()=>{selecting=!selecting;refresh();if(selecting)svg.focus({preventScroll:true});};fieldset.append(chooseLower);
    }
    panel.append(fieldset);groups.set(key,{toggle,issues});
  }
  const edge=node('fieldset'),edgeFields=node('div',undefined,'fields'),edgeState=state.edge_rebar;
  edge.append(node('legend','Fierro de canto de la aleta · obligatorio'),node('p','Reparto uniforme. Elige el largo total; la prolongación real debe alcanzar el mínimo indicado, de al menos 100 cm. No se redondea automáticamente.','muted'));
  edgeFields.append(field(edgeState,'mark','Marca del fierro de canto'),field(edgeState,'quantity','Cantidad de fierros de canto'),
    field(edgeState,'diameter_mm','Diámetro del fierro de canto','mm'),field(edgeState,'total_cm','Largo total del fierro de canto','cm'),field(edgeState,'min_extension_cm','Prolongación mínima del fierro de canto','cm'));
  const hookLabel=node('label',undefined,'rebar-wing-confirmation'),hookToggle=node('input');hookToggle.type='checkbox';
  hookLabel.append(hookToggle,node('span','Incluir gancho superior del fierro de canto'));
  const hookField=field(edgeState,'top_hook_cm','Gancho superior del fierro de canto','cm');
  hookToggle.onchange=()=>{edgeState.top_hook_enabled=hookToggle.checked;publish();};
  const edgeIssues=node('p',undefined,'wing-supplement-validation');edgeIssues.setAttribute('aria-live','polite');
  const extensionOutput=node('div',undefined,'wing-edge-extensions');extensionOutput.setAttribute('aria-live','polite');
  edge.append(edgeFields,hookLabel,hookField,edgeIssues,extensionOutput);root.append(edge);
  const legacy=node('p','Se conservaron los rangos anteriores como antecedente. Sus alturas no se aplican a estos grupos.','muted');legacy.hidden=!state.supplements_legacy;root.append(legacy);

  function invalid(owner,key){
    const value=owner[key];return key!=='mark'&&value!=null&&(!finite(value)||value<=0||(key==='quantity'&&(!Number.isInteger(value)||value<2))||key==='min_extension_cm'&&value<100||key==='range_height_cm'&&finite(metadata?.front_height_cm)&&value>metadata.front_height_cm);
  }
  function refresh(){
    const hasExtension=metadata?.extension_enabled===true;edge.hidden=!hasExtension;hookToggle.checked=edgeState.top_hook_enabled===true;
    for(const [key,{toggle,issues}] of groups){
      const values=state.supplements[key];toggle.checked=values.enabled===true;
      issues.textContent=values.enabled&&['diameter_mm','spacing_cm','hook_cm','straight_cm'].some(key=>invalid(values,key))?'Los diámetros, separaciones y largos deben ser positivos.':'';
      if(key==='front'&&values.enabled&&invalid(values,'range_height_cm'))issues.textContent+=' La altura del grupo debe ser positiva y no bajar de la cara superior de la zapata.';
      issues.hidden=!issues.textContent;
    }
    edgeIssues.textContent=hasExtension&&['quantity','diameter_mm','total_cm',...(edgeState.top_hook_enabled?['top_hook_cm']:[])].some(key=>invalid(edgeState,key))?'Usa una cantidad entera de al menos 2 fierros y medidas positivas.':'';
    if(hasExtension&&invalid(edgeState,'min_extension_cm'))edgeIssues.textContent+=' La prolongación mínima debe ser de al menos 100 cm.';
    edgeIssues.hidden=!edgeIssues.textContent;
    extensionOutput.replaceChildren();
    if(extensions.length){
      extensionOutput.append(node('p','Prolongación real calculada · cm','muted'));
      const rows=node('div',undefined,'fields');extensions.forEach((piece,index)=>{const label=node('label',`Fierro de canto ${index+1}`),input=node('input');input.readOnly=true;input.value=piece.extension_cm.toLocaleString('es-CL',{maximumFractionDigits:2});label.append(input);rows.append(label);});extensionOutput.append(rows);
    }
    for(const {input,owner,key} of inputs){
      if(document.activeElement!==input)input.value=owner[key]??'';
      input.disabled=owner===edgeState?!hasExtension||key==='top_hook_cm'&&!edgeState.top_hook_enabled:owner.enabled!==true;
      input.setAttribute('aria-invalid',String(!input.disabled&&invalid(owner,key)));
    }
    draw();
    chooseLower.disabled=!state.supplements.front.enabled||!frame;
    chooseLower.textContent=selecting?'Cancelar selección del límite inferior':'Elegir límite inferior en el perfil';chooseLower.setAttribute('aria-pressed',String(selecting));
  }
  function draw(){
    const focused=document.activeElement?.hasAttribute('data-front-lower');svg.replaceChildren();frame=null;const profile=metadata?.profile_cm;
    if(!Array.isArray(profile)||profile.length<3||profile.some(point=>!Array.isArray(point)||point.length!==2||!point.every(finite))){
      selecting=false;hint.textContent='Completa la geometría del ala para ver su perfil.';svg.setAttribute('hidden','');return;
    }
    const minX=Math.min(...profile.map(point=>point[0])),maxX=Math.max(...profile.map(point=>point[0]));
    const minZ=Math.min(...profile.map(point=>point[1])),maxZ=Math.max(...profile.map(point=>point[1]));
    if(maxX<=minX||maxZ<=minZ){svg.setAttribute('hidden','');return;}
    hint.textContent=selecting?'Pulsa la altura del límite inferior del grupo frontal. Escape cancela.':'Sólo el límite inferior del grupo frontal se puede mover. La unión y el techo quedan fijos.';svg.removeAttribute('hidden');
    const scale=Math.min(740/(maxX-minX),425/(maxZ-minZ));
    const left=90+(740-(maxX-minX)*scale)/2,top=70+(425-(maxZ-minZ)*scale)/2;
    const x=u=>left+(maxX-u)*scale,y=z=>top+(maxZ-z)*scale;
    frame={z:py=>maxZ-(py-top)/scale};
    const points=profile.map(([u,z])=>`${x(u)},${y(z)}`).join(' ');
    const defs=svgNode('defs'),clip=svgNode('clipPath',{id:clipId});clip.append(svgNode('polygon',{points}));defs.append(clip);svg.append(defs);
    svg.append(svgNode('polygon',{points,class:'wing-supplement-profile'}));
    const zero=y(0);svg.append(svgNode('line',{x1:60,x2:940,y1:zero,y2:zero,class:'wing-supplement-zero'}),svgNode('text',{x:60,y:Math.min(580,zero+35)},'0 · Cara superior de la zapata'));
    svg.append(svgNode('text',{x:90,y:30},metadata.extension_enabled?'Aleta / punta ←':'Punta ←'),svgNode('text',{x:910,y:30,'text-anchor':'end'},'→ Frontal / espaldar'));
    const back=metadata.back_thickness_cm,frontHeight=metadata.front_height_cm;
    const backTop=Math.max(...profile.filter(([u])=>u>=-back-1e-6&&u<=1e-6).map(point=>point[1]));
    const drawBand=(low,high,group)=>{if(finite(low)&&finite(high)&&high>low)svg.append(svgNode('rect',{x:x(maxX),y:y(high),width:x(minX)-x(maxX),height:(high-low)*scale,'clip-path':`url(#${clipId})`,class:`wing-supplement-band wing-supplement-band-${group}`}));};
    if(state.supplements.back.enabled)drawBand(frontHeight,backTop,'back');
    const front=state.supplements.front;
    if(front.enabled&&finite(front.range_height_cm)&&finite(frontHeight)){
      const low=frontHeight-front.range_height_cm;if(!invalid(front,'range_height_cm'))drawBand(low,frontHeight,'front');
      const limit=svgNode('g',{'data-front-lower':'',class:'wing-supplement-limit',role:'slider',tabindex:0,'aria-label':'Límite inferior del grupo frontal','aria-orientation':'vertical','aria-valuenow':low,'aria-valuetext':`${low} cm sobre la zapata`});
      limit.append(svgNode('line',{x1:x(maxX),x2:x(minX),y1:y(low),y2:y(low),class:'wing-supplement-limit-line'}),svgNode('line',{x1:x(maxX),x2:x(minX),y1:y(low),y2:y(low),class:'wing-supplement-limit-hit'}),svgNode('circle',{cx:880,cy:y(low),r:9}),svgNode('text',{x:940,y:y(low)-15,'text-anchor':'end'},`Límite ${low.toLocaleString('es-CL')} cm`));svg.append(limit);
    }
    if((front.enabled||state.supplements.back.enabled)&&finite(frontHeight))svg.append(svgNode('line',{x1:x(maxX),x2:x(minX),y1:y(frontHeight),y2:y(frontHeight),class:'wing-supplement-fixed'}));
    if(finite(back)&&back>0&&minX<0){
      if(finite(backTop)){const labelY=Math.max(60,y(backTop)-24);svg.append(svgNode('line',{x1:x(-back/2),x2:900,y1:y(backTop),y2:labelY+6,class:'wing-supplement-guide'}),svgNode('text',{x:920,y:labelY,'text-anchor':'end'},'Espaldar'));}
      if(finite(frontHeight))svg.append(svgNode('line',{x1:x((minX-back)/2),x2:900,y1:y(frontHeight),y2:y(frontHeight)-18,class:'wing-supplement-guide'}),svgNode('text',{x:920,y:y(frontHeight)-24,'text-anchor':'end'},'Frontal'));
    }
    if(focused)svg.querySelector('[data-front-lower]')?.focus({preventScroll:true});
  }
  function setLower(low){if(disposed||!state.supplements.front.enabled||!finite(low)||!finite(metadata?.front_height_cm))return;state.supplements.front.range_height_cm=metadata.front_height_cm-low;publish();}
  function heightAt(event){const matrix=svg.getScreenCTM();if(!frame||!matrix)return null;return Math.round(frame.z(new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse()).y));}
  svg.addEventListener('pointerdown',event=>{if(selecting||event.button!==0||!event.target.closest('[data-front-lower]'))return;dragging=event.pointerId;dragMoved=false;svg.setPointerCapture(event.pointerId);event.target.closest('[data-front-lower]').focus({preventScroll:true});event.preventDefault();});
  svg.addEventListener('pointermove',event=>{if(dragging!==event.pointerId)return;dragMoved=true;setLower(heightAt(event));});
  const release=event=>{if(dragging===event.pointerId){if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId);dragging=null;}};
  svg.addEventListener('pointerup',release);svg.addEventListener('pointercancel',release);
  svg.addEventListener('click',event=>{if(dragMoved){dragMoved=false;return;}if(selecting&&event.button===0){const low=heightAt(event);selecting=false;setLower(low);}});
  svg.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&selecting){selecting=false;refresh();event.preventDefault();return;}
    if(!event.target.closest('[data-front-lower]')||!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key))return;
    setLower(metadata.front_height_cm-state.supplements.front.range_height_cm+(['ArrowUp','ArrowRight'].includes(event.key)?1:-1)*(event.shiftKey?10:1));event.preventDefault();
  });
  refresh();
  return {update(next,result){if(!disposed){metadata=next;extensions=Array.isArray(result?.edge_extensions_cm)?result.edge_extensions_cm.filter(piece=>piece&&typeof piece.id==='string'&&finite(piece.extension_cm)):[];refresh();}},invalidate(){if(!disposed){extensions=[];refresh();}},dispose(){disposed=true;selecting=false;dragging=null;}};
}
