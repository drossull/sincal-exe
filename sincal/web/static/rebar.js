// UI only: all quantities and geometry are calculated by the Python domain model.
export async function renderRebar(ctx){
  const {project,api,node,button,section,notify,job,changed,current}=ctx;
  const intro=section('armaduras','Generador de armadura');
  ctx.projectLoader(intro);
  if(!project){intro.append(node('p','Carga aquí el JSON del proyecto para configurar sus armaduras. También estará disponible en Consulta.'));return;}
  intro.append(node('p',project.identification.structure_name||'Proyecto sin nombre'));
  intro.append(node('p','Las dimensiones disponibles vienen del JSON (mm → cm). Completa las ausentes y revisa el cálculo antes de dibujar. El programa documenta armaduras; no sustituye la revisión del ingeniero.','muted'));
  const defaults=await api('rebar/from-project',project.data);if(!current())return;
  project.rebar??={};let selected='entrada',revision=0;
  const controls=node('div',undefined,'actions');intro.append(controls);
  const body=node('div');intro.append(body);
  for(const [key,label] of [['entrada','Estribo de entrada'],['salida','Estribo de salida']]){
    controls.append(button(label,()=>{selected=key;draw();}));
  }
  function draw(){
    revision++;body.replaceChildren();
    if(!project.rebar[selected])project.rebar[selected]=structuredClone(defaults[selected]);
    const state=project.rebar[selected];
    body.append(node('h3',selected==='entrada'?'Estribo de entrada':'Estribo de salida'));
    const output=node('div');
    function invalidate(){revision++;changed();output.replaceChildren(node('p','Parámetros modificados. Pulsa Calcular marcas para actualizar.','muted'));}
    function numeric(label,obj,key,step){
      const field=node('label',label),input=node('input');input.type=key==='esviaje_grados'?'text':'number';input.inputMode='decimal';input.step=String(step);input.value=obj[key];
      input.addEventListener('input',()=>{obj[key]=input.value===''?null:Number(input.value);invalidate();});field.append(input);return field;
    }
    const dimensions=node('fieldset');dimensions.append(node('legend','1. Dimensiones y recubrimientos · cm'));
    const grid=node('div',undefined,'fields');
    for(const [key,label,step] of [['largo_cm','Largo',100],['ancho_cm','Ancho',100],['alto_cm','Alto',50],['esviaje_grados','Esviaje · grados',1]])grid.append(numeric(label,state.geometry,key,step));
    for(const [key,label] of [['inferior_cm','Recubrimiento inferior'],['superior_cm','Recubrimiento superior'],['lateral_cm','Recubrimiento lateral']])grid.append(numeric(label,state.cover,key,.5));
    dimensions.append(grid);body.append(dimensions);
    const rules=node('fieldset');rules.append(node('legend','2. Parámetros de armadura'));
    rules.append(node('p','Gancho 0 = automático. Los cambios solo afectan al estribo seleccionado.','muted'));
    for(const rule of state.rules){
      const card=node('div',undefined,'rule-row');card.append(node('h3',rule.label));
      const inputs=node('div',undefined,'fields');
      const markLabel=node('label','Marca base'),markInput=node('input');markInput.value=rule.mark;markInput.maxLength=32;markInput.addEventListener('input',()=>{rule.mark=markInput.value;invalidate();});markLabel.append(markInput);inputs.append(markLabel);
      const diameter=node('label','Diámetro · mm'),select=node('select');
      for(const value of [12,16,18,22,25,28,32,36]){const option=node('option',String(value));option.value=value;select.append(option);}select.value=rule.diameter_mm;
      select.addEventListener('change',()=>{rule.diameter_mm=Number(select.value);invalidate();});diameter.append(select);
      inputs.append(diameter,numeric('Separación · cm',rule,'spacing_cm',1),numeric('Gancho · cm',rule,'hook_cm',10));
      const origin=node('label','Origen'),originSelect=node('select');
      for(const [value,label]of [['inicio','Inicio'],['final','Final']]){const option=node('option',label);option.value=value;originSelect.append(option);}originSelect.value=rule.origin;
      originSelect.addEventListener('change',()=>{rule.origin=originSelect.value;invalidate();});origin.append(originSelect);
      const enabled=node('label','Activo'),check=node('input');check.type='checkbox';check.checked=rule.enabled;check.addEventListener('change',()=>{rule.enabled=check.checked;invalidate();});enabled.append(check);inputs.append(origin,enabled);card.append(inputs);rules.append(card);
    }
    body.append(rules,button('Calcular marcas',async()=>{
      const generation=++revision;const response=await api('rebar/preview',state);
      if(generation!==revision||!current())return;
      output.replaceChildren();
      for(const issue of response.issues)output.append(node('p',issue.message,'badge'));
      if(!response.valid){output.append(node('p','Corrige los parámetros antes de obtener un detalle.'));return;}
      output.append(node('h3',`3. Marcas · ${response.total_kg.toFixed(1)} kg provisionales`));
      const wrap=node('div',undefined,'table-wrap'),table=node('table');
      const head=node('tr');for(const label of ['Marca','Parte','Ubicación','Cantidad','Ø mm','@ cm','L unit. cm','L total cm','Área cm²','kg','Vistas','Rol'])head.append(node('th',label));const thead=node('thead');thead.append(head);table.append(thead);const tbody=node('tbody');
      for(const mark of response.marks){const row=node('tr'),cell=node('td');cell.append(button(mark.mark,()=>detail(response.details.find(d=>d.mark===mark.mark),mark)));row.append(cell);for(const value of [mark.element,mark.location,mark.quantity,mark.diameter_mm,mark.spacing_cm,mark.unit_length_cm,mark.total_length_cm,mark.area_cm2.toFixed(3),mark.kg.toFixed(1),mark.views.join(', '),mark.piece_role])row.append(node('td',String(value)));tbody.append(row);}table.append(tbody);wrap.append(table);output.append(wrap,node('p','Pulsa una marca para ver el fierro y sus medidas.','muted'));
      output.append(button('Ampliar tabla de marcas',()=>{const dialog=node('dialog'),copy=table.cloneNode(true),container=node('div',undefined,'table-wrap');dialog.append(node('h2','Marcas · '+selected));copy.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{const mark=response.marks.find(m=>m.mark===b.textContent);detail(response.details.find(d=>d.mark===mark.mark),mark);}));container.append(copy);dialog.append(container,button('Cerrar tabla',()=>dialog.close()));dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();}));
    },true),output);
    const cad=node('fieldset');cad.append(node('legend','4. Dibujo CAD · ZAPATA'));
    cad.append(node('p','1. Abre Model en metros. 2. Detecta moldajes. 3. Elige el contorno de cada vista. 4. Genera y revisa en CAD. Para el despiece, selecciona allí el punto de inserción.'));
    const candidates=node('div');let detection=null;const selections={};
    cad.append(button('Detectar moldajes',async()=>{const expected=await api('cad/status');if(expected.status!=='ready')throw Error(expected.message);if(!confirm(`Leer moldajes de ${expected.active.name}?`))return;detection=await job('cad-detect',{expected});candidates.replaceChildren();
      for(const view of ['FR','AA','BB','CC','EE']){const label=node('label',view==='FR'?'Frontal':view[0]+'–'+view[1]),select=node('select');const empty=node('option','Selecciona un contorno');empty.value='';select.append(empty);for(const item of detection.candidates.filter(c=>c.layer===view+'_ZAP'&&c.status==='OK')){const option=node('option',`${item.handle} · ${item.vertex_count} vértices · ${item.area_m2.toFixed(2)} m²`);option.value=item.handle;select.append(option);}label.append(select);selections[view]=select;
        label.append(button('Dibujar '+view,async()=>{if(!select.value)throw Error('Selecciona un contorno.');if(!confirm(`¿Generar vista ${view} en el contorno ${select.value}?`))return;await job('cad-rebar',{state,abutment:selected,view,handle:select.value,detection:detection.detection});notify('Orden terminada. Comprueba geometría, marcas y cotas en CAD.');}));candidates.append(label);}
    }),candidates,button('Generar despiece general',async()=>{const expected=await api('cad/status');if(expected.status!=='ready')throw Error(expected.message);if(confirm(`¿Generar despiece de ${selected} en ${expected.active.name}? Selecciona el punto en CAD.`))await job('cad-rebar',{state,abutment:selected,view:'detail',expected});},true));
    cad.append(node('p','D–D, muros y alas no tienen generador de zapata. No se inventa armadura para componentes todavía no definidos.','muted'));body.append(cad);
  }
  function detail(piece,mark){
    if(!piece){notify('No existe geometría para esta marca.');return;}
    const dialog=node('dialog');dialog.append(node('h2',`Marca ${piece.mark} · ${mark.element}`));
    const points=piece.points_m, xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
    const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
    const scale=Math.min(620/Math.max(maxX-minX,.01),260/Math.max(maxY-minY,.01));
    const convert=p=>[80+(p[0]-minX)*scale,80+(maxY-p[1])*scale];
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 800 440');svg.setAttribute('role','img');svg.setAttribute('aria-label',`Fierro ${piece.mark}. Parciales ${piece.partials_cm.join(', ')} cm; longitud total ${piece.total_cm} cm.`);
    const line=document.createElementNS(svg.namespaceURI,'polyline');line.setAttribute('points',points.map(p=>convert(p).join(',')).join(' '));line.setAttribute('class','rebar-line');svg.append(line);
    piece.partial_segments_m.forEach((segment,index)=>{const a=convert(segment[0]),b=convert(segment[1]);const text=document.createElementNS(svg.namespaceURI,'text');text.setAttribute('x',(a[0]+b[0])/2+12);text.setAttribute('y',(a[1]+b[1])/2-16);text.textContent=`${piece.partials_cm[index]} cm`;svg.append(text);});
    dialog.append(svg,node('p',`Parciales desarrolladas: ${piece.partials_cm.join(' + ')} = ${piece.total_cm} cm`),node('p',`${piece.quantity} Ø${piece.diameter_mm} @${piece.spacing_cm} · Radio ${mark.bend_radius_cm} cm · Longitud por eje ${piece.measured_cm.toFixed(2)} cm`));
    dialog.append(node('p','Geometría del núcleo Python; etiquetas de parciales desarrolladas, no cotas CAD.','muted'),button('Cerrar',()=>dialog.close()));dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.tabIndex=-1;dialog.showModal();dialog.scrollTop=0;dialog.focus({preventScroll:true});
  }
  draw();
  const trav=section('travesanos','TRAVESAÑOS');
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
