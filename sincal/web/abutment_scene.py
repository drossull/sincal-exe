"""Escena local de moldajes del estribo, sin FreeCAD ni acceso a CAD.

Fórmulas contrastadas con Proyecto-Puentes: gui/esquemas/estribos.py,
geometria_estribos.py, geometria_aparatos_apoyo.py e interfaz_topes.
Unidades de salida: m. X transversal, Y hacia salida, Z arriba; origen en
el centro de la zapata en planta y su cara inferior. s = Y - X*tan(theta).
Los perfiles que el esquema oficial declara nominales llevan quality=schematic.
No se calculan armaduras aquí y nunca se rellena una dimensión desconocida.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math

# Alto y ala inferior de los tipos publicados por vigas_predefinidas.py (mm).
_BEAMS = {1:(1010,720),2:(1350,720),3:(1510,850),4:(1700,850),5:(1850,850),
          6:(2000,950),7:(2200,950),8:(1350,720),9:(1510,720),10:(2010,840),
          11:(1860,720),12:(1881,700),13:(2600,450),14:(2250,940)}


def _num(value, field, *, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
        raise ValueError(f"Falta una medida válida: {field}.")
    if abs(value)>1e7 or (positive and value<=0) or (nonnegative and value<0):
        raise ValueError(f"Medida fuera de rango: {field}.")
    return float(value)


def _mesh(bottom, top):
    n=len(bottom)
    return {'vertices':[[float(v)/1000 for v in p] for p in (*bottom,*top)],
            'faces':[list(reversed(range(n))), list(range(n,2*n))] +
                    [[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]}


def _prism(footprint, lower, upper):
    low=lower if callable(lower) else lambda x,y:lower
    high=upper if callable(upper) else lambda x,y:upper
    return _mesh([(x,y,low(x,y)) for x,y in footprint],[(x,y,high(x,y)) for x,y in footprint])


def _cylinder(x,y,diameter,bottom,top):
    return _prism([(x+diameter/2*math.cos(i*math.tau/32),y+diameter/2*math.sin(i*math.tau/32)) for i in range(32)],bottom,top)


def _clip_x(polygon, x, keep_right):
    """Split a convex footprint at a transverse-profile change of slope."""
    result=[]
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        inside_a=(a[0]>=x) if keep_right else (a[0]<=x)
        inside_b=(b[0]>=x) if keep_right else (b[0]<=x)
        if inside_a:result.append(a)
        if inside_a != inside_b:
            fraction=(x-a[0])/(b[0]-a[0])
            result.append((x,a[1]+fraction*(b[1]-a[1])))
    clean=[]
    for point in result:
        if not clean or math.dist(point,clean[-1])>1e-8:clean.append(point)
    if len(clean)>1 and math.dist(clean[0],clean[-1])<1e-8:clean.pop()
    return clean


def _counterfort_plan(footprint, side, entry, angle, distance, thickness, width, orientation):
    """Same trapezoid construction as geometria_estribos.trapecio_contrafuerte_muro_ala."""
    a,b,c,d=footprint
    exterior,(q0,q1)=((a,d),(b,c)) if side=='izq' else ((b,c),(a,d))
    ux,uy=q1[0]-q0[0],q1[1]-q0[1]
    length=math.hypot(ux,uy);ux,uy=ux/length,uy/length
    nx,ny=-uy,ux
    if orientation=='perpendicular_ala':
        toward=(q0[0]-exterior[0][0],q0[1]-exterior[0][1])
        sign=1 if toward[0]*nx+toward[1]*ny>=0 else -1
        lx,ly=ux,uy;px,py=sign*nx,sign*ny
    elif orientation=='paralelo_espaldar':
        sy=-1 if entry else 1;sx=1 if side=='izq' else -1
        lx,ly=-sy*math.sin(angle),sy*math.cos(angle)
        px,py=sx*math.cos(angle),sx*math.sin(angle)
    else:raise ValueError('Orientación de contrafuerte desconocida.')
    denominator=px*nx+py*ny
    if abs(denominator)<1e-9:raise ValueError('Contrafuerte degenerado por su orientación.')
    delta=thickness*(lx*nx+ly*ny)/denominator
    w0,w1=(width,width+delta) if delta>=0 else (width-delta,width)
    if min(w0,w1)<=0 or distance+thickness>length:raise ValueError('El contrafuerte no cabe en el ala.')
    end=(q1[0]-distance*ux,q1[1]-distance*uy)
    outend=(end[0]+px*w1,end[1]+py*w1)
    outstart=(outend[0]-lx*thickness,outend[1]-ly*thickness)
    point=(outstart[0]-px*w0,outstart[1]-py*w0)
    along=(point[0]-q0[0])*ux+(point[1]-q0[1])*uy
    start=(q0[0]+along*ux,q0[1]+along*uy)
    return [start,end,outend,outstart]


def _stop_centres(beams,count):
    spaces=[(a+b)/2 for a,b in zip(beams,beams[1:])]
    if not spaces or count<=0:return []
    if count>=len(spaces):return spaces
    if len(beams)%2==0:
        centre=(len(spaces)-1)//2
        indices=list(range(len(spaces)))
        if count%2==0:indices.remove(centre)
        indices=sorted(indices,key=lambda i:(abs(i-centre),i))[:count]
    else:
        centre=len(spaces)//2
        indices=([centre] if count==1 else sorted(range(len(spaces)),key=lambda i:(abs(i-(centre-.5)),i))[:count])
    return [spaces[i] for i in sorted(indices)]


def build_scene(project_data, instance_key, reinforcement_state=None, *, use_state_geometry=False,
                include_wing_rebar=True):
    """Return independent meshes; absent optional elements are not fabricated.

    The parameter editor may explicitly preview its draft dimensions. This
    changes only a local copy of the source geometry, never the imported JSON,
    calculation state or the geometry checks used when inserting in CAD.
    """
    if not isinstance(project_data,Mapping):raise ValueError('El proyecto debe ser un objeto JSON.')
    if instance_key not in ('entrada','salida'):raise ValueError('Selecciona un estribo de entrada o salida.')
    es=project_data.get('estribos',{})
    if not isinstance(es,Mapping):raise ValueError('Los estribos deben ser un objeto JSON.')
    common=project_data.get('elementos_comunes',{})
    general=project_data.get('parametros_generales',{})
    piers=project_data.get('cepas',{})
    if not all(isinstance(group,Mapping) for group in (common,general,piers)):
        raise ValueError('Los grupos del proyecto deben ser objetos JSON.')
    globals_=piers.get('parametros_globales',{})
    if not isinstance(globals_,Mapping) or any(not isinstance(group,Mapping) for group in common.values()):
        raise ValueError('Los parámetros de los elementos deben ser objetos JSON.')
    issues=[];elements=[]
    scene={'units':'m','instance_key':instance_key,'elements':elements,'bars':[],
           'issues':issues,'reference':'Centro de la zapata; Z = 0 en su cara inferior.',
           'geometry_only':True,'geometry_source':'parameters' if use_state_geometry else 'project',
           'geometry_edited':False}
    state=reinforcement_state if isinstance(reinforcement_state,Mapping) else {}
    def n(key,**kw):return _num(es.get(key),key,**kw)
    def own(pattern,**kw):return n(pattern.format(e=instance_key),**kw)
    def add(key,label,meshes,schematic=False,note=None):
        if meshes:
            item={'key':'abutment.'+key,'label':label,'meshes':meshes,
                  'quality':'schematic' if schematic else 'parameterized'}
            if note:item['note']=note
            elements.append(item)
    def guarded(callback):
        try:callback()
        except (ValueError,TypeError,KeyError) as exc:issues.append(str(exc))
    try:
        if use_state_geometry:
            from .rebar import number
            geometry=state.get('geometry')
            if not isinstance(geometry,Mapping):
                raise ValueError('Completa las dimensiones de la zapata para actualizar la vista previa.')
            replacements={f'dado_muro_frontal_{source}_{instance_key}':number(geometry,field,1,10000)*10
                          for field,source in [('ancho_cm','ancho'),('largo_cm','largo'),('alto_cm','espesor')]}
            skew=number(geometry,'esviaje_grados',-89,89)
            scene['geometry_edited']=any(es.get(key)!=value for key,value in replacements.items()) or general.get('angulo_esviaje_puente')!=skew
            project_data=deepcopy(project_data)
            es=project_data['estribos']=dict(es)
            general=project_data['parametros_generales']=dict(general)
            es.update(replacements);general['angulo_esviaje_puente']=skew
            if scene['geometry_edited']:
                issues.append('Vista previa con dimensiones editadas de zapata y esviaje. El JSON original no se modifica; antes de insertar se validarán las medidas contra el dibujo.')
        theta=_num(general.get('angulo_esviaje_puente'),'angulo_esviaje_puente')
        if not -89<theta<89:raise ValueError('El esviaje debe estar entre −89 y 89 grados.')
        dims={}
        for output,jsonfield in [('width','ancho'),('length','largo'),('height','espesor')]:
            dims[output]=own('dado_muro_frontal_'+jsonfield+'_{e}',positive=True)
        angle=math.radians(theta);c=math.cos(angle);t=math.tan(angle)
        width,length,height=(dims[k] for k in ('width','length','height'))
        kind=es.get(f'tipo_estribo_{instance_key}')
        if kind not in ('muro_lleno','transparente'):raise ValueError('Falta un tipo de estribo compatible.')
        orientation=es.get(f'orientacion_dado_estribo_{instance_key}','romboide') if kind=='transparente' else 'romboide'
        if orientation not in ('romboide','rectangular','rectangular_rotado'):raise ValueError('Orientación de zapata desconocida.')
        ensanche=general.get('modo_ensanche') is True
        if ensanche:raise ValueError('El estribo en ensanche requiere la geometría de su excentricidad; vista pendiente.')
        # The legacy rectangular orientation is the old name for an unrotated
        # parallelogram grid; do not reinterpret rotated instances.
        if orientation=='rectangular_rotado':
            si=math.sin(angle)
            footprint=[(x*c-y*si,x*si+y*c) for x,y in ((-width/2,-length/2),(width/2,-length/2),(width/2,length/2),(-width/2,length/2))]
        else:
            footprint=[(x,s+x*t) for x,s in ((-width*c/2,-length/c/2),(width*c/2,-length/c/2),(width*c/2,length/c/2),(-width*c/2,length/c/2))]
        add('footing','Fundación / zapata',[_prism(footprint,0,height)])
        scene['footing']={'width_m':width/1000,'length_m':length/1000,'height_m':height/1000,
                          'skew_degrees':theta,'orientation':orientation}
    except (ValueError,TypeError,KeyError) as exc:
        issues.append(str(exc));return scene

    # Match the imported mouldage, or the editor's explicitly requested local
    # draft. Reinforcement is recalculated; it is never stretched to fit.
    from .abutment_scene_rebar import build_footing_bars
    expected={'ancho_cm':width/10,'largo_cm':length/10,'alto_cm':height/10,'esviaje_grados':theta}
    actual=state.get('geometry',{}) if isinstance(state.get('geometry',{}),Mapping) else {}
    matches=True
    for field,target in expected.items():
        val=actual.get(field)
        if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val) or abs(val-target)>1e-7:
            matches=False;break
    if state and not matches:
        issues.append('La geometría calculada de la zapata difiere del JSON o está incompleta. Actualízala para superponer su armadura sin deformarla.')
    else:
        overlay=build_footing_bars(state,orientation=orientation)
        scene['bars']=overlay['bars'];scene['reinforcement_note']=overlay['note']
        scene['removed_bars']=overlay['removed_bars']
        scene['geometry_only']=not bool(scene['bars'])
        issues.extend(overlay['issues'])

    # Pile positions use the same grid as _crear_pilotes_bajo_dado_estribo.
    def piles():
        if es.get(f'incluir_pilotes_dado_estribo_{instance_key}') is not True:return
        vals={k:own('pilotes_dado_estribo_{e}_'+k,positive=True) for k in ('diametro','largo','cantidad_transversal','cantidad_longitudinal')}
        nt,nl=vals['cantidad_transversal'],vals['cantidad_longitudinal']
        if nt!=int(nt) or nl!=int(nl) or nt*nl>500:raise ValueError('Cantidad de pilotes inválida (máximo 500).')
        st=own('pilotes_dado_estribo_{e}_separacion_transversal',nonnegative=True)
        sl=own('pilotes_dado_estribo_{e}_separacion_longitudinal',nonnegative=True)
        if (nt>1 and st==0) or (nl>1 and sl==0):raise ValueError('La separación de pilotes debe ser positiva.')
        meshes=[]
        for j in range(int(nl)):
            for i in range(int(nt)):
                a=(i-(nt-1)/2)*st;b=(j-(nl-1)/2)*sl
                if orientation=='rectangular_rotado':x,y=a*c-b*math.sin(angle),a*math.sin(angle)+b*c
                else:x,y=a*c,b/c+a*c*t
                meshes.append(_cylinder(x,y,vals['diametro'],-vals['largo'],0))
        add('pile','Pilotes',meshes)
    guarded(piles)

    try:
        tabs=project_data.get('tableros')
        if not isinstance(tabs,list) or not tabs:raise ValueError('Faltan tableros para reconstruir el ancho y perfil del estribo.')
        if any(not isinstance(tab,Mapping) for tab in tabs):raise ValueError('Cada tablero debe ser un objeto JSON.')
        first=tabs[0];adj=first if instance_key=='entrada' else tabs[-1]
        def value(key,group,tab=adj):
            return tab[key] if key in tab else common.get(group,{}).get(key)
        def val(key,group,tab=adj,**kw):return _num(value(key,group,tab),key,**kw)
        def transverse(x,tab,road_profile=False):
            slope=_num(tab.get('pendiente_longitudinal'),'pendiente_longitudinal')
            # _perfil_camino uses common widths/sidewalks, but the adjacent
            # deck's transverse pavement and longitudinal slopes.
            widths={} if road_profile else tab
            left=val('ancho_izq_pav','pavimento',widths,nonnegative=True);right=val('ancho_der_pav','pavimento',widths,nonnegative=True)
            ml=val('pend_izq_pav','pavimento',tab);mr=-val('pend_der_pav','pavimento',tab)
            factor=math.sqrt(1+slope*slope)
            if x<0:
                if x>=-left:return factor*ml*x
                side=(val('pend_pasillo_izq','pasillos',widths) if value('incluir_pasillo_izq','pasillos',widths) is True else ml)
                return factor*(-ml*left+side*(x+left))
            if x<=right:return factor*mr*x
            side=(-val('pend_pasillo_der','pasillos',widths) if value('incluir_pasillo_der','pasillos',widths) is True else mr)
            return factor*(mr*right+side*(x-right))
        def deck_bounds(tab):
            result=[]
            for ab,side in [('izq','izquierda'),('der','derecha')]:
                pavement=val('ancho_'+ab+'_pav','pavimento',tab,nonnegative=True)
                if value('incluir_pasillo_'+ab,'pasillos',tab) is True:extra=val('ancho_pasillo_'+ab,'pasillos',tab,nonnegative=True)
                else:
                    barrier=value('tipo_barrera_'+side,'pasillos',tab)
                    if barrier not in ('CON','SIN','NINGUNA'):raise ValueError('Falta el tipo de barrera para definir el ancho del muro.')
                    extra={'CON':365.,'SIN':359.,'NINGUNA':0.}[barrier]
                result.append(pavement+extra)
            return result
        bounds=deck_bounds(first)
        x1,x2=-bounds[0],bounds[1];xc=(x1+x2)/2
        sa=1 if instance_key=='entrada' else -1;so=-sa
        mesa=own('ancho_mesa_apoyo_estribo_{e}',positive=True)
        back=own('espesor_muro_espaldar_{e}',positive=True)
        wallheight=own('altura_cabezal_estribo_{e}' if kind=='transparente' else 'altura_muro_frontal_estribo_{e}',positive=True)
        advance=(length/2-(mesa+back)/2 if kind=='transparente' else own('dado_muro_frontal_avance_{e}',nonnegative=True))
        front=sa*(length/2-advance)/c;rear=front-sa*(mesa+back)/c;connection=rear+sa*back/c
        base=height
        if kind=='transparente':
            columnlength=own('columnas_estribo_{e}_largo',positive=True)
            base+=columnlength
        topaxis=base+wallheight
        # Coordinates before x-centering retain the roadway crown x=0.
        def xy(x,s):return x-xc,s+(x-xc)*t
        def quad(a,b,s1,s2):return [xy(a,s1),xy(b,s1),xy(b,s2),xy(a,s2)]
        firstslope=_num(first.get('pendiente_longitudinal'),'pendiente_longitudinal')
        def walltop(x,y):return topaxis+transverse(x+xc,first)-firstslope*(x+xc)*t
        breaks=sorted({x1,x2,*[p for p in (0,-val('ancho_izq_pav','pavimento',first),val('ancho_der_pav','pavimento',first),
                                         -val('ancho_izq_pav','pavimento',{}),val('ancho_der_pav','pavimento',{})) if x1<p<x2]})
        def strip(a,b,s1,s2,low,high):
            cuts=sorted({a,b,*[v for v in breaks if a<v<b]})
            return [_prism(quad(u,v,s1,s2),low,high) for u,v in zip(cuts,cuts[1:])]
        add('front_wall','Muro frontal' if kind=='muro_lleno' else 'Cabezal de estribo',strip(x1,x2,rear,front,base,walltop))
        if kind=='transparente':
            number=own('columnas_estribo_{e}_cantidad',positive=True)
            if number!=int(number) or number>100:raise ValueError('Cantidad de columnas inválida.')
            dia=own('columnas_estribo_{e}_diametro',positive=True)
            sep=own('columnas_estribo_{e}_separacion',nonnegative=True)
            mid=(rear+front)/2
            add('columns','Columnas del estribo',[_cylinder((i-(number-1)/2)*sep*c,mid+(i-(number-1)/2)*sep*math.sin(angle),dia,height,base) for i in range(int(number))])
    except (ValueError,TypeError,KeyError) as exc:
        issues.append(str(exc));return scene

    # Nominal roadway package from the official parameter-only preview.
    try:
        slope=_num(adj.get('pendiente_longitudinal'),'pendiente_longitudinal')
        beam_type=adj.get('tipo_viga_seleccionado')
        if isinstance(beam_type,bool) or beam_type not in _BEAMS:raise ValueError('Tipo de viga sin altura nominal conocida: espaldar y alas pendientes.')
        beamheight,flange=_BEAMS[beam_type]
        npwidth=val('ancho_total_neopreno_estribo','placas_apoyo',positive=True)
        nplength=val('longitud_total_neopreno_estribo','placas_apoyo',positive=True)
        count=val('num_placas_acero_internas_3mm_estribo','placas_apoyo',nonnegative=True)
        if count!=int(count):raise ValueError('Cantidad de placas de apoyo inválida.')
        layer=val('espesor_capa_neopreno_pura_estribo','placas_apoyo',positive=True)
        noinsert=value('sin_inserto_inferior_estribo','placas_apoyo')
        if not isinstance(noinsert,bool):raise ValueError('Falta definir el inserto inferior del apoyo.')
        bearing=(0 if noinsert else 94)+(count+1)*layer+count*3+25+abs(slope)*(nplength+140)/2
        bearing+=(50 if npwidth+140>flange-50 else 25)/math.sqrt(1+slope*slope)
        offsetkey=f'offset_cabezal_bajo_placa_{instance_key}'
        if offsetkey in es:offset=n(offsetkey)
        else:offset=_num(globals_.get('offset_cabezal_bajo_placa',0),'offset_cabezal_bajo_placa')-_num(globals_.get('deltaZ_cabezales',0),'deltaZ_cabezales')
        package=val('espesor_pav','pavimento',nonnegative=True)+val('espesor_losa','losa',positive=True)+beamheight+bearing+offset
        joint=n('junta_dilatacion_estribos',nonnegative=True)
        supportdelta=val('offset_travesano_extremo_desde_borde_losa','travesanos',nonnegative=True)-val('offset_y_vigas','vigas',nonnegative=True)
        roadheight=package+slope*sa*(joint/c+supportdelta)
        def road(x,y):return topaxis+roadheight-slope*(y-connection+xc*t)+transverse(x+xc,adj,True)
        nominal='Perfil nominal del esquema de Proyecto Puentes; la cota exacta depende de los sólidos de vigas y apoyos.'
        issues.append(nominal)
        add('back_wall','Muro espaldar',strip(x1,x2,rear,connection,walltop,road),True,nominal)
    except (ValueError,TypeError,KeyError) as exc:
        issues.append(str(exc));return scene

    wings={}
    def make_wings():
        if kind=='transparente':
            if es.get(f'incluir_aletas_estribo_{instance_key}') is not True:return
            thick=own('espesor_aleta_{e}',positive=True);winglength=own('largo_aleta_{e}',positive=True)
            minheight=own('alto_minimo_aleta_{e}',positive=True)
        else:thick=own('espesor_muro_ala_{e}',positive=True);winglength=own('largo_muro_ala_{e}',positive=True)
        extension_enabled=kind=='muro_lleno' and es.get(f'incluir_aletas_estribo_{instance_key}') is True
        if extension_enabled:
            extension_length=own('largo_aleta_{e}',positive=True)
            extension_min=own('alto_minimo_aleta_{e}',positive=True)
            extension_max=own('alto_maximo_aleta_{e}',positive=True)
        effective=winglength;ranges=[]
        for side in ('izq','der'):
            a,b=(x1,x1+thick) if side=='izq' else (x2-thick,x2)
            if kind=='muro_lleno':a,b=max(a,xc-width*c/2),min(b,xc+width*c/2)
            if a>=b:continue
            rot=own('rotacion_muro_ala_{e}_'+side)
            if abs(rot)>=89:raise ValueError('Giro del ala fuera del intervalo compatible.')
            if kind=='transparente':
                ranges.append((side,a,b,rot));continue
            if abs(rot)<1e-9:
                xe=a if side=='izq' else b
                for x in (a,b):
                    s0=rear+(xe-x)*t
                    available=(length/2/c-s0)/so if so>0 else (-length/2/c-s0)/so
                    effective=min(effective,available)
            else:
                ds=so*math.cos(math.radians(rot))+so*math.sin(math.radians(rot))*t
                available=(length/2/c-rear)/ds if ds>0 else (-length/2/c-rear)/ds
                effective=min(effective,available)
            ranges.append((side,a,b,rot))
        if effective<=0:raise ValueError('Las alas no caben en la huella de la zapata.')
        if effective<winglength-1e-6:issues.append('El largo de las alas se recorta al borde de la zapata, según Proyecto Puentes.')
        for side,a,b,rot in ranges:
            p1,p2=xy(a,rear),xy(b,rear)
            if abs(rot)<1e-9:
                xe=a if side=='izq' else b;ye=xy(xe,rear)[1]+so*effective
                fp=[p1,p2,(p2[0],ye),(p1[0],ye)]
            else:
                dx=-so*effective*math.sin(math.radians(rot));dy=so*effective*math.cos(math.radians(rot))
                fp=[p1,p2,(p2[0]+dx,p2[1]+dy),(p1[0]+dx,p1[1]+dy)]
            if kind=='muro_lleno':
                from .wing_geometry import build_wing_profile
                outer,inner=(fp[0],fp[1]) if side=='izq' else (fp[1],fp[0])
                end=fp[3] if side=='izq' else fp[2]
                original_inner_end=fp[2] if side=='izq' else fp[3]
                main_length=math.dist(outer,end)
                ux,uy=(end[0]-outer[0])/main_length,(end[1]-outer[1])/main_length
                side_offset=(inner[0]-outer[0],inner[1]-outer[1])
                nx,ny=-uy,ux
                if nx*side_offset[0]+ny*side_offset[1]<0:nx,ny=-nx,-ny
                normal_thickness=nx*side_offset[0]+ny*side_offset[1]
                local_issues=[]
                if extension_enabled:
                    ds=uy-ux*t
                    if abs(ds)<1e-9:raise ValueError('El ala no corta el borde exterior de la zapata.')
                    edge_length=(so*length/(2*c)-(outer[1]-outer[0]*t))/ds
                    if edge_length<=0:raise ValueError('El borde de la zapata queda detrás del arranque del ala.')
                    if abs(edge_length-main_length)>1e-5:
                        local_issues.append('La unión de la aleta se lleva al borde exterior de la zapata; el largo del ala difiere del nominal del JSON y requiere revisión.')
                    main_length=edge_length
                edge=(outer[0]+ux*main_length,outer[1]+uy*main_length)
                inner_edge=((inner[0]+ux*main_length,inner[1]+uy*main_length)
                            if extension_enabled else original_inner_end)
                reach=extension_length if extension_enabled else 0.
                tip=(edge[0]+ux*reach,edge[1]+uy*reach)
                inner_tip=(inner_edge[0]+ux*reach,inner_edge[1]+uy*reach)
                front_point=(outer[0],front+outer[0]*t)
                back_point=(outer[0],connection+outer[0]*t)
                front_depth=math.dist(outer,front_point)
                back_depth=math.dist(outer,back_point)
                metadata={
                    'instance_key':instance_key,'side':'left' if side=='izq' else 'right',
                    'json_side':side,'quality':'nominal','geometry_confirmed':False,
                    'geometry_edited':scene.get('geometry_edited',False),'extension_enabled':extension_enabled,
                    'geometry':{'thickness_cm':normal_thickness/10,'main_length_cm':main_length/10,
                                'extension_length_cm':reach/10,'top_join_cm':(road(*outer)-base)/10,
                                'top_edge_cm':(road(*edge)-base)/10,'top_tip_cm':(road(*tip)-base)/10,
                                'tip_height_cm':extension_min/10 if extension_enabled else 0.,
                                'front_height_cm':(walltop(*front_point)-base)/10,
                                'front_depth_cm':front_depth/10,'back_thickness_cm':back_depth/10},
                    'frame':{'origin_m':(outer[0]/1000,outer[1]/1000,base/1000),'axis_u':(ux,uy,0.),
                             'inward':(nx,ny,0.),'axis_z':(0.,0.,1.),'front_axis_u':(0.,so,0.),
                             'front_inward':(1. if side=='izq' else -1.,0.,0.)},
                    'front_available_width_cm':((x2-xc-outer[0]) if side=='izq' else (outer[0]-(x1-xc)))/10,
                    'side_offset_m':(side_offset[0]/1000,side_offset[1]/1000,0.),
                    'inner_main_length_delta_m':((inner_edge[0]-inner[0])*ux+(inner_edge[1]-inner[1])*uy-main_length)/1000,
                    'back_front_top_delta_cm':(road(*back_point)-road(*outer))/10,
                    'inner_top_join_delta_cm':(road(*inner)-road(*outer))/10,
                    'inner_top_edge_delta_cm':(road(*inner_edge)-road(*edge))/10,
                    'inner_top_tip_delta_cm':(road(*inner_tip)-road(*tip))/10,
                    'front_face_outer_m':(front_point[0]/1000,front_point[1]/1000,base/1000),
                    'back_front_outer_m':(back_point[0]/1000,back_point[1]/1000,base/1000),
                    'front_wall_meshes':deepcopy(next(item['meshes'] for item in elements if item['key']=='abutment.front_wall')),
                    'back_wall_meshes':deepcopy(next(item['meshes'] for item in elements if item['key']=='abutment.back_wall')),
                    'footing_meshes':deepcopy(next(item['meshes'] for item in elements if item['key']=='abutment.footing')),
                    'source':{'rotation_degrees':rot,'skew_degrees':theta,'espesor_muro_ala_cm':thick/10,
                              'largo_muro_ala_cm':winglength/10,'largo_muro_ala_efectivo_cm':effective/10,
                              'mesa_cm':mesa/10,'espaldar_cm':back/10,
                              'alto_maximo_aleta_cm':extension_max/10 if extension_enabled else None,
                              'alto_minimo_aleta_cm':extension_min/10 if extension_enabled else None,
                              'largo_aleta_cm':reach/10},'issues':local_issues,
                }
                profile=build_wing_profile(metadata)
                scene.setdefault('wing_geometry',{})[metadata['side']]=profile
                issues.extend(profile['issues'])
                # Reuse the same outer profile as the future steel calculation.
                # Other elements keep their own geometry and nominal heights.
                meshes=profile['meshes']
                fp=[tuple(1000*v for v in point) for point in profile['main_footprint_m']]
                if side=='der':fp=[fp[1],fp[0],fp[3],fp[2]]
                wings[side]=fp
                add('left_wing' if side=='izq' else 'right_wing','Ala izquierda' if side=='izq' else 'Ala derecha',meshes,True,nominal)
                continue
            low=base
            if kind=='transparente':
                def low(x,y,fp=fp):
                    rate=(y-fp[0][1])/(fp[3][1]-fp[0][1])
                    return base+(road(*fp[3])-minheight-base)*rate
            mesh=_prism(fp,low,road);wings[side]=fp
            add('left_wing' if side=='izq' else 'right_wing','Ala izquierda' if side=='izq' else 'Ala derecha',[mesh],True,nominal)
    guarded(make_wings)

    def front_console():
        if es.get(f'incluir_consola_frontal_{instance_key}') is not True:return
        reach=own('consola_frontal_{e}_largo',positive=True)/c
        depth=own('consola_frontal_{e}_profundidad_borde',positive=True)
        # Talud 45° en Y-Z: borde = profundidad, unión = profundidad + alcance Y.
        def low(x,y):
            s=y-x*t;distance=abs(s-front)
            return walltop(x,y)-depth-(reach-distance)
        add('front_console','Consola frontal',strip(x1,x2,front,front+sa*reach,low,walltop))
    guarded(front_console)

    def stops():
        meshes=[]
        ext=es.get('ancho_tope_exterior_estribos',globals_.get('ancho_tope_exterior'))
        ext=_num(ext,'ancho_tope_exterior_estribos',nonnegative=True)
        stopfront=front
        if es.get(f'incluir_consola_frontal_{instance_key}') is True and es.get(f'topes_abarcan_consola_frontal_{instance_key}') is True:
            stopfront+=sa*own('consola_frontal_{e}_largo',positive=True)/c
        if ext>0:
            z=topaxis+bearing+offset+300
            for a,b in ((x1,x1+ext),(x2-ext,x2)):meshes.extend(strip(a,b,connection,stopfront,walltop,z))
        if es.get('incluir_topes_interiores_estribos') is True:
            count=_num(globals_.get('num_topes_interiores'),'num_topes_interiores',nonnegative=True)
            countcut=adj.get('num_topes_interiores',count)
            countcut=_num(countcut,'num_topes_interiores',nonnegative=True)
            nv=val('num_vigas','vigas',positive=True);sep=val('separacion_vigas','vigas',positive=True)
            if any(v!=int(v) or v>100 for v in (count,countcut,nv)):raise ValueError('Cantidad de topes o vigas inválida.')
            recut=val('altura_recorte_travesano_sobre_cepa','travesanos',nonnegative=True)
            widthstop=n('ancho_tope_interior_estribos',positive=True)
            if recut>0:
                adjacent_bounds=deck_bounds(adj)
                adjacent_centre=(-adjacent_bounds[0]+adjacent_bounds[1])/2
                centers=_stop_centres([adjacent_centre+(i-(nv-1)/2)*sep for i in range(int(nv))],int(countcut))
                if len(centers)>count:
                    centre=(centers[0]+centers[-1])/2
                    centers=sorted(sorted(centers,key=lambda x:abs(x-centre))[:int(count)])
                correction=_num(globals_.get('correccion_altura_topes',0),'correccion_altura_topes')
                z=topaxis+bearing+offset+max(recut,400)+correction-50
                for x in centers:meshes.extend(strip(x-widthstop/2,x+widthstop/2,connection,stopfront,walltop,z))
        note='Alturas nominales de topes; dependen del recorte y voladizo del travesaño en el modelo original.'
        add('front_stop','Topes sísmicos',meshes,True,note)
        if meshes:issues.append(note)
    guarded(stops)
    def access_slab():
        if es.get('incluir_losas_acceso') is not True:return
        if es.get('tipo_losa_acceso')!=1:
            raise ValueError('Losa de acceso: el perfil de tipo 2 sigue pendiente.')
        reach=n('largo_losa_acceso',positive=True)/c
        slab=n('espesor_losa_acceso',positive=True)
        thick=own('espesor_aleta_{e}' if kind=='transparente' else 'espesor_muro_ala_{e}',positive=True)
        left,right=xy(x1+thick,rear),xy(x2-thick,rear)
        if right[0]<=left[0]:raise ValueError('La losa de acceso no cabe entre las alas.')
        ends=[]
        for side,p in (('izq',left),('der',right)):
            rotation=math.radians(own('rotacion_muro_ala_{e}_'+side))
            if abs(rotation)>=math.radians(89):raise ValueError('Giro del ala incompatible con la losa de acceso.')
            ends.append((p[0]-so*reach*math.sin(rotation),p[1]+so*reach*math.cos(rotation)))
        fp=[left,right,ends[1],ends[0]]
        turns=[(b[0]-a[0])*(q[1]-b[1])-(b[1]-a[1])*(q[0]-b[0])
               for a,b,q in zip(fp,fp[1:]+fp[:1],fp[2:]+fp[:2])]
        if not (all(v>1e-6 for v in turns) or all(v<-1e-6 for v in turns)):
            raise ValueError('Los bordes de la losa de acceso se cruzan; revisa los giros de las alas.')
        # Preserve every pavement/sidewalk break; a single prism would flatten
        # the transverse profile. Coordinates remain in the same local frame.
        cuts=sorted({min(p[0] for p in fp),max(p[0] for p in fp),
                     *[x-xc for x in breaks if min(p[0] for p in fp)<x-xc<max(p[0] for p in fp)]})
        meshes=[]
        for a,b in zip(cuts,cuts[1:]):
            section=_clip_x(_clip_x(fp,a,True),b,False)
            if len(section)>=3:meshes.append(_prism(section,lambda x,y:road(x,y)-slab,road))
        add('access_slab','Losa de acceso',meshes,True,nominal)
    guarded(access_slab)

    console_parameters={}
    def back_console():
        if es.get('incluir_losas_acceso') is not True:return
        if es.get('tipo_losa_acceso')!=1:
            raise ValueError('Consola del espaldar: el perfil de losa de acceso tipo 2 sigue pendiente.')
        # Confirmed legacy interpretation of Proyecto Puentes config_manager:
        # absent console fields inherit True / 250 / 250 / 50 mm. Preserve
        # explicit values (including False), and never write them into JSON.
        defaults={'consola_losa_acceso_ancho_apoyo':250.,
                  'consola_losa_acceso_canto_vertical':250.,
                  'consola_losa_acceso_solape_en_muro':50.}
        values={key:_num(es.get(key,value),key,positive=key!='consola_losa_acceso_solape_en_muro',
                         nonnegative=True) for key,value in defaults.items()}
        reach=values['consola_losa_acceso_ancho_apoyo']
        depth=values['consola_losa_acceso_canto_vertical']
        slab=n('espesor_losa_acceso',positive=True)
        thick=own('espesor_aleta_{e}' if kind=='transparente' else 'espesor_muro_ala_{e}',positive=True)
        # Only the visible part is shown, excluding the fusion overlap inside
        # the back wall. The source measures this console's reach along Y.
        if x1+thick>=x2-thick:raise ValueError('La consola del espaldar no cabe entre las alas.')
        def high(x,y):return road(x,y)-slab
        def low(x,y):
            endpoint=rear+so*reach+x*t
            return high(x,endpoint)-depth-(reach-abs((y-x*t)-rear))
        add('back_console','Consola del espaldar',strip(x1+thick,x2-thick,rear,rear+so*reach,low,high),True,nominal)
        console_parameters.update(reach=reach,depth=depth,slab=slab)
        element=next(e for e in elements if e['key']=='abutment.back_console')
        element['parameters_mm']=values
        element['inherited_fields']=[key for key in ('incluir_consola_losa_acceso',*defaults) if key not in es]
        if element['inherited_fields']:
            element['note']=nominal+' Medidas ausentes de consola: valores por defecto de Proyecto Puentes confirmados; el JSON original se conserva.'
    if es.get('incluir_consola_losa_acceso',True) is True:
        guarded(back_console)
    def counterforts():
        if not wings:raise ValueError('Contrafuertes: faltan las huellas de las alas.')
        if es.get(f'incluir_aletas_estribo_{instance_key}') is True:
            raise ValueError('Contrafuertes con aletas: el remate de apoyo requiere su perfil de prolongación; pendiente.')
        vals={key:own('contrafuerte_{e}_'+key,nonnegative=True) for key in ('espesor','ancho_superior','ancho_inferior','distancia_libre','altura_zona_pendiente','offset_inferior')}
        orient=es.get(f'contrafuerte_{instance_key}_orientacion','paralelo_espaldar')
        meshes=[]
        for side,fp in wings.items():
            def level(w):return _counterfort_plan(fp,side,instance_key=='entrada',angle,vals['distancia_libre'],vals['espesor'],w,orient)
            lower,upper=level(vals['ancho_inferior']),level(vals['ancho_superior'])
            z0=height;z1=z0+vals['offset_inferior'];z2=z1+vals['altura_zona_pendiente']
            if z1>z0:meshes.append(_prism(lower,z0,z1))
            if z2<=z1:raise ValueError('La altura de la zona pendiente del contrafuerte debe ser positiva.')
            if any(z2>road(x,y) for x,y in upper):raise ValueError('El contrafuerte supera la altura del ala; requiere revisar su encuentro.')
            meshes.append(_mesh([(x,y,z1) for x,y in lower],[(x,y,z2) for x,y in upper]))
        add('counterfort','Contrafuertes',meshes)
    if es.get(f'incluir_contrafuertes_mura_ala_{instance_key}') is True:
        guarded(counterforts)
    effective_wings = dict(scene.get('wing_geometry', {}))
    if include_wing_rebar and isinstance(state.get('wings'), Mapping):
        from .wing_geometry import build_wing_profile
        from .wing_exterior import preview_from_metadata
        for side, wing_state in state['wings'].items():
            metadata = scene.get('wing_geometry', {}).get(side)
            if metadata is None:
                issues.append(f'No hay moldaje disponible para el ala {side}.')
                continue
            try:
                profile = build_wing_profile(metadata, wing_state.get('geometry'))
                effective_wings[side] = profile
                element = next(item for item in elements if item['key'] == f'abutment.{side}_wing')
                element['meshes'] = profile['meshes']
                element['quality'] = 'parameterized' if wing_state.get('geometry_confirmed') else 'schematic'
                element['note'] = ('Perfil del ala revisado en sus parámetros.' if wing_state.get('geometry_confirmed')
                                   else 'Perfil nominal del ala; revisa sus cotas antes de calcular.')
                overlay = preview_from_metadata(metadata, side, wing_state, state)
                scene['bars'].extend(overlay['bars'])
                scene.setdefault('removed_bars', []).extend(overlay['removed_bars'])
                issues.extend(item['message'] for item in overlay['issues'])
            except (ValueError, TypeError, KeyError, StopIteration) as error:
                issues.append(f'Mallas del ala: {error}')
        scene['geometry_only'] = not bool(scene['bars'])

    def chamfers():
        # Proyecto Puentes adds concrete at the INNER wing/back-wall corners.
        # The two legs measure d along the actual faces, including their skew
        # and the wing's own rotation. They are not a removed external bevel.
        d = n('chaflan_estribos_medida', positive=True)
        for json_side, fp in wings.items():
            side = 'left' if json_side == 'izq' else 'right'
            profile = effective_wings.get(side)
            if profile:
                outer, corner, end, _ = [tuple(v*1000 for v in p)
                                          for p in profile['main_footprint_m']]
            else:
                outer, corner = (fp[0], fp[1]) if json_side == 'izq' else (fp[1], fp[0])
                end = fp[2] if json_side == 'izq' else fp[3]
            dx, dy = end[0]-corner[0], end[1]-corner[1]
            available = math.hypot(dx, dy)
            if available < d:
                raise ValueError(f'El chaflán de {d:g} mm no cabe en el ala {side}.')
            # A disconnected edited wing cannot acquire a concrete bridge by
            # silently moving its corner away from the back-wall plane.
            if abs(corner[1]-corner[0]*t-rear) > 1e-5:
                raise ValueError(f'Chaflán del ala {side}: revisa su encuentro con el espaldar después de editar el espesor.')
            toward = 1 if json_side == 'izq' else -1
            along_back = (corner[0]+toward*d*c, corner[1]+toward*d*math.sin(angle))
            along_wing = (corner[0]+d*dx/available, corner[1]+d*dy/available)
            triangle = [corner, along_back, along_wing]
            if not x1-xc <= along_back[0] <= x2-xc:
                raise ValueError(f'El chaflán del ala {side} supera el ancho del espaldar.')
            if kind == 'muro_lleno' and any(abs(x)>width*c/2+1e-6 or abs(y-x*t)>length/(2*c)+1e-6 for x,y in triangle):
                raise ValueError(f'El chaflán del ala {side} queda fuera de la zapata.')

            # Match the existing nominal/edited wing roof. The upper limit
            # remains nominal, just like the adjacent back wall in this scene.
            wing_roof = road
            if profile:
                vertices = profile['meshes'][0]['vertices']
                a, b, q = (tuple(v*1000 for v in vertices[i]) for i in (3, 7, 6))
                ux,uy,uz = (b[i]-a[i] for i in range(3))
                vx,vy,vz = (q[i]-a[i] for i in range(3))
                det = ux*vy-uy*vx
                if abs(det)<1e-9:
                    raise ValueError(f'El ala {side} no define una coronación válida para el chaflán.')
                gx,gy = (uz*vy-uy*vz)/det, (ux*vz-uz*vx)/det
                def wing_roof(x,y):return a[2]+gx*(x-a[0])+gy*(y-a[1])
            def high(x,y):return min(road(x,y),wing_roof(x,y))
            # If an explicit access-slab console is present, its underside is
            # the upper limit of this additive corner, not its top surface.
            console = next((e for e in elements if e['key']=='abutment.back_console'), None)
            if console:
                roof = high
                reach = console_parameters['reach']
                depth = console_parameters['depth']
                slab = console_parameters['slab']
                def high(x,y):
                    distance=so*(y-x*t-rear)
                    underside=road(x,rear+so*reach+x*t)-slab-depth-(reach-distance)
                    return min(roof(x,y),underside)
            if any(high(x,y)<=base for x,y in triangle):
                raise ValueError(f'El chaflán del ala {side} no tiene altura disponible.')
            # Consistent winding for both sides; keep the semantic order of
            # corner/back/wing separately for dimensioning the plan.
            oriented=list(triangle)
            if ((along_back[0]-corner[0])*(along_wing[1]-corner[1])
                    -(along_back[1]-corner[1])*(along_wing[0]-corner[0]))<0:
                oriented=[corner,along_wing,along_back]
            mesh=_prism(oriented,base,high)
            mesh['part']='wing_back_chamfer'
            element=next(e for e in elements if e['key']==f'abutment.{side}_wing')
            # Do not change the wing's calculation profile or any existing
            # steel. This concrete addition is available for the next family.
            element['meshes']=[*element['meshes'],mesh]
            element['chamfer']={'measure_m':d/1000,
                                'footprint_m':[[x/1000,y/1000] for x,y in triangle],
                                'height_quality':'nominal'}
    if es.get('incluir_chaflanes_estribos') is True:
        guarded(chamfers)
    return scene
