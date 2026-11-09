"""Optional interior horizontal supplements, interleaved with real mesh bars."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import math
import re
from types import SimpleNamespace

from .detail import detail_dimension_metadata, polyline_render_points
from .model import DIAMETROS_DISPONIBLES_MM
from .wing_exterior import make_single_hook_path
from .wing_mesh import _dot, _front_thickness, _roof_limit_segment, build_wing_mesh
from .wing_route import horizontal_face_path
from .wing_schedule import summarize_wing_bars


def _positive(value, label):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f'Completa {label} con un número positivo.')
    return float(value)


def _planes(mesh):
    vertices = mesh['vertices']
    center = tuple(sum(p[i] for p in vertices)/len(vertices) for i in range(3))
    result = []
    for face in mesh['faces']:
        points = [vertices[index] for index in face]
        first = points[0]
        normal = None
        for second, third in zip(points[1:], points[2:]):
            a, b = (tuple(x-y for x,y in zip(point,first)) for point in (second,third))
            cross = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
            size = math.hypot(*cross)
            if size > 1e-12:
                normal = tuple(value/size for value in cross)
                break
        if normal is None:
            raise ValueError('El moldaje contiene una cara sin área.')
        bound = _dot(normal, first)
        if any(abs(_dot(normal, point)-bound) > 1e-8 for point in points):
            raise ValueError('El moldaje contiene una cara no plana; revisa sus cotas.')
        if _dot(normal, center) > bound:
            normal, bound = tuple(-value for value in normal), -bound
        result.append((normal, bound))
    return tuple(result)


def _inside(point, planes):
    return all(_dot(normal, point) <= bound+1e-8 for normal, bound, *_ in planes)


def _material(profile, covers):
    frame = profile['frame']
    cells = []
    for family, meshes in (('wing', profile['meshes']),
                            ('front', profile.get('front_wall_meshes', ())),
                            ('front', profile.get('back_wall_meshes', ()))):
        axis = frame['axis_u' if family == 'wing' else 'front_axis_u']
        inward = frame['inward' if family == 'wing' else 'front_inward']
        for mesh in meshes:
            faces = []
            for normal, bound in _planes(mesh):
                if normal[2] > 1e-8:
                    cover = covers['top_cm']
                elif normal[2] < -1e-8:
                    cover = covers['diagonal_cm'] if family == 'wing' and abs(_dot(normal, axis)) > 1e-8 else covers['end_cm']
                elif abs(_dot(normal, inward)) > abs(_dot(normal, axis)):
                    cover = covers['inside_cm'] if _dot(normal, inward) > 0 else covers['outside_cm']
                else:
                    cover = covers['end_cm']
                faces.append((normal, bound, cover))
            cells.append(tuple(faces))
    return tuple(cells)


def _curve_checks(bar, cells):
    """Include every face-normal extremum, not just sampled arc chords."""
    points = list(bar.points_m)
    for i, bulge in enumerate(bar.bulges[:-1]):
        if abs(bulge) < 1e-12:
            continue
        a, b = bar.detail.vertices_m[i:i+2]
        dx, dy = b[0]-a[0], b[1]-a[1]
        chord, sweep = math.hypot(dx, dy), 4*math.atan(bulge)
        off = chord/(2*math.tan(sweep/2))
        center = ((a[0]+b[0])/2-dy/chord*off, (a[1]+b[1])/2+dx/chord*off)
        radius, start = math.dist(a, center), math.atan2(a[1]-center[1], a[0]-center[0])
        for normal, *_ in (face for cell in cells for face in cell):
            angle = math.atan2(_dot(normal, bar.axis_v), _dot(normal, bar.axis_u))
            for candidate in (angle, angle+math.pi):
                travelled = ((candidate-start) if sweep > 0 else (start-candidate)) % (2*math.pi)
                if travelled <= abs(sweep)+1e-10:
                    local = (center[0]+radius*math.cos(candidate), center[1]+radius*math.sin(candidate))
                    points.append(tuple(o+local[0]*u+local[1]*v for o,u,v in zip(bar.start_m,bar.axis_u,bar.axis_v)))
    return points


def _check_concrete(bar, cells):
    radius = bar.diameter_mm/2000
    for point in _curve_checks(bar, cells):
        containing = [index for index, cell in enumerate(cells) if _inside(point, cell)]
        if not containing:
            raise ValueError('El suple sale del moldaje; revisa el desarrollo, el gancho y su rango.')
        allowed = False
        for index in containing:
            for normal, bound, cover in cells[index]:
                distance = bound-_dot(normal, point)
                if distance >= cover+radius-1e-8:
                    continue
                projection = tuple(value+distance*n for value,n in zip(point,normal))
                if not any(other != index and _inside(projection, cell) for other,cell in enumerate(cells)):
                    break
            else:
                allowed = True
                break
        if not allowed:
            raise ValueError('El suple invade un recubrimiento del ala, frontal o espaldar; no se acortó automáticamente.')


def _segment_distance(a, b, c, d):
    u, v, w = (tuple(x-y for x,y in zip(last,first)) for first,last in ((a,b),(c,d),(c,a)))
    aa, bb, cc, dd, ee = _dot(u,u), _dot(u,v), _dot(v,v), _dot(u,w), _dot(v,w)
    if aa < 1e-24:
        t = max(0.,min(1.,ee/cc)) if cc > 1e-24 else 0.
        return math.dist(a,tuple(c[i]+t*v[i] for i in range(3)))
    if cc < 1e-24:
        s = max(0.,min(1.,-dd/aa))
        return math.dist(c,tuple(a[i]+s*u[i] for i in range(3)))
    denominator = aa*cc-bb*bb
    s = max(0., min(1., (bb*ee-cc*dd)/denominator)) if denominator > 1e-24 else 0.
    t = (bb*s+ee)/cc
    if t < 0:
        t, s = 0., max(0., min(1., -dd/aa))
    elif t > 1:
        t, s = 1., max(0., min(1., (bb-dd)/aa))
    return math.hypot(*(w[i]+s*u[i]-t*v[i] for i in range(3)))


def _clashes(bar, others):
    for other in others:
        clearance = (bar.diameter_mm+other['diameter_mm'])/2000
        if abs(bar.points_m[0][2]-other['points'][0][2]) >= clearance-1e-9:
            continue
        # Chords are used only to reject proximity; a small arc-sag margin
        # prevents a near-tangent sampled curve from being accepted falsely.
        tolerance = max(bar.bend_radius_cm/100, other.get('bend_radius_cm', 0)/100)*(1-math.cos(math.radians(2.5)))
        if any(_segment_distance(a,b,c,d) < clearance+tolerance-1e-9
               for a,b in zip(bar.points_m,bar.points_m[1:])
               for c,d in zip(other['points'],other['points'][1:])):
            return True
    return False


def _reference_horizontals(profile, state, abutment, side, inner_result):
    interior = state['interior']
    if interior.get('removed_pieces'):
        reference = deepcopy(state)
        reference.update({key: deepcopy(interior[key]) for key in ('vertical','horizontal')})
        reference['removed_pieces'] = []
        result = build_wing_mesh(profile, reference, abutment, side, mesh='interior')
        if not result['valid']:
            raise ValueError('No se pudo recuperar el reparto de referencia de la malla interior.')
    else:
        result = inner_result
    return [bar for bar in result['bars'] if bar['key'] in
            (f'wing_{side}_inner_horizontal_main', f'wing_{side}_inner_horizontal_upper')]


def build_wing_supplements(profile, wing_state, abutment_state, side, inner_result):
    """Build only enabled green groups; no CAD access or implicit steel data.

    ``straight_cm`` is the developed path from the initial hook's main-leg
    tangency to the free tip. It includes an intervening wing/frontal bend,
    but excludes the hook and its 90-degree arc.
    """
    result = {'valid': True, 'issues': [], 'marks': [], 'details': [], 'bars': [],
              'removed_bars': [], 'total_kg': 0., 'representation': 'physical_pieces'}
    groups = wing_state.get('supplements', {})
    active = [name for name in ('front','back') if groups.get(name,{}).get('enabled') is True]
    if not active:
        return result
    try:
        if side not in ('left','right'):
            raise ValueError('Selecciona el lado del ala.')
        if not wing_state.get('interior',{}).get('enabled') or not inner_result.get('valid'):
            raise ValueError('Los suples requieren una malla interior activada y válida.')
        g = {key: value/100 for key,value in profile['geometry'].items()}
        covers = {key: value/100 for key,value in wing_state['cover'].items()}
        frame = profile['frame']; origin = frame['origin_m']
        axis, inward, front_axis, front_inward = (frame[key] for key in ('axis_u','inward','front_axis_u','front_inward'))
        dv = wing_state['interior']['vertical']['diameter_mm']/1000
        principal = [bar for bar in inner_result['bars'] if '_inner_horizontal_' in bar['key']]
        reference = _reference_horizontals(profile, wing_state, abutment_state, side, inner_result)
        levels = sorted({round(bar['points'][0][2], 10) for bar in reference})
        if len(levels) < 2:
            raise ValueError('Se necesitan dos horizontales de referencia para intercalar los suples.')
        midpoints = [(a+b)/2 for a,b in zip(levels,levels[1:])]
        cells = _material(profile, covers)
        bars, rules, configurations = [], [], {}
        join = origin[2]+g['front_height_cm']
        nominal_roof = origin[2]+g['top_join_cm']
        result['supplement_ranges_cm'] = {}
        result['length_labels'] = {}

        def front_point(u, depth, z=0.):
            return tuple(origin[i]+u*front_axis[i]+depth*front_inward[i]+(z if i == 2 else 0.) for i in range(3))

        for name in active:
            entry = groups[name]
            diameter = _positive(entry.get('diameter_mm'), f'diámetro del suple {name}')
            if diameter not in DIAMETROS_DISPONIBLES_MM:
                raise ValueError('El diámetro del suple no está disponible.')
            spacing = _positive(entry.get('spacing_cm'), f'separación del suple {name}')/100
            hook = _positive(entry.get('hook_cm'), f'gancho del suple {name}')
            developed = _positive(entry.get('straight_cm'), f'desarrollo del suple {name}')/100
            mark = entry.get('mark')
            if not isinstance(mark,str) or not re.fullmatch(r'[0-9]+[A-Za-z]*',mark):
                raise ValueError(f'Completa una marca propia para el suple {name}.')
            radius, half = 3*diameter/1000, diameter/2000
            depth = g['thickness_cm']-covers['inside_cm']-dv-half
            front_depth = _front_thickness(profile)-covers['inside_cm']-dv-half
            if min(depth,front_depth) < covers['outside_cm']+half:
                raise ValueError('El diámetro del suple no cabe entre recubrimientos en la malla interior.')
            upper = name == 'back'
            meshes = profile.get('back_wall_meshes' if upper else 'front_wall_meshes', ())
            if not meshes:
                raise ValueError('Falta el moldaje frontal/espaldar para colocar el gancho del suple.')
            a,b = meshes[0]['vertices'][2:4]
            normal = (b[1]-a[1], a[0]-b[0], 0.)
            normal = tuple(value/math.hypot(*normal) for value in normal)
            if _dot(normal,front_axis) > 0:
                normal = tuple(-value for value in normal)
            bound = _dot(normal,a)
            desired = g['back_thickness_cm'] if upper else g['front_depth_cm']
            original_face = profile['back_front_outer_m' if upper else 'front_face_outer_m']
            bound += _dot(normal, tuple(x-y for x,y in zip(front_point(-desired,0), original_face)))
            reach = hook/100+radius
            u = max((bound-covers['end_cm']-half-_dot(normal,front_point(0,d)))/_dot(normal,front_axis)
                    for d in (front_depth,front_depth+reach))
            corner = front_point(u,front_depth)
            hook_tip = front_point(u,front_depth+reach)
            cap = _roof_limit_segment(meshes,corner,hook_tip,covers['top_cm']+half)
            far = tuple(origin[i]+(g['main_length_cm']+g['extension_length_cm']+developed+1)*axis[i]+depth*inward[i] for i in range(3))
            path = tuple(reversed(horizontal_face_path(profile,far,corner)))
            if len(path) == 2:
                route = (corner, tuple(corner[i]+(radius+developed)*front_axis[i] for i in range(3)))
            else:
                knot = path[1]
                front_length = math.dist(corner,knot)
                turn = math.acos(max(-1.,min(1.,_dot(front_axis,axis))))
                tangent = radius*math.tan(turn/2)
                first_straight = front_length-radius-tangent
                if first_straight < 0:
                    raise ValueError('El tramo frontal del suple no permite sus dos dobleces.')
                if developed <= first_straight+1e-10:
                    route = (corner, tuple(corner[i]+(radius+developed)*front_axis[i] for i in range(3)))
                elif developed < first_straight+radius*turn-1e-10:
                    raise ValueError('El desarrollo del suple termina dentro del doblez de unión; edita su largo.')
                else:
                    tail = tangent+developed-first_straight-radius*turn
                    route = (corner,knot,tuple(knot[i]+tail*axis[i] for i in range(3)))
            lower = join if upper else join-_positive(entry.get('range_height_cm'),'altura del rango frontal')/100
            high = nominal_roof if upper else join
            if lower < origin[2]-1e-9 or high <= lower:
                raise ValueError('El rango del suple frontal debe quedar sobre la zapata y bajo la coronación frontal.')
            result['supplement_ranges_cm'][name] = {'start_cm': (lower-origin[2])*100, 'end_cm': (high-origin[2])*100}
            result['length_labels'][name] = ('Desarrollo desde el gancho hasta el extremo libre'
                                            if len(route)>2 else 'Tramo recto desde la tangencia del gancho')
            high = min(high,cap,levels[-1])
            starts = [value for value in midpoints if lower-1e-9 <= value <= high+1e-9]
            if not starts:
                raise ValueError(f'El rango {name} no contiene un espacio para intercalar un suple.')
            start = starts[0]
            count = math.floor((high-start+1e-9)/spacing)+1
            if count > 5000:
                raise ValueError('La separación genera demasiados suples.')
            stations = [start+index*spacing for index in range(count)]
            configurations[name] = (entry, diameter, spacing, hook, route, stations, high)

        # Close only the front group's final residual interval. The back group
        # already starts at the closest available reference midpoint above the
        # common nominal crown. Existing nominal stations are never moved.
        if set(active) == {'front','back'}:
            front, back = configurations['front'], configurations['back']
            if back[5][0]-front[5][-1] > .2+1e-9:
                candidates = [z for z in reversed(midpoints) if front[5][-1]+1e-9 < z <= front[6]+1e-9
                              and back[5][0]-z <= .2+1e-9 and z-front[5][-1] <= front[2]+1e-9]
                if not candidates:
                    raise ValueError('No cabe un cierre intercalado de hasta 20 cm entre los suples frontal y espaldar.')
                front[5].append(candidates[0])

        for name in active:
            entry, diameter, spacing, hook, route, stations, _ = configurations[name]
            group = 'inner_supplement_'+name
            label = 'Suple interior · '+('muro frontal' if name == 'front' else 'muro espaldar')
            key = f'wing_{side}_{group}'
            rules.append(SimpleNamespace(key=key,mark=entry['mark'],label=label,diameter_mm=diameter,
                                         spacing_cm=spacing*100,continuation_mark='',removed_pieces=entry.get('removed_pieces',[])))
            for index,z in enumerate(stations):
                if not levels[0] < z < levels[-1]:
                    raise ValueError('El suple no queda entre horizontales de la malla interior.')
                placed = tuple(tuple(value+(z-origin[2] if i==2 else 0) for i,value in enumerate(point)) for point in route)
                bar = make_single_hook_path(placed,front_inward,diameter,hook,
                    identity=f'wing:{side}:{group}:{index}', key=key,mark=entry['mark'],label=label,spacing_cm=spacing*100)
                _check_concrete(bar,cells)
                if _clashes(bar,principal) or _clashes(bar,[{'diameter_mm':b.diameter_mm,'bend_radius_cm':b.bend_radius_cm,'points':b.points_m} for b in bars]):
                    raise ValueError('Un suple choca con un horizontal o con otro suple; cambia la separación o el rango, sin mover la malla principal.')
                bars.append(bar)

        original = {bar.id:bar for bar in bars}
        removed = set()
        for name in active:
            expected = f'wing_{side}_inner_supplement_{name}'
            for record in groups[name].get('removed_pieces',[]):
                bar = original.get(record.get('id'))
                matched = bar is not None and bar.key == expected and bar.signature == record.get('signature')
                result['removed_bars'].append({**record,'status':'removed' if matched else 'unresolved',
                    **({'key':bar.key,'mark':bar.mark,'label':bar.label} if bar else {})})
                if not matched:
                    raise ValueError('Un suple eliminado cambió de geometría; revisa o restaura esa baja.')
                removed.add(bar.id)
        bars = [bar for bar in bars if bar.id not in removed]
        summary = summarize_wing_bars(bars,rules,side)
        if not summary['schedule'].is_valid:
            raise ValueError('; '.join(issue.message for issue in summary['schedule'].issues))
        schedule = summary['schedule']
        result['marks'] = [{**asdict(mark),'kg':mark.kg_steel,'area_cm2':mark.area_m2*10000,
                           'spacing_cm':next(rule.spacing_cm for rule in rules if rule.key==mark.key)} for mark in schedule.marks]
        result['details'] = [{**asdict(piece),**detail_dimension_metadata(piece),
                              'points_m':polyline_render_points(piece),'measured_cm':piece.developed_length_cm} for piece in summary['details']]
        result['total_kg'] = schedule.total_kg
        result['bars'] = [{'id':bar.id,'signature':bar.signature,'key':bar.key,'element_key':f'abutment.{side}_wing',
            'label':bar.label,'mark':bar.mark,'marks':[bar.mark],'diameter_mm':bar.diameter_mm,
            'level':'interior','piece_role':bar.piece_role,'placement_id':bar.id,'length_cm':bar.length_cm,
            'developed_length_cm':bar.developed_length_cm,'bend_radius_cm':bar.bend_radius_cm,'lap_cm':0.,'lap_segments':[],
            'representation':'physical_pieces','points':bar.points_m,'vertices':bar.vertices_m,'bulges':bar.bulges,
            'main_start':bar.main_start_m,'main_end':bar.main_end_m} for bar in bars]
    except (ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError) as error:
        result['valid'] = False
        result['issues'].append({'severity':'error','message':str(error)})
        result.update(bars=[],marks=[],details=[],total_kg=0.)
    return result
