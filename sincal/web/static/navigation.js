// One navigation model for the sidebar, breadcrumbs and internal tool tabs.
export const groups={
  archivo:[['rename','Renombrado'],['convert','Conversión DXF–DWG']],
  revisiones:[['revision-editor','Editor de revisiones'],['revisions','Nueva revisión']],
  prospecciones:[['stratigraphy','Estratigrafía'],['prospect','Perfiles geofísicos']],
};
const icons={home:'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',docs:'M4 3h11l5 5v13H4ZM14 3v6h6M8 13h8M8 17h6',project:'M3 6h7l2 3h9v12H3ZM3 6V3h7l2 3h8v3',archivo:'M4 3h11l5 5v13H4ZM14 3v6h6M7 14h10M7 18h7',dwgprops:'M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6',revisiones:'M4 4h16v17H4ZM8 2v4M16 2v4M4 9h16M8 13h3M8 17h7',prospecciones:'M4 3h12v18H4ZM4 8h12M4 14h12M20 3v18M18 19l2 2 2-2',location:'M12 22s8-8 8-14a8 8 0 0 0-16 0c0 6 8 14 8 14ZM9 8a3 3 0 1 0 6 0 3 3 0 1 0-6 0',live:'M3 5h18v14H3ZM6 9l3 3-3 3M12 15h5',rebar:'M3 20V6h18v14M3 11h18M3 16h18M8 6v14M16 6v14',consulta:'M4 3h12v7M4 3v18h8M7 7h6M7 11h4M14 15a4 4 0 1 0 8 0 4 4 0 1 0-8 0M21 18l2 3',diagnostics:'M3 12h4l3-7 4 14 3-7h4'};
export const menu=[['home','Home'],['docs','Documentación'],['project','Proyecto'],['archivo','Archivo',true],['dwgprops','Propiedades',true],['revisiones','Revisiones',true],['prospecciones','Prospecciones',true],['location','Mapa de ubicación',true],['live','Comandos en vivo'],['rebar','Generador de armadura'],['consulta','Consulta de proyecto'],['diagnostics','Diagnóstico']];
const structures=[['rebar-abutments','Estribos','M4 20V4h5v11h6V4h5v16Z'],['rebar-beam','Viga','M3 7h18v10H3ZM7 7v10M17 7v10'],['rebar-pier','Cepa','M3 5h18v4H3ZM7 9v11M17 9v11M4 20h16'],['rebar-crossbeam','Travesaño','M3 7h18v10H3ZM8 3v18M16 3v18'],['rebar-slab','Losa','M3 8l10-5 8 5-10 5ZM3 8v5l8 5 10-5V8']];
menu.splice(menu.findIndex(([id])=>id==='rebar')+1,0,...structures.map(([id,label])=>[id,label,'rebar']));
for(const [id,,icon]of structures)icons[id]=icon;
export function owner(page){return Object.keys(groups).find(key=>groups[key].some(([id])=>id===page))||page;}
export function destination(page){return groups[page]?.[0][0]||page;}
export function title(page){const parent=owner(page),entry=menu.find(([id])=>id===parent);return (entry?.[2]==='rebar'?'Generador de armadura › ':entry?.[2]?'Proyecto › ':'')+(entry?.[1]||page)+(parent!==page?' › '+groups[parent].find(([id])=>id===page)[1]:'');}
export function renderNavigation(node){
  const nav=document.querySelector('#sidebar nav');nav.replaceChildren();
  for(const [id,label,child]of menu){const b=node('button',undefined,child?'subnav':'');b.dataset.page=id;
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),path=document.createElementNS(svg.namespaceURI,'path');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('class','nav-icon');svg.setAttribute('aria-hidden','true');svg.setAttribute('focusable','false');path.setAttribute('d',icons[id]);svg.append(path);b.append(svg,node('span',label));nav.append(b);
  }
}
export function renderTabs(page,node){const parent=owner(page);if(!groups[parent])return;const nav=node('nav',undefined,'module-tabs');nav.setAttribute('aria-label','Herramientas de '+menu.find(([id])=>id===parent)[1]);for(const [id,label]of groups[parent]){const b=node('button',label);b.dataset.page=id;b.setAttribute('aria-current',id===page?'page':'false');nav.append(b);}document.querySelector('#main').append(nav);}
