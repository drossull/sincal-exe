// The optional editor runs in its own process and browser; this page only manages it.
export async function renderPasarela({api,uploadPackage,node,section,notify,current,onStatus=()=>{}}){
  let status=null,selectedFile=null,busy=false;
  const intro=section('pasarela-bim','Pasarela BIM');
  intro.append(node('p','Diseña el recorrido de una pasarela de hormigón, configura sus elementos y genera el modelo BIM y sus vistas con FreeCAD. El editor se abre en el navegador de este equipo.'));
  const state=node('p','Comprobando disponibilidad…','badge');state.id='pasarela-module-state';
  const details=node('dl',undefined,'rows');details.id='pasarela-module-details';
  const message=node('p');message.id='pasarela-module-message';message.setAttribute('role','status');
  const actions=node('div',undefined,'actions');
  function action(label,callback,primary=false){const b=node('button',label,primary?'primary':'');b.type='button';b.addEventListener('click',()=>run(callback));return b;}
  const onlineInstall=action('Instalar Pasarela BIM',async()=>{
    message.textContent='Descargando, comprobando e instalando Pasarela BIM…';
    const result=await api('modules/pasarela/install-online',{});renderStatus(result);
    if(current())message.textContent=result.message||'Pasarela BIM instalado. Ya puedes abrir el editor.';
  },true);
  const open=action('Abrir editor',async()=>{
    message.textContent='Abriendo Pasarela BIM…';
    const result=await api('modules/pasarela/open',{});
    renderStatus(await api('modules/pasarela/status'));
    if(current())message.textContent=result.message||'Se ha solicitado abrir el editor en el navegador.';
  },true);
  const close=action('Cerrar módulo',async()=>{
    if(!confirm('Guarda el JSON de tu pasarela antes de cerrar. El editor dejará de estar disponible hasta que vuelvas a abrirlo. ¿Cerrar el módulo?'))return;
    message.textContent='Cerrando Pasarela BIM…';
    await api('modules/pasarela/close',{});renderStatus(await api('modules/pasarela/status'));
    if(current())message.textContent='Módulo cerrado. Puedes instalar una actualización o volver a abrirlo.';
  });
  const refresh=action('Actualizar estado',async()=>{message.textContent='Comprobando disponibilidad…';renderStatus(await api('modules/pasarela/status'));});
  const installInfo=node('p',undefined,'muted');installInfo.id='pasarela-online-info';
  const releaseLink=node('a','Ver publicación de SINCAL');releaseLink.hidden=true;releaseLink.rel='noopener noreferrer';releaseLink.target='_blank';
  releaseLink.addEventListener('click',event=>{event.preventDefault();run(()=>api('modules/pasarela/release',{}));});
  actions.append(onlineInstall,open,close,refresh);intro.append(state,details,installInfo,releaseLink,actions,message);

  const installation=section('pasarela-instalar','Opciones de instalación');
  installation.append(node('p','La instalación directa descarga el módulo compatible con tu versión de SINCAL y comprueba sus archivos. FreeCAD se instala por separado.','muted'));
  const manual=node('details');manual.append(node('summary','Instalar o actualizar desde un ZIP local'));
  manual.append(node('p','Si ya tienes el paquete del módulo, selecciónalo aquí para instalarlo sin descargarlo de nuevo.'));
  const label=node('label','Paquete de Pasarela BIM (.zip)');
  const file=node('input');file.type='file';file.accept='.zip,application/zip';file.id='pasarela-package';label.htmlFor=file.id;label.append(file);
  const selected=node('p','Ningún paquete seleccionado.','muted');selected.id='pasarela-package-selection';
  const install=action('Instalar paquete',async()=>{
    if(!selectedFile)return;
    message.textContent='Instalando el paquete…';
    const result=await uploadPackage(selectedFile);
    renderStatus(result);
    if(!current())return;
    selectedFile=null;file.value='';selected.textContent='Ningún paquete seleccionado.';
    message.textContent=result.message||'Paquete instalado. Ya puedes abrir el editor.';
    notify('Paquete de Pasarela BIM instalado.');
  });
  const installActions=node('div',undefined,'actions');installActions.append(install);
  const runningNote=node('p','Para actualizar, guarda el JSON de tu pasarela y usa «Cerrar módulo». Cerrar sólo la pestaña del navegador no detiene el módulo.','muted');runningNote.hidden=true;
  manual.append(label,selected,installActions,node('p','Máximo 150 MiB. SINCAL comprueba el manifiesto y los archivos del paquete antes de instalarlo.','muted'));
  installation.append(runningNote,manual);
  file.addEventListener('change',()=>{
    selectedFile=file.files?.[0]||null;
    if(selectedFile&&(!/\.zip$/i.test(selectedFile.name)||selectedFile.size>150*1024*1024||selectedFile.size===0)){
      message.textContent='Selecciona un ZIP no vacío de hasta 150 MiB.';selectedFile=null;file.value='';
    }
    selected.textContent=selectedFile?`${selectedFile.name} · ${(selectedFile.size/1024/1024).toFixed(1)} MiB`:'Ningún paquete seleccionado.';
    controls();
  });
  function controls(){onlineInstall.hidden=!!status?.installed;onlineInstall.disabled=busy||!status?.online_install_available||!!status?.running;open.hidden=!status?.installed;open.disabled=busy||!status?.installed;close.hidden=!status?.running;close.disabled=busy||!status?.running;refresh.disabled=busy;file.disabled=busy;install.disabled=busy||!selectedFile||!!status?.running;runningNote.hidden=!status?.running;}
  function renderStatus(value){
    onStatus(value);
    if(!current())return;
    status=value;
    state.textContent=value.installed?(value.source==='development'?'Disponible en desarrollo':'Módulo instalado'):'Módulo no instalado';
    details.replaceChildren();
    const sources={development:'Carpeta de desarrollo',user:'Instalado para este usuario',application:'Incluido con esta instalación'};
    for(const [title,text]of [['Versión',value.version||'No disponible'],['Origen',sources[value.source]||'Sin instalar'],['FreeCAD',value.freecad_available?'Disponible':'No detectado: necesario para generar el modelo BIM']])details.append(node('dt',title),node('dd',text));
    message.textContent=value.message||'';
    installInfo.textContent=value.install_message||'Puedes instalar el módulo desde un paquete ZIP local.';
    const sourceURL=String(value.release_url||'');
    releaseLink.hidden=!/^https:\/\/github\.com\/drossull\/sincal-updates\/releases(?:\/|$)/.test(sourceURL);
    if(!releaseLink.hidden)releaseLink.href=sourceURL;
    install.textContent=value.installed?'Actualizar desde paquete':'Instalar paquete';
    controls();
  }
  async function run(callback){
    if(busy)return;busy=true;controls();if(current())notify('');
    try{await callback();}catch(error){if(current()){if(!status)state.textContent='No se pudo comprobar el módulo.';message.textContent=error.message;notify(error.message);}}
    finally{busy=false;if(current())controls();}
  }
  await run(async()=>renderStatus(await api('modules/pasarela/status')));
}
