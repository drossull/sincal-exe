// The module owns its document. Keep its iframe attached while other tools are shown.
export function createPasarelaPanel({api,node,notify,current,onStatus=()=>{},onSettings=()=>{}}){
  let frame=null,frameOrigin='',editorState={dirty:false,busy:false,ready:false},opening=null,closing=false;
  const panel=node('div');panel.id='pasarela-editor';panel.hidden=true;
  const toolbar=node('div',undefined,'pasarela-editor-toolbar');
  const title=node('strong','Pasarela BIM'),state=node('span','Iniciando editor…');state.id='pasarela-editor-status';state.setAttribute('role','status');
  const settings=node('button','Ajustes'),close=node('button','Cerrar editor');settings.type=close.type='button';
  settings.addEventListener('click',()=>onSettings());
  close.addEventListener('click',async()=>{try{if(await controller.close())onSettings();}catch(error){notify(error.message);}});
  toolbar.append(title,state,settings,close);panel.append(toolbar);document.querySelector('#workspace').append(panel);
  function update(){
    state.textContent=editorState.busy?'Operación en curso':!editorState.ready?'Iniciando editor…':editorState.dirty?'Cambios sin guardar en JSON':'Editor listo';
    close.disabled=closing||editorState.busy;
  }
  function hide(){panel.hidden=true;document.body.classList.remove('pasarela-embedded-active');document.querySelector('.layout').hidden=false;}
  window.addEventListener('message',event=>{
    if(!frame||event.source!==frame.contentWindow||event.origin!==frameOrigin)return;
    const value=event.data;
    if(!value||!['pasarela:ready','pasarela:state'].includes(value.type)||typeof value.dirty!=='boolean'||typeof value.busy!=='boolean')return;
    editorState={dirty:value.dirty,busy:value.busy,ready:editorState.ready||value.type==='pasarela:ready'};update();
  });
  const controller={
    hasFrame:()=>!!frame,
    state:()=>({...editorState,opening:!!opening,closing}),
    hide,
    show(){if(!frame)return;document.querySelector('.layout').hidden=true;panel.hidden=false;document.body.classList.add('pasarela-embedded-active');window.scrollTo(0,0);},
    async open(){
      if(frame){if(current())controller.show();return;}
      if(opening)return opening;
      opening=(async()=>{
        const result=await api('modules/pasarela/open',{});
        const address=String(result.url||''),match=/^http:\/\/127\.0\.0\.1:([1-9]\d{0,4})\/$/.exec(address);
        if(!match||Number(match[1])>65535||result.embedding!==1||result.parent_origin!==location.origin)throw Error('El módulo no proporcionó una dirección local compatible. Actualiza Pasarela BIM y vuelve a intentarlo.');
        frameOrigin=new URL(address).origin;
        frame=node('iframe');frame.id='pasarela-editor-frame';frame.title='Editor de Pasarela BIM';
        frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-downloads allow-forms allow-modals');frame.referrerPolicy='no-referrer';frame.src=address;
        editorState={dirty:false,busy:false,ready:false};panel.append(frame);update();
        if(current())controller.show();
        try{onStatus(await api('modules/pasarela/status'));}catch{/* The mounted editor remains usable if this status refresh fails. */}
      })();
      try{return await opening;}finally{opening=null;}
    },
    async close(){
      if(closing)return false;
      if(editorState.busy)throw Error('Espera a que termine la operación de Pasarela BIM antes de cerrar el editor.');
      if(!confirm('Guarda el JSON de tu pasarela antes de cerrar. Se descartará el proyecto abierto y su historial de edición. ¿Cerrar el módulo?'))return false;
      closing=true;update();
      try{
        const result=await api('modules/pasarela/close',{});
        // A failed close must leave the iframe and its in-memory document untouched.
        frame?.remove();frame=null;frameOrigin='';editorState={dirty:false,busy:false,ready:false};hide();
        if(typeof result?.installed==='boolean')onStatus(result);
        return true;
      }finally{closing=false;update();}
    }
  };
  return controller;
}

export async function renderPasarela({api,uploadPackage,node,section,notify,current,panel,onStatus=()=>{}}){
  let status=null,selectedFile=null,busy=false;
  const intro=section('pasarela-bim','Pasarela BIM');
  intro.append(node('p','Diseña el recorrido de una pasarela de hormigón, configura sus elementos y genera el modelo BIM y sus vistas con FreeCAD. El editor se abre dentro de SINCAL y conserva tu trabajo al cambiar de herramienta.'));
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
    await panel.open();
  },true);
  const close=action('Cerrar módulo',async()=>{
    if(!await panel.close())return;
    renderStatus(await api('modules/pasarela/status'));
    if(current())message.textContent='Módulo cerrado. Puedes instalar una actualización o volver a abrirlo.';
  });
  const refresh=action('Actualizar estado',async()=>{message.textContent='Comprobando disponibilidad…';renderStatus(await api('modules/pasarela/status'));});
  const installInfo=node('p',undefined,'muted');installInfo.id='pasarela-online-info';
  const releaseInfo=node('div');releaseInfo.id='pasarela-release-info';releaseInfo.hidden=true;
  const releaseVersion=node('p',undefined,'muted'),releaseLabel=node('label','Dirección de publicación');
  const releaseURL=node('input');releaseURL.id='pasarela-release-url';releaseURL.type='url';releaseURL.readOnly=true;releaseLabel.htmlFor=releaseURL.id;releaseLabel.append(releaseURL);
  releaseURL.addEventListener('focus',()=>releaseURL.select());
  releaseInfo.append(releaseVersion,releaseLabel,node('p','Puedes seleccionar y copiar esta dirección. La instalación y el editor funcionan dentro de SINCAL.','muted'));
  const releaseButton=action('Datos de publicación',async()=>{
    const result=await api('modules/pasarela/release',{});if(!current())return;
    const address=String(result.url||'');
    if(!/^https:\/\/github\.com\/drossull\/sincal-updates\/releases\//.test(address))throw Error('La información de publicación no está disponible.');
    releaseURL.value=address;releaseVersion.textContent='Publicación compatible: '+new URL(address).pathname.split('/').filter(Boolean).pop();releaseInfo.hidden=false;
  });releaseButton.hidden=true;
  actions.append(onlineInstall,open,close,refresh,releaseButton);intro.append(state,details,installInfo,actions,releaseInfo,message);

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
  const runningNote=node('p','Para actualizar, guarda el JSON de tu pasarela y usa «Cerrar módulo». Cambiar de herramienta conserva abierto el editor.','muted');runningNote.hidden=true;
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
  function controls(){
    const compatible=!!status?.installed&&status?.embedded_supported===true;
    onlineInstall.hidden=compatible;onlineInstall.textContent=status?.installed?'Actualizar Pasarela BIM':'Instalar Pasarela BIM';onlineInstall.disabled=busy||!status?.online_install_available||!!status?.running;
    open.hidden=!compatible;open.disabled=busy||!compatible;open.textContent=panel.hasFrame()?'Volver al editor':'Abrir editor';
    close.hidden=!status?.running;close.disabled=busy||!status?.running||panel.state().busy;
    refresh.disabled=busy;releaseButton.disabled=busy;file.disabled=busy;install.disabled=busy||!selectedFile||!!status?.running;runningNote.hidden=!status?.running;
  }
  function renderStatus(value){
    onStatus(value);
    if(!current())return;
    status=value;
    state.textContent=value.installed?(value.embedded_supported!==true?'Actualización necesaria':value.source==='development'?'Disponible en desarrollo':'Módulo instalado'):'Módulo no instalado';
    details.replaceChildren();
    const sources={development:'Carpeta de desarrollo',user:'Instalado para este usuario',application:'Incluido con esta instalación'};
    for(const [title,text]of [['Versión',value.version||'No disponible'],['Origen',sources[value.source]||'Sin instalar'],['FreeCAD',value.freecad_available?'Disponible':'No detectado: necesario para generar el modelo BIM']])details.append(node('dt',title),node('dd',text));
    message.textContent=value.installed&&value.embedded_supported!==true?'Actualiza Pasarela BIM para usar el editor dentro de SINCAL. Tus archivos JSON se conservan.':value.message||'';
    installInfo.textContent=value.install_message||'Puedes instalar el módulo desde un paquete ZIP local.';
    const sourceURL=String(value.release_url||'');
    releaseButton.hidden=!/^https:\/\/github\.com\/drossull\/sincal-updates\/releases\//.test(sourceURL);
    if(releaseButton.hidden)releaseInfo.hidden=true;
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
