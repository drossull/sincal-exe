// A local preference for the two abutment panels; it does not change project data.
let preferredRatio=.95/(.95+1.25),nextId=0;
const DIVIDER_WIDTH=24,MIN_EDITOR=320,MIN_PREVIEW=420,STACK_WIDTH=820;

export function mountRebarSplitter(shell,editor,preview){
  const divider=document.createElement('div'),grip=document.createElement('span');
  divider.className='rebar-panel-divider';divider.tabIndex=0;
  divider.setAttribute('role','separator');divider.setAttribute('aria-orientation','vertical');
  divider.setAttribute('aria-label','Ancho de parámetros y visor');
  divider.title='Arrastra para ajustar los paneles. También puedes usar las flechas del teclado.';
  grip.setAttribute('aria-hidden','true');divider.append(grip);
  const id=++nextId;editor.id||=`rebar-editor-${id}`;preview.id||=`rebar-preview-${id}`;
  divider.setAttribute('aria-controls',`${editor.id} ${preview.id}`);
  shell.insertBefore(divider,preview);
  let ratio=preferredRatio,pointer=null,offset=0,disposed=false;
  function layout(){
    if(disposed)return null;
    const bounds=shell.getBoundingClientRect(),space=bounds.width-DIVIDER_WIDTH;
    const stacked=bounds.width<=STACK_WIDTH;
    divider.tabIndex=stacked?-1:0;divider.setAttribute('aria-disabled',String(stacked));
    if(stacked){end();return null;}
    const left=Math.max(MIN_EDITOR,Math.min(space-MIN_PREVIEW,space*ratio));
    shell.style.setProperty('--rebar-editor-width',`${left}px`);
    divider.setAttribute('aria-valuemin',String(Math.round(100*MIN_EDITOR/space)));
    divider.setAttribute('aria-valuemax',String(Math.round(100*(space-MIN_PREVIEW)/space)));
    divider.setAttribute('aria-valuenow',String(Math.round(100*left/space)));
    divider.setAttribute('aria-valuetext',`Parámetros ${Math.round(left)} píxeles; visor ${Math.round(space-left)} píxeles`);
    return {bounds,space,left};
  }
  function resize(left){
    const state=layout();if(!state)return;
    ratio=Math.max(MIN_EDITOR,Math.min(state.space-MIN_PREVIEW,left))/state.space;
    preferredRatio=ratio;layout();
  }
  function start(event){
    if(event.button!==0||pointer!==null)return;
    const state=layout();if(!state)return;
    event.preventDefault();divider.focus({preventScroll:true});
    pointer=event.pointerId;offset=event.clientX-state.bounds.left-state.left;
    divider.setPointerCapture(pointer);shell.classList.add('rebar-panels-resizing');
  }
  function move(event){
    if(event.pointerId!==pointer)return;
    event.preventDefault();resize(event.clientX-shell.getBoundingClientRect().left-offset);
  }
  function end(event){
    if(event?.pointerId!==undefined&&event.pointerId!==pointer)return;
    const previous=pointer;pointer=null;shell.classList.remove('rebar-panels-resizing');
    if(previous!==null&&divider.hasPointerCapture(previous))divider.releasePointerCapture(previous);
  }
  function key(event){
    const state=layout();if(!state)return;
    const step=event.shiftKey?50:10;
    if(event.key==='ArrowLeft')resize(state.left-step);
    else if(event.key==='ArrowRight')resize(state.left+step);
    else if(event.key==='Home')resize(MIN_EDITOR);
    else if(event.key==='End')resize(state.space-MIN_PREVIEW);
    else return;
    event.preventDefault();
  }
  divider.addEventListener('pointerdown',start);divider.addEventListener('pointermove',move);
  divider.addEventListener('pointerup',end);divider.addEventListener('pointercancel',end);
  divider.addEventListener('lostpointercapture',end);divider.addEventListener('keydown',key);
  window.addEventListener('blur',end);
  const resizeObserver=new ResizeObserver(layout);resizeObserver.observe(shell);
  const removalObserver=new MutationObserver(()=>{if(!shell.isConnected)dispose();});
  removalObserver.observe(document.body,{childList:true,subtree:true});
  function dispose(){
    if(disposed)return;end();disposed=true;resizeObserver.disconnect();removalObserver.disconnect();
    window.removeEventListener('blur',end);
    divider.removeEventListener('pointerdown',start);divider.removeEventListener('pointermove',move);
    divider.removeEventListener('pointerup',end);divider.removeEventListener('pointercancel',end);
    divider.removeEventListener('lostpointercapture',end);divider.removeEventListener('keydown',key);
  }
  layout();return dispose;
}
