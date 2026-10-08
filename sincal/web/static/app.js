'use strict';
import {renderRebar,renderCrossbeam} from '/rebar.js';
import {renderTools} from '/tools.js';
import {renderNavigation,renderTabs,title,owner,destination} from '/navigation.js';
import {createProjectFiles} from '/project_files.js';
const $ = selector => document.querySelector(selector);
const token = new URLSearchParams(location.hash.slice(1)).get('token') || sessionStorage.getItem('sincal-local-token') || '';
sessionStorage.setItem('sincal-local-token', token);
history.replaceState(null, '', '/');
let project = null, result = null, dirty = false, page = 'home';
renderNavigation(node);
const projectFiles=createProjectFiles({api,node,button,section,notify});
function node(tag, text, className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
function notify(text){$('#notice').textContent=text;}
async function api(path, payload){const response=await fetch('/api/'+path,{method:payload?'POST':'GET',headers:{'X-Sincal-Token':token,'Content-Type':'application/json'},body:payload?JSON.stringify(payload):undefined});const data=await response.json();if(!response.ok)throw Error(data.error);return data;}
function button(text, action, primary=false){const b=node('button',text,primary?'primary':'');b.addEventListener('click',async()=>{b.disabled=true;try{await action();}catch(e){notify(e.message);}finally{b.disabled=false;}});return b;}
function section(id,title){const s=node('section');s.id=id;s.append(node('h2',title));$('#main').append(s);const a=node('a',title);a.href='#'+id;$('#anchors').append(a);return s;}
function acceptReplacement(){if(activeJob){notify('Termina o cancela la operación en curso antes de cambiar de proyecto.');return false;}return !dirty||confirm('Hay trabajo cargado o modificado. Al continuar se descartará; no se guardan sesiones. ¿Continuar?');}
function identity(){const output={};for(const key of ['ot','revision','structure_name'])output[key]=$('#'+key)?.value??project?.identification?.[key]??'';return output;}
function projectLoader(parent){
  const label=node('label','Cargar JSON del proyecto'),input=node('input');input.type='file';input.accept='.json,application/json';label.append(input);parent.append(label);
  input.addEventListener('change',async()=>{try{
    const file=input.files[0];if(!file||!acceptReplacement())return;
    if(file.size>4*1024*1024)throw Error('El límite del JSON es 4 MB.');
    const previous=project,candidate={data:JSON.parse(await file.text()),identification:{...identity()},sourceName:file.name};
    const preview=await api('project/preview',candidate);candidate.rebar=await api('rebar/from-project',candidate.data);
    if(project!==previous)throw Error('El proyecto cambió durante la carga. Selecciona el archivo nuevamente.');
    project=candidate;result=preview;dirty=true;await show(page);notify('JSON cargado. Consulta y Generador de armadura comparten este proyecto.');
  }catch(error){notify(error.message);}finally{input.value='';}});
}
let activeJob=null;
const motion=document.createElementNS('http://www.w3.org/2000/svg','svg');motion.setAttribute('viewBox','0 0 88 54');motion.setAttribute('width','88');motion.setAttribute('height','54');motion.setAttribute('aria-hidden','true');$('#activity img').replaceWith(motion);
function animateBridge(now=0){
  if(!activeJob)return;motion.replaceChildren();const guide=x=>.78-.67*Math.pow(Math.max(0,Math.min(1,x)),1.72);
  function polygon(points){const shape=document.createElementNS(motion.namespaceURI,'polygon');shape.setAttribute('points',points.map(([x,y])=>`${x*88},${y*54}`).join(' '));motion.append(shape);}
  const deckTop=.18,deckEnd=Math.pow((.78-deckTop)/.67,1/1.72),barWidth=.047*1.15;
  const end=Array.from({length:81},(_,i)=>deckEnd*i/80);polygon([[0,deckTop],[deckEnd,deckTop],...end.toReversed().map(x=>[x,guide(x)])]);
  const phase=matchMedia('(prefers-reduced-motion: reduce)').matches?0:(now%1200)/1200*.145;
  // Keep every column inside the deck's footprint, including animated edge frames.
  for(let x=-.145+phase;x<=deckEnd;x+=.145){const left=Math.max(0,x),right=Math.min(deckEnd,x+barWidth);if(right>left)polygon([[left,1],[right,1],[right,Math.max(deckTop,guide(right))],[left,Math.max(deckTop,guide(left))]]);}
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches)requestAnimationFrame(animateBridge);
}
async function artifact(path,name){const response=await fetch('/api/'+path,{headers:{'X-Sincal-Token':token}});if(!response.ok)throw Error('No se pudo obtener el resultado.');const url=URL.createObjectURL(await response.blob());const a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);}
async function job(operation,payload={}){
  if(activeJob)throw Error('Espera a que termine la operación actual.');
  activeJob='starting';$('#activity').hidden=false;$('#activity-text').textContent='Iniciando…';$('#activity-progress').removeAttribute('value');requestAnimationFrame(animateBridge);
  try{const started=await api('jobs',{operation,payload});activeJob=started.id;
    while(true){const state=await api('jobs/'+started.id);$('#activity-text').textContent=state.message+(state.progress===null?'':` · ${Math.round(state.progress)} %`);
      if(state.progress===null)$('#activity-progress').removeAttribute('value');else $('#activity-progress').value=state.progress;
      if(state.state==='completed')return state.result;
      if(['failed','cancelled'].includes(state.state))throw Error(state.message+' · Registro disponible en Home → Historial.');
      await new Promise(resolve=>setTimeout(resolve,600));
    }
  }finally{activeJob=null;$('#activity').hidden=true;}
}
$('#cancel-job').addEventListener('click',()=>{if(activeJob&&activeJob!=='starting')api('jobs/cancel',{id:activeJob}).then(()=>notify('Cancelación solicitada. CAD podría seguir ejecutando la orden.')).catch(e=>notify(e.message));});
function toolContext(currentPage){return {api:(path,payload)=>path==='files/choose'?projectFiles.choose(payload.kind):api(path,payload),chooseOutput:()=>api('files/choose',{kind:'folder'}),node,button,section,notify,job,artifact,project,changed:()=>{dirty=true;},current:()=>page===currentPage};}
function download(name,text){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
async function show(next){page=destination(next);$('#main').replaceChildren();$('#anchors').replaceChildren();$('#breadcrumb').textContent=title(page);document.querySelectorAll('#sidebar [data-page]').forEach(b=>b.setAttribute('aria-current',b.dataset.page===owner(page)?'page':'false'));$('#main').append(node('span','SINCAL SUITE 3.0 / ESCRITORIO','eyebrow'));renderTabs(page,node);window.scrollTo(0,0);
if(page==='home'){
await renderTools('shell-batch',toolContext('home'));if(page!=='home')return;
await renderTools('sync',toolContext('home'));if(page!=='home')return;
section('privacidad','Privacidad del piloto').append(node('p','Los datos quedan en este equipo y en el perfil de Windows actual. No existe todavía login web, sincronización ni aislamiento entre personas que compartan la misma cuenta de Windows.'));
section('creditos','Créditos').append(node('p','Por Gonzalo M. para SINCAL Ltda. 2026.'));
}else if(page==='project'){
const s=section('proyecto','Proyecto');s.append(node('p','Reúne los archivos que utilizarás en las herramientas. Incorporar un archivo no ejecuta procesos ni modifica su contenido.'));
projectLoader(s);if(project?.sourceName)s.append(node('p','JSON activo: '+project.sourceName));
const restoreLabel=node('label','Incorporar reconocimiento de estratigrafía guardado (JSON)'),restore=node('input');restore.type='file';restore.accept='.json,application/json';restoreLabel.append(restore);s.append(restoreLabel);
restore.addEventListener('change',async()=>{try{
  const file=restore.files[0];if(!file||!acceptReplacement())return;if(file.size>48*1024*1024)throw Error('El reconocimiento supera 48 MB.');
  const saved=JSON.parse(await file.text());if(saved.schema!=='sincal-stratigraphy-1')throw Error('Formato de reconocimiento no compatible.');
  const checked=await api('stratigraphy/preview',{report:saved.report,table:false});
  project??={data:{},identification:{ot:'',revision:'',structure_name:''}};project.stratigraphy={report:saved.report,...checked};dirty=true;notify('Reconocimiento incorporado. Disponible en Proyecto → Prospecciones → Estratigrafía.');
}catch(e){notify(e.message);}finally{restore.value='';}});
s.append(button('Descartar proyecto actual',async()=>{
  if(activeJob){notify('Termina o cancela la operación en curso antes de descartar el proyecto.');return;}
  if(!confirm('¿Descartar el proyecto actual? Se quitarán el JSON, los datos de consulta, armaduras y prospecciones cargados, y la lista de archivos y carpetas del proyecto. Los archivos originales del equipo no se borrarán ni se desharán cambios ya guardados en ellos.'))return;
  project=null;result=null;dirty=false;projectFiles.clear();await show('project');notify('Proyecto descartado. Los archivos originales permanecen en el equipo.');
}));
projectFiles.render();
}else if(['docs','live','convert','rename','location','prospect','stratigraphy','dwgprops','revisions','revision-editor'].includes(page)){
if(['prospect','stratigraphy'].includes(page)&&!project)project={data:{},identification:{ot:'',revision:'',structure_name:''}};
await renderTools(page,toolContext(page));
}else if(page==='consulta'){
const s=section('proyecto','Consulta del proyecto');s.append(node('p','Consulta el JSON incorporado desde Proyecto. La consulta es de solo lectura; OT, revisión y nombre son datos del proyecto actual. El archivo original no se modifica.'));
const fields=node('div',undefined,'fields');for(const [key,title] of [['ot','OT'],['revision','Revisión'],['structure_name','Nombre de estructura']]){const label=node('label',title);const input=node('input');input.id=key;input.maxLength=300;input.value=project?.identification?.[key]||'';input.addEventListener('input',()=>{if(project){project.identification=identity();dirty=true;}});label.append(input);fields.append(label);}s.append(fields);
s.append(node('p',project?.sourceName?'JSON activo: '+project.sourceName:'Incorpora el JSON del puente en Proyecto.'));
const actions=node('div',undefined,'actions');actions.append(button('Exportar TXT',async()=>{if(!project)throw Error('Carga un proyecto primero.');project.identification=identity();result=await api('project/preview',project);download('consulta-sincal.txt',result.text);}),button('Limpiar proyecto',()=>{if(acceptReplacement()){project=null;result=null;dirty=false;show('consulta');}}));s.append(actions);
if(result){if(result.warnings.length){const w=section('advertencias','Advertencias del JSON');const ul=node('ul');result.warnings.forEach(text=>ul.append(node('li',text)));w.append(ul);}for(const item of result.sections){const part=section(item.anchor,item.title);if(!item.groups.length)part.append(node('p','Sin información en este archivo.','muted'));for(const group of item.groups){part.append(node('h3',group.title));const rows=node('dl',undefined,'rows');for(const [,label,value]of group.rows)rows.append(node('dt',label),node('dd',value));part.append(rows);}}}
}else if(page==='diagnostics'){
await renderTools('diagnostics',toolContext('diagnostics'));if(page!=='diagnostics')return;
const s=section('conexion','Conexión con AutoCAD / ZWCAD');
s.append(node('p','Comprueba el CAD abierto en este equipo. Esta etapa solo lee el estado: no ejecuta comandos, guarda ni modifica dibujos.'));
const status=node('div');
s.append(button('Comprobar conexión',async()=>{
status.replaceChildren(node('p','Comprobando CAD… puede tardar hasta 15 segundos.','badge'));
try{const data=await api('cad/status');if(page!=='diagnostics')return;status.replaceChildren(node('p',data.message,'badge'));
if(data.product)status.append(node('p',`${data.product} · versión ${data.version}`));
if(data.active){status.append(node('h3','Dibujo activo'),node('p',data.active.name),node('p',data.active.path||'Sin guardar'),node('p',`Espacio: ${data.active.layout} · INSUNITS: ${data.active.insunits}`));if(data.active.insunits!==6)status.append(node('p','Atención: el generador de zapata trabaja en metros; el dibujo no declara INSUNITS = 6.'));
const list=node('ul');for(const doc of data.documents)list.append(node('li',doc.name));status.append(node('h3','Dibujos abiertos'),list);}
}catch(error){status.replaceChildren(node('p',error.message));}
},true),status);
section('seguridad-cad','Conexión segura').append(node('p','No se inicia CAD automáticamente. Si hay varias instancias, la conexión se bloquea para no elegir un dibujo equivocado. Si COM se cuelga, solo se detiene el proceso de comprobación. Este estado es una instantánea y debe validarse de nuevo antes de cualquier futura operación.'));
}else if(page==='rebar'){
const intro=section('generador','Generador de armadura');intro.append(node('p','Prepara los antecedentes del puente y trabaja por estructura. El JSON se comparte con Consulta de proyecto; las memorias quedan como antecedentes para un análisis futuro.'));
projectLoader(intro);if(project?.sourceName)intro.append(node('p','JSON activo: '+project.sourceName));
projectFiles.render(['memory_pdf','memory_excel'],true);
const guide=section('guia-armadura','Cómo funciona');const steps=node('ol');for(const text of ['Carga el JSON del puente y adjunta las memorias PDF y Excel disponibles.','Selecciona la estructura en el menú: Estribos, Viga, Cepa, Travesaño o Losa.','En las herramientas disponibles, revisa dimensiones, recubrimientos, marcas y despieces antes de generar.','Comprueba la conexión en Diagnóstico y revisa el dibujo de destino antes de enviar a CAD.'])steps.append(node('li',text));guide.append(steps,node('p','El módulo documenta armaduras; no sustituye la revisión del ingeniero. Viga, Cepa y Losa aún no tienen generador. La carga de memorias no realiza análisis automático.'));
}else if(page==='rebar-abutments'){
await renderRebar({...toolContext(page),project});
}else if(page==='rebar-crossbeam'){
await renderCrossbeam({...toolContext(page),project});
}else if(['rebar-beam','rebar-pier','rebar-slab'].includes(page)){
const names={'rebar-beam':'Viga','rebar-pier':'Cepa','rebar-slab':'Losa'},s=section('estructura',names[page]);s.append(node('p',page==='rebar-pier'?'Se utilizará cuando el puente incluya cepas.':'Estructura incluida en el flujo del módulo.'));s.append(node('p','Generador pendiente de desarrollo. No se realizan cálculos ni se generan armaduras desde esta página todavía.'));
}else{section('no-disponible','Sección no disponible').append(node('p','Selecciona una herramienta del menú lateral.'));}
}
document.addEventListener('click',event=>{const b=event.target.closest('[data-page]');if(!b||event.defaultPrevented||destination(b.dataset.page)===page)return;if(activeJob){notify('Espera a que termine la operación actual o cancélala antes de cambiar de herramienta.');return;}show(b.dataset.page).catch(e=>notify(e.message));});
const system=matchMedia('(prefers-color-scheme: dark)');function theme(){const value=$('#theme').value;document.documentElement.dataset.theme=value==='system'?(system.matches?'dark':'light'):value;localStorage.setItem('sincal-web-theme',value);}$('#theme').value=localStorage.getItem('sincal-web-theme')||'system';$('#theme').addEventListener('change',theme);system.addEventListener('change',theme);theme();
$('#zoom').addEventListener('change',()=>{document.documentElement.dataset.zoom=$('#zoom').value;localStorage.setItem('sincal-zoom',$('#zoom').value);});$('#zoom').value=localStorage.getItem('sincal-zoom')||'100';document.documentElement.dataset.zoom=$('#zoom').value;
$('#right-panel').addEventListener('click',()=>{const hidden=document.body.classList.toggle('outline-hidden');$('#right-panel').setAttribute('aria-expanded',String(!hidden));});
$('#panels').addEventListener('click',()=>{if(matchMedia('(max-width:700px)').matches){const open=document.body.classList.toggle('mobile-open');$('#panels').setAttribute('aria-expanded',String(open));}else{const hidden=document.body.classList.toggle('panels-hidden');$('#panels').setAttribute('aria-expanded',String(!hidden));}});
window.addEventListener('beforeunload',event=>{if(dirty||activeJob){event.preventDefault();event.returnValue='';}});
function persistPreferences(){api('preferences',{theme:$('#theme').value,palette:$('#palette').value,zoom:$('#zoom').value,sidebar:!document.body.classList.contains('panels-hidden'),outline:!document.body.classList.contains('outline-hidden')}).catch(e=>notify(e.message));}
$('#palette').addEventListener('change',()=>{document.documentElement.dataset.palette=$('#palette').value;persistPreferences();});
for(const id of ['theme','zoom','panels','right-panel'])$('#'+id).addEventListener(id==='theme'||id==='zoom'?'change':'click',persistPreferences);
async function start(){
  const [preferences,palettes]=await Promise.all([api('preferences'),api('palettes')]);
  for(const palette of palettes){const option=node('option',palette.charAt(0).toUpperCase()+palette.slice(1));option.value=palette;$('#palette').append(option);}
  $('#palette').value=preferences.palette||'sincal';document.documentElement.dataset.palette=$('#palette').value;
  $('#theme').value=preferences.theme||'system';theme();$('#zoom').value=preferences.zoom||'100';document.documentElement.dataset.zoom=$('#zoom').value;
  document.body.classList.toggle('panels-hidden',preferences.sidebar===false);document.body.classList.toggle('outline-hidden',preferences.outline===false);
  await show(project?'consulta':'home');
}
start().catch(e=>{notify(e.message);show('home').catch(error=>notify(error.message));});
