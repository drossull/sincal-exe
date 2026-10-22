"use strict";
(function(root){
  const interpolate=(points,t,key)=>{if(t<=points[0].t)return points[0][key];for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(t<=b.t)return a[key]+(b[key]-a[key])*(t-a.t)/(b.t-a.t);}return points.at(-1)[key];};
  function sectionFamily(model,edge,family=model.familias[edge.familia]){
    const ps=edge.rasante||[];
    if(!family||family.tipo==='escalera'||!ps.some((p,i)=>i&&p.t>ps[i-1].t&&Math.abs(p.f-ps[i-1].f)<1e-10&&p.f>0&&p.f<1))return family;
    const a=model.nodos.find(n=>n.id===edge.desde),b=model.nodos.find(n=>n.id===edge.hasta);if(!a||!b)return family;
    const L=Math.hypot(b.x-a.x,b.y-a.y),dz=b.z-a.z;if(!(L>0)||Math.abs(dz)<1e-7)return family;
    if(ps.some((p,i)=>i&&(p.t<=ps[i-1].t||(p.f>ps[i-1].f&&Math.abs(Math.abs(dz)*(p.f-ps[i-1].f)/(L*(p.t-ps[i-1].t))-.08)>1e-8))))return family;
    const profile=ps.map(p=>({t:p.t,canto_mm:family.canto_mm+.08*L*(dz>0?1-p.t:p.t)-Math.abs(dz)*(dz>0?1-p.f:p.f)}));
    return {...family,perfil_canto:profile,canto_fin_mm:profile.at(-1).canto_mm,canto_por_descanso:true};
  }
  function faces(model,edge){
    const a=model.nodos.find(n=>n.id===edge.desde),b=model.nodos.find(n=>n.id===edge.hasta),f=sectionFamily(model,edge);
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
        const drop=(f.pendiente_transversal_pct??1)*w/200;
        if(drop>0)profile.splice(0,2,[-w/2,-drop],[0,0],[w/2,-drop]);
        return profile.map(([v,z])=>place(c,v,z));
      });
      output.push(sections[0],sections.at(-1));
      for(let i=1;i<sections.length;i++)for(let j=0;j<sections[i].length;j++){const k=(j+1)%sections[i].length;output.push([sections[i-1][j],sections[i][j],sections[i][k],sections[i-1][k]]);}
    }
    return output.filter(poly=>poly.every(pt=>pt.every(Number.isFinite)));
  }
  function longitudinalSection(model,e){
    const a=model.nodos.find(n=>n.id===e.desde),b=model.nodos.find(n=>n.id===e.hasta),f=sectionFamily(model,e);
    if(!a||!b||!f)return null;
    const L=Math.hypot(b.x-a.x,b.y-a.y),start=e.retranqueo_inicio_mm||0,end=L-(e.retranqueo_fin_mm||0);
    if(!(L>0&&end>start))return null;
    const grade=e.rasante||[{t:0,f:0},{t:1,f:1}],depth=f.perfil_canto||[{t:0,canto_mm:f.canto_mm},{t:1,canto_mm:f.canto_fin_mm??f.canto_mm}];
    const z=s=>a.z+(b.z-a.z)*interpolate(grade,s/L,'f'),h=s=>interpolate(depth,s/L,'canto_mm');
    const stations=(lo,hi)=>[...new Set([lo,hi,...grade.map(p=>p.t*L),...depth.map(p=>p.t*L)])].filter(s=>s>=lo&&s<=hi).sort((a,b)=>a-b);
    const ts=stations(start,end);let upper=ts.map(s=>[s,z(s)]),lower=ts.map(s=>[s,z(s)-h(s)]),inner=[];
    if(f.tipo==='escalera'){
      const n=f.numero_peldanos,ascending=b.z>=a.z,lo=ascending?start:end,hi=ascending?end:start,run=(end-start)/n,rise=Math.abs(z(end)-z(start))/n;
      if(!Number.isInteger(n)||n<=0)return null;
      upper=[[lo,z(lo)]];for(let i=0;i<n;i++)upper.push([lo+(ascending?1:-1)*i*run,z(lo)+(i+1)*rise],[lo+(ascending?1:-1)*(i+1)*run,z(lo)+(i+1)*rise]);
      lower=[[lo,z(lo)-f.canto_mm],[hi,z(hi)-f.canto_mm]];
    }else if(f.tipo==='cajon'){
      const solid=f.macizado_mm??500,lo=start+solid,hi=end-solid;
      if(hi>lo){const ss=stations(lo,hi);inner=[...ss.map(s=>[s,z(s)-f.losa_superior_mm]),...ss.slice().reverse().map(s=>[s,z(s)-h(s)+f.losa_inferior_mm])];}
    }
    return {length:L,outer:[...upper,...lower.slice().reverse()],inner};
  }
  // Match the conceptual wedges created by freecad_backend._capitel_shape.
  function capitals(model,support){
    const node=model.nodos.find(n=>n.id===support.nodo),base=support.cota_superior_mm;
    if(!node||!Number.isFinite(base))return [];
    const diameter=support.diametro_mm??1000,parts=[];
    for(const e of model.tramos.filter(e=>e.desde===node.id||e.hasta===node.id)){
      const a=model.nodos.find(n=>n.id===e.desde),b=model.nodos.find(n=>n.id===e.hasta),f=sectionFamily(model,e);
      if(!a||!b||!f)return [];
      const L=Math.hypot(b.x-a.x,b.y-a.y);if(L<=0)return [];
      const start=e.desde===node.id,sign=start?1:-1,ux=(b.x-a.x)/L*sign,uy=(b.y-a.y)/L*sign;
      const retreat=(start?e.retranqueo_inicio_mm:e.retranqueo_fin_mm)||0;
      const extent=Math.max(diameter/2+150,retreat+400),width=Math.max(diameter+200,Math.min(e.ancho_mm,1400));
      const grade=e.rasante||[{t:0,f:0},{t:1,f:1}],depth=f.perfil_canto||[{t:0,canto_mm:f.canto_mm},{t:1,canto_mm:f.canto_fin_mm??f.canto_mm}];
      const stations=[-diameter/2,extent],tops=stations.map(s=>{const t=Math.max(0,Math.min(L,start?s:L-s))/L;return a.z+(b.z-a.z)*interpolate(grade,t,'f')-interpolate(depth,t,'canto_mm');});
      if(tops.some(z=>!Number.isFinite(z)||z<=base+.1))return [];
      const rings=stations.map((s,i)=>[[-width/2,base],[width/2,base],[width/2,tops[i]],[-width/2,tops[i]]].map(([v,z])=>[node.x+ux*s-uy*v,node.y+uy*s+ux*v,z]));
      const faces=[rings[0],rings[1]];for(let j=0;j<4;j++){const k=(j+1)%4;faces.push([rings[0][j],rings[1][j],rings[1][k],rings[0][k]]);}
      parts.push({edgeId:e.id,nodeId:node.id,stations,tops,base,width,faces});
    }
    return parts;
  }
  function capital(model,support,project){
    const NS='http://www.w3.org/2000/svg',group=document.createElementNS(NS,'g');group.setAttribute('class','capital-preview');group.setAttribute('pointer-events','none');
    const title=document.createElementNS(NS,'title');title.textContent=`Cabezal conceptual de ${support.nodo}; dimensiones aproximadas según los tramos conectados`;group.append(title);
    for(const part of capitals(model,support))for(const face of part.faces){const poly=document.createElementNS(NS,'polygon');poly.setAttribute('points',face.map(p=>project(...p).join(',')).join(' '));poly.setAttribute('fill','#dbc39b');poly.setAttribute('stroke','#9a7d52');poly.setAttribute('stroke-width','.7');poly.setAttribute('vector-effect','non-scaling-stroke');group.append(poly);}
    return group;
  }
  function edge(model,connection,project,view,active,orbitAngle=0){
    const NS='http://www.w3.org/2000/svg',g=document.createElementNS(NS,'g');g.setAttribute('class','volume-preview');g.style.pointerEvents='none';
    const polygons=faces(model,connection);
    if(view==='iso'){const c=Math.cos(orbitAngle),s=Math.sin(orbitAngle),depth=p=>(p[0]*c-p[1]*s)+(p[0]*s+p[1]*c)+p[2];polygons.sort((a,b)=>a.reduce((sum,p)=>sum+depth(p),0)/a.length-b.reduce((sum,p)=>sum+depth(p),0)/b.length);}
    for(const polygon of polygons){
      const poly=document.createElementNS(NS,'polygon');poly.setAttribute('points',polygon.map(p=>project(...p).join(',')).join(' '));
      poly.setAttribute('fill',active?'#b8dae8':connection.funcion==='escalera'?'#d6ddd0':'#d5e1e5');poly.setAttribute('stroke',active?'#4382a1':'#94abb6');poly.setAttribute('stroke-width','.6');poly.setAttribute('vector-effect','non-scaling-stroke');g.append(poly);
    }
    return g;
  }
  root.VolumePreview={edge,faces,capitals,capital,longitudinalSection,sectionFamily};if(typeof module!=='undefined')module.exports=root.VolumePreview;
})(typeof window!=='undefined'?window:globalThis);
