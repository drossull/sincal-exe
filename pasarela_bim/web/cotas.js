/* Arrowheads measured from GSG_COTAS in FORMATOS ANOTATIVOS ACAD_2025.dwg.
   DIMASZ = DIMTXT = 2.5; DIMTSZ = DIMSAH = 0; closed filled, base width = L/3.
   Drawing units are converted to preview text size, never to model dimensions. */
(function(root){
  'use strict';
  function arrowPair(a,b,textSize){
    if(![...a,...b,textSize].every(Number.isFinite)||textSize<=0)return null;
    const dx=b[0]-a[0],dy=b[1]-a[1],span=Math.hypot(dx,dy);if(span<1e-8)return null;
    const u=[dx/span,dy/span],n=[-u[1],u[0]],length=textSize;
    const outside=span<length*2.5,sign=outside?-1:1;
    const head=(tip,direction)=>[tip,[tip[0]+u[0]*length*direction+n[0]*length/6,tip[1]+u[1]*length*direction+n[1]*length/6],[tip[0]+u[0]*length*direction-n[0]*length/6,tip[1]+u[1]*length*direction-n[1]*length/6]];
    return {outside,heads:[head(a,sign),head(b,-sign)],extensions:outside?[
      [a,[a[0]-u[0]*length*1.4,a[1]-u[1]*length*1.4]],
      [b,[b[0]+u[0]*length*1.4,b[1]+u[1]*length*1.4]]]:[]};
  }
  function appendArrows(svg,group,a,b,{textSize=10,color='#738c9b',onPoint=()=>{}}={}){
    const pair=arrowPair(a,b,textSize);if(!pair)return;
    for(const [start,end] of pair.extensions){onPoint(start);onPoint(end);group.append(svg('line',{class:'dimension-arrow-extension',x1:start[0],y1:start[1],x2:end[0],y2:end[1],stroke:color,'stroke-width':.85,'vector-effect':'non-scaling-stroke'}));}
    pair.heads.forEach((points,i)=>{
      points.forEach(onPoint);
      group.append(svg('polygon',{class:'dimension-arrowhead','data-arrow-style':'GSG_COTAS','data-arrow-end':i===0?'start':'end','data-arrow-outside':pair.outside,points:points.map(p=>p.join(',')).join(' '),fill:color,stroke:'none'}));
    });
  }
  root.DimensionStyle={arrowPair,appendArrows};
  if(typeof module!=='undefined')module.exports=root.DimensionStyle;
})(typeof window!=='undefined'?window:globalThis);
