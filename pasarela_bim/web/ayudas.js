/* Contextual explanations, shared by forms and the section inspector. */
(function(){
  'use strict';
  const texts={
    'Cota de terreno proyectado':'Altura del terreno proyectado en el centro de este apoyo, respecto de Z = 0 del proyecto. Un punto 6,50 m bajo el origen tiene cota −6,50 m. Cada apoyo tiene su propia cota, aunque comparta fundación. Cambiarla no mueve la estructura ni define la superficie de las pistas.',
    'Cota del tope de viga / origen':'Cota geográfica de la cara superior de la viga, sobre su eje y a mitad del atravieso. Ese punto corresponde a Z = 0 local. Cota geográfica de un punto = cota del origen + Z local.',
    'Cota del origen actual':'Cota geográfica que corresponde al Z = 0 del archivo actual. Para cambiar el origen al tope de la viga sin mover la estructura, utiliza «Origen en tope de viga».',
    'Este del origen':'Coordenada Este del punto de origen de la pasarela en el sistema de referencia de la planta, expresada en metros.',
    'Norte del origen':'Coordenada Norte del punto de origen de la pasarela en el sistema de referencia de la planta, expresada en metros.',
    'Norte: giro horario desde Y':'Ángulo desde el eje local Y positivo hasta el norte, medido en sentido horario en planta. 0° significa que Y positivo apunta al norte.',
    'Sistema de referencia':'Identifica el sistema de coordenadas de la planta, incluyendo proyección, zona y datum cuando corresponda. Debe coincidir con el usado para las coordenadas Este y Norte.',
    'Gálibo de proyecto':'Distancia vertical mínima requerida entre la carretera y la cara inferior de la viga. Se conserva como requisito. Las cotas de terreno en los apoyos no describen las pistas; por eso la comprobación del gálibo queda pendiente.',
    'Cota local':'Altura del nodo respecto de Z = 0. Modificarla puede afectar las conexiones; las rampas deben conservar el 8 % en sus sectores inclinados.',
    'X local':'Posición del nodo sobre el eje X del proyecto, en metros desde el origen. El X inicial sigue el atravieso.',
    'Y local':'Posición del nodo sobre el eje Y del proyecto, en metros desde el origen y perpendicular al X en planta.',
    'Longitud total':'Distancia en planta entre los ejes de los extremos del atravieso. Los retranqueos determinan después los extremos físicos de sus piezas.',
    'Ancho sección atravieso':'Ancho total de la sección de la viga del atravieso, incluidas sus alas. No representa por sí solo el ancho libre entre barandas.',
    'Ancho estructural':'Ancho total de la pieza estructural del tramo. En una viga cajón incluye ambas alas de la losa superior.',
    'Alto viga':'Distancia vertical entre la cara superior, sobre el eje de la sección, y la cara inferior de la viga.',
    'Alto viga en la porción alta':'Canto de la parte más alta de la viga. La cara inferior sigue una recta al 8 %; durante el descanso el canto aumenta hacia la parte baja. Un descanso de 1,50 m añade 0,12 m al canto de la porción baja.',
    'Retranqueo inicial':'Distancia en planta desde el nodo «Desde» hasta el inicio físico de la viga. Acorta la pieza sin mover el nodo ni su eje.',
    'Retranqueo final':'Distancia en planta desde el nodo «Hasta» hasta el final físico de la viga. Acorta la pieza sin mover el nodo ni su eje.',
    'Vuelo del ala a cada lado':'Cuánto sobresale la losa superior a cada lado del cajón. Ancho total = ancho superior del cajón + dos vuelos.',
    'Ancho superior del cajón sin alas':'Ancho exterior del cuerpo del cajón bajo la losa superior, sin incluir los aleros laterales.',
    'Ancho exterior inferior':'Ancho exterior de la base del cajón. Junto con el ancho superior y la altura define la inclinación de sus paredes.',
    'Espesor losa superior en el centro':'Espesor vertical de la losa superior medido en el eje. Con pendiente transversal del 1 % y cara inferior horizontal, el espesor disminuye hacia los bordes.',
    'Espesor losa inferior':'Espesor de hormigón entre el fondo del hueco interior y la cara inferior de la viga cajón.',
    'Espesor horizontal de alma':'Espesor horizontal de cada pared lateral del cajón en este modelo. No es la medida perpendicular a la pared inclinada.',
    'Macizado en cada extremo':'Zona sin hueco interior en cada extremo físico de la viga cajón. Está fijada en 0,50 m por extremo.',
    'Pendiente transversal a dos aguas':'La superficie superior desciende desde el eje hacia ambos bordes con pendiente fija del 1 %. Es independiente de la pendiente longitudinal del 8 %.',
    'Canto / espesor':'Espesor vertical de la sección maciza, medido en el eje del tramo.',
    'Ancho inferior':'Ancho de la cara inferior de la sección maciza. Puede diferir del ancho superior del tramo.',
    'Cota superior':'Altura de la cara superior del elemento respecto de Z = 0 local. En un soporte determina dónde termina la columna; en una fundación, la cara superior de la base.',
    'Altura sobre fundación':'Distancia vertical entre la cara superior de la fundación y el tope del soporte.',
    'Espesor del dado':'Altura vertical de la fundación. Su cara inferior se obtiene restando este espesor a su cota superior; desde allí bajan los pilotes.',
    'Giro en planta':'Rotación de la fundación respecto de los ejes locales del proyecto. Los desplazamientos locales de sus pilotes giran con ella.',
    'Desplazamiento X':'Desplazamiento en metros sobre el eje X de referencia indicado en este formulario. En pilotes, se mide desde el centro del dado y gira con él.',
    'Desplazamiento Y':'Desplazamiento en metros sobre el eje Y de referencia indicado en este formulario. En pilotes, se mide desde el centro del dado y gira con él.',
    'Diámetro':'Diámetro de la sección circular del elemento, en metros. En un pilote, su huella debe quedar dentro del dado.',
    'Número de peldaños':'Cantidad de peldaños del tramo de escalera. La huella y la contrahuella se calculan a partir de su longitud y desnivel.',
    'Espesor de losa inclinada':'Espesor de la losa que sostiene los peldaños de la escalera.',
    'Desde':'Nodo de inicio de la conexión. Define el sentido del tramo junto con el nodo «Hasta».',
    'Hasta':'Nodo final de la conexión. Sus coordenadas, junto con las del nodo inicial, definen la longitud y el desnivel.',
    'Familia':'Sección y parámetros compartidos por los tramos que usan esta familia. Duplicarla permite modificar sólo el tramo seleccionado.',
    'Familia del tramo':'Sección y parámetros compartidos por los tramos que usan esta familia. Duplicarla permite modificar sólo el tramo seleccionado.',
    'Longitud':'Longitud en metros del elemento. Para un pilote es la distancia vertical desde la cara inferior del dado hasta su punta.',
    'Disposición':'Número de vanos del atravieso: un vano entre dos extremos, o dos vanos con un nodo de apoyo intermedio.'
  };
  let serial=0,current=null,timer;
  const tip=document.createElement('div');tip.className='field-help-popup';tip.setAttribute('aria-hidden','true');tip.hidden=true;
  if(typeof tip.showPopover==='function')tip.setAttribute('popover','manual');
  document.body.append(tip);
  function close(){clearTimeout(timer);if(tip.matches(':popover-open'))tip.hidePopover();tip.hidden=true;current=null;}
  function show(label){
    clearTimeout(timer);if(!label?.isConnected)return;
    current=label;tip.textContent=label.dataset.helpText;tip.hidden=false;
    if(tip.showPopover)tip.showPopover();else (label.closest('dialog')||document.body).append(tip);
    // Keep the help outside the complete field, including its input.
    const r=label.getBoundingClientRect(),b=tip.getBoundingClientRect(),gap=8;
    tip.style.left=Math.max(gap,Math.min(r.left,innerWidth-b.width-gap))+'px';
    tip.style.top=(r.top-b.height-gap>=gap?r.top-b.height-gap:Math.min(r.bottom+gap,innerHeight-b.height-gap))+'px';
  }
  function decorate(){
    for(const label of document.querySelectorAll('label.field,label.sections-field')){
      if(label.dataset.helpText)continue;
      const title=label.querySelector('span'),input=label.querySelector('input,select');if(!title||!input)continue;
      const clone=title.cloneNode(true);clone.querySelectorAll('small').forEach(n=>n.remove());
      const name=clone.textContent.trim().replace(/\s*\((m|%|°)\)\s*$/,'');
      const help=texts[name];if(!help)continue;
      label.dataset.helpText=help;title.classList.add('field-help-label');
      const desc=document.createElement('span');desc.id='field-help-'+(++serial);desc.className='sr-only';desc.textContent=help;label.append(desc);
      input.setAttribute('aria-describedby',[input.getAttribute('aria-describedby'),desc.id].filter(Boolean).join(' '));
    }
    if(current&&!current.isConnected)close();
  }
  document.addEventListener('pointerover',event=>{
    const title=event.target.closest('.field-help-label');
    if(!title){if(event.target.closest('input,select,textarea,button'))close();return;}
    const label=title.closest('label[data-help-text]');if(!label||label===current)return;
    close();timer=setTimeout(()=>show(label),350);
  });
  document.addEventListener('pointerout',event=>{
    const title=event.target.closest('.field-help-label');
    if(title&&!title.contains(event.relatedTarget))close();
  });
  // Help must never compete with editing, including a delayed hover callback.
  document.addEventListener('pointerdown',close,true);
  document.addEventListener('focusin',close);
  document.addEventListener('input',close,true);
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&current){close();event.preventDefault();event.stopImmediatePropagation();}
    else close();
  },true);
  window.addEventListener('resize',close);document.addEventListener('scroll',close,true);
  let scheduled=false;new MutationObserver(()=>{if(!scheduled){scheduled=true;requestAnimationFrame(()=>{scheduled=false;decorate();});}}).observe(document.body,{childList:true,subtree:true});
  decorate();
})();
