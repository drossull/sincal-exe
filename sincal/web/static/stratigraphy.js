// Documentary values are read-only. Material choices are drawing conventions,
// not changes to the official descriptions, recovery, SPT or depths.
export async function renderStratigraphy(ctx){
  const {api,node,button,section,notify,job,project,changed,current}=ctx;
  const input=section('estratigrafia-informe','Estratigrafía');
  input.append(node('p','Carga el informe de mecánica de suelos y selecciona un sondaje. Se identifica el formato por sus tablas antes de insertar; la vista previa y el dibujo CAD usan el mismo formato.'));
  input.append(node('p','Formatos: tablas resumen VISAN e informes individuales tipo Puerto Octay. Puedes mantener hasta 10 informes en la sesión. No se estiman cifras desde curvas; los escaneos sin texto todavía no son compatibles.','muted'));
  const output=section('estratigrafia-revision','Sondajes, vista previa y evidencia');
  let selected=project.stratigraphy?.report?.boreholes?.[0]?.key, includeTable=false, revision=0;
  let annotationScale={name:'1:100 (m) · referencia de vista previa',value:10};
  function cadScale(expected){
    if(expected.status!=='ready')throw Error(expected.message);
    if(expected.active?.insunits!==6)throw Error('La estratigrafía requiere un dibujo en metros (INSUNITS=6).');
    const scale=expected.active?.annotation_scale;
    if(!scale?.name||!Number.isFinite(scale.value)||scale.value<=0)throw Error('No se pudo leer la escala anotativa de CAD.');
    return scale;
  }
  function table(parent,headers,rows){
    const wrap=node('div',undefined,'table-wrap'),t=node('table'),head=node('tr'),body=node('tbody');
    headers.forEach(h=>head.append(node('th',h)));const th=node('thead');th.append(head);t.append(th);
    rows.forEach(values=>{const tr=node('tr');values.forEach(value=>tr.append(node('td',String(value))));body.append(tr);});t.append(body);wrap.append(t);parent.append(wrap);
  }
  async function refresh(){
    const ticket=++revision,state=project.stratigraphy;
    if(!state?.report)return;
    const result=await api('stratigraphy/preview',{report:state.report,table:includeTable,annotation_scale:annotationScale.value});
    if(ticket!==revision||project.stratigraphy!==state||!current())return;
    Object.assign(state,result);draw();return true;
  }
  function draw(){
    output.replaceChildren(node('h2','Sondajes, vista previa y evidencia'));
    const state=project.stratigraphy,report=state?.report;
    if(!report){output.append(node('p','Aún no has cargado un informe.'));return;}
    const reports=[report,...(state.library||[])];
    if(reports.length>1){
      const fileLabel=node('label','Informe'),fileSelect=node('select');fileSelect.setAttribute('aria-label','Informe de estratigrafía');fileLabel.append(fileSelect);output.append(fileLabel);
      reports.forEach((r,i)=>{const option=node('option',`${r.source} · ${r.boreholes.map(h=>h.name).join(', ')}`);option.value=i;fileSelect.append(option);});
      fileSelect.addEventListener('change',async()=>{const index=Number(fileSelect.value);project.stratigraphy={report:reports[index],library:reports.filter((_,i)=>i!==index)};selected=reports[index].boreholes[0]?.key;changed();try{await refresh();}catch(e){notify(e.message);}});
    }
    output.append(node('p',report.source));
    for(const notice of report.notices||[])output.append(node('p',notice,'muted'));
    const label=node('label','Sondaje'),select=node('select');label.append(select);output.append(label);
    for(const hole of report.boreholes){const option=node('option',`${hole.name} · ${hole.horizons?.length||hole.intervals.length} estratos · ${hole.tests.length} ensayos SPT`);option.value=hole.key;select.append(option);}
    if(!report.boreholes.some(h=>h.key===selected))selected=report.boreholes[0]?.key;
    select.value=selected;select.addEventListener('change',()=>{selected=select.value;draw();});
    const hole=report.boreholes.find(h=>h.key===selected);if(!hole)return;
    const checks=state.checks?.find(c=>c.key===hole.key);
    const format=checks?.format;
    output.append(node('p',`Formato identificado: ${format?.label||'No reconocido'}`,'badge'));
    if(format?.description)output.append(node('p',format.description,'muted'));
    for(const warning of checks?.warnings||[])output.append(node('p',warning,'badge'));
    for(const error of checks?.errors||[])output.append(node('p',error,'badge'));
    const toggle=node('label','Incluir tablas de valores debajo del gráfico'),inc=node('input');inc.type='checkbox';inc.checked=includeTable;toggle.prepend(inc);output.append(toggle);
    inc.addEventListener('change',async()=>{includeTable=inc.checked;try{await refresh();}catch(e){notify(e.message);}});
    output.append(node('p',`Escala de vista previa: ${annotationScale.name}. Profundidades reales en metros; textos de 2,5 mm en papel.`,'badge'));
    output.append(button('Tomar escala anotativa de CAD',async()=>{
      annotationScale=cadScale(await api('cad/status'));await refresh();
    }));
    if(checks?.scene){output.append(renderScene(checks.scene, state.hatches));output.append(node('p','Hatch de la simbología PROSPECCIONES del maestro. CAD consulta el DWG instalado; si actualizas sus patrones, la vista previa puede variar. Textos CAD: RomanD anotativo, altura de papel 2,5. Los bolones y bloques descritos se superponen al suelo principal, sin inferir porcentajes.','muted'));}
    const drilling=node('details');drilling.append(node('summary','Intervalos de perforación y asignación de hatch (revisar)'));output.append(drilling);
    if(hole.horizons?.length){
      table(drilling,['Horizonte','Desde m','Hasta m','Espesor m','Descripción oficial','Pág.'],hole.horizons.map(r=>[r.index,r.start,r.end,r.thickness,r.description,r.page]));
      const samples=node('details');samples.append(node('summary','Pasadas y recuperación — no son los límites de los estratos'));output.append(samples);
      table(samples,['Muestra','Desde m','Hasta m','Método','Recuperado cm','Recuperación %','Descripción oficial','Pág.'],hole.samples.map(r=>[r.index,r.start,r.end,r.method,r.recovered,r.recovery,r.description||'No recuperada',r.page]));
      if(hole.water_depth)output.append(node('p',`Napa publicada: ${hole.water_depth} m · pág. ${hole.water_page}`));
    }else table(drilling,['Desde m','Hasta m','Perforado m','Recuperado m','Recuperación %','Descripción oficial','Pág.'],hole.intervals.map(r=>[r.start,r.end,r.drilled,r.recovered,r.recovery,r.description,r.page]));
    const choices=node('div',undefined,'strata-materials');drilling.append(choices);
    (hole.horizons?.length?hole.horizons:hole.intervals).forEach((row,index)=>{
      if(Number(row.end.replace(',','.'))<=Number(row.start.replace(',','.')))return;
      const label=node('label',`${row.start}–${row.end} m · ${row.description}`),choice=node('select');
      const unset=node('option','Sin asignar — requiere revisión');unset.value='sin_asignar';choice.append(unset);
      for(const [key,hatch]of Object.entries(state.hatches||{})){const option=node('option',`${hatch.label} · ${hatch.pattern}`);option.value=key;choice.append(option);}
      choice.value=row.material;choice.setAttribute('aria-label',`Hatch del intervalo ${index+1}`);label.append(choice);choices.append(label);
      choice.addEventListener('change',async()=>{row.material=choice.value;hole.reviewed=false;changed();try{await refresh();}catch(e){notify(e.message);}});
    });
    const tests=node('details');tests.append(node('summary','Tabla oficial NSPT — no es la recuperación'));output.append(tests);
    table(tests,['N.º','Desde m','Hasta m','Hincado m','Recuperado (unidad)','N1','N2','N3','NSPT / NF','Pág.'],hole.tests.map(r=>[r.index,r.start,r.end,r.driven||'—',r.recovered+' '+(r.recovered_unit||'m'),r.n1,r.n2,r.n3,r.nspt,r.page]));
    const vs=node('details');vs.append(node('summary','Vs por tramo — valores y rangos de la figura'));output.append(vs);
    if(hole.vs_bands?.length){
      table(vs,['Desde m','Hasta m','Vs m/s (figura)','Pág. figura','Tabla de profundidades'],hole.vs_bands.map(r=>[r.start,r.end,r.low===r.high?r.low:`${r.low} - ${r.high}`,r.page,`${r.profile} · pág. ${r.table_page}`]));
      vs.append(node('p','Se conserva el valor o rango impreso en la figura. Los límites se contrastan con la tabla geofísica; no se promedian velocidades ni se extiende la perforación.','muted'));
    }else vs.append(node('p','Sin tramos Vs reconocidos para este sondaje. Si abriste un reconocimiento guardado con una versión anterior, vuelve a cargar el PDF para buscarlos.','muted'));
    const evidence=node('details');evidence.append(node('summary','Páginas originales: cotejar tablas, figura y discrepancias'));output.append(evidence);
    for(const [page,data]of Object.entries(report.pages||{})){
      const part=node('details');part.append(node('summary','Página PDF '+page));
      part.addEventListener('toggle',()=>{if(!part.open||part.dataset.loaded)return;part.dataset.loaded='true';if(data.image_png){const img=node('img');img.src='data:image/png;base64,'+data.image_png;img.alt='Página original '+page;img.className='evidence';part.append(img);}part.append(node('pre',data.text||''));});evidence.append(part);
    }
    const review=node('label','He cotejado el formato identificado, las cifras, profundidades, avisos de discrepancia y hatch con el informe original.'),check=node('input');check.type='checkbox';check.checked=hole.reviewed&&(format?.id==='visan-summary-v1'||hole.reviewed_format===format?.id);review.prepend(check);output.append(review);
    const insert=button('Insertar este sondaje en AutoCAD / ZWCAD',async()=>{
      if(!check.checked||checks?.errors?.length)throw Error('Revisa el formato y el sondaje antes de insertar.');
      const expected=await api('cad/status');annotationScale=cadScale(expected);
      if(!await refresh())return;
      if(!current()||project.stratigraphy!==state||selected!==hole.key||!hole.reviewed)return;
      if(!confirm(`¿Insertar ${hole.name} exclusivamente en ${expected.active.name}?\nFormato: ${format?.label}\nEscala anotativa: ${annotationScale.name}. Profundidades reales (1 m = 1 unidad); texto de 2,5 mm en papel.\nSe actualizó la vista previa con esta escala. Se crearán entidades vectoriales agrupadas, sin guardar ni modificar otros dibujos. Selecciona el punto de inserción en CAD.`))return;
      const result=await job('cad-stratigraphy',{report,key:hole.key,table:includeTable,expected});notify(result.message);
    },true);
    const setEnabled=()=>{insert.disabled=!check.checked||!format?.id||!checks?.scene||Boolean(checks?.errors?.length);};
    check.addEventListener('change',()=>{hole.reviewed=check.checked;hole.reviewed_format=check.checked?format?.id:'';changed();setEnabled();});setEnabled();output.append(insert);
  }
  input.append(button('Añadir informes de Proyecto',async()=>{
    const files=await api('files/choose',{kind:'report',multiple:true});if(!files.length)return;
    if(files.length>10)throw Error('Selecciona hasta 10 informes.');
    const result=await job('stratigraphy',{files:files.map(f=>f.id)});
    const state=project.stratigraphy,reports=state?.report?[state.report,...(state.library||[])]:[];
    for(const r of result.reports)if(!reports.some(old=>old.sha256&&old.sha256===r.sha256))reports.push(r);
    if(reports.length>10)throw Error('La sesión admite 10 informes; no se reemplazó el reconocimiento actual.');
    if(new Blob([JSON.stringify(reports)]).size>45*1024*1024)throw Error('La evidencia supera 45 MB; divide los informes en sesiones separadas. Se conserva el reconocimiento anterior.');
    project.stratigraphy={report:reports[0],library:reports.slice(1)};selected=reports[0].boreholes[0]?.key;changed();if(current())await refresh();
  },true));
  input.append(button('Guardar reconocimiento',()=>{
    if(!project.stratigraphy?.report)throw Error('Carga un informe primero.');
    const blob=new Blob([JSON.stringify({schema:'sincal-stratigraphy-2',reports:[project.stratigraphy.report,...(project.stratigraphy.library||[])]},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download='estratigrafia-sincal.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }));
  input.append(node('p','Los informes y reconocimientos guardados se incorporan desde Proyecto.'));
  if(project.stratigraphy?.report)await refresh();else draw();
}

export function renderScene(scene,hatches){
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',scene.viewbox.join(' '));svg.setAttribute('class','stratigraphy-preview');svg.setAttribute('role','img');svg.setAttribute('aria-label',scene.accessible_label||'Estratigrafía, recuperación porcentual, ensayos NSPT y tramos Vs disponibles');
  const colors={1:'#ff5959',3:'#68f778',5:'#579bff',7:'#ffffff',8:'#808080'};
  function shape(name,attrs,parent=svg){const el=document.createElementNS(ns,name);for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);parent.append(el);return el;}
  for(const item of scene.items){const stroke=colors[item.color]||'#fff';
    if(item.kind==='line')shape('line',{x1:item.points[0][0],y1:item.points[0][1],x2:item.points[1][0],y2:item.points[1][1],stroke,'stroke-width':.22});
    else if(item.kind==='circle')shape('circle',{cx:item.point[0],cy:item.point[1],r:item.radius,stroke,fill:'none','stroke-width':.24});
    else if(item.kind==='triangle')shape('polygon',{points:item.points.map(p=>p.join(',')).join(' '),fill:stroke});
    else if(item.kind==='hatch')shape('path',{d:patternPath(item.bounds,hatches[item.material].lines),fill:'none',stroke:'#b5b5b5','stroke-width':.14,'stroke-linecap':'round'});
    else if(item.kind==='text'){
      const text=shape('text',{x:item.point[0],y:item.point[1],fill:stroke,'text-anchor':{left:'start',right:'end',center:'middle'}[item.anchor],'dominant-baseline':'middle','font-size':2.5});
      const lines=item.text.split('\n');lines.forEach((line,i)=>{
        const span=shape('tspan',{x:item.point[0],dy:i?4:-2*(lines.length-1)},text);
        for(const part of line.split(/\b(NSPT)\b/g)){
          if(part==='NSPT'){
            span.append(document.createTextNode('N'));
            shape('tspan',{'font-size':'70%','baseline-shift':'sub'},span).textContent='SPT';
          }else span.append(document.createTextNode(part));
        }
      });
    }
  }return svg;
}

// Clip the actual master's pattern lines in paper coordinates, with CAD's Y
// upwards. Dash phase, angle and density are preserved (not symbolic icons).
export function patternPath(bounds,lines){
  const [x1,y1,x2,y2]=bounds,box=[x1,-y2,x2,-y1],path=[];
  const emit=(bx,by,ux,uy,a,b)=>path.push(`M${(bx+ux*a).toFixed(4)},${(-by-uy*a).toFixed(4)}L${(bx+ux*b).toFixed(4)},${(-by-uy*b).toFixed(4)}`);
  for(const [angle,bx,by,dx,dy,dashes]of lines){
    const rad=angle*Math.PI/180,ux=Math.cos(rad),uy=Math.sin(rad),vx=-uy,vy=ux,offset=vx*dx+vy*dy;
    if(Math.abs(offset)<1e-9)continue;
    const distances=[[box[0],box[1]],[box[0],box[3]],[box[2],box[1]],[box[2],box[3]]].map(([x,y])=>(vx*(x-bx)+vy*(y-by))/offset);
    const first=Math.ceil(Math.min(...distances)),last=Math.floor(Math.max(...distances));
    if(last-first>20000)throw Error('Patrón demasiado denso para la vista previa.');
    for(let n=first;n<=last;n++){
      const px=bx+n*dx,py=by+n*dy;let lo=-Infinity,hi=Infinity;
      for(const [p,u,min,max]of [[px,ux,box[0],box[2]],[py,uy,box[1],box[3]]]){
        if(Math.abs(u)<1e-10){if(p<min-1e-8||p>max+1e-8){lo=1;hi=0;break;}}
        else{const a=(min-p)/u,b=(max-p)/u;lo=Math.max(lo,Math.min(a,b));hi=Math.min(hi,Math.max(a,b));}
      }
      if(hi<lo)continue;
      if(!dashes.length){emit(px,py,ux,uy,lo,hi);continue;}
      const period=dashes.reduce((sum,v)=>sum+Math.abs(v),0);if(period<=0)continue;
      for(let cycle=Math.floor(lo/period);cycle<=Math.floor(hi/period);cycle++){
        let pos=cycle*period;
        for(const dash of dashes){const end=pos+Math.abs(dash);if(dash>=0&&end>=lo&&pos<=hi)emit(px,py,ux,uy,Math.max(lo,pos),Math.min(hi,dash===0?pos+.015:end));pos=end;}
      }
    }
  }return path.join('');
}
