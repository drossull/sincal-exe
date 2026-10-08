import {destination as pageDestination} from '/navigation.js';
export async function renderRevisionEditor(ctx){
  const {api,node,button,section,job,current,notify}=ctx;
  const intro=section('revision-editor','Editor de revisiones');
  intro.append(node('p','Selecciona DWG o carpetas incorporados en Proyecto. Solo se editan tablas de revisiones dentro de bloques con prefijo VIÑETA. Los archivos no se suben a Internet.'));
  intro.append(node('p','La primera fila conserva sus Fields: sus valores vinculados se cambian mediante DWGPROPS. Las demás celdas de texto se editan directamente, sin desplazar el historial. Las propiedades son comunes a todo el DWG, incluidos otros textos vinculados.'));
  const engineLabel=node('label','Motor AutoCAD'),engine=node('select');engine.setAttribute('aria-label','Motor del editor de revisiones');engineLabel.append(engine);intro.append(engineLabel);
  const list=section('editor-files','Archivos'),bulk=section('editor-common','Tabla común de revisiones'),editor=section('editor-table','Detalle por archivo'),preview=section('editor-preview','Cambios pendientes'),results=section('editor-results','Resultados');
  const labels=['Revisión','Fecha','Dibujante','Revisor','Aprobador','Descripción'];
  let files=[],snapshot=null,active=null,busy=false;
  const drafts=new Map(),selectedFiles=new Set(),lifecycle=new AbortController();
  let searchText='';
  const dirty=()=>[...drafts.values()].some(m=>m.size);
  const discard=()=>!dirty()||confirm('Hay cambios sin guardar. ¿Descartarlos?');
  document.addEventListener('click',e=>{
    const dest=e.target.closest('[data-page]');if(!dest)return;
    if(pageDestination(dest.dataset.page)==='revision-editor'){e.preventDefault();e.stopImmediatePropagation();return;}
    if(busy||!discard()){e.preventDefault();e.stopImmediatePropagation();if(busy)notify('Espera o cancela el procesamiento entre archivos.');}
  },{capture:true,signal:lifecycle.signal});
  window.addEventListener('beforeunload',e=>{if(busy||dirty()){e.preventDefault();e.returnValue='';}},{signal:lifecycle.signal});
  const observer=new MutationObserver(()=>{if(!intro.isConnected){lifecycle.abort();observer.disconnect();}});observer.observe(document.querySelector('#main'),{childList:true});
  const cellKey=(t,r,c)=>JSON.stringify([t,r,c]);
  function change(file,table,r,c,value,refresh=true){
    const draft=drafts.get(file.id),cell=table.cells[r][c];
    // Reflect a shared DWG property in every linked cell; never send conflicting patches.
    for(const t of file.editor.tables)t.cells.forEach((row,ri)=>row.forEach((other,ci)=>{
      if((t.id===table.id&&r===ri&&c===ci)||(cell.property&&other.property?.toLowerCase()===cell.property.toLowerCase())){
        const key=cellKey(t.id,ri,ci);
        if(value===other.text)draft.delete(key);else draft.set(key,{table:t.id,row:ri,column:ci,value});
      }
    }));
    if(file.id===active)editor.querySelectorAll('input[data-cell]').forEach(input=>{
      const [id,ri,ci]=JSON.parse(input.dataset.cell),t=file.editor.tables.find(t=>t.id===id);
      if(input!==document.activeElement)input.value=draft.get(input.dataset.cell)?.value??t.cells[ri][ci].text;
    });if(refresh)drawPreview();
  }
  function valueOf(file,table,r,c){return drafts.get(file.id).get(cellKey(table.id,r,c))?.value??table.cells[r][c].text;}
  function drawBulk(){
    bulk.replaceChildren(node('h2','Tabla común de revisiones'));
    const chosen=files.filter(f=>selectedFiles.has(f.id));
    bulk.append(node('p',`${chosen.length} archivos seleccionados. Edita aquí la tabla completa, incluido el historial, o usa una tabla existente como base. Solo se preparan cambios: revisa las excepciones por archivo antes de guardar.`));
    if(!chosen.length){bulk.append(node('p','Marca las casillas de los archivos que quieras editar juntos.'));return;}
    const targets=chosen.flatMap(file=>file.editor.tables.map(table=>({file,table})));
    const base=targets[0]?.table;
    if(!base||targets.some(({table})=>table.cells.length!==base.cells.length||table.cells.some((row,r)=>row.length!==base.cells[r].length))){bulk.append(node('p','Las tablas seleccionadas tienen distinta cantidad de filas o columnas. Selecciona un grupo con el mismo formato; no se agregarán ni eliminarán filas.'));return;}
    const sourceLabel=node('label','Tabla que se usará como base'),source=node('select');source.setAttribute('aria-label','Tabla base');
    const sources=files.filter(f=>f.id).flatMap(file=>file.editor.tables.map(table=>({file,table})));
    sources.forEach(({file,table},i)=>{const option=node('option',`${file.name} · ${table.block}`);option.value=String(i);source.append(option);});sourceLabel.append(source);source.disabled=busy;bulk.append(sourceLabel);
    const copy=button('Aplicar tabla base a seleccionados',()=>{
      const original=sources[Number(source.value)];if(!original)return;
      const values=original.table.cells.map((row,r)=>row.map((_,c)=>valueOf(original.file,original.table,r,c)));
      const plan=[],properties=new Map();
      for(const {file,table}of targets){
        if(table.cells.length!==values.length||table.cells.some((row,r)=>row.length!==values[r].length))throw Error('La tabla base tiene otro tamaño. No se preparó ningún cambio.');
        table.cells.forEach((row,r)=>row.forEach((cell,c)=>{
          const value=values[r][c];
          if(!cell.editable&&value!==valueOf(file,table,r,c))throw Error(`${file.name}: fila ${r+1}, ${labels[c]} está protegida y tiene otro valor. No se preparó ningún cambio.`);
          if(cell.property){const key=JSON.stringify([file.id,cell.property.toLowerCase()]);if(properties.has(key)&&properties.get(key)!==value)throw Error(`${file.name}: la tabla base asignaría valores diferentes a una misma propiedad. No se preparó ningún cambio.`);properties.set(key,value);}
          if(cell.editable)plan.push({file,table,r,c,value});
        }));
      }
      if(!confirm(`¿Preparar la misma tabla completa de ${original.file.name} en ${chosen.length} DWG seleccionados, incluido todo el historial? Se reemplazarán sus borradores de esas celdas. Los Fields y el formato de destino se conservan. Aún no se guardarán archivos.`))return;
      for(const p of plan)change(p.file,p.table,p.r,p.c,p.value,false);draw();notify('Tabla común preparada. Ajusta las excepciones con Ver / editar y revisa el resumen antes de guardar.');
    });copy.disabled=busy;bulk.append(copy);
    const wrap=node('div',undefined,'table-wrap revision-table'),t=node('table'),head=node('tr');labels.forEach(label=>head.append(node('th',label)));t.append(head);
    base.cells.forEach((row,r)=>{const tr=node('tr');labels.forEach((label,c)=>{
      const cells=targets.map(({file,table})=>({file,table,cell:table.cells[r]?.[c]}));
      const editable=cells.length&&cells.every(({cell})=>cell?.editable);
      const values=cells.map(({file,table,cell})=>cell?valueOf(file,table,r,c):'');
      const same=values.every(v=>v===values[0]);const group=node('td'),input=node('input');
      input.setAttribute('aria-label',r===0?'Común: '+label:`Común fila ${r+1}: ${label}`);input.maxLength=250;input.value=same?(values[0]??''):'';input.placeholder=same?'':'Valores distintos';input.disabled=busy||!editable;
      group.append(input);if(!editable)group.append(node('small','Campo protegido o ausente en algún archivo.'));
      input.addEventListener('input',()=>{for(const {file,table}of cells)change(file,table,r,c,input.value,false);drawPreview();});tr.append(group);
    });t.append(tr);});wrap.append(t);bulk.append(wrap,node('p','Las celdas con valores distintos no cambian hasta que escribas o apliques una tabla base. Después ajusta las excepciones con “Ver / editar”. Guardar incluye todos los cambios pendientes, aunque desmarques un archivo.','muted'));
  }
  function drawList(){
    list.replaceChildren(node('h2','Archivos'));
    const search=node('input');search.type='search';search.placeholder='Buscar archivo';search.setAttribute('aria-label','Buscar archivo de revisión');search.value=searchText;
    const actions=node('div',undefined,'actions'),rows=node('div',undefined,'revision-file-list'),count=node('p');
    const visible=()=>files.filter(f=>f.name.toLocaleLowerCase().includes(searchText.toLocaleLowerCase()));
    const all=button('Seleccionar visibles',()=>{visible().filter(f=>f.id).forEach(f=>selectedFiles.add(f.id));renderRows();drawBulk();});
    const none=button('Quitar selección',()=>{selectedFiles.clear();renderRows();drawBulk();});all.disabled=none.disabled=busy;search.disabled=busy;actions.append(all,none);list.append(search,actions,count,rows);
    function renderRows(){
      count.textContent=`${selectedFiles.size} seleccionados · ${files.filter(f=>f.id).length} compatibles · ${files.length} archivos`;
      rows.replaceChildren();for(const f of visible()){
        const row=node('div',undefined,'revision-file-row'),label=node('label'),check=node('input');check.type='checkbox';check.checked=selectedFiles.has(f.id);check.disabled=busy||!f.id;check.setAttribute('aria-label','Seleccionar '+f.name);
        check.addEventListener('change',()=>{if(check.checked)selectedFiles.add(f.id);else selectedFiles.delete(f.id);count.textContent=`${selectedFiles.size} seleccionados · ${files.filter(f=>f.id).length} compatibles · ${files.length} archivos`;drawBulk();});
        label.append(check,node('span',f.name));row.append(label);
        if(f.id){const view=button('Ver / editar',()=>{active=f.id;draw();editor.scrollIntoView({block:'start'});});view.setAttribute('aria-label','Ver / editar '+f.name);view.setAttribute('aria-pressed',String(active===f.id));view.disabled=busy;row.append(view);}else row.append(node('small',f.error||'No compatible'));
        rows.append(row);
      }if(!visible().length)rows.append(node('p','No hay archivos que coincidan.'));
    }search.addEventListener('input',()=>{searchText=search.value;renderRows();});renderRows();
  }
  function drawPreview(){
    preview.replaceChildren(node('h2','Cambios pendientes'));
    for(const file of files){const changes=drafts.get(file.id);if(!changes?.size)continue;
      const detail=node('details');detail.open=true;detail.append(node('summary',`${file.name} · ${changes.size} celdas`));
      for(const edit of changes.values()){
        const t=file.editor.tables.find(t=>t.id===edit.table),old=t.cells[edit.row][edit.column];
        detail.append(node('p',`${t.block} · fila ${edit.row+1} · ${labels[edit.column]}: «${old.text}» → «${edit.value}»${old.property?' · DWGPROPS: '+old.property:''}`));
      }preview.append(detail);
    }
    if(!dirty())preview.append(node('p','No hay cambios pendientes.'));
    const save=button('Guardar cambios con respaldo',saveChanges,true);save.disabled=busy||!dirty();preview.append(save);
  }
  function draw(){
    engine.disabled=busy;loadFiles.disabled=busy;loadFolder.disabled=busy;
    drawList();drawBulk();
    editor.replaceChildren(node('h2','Detalle por archivo'));
    const file=files.find(f=>f.id===active);
    if(!file){editor.append(node('p','Selecciona un archivo compatible para editar su tabla.'));drawPreview();return;}
    editor.append(node('h3',file.name),node('p',file.path, 'revision-file-path'));
    for(const table of file.editor.tables){
      editor.append(node('h3',table.block),node('p','Instancias afectadas: '+table.locations.join(' · ')));
      const wrap=node('div',undefined,'table-wrap revision-table'),t=node('table'),head=node('tr');labels.forEach(l=>head.append(node('th',l)));t.append(head);
      table.cells.forEach((row,r)=>{const tr=node('tr');row.forEach((cell,c)=>{
        const td=node('td'),input=node('input'),key=cellKey(table.id,r,c);input.dataset.cell=key;
        input.value=drafts.get(file.id).get(key)?.value??cell.text;input.maxLength=250;input.disabled=busy||!cell.editable;
        input.setAttribute('aria-label',`${table.block} fila ${r+1} ${labels[c]}`);
        input.addEventListener('input',()=>{change(file,table,r,c,input.value);drawBulk();});td.append(input);
        if(cell.field)td.append(node('small',cell.property?'DWGPROPS: '+cell.property:'FIELD protegido'));
        tr.append(td);
      });t.append(tr);});wrap.append(t);editor.append(wrap);
    }
    const reset=button('Descartar cambios de este DWG',()=>{if(confirm('¿Descartar los cambios de este DWG?')){drafts.set(file.id,new Map());draw();}});reset.disabled=busy;editor.append(reset);drawPreview();
  }
  async function saveChanges(){
    if(busy||!dirty())return;
    const selected=files.filter(f=>drafts.get(f.id)?.size);
    if(!confirm(`Guardar los cambios mostrados en ${selected.length} DWG:\n${selected.map(f=>f.path).join('\n')}\n\nSe reemplaza cada original tras verificar su copia, con respaldo en SINCAL_Backups. No se desplaza el historial. Las propiedades afectan a todos sus Fields vinculados. ¿Continuar?`))return;
    busy=true;draw();
    try{
      const data=await job('revision-editor-write',{snapshot,files:selected.map(f=>({id:f.id,changes:[...drafts.get(f.id).values()]})),confirm:true});if(!current())return;
      results.replaceChildren(node('h2','Resultados'));
      for(const row of data.files){results.append(node('p',`${row.name}: ${row.status}${row.error?' · '+row.error:' · Respaldo: '+row.backup}`));
        if(row.editor){files.find(f=>f.id===row.id).editor=row.editor;drafts.set(row.id,new Map());}
      }
      if(data.cancelled)results.append(node('p','Cancelado entre archivos. Los cambios no guardados siguen pendientes.'));
    }finally{busy=false;if(current())draw();}
  }
  async function load(kind){
    if(busy||!discard())return;if(!engine.value)throw Error('No hay un motor AutoCAD compatible.');
    const picked=await api('files/choose',{kind});if(!picked.length||!current())return;
    busy=true;files=[];active=null;drafts.clear();selectedFiles.clear();searchText='';results.replaceChildren(node('h2','Resultados'));draw();
    try{
      const data=await job('revision-editor-read',{engine:engine.value,...(kind==='folder'?{folder:picked[0].id}:{files:picked.map(f=>f.id)})});if(!current())return;
      files=data.files;snapshot=data.snapshot;for(const f of files)if(f.id)drafts.set(f.id,new Map());active=files.find(f=>f.id)?.id;
      if(data.cancelled)notify('Lectura cancelada; se muestran los archivos ya leídos.');
    }finally{busy=false;if(current())draw();}
  }
  const loadFiles=button('Seleccionar DWG',()=>load('dwg')),loadFolder=button('Seleccionar carpeta',()=>load('folder'));intro.append(loadFiles,loadFolder);draw();
  const engines=await api('dwgprops/engines');if(!current())return;
  for(const e of engines){const option=node('option',e.name);option.value=e.id;engine.append(option);}
}
