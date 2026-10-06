// Exercise the actual UI animation across a complete cycle without CAD or a server.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(path.join(__dirname,'../sincal/web/static/app.js'),'utf8');
const animation=source.slice(source.indexOf('function animateBridge('),source.indexOf('async function artifact('));
const shapes=[];
const context=vm.createContext({activeJob:true,motion:{namespaceURI:'svg',replaceChildren(){shapes.length=0;},append(shape){shapes.push(shape.points);}},document:{createElementNS(){return {setAttribute(name,value){this[name]=value;}};}},matchMedia:()=>({matches:false}),requestAnimationFrame(){}});
vm.runInContext(animation,context);
let fullWidthSeen=false;
for(let ms=0;ms<=1200;ms++){
  vm.runInContext(`animateBridge(${ms})`,context);
  const polygons=shapes.map(s=>s.split(' ').map(p=>p.split(',').map(Number)));
  const deckRight=Math.max(...polygons[0].map(p=>p[0]));
  for(const points of polygons.slice(1)){
    for(const [x,y] of points){assert(x>=0&&x<=deckRight+1e-9);assert(y>=.18*54-1e-9&&y<=54);}
    const width=points[1][0]-points[0][0];
    assert(width<=.047*1.15*88+1e-9);
    if(Math.abs(width-.047*1.15*88)<1e-9)fullWidthSeen=true;
  }
}
assert(fullWidthSeen);
console.log('OK: 1201 animation frames stay inside the deck; vertical bars are 15% wider.');
