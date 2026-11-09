/* Orthographic, Z-up navigation matching Cadence's IFC viewer / OrbitControls. */
(function(root){
  'use strict';
  const SCALE=14/1000,TAU=Math.PI*2,MIN_POLAR=.01,MAX_POLAR=Math.PI-.01;
  const DEFAULT_AZIMUTH=Math.atan2(-1.4,1),DEFAULT_POLAR=Math.acos(1/Math.hypot(1,1.4,1));
  const ZOOM_SPEED=-Math.log(1.2)/Math.log(.95);
  const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
  function basis(azimuth,polar){
    const a=Number.isFinite(azimuth)?azimuth:DEFAULT_AZIMUTH,p=Number.isFinite(polar)?polar:DEFAULT_POLAR;
    const ca=Math.cos(a),sa=Math.sin(a),cp=Math.cos(p),sp=Math.sin(p);
    return {right:[-sa,ca,0],up:[-ca*cp,-sa*cp,sp],camera:[ca*sp,sa*sp,cp]};
  }
  function project(point,azimuth=DEFAULT_AZIMUTH,polar=DEFAULT_POLAR){
    const b=basis(azimuth,polar);return [dot(point,b.right)*SCALE,-dot(point,b.up)*SCALE];
  }
  function depth(point,azimuth=DEFAULT_AZIMUTH,polar=DEFAULT_POLAR){return dot(point,basis(azimuth,polar).camera);}
  function screenDelta(dx,dy,azimuth=DEFAULT_AZIMUTH,polar=DEFAULT_POLAR){
    const b=basis(azimuth,polar);return b.right.map((v,i)=>(v*dx-b.up[i]*dy)/SCALE);
  }
  function orbit(azimuth,polar,dx,dy,height){
    if(!Number.isFinite(height)||height<=0)return {azimuth,polar};
    return {azimuth:azimuth-TAU*dx/height,polar:Math.max(MIN_POLAR,Math.min(MAX_POLAR,polar-TAU*dy/height))};
  }
  function wheelFactor(event,controlPressed=false){
    let delta=Number(event.deltaY)||0;
    if(event.deltaMode===1)delta*=16;else if(event.deltaMode===2)delta*=100;
    if(event.ctrlKey&&!controlPressed)delta*=10;
    // A malformed device event must not introduce Infinity into the viewport.
    return Math.pow(1.2,Math.max(-10000,Math.min(10000,delta))/100);
  }
  function bind(canvas,{hasModel=()=>true,getView=()=> 'iso',onPan=()=>{},onOrbit=()=>{},onZoom=()=>{}}={}){
    const doc=canvas.ownerDocument,win=doc.defaultView||root,listeners=[],touches=new Map();
    const oldTouchAction=canvas.style.touchAction;
    let mouse=null,controlPressed=false,touchDragged=false,suppressClickUntil=0,destroyed=false;
    canvas.style.touchAction='none';
    function listen(target,type,fn,options){target.addEventListener(type,fn,options);listeners.push([target,type,fn,options]);}
    function showDrag(mode){
      canvas.classList.toggle('dragging',!!mode);canvas.classList.toggle('orbiting',mode==='orbit');
      if(mode){canvas.dataset.dragging='true';canvas.dataset.navigationDragging=mode;}
      else{delete canvas.dataset.dragging;delete canvas.dataset.navigationDragging;}
    }
    function capture(id){try{canvas.setPointerCapture(id);}catch{ /* Pointer may already have ended. */ }}
    function release(id){try{if(canvas.hasPointerCapture(id))canvas.releasePointerCapture(id);}catch{ /* Cancelled pointer. */ }}
    function metrics(){
      const ps=[...touches.values()].slice(0,2);
      if(ps.length===1)return {x:ps[0].x,y:ps[0].y,distance:0};
      if(ps.length===2)return {x:(ps[0].x+ps[1].x)/2,y:(ps[0].y+ps[1].y)/2,distance:Math.hypot(ps[0].x-ps[1].x,ps[0].y-ps[1].y)};
      return null;
    }
    function finishPointer(event){
      const id=event.pointerId;
      if(mouse?.id===id){mouse=null;release(id);}
      if(touches.has(id)){
        touches.delete(id);release(id);
        if(touchDragged)suppressClickUntil=Date.now()+500;
        for(const p of touches.values()){p.startX=p.x;p.startY=p.y;}
      }
      if(!mouse&&!touches.size){showDrag(null);touchDragged=false;}
    }
    function clear(){
      const ids=[...touches.keys()];if(mouse)ids.push(mouse.id);
      if(touchDragged)suppressClickUntil=Date.now()+500;
      mouse=null;touches.clear();touchDragged=false;controlPressed=false;showDrag(null);ids.forEach(release);
    }
    listen(canvas,'pointerdown',event=>{
      if(destroyed||!hasModel())return;
      if(event.pointerType==='touch'){
        if(mouse)return;
        touches.set(event.pointerId,{x:event.clientX,y:event.clientY,startX:event.clientX,startY:event.clientY});
        if(touches.size>1){touchDragged=true;showDrag('pan');for(const id of touches.keys())capture(id);}
        return;
      }
      if(event.button!==1||touches.size)return;
      event.preventDefault();
      mouse={id:event.pointerId,x:event.clientX,y:event.clientY,mode:getView()==='iso'&&(event.shiftKey||event.ctrlKey||event.metaKey)?'orbit':'pan'};
      showDrag(mouse.mode);capture(event.pointerId);
    });
    listen(doc,'pointermove',event=>{
      if(mouse?.id===event.pointerId){
        event.preventDefault();const dx=event.clientX-mouse.x,dy=event.clientY-mouse.y;
        mouse.x=event.clientX;mouse.y=event.clientY;
        if(mouse.mode==='orbit'&&getView()==='iso')onOrbit(dx,dy);else onPan(dx,dy);
      }else if(touches.has(event.pointerId)){
        const before=metrics(),point=touches.get(event.pointerId);point.x=event.clientX;point.y=event.clientY;
        if(!touchDragged&&Math.hypot(point.x-point.startX,point.y-point.startY)>3){touchDragged=true;showDrag('pan');capture(event.pointerId);}
        if(!touchDragged)return;
        event.preventDefault();const after=metrics();
        onPan(after.x-before.x,after.y-before.y);
        if(before.distance>0&&after.distance>0&&after.distance!==before.distance)onZoom(Math.pow(after.distance/before.distance,-ZOOM_SPEED),after.x,after.y);
      }
    },{passive:false});
    listen(doc,'pointerup',finishPointer);
    listen(doc,'pointercancel',finishPointer);
    listen(canvas,'lostpointercapture',finishPointer);
    listen(canvas,'wheel',event=>{
      if(!hasModel())return;
      event.preventDefault();if(mouse||touches.size)return;
      const factor=wheelFactor(event,controlPressed);if(factor!==1)onZoom(factor,event.clientX,event.clientY);
    },{passive:false});
    listen(canvas,'mousedown',event=>{if(event.button===1)event.preventDefault();});
    listen(canvas,'auxclick',event=>{if(event.button===1)event.preventDefault();});
    listen(canvas,'contextmenu',event=>event.preventDefault());
    listen(canvas,'click',event=>{
      const touchClick=event.pointerType==='touch'||event.sourceCapabilities?.firesTouchEvents;
      if(touchClick&&Date.now()<suppressClickUntil){event.preventDefault();event.stopImmediatePropagation();suppressClickUntil=0;}
    },true);
    listen(doc,'keydown',event=>{if(event.key==='Control')controlPressed=true;},{capture:true,passive:true});
    listen(doc,'keyup',event=>{if(event.key==='Control')controlPressed=false;},{capture:true,passive:true});
    listen(win,'blur',clear);
    return {destroy(){if(destroyed)return;destroyed=true;clear();listeners.forEach(([target,type,fn,options])=>target.removeEventListener(type,fn,options));canvas.style.touchAction=oldTouchAction;}};
  }
  root.ViewerNavigation={SCALE,DEFAULT_AZIMUTH,DEFAULT_POLAR,MIN_POLAR,MAX_POLAR,ZOOM_SPEED,project,depth,screenDelta,orbit,wheelFactor,bind};
  if(typeof module!=='undefined')module.exports=root.ViewerNavigation;
})(typeof window!=='undefined'?window:globalThis);
