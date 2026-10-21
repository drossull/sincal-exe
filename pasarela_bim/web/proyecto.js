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
  function newProject(params = {}) {
    return {
      version: 1,
      proyecto: {
        id: uid(), nombre: params.nombre || params.name || "Nueva pasarela", estado: "borrador", unidades: "mm",
        revision: 0, motor: "pasarela-bim", version_motor: "0.3.1", esquema_intercambio: 2,
        reglas: {pendiente_rampas_pct: 8},
        georreferencia: {este_m: Number(params.este_m || 0), norte_m: Number(params.norte_m || 0), cota_m: Number(params.cota_m || 0), norte_desde_x_horario_deg: Number(params.norte_desde_x_horario_deg ?? 270), crs: params.crs || "Por definir"},
        galibo_m: Number(params.galibo_mm ?? 5500) / 1000, cota_carretera_m: Number(params.cota_carretera_mm || 0) / 1000,
        origen_local: "Punto medio del atravieso al nivel del terreno; X atravieso, Y transversal local, Z arriba."
      },
      nodos: [], tramos: [], soportes: [], fundaciones: [], ejes: [],
      familias: {
        cajon: {tipo:"cajon", canto_mm:1000, ancho_inferior_mm:1000, ancho_alma_superior_mm:1260, ala_mm:370, losa_superior_mm:150, losa_inferior_mm:150, alma_mm:140, macizado_mm:500, estado:"dimensiones_iniciales_editables"},
        losa: {tipo:"maciza", canto_mm:250, estado:"dimensiones_iniciales_editables"},
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
  root.ProjectIO = {toInternal: model => convert(model,false), toPortable: model => convert(model,true), newProject, localToWorld, worldToLocal, uid};
  if (typeof module !== "undefined") module.exports = root.ProjectIO;
})(typeof window !== "undefined" ? window : globalThis);
