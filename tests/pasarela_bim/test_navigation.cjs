'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const nav=require('../../pasarela_bim/web/navegacion.js');
const close=(a,b,eps=1e-9)=>assert(Math.abs(a-b)<eps,`${a} != ${b}`);
test('vista inicial comparte la dirección de cámara de Cadence y Z permanece vertical',()=>{
 const a=nav.DEFAULT_AZIMUTH,p=nav.DEFAULT_POLAR;
 close(nav.depth([1,-1.4,1],a,p),Math.hypot(1,-1.4,1));
 const projected=nav.project([1000,-1400,1000],a,p);projected.forEach(v=>close(v,0));
 for(const angle of [-5,-1,0,1,5])for(const polar of [.01,.7,Math.PI/2,Math.PI-.01]){
  const bottom=nav.project([173,289,0],angle,polar),top=nav.project([173,289,1000],angle,polar);
  close(top[0],bottom[0]);assert(top[1]<bottom[1]);
 }
});
test('traslación de pantalla se invierte sin alterar la profundidad en cualquier orientación',()=>{
 for(const a of [-2.4,-.3,1.8])for(const p of [.01,.7,1.7,Math.PI-.01]){
  const world=nav.screenDelta(37,-18,a,p),screen=nav.project(world,a,p);
  close(screen[0],37);close(screen[1],-18);close(nav.depth(world,a,p),0);
 }
});
test('órbita usa el alto de visor para ambos movimientos y evita ambos polos',()=>{
 const start={azimuth:.5,polar:1};let moved=nav.orbit(start.azimuth,start.polar,100,50,400);
 close(moved.azimuth,.5-Math.PI/2);close(moved.polar,1-Math.PI/4);
 assert.equal(nav.orbit(.5,1,0,1000,400).polar,.01);
 assert.equal(nav.orbit(.5,1,0,-1000,400).polar,Math.PI-.01);
 assert.deepEqual(nav.orbit(.5,1,5,5,0),start);
});
test('rueda usa zoom de 1.2, normaliza líneas/páginas y distingue Control físico del pinch',()=>{
 close(nav.wheelFactor({deltaY:-100}),1/1.2);close(nav.wheelFactor({deltaY:100}),1.2);
 close(nav.wheelFactor({deltaY:6.25,deltaMode:1}),1.2);close(nav.wheelFactor({deltaY:1,deltaMode:2}),1.2);
 close(nav.wheelFactor({deltaY:10,ctrlKey:true}),1.2);
 close(nav.wheelFactor({deltaY:100,ctrlKey:true},true),1.2);
 close(nav.wheelFactor({deltaY:0}),1);assert(Number.isFinite(nav.wheelFactor({deltaY:Infinity})));
});
test('anclaje de zoom conserva el punto bajo el cursor con la escala devuelta',()=>{
 const view={x:-200,y:-50,w:400,h:200},u=.23,v=.71,f=nav.wheelFactor({deltaY:-100});
 const before=[view.x+u*view.w,view.y+v*view.h];
 const next={x:view.x+u*view.w*(1-f),y:view.y+v*view.h*(1-f),w:view.w*f,h:view.h*f};
 close(next.x+u*next.w,before[0]);close(next.y+v*next.h,before[1]);
});
function fakeSurface(){
 class Surface{
  constructor(){this.listeners=new Map();this.dataset={};this.style={touchAction:'auto'};this.classes=new Set();this.captures=new Set();this.classList={toggle:(name,on)=>on?this.classes.add(name):this.classes.delete(name)};}
  addEventListener(type,fn){if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(fn);}
  removeEventListener(type,fn){this.listeners.get(type)?.delete(fn);}
  setPointerCapture(id){this.captures.add(id);}hasPointerCapture(id){return this.captures.has(id);}releasePointerCapture(id){this.captures.delete(id);}
  emit(type,attrs={}){const e={pointerId:1,pointerType:'mouse',button:0,clientX:10,clientY:20,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...attrs};for(const fn of this.listeners.get(type)||[]){fn(e);if(e.stopped)break;}return e;}
 }
 const win=new Surface(),doc=new Surface(),canvas=new Surface();doc.defaultView=win;canvas.ownerDocument=doc;return {win,doc,canvas};
}
test('botón central desplaza, modificadores orbitan solo en 3D, y cancelar permite volver al zoom',()=>{
 const {canvas,doc,win}=fakeSurface(),calls=[];let view='iso';
 const bound=nav.bind(canvas,{getView:()=>view,onPan:(...args)=>calls.push(['pan',...args]),onOrbit:(...args)=>calls.push(['orbit',...args]),onZoom:(...args)=>calls.push(['zoom',...args])});
 canvas.emit('pointerdown');doc.emit('pointermove',{clientX:40});doc.emit('pointerup');assert.equal(calls.length,0,'Izquierdo conserva selección.');
 assert(canvas.emit('pointerdown',{button:1}).prevented);
 doc.emit('pointermove',{clientX:15,clientY:26});assert.deepEqual(calls.pop(),['pan',5,6]);
 canvas.emit('wheel',{deltaY:-100});assert.equal(calls.length,0,'No se aplica zoom durante un arrastre.');doc.emit('pointerup');
 canvas.emit('pointerdown',{button:1,shiftKey:true});doc.emit('pointermove',{clientX:15,clientY:26});assert.deepEqual(calls.pop(),['orbit',5,6]);assert(canvas.classes.has('orbiting'));
 doc.emit('pointercancel');assert(!canvas.classes.has('dragging'));
 view='plan';canvas.emit('pointerdown',{button:1,ctrlKey:true});doc.emit('pointermove',{clientX:15,clientY:26});assert.deepEqual(calls.pop(),['pan',5,6]);win.emit('blur');
 canvas.emit('wheel',{deltaY:-100});assert.equal(calls[0][0],'zoom');close(calls[0][1],1/1.2);
 bound.destroy();assert.equal(canvas.style.touchAction,'auto');assert.equal(canvas.captures.size,0);assert([...doc.listeners.values()].every(s=>!s.size));
});
test('tacto conserva el tap, desplaza con un dedo y pinza en el centro sin órbita ni selección accidental',()=>{
 const {canvas,doc}=fakeSurface(),calls=[];
 const bound=nav.bind(canvas,{onPan:(...args)=>calls.push(['pan',...args]),onOrbit:()=>assert.fail('El gesto táctil no orbita.'),onZoom:(...args)=>calls.push(['zoom',...args])});
 canvas.emit('pointerdown',{pointerType:'touch'});doc.emit('pointerup',{pointerType:'touch'});
 assert(!canvas.emit('click',{pointerType:'touch'}).prevented,'Un tap normal conserva la selección.');
 canvas.emit('pointerdown',{pointerType:'touch'});doc.emit('pointermove',{pointerType:'touch',clientX:30});doc.emit('pointerup',{pointerType:'touch'});
 assert.deepEqual(calls.pop(),['pan',20,0]);
 assert(!canvas.emit('click',{pointerType:'mouse'}).stopped,'Cambiar del gesto táctil al mouse no bloquea su clic real.');
 assert(canvas.emit('click',{pointerType:'touch'}).stopped,'El arrastre no selecciona el elemento situado bajo el dedo.');
 canvas.emit('pointerdown',{pointerType:'touch',pointerId:1,clientX:0,clientY:0});
 canvas.emit('pointerdown',{pointerType:'touch',pointerId:2,clientX:100,clientY:0});
 doc.emit('pointermove',{pointerType:'touch',pointerId:2,clientX:120,clientY:0});
 assert.deepEqual(calls[0],['pan',10,0]);assert.equal(calls[1][0],'zoom');close(calls[1][1],Math.pow(1.2,-nav.ZOOM_SPEED));assert.deepEqual(calls[1].slice(2),[60,0]);
 bound.destroy();
});
