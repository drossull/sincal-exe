"use strict";
(function(root){
  const interpolate=(points,t,key)=>{if(t<=points[0].t)return points[0][key];for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(t<=b.t)return a[key]+(b[key]-a[key])*(t-a.t)/(b.t-a.t);}return points.at(-1)[key];};
  function faces(model,edge){
    const a=model.nodos.find(n=>n.id===edge.desde),b=model.nodos.find(n=>n.id===edge.hasta),f=model.familias[edge.familia];
    if(!a||!b||!f)return[];
    const dx=b.x-a.x,dy=b.y-a.y,L=Math.hypot(dx,dy),w=edge.ancho_mm;
    if(!Number.isFinite(L)||L<=0||!Number.isFinite(w)||w<=0||!Number.isFinite(f.canto_mm)||f.canto_mm<=0)return[];
    const start=(edge.retranqueo_inicio_mm||0)/L,end=1-(edge.retranqueo_fin_mm||0)/L;
    if(start>=end)return[];
    const ux=dx/L,uy=dy/L,grade=edge.rasante||[{t:0,f:0},{t:1,f:1}],depth=f.perfil_canto||[{t:0,canto_mm:f.canto_mm},{t:1,canto_mm:f.canto_fin_mm||f.canto_mm}];
    if(!grade.length||!depth.length)return[];
    const centre=t=>[a.x+dx*t,a.y+dy*t,a.z+(b.z-a.z)*interpolate(grade,t,'f')];
    const place=(c,v,z)=>[c[0]-uy*v,c[1]+ux*v,c[2]+z];
    const output=[];
    if(f.tipo==='escalera'){
      const count=f.numero_peldanos;if(!Number.isInteger(count)||count<1||count>1000)return[];
      const descending=a.z>b.z,lo=centre(descending?end:start),hi=centre(descending?start:end),D=(end-start)*L,H=hi[2]-lo[2],sx=(hi[0]-lo[0])/D,sy=(hi[1]-lo[1])/D;
      const profile=[[0,0]];
      for(let i=0;i<count;i++)profile.push([D*i/count,H*(i+1)/count],[D*(i+1)/count,H*(i+1)/count]);
      profile.push([D,H-f.canto_mm],[0,-f.canto_mm]);
      const strip=side=>profile.map(([s,z])=>[lo[0]+sx*s-sy*side*w/2,lo[1]+sy*s+sx*side*w/2,lo[2]+z]);
      const left=strip(-1),right=strip(1);output.push(left,right);
      for(let i=0;i<profile.length;i++){const j=(i+1)%profile.length;output.push([left[i],left[j],right[j],right[i]]);}
    }else{
      const ts=[...new Set([start,end,...grade.map(p=>p.t),...depth.map(p=>p.t)].filter(t=>t>=start&&t<=end))].sort((x,y)=>x-y);
      const sections=ts.map(t=>{
        const c=centre(t),h=interpolate(depth,t,'canto_mm');
        const profile=f.tipo==='cajon'?[[-w/2,0],[w/2,0],[w/2,-(f.losa_superior_mm||h/4)],[(f.ancho_alma_superior_mm||w)/2,-(f.losa_superior_mm||h/4)],[(f.ancho_inferior_mm||w)/2,-h],[-(f.ancho_inferior_mm||w)/2,-h],[-(f.ancho_alma_superior_mm||w)/2,-(f.losa_superior_mm||h/4)],[-w/2,-(f.losa_superior_mm||h/4)]]:[[-w/2,0],[w/2,0],[w/2,-h],[-w/2,-h]];
        return profile.map(([v,z])=>place(c,v,z));
      });
      output.push(sections[0],sections.at(-1));
      for(let i=1;i<sections.length;i++)for(let j=0;j<sections[i].length;j++){const k=(j+1)%sections[i].length;output.push([sections[i-1][j],sections[i][j],sections[i][k],sections[i-1][k]]);}
    }
    return output.filter(poly=>poly.every(pt=>pt.every(Number.isFinite)));
  }
  function edge(model,connection,project,view,active){
    const NS='http://www.w3.org/2000/svg',g=document.createElementNS(NS,'g');g.setAttribute('class','volume-preview');g.style.pointerEvents='none';
    const polygons=faces(model,connection);
    if(view==='iso')polygons.sort((a,b)=>a.reduce((s,p)=>s+p[0]+p[1]+p[2],0)/a.length-b.reduce((s,p)=>s+p[0]+p[1]+p[2],0)/b.length);
    for(const polygon of polygons){
      const poly=document.createElementNS(NS,'polygon');poly.setAttribute('points',polygon.map(p=>project(...p).join(',')).join(' '));
      poly.setAttribute('fill',active?'#b8dae8':connection.funcion==='escalera'?'#d6ddd0':'#d5e1e5');poly.setAttribute('stroke',active?'#4382a1':'#94abb6');poly.setAttribute('stroke-width','.6');poly.setAttribute('vector-effect','non-scaling-stroke');g.append(poly);
    }
    return g;
  }
  root.VolumePreview={edge,faces};if(typeof module!=='undefined')module.exports=root.VolumePreview;
})(typeof window!=='undefined'?window:globalThis);
