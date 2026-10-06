// A field is written only when explicitly included in the pending patch.
export async function renderDwgProps(ctx){
  const {api,node,button,section,job,current,notify}=ctx;
  const intro=section('dwgprops','Propiedades personalizadas DWGPROPS');
  intro.append(node('p','Editor local independiente con AutoCAD Core Console, sin abrir la interfaz de CAD. Se usan copias temporales. Cierra los DWG que quieras editar. No se recorren subcarpetas.'));
  const engineLabel=node('label','Motor para la próxima lectura'),engine=node('select');engine.setAttribute('aria-label','Motor DWGPROPS');engineLabel.append(engine);intro.append(engineLabel);
  intro.append(node('p','Se conserva lo que no edites. Antes de guardar se crea SINCAL_Backups junto a los planos. La cancelación se atiende entre archivos. Los campos FIELD se actualizarán según la configuración del dibujo al abrirlo o regenerarlo.'));
  intro.append(node('p','Cambiar la propiedad Revisión aquí no desplaza el historial de la viñeta. Para eso utiliza Nueva revisión en el menú.'));
  const folderText=node('p','Ninguna carpeta seleccionada');
  const list=section('archivos-prop','Archivos DWG'), editor=section('editor-prop','Editar selección'), results=section('resultados-prop','Resultados');
  let files=[],snapshot=null,selected=new Set(),pending={},busy=false;
  const search=node('input');search.type='search';search.placeholder='Buscar plano';search.setAttribute('aria-label','Buscar plano');
  const counter=node('p'),table=node('div',undefined,'table-wrap');list.append(search,counter,table);
  function dirty(){return Object.keys(pending).length>0;}
  function discard(){return !dirty()||confirm('Hay cambios sin aplicar. ¿Descartarlos para cambiar la selección?');}
  const lifecycle=new AbortController();
  document.querySelector('#sidebar').addEventListener('click',event=>{
    const destination=event.target.closest('[data-page]');
    if(!destination||destination.dataset.page==='dwgprops')return;
    if(busy||!discard()){event.preventDefault();event.stopImmediatePropagation();if(busy)notify('Espera a que termine la operación o cancélala entre archivos.');}
  },{capture:true,signal:lifecycle.signal});
  window.addEventListener('beforeunload',event=>{if(dirty()||busy){event.preventDefault();event.returnValue='';}},{signal:lifecycle.signal});
  const observer=new MutationObserver(()=>{if(!intro.isConnected){lifecycle.abort();observer.disconnect();}});
  observer.observe(document.querySelector('#main'),{childList:true});
  function drawList(){
    table.replaceChildren();counter.textContent=`${selected.size} seleccionados · ${files.length} archivos`;
    const t=node('table'),head=node('tr');['Seleccionar','Archivo','Propiedades / estado'].forEach(x=>head.append(node('th',x)));t.append(head);
    for(const file of files.filter(f=>f.name.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()))){
      const tr=node('tr'),cell=node('td'),check=node('input');check.type='checkbox';check.checked=selected.has(file.id);check.disabled=busy||!file.id;
      check.setAttribute('aria-label','Seleccionar '+file.name);
      check.addEventListener('change',()=>{if(!discard()){check.checked=!check.checked;return;}pending={};if(check.checked)selected.add(file.id);else selected.delete(file.id);drawList();drawEditor();});
      cell.append(check);tr.append(cell,node('td',file.name),node('td',file.error||String(Object.keys(file.properties).length)));t.append(tr);
    }table.append(t);
  }
  function drawEditor(){
    editor.replaceChildren(node('h2','Editar selección'));
    const chosen=files.filter(f=>selected.has(f.id));
    if(!chosen.length){editor.append(node('p','Selecciona uno o varios archivos.'));return;}
    editor.append(node('p',`${chosen.length} DWG. Marca “Cambiar” para aplicar un valor o “Eliminar” para quitar la propiedad. Los valores distintos no se reemplazan automáticamente.`));
    const keys=[...new Set([...chosen.flatMap(f=>Object.keys(f.properties)),...Object.keys(pending)])].sort((a,b)=>a.localeCompare(b,'es'));
    const t=node('table'),head=node('tr');['Cambiar','Propiedad','Valor','Eliminar'].forEach(x=>head.append(node('th',x)));t.append(head);
    for(const key of keys){
      const row=node('tr'),use=node('input'),value=node('input'),remove=node('input');use.type=remove.type='checkbox';
      const values=chosen.map(f=>Object.hasOwn(f.properties,key)?f.properties[key]:undefined),same=values.every(v=>v===values[0]);
      value.value=same?(values[0]??''):'';value.placeholder=same?'':'Valores distintos o propiedad ausente';value.maxLength=4096;
      if(Object.hasOwn(pending,key)){use.checked=true;remove.checked=pending[key]===null;value.value=pending[key]??'';}
      use.setAttribute('aria-label','Cambiar '+key);value.setAttribute('aria-label','Valor de '+key);remove.setAttribute('aria-label','Eliminar '+key);
      for(const input of [use,value,remove])input.disabled=busy;
      function capture(){if(use.checked)pending[key]=remove.checked?null:value.value;else delete pending[key];}
      use.addEventListener('change',capture);value.addEventListener('input',()=>{use.checked=true;remove.checked=false;capture();});remove.addEventListener('change',()=>{use.checked=true;capture();});
      for(const element of [use,node('span',key),value,remove]){const td=node('td');td.append(element);row.append(td);}t.append(row);
    }
    const wrap=node('div',undefined,'table-wrap');wrap.append(t);editor.append(wrap);
    const name=node('input'),value=node('input');name.placeholder='Nombre de propiedad nueva';value.placeholder='Valor';name.maxLength=255;value.maxLength=4096;
    name.setAttribute('aria-label','Nombre de propiedad nueva');value.setAttribute('aria-label','Valor de propiedad nueva');
    const added=node('p');
    const add=button('Añadir al cambio',()=>{const key=name.value.trim();if(!key)throw Error('Escribe un nombre.');if(keys.some(k=>k.toLocaleLowerCase()===key.toLocaleLowerCase()))throw Error('Edita esa propiedad en la tabla.');pending[key]=value.value;added.textContent='Nuevas: '+Object.keys(pending).filter(k=>!keys.includes(k)).join(', ');name.value='';value.value='';});
    const save=button('Guardar en seleccionados',async()=>{
      if(!dirty())throw Error('No hay cambios marcados.');
      const summary=Object.entries(pending).map(([k,v])=>`${k}: ${v===null?'ELIMINAR':JSON.stringify(v)}`).join('\n');
      if(!confirm(`Se modificarán ${chosen.length} DWG:\n${chosen.map(f=>f.name).join('\n')}\n\n${summary}\n\nSe creará un respaldo por archivo. ¿Guardar?`))return;
      busy=true;drawList();drawEditor();
      try{
        const data=await job('dwgprops-write',{snapshot,ids:[...selected],changes:{...pending},confirm:true});
        if(!current())return;
        results.replaceChildren(node('h2','Resultados'));
        for(const row of data.files){results.append(node('p',`${row.name}: ${row.status}${row.error?' · '+row.error:row.backup?' · Respaldo: '+row.backup:''}`));if(row.properties)files.find(f=>f.id===row.id).properties=row.properties;}
        if(data.cancelled)results.append(node('p','Cancelado entre archivos. Los archivos no listados no se modificaron.'));
        pending={};
      }finally{busy=false;if(current()){drawList();drawEditor();}}
    },true);
    for(const element of [name,value,add,save])element.disabled=busy;
    editor.append(name,value,add,added,save);
  }
  intro.append(button('Elegir carpeta y leer DWG',async()=>{
    if(busy||!discard())return;if(!engine.value)throw Error('No hay un motor AutoCAD compatible con el conector instalado.');
    const [folder]=await api('files/choose',{kind:'folder'});if(!folder||!current())return;
    busy=true;pending={};files=[];selected.clear();snapshot=null;folderText.textContent=folder.path;drawList();drawEditor();
    try{
      const listing=await api('files/list',{folder:folder.id});if(!current())return;
      files=listing.filter(f=>f.name.toLowerCase().endsWith('.dwg')).map(f=>({name:f.name,error:'Pendiente de lectura…'}));drawList();
      const data=await job('dwgprops-read',{folder:folder.id,engine:engine.value});if(!current())return;
      files=data.files;snapshot=data.snapshot;if(data.cancelled)notify('Lectura cancelada; se muestran los archivos ya leídos.');
    }
    finally{busy=false;if(current()){drawList();drawEditor();}}
  }),folderText);
  list.insertBefore(button('Seleccionar visibles',()=>{if(busy||!discard())return;pending={};selected=new Set(files.filter(f=>f.id&&f.name.toLocaleLowerCase().includes(search.value.toLocaleLowerCase())).map(f=>f.id));drawList();drawEditor();}),counter);
  list.insertBefore(button('Quitar selección',()=>{if(busy||!discard())return;pending={};selected.clear();drawList();drawEditor();}),counter);
  search.addEventListener('input',drawList);drawList();drawEditor();
  const engines=await api('dwgprops/engines');if(!current())return;
  for(const item of engines){const option=node('option',item.name);option.value=item.id;engine.append(option);}
  if(!engines.length)intro.append(node('p','No se encontró AutoCAD con un conector compatible. Instala la versión completa de SINCAL con DWGPROPS.'));
}
