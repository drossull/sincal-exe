// One picker-authorized root; tools consume typed grants, never arbitrary paths.
export function createProjectFiles({api,node,button,section,notify}){
  let catalog=null;
  const labels={report:'Informes PDF / TXT',location:'KML / KMZ',dwg:'Planos DWG',dxf:'Archivos DXF',folder:'Carpetas',reference:'Otros documentos',memory_pdf:'Memoria PDF',memory_excel:'Memoria Excel',session:'JSON'};
  async function choose(kind,options={}){
    const available=(catalog?.entries||[]).filter(e=>e.grants[kind]);
    if(!available.length){notify('No hay '+(labels[kind]||kind)+' en la carpeta. Abre o actualiza la carpeta desde Proyecto.');return [];}
    return new Promise(resolve=>{
      const dialog=node('dialog');dialog.setAttribute('aria-label','Seleccionar archivos del proyecto');dialog.append(node('h2',labels[kind]||kind),node('p',catalog.root.path));
      const search=node('input');search.placeholder='Filtrar por nombre o subcarpeta';search.setAttribute('aria-label','Filtrar archivos');dialog.append(search);
      const multiple=['dwg','dxf'].includes(kind)||(kind==='report'&&options.multiple===true),selected=new Set(),rows=[];
      for(const file of available){const label=node('label',undefined,'asset-choice'),input=node('input');input.type=multiple?'checkbox':'radio';input.name='project-file';input.addEventListener('change',()=>{if(!multiple)selected.clear();if(input.checked)selected.add(file);else selected.delete(file);});label.append(input,node('span',file.name),node('small',file.relative));dialog.append(label);rows.push([label,file]);}
      search.addEventListener('input',()=>{for(const [label,file]of rows)label.hidden=!file.relative.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());});
      const actions=node('div',undefined,'actions');let settled=false;
      function done(value){if(settled)return;settled=true;dialog.close();dialog.remove();resolve(value);}
      actions.append(button('Usar selección',()=>{if(!selected.size)throw Error('Selecciona al menos un archivo.');done([...selected].map(f=>({id:f.grants[kind],name:f.name,path:f.path})));},true),button('Cancelar',()=>done([])));dialog.append(actions);dialog.addEventListener('cancel',e=>{e.preventDefault();done([]);});document.body.append(dialog);dialog.showModal();
    });
  }
  function render(kinds=Object.keys(labels),memories=false,options={}){
    const s=section(memories?'memorias':'archivos-proyecto',memories?'Memorias de cálculo':'Carpeta del proyecto');
    s.append(node('p',memories?'PDF y Excel disponibles en la carpeta del proyecto. No se ejecutan macros ni se calculan armaduras automáticamente.':'Abre una única carpeta. Se reconocen sus archivos y subcarpetas para usarlos en las herramientas siguientes. No se modifican ni se suben a Internet.'));
    const actions=node('div',undefined,'actions'),list=node('div');s.append(actions,list);
    if(!memories){
      actions.append(button('Abrir carpeta de proyecto',async()=>{
        if(options.beforeOpen&&!options.beforeOpen())return;
        const picked=await api('files/choose',{kind:'folder'});if(!picked.length)return;
        const next=await api('files/project',{folder:picked[0].id});
        catalog=next;await options.onOpen?.(next.root);draw();
      },true),button('Actualizar archivos',async()=>{if(!catalog)throw Error('Abre una carpeta primero.');if(options.beforeRefresh&&!options.beforeRefresh())return;catalog=await api('files/project',{folder:catalog.root.id});draw();}));
    }
    function draw(){
      list.replaceChildren();if(!catalog){list.append(node('p','Todavía no hay una carpeta abierta.'));return;}
      list.append(node('p',catalog.root.path));for(const warning of catalog.warnings||[])list.append(node('p',warning,'badge'));
      const shown=catalog.entries.filter(f=>kinds.some(k=>f.grants[k]));
      list.append(node('p',`${shown.length} archivos y carpetas disponibles. La selección de carpeta dura mientras SINCAL esté abierto.`));
      const search=node('input');search.placeholder='Filtrar archivos del proyecto';search.setAttribute('aria-label','Filtrar catálogo');list.append(search);
      const wrap=node('div',undefined,'table-wrap'),table=node('table'),head=node('tr');['Archivo / subcarpeta','Tipos',''].forEach(t=>head.append(node('th',t)));table.append(head);
      const rows=[];
      for(const file of shown){const row=node('tr'),action=node('td');if(file.grants.session&&options.onJson)action.append(button('Usar JSON',()=>options.onJson({id:file.grants.session,name:file.name,path:file.path})));row.append(node('td',file.relative),node('td',Object.keys(file.grants).map(k=>labels[k]||k).join(' · ')),action);table.append(row);rows.push([row,file]);}
      search.addEventListener('input',()=>{for(const [row,file]of rows)row.hidden=!file.relative.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());});wrap.append(table);list.append(wrap);
    }draw();
  }
  return {choose,render,clear:()=>{catalog=null;}};
}
