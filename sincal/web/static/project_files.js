// Local grants only: a project library never uploads file contents to the Internet.
export function createProjectFiles({api,node,button,section,notify}){
  const assets=[];
  const labels={report:'Informes PDF / TXT',location:'KML / KMZ',dwg:'Planos DWG',dxf:'Archivos DXF',folder:'Carpetas',reference:'Otros documentos',memory_pdf:'Memoria PDF',memory_excel:'Memoria Excel'};
  function add(kind,files){for(const file of files){const key=(file.path||file.id).toLocaleLowerCase();if(!assets.some(a=>a.kind===kind&&(a.path||a.id).toLocaleLowerCase()===key))assets.push({...file,kind});}return files;}
  async function browse(kind){return add(kind,await api('files/choose',{kind}));}
  async function choose(kind){
    const available=assets.filter(a=>a.kind===kind);
    if(!available.length){notify('No hay archivos disponibles de este tipo: '+(labels[kind]||kind)+'. Añádelos primero en Proyecto.');return [];}
    return new Promise(resolve=>{
      const dialog=node('dialog'),heading=node('h2','Archivos del proyecto');dialog.setAttribute('aria-label','Seleccionar archivos del proyecto');dialog.append(heading,node('p',labels[kind]||kind));
      const multiple=['dwg','dxf'].includes(kind),selected=new Set();
      for(const file of available){const label=node('label',undefined,'asset-choice'),input=node('input');input.type=multiple?'checkbox':'radio';input.name='project-file';input.addEventListener('change',()=>{if(!multiple)selected.clear();if(input.checked)selected.add(file);else selected.delete(file);});label.append(input,node('span',file.name),node('small',file.path||''));dialog.append(label);}
      const actions=node('div',undefined,'actions');let settled=false;
      function done(value){if(settled)return;settled=true;dialog.close();dialog.remove();resolve(value);}
      actions.append(button('Usar selección',()=>{if(!selected.size)throw Error('Selecciona al menos un archivo.');done([...selected]);},true),button('Cancelar',()=>done([])));dialog.append(actions);dialog.addEventListener('cancel',e=>{e.preventDefault();done([]);});document.body.append(dialog);dialog.showModal();
    });
  }
  function render(kinds=Object.keys(labels),memories=false){
    const s=section(memories?'memorias':'archivos-proyecto',memories?'Memorias de cálculo':'Archivos del proyecto');s.append(node('p',memories?'Adjunta las memorias PDF y Excel como antecedentes. Todavía no se analizan, no se ejecutan macros ni se calculan armaduras desde ellas. Se guardan referencias locales mientras SINCAL permanezca abierto.':'Incorpora aquí informes, planos, mapas y documentos de referencia. Los módulos permiten elegirlos sin volver a buscarlos en el equipo. No se copian ni se suben a Internet; la lista dura mientras SINCAL permanezca abierto.'));
    const actions=node('div',undefined,'actions'),list=node('div');
    for(const kind of kinds)actions.append(button('Añadir '+labels[kind],async()=>{await browse(kind);draw();}));s.append(actions,list);
    function draw(){const shown=assets.filter(a=>kinds.includes(a.kind));list.replaceChildren();if(!shown.length){list.append(node('p','Todavía no hay archivos incorporados.'));return;}
      const wrap=node('div',undefined,'table-wrap'),table=node('table'),head=node('tr');['Archivo','Tipo','Ruta local',''].forEach(t=>head.append(node('th',t)));table.append(head);
      for(const file of shown){const row=node('tr'),action=node('td');action.append(button('Quitar',()=>{assets.splice(assets.indexOf(file),1);draw();notify('Referencia retirada del proyecto; el archivo del equipo no se ha eliminado.');}));row.append(node('td',file.name),node('td',labels[file.kind]),node('td',file.path||''),action);table.append(row);}wrap.append(table);list.append(wrap);
    }draw();
  }
  return {choose,render,clear:()=>{assets.length=0;}};
}
