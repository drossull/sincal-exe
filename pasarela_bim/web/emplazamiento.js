"use strict";
(function(root) {
  const NS = "http://www.w3.org/2000/svg";
  const plan = model => model?.emplazamiento?.planta;
  function checked(model) {
    const p = plan(model);
    if (!p) return null;
    if (p.unidades !== "m" || p.marco !== "este_norte" || !Array.isArray(p.capas) || p.capas.some(c=>typeof c!=="string") || !Array.isArray(p.entidades) || p.entidades.length > 25000) throw new Error("La planta de referencia no tiene un formato compatible.");
    let count = 0;
    for (const e of p.entidades) {
      if (!e || typeof e.capa !== "string" || !Array.isArray(e.puntos_m)) throw new Error("Entidad de planta no válida.");
      count += e.puntos_m.length;
      if (count > 250000 || e.puntos_m.some(pt => !Array.isArray(pt) || pt.length !== 3 || pt.some(v => typeof v !== "number" || !Number.isFinite(v) || Math.abs(v) > 1e12))) throw new Error("La planta contiene coordenadas no válidas o demasiados puntos.");
    }
    return p;
  }
  function local(model, p) {
    const xyz = root.ProjectIO.worldToLocal(model,p[0],p[1]);
    // A plan is a 2D reference. Its Z values are retained in JSON but not treated as a terrain surface.
    return [xyz[0]*1000,xyz[1]*1000,0];
  }
  function bounds(model) {
    const p = checked(model); if (!p || p.visible === false) return [];
    const hidden = new Set(p.capas_ocultas || []);
    let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
    for (const e of p.entidades) if (!hidden.has(e.capa)) for (const pt of e.puntos_m) {
      const [x,y] = local(model,pt); minX=Math.min(x,minX);minY=Math.min(y,minY);maxX=Math.max(x,maxX);maxY=Math.max(y,maxY);
    }
    return Number.isFinite(minX) ? [[minX,minY,0],[maxX,maxY,0]] : [];
  }
  function svg(model,project) {
    const g = document.createElementNS(NS,"g");g.setAttribute("class","site-plan");g.setAttribute("aria-label","Planta de referencia");g.style.pointerEvents="none";
    const p = checked(model);if (!p || p.visible === false) return g;
    const hidden = new Set(p.capas_ocultas || []);
    for (const e of p.entidades) {
      if (hidden.has(e.capa) || !e.puntos_m.length) continue;
      const pts=e.puntos_m.map(pt=>project(...local(model,pt)));
      const node=document.createElementNS(NS,e.texto!==undefined?"text":pts.length===1?"circle":"polyline");
      if(e.texto!==undefined){node.textContent=e.texto;node.setAttribute("x",pts[0][0]);node.setAttribute("y",pts[0][1]);node.setAttribute("font-size","7");node.setAttribute("fill","#87959d");}
      else if(pts.length===1){node.setAttribute("cx",pts[0][0]);node.setAttribute("cy",pts[0][1]);node.setAttribute("r","1");node.setAttribute("fill","#87959d");}
      else{node.setAttribute("points",pts.map(pt=>pt.join(",")).join(" "));node.setAttribute("fill","none");node.setAttribute("stroke","#9baab1");node.setAttribute("stroke-width",".8");node.setAttribute("vector-effect","non-scaling-stroke");}
      g.append(node);
    }
    return g;
  }
  async function load(file,model) {
    root.ProjectIO.worldToLocal(model,0,0);
    if (!/\.(dwg|dxf)$/i.test(file.name) || file.size>20*1024*1024) throw new Error("Selecciona una planta DWG o DXF de hasta 20 MB.");
    const response=await fetch("/api/planta",{method:"POST",headers:{"Content-Type":"application/octet-stream","X-Pasarela-Token":document.querySelector('meta[name="pasarela-token"]').content,"X-File-Name":encodeURIComponent(file.name)},body:file});
    let data;try{data=await response.json();}catch(_){throw new Error("No se recibió una planta válida del servidor.");}
    if(!response.ok)throw new Error(data.mensaje||"No se pudo cargar la planta.");
    checked({emplazamiento:{planta:data}});return data;
  }
  function status(model){const p=plan(model);return p?`${p.nombre} · ${p.entidades.length} entidades · ${p.capas.length} capas`:"Sin planta de referencia";}
  root.SitePlan={load,svg,bounds,status,checked};
})(typeof window!=="undefined"?window:globalThis);
