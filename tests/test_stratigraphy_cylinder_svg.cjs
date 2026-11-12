// Exercise the shared SVG renderer with exact elliptical scene primitives.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
class Element{
  constructor(tag){this.tag=tag;this.attrs={};this.children=[];this.textContent='';}
  setAttribute(name,value){this.attrs[name]=String(value);}
  append(child){this.children.push(child);}
}
global.document={createElementNS:(_,tag)=>new Element(tag),createTextNode:text=>({tag:'#text',textContent:text,children:[]})};
const descendants=element=>[element,...element.children.flatMap(descendants)];
(async()=>{
  const root=path.resolve(__dirname,'../sincal/web/static');
  const moduleUrl=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
  const source=fs.readFileSync(path.join(root,'stratigraphy.js'),'utf8').replace("'/study_info.js'",JSON.stringify(moduleUrl(fs.readFileSync(path.join(root,'study_info.js'),'utf8'))));
  const {renderScene,patternPath}=await import(moduleUrl(source));
  const ellipse=(y,start,end)=>({kind:'ellipse',point:[10,y],rx:7,ry:3.5,start,end,color:1});
  const boundary=[ellipse(5,Math.PI,0),{kind:'line',points:[[17,5],[17,20]]},ellipse(20,0,Math.PI),{kind:'line',points:[[3,20],[3,5]]}];
  const hatches={arena:{lines:[[45,0,0,0,1,[]]]}};
  const scene={viewbox:[0,0,30,30],items:[
    {kind:'hatch',bounds:[3,5,17,23.5],boundary,material:'arena',color:8},
    ellipse(5,0,2*Math.PI),ellipse(20,0,Math.PI),ellipse(5,Math.PI,0),
    {kind:'text',point:[10,27],anchor:'center',text:'H1 · 2 m',color:3},
  ]};
  const svg=renderScene(scene,hatches),all=descendants(svg);
  const clip=all.find(element=>element.tag==='clipPath');
  assert.equal(clip.attrs.clipPathUnits,'userSpaceOnUse');
  assert.equal((clip.children[0].attrs.d.match(/A/g)||[]).length,2);
  assert.equal((clip.children[0].attrs.d.match(/L/g)||[]).length,2);
  assert(clip.children[0].attrs.d.endsWith('Z'));
  assert(clip.children[0].attrs.d.includes('A7,3.5 0 0 0 '));
  assert(clip.children[0].attrs.d.includes('A7,3.5 0 0 1 '));
  const hatch=all.find(element=>element.attrs?.['clip-path']);
  assert.equal(hatch.attrs['clip-path'],`url(#${clip.attrs.id})`);
  assert.equal(hatch.attrs.stroke,'#808080');
  assert.equal(hatch.attrs.d,patternPath(scene.items[0].bounds,hatches.arena.lines));
  const curves=svg.children.filter(element=>element.tag==='path'&&!element.attrs['clip-path']);
  assert.deepEqual(curves.map(element=>(element.attrs.d.match(/A/g)||[]).length),[2,1,1]);
  assert(curves.every(element=>!element.attrs.d.includes('L')&&element.attrs.stroke==='#ff5959'));
  const text=all.find(element=>element.tag==='text');
  assert.equal(text.attrs.fill,'#68f778');assert.equal(text.attrs['font-size'],'2.5');
  const second=descendants(renderScene(scene,hatches)).find(element=>element.tag==='clipPath');
  assert.notEqual(second.attrs.id,clip.attrs.id,'Separate previews must not share clip identifiers');
  const legacy=renderScene({viewbox:[0,0,20,30],items:[{kind:'hatch',bounds:[3,5,17,20],material:'arena',color:8}]},hatches);
  assert.equal(legacy.children.length,1);assert.equal(legacy.children[0].attrs.stroke,'#b5b5b5');
  assert.equal(legacy.children[0].attrs['clip-path'],undefined);
  console.log('OK: exact full/reversed elliptical arcs, closed hatch clipping, unique IDs, C1/C8/C3 and unchanged rectangular hatch rendering.');
})().catch(error=>{console.error(error);process.exitCode=1;});
