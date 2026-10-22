/* Project exchange uses metres. Only the CAD adapter/editor internals use mm. */
"use strict";
(function (root) {
  const collections = ["nodos", "tramos", "familias", "fundaciones", "soportes"];
  const copy = value => JSON.parse(JSON.stringify(value));
  const uid = () => root.crypto?.randomUUID?.() || `p-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  function dimensions(value, from, to, factor) {
    if (Array.isArray(value)) return value.map(v => dimensions(v, from, to, factor));
    if (!value || typeof value !== "object") return value;
    const result = {};
    for (const [key, item] of Object.entries(value)) {
      if (["metadatos","georreferencia","fuente","revision"].includes(key)) {result[key]=copy(item);continue;}
      const dimensional = key.endsWith(from);
      const target = dimensional ? key.slice(0, -from.length) + to : key;
      if (target !== key && Object.hasOwn(value, target)) throw new Error(`Dimensión duplicada: ${key} / ${target}.`);
      result[target] = dimensional ? (typeof item === "number" ? item * factor : copy(item)) : dimensions(item, from, to, factor);
      if (typeof result[target] === "number" && !Number.isFinite(result[target])) throw new Error(`Dimensión fuera de rango: ${key}.`);
    }
    return result;
  }
  function convert(model, portable) {
    if (!model || typeof model !== "object" || Array.isArray(model)) throw new Error("El proyecto debe ser un objeto JSON.");
    const version = model.version;
    if (version !== 1 && version !== 2) throw new Error("Versión de proyecto no compatible; se admite 1 o 2.");
    const expected = version === 2 ? "m" : "mm";
    if (model.proyecto?.unidades !== expected) throw new Error(`La versión ${version} requiere unidades ${expected}.`);
    if ((portable && version === 2) || (!portable && version === 1)) return copy(model);
    const result = copy(model), factor = portable ? .001 : 1000;
    for (const key of collections) if (result[key] !== undefined) {
      const dim = v => dimensions(v, portable ? "_mm" : "_m", portable ? "_m" : "_mm", factor);
      result[key] = key === "familias" && result[key] && !Array.isArray(result[key]) ? Object.fromEntries(Object.entries(result[key]).map(([id,f])=>[id,dim(f)])) : dim(result[key]);
    }
    for (const node of result.nodos || []) for (const axis of ["x", "y", "z"]) if (typeof node[axis] === "number") node[axis] *= factor;
    result.version = portable ? 2 : 1;
    result.proyecto.unidades = portable ? "m" : "mm";
    if (!portable) result.proyecto.esquema_intercambio = 2;
    return result;
  }
  // Keep the explicit X-based exchange field compatible with existing JSON.
  // The editor presents clockwise angles from +Y: Y = (X + 90) mod 360.
  function northAngleFromY(reference = {}) {
    return ((Number(reference.norte_desde_x_horario_deg ?? 270) + 90) % 360 + 360) % 360;
  }
  function newProject(params = {}) {
    let northFromX = Number(params.norte_desde_x_horario_deg ?? 270);
    if (params.norte_desde_y_horario_deg !== undefined) {
      const angle = Number(params.norte_desde_y_horario_deg);
      if (!Number.isFinite(angle) || angle < 0 || angle >= 360) throw new Error("El ángulo al norte desde Y debe estar entre 0 incluido y 360 excluido.");
      northFromX = (angle + 270) % 360;
    }
    return {
      version: 1,
      proyecto: {
        id: uid(), nombre: params.nombre || params.name || "Nueva pasarela", estado: "borrador", unidades: "mm",
        revision: 0, motor: "pasarela-bim", version_motor: "0.3.2", esquema_intercambio: 2,
        reglas: {pendiente_rampas_pct: 8},
        georreferencia: {este_m: Number(params.este_m || 0), norte_m: Number(params.norte_m || 0), cota_m: Number(params.cota_m || 0), norte_desde_x_horario_deg: northFromX, crs: params.crs || "Por definir"},
        galibo_m: Number(params.galibo_mm ?? 5500) / 1000,
        referencia_vertical: "tope_atravieso",
        origen_local: "Punto medio del atravieso en la cara superior de la viga sobre su eje; X atravieso, Y transversal local, Z arriba."
      },
      nodos: [], tramos: [], soportes: [], fundaciones: [], ejes: [],
      familias: {
        cajon: {tipo:"cajon", pendiente_transversal_pct:1, canto_mm:1000, ancho_inferior_mm:1000, ancho_alma_superior_mm:1260, ala_mm:370, losa_superior_mm:150, losa_inferior_mm:150, alma_mm:140, macizado_mm:500, estado:"dimensiones_iniciales_editables"},
        losa: {tipo:"maciza", pendiente_transversal_pct:1, canto_mm:250, estado:"dimensiones_iniciales_editables"},
        escalera: {tipo:"escalera", canto_mm:200, numero_peldanos:12, estado:"dimensiones_iniciales_editables"}
      },
      pendientes_documentales: [], simplificaciones: [], vistas: []
    };
  }
  function reference(model) {
    const g = model.proyecto?.georreferencia || model.georreferencia;
    if (!g || ![g.este_m,g.norte_m,g.cota_m,g.norte_desde_x_horario_deg].every(Number.isFinite)) throw new Error("Define primero Este, Norte, cota y orientación del proyecto.");
    return g;
  }
  function localToWorld(model, x, y, z = 0) {
    const g = reference(model), a = g.norte_desde_x_horario_deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    return [g.este_m - x*s - y*c, g.norte_m + x*c - y*s, g.cota_m + z];
  }
  function worldToLocal(model, east, north, elevation) {
    const g = reference(model), a = g.norte_desde_x_horario_deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), e = east-g.este_m, n = north-g.norte_m;
    return [-e*s+n*c, -e*c-n*s, elevation === undefined ? 0 : elevation-g.cota_m];
  }
  function rebaseToCrossing(model){
    const result=copy(model),primary=(result.ejes||[]).find(a=>a.principal&&a.tipo==='atravieso');
    const edges=primary?primary.tramos.map(id=>result.tramos.find(e=>e.id===id)):(result.tramos||[]).filter(e=>e.funcion==='cruce');
    if(!edges.length||edges.some(e=>!e))throw new Error("Define el eje principal del atravieso para situar su origen vertical.");
    const links=new Map();for(const e of edges)for(const id of [e.desde,e.hasta]){if(!links.has(id))links.set(id,[]);links.get(id).push(e);}
    const ends=[...links].filter(([,es])=>es.length===1).map(([id])=>id);
    if(ends.length!==2||[...links.values()].some(es=>es.length>2))throw new Error("El atravieso principal debe ser un recorrido continuo sin bifurcaciones.");
    const segments=[],seen=new Set();let id=ends[0];
    while(true){const e=links.get(id)?.find(e=>!seen.has(e.id));if(!e)break;seen.add(e.id);const next=e.desde===id?e.hasta:e.desde,a=result.nodos.find(n=>n.id===id),b=result.nodos.find(n=>n.id===next);if(!a||!b)throw new Error("Faltan nodos del atravieso.");const length=Math.hypot(b.x-a.x,b.y-a.y);segments.push({e,a,b,length,forward:e.desde===id});id=next;}
    if(seen.size!==edges.length)throw new Error("El atravieso tiene tramos desconectados.");
    let remaining=segments.reduce((sum,s)=>sum+s.length,0)/2,shift;
    for(const s of segments){if(remaining>s.length){remaining-=s.length;continue;}if(s.length<=0)throw new Error("El atravieso no tiene longitud válida.");const t=s.forward?remaining/s.length:1-remaining/s.length,ps=s.e.rasante||[{t:0,f:0},{t:1,f:1}];let fraction;
      for(let i=1;i<ps.length;i++)if(t<=ps[i].t){const a=ps[i-1],b=ps[i];fraction=a.f+(b.f-a.f)*(t-a.t)/(b.t-a.t);break;}
      const a=result.nodos.find(n=>n.id===s.e.desde),b=result.nodos.find(n=>n.id===s.e.hasta);shift=a.z+(b.z-a.z)*fraction;break;
    }
    if(!Number.isFinite(shift))throw new Error("No se puede determinar la cota superior del atravieso.");
    const p=result.proyecto,g=p.georreferencia||result.georreferencia;
    if(p.georreferencia&&result.georreferencia&&JSON.stringify(p.georreferencia)!==JSON.stringify(result.georreferencia))throw new Error("Las georreferencias del archivo difieren. Unifícalas antes de cambiar el origen.");
    if(g){if(!Number.isFinite(g.cota_m))throw new Error("La cota geográfica del origen debe ser numérica.");g.cota_m+=shift/1000;if(p.georreferencia&&result.georreferencia)result.georreferencia=copy(g);}
    for(const n of result.nodos)n.z-=shift;
    for(const item of [...(result.soportes||[]),...(result.fundaciones||[])])if(Number.isFinite(item.cota_superior_mm))item.cota_superior_mm-=shift;
    for(const support of result.soportes||[])if(Number.isFinite(support.cota_terreno_proyectado_mm))support.cota_terreno_proyectado_mm-=shift;
    // Legacy global elevations remain available for round-trip compatibility,
    // but never fill missing projected terrain elevations at individual supports.
    if(Number.isFinite(p.cota_terreno_m))p.cota_terreno_m-=shift/1000;
    if(Number.isFinite(p.cota_carretera_m))p.cota_carretera_m-=shift/1000;
    p.referencia_vertical='tope_atravieso';p.origen_local='Punto medio del atravieso en la cara superior de la viga sobre su eje; X atravieso, Y transversal local, Z arriba.';
    return {model:result,shiftMm:shift};
  }
  root.ProjectIO = {rebaseToCrossing,toInternal: model => convert(model,false), toPortable: model => convert(model,true), newProject, northAngleFromY, localToWorld, worldToLocal, uid};
  if (typeof module !== "undefined") module.exports = root.ProjectIO;
})(typeof window !== "undefined" ? window : globalThis);
