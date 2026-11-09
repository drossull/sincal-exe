"""Wing mesh from an explicit, reviewed mouldage profile.

No CAD lookup and no steel defaults. Coordinates are in the same world frame
as the mouldage; displayed views never multiply the physical quantities.
"""
from __future__ import annotations

from dataclasses import asdict
import math
import re
from types import SimpleNamespace

from .detail import detail_dimension_metadata, polyline_render_points
from .model import DIAMETROS_DISPONIBLES_MM, distribution_positions_cm
from .wing_exterior import make_bracket
from .wing_schedule import summarize_wing_bars
from .wing_route import horizontal_face_path


GROUPS = {
    'vertical_main': 'Malla exterior · verticales anclados en zapata',
    'vertical_extension': 'Malla exterior · verticales cortos de aleta',
    'horizontal_main': 'Malla exterior · horizontales hasta frontal',
    'horizontal_upper': 'Malla exterior · horizontales hasta espaldar',
}


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _front_thickness(profile):
    """Current inner-face offset in the straight frontal frame, in metres."""
    frame = profile['frame']
    axis, inward = frame['axis_u'], frame['inward']
    shear = _dot(profile['side_offset_m'], axis)
    thickness = profile['geometry']['thickness_cm']/100
    inner_offset = tuple(shear*u+thickness*n for u, n in zip(axis, inward))
    return _dot(inner_offset, frame.get('front_inward', inward))


def opposed_mesh_issues(profile, exterior_state, interior_state):
    """Reject overlapping straight layers, without imposing hook staggering.

    Call only for the two active meshes. Incomplete engineering values are
    handled by each mesh's ordinary validation; they do not become defaults.
    """
    values = (exterior_state.get('cover', {}).get('outside_cm'),
              interior_state.get('cover', {}).get('inside_cm'),
              *(state.get(family, {}).get('diameter_mm')
                for state in (exterior_state, interior_state) for family in ('vertical', 'horizontal')))
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) or value < 0 for value in values):
        return []
    required = (values[0]+values[1])/100+sum(values[2:])/1000
    widths = (('ala', profile['geometry']['thickness_cm']/100),
              ('encuentro frontal/espaldar', _front_thickness(profile)))
    return [{'severity': 'error', 'message':
             f'Las capas rectas de ambas mallas se superponen en el {name}: requieren '
             f'{required*100:g} cm entre recubrimientos y diámetros; hay {width*100:g} cm.'}
            for name, width in widths if width < required-1e-9]


def _positions(start, end, spacing, diameter):
    if end < start:
        raise ValueError('No queda espacio útil para distribuir los fierros del ala.')
    if (end-start)/spacing > 5000:
        raise ValueError('La separación genera demasiados fierros en el ala.')
    return [start+p/100 for p in distribution_positions_cm(
        (end-start)*100, spacing*100, include_endpoints=True, minimum_spacing_cm=diameter*100)]


def _material_cell(mesh, origin, axis, inward):
    """Actual concrete half-spaces in orthonormal (u, depth, z) metres.

    Covers are offsets normal to each face, including the skewed end faces
    and the transverse road slope. A nonplanar nominal face needs review;
    choosing an arbitrary diagonal here would invent concrete geometry.
    """
    points = []
    for point in mesh['vertices']:
        delta = tuple(a-b for a, b in zip(point, origin))
        points.append((_dot(delta, axis), _dot(delta, inward), delta[2]))
    center = tuple(sum(p[i] for p in points)/len(points) for i in range(3))
    faces = {'outside': (0, 1, 2, 3), 'inside': (4, 5, 6, 7),
             'lower': (0, 1, 5, 4), 'end': (1, 2, 6, 5),
             'top': (3, 2, 6, 7), 'join': (0, 3, 7, 4)}
    result = {}
    for name, indices in faces.items():
        first, second, third, fourth = (points[i] for i in indices)
        a = tuple(x-y for x, y in zip(second, first))
        b = tuple(x-y for x, y in zip(third, first))
        normal = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
        size = math.hypot(*normal)
        if size < 1e-12:
            raise ValueError('El moldaje del ala tiene una cara sin área; revisa sus cotas.')
        normal = tuple(value/size for value in normal)
        bound = _dot(normal, first)
        if abs(_dot(normal, fourth)-bound) > 1e-8:
            raise ValueError('Una cara del moldaje del ala no es plana; revisa sus cotas y pendientes antes de calcular.')
        if _dot(normal, center) > bound:
            normal, bound = tuple(-v for v in normal), -bound
        result[name] = normal, bound
    return result


def _footing_material(abutment_state):
    """Footing planes in the same scene frame, without querying CAD."""
    data = (abutment_state or {}).get('geometry', {})
    values = [data.get(key) for key in ('ancho_cm', 'largo_cm', 'esviaje_grados')]
    cover = (abutment_state or {}).get('cover', {}).get('lateral_cm')
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) for value in (*values, cover)):
        raise ValueError('Completa las dimensiones y el recubrimiento lateral de la zapata para comprobar los anclajes del ala.')
    width, length, skew = values
    cosine, sine = math.cos(math.radians(skew)), math.sin(math.radians(skew))
    if min(width, length) <= 0 or cosine <= 1e-6 or cover < 0:
        raise ValueError('La geometría de la zapata no permite comprobar los anclajes del ala.')
    # |x| <= W cos(theta)/2; |y-x tan(theta)| <= L/(2 cos(theta)).
    planes = (((1., 0., 0.), width/200*cosine), ((-1., 0., 0.), width/200*cosine),
              ((-sine, cosine, 0.), length/200), ((sine, -cosine, 0.), length/200))
    return planes, cover/100


def _roof_limit_segment(meshes, first, last, clearance):
    """Lowest cover-offset roof along a segment across piecewise road slopes."""
    intervals = []
    limits = []
    delta = tuple(b-a for a, b in zip(first, last))
    for mesh in meshes:
        vertices = mesh['vertices']
        n = len(vertices)//2
        footprint = vertices[:n]
        center = tuple(sum(p[i] for p in footprint)/n for i in range(2))
        low, high = 0., 1.
        for a, b in zip(footprint, (*footprint[1:], footprint[0])):
            normal = (b[1]-a[1], a[0]-b[0])
            bound = _dot(normal, a)
            if _dot(normal, center) > bound:
                normal, bound = tuple(-v for v in normal), -bound
            available = bound-_dot(normal, first)
            coefficient = _dot(normal, delta)
            if abs(coefficient) < 1e-12:
                if available < -1e-9:
                    low, high = 1., 0.; break
            elif coefficient > 0:
                high = min(high, available/coefficient)
            else:
                low = max(low, available/coefficient)
        if high < low-1e-9:
            continue
        a, b, c = vertices[n:n+3]
        ab, ac = tuple(y-x for x,y in zip(a,b)), tuple(y-x for x,y in zip(a,c))
        normal = (ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0])
        size = math.hypot(*normal)
        if abs(normal[2]) < 1e-12:
            raise ValueError('La coronación del frontal o espaldar no define un techo utilizable.')
        normal = tuple(value/size*(1 if normal[2] > 0 else -1) for value in normal)
        bound = _dot(normal, a)
        intervals.append((max(0., low), min(1., high)))
        for t in (max(0., low), min(1., high)):
            x, y = (first[i]+t*delta[i] for i in range(2))
            limits.append((bound-clearance-normal[0]*x-normal[1]*y)/normal[2])
    covered = 0.
    for low, high in sorted(intervals):
        if low > covered+1e-8:
            break
        covered = max(covered, high)
    if covered < 1.-1e-8 or not limits:
        raise ValueError('El gancho o recorrido horizontal sale del moldaje frontal/espaldar; revisa sus cotas y giro.')
    return min(limits)


def build_wing_mesh(profile, state, abutment_state, side, *, mesh='exterior'):
    result = {'valid': False, 'issues': [], 'marks': [], 'details': [], 'bars': [],
              'removed_bars': [], 'total_kg': 0., 'representation': 'physical_pieces'}
    issues = result['issues']
    def problem(message):
        issues.append({'severity': 'error', 'message': message})
    if mesh not in ('exterior', 'interior'):
        problem('Selecciona la malla exterior o interior del ala.'); return result
    interior = mesh == 'interior'
    prefix = 'inner_' if interior else ''
    hook_sign = -1 if interior else 1
    for message in profile.get('issues', ()):
        issues.append({'severity': 'warning', 'message': str(message)})
    if side not in ('left', 'right'):
        problem('Selecciona el lado del ala.'); return result
    for group in ('cover', 'vertical', 'horizontal'):
        for field, value in state[group].items():
            if field.startswith('mark_'):
                continue
            if value is None:
                problem(f'Completa {group}.{field} de la malla {mesh}.')
            elif (isinstance(value, bool) or not isinstance(value, (int, float))
                  or not math.isfinite(value) or value < 0 or (group != 'cover' and value == 0)):
                problem(f'Revisa {group}.{field}: la medida no es válida.')
    if state['outer_family'] not in ('vertical', 'horizontal'):
        problem('Selecciona qué familia queda más cerca de la cara exterior.')
    if interior and state['outer_family'] != 'vertical':
        problem('En la malla interior los verticales deben quedar junto al hormigón y los horizontales hacia el centro del espesor.')
    if state['horizontal_start'] not in ('wall', 'footing'):
        problem('Selecciona desde dónde se distribuyen los horizontales.')
    for name in ('vertical', 'horizontal'):
        if state[name]['diameter_mm'] is not None and state[name]['diameter_mm'] not in DIAMETROS_DISPONIBLES_MM:
            problem(f'El diámetro de los {name} no está disponible.')
    if any(i['severity'] == 'error' for i in issues):
        return result
    g = {key: value/100 for key, value in profile['geometry'].items()}
    frame = profile['frame']; origin = frame['origin_m']; axis = frame['axis_u']; inward = frame['inward']
    front_axis = frame.get('front_axis_u', axis); front_inward = frame.get('front_inward', inward)
    joint, extension = g['main_length_cm'], g['extension_length_cm']
    tip = joint+extension; thickness = g['thickness_cm']
    covers = {key: value/100 for key, value in state['cover'].items()}
    vertical, horizontal = state['vertical'], state['horizontal']
    dv, dh = vertical['diameter_mm']/1000, horizontal['diameter_mm']/1000
    depths = ({'vertical': covers['outside_cm']+dv/2, 'horizontal': covers['outside_cm']+dv+dh/2}
              if state['outer_family'] == 'vertical' else
              {'horizontal': covers['outside_cm']+dh/2, 'vertical': covers['outside_cm']+dh+dv/2})
    if interior:
        depths = {'vertical': thickness-covers['inside_cm']-dv/2,
                  'horizontal': thickness-covers['inside_cm']-dv-dh/2}
    front_depth = depths['horizontal']
    if interior:
        # The interior face has its own transverse offset at the straight
        # front wall. A rotated wing's normal thickness is not its ΔX there.
        front_thickness = _front_thickness(profile)
        front_depth = front_thickness-covers['inside_cm']-dv-dh/2
    wing_hook_direction = tuple(hook_sign*value for value in inward)
    footing_height = origin[2]
    footing_cover = (abutment_state or {}).get('cover', {}).get('inferior_cm')
    if (isinstance(footing_cover, bool) or not isinstance(footing_cover, (int, float))
            or not math.isfinite(footing_cover) or footing_cover < 0):
        problem('Completa el recubrimiento inferior de la zapata para anclar los verticales del ala.')
        return result
    footing_cover /= 100
    if footing_height <= footing_cover:
        problem('El espesor de zapata no permite el anclaje inferior.'); return result
    for family, diameter, hooks in (
        ('vertical', dv, [vertical['hook_top_cm']/100]),
        ('horizontal', dh, [horizontal['hook_ala_cm']/100]),
    ):
        face_depth = thickness-depths[family] if interior else depths[family]
        opposite_cover = covers['outside_cm' if interior else 'inside_cm']
        required = face_depth+max(hooks)+3*diameter+diameter/2+opposite_cover
        if required > thickness+1e-9:
            problem(f'El gancho de {family} no cabe en el espesor del ala: necesita '
                    f'{required*100:.1f} cm contando radios, diámetros y recubrimientos; hay {thickness*100:g} cm.')
    # The free end in the front/back wall has the full transverse wall width.
    available_front = profile.get('front_available_width_cm')
    if available_front is not None and (
            front_depth+horizontal['hook_join_cm']/100+3*dh+dh/2+covers['inside_cm'] > available_front/100):
        problem('El gancho del extremo frontal/espaldar invade la cara opuesta.')
    if any(i['severity'] == 'error' for i in issues):
        return result

    def world(u, z, depth=0.):
        # A sheared rear face can contain wing stations with u < 0. Their
        # frame remains the wing frame; only explicit front points use the
        # separate front-wall axes.
        return tuple(origin[i]+u*axis[i]+depth*inward[i]+(z if i == 2 else 0.) for i in range(3))

    try:
        cells = [_material_cell(mesh, origin, axis, inward) for mesh in profile['meshes']]
        footing_planes, footing_side_cover = _footing_material(abutment_state)
        for x, y in profile['main_footprint_m']:
            if any(_dot(normal, (x, y, 0.))-bound > 1e-8 for normal, bound in footing_planes):
                raise ValueError('El ala principal sale de la huella de la zapata; revisa su giro y largo antes de anclar sus fierros.')
    except (ValueError, TypeError, KeyError) as error:
        problem(str(error)); return result

    def face_height(cell, face, u, depth, clearance):
        normal, bound = cell[face]
        if abs(normal[2]) < 1e-9:
            raise ValueError('La coronación o diagonal del ala no define una altura utilizable.')
        return (bound-clearance-normal[0]*u-normal[1]*depth)/normal[2]

    def top_clear(u, radius, depth=None, reach=None, cell=None):
        depth = depths['horizontal'] if depth is None else depth
        reach = hook_sign*(horizontal['hook_ala_cm']/100+3*dh) if reach is None else reach
        cell = cells[1 if extension and u > joint else 0] if cell is None else cell
        return min(face_height(cell, 'top', u, d, covers['top_cm']+radius)
                   for d in (depth, depth+reach))

    def bottom_clear(u, radius, depth=None, reach=None):
        depth = depths['horizontal'] if depth is None else depth
        reach = hook_sign*(horizontal['hook_ala_cm']/100+3*dh) if reach is None else reach
        return max(face_height(cells[-1], 'lower', u, d, covers['diagonal_cm']+radius)
                   for d in (depth, depth+reach))

    def u_limits(cell, radius, depth, reach):
        """Keep the entire hook inside the real skewed start/end faces."""
        low, high = -math.inf, math.inf
        for face in ('join', 'end'):
            normal, bound = cell[face]
            for d in (depth, depth+reach):
                value = (bound-covers['end_cm']-radius-normal[1]*d)/normal[0]
                if normal[0] < 0:
                    low = max(low, value)
                else:
                    high = min(high, value)
        return low, high

    def footing_u_limits(radius, depth, reach):
        low, high = -math.inf, math.inf
        for normal, bound in footing_planes:
            coefficient = _dot(normal, axis)
            for d in (depth, depth+reach):
                available = bound-footing_side_cover-radius-_dot(normal, world(0., 0., d))
                if abs(coefficient) < 1e-10:
                    if available < -1e-9:
                        raise ValueError('El anclaje del ala invade el recubrimiento lateral de la zapata.')
                elif coefficient > 0:
                    high = min(high, available/coefficient)
                else:
                    low = max(low, available/coefficient)
        return low, high

    def check_vertical(group, u, lower, upper):
        # The fillets lie inside this raw bracket. Checking its straight
        # corners against convex face offsets therefore includes each arc.
        depth, radius = depths['vertical'], dv/2
        lower_sign = hook_sign if group == 'vertical_extension' else 1
        raw = ((u, depth+lower_sign*(vertical['hook_bottom_cm']/100+3*dv), lower),
               (u, depth, lower), (u, depth, upper),
               (u, depth+hook_sign*(vertical['hook_top_cm']/100+3*dv), upper))
        cell = cells[1 if group == 'vertical_extension' else 0]
        for point in raw:
            if group == 'vertical_main' and point[2] < 0:
                global_point = world(point[0], point[2], point[1])
                if (global_point[2] < footing_cover+radius-1e-9
                        or any(_dot(n, global_point) > bound-footing_side_cover-radius+1e-9
                               for n, bound in footing_planes)):
                    raise ValueError('Un gancho del ala invade los recubrimientos de la zapata.')
                continue
            for face, (normal, bound) in cell.items():
                if face == 'lower' and group == 'vertical_main':
                    continue
                cover_key = {'join': 'end_cm', 'end': 'end_cm', 'lower': 'diagonal_cm'}.get(face, face+'_cm')
                if _dot(normal, point) > bound-covers[cover_key]-radius+1e-9:
                    raise ValueError('Un gancho vertical invade el recubrimiento del moldaje; revisa sus largos y las cotas del ala.')

    def front_point(u, depth):
        return tuple(origin[i]+u*front_axis[i]+depth*front_inward[i] for i in range(3))

    def front_endpoint(upper):
        """Offset the actual skewed free face, including the complete hook."""
        meshes = profile.get('back_wall_meshes' if upper else 'front_wall_meshes', ())
        if not meshes:
            raise ValueError('Falta el moldaje frontal/espaldar para comprobar el gancho horizontal.')
        vertices = meshes[0]['vertices']
        a, b = vertices[2:4]
        normal = (b[1]-a[1], a[0]-b[0], 0.)
        size = math.hypot(*normal)
        normal = tuple(value/size for value in normal)
        if _dot(normal, front_axis) > 0:
            normal = tuple(-value for value in normal)
        bound = _dot(normal, a)
        desired_depth = g['back_thickness_cm'] if upper else g['front_depth_cm']
        original_face = profile['back_front_outer_m' if upper else 'front_face_outer_m']
        # Respect a locally edited depth; the actual global mouldage remains
        # authoritative for containment, so incompatible edits are rejected.
        bound += _dot(normal, tuple(front_point(-desired_depth, 0.)[i]-original_face[i] for i in range(3)))
        reach = horizontal['hook_join_cm']/100+3*dh
        corner = max((bound-covers['end_cm']-dh/2-_dot(normal, front_point(0., d)))/_dot(normal, front_axis)
                     for d in (front_depth, front_depth+reach))
        first = front_point(corner, front_depth)
        last = front_point(corner, front_depth+reach)
        cap = _roof_limit_segment(meshes, first, last, covers['top_cm']+dh/2)-origin[2]
        if upper:
            # The short back-wall part also follows the longitudinal slope.
            normal, bound = cells[0]['join']
            world_normal = tuple(normal[0]*axis[i]+normal[1]*inward[i] for i in range(3))
            join_u = (bound-_dot(world_normal, front_inward)*front_depth)/_dot(world_normal, front_axis)
            cap = min(cap, _roof_limit_segment(meshes, first, front_point(join_u, front_depth),
                                               covers['top_cm']+dh/2)-origin[2])
        return corner, cap

    rules = []
    for group, label in GROUPS.items():
        label = label.replace('exterior', mesh)
        source = vertical if group.startswith('vertical') else horizontal
        mark_key = 'mark_extension' if group == 'vertical_extension' else 'mark_upper' if group == 'horizontal_upper' else 'mark_main'
        rules.append(SimpleNamespace(key=f'wing_{side}_{prefix}{group}', mark=source[mark_key].strip(),
                                     label=label, diameter_mm=source['diameter_mm'], spacing_cm=source['spacing_cm'],
                                     continuation_mark='', terminal_mark='', removed_pieces=state['removed_pieces']))
    by_group = dict(zip(GROUPS, rules)); bars = []; counts = dict.fromkeys(GROUPS, 0)
    def add(group, start, end, first_hook, last_hook, hook_direction, points=None, last_direction=None):
        rule = by_group[group]
        if not re.fullmatch(r'[0-9]+[A-Za-z]*', rule.mark):
            raise ValueError(f'Completa una marca válida para {rule.label}.')
        number = counts[group]; counts[group] += 1
        args = dict(identity=f'wing:{side}:{prefix}{group}:{number}', key=rule.key, mark=rule.mark,
                    label=rule.label, spacing_cm=rule.spacing_cm)
        last_direction = hook_direction if last_direction is None else last_direction
        if points is None and math.dist(hook_direction, last_direction) <= 1e-12:
            bar = make_bracket(start, end, hook_direction, rule.diameter_mm, first_hook, last_hook, **args)
        else:
            from .wing_exterior import make_bracket_path
            bar = make_bracket_path(points if points is not None else (start, end), hook_direction, last_direction, rule.diameter_mm,
                                    first_hook, last_hook, **args)
        bars.append(bar)

    try:
        top_reach = hook_sign*(vertical['hook_top_cm']/100+3*dv)
        bottom_reach = vertical['hook_bottom_cm']/100+3*dv
        first, last = u_limits(cells[0], dv/2, depths['vertical'], top_reach)
        foundation_first, foundation_last = footing_u_limits(dv/2, depths['vertical'], bottom_reach)
        first, last = max(first, foundation_first), min(last, foundation_last)
        for u in _positions(first, last, vertical['spacing_cm']/100, dv):
            lower = -footing_height+footing_cover+dv/2
            upper = top_clear(u, dv/2, depths['vertical'], top_reach, cells[0])
            check_vertical('vertical_main', u, lower, upper)
            add('vertical_main', world(u, lower, depths['vertical']),
                world(u, upper, depths['vertical']),
                vertical['hook_bottom_cm'], vertical['hook_top_cm'], inward,
                last_direction=wing_hook_direction)
        if extension > 0:
            extension_bottom_reach = hook_sign*bottom_reach
            first, last = u_limits(cells[1], dv/2, depths['vertical'], hook_sign*max(abs(top_reach), bottom_reach))
            for u in _positions(first, last, vertical['spacing_cm']/100, dv):
                # Both hooks belong to the wing thickness in the cantilever.
                face_depth = thickness-depths['vertical'] if interior else depths['vertical']
                opposite_cover = covers['outside_cm' if interior else 'inside_cm']
                if face_depth+bottom_reach+dv/2+opposite_cover > thickness+1e-9:
                    raise ValueError('El gancho inferior de la aleta no cabe dentro de su espesor.')
                lower = bottom_clear(u, dv/2, depths['vertical'], extension_bottom_reach)
                upper = top_clear(u, dv/2, depths['vertical'], top_reach, cells[1])
                check_vertical('vertical_extension', u, lower, upper)
                add('vertical_extension', world(u, lower, depths['vertical']),
                    world(u, upper, depths['vertical']),
                    vertical['hook_bottom_cm'], vertical['hook_top_cm'], wing_hook_direction)
        low = (covers['end_cm']+dh/2 if state['horizontal_start'] == 'wall'
               else -footing_height+footing_cover+dh/2)
        frontal_u, frontal_cap = front_endpoint(False)
        back_u, back_cap = front_endpoint(True)
        horizontal_reach = hook_sign*(horizontal['hook_ala_cm']/100+3*dh)
        high = min(back_cap, *(top_clear(u, dh/2, depths['horizontal'], horizontal_reach, cell)
                              for cell in cells for u in u_limits(cell, dh/2, depths['horizontal'], horizontal_reach)))
        for z in _positions(low, high, horizontal['spacing_cm']/100, dh):
            _, end_u = u_limits(cells[-1], dh/2, depths['horizontal'], horizontal_reach)
            if extension > 0 and z < bottom_clear(end_u, dh/2):
                normal, bound = cells[1]['lower']
                if normal[0] > 1e-12:
                    end_u = min((bound-covers['diagonal_cm']-dh/2-normal[1]*d-normal[2]*z)/normal[0]
                                for d in (depths['horizontal'], depths['horizontal']+horizontal_reach))
                else:
                    end_u = -math.inf
                ext_first, _ = u_limits(cells[1], dh/2, depths['horizontal'], horizontal_reach)
                if end_u < ext_first:
                    _, end_u = u_limits(cells[0], dh/2, depths['horizontal'], horizontal_reach)
            if z < 0:
                _, foundation_end = footing_u_limits(dh/2, depths['horizontal'], horizontal_reach)
                end_u = min(end_u, foundation_end)
            upper = z > min(frontal_cap, g['front_height_cm']-covers['top_cm']-dh/2)
            start_u = back_u if upper else frontal_u
            if start_u >= 0 or end_u <= start_u:
                raise ValueError('El recubrimiento no deja lugar para el horizontal hasta frontal/espaldar.')
            start = world(end_u, z, depths['horizontal'])
            end = tuple(value+(z if i == 2 else 0.) for i, value in enumerate(front_point(start_u, front_depth)))
            turned = abs(_dot(axis, front_axis)-1.) > 1e-9
            route = horizontal_face_path(profile, start, end) if turned else None
            add('horizontal_upper' if upper else 'horizontal_main', start, end,
                horizontal['hook_ala_cm'], horizontal['hook_join_cm'], wing_hook_direction,
                points=route, last_direction=front_inward)
    except (ValueError, TypeError, ZeroDivisionError) as error:
        problem(str(error)); return result

    original = {bar.id: bar for bar in bars}
    removed_ids = set()
    for removal in state['removed_pieces']:
        bar = original.get(removal['id'])
        matched = bar is not None and bar.signature == removal['signature']
        result['removed_bars'].append({**removal, 'status': 'removed' if matched else 'unresolved',
                                      **({'key': bar.key, 'mark': bar.mark, 'label': bar.label} if bar else {})})
        if matched:
            removed_ids.add(bar.id)
        else:
            problem('Un fierro eliminado del ala cambió de geometría. Restaura o revisa esa baja antes de insertar.')
    bars = [bar for bar in bars if bar.id not in removed_ids]
    active_rules = [rule for group, rule in by_group.items() if counts[group]]
    summary = summarize_wing_bars(bars, active_rules, side)
    schedule = summary['schedule']; issues.extend(asdict(issue) for issue in schedule.issues)
    result['valid'] = not any(issue['severity'] == 'error' for issue in issues)
    if not result['valid']:
        return result
    result['marks'] = [{**asdict(mark), 'kg': mark.kg_steel, 'area_cm2': mark.area_m2*10000,
                        'spacing_cm': next(rule.spacing_cm for rule in active_rules if rule.key == mark.key)}
                       for mark in schedule.marks]
    result['details'] = [{**asdict(piece), **detail_dimension_metadata(piece),
                          'points_m': polyline_render_points(piece), 'measured_cm': piece.developed_length_cm}
                         for piece in summary['details']]
    result['total_kg'] = schedule.total_kg
    result['bars'] = [{
        'id': bar.id, 'signature': bar.signature, 'key': bar.key,
        'element_key': f'abutment.{side}_wing', 'label': bar.label,
        'mark': bar.mark, 'marks': [bar.mark], 'diameter_mm': bar.diameter_mm,
        'level': mesh, 'piece_role': bar.piece_role, 'placement_id': bar.id,
        'length_cm': bar.length_cm, 'developed_length_cm': bar.developed_length_cm,
        'bend_radius_cm': bar.bend_radius_cm, 'lap_cm': 0., 'lap_segments': [],
        'representation': 'physical_pieces', 'points': bar.points_m,
        'vertices': bar.vertices_m, 'bulges': bar.bulges,
        'main_start': bar.main_start_m, 'main_end': bar.main_end_m,
    } for bar in bars]
    return result
