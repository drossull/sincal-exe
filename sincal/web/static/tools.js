// Module renderers use the shared local API; no shell or filesystem paths are executed by JS.
export async function renderTools(page, ctx){
  const {api,node,button,section,notify,job,artifact,project,changed,current}=ctx;
  function field(parent, title, type='text', value=''){
    const label=node('label',title),input=node('input');input.type=type;input.value=value;label.append(input);parent.append(label);return input;
  }
  function select(parent,title,options){
    const label=node('label',title),input=node('select');
    for(const [value,text] of options){const option=node('option',text);option.value=value;input.append(option);}label.append(input);parent.append(label);return input;
  }
  function table(parent,headers,rows){const wrap=node('div',undefined,'table-wrap'),t=node('table'),head=node('tr');headers.forEach(h=>head.append(node('th',h)));const th=node('thead');th.append(head);t.append(th);const body=node('tbody');rows.forEach(values=>{const row=node('tr');values.forEach(value=>row.append(node('td',String(value))));body.append(row);});t.append(body);wrap.append(t);parent.append(wrap);}
  async function choose(kind){return api('files/choose',{kind});}
  async function target(scope='active'){const result=await api('cad/status');if(result.status!=='ready')throw Error(result.message);const destination=scope==='all'?`TODOS los dibujos abiertos (${result.documents.length}):\n${result.documents.map(d=>d.name).join('\n')}`:`SOLO ${result.active.name}\n${result.active.path||'Dibujo sin guardar'}`;if(!confirm(`Enviar a ${destination}\n\nLa orden puede modificar, guardar o exportar según su función. ¿Continuar?`))return null;return result;}
  if(page==='docs'){
    const s=section('buscar','Documentación');const search=field(s,'Buscar en títulos y contenido','search');
    const manual=await api('documentation');if(!current())return;
    const topics=[...(manual.temas||[]),...Object.entries(manual.comandos_lisp||{}).sort(([a],[b])=>a.localeCompare(b,'es')).map(([command,entry])=>({
      titulo:`${command} — ${entry.titulo||command}`,categoria:'Glosario de LISPs',tags:entry.tags||[],
      contenido:[entry.descripcion,...(entry.pasos||[]),...(entry.notas||[])].filter(Boolean).join('\n'),lisp:entry
    }))];
    const content=section('manual','Guía de herramientas'),list=node('div',undefined,'documentation');content.append(list);
    const reset=button('Mostrar todas las secciones',()=>focusTopic(null));reset.hidden=true;s.append(reset);
    function focusTopic(id){
      list.classList.toggle('has-selection',Boolean(id));reset.hidden=!id;
      list.querySelectorAll('article').forEach(article=>article.classList.toggle('selected-topic',article.id===id));
      document.querySelectorAll('#anchors .topic-anchor a').forEach(a=>{if(a.hash==='#'+id)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});
    }
    const sentences=new Intl.Segmenter('es',{granularity:'sentence'});
    function draw(){list.replaceChildren();document.querySelectorAll('#anchors .topic-anchor').forEach(a=>a.remove());const groups={};for(const [index,topic] of topics.entries()){
      if(!`${topic.titulo} ${topic.tags} ${topic.contenido}`.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()))continue;
      const article=node('article',undefined,'documentation-topic');article.id='topic-'+index;article.tabIndex=-1;article.append(node('h3',topic.titulo));
      const steps=node('ul',undefined,'documentation-steps');
      if(topic.lisp){
        article.append(node('p',topic.lisp.descripcion||''));
        for(const [heading,items] of [['Cómo usarlo',topic.lisp.pasos],['Notas y precauciones',topic.lisp.notas]]){
          if(!items?.length)continue;article.append(node('h4',heading));const bullets=node('ul',undefined,'documentation-steps');
          for(const text of items)bullets.append(node('li',text));article.append(bullets);
        }
      }
      for(const line of (topic.lisp?'':topic.contenido).split(/\n+/).map(text=>text.trim()).filter(Boolean)){
        const clean=line.replace(/^\s*(?:[-*•]|\d+[.)])\s+/,'');
        // Preserve existing list items; segment prose without splitting decimal numbers or abbreviations.
        const parts=clean!==line?[clean]:Array.from(sentences.segment(clean),part=>part.segment.trim());
        for(const text of parts.filter(Boolean))steps.append(node('li',text));
      }
      if(steps.childElementCount)article.append(steps);list.append(article);
      article.addEventListener('click',()=>{if(list.classList.contains('has-selection'))focusTopic(article.id);});
      if(!groups[topic.categoria]){const group=node('details',undefined,'topic-anchor');group.append(node('summary',topic.categoria));groups[topic.categoria]=group;document.querySelector('#anchors').append(group);}
      const a=node('a',topic.titulo);a.href='#'+article.id;a.addEventListener('click',()=>{focusTopic(article.id);article.focus({preventScroll:true});});groups[topic.categoria].append(a);
    }focusTopic(null);if(!list.childElementCount)list.append(node('p','No hay instructivos que coincidan con la búsqueda.'));}search.addEventListener('input',draw);draw();
  }else if(page==='sync'){
    const s=section('sincronizador','Sincronizador');s.append(node('p','Comprueba y actualiza recursos oficiales sin reinstalar la aplicación. Esta operación sí necesita Internet. Los recursos ya descargados permanecen disponibles sin conexión.'));
    const result=node('div'),actions=node('div',undefined,'actions sync-actions');let plan=null;
    const apply=button('Aplicar actualización',async()=>{if(!plan)throw Error('Comprueba los recursos antes de actualizar.');if(!confirm('¿Descargar y activar estos recursos CAD?'))return;const selected=plan;plan=null;const applied=await job('sync-apply',{plan:selected});notify(`${applied.updated.length} recursos actualizados.`);});apply.disabled=true;
    const check=button('Comprobar recursos',async()=>{plan=null;apply.disabled=true;const data=await job('sync-check');if(!current())return;plan=data.plan;apply.disabled=false;result.replaceChildren(node('p',`Revisión ${data.tree_sha.slice(0,12)} · ${data.changed.length} cambios · ${data.removed.length} retirados`));table(result,['Recurso','Bytes'],data.changed.map(r=>[r.path,r.size]));});
    actions.append(check,apply,button('Preparar integración CAD',async()=>{if(confirm('Se modificarán las rutas de soporte/confianza CAD y PATH de tu usuario. ¿Continuar?')){const data=await job('cad-prepare',{confirm:true});notify(data.message);}}));
    s.insertBefore(actions,s.querySelector('p'));s.append(node('p','La integración CAD registra recursos y rutas de confianza para el usuario actual. Reinicia CAD después.','muted'),result);
    const history=section('historial','Historial de ejecuciones');history.append(button('Actualizar historial',async()=>{const entries=await api('jobs');log.replaceChildren();for(const item of entries){const row=node('p',`${item.operation} · ${item.state} · ${item.message}`);row.append(button('Registro',()=>artifact('jobs/'+item.id+'/log',`sincal-${item.id}.log`)));log.append(row);}}));const log=node('div');history.append(log);
  }else if(page==='live'){
    const s=section('comandos','Comandos en vivo');s.append(node('p','Por defecto se ejecuta en el dibujo activo. Puedes elegir todos los dibujos abiertos de esa instancia, revisando los destinos antes de enviar. Guarda una copia antes de limpiar un plano. Nunca se repite automáticamente una orden con resultado incierto.'));
    const command=field(s,'Comando CAD');const custom=field(s,'Confirmo que el comando personalizado termina sin pedir puntos, opciones ni respuestas','checkbox');
    const all=field(s,'Aplicar a todos los dibujos abiertos de esta instancia','checkbox');
    const send=button('Ejecutar',async()=>{const scope=all.checked?'all':'active';const expected=await target(scope);if(expected){const result=await job('cad-command',{command:command.value,autonomous:custom.checked,expected,scope});notify(result.message);}},true);s.append(send);command.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();send.click();}});
    const glossary=section('glosario','Comandos disponibles');const commands=await api('commands');if(!current())return;
    const commandGrid=node('div',undefined,'command-grid');glossary.append(commandGrid);
    for(const [name,description]of Object.entries(commands)){
      const card=node('article',undefined,'command-card'),heading=node('h3');
      heading.append(button(name,()=>{command.value=name;command.focus();}));
      card.append(heading,node('p',description));commandGrid.append(card);
    }
  }else if(page==='rename'){
    const s=section('renombrado','Buscar y reemplazar nombres');s.append(node('p','Solo archivos de la carpeta seleccionada, sin recorrer subcarpetas. Conserva extensiones y no sobrescribe destinos existentes.'));
    let folder=null;const selected=node('p','Sin carpeta'),inventory=node('div');
    async function refreshFiles(){const chosen=folder;if(!chosen)return;inventory.replaceChildren(node('p','Leyendo archivos…'));try{const files=await api('files/list',{folder:chosen.id});if(!current()||folder!==chosen)return;inventory.replaceChildren(node('h3',`Archivos de la carpeta (${files.length})`));if(files.length)table(inventory,['Nombre actual','Tamaño · KB'],files.map(file=>[file.name,(file.bytes/1024).toLocaleString('es-CL',{maximumFractionDigits:1})]));else inventory.append(node('p','No hay archivos en esta carpeta. No se incluyen subcarpetas.'));}catch(error){inventory.replaceChildren(node('p','No se pudo leer la carpeta. Vuelve a seleccionarla.'));throw error;}}
    s.append(button('Elegir carpeta',async()=>{const chosen=(await choose('folder'))[0];if(!chosen)return;folder=chosen;selected.textContent=folder.path;output.replaceChildren(node('h2','Vista previa'));await refreshFiles();}),selected,inventory);
    const fields=node('div',undefined,'fields');s.append(fields);const search=field(fields,'Buscar'),replacement=field(fields,'Reemplazar por');const output=section('plan','Vista previa');
    for(const input of [search,replacement])input.addEventListener('input',()=>output.replaceChildren(node('h2','Vista previa'),node('p','Pulsa Preparar cambios para revisar los nuevos nombres.')));
    s.append(button('Preparar cambios',async()=>{if(!folder)throw Error('Selecciona una carpeta.');output.replaceChildren(node('h2','Vista previa'));const chosen=folder,query=search.value,replace=replacement.value;const data=await api('rename/plan',{folder:chosen.id,search:query,replacement:replace});if(!current()||folder!==chosen||search.value!==query||replacement.value!==replace)return;table(output,['Actual','Nuevo'],data.changes.map(x=>[x.source,x.target]));if(data.changes.length)output.append(button('Aplicar estos cambios',async()=>{if(confirm(`¿Renombrar ${data.changes.length} archivos según esta vista previa?`)){const result=await job('rename',{plan:data.plan});notify(`${result.renamed} archivos renombrados.`);if(current()){output.replaceChildren(node('p','Renombrado terminado.'));await refreshFiles();}}},true));else output.append(node('p','No se encontraron cambios.'));}));
  }else if(page==='convert'){
    const s=section('conversion','Conversión DXF–DWG');s.append(node('p','Crea DWG nuevos con una instancia CAD independiente. No modifica los DXF ni sobrescribe DWG. Si cancelas mientras CAD trabaja, revisa la instancia de conversión; no se fuerza el cierre de CAD.'));
    let files=[],folder=null;const list=node('p','Sin archivos');s.append(button('Seleccionar DXF',async()=>{files=await choose('dxf');list.textContent=files.map(f=>f.name).join(', ')||'Sin archivos';}),list);
    const destination=node('p','Sin carpeta de salida');s.append(button('Carpeta de salida',async()=>{folder=(await choose('folder'))[0]||null;destination.textContent=folder?.path||'Sin carpeta';}),destination);
    const engine=select(s,'Motor instalado',[['AutoCAD','AutoCAD'],['ZWCAD','ZWCAD']]);s.append(button('Convertir',async()=>{if(!files.length||!folder)throw Error('Selecciona DXF y carpeta de salida.');if(confirm(`¿Convertir ${files.length} DXF a ${folder.path}?`)){const result=await job('convert',{files:files.map(f=>f.id),folder:folder.id,engine:engine.value});notify(`${result.files.length} DWG generados.`);}},true));
  }else if(page==='location'){
    const s=section('ubicacion','Ubicación geográfica');s.append(node('p','Carga puntos geográficos desde KML/KMZ. Estas coordenadas no son las coordenadas PTL del JSON del puente.'));
    const data=section('puntos','Puntos y mapa');let points={};const point=select(data,'Punto',[]);const maps=await api('maps');if(!current())return;const map=select(data,'Mapa calibrado',maps.map(m=>[m,m]));const dx=field(data,'Ajuste horizontal · px','number',0),dy=field(data,'Ajuste vertical · px','number',0);
    s.append(button('Cargar KML / KMZ',async()=>{const file=(await choose('location'))[0];if(!file)return;const result=await job('location',{file:file.id});points=result.points;point.replaceChildren();for(const name of Object.keys(points)){const option=node('option',name);option.value=name;point.append(option);}notify(`${Object.keys(points).length} puntos; ${result.ignored} ignorados.`);}));
    data.append(button('Generar croquis PNG',async()=>{if(!points[point.value])throw Error('Selecciona un punto.');const result=await job('location-render',{point:points[point.value],map:map.value,dx:Number(dx.value),dy:Number(dy.value)});await artifact('artifacts/'+result.artifact,result.name);},true));if(!maps.length)data.append(node('p','No se encontraron mapas calibrados válidos. Actualiza los recursos CAD.'));
  }else if(page==='diagnostics'){
    const s=section('diagnostico','Diagnóstico y soporte');s.append(node('p','El informe no adjunta DWG. Las rutas personales del diagnóstico se anonimizan. Revisa el contenido antes de compartirlo.'));const description=field(s,'Describe el problema');const output=section('resultado','Resultado');s.append(button('Generar diagnóstico',async()=>{const result=await job('diagnostics',{description:description.value});if(!current())return;output.replaceChildren(node('pre',result.summary));output.append(button('Guardar ZIP',()=>artifact('artifacts/'+result.artifact,result.name)));},true));
    section('registros','Registros por ejecución').append(node('p','Las tareas tienen un registro individual local. Se conservan hasta 100 registros durante 30 días; los archivos del usuario no participan de esa limpieza. Los registros están disponibles en Home → Historial.'));
    const engines=section('motores','Motor para scripts por carpeta'),choices=node('div');engines.append(button('Detectar motores instalados',async()=>{const result=await job('engines');choices.replaceChildren(node('p',result.selected?'Actual: '+result.selected.label:'Sin motor seleccionado'));for(const engine of result.engines){const row=node('p',engine.label);row.append(button('Usar este motor',async()=>{if(confirm('¿Usar '+engine.label+' para los scripts por carpeta?')){const value=await job('engine-select',{id:engine.id});notify('Motor guardado: '+value.label);}}));choices.append(row);}}),choices);
  }else if(page==='prospect'){
    const s=section('informe','Prospecciones');if(!project){s.append(node('p','Carga un proyecto en Consulta primero.'));return;}
    s.append(node('p','Extracción local PDF/TXT, con OCR cuando sea necesario. Se conserva el valor oficial publicado; el cálculo es solo un control.'));
    const exhaustive=field(s,'OCR en todas las páginas (más lento)','checkbox');const output=section('arreglos','Arreglos, tabla y evidencia');
    if(project.prospecciones?.report){const checked=await api('prospect/preview',project.prospecciones.report);project.prospecciones.checks=checked.checks;if(!current())return;}
    function draw(){output.replaceChildren(node('h2','Arreglos, tabla y evidencia'));const report=project.prospecciones?.report;if(!report)return;
      (report.notices||[]).forEach(t=>output.append(node('p',t,'badge')));
      for(const profile of report.profiles){const part=node('details');const summary=node('summary',`${profile.name} · página ${profile.page} · ${profile.method.toUpperCase()}`);part.append(summary);table(part,['Estrato','Desde · m','Hasta · m','Vs · m/s'],profile.layers.map(r=>[r.index,r.start,r.end,r.vs]));part.append(node('p',`Vs,30 oficial: ${profile.official_vs30||'No publicado'}`));
        const checks=project.prospecciones.checks?.find(c=>c.key===profile.key);for(const warning of checks?.warnings||profile.extraction_warnings||[])part.append(node('p',warning,'badge'));
        if(checks?.scene?.length){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','-24 -12 140 205');svg.setAttribute('class','profile-preview');svg.setAttribute('role','img');svg.setAttribute('aria-label','Perfil Vs de '+profile.name);
          for(const item of checks.scene){const shape=document.createElementNS(svg.namespaceURI,item.kind==='polyline'?'polyline':item.kind);shape.setAttribute('class','vs-'+item.kind);
            if(item.kind==='line'){for(const [attribute,value] of Object.entries({x1:item.points[0][0],y1:item.points[0][1],x2:item.points[1][0],y2:item.points[1][1]}))shape.setAttribute(attribute,value);}
            else if(item.kind==='polyline')shape.setAttribute('points',item.points.map(p=>p.join(',')).join(' '));
            else if(item.kind==='circle'){shape.setAttribute('cx',item.point[0]);shape.setAttribute('cy',item.point[1]);shape.setAttribute('r',item.radius);}
            else{shape.setAttribute('x',item.point[0]);shape.setAttribute('y',item.point[1]);shape.setAttribute('text-anchor',item.anchor==='left'?'start':item.anchor==='right'?'end':'middle');shape.textContent=item.text;}svg.append(shape);
          }part.append(svg);}
        const evidence=node('details');evidence.append(node('summary','Texto / imagen original'),node('pre',profile.source_text));if(profile.evidence?.image_png){const img=node('img');img.alt='Evidencia OCR original';img.src='data:image/png;base64,'+profile.evidence.image_png;img.className='evidence';evidence.append(img);}if(profile.evidence?.cells?.length)table(evidence,['Texto OCR','Confianza'],profile.evidence.cells.map(c=>[c.text,(c.confidence*100).toFixed(1)+' %']));part.append(evidence);
        if(profile.method==='ocr'){const reviewed=field(part,'He cotejado las cifras OCR con la imagen original','checkbox');reviewed.checked=profile.reviewed;reviewed.addEventListener('change',()=>{profile.reviewed=reviewed.checked;changed();});}
        const include=field(part,'Incluir tabla en CAD','checkbox');include.checked=true;
        part.append(button('Insertar perfil en CAD',async()=>{const expected=await target();if(expected)await job('cad-profile',{report,key:profile.key,table:include.checked,expected});}));output.append(part);
      }}
    s.append(node('p','Carga directamente el informe PDF (también se admite TXT). No necesitas cargar un JSON. El informe se conserva solo mientras la aplicación esté abierta.'));
    s.append(button('Cargar informe PDF / TXT',async()=>{if(project.prospecciones?.report&&!confirm('¿Reemplazar el informe de prospecciones actual? El informe actual será descartado.'))return;const file=(await choose('report'))[0];if(!file)return;const result=await job('prospect',{file:file.id,exhaustive:exhaustive.checked});project.prospecciones=result;changed();if(current())draw();},true));draw();
  }
}
