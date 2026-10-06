export async function renderRevisions(ctx){
  const {api,node,button,section,job,current,notify}=ctx;
  const intro=section('revisions','Nueva revisión de planos');
  intro.append(node('p','Selecciona DWG locales con un único layout y una viñeta dinámica compatible. No se suben a Internet. La nueva revisión queda arriba; el historial baja una fila y mantiene su tamaño.'));
  intro.append(node('p','Los Fields de la primera fila se conservan. La última fila deja de verse, pero queda en el respaldo completo SINCAL_Backups. No se renombra el archivo ni se modifica Fecha_Inf.'));
  const engineLabel=node('label','Motor AutoCAD'),engine=node('select');engine.setAttribute('aria-label','Motor de revisiones');engineLabel.append(engine);intro.append(engineLabel);
  const list=section('revision-files','Archivos'),editor=section('revision-input','Datos de la nueva revisión'),preview=section('revision-preview','Vista previa'),results=section('revision-results','Resultados');
  const labels=['Revisión','Fecha','Dibujante','Revisor','Aprobador','Descripción'];
  let files=[],snapshot=null,selected=new Set(),values=Array(6).fill(''),busy=false,dirty=false;
  const lifecycle=new AbortController();
  const discard=()=>!dirty||confirm('Hay datos de una nueva revisión sin aplicar. ¿Descartarlos?');
  document.querySelector('#sidebar').addEventListener('click',e=>{
    const dest=e.target.closest('[data-page]');if(!dest||dest.dataset.page==='revisions')return;
    if(busy||!discard()){e.preventDefault();e.stopImmediatePropagation();if(busy)notify('Espera o cancela el procesamiento entre archivos.');}
  },{capture:true,signal:lifecycle.signal});
  window.addEventListener('beforeunload',e=>{if(busy||dirty){e.preventDefault();e.returnValue='';}},{signal:lifecycle.signal});
  const observer=new MutationObserver(()=>{if(!intro.isConnected){lifecycle.abort();observer.disconnect();}});observer.observe(document.querySelector('#main'),{childList:true});
  const chosen=()=>files.filter(f=>selected.has(f.id));
  function table(parent,rows){const wrap=node('div',undefined,'table-wrap'),t=node('table'),head=node('tr');labels.forEach(s=>head.append(node('th',s)));t.append(head);for(const row of rows){const tr=node('tr');row.forEach(s=>tr.append(node('td',s)));t.append(tr);}wrap.append(t);parent.append(wrap);}
  function drawPreview(){
    preview.replaceChildren(node('h2','Vista previa'));
    for(const f of chosen()){
      const detail=node('details'),summary=node('summary',`${f.name} · layout ${f.revision.layout} · ${f.revision.rows.length} filas`);detail.append(summary);detail.open=chosen().length===1;
      detail.append(node('h3','Actual'));table(detail,f.revision.rows);
      detail.append(node('h3','Después de guardar'));
      table(detail,[values.map((v,c)=>v?(f.revision.fields[c]?.includes('%tc1')?v.toUpperCase():v):`[${labels[c]} pendiente]`),...f.revision.rows.slice(0,-1)]);
      detail.append(node('p','Fila que sale del cuadro y queda en el respaldo: '+f.revision.rows.at(-1).join(' · ')));preview.append(detail);
    }
  }
  function defaults(){
    const items=chosen();values=labels.map((_,c)=>c<2?'':items.length&&items.every(f=>f.revision.rows[0][c]===items[0].revision.rows[0][c])?items[0].revision.rows[0][c]:'');dirty=false;
  }
  function draw(){
    list.replaceChildren(node('h2','Archivos'),node('p',`${selected.size} seleccionados · ${files.length} archivos`));
    const all=button('Seleccionar todos los compatibles',()=>{if(busy||!discard())return;selected=new Set(files.filter(f=>f.id).map(f=>f.id));defaults();draw();});all.disabled=busy;list.append(all);
    for(const f of files){const label=node('label'),check=node('input');check.type='checkbox';check.checked=selected.has(f.id);check.disabled=busy||!f.id;check.setAttribute('aria-label','Seleccionar '+f.name);
      check.addEventListener('change',()=>{if(!discard()){check.checked=!check.checked;return;}if(check.checked)selected.add(f.id);else selected.delete(f.id);defaults();draw();});label.append(check,node('span',f.name+(f.error?' · '+f.error:'')));list.append(label);}
    editor.replaceChildren(node('h2','Datos de la nueva revisión'));
    if(!chosen().length){editor.append(node('p','Selecciona archivos compatibles para continuar.'));drawPreview();return;}
    editor.append(node('p','Escribe la revisión y la fecha. Los responsables y la descripción comunes se proponen como punto de partida. Comprueba y completa los seis campos.'));
    labels.forEach((title,c)=>{const label=node('label',title),input=node('input');input.value=values[c];input.maxLength=250;input.disabled=busy;input.setAttribute('aria-label','Nueva '+title);input.placeholder=c===1?'DD/MM/AA':'';input.addEventListener('input',()=>{values[c]=input.value;dirty=true;drawPreview();});label.append(input);editor.append(label);});
    const save=button('Crear revisión en seleccionados',async()=>{
      if(busy)return;
      const submitted=values.map(v=>v.trim());if(submitted.some(v=>!v))throw Error('Completa los seis datos.');
      if(chosen().some(f=>f.revision.rows[0][0].trim().toLocaleLowerCase()===submitted[0].toLocaleLowerCase()))throw Error('La revisión nueva ya es la actual en uno de los archivos seleccionados.');
      if(!confirm(`Crear revisión ${submitted[0]} en ${chosen().length} DWG:\n${chosen().map(f=>f.name).join('\n')}\n\n${labels.map((l,c)=>l+': '+submitted[c]).join('\n')}\n\nSe sobrescribirán los originales con respaldo. El historial baja y la última fila queda solo en el respaldo. ¿Continuar?`))return;
      busy=true;draw();try{
        const data=await job('revision-write',{snapshot,ids:[...selected],values:submitted,confirm:true});if(!current())return;
        results.replaceChildren(node('h2','Resultados'));
        const succeeded=new Set();
        for(const row of data.files){results.append(node('p',`${row.name}: ${row.status}${row.error?' · '+row.error:' · Respaldo: '+row.backup}`));if(row.revision){files.find(f=>f.id===row.id).revision=row.revision;succeeded.add(row.id);}}
        if(data.cancelled)results.append(node('p','Cancelado entre archivos. Los no procesados no se modificaron.'));
        selected=new Set([...selected].filter(id=>!succeeded.has(id)));dirty=selected.size>0;
      }finally{busy=false;if(current())draw();}
    },true);save.disabled=busy;editor.append(save);drawPreview();
  }
  const load=button('Seleccionar DWG y leer revisiones',async()=>{
    if(busy||!discard())return;if(!engine.value)throw Error('No hay un motor AutoCAD compatible.');
    const picked=await api('files/choose',{kind:'dwg'});if(!picked.length||!current())return;
    busy=true;dirty=false;files=picked.map(f=>({name:f.name,error:'Pendiente de lectura…'}));selected.clear();draw();
    try{const data=await job('revision-read',{files:picked.map(f=>f.id),engine:engine.value});if(!current())return;files=data.files;snapshot=data.snapshot;selected=new Set(files.filter(f=>f.id).map(f=>f.id));defaults();if(data.cancelled)notify('Lectura cancelada; se muestran los archivos ya leídos.');}
    finally{busy=false;if(current())draw();}
  });intro.append(load);draw();
  const engines=await api('dwgprops/engines');if(!current())return;for(const e of engines){const option=node('option',e.name);option.value=e.id;engine.append(option);}
}
