/* Foundation-local pile layout. The dialog edits a draft; only Apply commits it. */
(function (root) {
  'use strict';
  const copy = value => JSON.parse(JSON.stringify(value));
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const coordinate = value => value === undefined ? 0 : value;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const metres = value => finite(value) ? String(Math.round(value) / 1000) : '';
  const fmt = value => finite(value) ? (value / 1000).toLocaleString('es-CL', {minimumFractionDigits:3, maximumFractionDigits:3}) : '—';
  const uid = () => root.ProjectIO?.uid?.() || root.crypto?.randomUUID?.() || `pile-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

  function foundationFrame(model, foundation) {
    const nodes = (foundation.nodos || []).map(id => (model.nodos || []).find(n => n.id === id))
      .filter(n => n && finite(n.x) && finite(n.y));
    if (!nodes.length) return {centre:[0, 0], angle:finite(foundation.angulo_deg) ? foundation.angulo_deg * Math.PI / 180 : 0, nodes:[], located:false};
    const centre = [nodes.reduce((sum,n) => sum+n.x,0)/nodes.length, nodes.reduce((sum,n) => sum+n.y,0)/nodes.length];
    const angle = finite(foundation.angulo_deg) ? foundation.angulo_deg * Math.PI / 180
      : nodes.length > 1 ? Math.atan2(nodes.at(-1).y-nodes[0].y, nodes.at(-1).x-nodes[0].x) : 0;
    return {centre, angle, nodes, located:true};
  }

  function supportLayout(model, foundation) {
    const frame = foundationFrame(model, foundation), c = Math.cos(frame.angle), s = Math.sin(frame.angle);
    const supports = (model.soportes || []).filter(support => support.fundacion === foundation.id);
    const nodes = supports.flatMap(support => {
      const node = (model.nodos || []).find(n => n.id === support.nodo);
      if (!node || !finite(node.x) || !finite(node.y) || !frame.located) return [];
      const dx = node.x-frame.centre[0], dy = node.y-frame.centre[1];
      const round = finite(support.diametro_mm) && support.diametro_mm > 0;
      const rx = round ? support.diametro_mm/2 : finite(support.largo_mm) && support.largo_mm > 0 ? support.largo_mm/2 : 0;
      const ry = round ? rx : finite(support.ancho_mm) && support.ancho_mm > 0 ? support.ancho_mm/2 : 0;
      return [{id:support.id, nodeId:node.id, x:dx*c+dy*s, y:-dx*s+dy*c, shape:round ? 'circle' : 'rectangle', rx, ry}];
    });
    return {centre:frame.centre, angle:frame.angle, located:frame.located, nodes};
  }

  function validateLayout(foundation, piles) {
    const errors = [], invalid = new Set(), ids = new Set();
    if (![foundation.largo_mm, foundation.ancho_mm].every(value => finite(value) && value > 0))
      errors.push('Completa el largo y el ancho de la fundación con valores positivos.');
    for (const pile of piles) {
      const id = pile.id || 'Pilote sin identificación', x = coordinate(pile.dx_mm), y = coordinate(pile.dy_mm);
      if (!pile.id || ids.has(pile.id)) {errors.push(`${id}: cada pilote debe tener una identificación única.`); invalid.add(pile.id);}
      ids.add(pile.id);
      if (![pile.diametro_mm,pile.longitud_mm].every(value => finite(value) && value > 0) || ![x,y].every(finite)) {
        errors.push(`${id}: completa diámetro y longitud positivos y coordenadas válidas.`); invalid.add(pile.id); continue;
      }
      if (finite(foundation.largo_mm) && finite(foundation.ancho_mm)
          && (Math.abs(x)+pile.diametro_mm/2 > foundation.largo_mm/2+1e-6 || Math.abs(y)+pile.diametro_mm/2 > foundation.ancho_mm/2+1e-6)) {
        errors.push(`${id}: su sección debe quedar dentro de la fundación.`); invalid.add(pile.id);
      }
    }
    for (let i=0; i<piles.length; i++) for (let j=i+1; j<piles.length; j++) {
      const a=piles[i], b=piles[j], values=[coordinate(a.dx_mm),coordinate(a.dy_mm),coordinate(b.dx_mm),coordinate(b.dy_mm),a.diametro_mm,b.diametro_mm];
      if (!values.every(finite) || a.diametro_mm <= 0 || b.diametro_mm <= 0) continue;
      if (Math.hypot(values[0]-values[2], values[1]-values[3]) < (a.diametro_mm+b.diametro_mm)/2-1e-6) {
        errors.push(`${a.id} y ${b.id}: las secciones de los pilotes se superponen.`); invalid.add(a.id); invalid.add(b.id);
      }
    }
    return {valid:errors.length === 0, errors, invalidPileIds:[...invalid]};
  }

  function setSpacing(pile, reference, changes) {
    const next = {...pile};
    const rx=coordinate(reference.dx_mm), ry=coordinate(reference.dy_mm), x=coordinate(pile.dx_mm), y=coordinate(pile.dy_mm);
    if (![rx,ry,x,y].every(finite)) throw new Error('Completa las coordenadas de ambos pilotes antes de definir distancias.');
    if (changes.dx !== undefined) {
      if (!finite(changes.dx)) throw new Error('Introduce una separación X válida.');
      next.dx_mm=rx+changes.dx;
    }
    if (changes.dy !== undefined) {
      if (!finite(changes.dy)) throw new Error('Introduce una separación Y válida.');
      next.dy_mm=ry+changes.dy;
    }
    if (changes.distance !== undefined || changes.angle !== undefined) {
      const distance=changes.distance ?? Math.hypot(x-rx,y-ry), angle=changes.angle ?? Math.atan2(y-ry,x-rx)*180/Math.PI;
      if (!finite(distance) || distance < 0 || !finite(angle)) throw new Error('Introduce una distancia entre centros no negativa y un ángulo válido.');
      next.dx_mm=rx+distance*Math.cos(angle*Math.PI/180); next.dy_mm=ry+distance*Math.sin(angle*Math.PI/180);
    }
    return next;
  }

  function nextPileId(model, draft) {
    const occupied=new Set([...(model.nodos||[]),...(model.tramos||[]),...(model.soportes||[]),...(model.fundaciones||[]),...(model.ejes||[]),...(model.fundaciones||[]).flatMap(f=>f.pilotes||[]),...draft].map(item=>item.id));
    let index=1; while (occupied.has(`P${index}`)) index++;
    return `P${index}`;
  }

  function styles() {
    if (document.getElementById('pile-plan-styles')) return;
    const style=document.createElement('style'); style.id='pile-plan-styles';
    style.textContent=`
      .pile-plan-dialog{width:min(1120px,calc(100vw - 36px));max-width:none;max-height:calc(100vh - 36px);padding:0;border:1px solid #d5e1e8;border-radius:14px;color:#233e50;background:#fff;box-shadow:0 24px 80px #172c3b33;font:13px system-ui,sans-serif;overflow:auto}
      .pile-plan-dialog::backdrop{background:#14304366}.pile-plan-dialog *{box-sizing:border-box}
      .pile-plan-dialog header{padding:19px 22px 14px;border-bottom:1px solid #e3ebf1;display:flex;gap:18px;align-items:flex-start;justify-content:space-between}
      .pile-plan-dialog h2{font-size:18px;margin:0 0 7px}.pile-plan-dialog h3{font-size:14px;margin:0 0 12px}.pile-plan-dialog p{margin:5px 0 10px;line-height:1.5}
      .pile-plan-dialog .pile-helper{font-size:12px;color:#677f91}.pile-plan-dialog .pile-plan-body{display:grid;grid-template-columns:minmax(0,1fr) 290px;gap:18px;padding:18px 22px}
      .pile-plan-dialog .pile-plan-preview{min-width:0}.pile-plan-dialog [data-pile-plan]{width:100%;height:auto;max-height:57vh;min-height:300px;border:1px solid #dbe7ee;border-radius:10px;background:#f8fbfd;touch-action:none;user-select:none}
      .pile-plan-dialog .pile-plan-item{cursor:grab;outline:none}.pile-plan-dialog .pile-plan-item:active{cursor:grabbing}.pile-plan-dialog .pile-plan-item:focus-visible>circle{stroke:#146fa1;stroke-width:3}
      .pile-plan-dialog [data-pile-list]{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.pile-plan-dialog button{font:inherit;background:#fff;color:#285b78;border:1px solid #cbdde7;border-radius:6px;padding:8px 12px;cursor:pointer}
      .pile-plan-dialog button:disabled{opacity:.45;cursor:default}.pile-plan-dialog button:focus-visible,.pile-plan-dialog input:focus-visible,.pile-plan-dialog select:focus-visible{outline:2px solid #2b86b5;outline-offset:2px}
      .pile-plan-dialog button[data-pile-list-id][aria-pressed=true]{background:#e6f3fb;border-color:#2b86b5;color:#095b89}.pile-plan-dialog button.pile-primary{background:#226f98;color:white;border-color:#226f98}
      .pile-plan-dialog .pile-plan-actions{display:flex;gap:8px;flex-wrap:wrap}.pile-plan-dialog [data-pile-editor]{border-left:1px solid #e2ebf0;padding-left:18px;min-width:0}
      .pile-plan-dialog .pile-fields{display:grid;grid-template-columns:1fr 1fr;gap:10px}.pile-plan-dialog label{display:block;color:#5f788a;font-size:12px;margin-bottom:10px}
      .pile-plan-dialog label>span{display:block;margin-bottom:5px}.pile-plan-dialog input,.pile-plan-dialog select{font:13px system-ui,sans-serif;width:100%;min-width:0;padding:8px;border:1px solid #d0dfe9;border-radius:6px;background:#fbfdff;color:#243d4f}
      .pile-plan-dialog .pile-pair{border-top:1px solid #e2ebf0;margin-top:16px;padding-top:14px}.pile-plan-dialog [data-pile-errors]{color:#a53d2e;background:#fff1ed;border-radius:7px;padding:9px 12px;font-size:12px;line-height:1.5}
      .pile-plan-dialog [data-pile-errors]:empty{display:none}.pile-plan-dialog [data-pile-errors] p{margin:2px 0}.pile-plan-dialog .pile-legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:#688091}
      .pile-plan-dialog .pile-legend span::before{content:'';display:inline-block;width:11px;height:11px;margin-right:5px;vertical-align:-1px;border:1px solid #7c95a5;background:#e2ebf1}.pile-plan-dialog .pile-legend .pile-legend-pile::before{border-radius:50%;background:#bedbeb;border-color:#407f9d}.pile-plan-dialog .pile-legend .pile-legend-support::before{background:#e4d6ba;border-color:#a28b60}
      .pile-plan-dialog footer{display:flex;gap:10px;justify-content:flex-end;padding:14px 22px 18px;border-top:1px solid #e3ebf1}.pile-plan-dialog [data-pile-close]{padding:3px 8px;font-size:20px;border:0;color:#687f8d}
      @media(max-width:780px){.pile-plan-dialog .pile-plan-body{grid-template-columns:1fr}.pile-plan-dialog [data-pile-editor]{border-left:0;border-top:1px solid #e2ebf0;padding:14px 0 0}.pile-plan-dialog [data-pile-plan]{min-height:260px;max-height:none}.pile-plan-dialog .pile-fields{grid-template-columns:repeat(2,minmax(0,1fr))}}
    `;
    document.head.append(style);
  }

  function open(options) {
    const {model,foundationId,onApply,onMessage}=options, foundation=(model?.fundaciones||[]).find(f=>f.id===foundationId);
    if (!foundation) {onMessage?.('No se encontró la fundación seleccionada.',true); return null;}
    styles();
    const draft=copy(foundation.pilotes || []); let selectedId=draft.some(p=>p.id===options.initialPileId)?options.initialPileId:draft[0]?.id;
    let referenceId=null, drag=null, applying=false; const inputErrors=new Map();
    const support=supportLayout(model,foundation), dialog=document.createElement('dialog'); dialog.className='pile-plan-dialog';
    const titleId=`pile-title-${uid()}`; dialog.setAttribute('aria-labelledby',titleId);
    dialog.innerHTML=`<header><div><h2 id="${esc(titleId)}">Pilotes de ${esc(foundation.id)}</h2><p class="pile-helper">Ubica los pilotes bajo la fundación. X e Y son distancias desde su centro, en sus ejes locales.</p></div><button type="button" data-pile-close aria-label="Cerrar">×</button></header>
      <div class="pile-plan-body"><section class="pile-plan-preview"><svg data-pile-plan viewBox="0 0 700 580" role="group" aria-label="Planta de la fundación y sus pilotes"></svg>
      <div class="pile-legend"><span>Fundación</span><span class="pile-legend-support">Columna / estribo</span><span class="pile-legend-pile">Pilote</span></div>
      <p class="pile-helper">Selecciona y arrastra un pilote, o escribe sus coordenadas. Con el pilote enfocado: flechas = 0,01 m; Mayús + flechas = 0,10 m.</p>
      <div data-pile-list aria-label="Pilotes"></div><div class="pile-plan-actions"><button type="button" data-pile-add>+ Añadir pilote</button></div>
      <p class="pile-helper" data-pile-summary></p><div data-pile-errors role="status" aria-live="polite"></div></section><aside data-pile-editor></aside></div>
      <footer><button type="button" data-pile-cancel>Cancelar</button><button type="button" class="pile-primary" data-pile-apply>Aplicar pilotes</button></footer>`;
    document.body.append(dialog);
    const plot=dialog.querySelector('[data-pile-plan]'), editor=dialog.querySelector('[data-pile-editor]');
    const length=finite(foundation.largo_mm)&&foundation.largo_mm>0?foundation.largo_mm:3000;
    const width=finite(foundation.ancho_mm)&&foundation.ancho_mm>0?foundation.ancho_mm:3000;
    const scale=Math.min(430/length,360/width), origin=[328,278];
    const point=(x,y)=>[origin[0]+x*scale,origin[1]-y*scale];
    const selected=()=>draft.find(p=>p.id===selectedId), reference=()=>draft.find(p=>p.id===referenceId && p.id!==selectedId);
    const svg=(name,attrs={},text)=>{const el=document.createElementNS('http://www.w3.org/2000/svg',name);Object.entries(attrs).forEach(([key,value])=>el.setAttribute(key,String(value)));if(text!==undefined)el.textContent=text;return el;};
    const input=(label,name,value,kind='pile',min)=>`<label><span>${label}</span><input type="number" step="0.001" ${min!==undefined?`min="${min}"`:''} data-${kind}-field="${name}" value="${finite(value)?esc(kind==='spacing'&&name==='angle'?Math.round(value*1000)/1000:metres(value)):''}"></label>`;

    function label(group,text,x,y,{color='#577082',anchor='middle',size=12,background=true}={}) {
      if (![x,y].every(finite)) return;
      if (background) {const w=String(text).length*size*.55+8;group.append(svg('rect',{x:anchor==='middle'?x-w/2:anchor==='end'?x-w:x,y:y-size,width:w,height:size+4,rx:2,fill:'#f8fbfd',opacity:.96}));}
      group.append(svg('text',{x,y,fill:color,'font-size':size,'text-anchor':anchor},text));
    }
    function dimension(group,a,b,text,offset=0,{leftLabel=false}={}) {
      if (![...a,...b,offset].every(finite) || Math.hypot(b[0]-a[0],b[1]-a[1])<.01) return;
      const dx=b[0]-a[0],dy=b[1]-a[1],distance=Math.hypot(dx,dy),n=[-dy/distance,dx/distance];
      const aa=[a[0]+n[0]*offset,a[1]+n[1]*offset],bb=[b[0]+n[0]*offset,b[1]+n[1]*offset],color='#738c9b';
      if (offset) for (const [source,target] of [[a,aa],[b,bb]]) group.append(svg('line',{x1:source[0],y1:source[1],x2:target[0]+n[0]*Math.sign(offset)*5,y2:target[1]+n[1]*Math.sign(offset)*5,stroke:color,'stroke-width':.7}));
      group.append(svg('line',{x1:aa[0],y1:aa[1],x2:bb[0],y2:bb[1],stroke:color,'stroke-width':.85}));
      root.DimensionStyle?.appendArrows(svg,group,aa,bb,{textSize:10,color});
      const horizontal=Math.abs(dx)>=Math.abs(dy),mx=(aa[0]+bb[0])/2,my=(aa[1]+bb[1])/2;
      label(group,text,horizontal?mx:mx+(leftLabel?-8:8),horizontal?my-7:my+4,{anchor:horizontal?'middle':leftLabel?'end':'start',size:11});
    }

    function renderPanel() {
      const pile=selected();
      if (!pile) {editor.innerHTML='<h3>Distribución de pilotes</h3><p class="pile-helper">Añade un pilote para definir su diámetro, longitud y posición. Los pilotes nacen en la cara inferior de la fundación.</p>';return;}
      if (!reference()) referenceId=draft.find(p=>p.id!==selectedId)?.id || null;
      editor.innerHTML=`<h3 data-pile-selected-title>${esc(pile.id)}</h3><div class="pile-fields">${input('X local (m)','dx_mm',coordinate(pile.dx_mm))}${input('Y local (m)','dy_mm',coordinate(pile.dy_mm))}${input('Diámetro (m)','diametro_mm',pile.diametro_mm,'pile',.001)}${input('Longitud (m)','longitud_mm',pile.longitud_mm,'pile',.001)}</div>
        <button type="button" data-pile-remove>Quitar ${esc(pile.id)}</button><section class="pile-pair" data-pile-pair></section>`;
      renderPair();
    }
    function renderPair() {
      const panel=editor.querySelector('[data-pile-pair]'), pile=selected(); if(!panel||!pile)return;
      const others=draft.filter(p=>p.id!==selectedId), ref=reference();
      if (!ref) {panel.innerHTML='<h3>Distancias entre pilotes</h3><p class="pile-helper">Añade otro pilote para definir separaciones entre sus centros.</p>';return;}
      const dx=coordinate(pile.dx_mm)-coordinate(ref.dx_mm),dy=coordinate(pile.dy_mm)-coordinate(ref.dy_mm);
      panel.innerHTML=`<h3>Distancias entre pilotes</h3><label><span>Referencia fija</span><select data-pile-reference>${others.map(p=>`<option value="${esc(p.id)}"${p.id===ref.id?' selected':''}>${esc(p.id)}</option>`).join('')}</select></label>
        <div class="pile-fields">${input('Separación X (m)','dx',dx,'spacing')}${input('Separación Y (m)','dy',dy,'spacing')}${input('Entre centros (m)','distance',Math.hypot(dx,dy),'spacing',0)}${input('Dirección desde X+ (°)','angle',Math.atan2(dy,dx)*180/Math.PI,'spacing')}</div>
        <p class="pile-helper">Las separaciones X e Y tienen signo. Al editar una distancia se mueve ${esc(pile.id)}; ${esc(ref.id)} queda fijo. La dirección gira hacia Y+.</p>`;
    }
    function syncFields(except) {
      const pile=selected(),ref=reference(); if(!pile)return;
      for(const field of editor.querySelectorAll('[data-pile-field]')) if(field!==except) field.value=metres(coordinate(pile[field.dataset.pileField]));
      if(ref){const dx=coordinate(pile.dx_mm)-coordinate(ref.dx_mm),dy=coordinate(pile.dy_mm)-coordinate(ref.dy_mm),values={dx,dy,distance:Math.hypot(dx,dy),angle:Math.atan2(dy,dx)*180/Math.PI};
        for(const field of editor.querySelectorAll('[data-spacing-field]')) if(field!==except){const key=field.dataset.spacingField;field.value=finite(values[key])?(key==='angle'?String(Math.round(values[key]*1000)/1000):metres(values[key])):'';}}
    }
    function renderPreview() {
      plot.replaceChildren(); const valid=validateLayout(foundation,draft), invalid=new Set(valid.invalidPileIds);
      const [left,top]=point(-length/2,width/2),[right,bottom]=point(length/2,-width/2);
      plot.append(svg('rect',{x:left,y:top,width:length*scale,height:width*scale,fill:'#e9f0f5',stroke:'#8097a6','stroke-width':1.4,'data-foundation-outline':foundation.id}));
      const annotations=svg('g',{'pointer-events':'none','data-pile-dimensions':''});
      dimension(annotations,[left,top],[right,top],`${fmt(foundation.largo_mm)} m`,-28);
      dimension(annotations,[left,bottom],[left,top],`${fmt(foundation.ancho_mm)} m`,-28);
      plot.append(svg('line',{x1:left-10,y1:origin[1],x2:right+18,y2:origin[1],stroke:'#9cb2c1','stroke-dasharray':'5 5'}),svg('line',{x1:origin[0],y1:bottom+10,x2:origin[0],y2:top-15,stroke:'#9cb2c1','stroke-dasharray':'5 5'}));
      label(annotations,'X+',right+22,origin[1]-7,{anchor:'start',background:false});label(annotations,'Y+',origin[0]+7,top-17,{anchor:'start',background:false});
      label(annotations,'0,0',origin[0]+7,origin[1]+17,{anchor:'start',size:10});
      for (const item of support.nodes) {
        const [x,y]=point(item.x,item.y), attrs={fill:'#e4d6ba',stroke:'#a28b60','stroke-width':1.2,'data-plan-support':item.id};
        if(item.rx>0&&item.ry>0)plot.append(item.shape==='circle'?svg('circle',{...attrs,cx:x,cy:y,r:item.rx*scale}):svg('rect',{...attrs,x:x-item.rx*scale,y:y-item.ry*scale,width:item.rx*2*scale,height:item.ry*2*scale}));
        else plot.append(svg('path',{...attrs,d:`M ${x-5} ${y} h 10 M ${x} ${y-5} v 10`,fill:'none'}));
        label(annotations,item.nodeId,x,y-item.ry*scale-8,{color:'#8b7044',size:10});
      }
      for (const pile of draft) {
        const x=coordinate(pile.dx_mm),y=coordinate(pile.dy_mm); if(![x,y,pile.diametro_mm].every(finite)||pile.diametro_mm<=0)continue;
        const [px,py]=point(x,y),isSelected=pile.id===selectedId,bad=invalid.has(pile.id),g=svg('g',{class:'pile-plan-item','data-pile-id':pile.id,role:'button',tabindex:0,'aria-pressed':isSelected,'aria-label':`Seleccionar pilote ${pile.id}, X ${fmt(x)} m, Y ${fmt(y)} m`});
        g.append(svg('circle',{cx:px,cy:py,r:pile.diametro_mm*scale/2,fill:bad?'#f4c6bb':isSelected?'#a8d5ed':'#cce3ef',stroke:bad?'#b44d35':isSelected?'#16658d':'#5f90aa','stroke-width':isSelected?2.5:1.4,'fill-opacity':.84}),svg('path',{d:`M ${px-4} ${py} h 8 M ${px} ${py-4} v 8`,stroke:bad?'#a13925':'#42748d','stroke-width':1,'pointer-events':'none'}));
        const text=svg('text',{x:px,y:py+4,'text-anchor':'middle','font-size':11,'font-weight':600,fill:'#1e5675','pointer-events':'none'},pile.id);g.append(text);plot.append(g);
      }
      const pile=selected(),ref=reference();
      if(pile&&[coordinate(pile.dx_mm),coordinate(pile.dy_mm)].every(finite)){
        const x=coordinate(pile.dx_mm),y=coordinate(pile.dy_mm),p=point(x,y);
        dimension(annotations,[origin[0],bottom+29],[p[0],bottom+29],`X ${fmt(x)} m`);
        dimension(annotations,[right+27,origin[1]],[right+27,p[1]],`Y ${fmt(y)} m`);
        if(ref&&[coordinate(ref.dx_mm),coordinate(ref.dy_mm)].every(finite)){
          const r=point(coordinate(ref.dx_mm),coordinate(ref.dy_mm)),dx=x-coordinate(ref.dx_mm),dy=y-coordinate(ref.dy_mm);
          annotations.append(svg('path',{d:`M ${r[0]} ${r[1]} H ${p[0]} V ${p[1]}`,fill:'none',stroke:'#68a2bd','stroke-dasharray':'4 3','stroke-width':1}));
          dimension(annotations,[r[0],Math.min(r[1],p[1])-24],[p[0],Math.min(r[1],p[1])-24],`ΔX ${fmt(dx)} m`);
          dimension(annotations,[Math.max(r[0],p[0])+25,r[1]],[Math.max(r[0],p[0])+25,p[1]],`ΔY ${fmt(dy)} m`);
          // Keep the centre distance on the opposite side from the X/Y separation,
          // independent of which pile is the reference and which one is selected.
          const vertical=Math.abs(dx)<1e-6,horizontal=Math.abs(dy)<1e-6;
          const offset=vertical?Math.sign(p[1]-r[1])*22:horizontal?Math.sign(p[0]-r[0])*22:0;
          dimension(annotations,r,p,`${fmt(Math.hypot(dx,dy))} m`,offset,{leftLabel:vertical});
        }
      }
      plot.append(annotations);
      dialog.querySelector('[data-pile-list]').innerHTML=draft.map(p=>`<button type="button" data-pile-list-id="${esc(p.id)}" aria-pressed="${p.id===selectedId}">${esc(p.id)}</button>`).join('');
      const errors=[...valid.errors,...inputErrors.values()];
      dialog.querySelector('[data-pile-errors]').innerHTML=errors.map(error=>`<p>${esc(error)}</p>`).join('');
      dialog.querySelector('[data-pile-apply]').disabled=errors.length>0 || applying;
      dialog.querySelector('[data-pile-summary]').textContent=`${draft.length} ${draft.length===1?'pilote':'pilotes'} · ${draft.length?'Dado':'Fundación sin pilotes'} · Giro de la fundación ${(support.angle*180/Math.PI).toLocaleString('es-CL',{maximumFractionDigits:2})}°${support.located?'':' · Ubicación del apoyo pendiente'}`;
    }
    function focusPile(id) {for(const item of plot.querySelectorAll('[data-pile-id]'))if(item.dataset.pileId===id){item.focus({preventScroll:true});break;}}
    function choose(id,focus=false) {selectedId=id;inputErrors.clear();renderPanel();renderPreview();if(focus)focusPile(id);}
    function close() {if(dialog.open)dialog.close();dialog.remove();}
    function eventPoint(event) {const matrix=plot.getScreenCTM();if(!matrix)return null;const p=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());return [(p.x-origin[0])/scale,(origin[1]-p.y)/scale];}
    function add() {
      const previous=selected(),diameter=previous&&finite(previous.diametro_mm)&&previous.diametro_mm>0?previous.diametro_mm:Math.min(1000,length,width);
      const pile={id:nextPileId(model,draft),uuid:uid(),diametro_mm:diameter,longitud_mm:previous&&finite(previous.longitud_mm)&&previous.longitud_mm>0?previous.longitud_mm:10000,dx_mm:0,dy_mm:0};
      // Prefer a free grid position inside the foundation; users can refine it numerically.
      if(draft.length){const step=Math.max(diameter,100),positions=[];
        for(let row=0;row<40;row++)for(let col=0;col<40;col++){
          const x=-length/2+diameter/2+col*step,y=-width/2+diameter/2+row*step;
          if(x+diameter/2<=length/2+1e-6&&y+diameter/2<=width/2+1e-6)positions.push([x,y]);
        }
        positions.sort((a,b)=>Math.hypot(...a)-Math.hypot(...b));
        const position=positions.find(([x,y])=>draft.every(p=>!finite(p.diametro_mm)||Math.hypot(x-coordinate(p.dx_mm),y-coordinate(p.dy_mm))>=(diameter+p.diametro_mm)/2-1e-6));
        if(position)[pile.dx_mm,pile.dy_mm]=position;
      }
      draft.push(pile);choose(pile.id);editor.querySelector('[data-pile-field="dx_mm"]')?.focus();
    }
    dialog.addEventListener('click',event=>{
      if(event.target.closest('[data-pile-close],[data-pile-cancel]'))close();
      if(event.target.closest('[data-pile-add]'))add();
      const item=event.target.closest('[data-pile-list-id]');if(item)choose(item.dataset.pileListId);
      if(event.target.closest('[data-pile-remove]')){const index=draft.findIndex(p=>p.id===selectedId);if(index>=0)draft.splice(index,1);choose(draft[Math.min(index,draft.length-1)]?.id);}
      if(event.target.closest('[data-pile-apply]')){
        const validation=validateLayout(foundation,draft);if(!validation.valid||inputErrors.size||applying)return;
        applying=true;renderPreview();
        try {const result=onApply?.(copy(draft));Promise.resolve(result).then(()=>{onMessage?.(`Distribución de pilotes de ${foundation.id} actualizada.`);close();},error=>{applying=false;inputErrors.set('apply',error?.message||'No se pudieron aplicar los pilotes.');renderPreview();});}
        catch(error){applying=false;inputErrors.set('apply',error?.message||'No se pudieron aplicar los pilotes.');renderPreview();}
      }
    });
    dialog.addEventListener('input',event=>{
      const field=event.target,pile=selected();if(!pile)return;inputErrors.delete('apply');
      if(field.dataset.pileField){const key=field.dataset.pileField;pile[key]=field.valueAsNumber*1000;inputErrors.clear();syncFields(field);renderPreview();}
      if(field.dataset.spacingField){const key=field.dataset.spacingField,ref=reference();if(!ref)return;
        try{const next=setSpacing(pile,ref,{[key]:field.valueAsNumber*(key==='angle'?1:1000)});Object.assign(pile,next);inputErrors.clear();syncFields(field);}
        catch(error){inputErrors.set(key,error.message);}
        renderPreview();
      }
    });
    dialog.addEventListener('change',event=>{if(event.target.matches('[data-pile-reference]')){referenceId=event.target.value;inputErrors.clear();renderPair();renderPreview();}});
    plot.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;const item=event.target.closest('[data-pile-id]');if(!item)return;
      event.preventDefault();choose(item.dataset.pileId);const pile=selected(),p=eventPoint(event);if(!pile||!p)return;
      drag={id:pile.id,start:p,before:[coordinate(pile.dx_mm),coordinate(pile.dy_mm)],pointerId:event.pointerId};plot.setPointerCapture(event.pointerId);
    });
    plot.addEventListener('pointermove',event=>{
      if(!drag||event.pointerId!==drag.pointerId)return;const pile=draft.find(p=>p.id===drag.id),p=eventPoint(event);if(!pile||!p)return;
      pile.dx_mm=Math.round(drag.before[0]+p[0]-drag.start[0]);pile.dy_mm=Math.round(drag.before[1]+p[1]-drag.start[1]);inputErrors.clear();syncFields();renderPreview();
    });
    const finishDrag=event=>{if(!drag||event.pointerId!==drag.pointerId)return;const id=drag.id;drag=null;if(plot.hasPointerCapture(event.pointerId))plot.releasePointerCapture(event.pointerId);focusPile(id);};
    plot.addEventListener('pointerup',finishDrag);plot.addEventListener('pointercancel',finishDrag);
    plot.addEventListener('keydown',event=>{
      const item=event.target.closest('[data-pile-id]');if(!item)return;
      if(event.key==='Enter'||event.key===' '){event.preventDefault();choose(item.dataset.pileId,true);return;}
      const direction={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowDown:[0,-1],ArrowUp:[0,1]}[event.key];if(!direction)return;
      event.preventDefault();selectedId=item.dataset.pileId;const pile=selected(),step=event.shiftKey?100:10;if(!pile)return;
      pile.dx_mm=coordinate(pile.dx_mm)+direction[0]*step;pile.dy_mm=coordinate(pile.dy_mm)+direction[1]*step;inputErrors.clear();renderPanel();renderPreview();focusPile(pile.id);
    });
    dialog.addEventListener('cancel',event=>{event.preventDefault();close();});dialog.addEventListener('close',()=>dialog.remove());
    renderPanel();renderPreview();dialog.showModal();
    return {dialog,close};
  }

  const api={open,validateLayout,supportLayout,foundationFrame,setSpacing,nextPileId};root.PilePlanEditor=api;
  if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
