// Configuration preview only. Fabrication geometry, quantities and CAD insertion
// remain unavailable until the pile detailing rules have been completed.
const ZONES=[
  {key:'lower',label:'Inferior',color:'#e6a23c'},
  {key:'middle',label:'Medio',color:'#55a8e6'},
  {key:'upper',label:'Superior / confinamiento',color:'#bd86df'},
];
const SVG_NS='http://www.w3.org/2000/svg';
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const positive=value=>finite(value)&&value>0;
const format=value=>Number(value).toLocaleString('es-CL',{maximumFractionDigits:2});

function svgNode(tag,attributes,text){
  const element=document.createElementNS(SVG_NS,tag);
  for(const [key,value] of Object.entries(attributes))element.setAttribute(key,String(value));
  if(text!==undefined)element.textContent=text;
  return element;
}

export async function renderPilePreview(ctx,host,instanceKey){
  const {project,api,node,changed,current,notify}=ctx;
  const root=node('div',undefined,'rebar-pile-preview');host.append(root);
  const alive=()=>root.isConnected&&current();
  root.append(node('p','Preparando vista previa del pilote…','muted'));
  let source;
  try{
    source=await api('rebar/pile/from-project',{project:project.data,instance_key:instanceKey});
    if(!alive())return;
    if(source.present!==true){root.replaceChildren(node('p','El JSON no activa pilotes para este estribo.','muted'));return;}
    project.rebar??={};
    if(!project.rebar[instanceKey]){
      const footings=await api('rebar/from-project',project.data);
      if(!alive())return;
      project.rebar[instanceKey]=structuredClone(footings[instanceKey]);
    }
    if(!project.rebar[instanceKey].pile){
      project.rebar[instanceKey].pile=structuredClone(source.state);
      changed();
    }
  }catch(error){
    if(alive()){root.replaceChildren(node('p','No se pudo preparar la vista previa del pilote.','badge'));notify(error.message);}
    return;
  }

  const state=project.rebar[instanceKey].pile;
  let revision=0,timer,firstStartInput;
  root.replaceChildren(node('h3','Vista previa del pilote'));
  root.append(node('p','Vista previa de rangos; cálculo y despiece pendientes.','badge'));
  const drawing=node('div'),messages=node('div');messages.setAttribute('aria-live','polite');

  function fieldset(title){
    const fieldset=node('fieldset'),grid=node('div',undefined,'fields');
    grid.style.gridTemplateColumns='repeat(auto-fit,minmax(min(100%,150px),1fr))';
    fieldset.append(node('legend',title),grid);root.append(fieldset);return {fieldset,grid};
  }

  function numeric(label,object,key,step=1,placeholder){
    const field=node('label',label),input=node('input');
    input.type='number';input.inputMode='decimal';input.step=String(step);input.min='0';
    input.value=object[key]??'';
    if(placeholder!==undefined)input.placeholder=String(placeholder);
    input.addEventListener('input',()=>{
      object[key]=input.value===''?null:Number(input.value);
      changed();schedulePreview();
    });
    field.append(input);return field;
  }

  const dimensions=fieldset('Dimensiones del pilote · cm');
  dimensions.grid.append(
    numeric('Diámetro del pilote',state.geometry,'diameter_cm',1),
    numeric('Largo bajo la zapata',state.geometry,'length_cm',10),
    numeric('Espesor de la zapata',state.geometry,'footing_height_cm',1),
    numeric('Penetración en la zapata',state,'confinement_cm',1),
  );
  dimensions.fieldset.append(node('p','La penetración se mide hacia arriba desde la cara inferior de la zapata y se suma al largo del pilote.','muted'));

  const covers=fieldset('Recubrimientos del pilote · cm');
  covers.grid.append(numeric('Recubrimiento lateral del pilote',state.cover,'lateral_cm',.5,'Ej.: 5'),numeric('Recubrimiento inferior del pilote',state.cover,'inferior_cm',.5,'Ej.: 7,5'));

  const longitudinals=fieldset('Fierros longitudinales');
  longitudinals.grid.append(
    numeric('Diámetro longitudinal · mm',state.longitudinal,'diameter_mm',1,'Ej.: 22'),
    numeric('Separación entre ejes sobre la circunferencia · cm',state.longitudinal,'spacing_cm',1),
    numeric('Gancho inferior · tramo recto · cm',state.longitudinal,'hook_cm',1,'Ej.: 40'),
  );
  longitudinals.fieldset.append(node('p','Pieza inferior con gancho de 90° y largo desarrollado máximo de 12 m. Radio de doblez: 3 × Ø. Los empalmes alternados se indicarán en la cota de traslapo.','muted'));

  const ties=fieldset('Estribos circulares');
  ties.grid.append(
    numeric('Diámetro del estribo circular · mm',state.ties,'diameter_mm',1,'Ej.: 12'),
    numeric('Gancho de 90° · tramo recto · cm',state.ties,'hook_90_cm',1,'Ej.: 15'),
    numeric('Gancho de 45° · tramo recto · cm',state.ties,'hook_45_cm',1,'Ej.: 25'),
    numeric('Longitud adicional a la vuelta · cm',state.ties,'overrun_cm',1,'Ej.: 20 o 30'),
  );
  ties.fieldset.append(node('p','Cierre con un gancho de 90° y otro de 45° hacia adentro. Los largos iniciales de gancho son editables. Radio de doblez: 3 × Ø. La geometría del cierre todavía no se representa en esta vista previa.','muted'));

  const ranges=node('fieldset');ranges.append(node('legend','Rangos de separación · cm'));
  ranges.append(node('p','Todas las alturas se miden desde el fondo de hormigón del pilote hacia arriba: 0 = fondo. La unión con la zapata está a la altura indicada por el largo del pilote. Dentro de la zapata, las alturas son mayores que ese largo.','muted'));
  ranges.append(node('p','El primer estribo circular coincide con el inicio del doblez del longitudinal inferior. El inicio del tramo inferior se calcula a partir del recubrimiento inferior, el diámetro del longitudinal y su radio de doblez.','muted'));
  for(const definition of ZONES){
    const zone=state.zones.find(item=>item.key===definition.key);
    const row=node('div',undefined,'rule-row'),grid=node('div',undefined,'fields');
    const title=node('h4',definition.label);title.style.borderLeft=`4px solid ${definition.color}`;title.style.paddingLeft='.5rem';
    row.append(title,grid);
    for(const [label,key] of [['Desde','from_cm'],['Hasta','to_cm'],['Separación','spacing_cm']]){
      const field=numeric(label,zone,key,1);
      const input=field.querySelector('input');
      input.setAttribute('aria-label',`${definition.label}: ${label.toLowerCase()}`);
      if(definition.key==='lower'&&key==='from_cm'){
        firstStartInput=input;input.readOnly=true;input.placeholder='Automático';
        input.title='Altura calculada del inicio del doblez del longitudinal';
      }
      grid.append(field);
    }
    ranges.append(row);
  }
  root.append(ranges);
  // Keep range editing beside its drawing where there is room, and immediately
  // below it in a narrow inspector; unrelated reinforcement controls follow.
  const rangeEditor=node('div');rangeEditor.style.display='grid';
  rangeEditor.style.gridTemplateColumns='repeat(auto-fit,minmax(min(100%,270px),1fr))';
  rangeEditor.style.gap='16px';drawing.style.minWidth='0';ranges.style.minWidth='0';
  for(const grid of ranges.querySelectorAll('.fields'))grid.style.gridTemplateColumns='repeat(3,minmax(0,1fr))';
  for(const input of ranges.querySelectorAll('input'))input.style.minWidth='0';
  rangeEditor.append(drawing,ranges);root.insertBefore(rangeEditor,covers.fieldset);
  root.insertBefore(messages,covers.fieldset);

  function draw(response){
    drawing.replaceChildren();
    const geometry=state.geometry,length=geometry.length_cm,diameter=geometry.diameter_cm;
    if(!positive(length)||!positive(diameter)){
      drawing.append(node('p','Completa el diámetro y el largo del pilote para ver su elevación.','muted'));return;
    }
    const footingHeight=positive(geometry.footing_height_cm)?geometry.footing_height_cm:0;
    const confinement=finite(state.confinement_cm)&&state.confinement_cm>=0?state.confinement_cm:0;
    const total=length+Math.max(footingHeight,confinement),scale=370/total;
    const y=value=>410-value*scale,center=180,width=Math.max(36,Math.min(150,diameter*scale));
    const left=center-width/2,right=center+width/2;
    const svg=svgNode('svg',{viewBox:'0 0 360 455',role:'img','aria-label':'Elevación del pilote con penetración en la zapata y rangos de separación'});
    svg.style.width='100%';svg.style.maxHeight='460px';svg.style.display='block';svg.style.margin='0 auto';
    svg.append(svgNode('title',{},'Rangos de separación del pilote'));
    if(footingHeight>0)svg.append(svgNode('rect',{x:left-45,y:y(length+footingHeight),width:width+90,height:footingHeight*scale,fill:'currentColor','fill-opacity':'.06',stroke:'currentColor','stroke-width':1.5}));
    svg.append(svgNode('rect',{x:left,y:y(length),width,height:length*scale,fill:'currentColor','fill-opacity':'.025',stroke:'currentColor','stroke-width':1.5}));
    if(confinement>0)svg.append(svgNode('rect',{x:left,y:y(length+confinement),width,height:confinement*scale,fill:'#55b99a','fill-opacity':'.2',stroke:'#55b99a','stroke-dasharray':'5 3','stroke-width':1.5}));
    const zones=Array.isArray(response?.zones)?response.zones:[];
    for(const definition of ZONES){
      const zone=zones.find(item=>item.key===definition.key);
      if(!zone||!finite(zone.from_cm)||!finite(zone.to_cm)||zone.to_cm<=zone.from_cm)continue;
      svg.append(svgNode('rect',{x:left,y:y(zone.to_cm),width,height:(zone.to_cm-zone.from_cm)*scale,fill:definition.color,'fill-opacity':'.22'}));
      svg.append(svgNode('path',{d:`M ${right+8} ${y(zone.to_cm)} h 9 V ${y(zone.from_cm)} h -9`,fill:'none',stroke:definition.color,'stroke-width':3}));
    }
    const firstTie=response?.first_tie_height_cm;
    if(finite(firstTie))svg.append(svgNode('line',{x1:left-6,y1:y(firstTie),x2:right+6,y2:y(firstTie),stroke:'#ef8575','stroke-width':3,'data-first-tie-height-cm':firstTie}));
    svg.append(svgNode('line',{x1:15,y1:y(length),x2:345,y2:y(length),stroke:'currentColor','stroke-opacity':'.6','stroke-dasharray':'5 4'}));
    svg.append(svgNode('text',{x:15,y:23,fill:'currentColor','font-size':14},`Unión con zapata: ${format(length)} cm`));
    svg.append(svgNode('text',{x:center,y:435,fill:'currentColor','font-size':14,'text-anchor':'middle'},'Fondo del pilote: 0 cm'));
    drawing.append(svg,node('p','Esquema de elevación: alturas proporcionales; ancho ampliado para leer los rangos.','muted'));
    if(finite(firstTie))drawing.append(node('p',`Primer estribo circular: ${format(firstTie)} cm desde el fondo, al inicio del doblez del longitudinal.`,'muted'));
    if(finite(state.confinement_cm))drawing.append(node('p',`Penetración en zapata: ${format(state.confinement_cm)} cm · altura superior: ${format(length+state.confinement_cm)} cm.`,'muted'));
    for(const definition of ZONES){
      const zone=zones.find(item=>item.key===definition.key);
      if(!zone)continue;
      const line=node('p',`${definition.label}: ${format(zone.from_cm)}–${format(zone.to_cm)} cm · separación ${format(zone.spacing_cm)} cm.`);
      line.style.borderLeft=`4px solid ${definition.color}`;line.style.paddingLeft='.5rem';drawing.append(line);
    }
  }

  function schedulePreview(){
    const generation=++revision;clearTimeout(timer);firstStartInput.value='';draw(null);
    messages.replaceChildren(node('p','Actualizando rangos…','muted'));
    timer=setTimeout(()=>refresh(generation),200);
  }

  async function refresh(generation){
    if(!alive()||generation!==revision)return;
    try{
      const response=await api('rebar/pile/preview',{state:structuredClone(state)});
      if(!alive()||generation!==revision)return;
      const firstTie=finite(response.first_tie_height_cm)?response.first_tie_height_cm:null;
      firstStartInput.value=firstTie===null?'':String(Number(firstTie.toFixed(6)));
      const lower=state.zones.find(zone=>zone.key==='lower');
      if(lower.from_cm!==firstTie){lower.from_cm=firstTie;changed();}
      draw(response);messages.replaceChildren();
      const issues=Array.isArray(response.issues)?response.issues:[];
      const missing=issues.filter(issue=>issue.message.startsWith('Completa '));
      for(const issue of issues.filter(issue=>!missing.includes(issue)))messages.append(node('p',issue.message,'muted'));
      if(missing.length){
        const details=node('details');details.append(node('summary',`${missing.length} campos pendientes de completar`));
        for(const issue of missing)details.append(node('p',issue.message,'muted'));
        messages.append(details);
      }
      if(response.valid)messages.append(node('p','Rangos válidos para esta vista previa. El cálculo y el despiece siguen pendientes.','muted'));
    }catch(error){
      if(alive()&&generation===revision)messages.replaceChildren(node('p',error.message,'badge'));
    }
  }

  schedulePreview();
}
