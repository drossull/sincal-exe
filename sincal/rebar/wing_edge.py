"""Physical bars along a wing extension's free edge, diagonal and anchorage."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
import math
import re
from types import SimpleNamespace

from .detail import detail_dimension_metadata, polyline_render_points
from .model import DIAMETROS_DISPONIBLES_MM
from .wing_exterior import make_open_path, make_single_hook_path
from .wing_mesh import _dot, _footing_material, _material_cell
from .wing_schedule import summarize_wing_bars


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _interval(first, last, planes):
    low, high = 0., 1.
    direction = tuple(b-a for a,b in zip(first,last))
    for normal,bound in planes:
        available = bound-_dot(normal,first)
        coefficient = _dot(normal,direction)
        if abs(coefficient) < 1e-12:
            if available < -1e-9:
                return None
        elif coefficient > 0:
            high = min(high,available/coefficient)
        else:
            low = max(low,available/coefficient)
        if high < low-1e-9:
            return None
    return max(0.,low), min(1.,high)


def _covered_segment(first, last, solids):
    intervals = [value for solid in solids if (value := _interval(first,last,solid)) is not None]
    covered = 0.
    for low,high in sorted(intervals):
        if low > covered+1e-8:
            break
        covered = max(covered,high)
    return covered >= 1.-1e-8


def _safe_solids(cells, covers, radius, footing_planes, footing_side_cover,
                 footing_bottom_cover, footing_top_cover, origin, axis, inward):
    """Cover-offset concrete cells with no fictitious cover at shared faces."""
    solids = []
    for index,cell in enumerate(cells):
        limits = []
        for face,(normal,bound) in cell.items():
            if (index == 0 and face in ('end','lower')) or (index == 1 and face == 'join'):
                clearance = 0.  # Joined concrete, not an exposed mouldage face.
            else:
                field = {'join':'end_cm','end':'end_cm','lower':'diagonal_cm'}.get(face,face+'_cm')
                clearance = covers[field]+radius
            limits.append((normal,bound-clearance))
        solids.append(tuple(limits))
    foundation = []
    for normal,bound in footing_planes:
        local = (_dot(normal,axis),_dot(normal,inward),normal[2])
        foundation.append((local,bound-_dot(normal,origin)-footing_side_cover-radius))
    foundation.append(((0.,0.,-1.),origin[2]-footing_bottom_cover-radius))
    # Elsewhere the top of the footing is exposed and needs its own cover.
    solids.append(tuple((*foundation,((0.,0.,1.),-footing_top_cover-radius))))
    # Below the main wing there is continuous concrete across the footing's
    # top. Preserve the wall side covers and the physical main footprint.
    under_wall = list(foundation)
    for face in ('outside','inside','join','end'):
        normal,bound = cells[0][face]
        clearance = (covers[face+'_cm']+radius if face in ('outside','inside') else 0.)
        under_wall.append((normal,bound-clearance))
    under_wall.append(((0.,0.,1.),0.))
    solids.append(tuple(under_wall))
    return tuple(solids)


def _validate_route(bar, solids, origin, axis, inward):
    def local(point):
        delta = tuple(value-zero for value,zero in zip(point,origin))
        return _dot(delta,axis), _dot(delta,inward), delta[2]
    def lift(point):
        return tuple(zero+point[0]*u+point[1]*v for zero,u,v in zip(bar.start_m,bar.axis_u,bar.axis_v))
    raw_flat = tuple(segment[0] for segment in bar.detail.partial_segments_m)+(bar.detail.partial_segments_m[-1][1],)
    raw = tuple(local(lift(point)) for point in raw_flat)
    for first,last in zip(raw,raw[1:]):
        if not _covered_segment(first,last,solids):
            raise ValueError('El recorrido o su prolongación sale del hormigón o invade sus recubrimientos; revisa el largo total y el moldaje.')
    radius = bar.bend_radius_cm/100
    for first,corner,last in zip(raw,raw[1:],raw[2:]):
        incoming = tuple(b-a for a,b in zip(first,corner))
        outgoing = tuple(b-a for a,b in zip(corner,last))
        incoming = tuple(value/math.dist(first,corner) for value in incoming)
        outgoing = tuple(value/math.dist(corner,last) for value in outgoing)
        cosine = max(-1.,min(1.,_dot(incoming,outgoing)))
        angle = math.acos(cosine)
        if angle < 1e-9:
            continue
        tangent = radius*math.tan(angle/2)
        triangle = (corner, tuple(value-tangent*u for value,u in zip(corner,incoming)),
                    tuple(value+tangent*u for value,u in zip(corner,outgoing)))
        # A fillet lies in the convex triangle between its theoretical corner
        # and tangencies. One containing convex solid guarantees every point
        # of the arc, without relying on display sampling.
        if not any(all(_dot(n,point) <= bound+1e-8 for point in triangle for n,bound in solid)
                   for solid in solids):
            raise ValueError('Un doblez del canto no cabe con sus recubrimientos en el hormigón; revisa el recorrido.')


def build_wing_edge(profile, state, abutment_state, side):
    result = {'valid':False,'issues':[],'marks':[],'details':[],'bars':[],
              'removed_bars':[],'total_kg':0.,'representation':'physical_pieces','edge_extensions_cm':[]}
    issues = result['issues']
    def problem(message):
        issues.append({'severity':'error','message':message})
    if side not in ('left','right'):
        problem('Selecciona el lado del ala.'); return result
    if not profile.get('extension_enabled'):
        result['valid'] = True
        return result
    for message in profile.get('issues',()):
        issues.append({'severity':'warning','message':str(message)})
    if not isinstance(state,Mapping):
        problem('Completa la configuración de los fierros de canto.'); return result
    quantity,diameter,total = (state.get(key) for key in ('quantity','diameter_mm','total_cm'))
    minimum,enabled,hook = (state.get(key) for key in ('min_extension_cm','top_hook_enabled','top_hook_cm'))
    if not _number(quantity) or int(quantity) != quantity or not 2 <= quantity <= 5000:
        problem('Ingresa una cantidad entera de fierros de canto (mínimo 2 y máximo 5000).')
    if not _number(diameter) or diameter not in DIAMETROS_DISPONIBLES_MM:
        problem('Completa un diámetro disponible para los fierros de canto.')
    if not _number(total) or not 0 < total <= 1200:
        problem('Ingresa el largo total por eje del fierro de canto, mayor que cero y máximo 1200 cm.')
    if not _number(minimum) or minimum < 100:
        problem('La prolongación mínima del canto debe ser al menos 100 cm.')
    if not isinstance(enabled,bool):
        problem('Indica si el fierro de canto lleva gancho superior.')
    if enabled and (not _number(hook) or hook <= 0):
        problem('Completa el tramo recto del gancho superior del canto.')
    mark = state.get('mark')
    if not isinstance(mark,str) or not re.fullmatch(r'[0-9]+[A-Za-z]*',mark.strip()):
        problem('Completa una marca válida para los fierros de canto.')
    wing = (abutment_state or {}).get('wings',{}).get(side,{})
    raw_cover = wing.get('cover',{})
    cover_fields = ('outside_cm','inside_cm','top_cm','end_cm','diagonal_cm')
    for key in cover_fields:
        value = raw_cover.get(key)
        if not _number(value) or value < 0:
            problem('Completa todos los recubrimientos del ala antes de calcular sus fierros de canto.')
            break
    foundation_cover = (abutment_state or {}).get('cover',{})
    for key in ('inferior_cm','superior_cm','lateral_cm'):
        value = foundation_cover.get(key)
        if not _number(value) or value < 0:
            problem('Completa los recubrimientos inferior, superior y lateral de la zapata para comprobar la prolongación del canto.')
            break
    removals = state.get('removed_pieces',[])
    if not isinstance(removals,list) or len(removals) > 5000:
        problem('La lista de fierros de canto eliminados no es válida.')
    else:
        seen = set()
        for record in removals:
            if (not isinstance(record,Mapping) or set(record) != {'id','signature'}
                    or not isinstance(record['id'],str)
                    or not re.fullmatch(r'wing:(left|right):edge:[0-9]{1,6}',record['id'])
                    or record['id'] in seen or not isinstance(record['signature'],str)
                    or not re.fullmatch(r'[a-f0-9]{64}',record['signature'])):
                problem('La identidad o firma de un fierro de canto eliminado no es válida.'); break
            seen.add(record['id'])
    if any(issue['severity']=='error' for issue in issues):
        return result
    covers = {key:raw_cover[key]/100 for key in cover_fields}
    frame = profile['frame']
    origin,axis,inward = frame['origin_m'],frame['axis_u'],frame['inward']
    thickness = profile['geometry']['thickness_cm']/100
    radius,steel_radius = 3*diameter/1000,diameter/2000
    first_depth,last_depth = covers['outside_cm']+steel_radius,thickness-covers['inside_cm']-steel_radius
    spacing = (last_depth-first_depth)/(int(quantity)-1)
    if spacing < diameter/1000-1e-9:
        problem('La cantidad de fierros de canto no cabe entre los recubrimientos sin superponer barras.'); return result
    def world(u,depth,z):
        return tuple(zero+u*a+depth*n+(z if i==2 else 0.) for i,(zero,a,n) in enumerate(zip(origin,axis,inward)))
    try:
        cells = [_material_cell(item,origin,axis,inward) for item in profile['meshes']]
        if len(cells) != 2:
            raise ValueError('Falta el moldaje completo de ala y aleta para definir el canto.')
        footing_planes,footing_side_cover = _footing_material(abutment_state)
        for x,y in profile['main_footprint_m']:
            if any(_dot(n,(x,y,0.)) > bound+1e-8 for n,bound in footing_planes):
                raise ValueError('El ala principal sale de la huella de la zapata; revisa el moldaje antes de prolongar el canto.')
        solids = _safe_solids(cells,covers,steel_radius,footing_planes,footing_side_cover,
                              foundation_cover['inferior_cm']/100,foundation_cover['superior_cm']/100,
                              origin,axis,inward)
        free,bottom,join,roof = (cells[1][face] for face in ('end','lower','join','top'))
        if free[0][0] <= 1e-9 or join[0][0] >= -1e-9 or bottom[0][2] >= -1e-9 or roof[0][2] <= 1e-9:
            raise ValueError('Las caras de la aleta no definen un borde libre y una diagonal utilizables.')
        slope = -bottom[0][0]/bottom[0][2]
        if slope < -1e-9:
            raise ValueError('La diagonal de la aleta tiene una pendiente incompatible con la prolongación hacia la zapata.')
        diagonal = (-1/math.hypot(1,slope),0.,-slope/math.hypot(1,slope))
        angle = math.acos(max(-1.,min(1.,-diagonal[2])))
        tangent = radius*math.tan(angle/2)
        hook_m = hook/100 if enabled else 0.
        top_correction = radius*(math.pi/2-1) if enabled else 0.
        bars,extensions = [],{}
        for index in range(int(quantity)):
            depth = first_depth+spacing*index
            u = (free[1]-covers['end_cm']-steel_radius-free[0][1]*depth)/free[0][0]
            roof_positions = (u,u-hook_m-radius) if enabled else (u,)
            top = min((roof[1]-covers['top_cm']-steel_radius-roof[0][0]*pos-roof[0][1]*depth)/roof[0][2]
                      for pos in roof_positions)
            low = (bottom[1]-covers['diagonal_cm']-steel_radius-bottom[0][0]*u-bottom[0][1]*depth)/bottom[0][2]
            axila_u = (join[1]-join[0][1]*depth)/join[0][0]
            to_axila = (u-axila_u)/(-diagonal[0])
            if to_axila <= tangent or top-low <= tangent+(radius if enabled else 0.):
                raise ValueError(f'Fierro de canto {index+1}: no hay espacio para los dobleces entre la coronación, el borde libre y la axila.')
            base = top-low+hook_m+top_correction+radius*angle-2*tangent
            diagonal_length = total/100-base
            extension = diagonal_length-to_axila
            if extension < minimum/100-1e-9:
                raise ValueError(f'Fierro de canto {index+1}: el largo total deja {max(0.,extension*100):.1f} cm de prolongación; '
                                 f'se requieren al menos {minimum:g} cm. Aumenta el largo total o revisa las medidas.')
            start,corner = world(u,depth,top),world(u,depth,low)
            axila = world(axila_u,depth,low+to_axila*diagonal[2])
            end = world(u+diagonal_length*diagonal[0],depth,low+diagonal_length*diagonal[2])
            if end[2] < foundation_cover['inferior_cm']/100+steel_radius-1e-9:
                raise ValueError(f'Fierro de canto {index+1}: la prolongación atraviesa el recubrimiento inferior de la zapata; revisa el largo total.')
            identity = f'wing:{side}:edge:{index}'
            kwargs = dict(identity=identity,key=f'wing_{side}_edge',mark=mark.strip(),
                          label='Canto de aleta · borde libre y diagonal',spacing_cm=spacing*100)
            route = (start,corner,axila,end)
            if enabled:
                bar = make_single_hook_path(route,tuple(-v for v in axis),diameter,hook,**kwargs)
            else:
                bar = make_open_path(route,diameter,**kwargs)
            if abs(bar.developed_length_cm-total) > 1e-7:
                raise ValueError('No se pudo conservar el largo total por eje del fierro de canto.')
            _validate_route(bar,solids,origin,axis,inward)
            bars.append(bar)
            extensions[identity] = extension*100
    except (ValueError,TypeError,KeyError,ZeroDivisionError) as error:
        problem(str(error)); return result
    original = {bar.id:bar for bar in bars}
    removed_ids = set()
    for removal in removals:
        bar = original.get(removal['id'])
        matched = bar is not None and bar.signature == removal['signature']
        result['removed_bars'].append({**removal,'status':'removed' if matched else 'unresolved',
                                      **({'key':bar.key,'mark':bar.mark,'label':bar.label} if bar else {})})
        if matched:
            removed_ids.add(bar.id)
        else:
            problem('Un fierro de canto eliminado cambió de geometría. Restaura o revisa esa baja antes de insertar.')
    bars = [bar for bar in bars if bar.id not in removed_ids]
    rule = SimpleNamespace(key=f'wing_{side}_edge',mark=mark.strip(),label='Canto de aleta · borde libre y diagonal',
                           diameter_mm=diameter,spacing_cm=spacing*100,continuation_mark='')
    summary = summarize_wing_bars(bars,[rule],side)
    schedule = summary['schedule']
    issues.extend(asdict(issue) for issue in schedule.issues)
    result['valid'] = not any(issue['severity']=='error' for issue in issues)
    if not result['valid']:
        return result
    result['marks'] = [{**asdict(item),'kg':item.kg_steel,'area_cm2':item.area_m2*10000,'spacing_cm':spacing*100}
                       for item in schedule.marks]
    for piece in summary['details']:
        detail = {**asdict(piece),**detail_dimension_metadata(piece),
                  'points_m':polyline_render_points(piece),'measured_cm':piece.developed_length_cm}
        ranges = summary.get('detail_partial_ranges',{}).get(piece.key)
        if ranges:
            detail['partial_ranges_cm'] = ranges
            detail['detail_note'] = 'Largo total fijo; las parciales varían entre fierros. Se representa una pieza de la serie.'
        result['details'].append(detail)
    result['total_kg'] = schedule.total_kg
    result['bars'] = [{
        'id':bar.id,'signature':bar.signature,'key':bar.key,'element_key':f'abutment.{side}_wing',
        'label':bar.label,'mark':bar.mark,'marks':[bar.mark],'diameter_mm':bar.diameter_mm,
        'level':'edge','piece_role':bar.piece_role,'placement_id':bar.id,
        'length_cm':bar.length_cm,'developed_length_cm':bar.developed_length_cm,
        'bend_radius_cm':bar.bend_radius_cm,'lap_cm':0.,'lap_segments':[],
        'representation':'physical_pieces','points':bar.points_m,'vertices':bar.vertices_m,'bulges':bar.bulges,
        'main_start':bar.main_start_m,'main_end':bar.main_end_m,
    } for bar in bars]
    result['edge_extensions_cm'] = [{'id':bar.id,'extension_cm':extensions[bar.id]} for bar in bars]
    if any(bar.end_m[2] < origin[2]-1e-9 for bar in bars):
        issues.append({'severity':'warning','message':
            'La prolongación continúa la diagonal después de la axila y penetra en la zapata; se comprobaron sus recubrimientos.'})
    return result
