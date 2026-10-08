// Exercise the actual SVG renderer without a browser or added dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
class Element {
  constructor(tag) { this.tag=tag; this.attrs={}; this.children=[]; this.textContent=''; }
  setAttribute(name,value) { this.attrs[name]=String(value); }
  append(child) { this.children.push(child); }
}
global.document = {
  createElementNS: (_, tag) => new Element(tag),
  createTextNode: text => ({tag:'#text',textContent:text,children:[]}),
};
(async()=>{
  const source=fs.readFileSync(path.join(__dirname,'../sincal/web/static/stratigraphy.js'),'utf8');
  const {renderScene}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const svg=renderScene({viewbox:[0,0,100,100],items:[
    {kind:'text',point:[5,5],color:3,anchor:'left',text:'NSPT (GOLPES/PIE)\nNSPT A PROFUNDIDAD DESDE'},
    {kind:'text',point:[5,20],color:3,anchor:'left',text:'VS = 608 - 676 m/s'},
    {kind:'line',points:[[1,1],[2,2]],color:1},
    {kind:'triangle',points:[[1,1],[2,2],[1,2]],color:1},
  ]},{});
  const descendants=el=>[el,...el.children.flatMap(descendants)];
  const all=descendants(svg);
  const subs=all.filter(el=>el.attrs?.['baseline-shift']==='sub');
  assert.equal(subs.length,2);
  assert.ok(subs.every(el=>el.textContent==='SPT' && el.attrs['font-size']==='70%'));
  assert.ok(all.some(el=>el.textContent==='N'));
  assert.ok(all.some(el=>el.textContent==='VS = 608 - 676 m/s'));
  assert.equal(all.find(el=>el.tag==='line').attrs.stroke,'#ff5959');
  assert.equal(all.find(el=>el.tag==='polygon').attrs.fill,'#ff5959');
  console.log('OK: SVG subscript, multiline labels, units, C1 lines and arrowheads.');
})().catch(error=>{console.error(error);process.exitCode=1;});
