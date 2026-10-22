/* Secciones y relaciones de cimentación. Todas las dimensiones internas están en mm. */
(function (root) {
  "use strict";
  const clone = x => JSON.parse(JSON.stringify(x));
  const esc = x => String(x ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const finite = x => typeof x === "number" && Number.isFinite(x);
  const uid = () => root.ProjectIO?.uid?.() || root.crypto.randomUUID();
  const m = x => finite(x) ? Number((x / 1000).toFixed(4)) : "";
  const fmt = x => finite(x) ? (x / 1000).toLocaleString("es-CL", {maximumFractionDigits:3}) : "—";
  const defs = {
    cajon: [{key:"canto_mm",label:"Alto viga"},{key:"ancho_alma_superior_mm",label:"Ancho superior del cajón sin alas"},{key:"ancho_inferior_mm",label:"Ancho exterior inferior"},{key:"losa_superior_mm",label:"Espesor losa superior en el centro"},{key:"losa_inferior_mm",label:"Espesor losa inferior"},{key:"alma_mm",label:"Espesor horizontal de alma"},{key:"macizado_mm",label:"Macizado en cada extremo",zero:true}],
    maciza: [{key:"canto_mm",label:"Canto / espesor"},{key:"ancho_inferior_mm",label:"Ancho inferior"}],
    escalera: [{key:"canto_mm",label:"Espesor de losa inclinada"},{key:"numero_peldanos",label:"Número de peldaños",integer:true}]
  };
  function defaults(type, width=2000) {
    if (type === "escalera") return {tipo:type,canto_mm:180,numero_peldanos:18};
    if (type === "maciza") return {tipo:type,pendiente_transversal_pct:1,canto_mm:250,ancho_inferior_mm:width};
    return {tipo:"cajon",pendiente_transversal_pct:1,canto_mm:600,ancho_alma_superior_mm:Math.min(1260,width),ancho_inferior_mm:Math.min(1000,width),losa_superior_mm:150,losa_inferior_mm:140,alma_mm:140,macizado_mm:500};
  }
  function profile(f) {
    return Array.isArray(f.perfil_canto) && f.perfil_canto.length ? f.perfil_canto : [{t:0,canto_mm:f.canto_mm},{t:1,canto_mm:f.canto_fin_mm ?? f.canto_mm}];
  }
  function depthAt(f, t=0) {
    const ps=profile(f); if(t<=ps[0].t)return ps[0].canto_mm;
    for(let i=1;i<ps.length;i++)if(t<=ps[i].t){const a=ps[i-1],b=ps[i];return a.canto_mm+(b.canto_mm-a.canto_mm)*(t-a.t)/(b.t-a.t);}
    return ps.at(-1).canto_mm;
  }
  function validate(f, width, context={}) {
    const errors=[]; if(!f||typeof f!=="object")return ["Falta la definición de la sección."]; const type=f.tipo || "maciza";
    if(!defs[type])return ["Tipo de sección desconocido."];
    if(!finite(width)||width<=0)errors.push("El ancho estructural debe ser positivo.");
    for(const d of defs[type]){
      const v=f[d.key] ?? (d.key==="ancho_inferior_mm"?width:d.key==="macizado_mm"?500:undefined);
      if(!finite(v)||(d.zero?v<0:v<=0)||(d.integer&&!Number.isInteger(v)))errors.push(`${d.label}: introduce ${d.integer?"un entero positivo":"una dimensión válida"}.`);
    }
    const slope=f.pendiente_transversal_pct??(type==="escalera"?0:1);
    if(!finite(slope)||slope<0)errors.push("La pendiente transversal debe ser un porcentaje finito mayor o igual a cero.");
    if(type==="escalera"&&slope!==0)errors.push("La pendiente transversal no está disponible para escaleras.");
    if(type!=="escalera"&&slope!==1)errors.push("La pendiente transversal debe ser 1 % a dos aguas (regla del proyecto).");
    const ps=profile(f);
    if(type!=="escalera"&&finite(slope)){
      const thickness=type==="cajon"?f.losa_superior_mm:Math.min(...ps.map(p=>p.canto_mm));
      if(slope*width/200>=thickness)errors.push("La pendiente transversal agota el espesor en los bordes. Reduce la pendiente o aumenta el espesor.");
    }
    if(ps.length<2||ps[0].t!==0||ps.at(-1).t!==1||ps.some((p,i)=>!finite(p.t)||!finite(p.canto_mm)||p.canto_mm<=0||p.t<0||p.t>1||(i&&p.t<=ps[i-1].t)))errors.push("Las estaciones de canto deben aumentar de 0 a 1 y tener cantos positivos.");
    if(type==="cajon"){
      if((f.macizado_mm??500)!==500)errors.push("El macizado debe ser 0,50 m en cada extremo.");
      const sup=f.ancho_alma_superior_mm,inf=f.ancho_inferior_mm,es=f.losa_superior_mm,ei=f.losa_inferior_mm,a=f.alma_mm;
      if(sup>width)errors.push("El cajón supera el ancho estructural del tramo.");
      for(const h of ps.map(p=>p.canto_mm)){
        if(h<=es+ei){errors.push("El canto debe superar la suma de las dos losas.");break;}
        if(sup-2*a<=0||inf+(sup-inf)*ei/(h-es)-2*a<=0){errors.push("El espesor de alma cierra el hueco del cajón.");break;}
      }
    }
    if(type==="escalera"){
      if(f.perfil_canto?.length||f.canto_fin_mm!==undefined&&f.canto_fin_mm!==f.canto_mm)errors.push("Esta escalera requiere espesor constante.");
      if(f.numero_peldanos>500)errors.push("Usa un máximo de 500 peldaños por tramo.");
      if(finite(context.riseMm)&&Math.abs(context.riseMm)<0.1)errors.push("La escalera necesita desnivel entre sus extremos.");
      if(finite(context.lengthMm)&&context.lengthMm<=0)errors.push("La escalera necesita longitud útil positiva.");
    }
    return [...new Set(errors)];
  }
  function wingWidth(f,width) {return (width-f.ancho_alma_superior_mm)/2;}
  function withWingWidth(f,width,wing) {return {...f,ancho_alma_superior_mm:width-2*wing,ala_mm:wing};}
  function geometry(f,width,t=0) {
    const h=depthAt(f,t),inf=f.ancho_inferior_mm??width;
    const drop=(f.pendiente_transversal_pct??1)*width/200;
    const top=drop>0?[[-width/2,drop],[0,0],[width/2,drop]]:[[-width/2,0],[width/2,0]];
    if(f.tipo!=="cajon")return {outer:[...top,[inf/2,h],[-inf/2,h]],inner:[],depth:h};
    const sup=f.ancho_alma_superior_mm,es=f.losa_superior_mm,ei=f.losa_inferior_mm,a=f.alma_mm;
    const bt=sup-2*a,bb=inf+(sup-inf)*ei/(h-es)-2*a;
    return {outer:[...top,[width/2,es],[sup/2,es],[inf/2,h],[-inf/2,h],[-sup/2,es],[-width/2,es]],inner:[[-bt/2,es],[bt/2,es],[bb/2,h-ei],[-bb/2,h-ei]],depth:h};
  }
  function render(f,width,options={}) {
    const errors=validate(f,width,options);
    if(errors.length)return `<div class="sections-empty">Vista pendiente: ${esc(errors[0])}</div>`;
    const isStair=f.tipo==="escalera",t=options.t??0;
    const w=560,h=290,margin=54;
    let body="",caption="Sección transversal · dimensiones en metros";
    const line=(x1,y1,x2,y2)=>`<path d="M${x1},${y1} L${x2},${y2}" fill="none" stroke="#7a929f" stroke-width="1"/>`;
    const text=(x,y,value)=>`<text x="${x}" y="${y}" text-anchor="middle" fill="#31566c" font-size="12">${esc(value)}</text>`;
    const dim=(x1,y1,x2,y2,value)=>line(x1,y1,x2,y2)+line(x1-3,y1-4,x1+3,y1+4)+line(x2-3,y2-4,x2+3,y2+4)+text((x1+x2)/2,(y1+y2)/2-7,value);
    if(isStair){
      const real=finite(options.lengthMm)&&finite(options.riseMm);
      const run=real?options.lengthMm:4500,rise=real?Math.abs(options.riseMm):3000,n=f.numero_peldanos,slab=f.canto_mm;
      const scale=Math.min((w-margin*2)/run,(h-85)/(rise+slab)),x=margin,y=h-45;
      const pts=[[x,y]];
      for(let i=0;i<n;i++){pts.push([x+i*run/n*scale,y-(i+1)*rise/n*scale]);pts.push([x+(i+1)*run/n*scale,y-(i+1)*rise/n*scale]);}
      pts.push([x+run*scale,y-rise*scale+slab*scale],[x,y+slab*scale]);
      body=`<polygon points="${pts.map(p=>p.join(',')).join(' ')}" fill="#d8e7ef" stroke="#2a6385" stroke-width="1.5"/>`;
      body+=dim(x,y+30,x+run*scale,y+30,`${fmt(run)} m`);
      body+=text(w/2,20,`${n} peldaños · huella ${fmt(run/n)} m · contrahuella ${fmt(rise/n)} m`);
      caption=real?"Alzado esquemático del tramo seleccionado; las cotas proceden de sus extremos.":"Ejemplo de alzado: el desarrollo real depende del tramo asignado.";
    }else{
      caption+=` · Pendiente a dos aguas 1 % · descenso al borde ${fmt(width/200)} m`;
      const g=geometry(f,width,t),maxWidth=Math.max(width,f.ancho_inferior_mm||width),scale=Math.min((w-margin*2)/maxWidth,(h-110)/g.depth);
      const x=w/2,y=55;const path=pts=>pts.map((p,i)=>`${i?'L':'M'}${x+p[0]*scale},${y+p[1]*scale}`).join(' ')+' Z';
      body=`<path d="${path(g.outer)} ${g.inner.length?path(g.inner):''}" fill="#d8e7ef" fill-rule="evenodd" stroke="#2a6385" stroke-width="1.8"/>`;
      body+=dim(x-width/2*scale,y-22,x+width/2*scale,y-22,`${fmt(width)} m`);
      body+=dim(x-maxWidth/2*scale-23,y,x-maxWidth/2*scale-23,y+g.depth*scale,`${fmt(g.depth)} m`);
      body+=dim(x-(f.ancho_inferior_mm??width)/2*scale,y+g.depth*scale+26,x+(f.ancho_inferior_mm??width)/2*scale,y+g.depth*scale+26,`${fmt(f.ancho_inferior_mm??width)} m`);
      if(f.tipo==="cajon"&&wingWidth(f,width)>0){
        const wing=wingWidth(f,width),outer=width/2*scale,inner=f.ancho_alma_superior_mm/2*scale;
        body+=dim(x-outer,y+f.losa_superior_mm*scale+18,x-inner,y+f.losa_superior_mm*scale+18,`${fmt(wing)} m`);
        body+=dim(x+inner,y+f.losa_superior_mm*scale+18,x+outer,y+f.losa_superior_mm*scale+18,`${fmt(wing)} m`);
      }
      if(f.tipo==="cajon")body+=text(w/2,h-8,`Losa superior ${fmt(f.losa_superior_mm)} · inferior ${fmt(f.losa_inferior_mm)} · alma ${fmt(f.alma_mm)} m`);
    }
    return `<svg class="sections-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(caption)}" xmlns="http://www.w3.org/2000/svg">${body}</svg><p class="sections-caption">${esc(caption)}</p>`;
  }
  function styles() {
    if(document.getElementById("sections-style"))return;
    const style=document.createElement("style");style.id="sections-style";
    style.textContent=`.sections-panel{margin:20px 0 0;padding-top:15px;border-top:1px solid #dce6ec;font:12px system-ui;color:#24475d}.sections-panel h3{font-size:13px;margin:0 0 12px}.sections-field{display:block;margin:9px 0}.sections-field>span{display:block;font-size:11px;color:#526d7f;margin-bottom:5px}.sections-field input,.sections-field select{box-sizing:border-box;width:100%;padding:8px;border:1px solid #d4e0e8;border-radius:6px;background:white;color:#23465c;font:12px system-ui}.sections-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 10px}.sections-svg{display:block;width:100%;background:#f5f9fc;border:1px solid #e0e9ef;border-radius:7px;min-height:150px}.sections-caption,.sections-info{font-size:11px;line-height:1.5;color:#6e8492;margin:8px 0}.sections-empty,.sections-errors{padding:10px;background:#fff6e9;border-radius:6px;color:#8a5923;font-size:11px;line-height:1.5}.sections-errors:empty{display:none}.sections-actions{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.sections-actions button{font:11px system-ui;border:1px solid #c9dae5;border-radius:6px;background:white;color:#285d7e;padding:8px;cursor:pointer}.sections-actions .primary{background:#256b95;color:white;border-color:#256b95}.sections-actions button:disabled{opacity:.45;cursor:default}.sections-check{display:flex;align-items:center;gap:7px;margin:12px 0;font-size:11px}.sections-profile-row{display:grid;grid-template-columns:1fr 1fr 25px;gap:5px;align-items:center}.sections-profile-row input{min-width:0;width:100%;box-sizing:border-box;padding:7px;border:1px solid #d4e0e8;border-radius:5px}.sections-profile-row button{border:0;background:none;color:#8e4b38;cursor:pointer}.sections-modal{width:min(880px,94vw);max-height:90vh;border:1px solid #cfdee8;border-radius:12px;padding:24px;color:#24475d;font:13px system-ui;box-sizing:border-box}.sections-modal::backdrop{background:#15334677}.sections-modal h2{margin:0 0 10px;font-size:20px}.sections-modal-grid{display:grid;grid-template-columns:1fr 1.2fr;gap:22px}.sections-node-list{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;max-height:180px;overflow:auto;padding:8px;background:#f5f8fa;border-radius:7px}.sections-node-list label{font-size:12px}.sections-close{float:right;border:0;background:none;font-size:22px;color:#607a8b;cursor:pointer}@media(max-width:640px){.sections-modal-grid{grid-template-columns:1fr}.sections-grid{grid-template-columns:1fr}}`;
    document.head.append(style);
  }
  function edgeContext(model,edge) {
    const a=model.nodos?.find(n=>n.id===edge?.desde),b=model.nodos?.find(n=>n.id===edge?.hasta);
    if(!a||!b)return {};
    const length=Math.hypot(b.x-a.x,b.y-a.y),start=edge.retranqueo_inicio_mm||0,end=edge.retranqueo_fin_mm||0;
    return {lengthMm:length-start-end,riseMm:(b.z-a.z)*(length-start-end)/length};
  }
  function uniqueId(model,base) {let id=base,i=2;while(model.familias?.[id])id=base+"_"+i++;return id;}
  function mount(container,options) {
    styles();let familyId,draft,station=0,disposable=false,isNew=false;
    const model=()=>options.getModel();const edge=()=>options.getSelectedEdge?.();
    const message=(text,error=false)=>options.onMessage?.(text,error);
    function choose(id,newFamily=false){familyId=id;isNew=newFamily;draft=newFamily?defaults("cajon",edge()?.ancho_mm||2000):clone(model().familias[id]);draft.tipo ||= edge()?.tipo==="retorno"?"maciza":"cajon";draft.ancho_inferior_mm??=edge()?.ancho_mm||2000;if(draft.tipo!=="escalera")draft.pendiente_transversal_pct=1;if(draft.tipo==="cajon")draft.macizado_mm=500;draw();}
    function draw(){
      if(disposable)return;
      const e=edge(),f=model()?.familias||{};
      if(!e){container.innerHTML='<div class="sections-panel"><p class="sections-info">Selecciona un tramo para editar su sección.</p></div>';return;}
      const automatic=root.VolumePreview?.sectionFamily(model(),e,draft)?.canto_por_descanso,ds=defs[draft.tipo]||defs.maciza,variable=!automatic&&(Array.isArray(draft.perfil_canto)&&draft.perfil_canto.length||draft.canto_fin_mm!==undefined&&draft.canto_fin_mm!==draft.canto_mm);
      const input=(d)=>`<label class="sections-field"><span>${esc(automatic&&d.key==='canto_mm'?'Alto viga en la porción alta':d.label)}${d.integer?'':' (m)'}</span><input type="number" step="${d.integer?'1':'.001'}" data-section-field="${d.key}" ${d.key==='macizado_mm'?'readonly':''} value="${d.integer?esc(draft[d.key]):m(draft[d.key])}"></label>`;
      container.innerHTML=`<section class="sections-panel"><h3>Sección de la familia</h3><label class="sections-field"><span>Familia del tramo</span><select data-section-action="choose">${Object.keys(f).map(id=>`<option value="${esc(id)}" ${id===familyId?'selected':''}>${esc(id)}</option>`).join('')}${isNew?`<option selected value="${esc(familyId)}">${esc(familyId)} (nueva)</option>`:''}</select></label><label class="sections-field"><span>Identificador ${isNew?'de la nueva familia':''}</span><input data-section-id value="${esc(familyId)}" ${isNew?'':'readonly'}></label><label class="sections-field"><span>Forma</span><select data-section-action="type">${[['cajon','Cajón con alas'],['maciza','Maciza / losa'],['escalera','Escalera recta']].map(([v,l])=>`<option value="${v}" ${draft.tipo===v?'selected':''}>${l}</option>`).join('')}</select></label><p class="sections-info">${e.funcion === "cruce" ? "Ancho sección atravieso (viga)" : "Ancho estructural del tramo"}: <strong>${fmt(e.ancho_mm)} m</strong>. Se edita en las propiedades del tramo.</p>${draft.tipo==='cajon'?`<p class="sections-info">El ancho total incluye las dos alas. Cada ala sobresale del cajón bajo la losa superior.</p><label class="sections-field"><span>Vuelo del ala a cada lado (m)</span><input type="number" min="0" step=".001" data-section-wing value="${m(wingWidth(draft,e.ancho_mm))}"></label>`:''}${draft.tipo!=='escalera'?`<label class="sections-field"><span>Pendiente transversal a dos aguas (%)</span><input type="number" readonly data-section-slope value="1"></label><p class="sections-info">Valor fijo por regla del proyecto. El eje es el punto alto. La superficie desciende hacia ambos bordes, con cara inferior horizontal. El espesor superior se mide en el centro. Es independiente de la pendiente longitudinal.</p>`:''}<div class="sections-grid">${ds.filter(d=>!variable||d.key!=='canto_mm').map(input).join('')}</div>${variable?`<p class="sections-info">Este archivo contiene un perfil de canto importado. Se conserva para no alterar la geometría existente. Al insertar un descanso, el canto se calcula automáticamente.</p><div class="sections-info">${profile(draft).map(p=>`Posición ${esc(p.t)} · alto ${fmt(p.canto_mm)} m`).join('<br>')}</div><label class="sections-field"><span>Vista en posición <b data-station-value>${station.toFixed(2)}</b></span><input type="range" min="0" max="1" step=".01" value="${station}" data-section-action="station"></label>`:''}${automatic?`<p class="sections-info">Canto automático por descanso. Cara inferior recta al 8 %; el alto aumenta hacia la porción baja.<span data-automatic-depth></span></p><label class="sections-field"><span>Vista en posición <b data-station-value>${station.toFixed(2)}</b></span><input type="range" min="0" max="1" step=".01" value="${station}" data-section-action="station"></label>`:''}<div data-section-preview></div><div class="sections-errors" data-section-errors></div><p class="sections-info" data-section-impact></p><div class="sections-actions"><button type="button" class="primary" data-section-action="apply">${isNew?'Crear y asignar':'Aplicar a esta familia'}</button><button type="button" data-section-action="duplicate">Duplicar para este tramo</button><button type="button" data-section-action="new">Nueva familia</button></div></section>`;
      preview();
    }
    function preview(){
      const e=edge();if(!e||!draft)return;
      const context=edgeContext(model(),e),effective=root.VolumePreview?.sectionFamily(model(),e,draft)||draft,errors=validate(effective,e.ancho_mm,context),used=model().tramos.filter(t=>t.familia===familyId||t===e);
      for(const other of used.filter(t=>t.id!==e.id))for(const err of validate(root.VolumePreview?.sectionFamily(model(),other,draft)||draft,other.ancho_mm,edgeContext(model(),other)))errors.push(`${other.id}: ${err}`);
      container.querySelector('[data-section-preview]').innerHTML=render(effective,e.ancho_mm,{...context,t:station});
      const automaticDepth=container.querySelector('[data-automatic-depth]');if(automaticDepth){const values=profile(effective).map(p=>p.canto_mm);automaticDepth.textContent=` Porción alta: ${fmt(Math.min(...values))} m · porción baja: ${fmt(Math.max(...values))} m.`;}
      container.querySelector('[data-section-errors]').textContent=[...new Set(errors)].slice(0,5).join(' ');
      container.querySelector('[data-section-impact]').textContent=isNew?`La nueva familia se asignará únicamente a ${e.id}.`:`Al aplicar se ${used.length===1?"actualizará":"actualizarán"} ${used.length} tramo${used.length===1?'':'s'}: ${used.map(t=>t.id).join(', ')}. Duplica la familia para cambiar sólo ${e.id}.`;
      container.querySelector('[data-section-action="apply"]').disabled=!!errors.length;
      container.querySelector('[data-section-action="duplicate"]').disabled=!!validate(effective,e.ancho_mm,context).length;
    }
    function apply(duplicate=false){
      const e=edge(),data=model();if(!e)return;
      const id=duplicate?uniqueId(data,familyId+"_"+e.id):isNew?container.querySelector('[data-section-id]').value.trim():familyId;
      if(!id||isNew&&data.familias[id]){message("Usa un identificador nuevo para la familia.",true);return;}
      const affected=duplicate||isNew?[e]:data.tramos.filter(t=>t.familia===familyId||t===e);
      const errors=affected.flatMap(t=>validate(root.VolumePreview?.sectionFamily(data,t,draft)||draft,t.ancho_mm,edgeContext(data,t)));
      if(errors.length){message(errors[0],true);return;}
      options.onBeforeChange?.();data.familias ||= {};data.familias[id]={...clone(draft),...((duplicate||isNew)?{uuid:uid()}:{})};
      e.familia=id;
      if(draft.tipo==="escalera")affected.forEach(t=>{t.tipo="viga";t.funcion="escalera";t.rasante=[{t:0,f:0},{t:1,f:1}];});
      else affected.forEach(t=>{if(t.funcion==="escalera")delete t.funcion;});
      familyId=id;isNew=false;options.onChange?.({familyId:id,duplicated:duplicate,affectedEdges:affected.map(t=>t.id)});message(`Familia ${id} aplicada a ${affected.length} tramo${affected.length===1?'':'s'}.`);if(!disposable)draw();
    }
    function change(event){
      const input=event.target,key=input.dataset.sectionField,action=input.dataset.sectionAction;
      if(input.hasAttribute('data-section-slope')){input.value='1';draft.pendiente_transversal_pct=1;preview();}
      else if(input.hasAttribute('data-section-wing')){
        draft=withWingWidth(draft,edge().ancho_mm,input.valueAsNumber*1000);
        container.querySelector('[data-section-field="ancho_alma_superior_mm"]').value=m(draft.ancho_alma_superior_mm);preview();
      }
      else if(key){if(key==="macizado_mm"){draft.macizado_mm=500;input.value="0.5";preview();return;}draft[key]=finite(input.valueAsNumber)?(key==="numero_peldanos"?input.valueAsNumber:Math.round(input.valueAsNumber*1000)):NaN;if(key==="canto_mm")delete draft.canto_fin_mm;
        if(key==="ancho_alma_superior_mm"&&draft.tipo==="cajon"){
          draft.ala_mm=wingWidth(draft,edge().ancho_mm);
          container.querySelector('[data-section-wing]').value=m(draft.ala_mm);
        }preview();}
      else if(action==="station"){station=input.valueAsNumber;container.querySelector('[data-station-value]').textContent=station.toFixed(2);preview();}
    }
    function changed(event){const input=event.target,action=input.dataset.sectionAction;if(action==="choose")choose(input.value);else if(action==="type"){draft=defaults(input.value,edge()?.ancho_mm||2000);draw();}}
    function click(event){const button=event.target.closest('button');if(!button)return;const action=button.dataset.sectionAction;if(action==="apply")apply();else if(action==="duplicate")apply(true);else if(action==="new")choose(uniqueId(model(),"seccion"),true);}
    container.addEventListener('input',change);container.addEventListener('change',changed);container.addEventListener('click',click);
    function refresh(){if(disposable)return;const e=edge();if(e&&model()?.familias?.[e.familia])choose(e.familia);else{draft=defaults('cajon',e?.ancho_mm||2000);familyId=uniqueId(model()||{},'seccion');isNew=true;draw();}}
    refresh();return {refresh,destroy(){disposable=true;container.removeEventListener('input',change);container.removeEventListener('change',changed);container.removeEventListener('click',click);container.replaceChildren();}};
  }
  function foundationLayout(model,ids,f) {
    const ns=(model.nodos||[]).filter(n=>ids.includes(n.id));if(!ns.length)return {nodes:[],outside:[],centre:[0,0]};
    const centre=[ns.reduce((v,n)=>v+n.x,0)/ns.length,ns.reduce((v,n)=>v+n.y,0)/ns.length],angle=(f.angulo_deg||0)*Math.PI/180;
    const items=ns.map(n=>{const dx=n.x-centre[0],dy=n.y-centre[1],s=model.soportes?.find(s=>s.nodo===n.id);return {id:n.id,x:dx*Math.cos(angle)+dy*Math.sin(angle),y:-dx*Math.sin(angle)+dy*Math.cos(angle),rx:(s?.largo_mm||s?.diametro_mm||0)/2,ry:(s?.ancho_mm||s?.diametro_mm||0)/2};});
    return {nodes:items,centre,outside:items.filter(n=>Math.abs(n.x)+n.rx>f.largo_mm/2||Math.abs(n.y)+n.ry>f.ancho_mm/2).map(n=>n.id)};
  }
  function openFoundationEditor(options) {
    styles();const model=options.getModel();if(!model)return;
    const dialog=document.createElement('dialog');dialog.className='sections-modal';
    const existing=model.fundaciones||[],initial=new Set(options.selectedNodeIds||[]);let destination=existing.find(f=>f.nodos.some(id=>initial.has(id)))?.id||"__new";
    let draft=clone(existing.find(f=>f.id===destination)||{id:"F_COMPARTIDA",largo_mm:6000,ancho_mm:3000,alto_mm:1000,cota_superior_mm:0,angulo_deg:0,pilotes:[]});
    const getChecked=()=>[...dialog.querySelectorAll('[data-foundation-node]:checked')].map(n=>n.value);
    function fields(){const items=[['largo_mm','Longitud X local (m)'],['ancho_mm','Ancho Y local (m)'],['alto_mm','Espesor (m)'],['cota_superior_mm','Cota superior (m)'],['angulo_deg','Ángulo en planta (°)']];return items.map(([key,label])=>`<label class="sections-field"><span>${label}</span><input type="number" step=".001" data-foundation-field="${key}" value="${key==='angulo_deg'?draft[key]||0:m(draft[key])}"></label>`).join('');}
    dialog.innerHTML=`<button class="sections-close" data-foundation-close aria-label="Cerrar">×</button><h2>Compartir una fundación</h2><p class="sections-info">Los nodos y sus soportes siguen separados. La base se sitúa en el centro de sus nodos asociados.</p><div class="sections-modal-grid"><div><p>Selecciona los nodos que compartirán la base:</p><div class="sections-node-list">${(model.nodos||[]).map(n=>`<label><input type="checkbox" data-foundation-node value="${esc(n.id)}" ${initial.has(n.id)?'checked':''}> ${esc(n.id)}</label>`).join('')}</div><label class="sections-field"><span>Fundación de destino</span><select data-foundation-destination><option value="__new">Crear fundación compartida</option>${existing.map(f=>`<option value="${esc(f.id)}" ${f.id===destination?'selected':''}>${esc(f.id)} · ${esc(f.nodos.join(' + '))}</option>`).join('')}</select></label><div class="sections-grid" data-foundation-fields>${fields()}</div></div><div><div data-foundation-preview></div><p class="sections-info" data-foundation-summary></p><div class="sections-errors" data-foundation-errors></div><p class="sections-info">Se conservan los pilotes de la fundación de destino. Las bases que queden sin nodos se retiran junto con sus pilotes. Las cotas de los soportes se conservan. Puedes recuperar los cambios con Deshacer.</p></div></div><div class="sections-actions"><button class="primary" data-foundation-apply>Aplicar fundación compartida</button><button data-foundation-close>Cancelar</button></div>`;
    function allIds(){return [...new Set([...(existing.find(f=>f.id===destination)?.nodos||[]),...getChecked()])];}
    function errors(){const ids=allIds(),errs=[];if(getChecked().length<2)errs.push('Selecciona al menos dos nodos.');for(const key of ['largo_mm','ancho_mm','alto_mm'])if(!finite(draft[key])||draft[key]<=0)errs.push('Las dimensiones de la fundación deben ser positivas.');if(!finite(draft.cota_superior_mm)||!finite(draft.angulo_deg??0))errs.push('Introduce cotas y ángulo válidos.');const missing=ids.filter(id=>!model.soportes?.some(s=>s.nodo===id));if(missing.length)errs.push(`Crea primero los soportes de ${missing.join(', ')}.`);return errs;}
    function preview(){const ids=allIds(),layout=foundationLayout(model,ids,draft),errs=errors(),scale=Math.min(330/(draft.largo_mm||1),210/(draft.ancho_mm||1)),x=210,y=140;const rect=(cx,cy,w,h,fill,stroke)=>`<rect x="${cx-w/2}" y="${cy-h/2}" width="${w}" height="${h}" fill="${fill}" stroke="${stroke}"/>`;let svg=rect(x,y,draft.largo_mm*scale,draft.ancho_mm*scale,'#e2edf3','#427894');svg+=layout.nodes.map(n=>rect(x+n.x*scale,y-n.y*scale,Math.max(7,n.rx*2*scale),Math.max(7,n.ry*2*scale),layout.outside.includes(n.id)?'#f4c5b8':'#fff',layout.outside.includes(n.id)?'#ad4c36':'#2e6384')+`<text x="${x+n.x*scale}" y="${y-n.y*scale-10}" text-anchor="middle" font-size="11">${esc(n.id)}</text>`).join('');svg+=`<text x="210" y="280" text-anchor="middle" font-size="12">${fmt(draft.largo_mm)} × ${fmt(draft.ancho_mm)} m · ejes locales de la base</text>`;dialog.querySelector('[data-foundation-preview]').innerHTML=errs.length?'<div class="sections-empty">Completa la selección y las dimensiones para revisar la base.</div>':`<svg class="sections-svg" viewBox="0 0 420 300" role="img" aria-label="Planta de fundación y soportes">${svg}</svg>`;const removed=existing.filter(f=>f.id!==destination&&f.nodos.every(id=>ids.includes(id)));dialog.querySelector('[data-foundation-summary]').textContent=`Nodos asociados: ${ids.join(', ')||'ninguno'}. Pilotes conservados: ${draft.pilotes?.length||0}. Bases que se retiran: ${removed.map(f=>f.id).join(', ')||'ninguna'}.`;dialog.querySelector('[data-foundation-errors]').textContent=[...errs,...(layout.outside.length?[`Soportes fuera del contorno: ${layout.outside.join(', ')}. Amplía o gira la base antes de generar.`]:[])].join(' ');dialog.querySelector('[data-foundation-apply]').disabled=!!errs.length;}
    dialog.addEventListener('input',event=>{const key=event.target.dataset.foundationField;if(key){const value=event.target.valueAsNumber;draft[key]=key==='angulo_deg'?value:value*1000;}preview();});
    dialog.addEventListener('change',event=>{if(event.target.matches('[data-foundation-destination]')){destination=event.target.value;draft=clone(existing.find(f=>f.id===destination)||{id:'F_COMPARTIDA',largo_mm:6000,ancho_mm:3000,alto_mm:1000,cota_superior_mm:0,angulo_deg:0,pilotes:[]});dialog.querySelector('[data-foundation-fields]').innerHTML=fields();}preview();});
    function close(){dialog.close();dialog.remove();}
    dialog.addEventListener('click',event=>{if(event.target.closest('[data-foundation-close]'))close();if(event.target.closest('[data-foundation-apply]')){if(errors().length)return;const ids=allIds();let id=destination;if(id==='__new'){let i=1;id='F_COMPARTIDA';const occupied=new Set([...(model.nodos||[]),...(model.tramos||[]),...(model.soportes||[]),...existing,...existing.flatMap(f=>f.pilotes||[])].map(x=>x.id));while(occupied.has(id))id='F_COMPARTIDA_'+i++;draft.uuid=uid();}options.onBeforeChange?.();model.fundaciones=existing.filter(f=>f.id!==destination).map(f=>({...f,nodos:f.nodos.filter(n=>!ids.includes(n))})).filter(f=>f.nodos.length);model.fundaciones.push({...clone(draft),id,nodos:ids});model.soportes.forEach(s=>{if(ids.includes(s.nodo))s.fundacion=id;});options.onChange?.({foundationId:id,nodeIds:ids});options.onMessage?.(`Fundación ${id} asociada a ${ids.join(', ')}.`);close();}});
    dialog.addEventListener('cancel',()=>dialog.remove());document.body.append(dialog);dialog.showModal();preview();return {close};
  }
  const api={mount,render,validate,geometry,wingWidth,withWingWidth,defaults,fields:type=>clone(defs[type]||[]),depthAt,foundationLayout,openFoundationEditor};
  root.Sections=api;if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:window);
