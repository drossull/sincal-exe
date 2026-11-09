"""Vista local de moldaje de viga, sin consultar CAD ni modificar el JSON.

El perfil se extruye con la rotación atan(-pendiente_longitudinal) de
Proyecto Puentes y se recorta por los dos planos verticales esviados.
El origen local está en la base del eje de la viga en el corte inicial.
No se atribuyen a esta vista cotas globales de apoyos ni armaduras.
Las vistas frontal e isométrica usan un tramo interior corto, identificado
como tal; la escena completa conserva los planos esviados de los extremos.
"""
from __future__ import annotations

from collections.abc import Mapping
import math

from sincal.rebar.beam_profiles import half_section, resolve_profile, section


def _number(value, label, *, positive=False, nonnegative=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (positive and value <= 0)
            or (nonnegative and value < 0)):
        raise ValueError(f'Completa un valor válido de viga: {label}.')
    return float(value)


def _index(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'Selecciona un {label} válido.')
    return value


def _value(board, common, key):
    # Los tableros efectivos de Proyecto Puentes sobrescriben claves planas.
    return board[key] if key in board else common.get(key)


def _count(value):
    count = _number(value, 'cantidad de vigas', nonnegative=True)
    if count != int(count) or count > 1000:
        raise ValueError('La cantidad de vigas debe ser un entero entre 0 y 1000.')
    return int(count)


def _clean(points):
    result = []
    for point in points:
        if not result or math.dist(point, result[-1]) > 1e-12:
            result.append(list(point))
    if len(result) > 1 and math.dist(result[0], result[-1]) < 1e-12:
        result.pop()
    return result


def _views(profile, length, skew, slope):
    """Proyecciones ortográficas exactas del prisma recortado.

    No se usa una envolvente convexa de la elevación: conservar los entrantes
    del alma en los extremos evita inventar hormigón cuando hay esviaje.
    """
    parameters = profile['parameters_mm']
    half = half_section(parameters)
    factor, shear = math.hypot(1, slope), math.tan(math.radians(skew))
    width = max(x for x, _ in half)
    plan = [[shear*-width, -width], [length+shear*-width, -width],
            [length+shear*width, width], [shear*width, width]]
    projected = lambda u, z: [u, factor*z-slope*u]
    elevation = _clean([projected(-abs(shear)*x, z) for x, z in half]
                       + [projected(length+abs(shear)*x, z) for x, z in reversed(half)])
    # Líneas longitudinales bajo el ala superior: alma y ala inferior.
    inner_widths = sorted({parameters['b4']/2000, parameters['b7']/2000,
                           parameters['b1']/2000}-{width})
    plan_lines = [[[shear*x, x], [length+shear*x, x]]
                  for w in inner_widths for x in (-w, w)]
    # Aristas longitudinales del perfil, sin introducir divisiones transversales.
    elevation_lines = []
    seen = set()
    for x, z in half:
        if z == 0 or z == parameters['d7']/1000:
            continue
        for sign in (-1, 1):
            u = shear*x*sign
            edge = [projected(u, z), projected(length+u, z)]
            key = tuple(round(v, 12) for p in edge for v in p)
            if key not in seen:
                seen.add(key)
                elevation_lines.append(edge)
    return {'plan': {'outline': _clean(plan), 'lines': plan_lines},
            'elevation': {'outline': elevation, 'lines': elevation_lines}}


def _topology(vertices, count, **metadata):
    """Dos perfiles homólogos, unidos sin convexificar sus entrantes."""
    faces = [list(reversed(range(count))), list(range(count, 2*count))]
    faces.extend([[i, (i+1) % count, (i+1) % count+count, i+count]
                  for i in range(count)])
    edges = [[i+end, (i+1) % count+end] for end in (0, count)
             for i in range(count)]
    edges.extend([[i, i+count] for i in range(count)])
    return {'vertices': vertices, 'faces': faces, 'edges': edges,
            'units': 'm', 'axes': {'x': 'transversal', 'y': 'longitudinal', 'z': 'vertical'},
            **metadata}


def _scenes(profile, length, skew, slope):
    """Moldaje completo y recorte interior, con la misma rotación física.

    Las caras del tramo corto son cortes de visualización perpendiculares al
    eje de la viga, no extremos esviados ficticios. Si los extremos reales se
    solapan en toda estación, no existe un prisma interior de sección completa.
    """
    polygon = profile['section_m']
    count = len(polygon)
    factor, shear = math.hypot(1, slope), math.tan(math.radians(skew))
    full = _topology(
        [[x, end+x*shear, factor*z-slope*(end+x*shear)]
         for end in (0., length) for x, z in polygon], count,
        scope='full_beam', length_projected_m=length,
        origin_reference='Base del eje de la viga en el corte inicial; cotas locales.')
    alpha = math.atan(-slope)
    c, s = math.cos(alpha), math.sin(alpha)
    # For every profile point the longitudinal coordinate q must satisfy
    # x*tan(skew) <= q*c-z*s <= length+x*tan(skew).
    lower = max((x*shear+z*s)/c for x, z in polygon)
    upper = min((length+x*shear+z*s)/c for x, z in polygon)
    available = upper-lower
    if available <= 1e-10:
        return None, full
    sample_length = min(.75, available)
    start = (lower+upper-sample_length)/2
    sample = _topology(
        [[x, q*c-z*s, q*s+z*c]
         for q in (0., sample_length) for x, z in polygon], count,
        scope='interior_sample', specimen_length_m=sample_length,
        requested_specimen_length_m=.75, length_projected_m=sample_length*c,
        start_station_m=start,
        origin_reference='Base del eje al inicio del tramo interior; cotas locales del recorte.')
    return sample, full


def _scene_view(scene, view):
    """Proyección ortográfica; la segunda coordenada crece hacia arriba."""
    if scene is None:
        return {'outline': [], 'lines': []}
    def project(point):
        x, y, z = point
        if view == 'front':
            return [x, z]
        return [(x+y)/math.sqrt(2), z*math.sqrt(2/3)+(y-x)/math.sqrt(6)]
    vertices = [project(p) for p in scene['vertices']]
    return {'outline': [vertices[i] for i in scene['faces'][0]],
            'lines': [[vertices[i], vertices[j]] for i, j in scene['edges']],
            'vertices': vertices,
            'faces': [[vertices[i] for i in face] for face in scene['faces']],
            'scope': scene['scope'], 'projection': 'orthographic'}


def preview(project_data, board_index=0, beam_index=0):
    """Contrato JSON: errores de datos devuelven valid=False e issues en español."""
    result = {'units': 'm', 'boards': [], 'board_index': board_index,
              'beam_index': beam_index, 'profile': None, 'geometry': None,
              'scene': None, 'full_scene': None, 'definition': None,
              'views': {'plan': {'outline': [], 'lines': []},
                        'elevation': {'outline': [], 'lines': []},
                        'front': {'outline': [], 'lines': []},
                        'isometric': {'outline': [], 'lines': []}},
              'issues': [], 'valid': False}
    try:
        if not isinstance(project_data, Mapping):
            raise ValueError('Carga el JSON del proyecto para mostrar sus vigas.')
        common_elements = project_data.get('elementos_comunes')
        common_elements = common_elements if isinstance(common_elements, Mapping) else {}
        common = common_elements.get('vigas')
        common = common if isinstance(common, Mapping) else {}
        boards = project_data.get('tableros')
        if not isinstance(boards, list) or not boards:
            raise ValueError('El JSON no contiene tableros para identificar una viga.')
        for i, board in enumerate(boards):
            if not isinstance(board, Mapping):
                result['boards'].append({'index': i, 'label': f'Tablero {i+1}',
                                         'beam_count': 0, 'profile_name': 'Sin perfil válido'})
                continue
            try:
                count = _count(_value(board, common, 'num_vigas'))
            except ValueError:
                count = 0
            try:
                info = resolve_profile(_value(board, common, 'tipo_viga_seleccionado'),
                                       _value(board, common, 'perfiles_viga_personalizados'))
                profile_name = info['name']
            except ValueError:
                profile_name = 'Sin perfil válido'
            label = board.get('nombre_grupo_tablero')
            label = label if isinstance(label, str) and label.strip() else f'Tablero {i+1}'
            # usar_grupo_tablero sólo controla la agrupación en FreeCAD.
            result['boards'].append({'index': i, 'label': label, 'beam_count': count,
                                     'profile_name': profile_name})
        selected = _index(board_index, 'tablero')
        beam = _index(beam_index, 'número de viga')
        if selected >= len(boards) or not isinstance(boards[selected], Mapping):
            raise ValueError('El tablero seleccionado no existe en el JSON.')
        board = boards[selected]
        count = _count(_value(board, common, 'num_vigas'))
        if count == 0:
            raise ValueError('El tablero seleccionado no tiene vigas.')
        if beam >= count:
            raise ValueError('La viga seleccionada no existe en este tablero.')
        profile = resolve_profile(_value(board, common, 'tipo_viga_seleccionado'),
                                  _value(board, common, 'perfiles_viga_personalizados'))
        spacing = _number(_value(board, common, 'separacion_vigas'), 'separación entre vigas', positive=True)/1000
        offset = _number(_value(board, common, 'offset_y_vigas'), 'offset longitudinal', nonnegative=True)/1000
        slab = _number(board.get('largo_losa'), 'largo de losa', positive=True)/1000
        slope = _number(board.get('pendiente_longitudinal'), 'pendiente longitudinal')
        general = project_data.get('parametros_generales')
        general = general if isinstance(general, Mapping) else {}
        skew = _number(board.get('angulo_esviaje_puente', general.get('angulo_esviaje_puente')), 'esviaje')
        if abs(skew) >= 90:
            raise ValueError('El esviaje debe estar entre −90° y 90° sin incluir los extremos.')
        length = slab-2*offset
        if length <= 0:
            raise ValueError('Los offsets longitudinales consumen todo el largo de la viga.')
        profile['section_m'] = section(profile['parameters_mm'])
        views = _views(profile, length, skew, slope)
        scene, full_scene = _scenes(profile, length, skew, slope)
        views.update({key: _scene_view(scene, key) for key in ('front', 'isometric')})
        all_points = [p for v in views.values() for p in v['outline']]
        all_points.extend(full_scene['vertices'])
        if scene:
            all_points.extend(scene['vertices'])
        if not all(math.isfinite(v) for p in all_points for v in p):
            raise ValueError('Los parámetros de la viga exceden el rango geométrico válido.')
        from sincal.web.beam_definition import build_definition
        definition = build_definition(profile, scene, slope)
        result.update(profile=profile, geometry={
            'length_projected_m': length, 'slab_length_m': slab,
            'skew_degrees': skew, 'slope': slope, 'beam_count': count,
            'beam_spacing_m': spacing, 'beam_center_offset_m': (beam-(count-1)/2)*spacing,
            'offset_m': offset, 'height_m': profile['parameters_mm']['d7']/1000,
            'width_upper_m': profile['parameters_mm']['b1']/1000,
            'width_lower_m': profile['parameters_mm']['b7']/1000,
            'web_thickness_m': profile['parameters_mm']['b4']/1000,
            'origin_reference': 'Base del eje de la viga en el corte inicial; cotas locales.',
            'offset_source': 'JSON',
        }, views=views, scene=scene, full_scene=full_scene, definition=definition, valid=True)
        if scene is None:
            result['issues'].append(
                'Los extremos esviados no dejan un tramo interior de sección completa; '
                'se conserva la vista de la viga completa.')
        if not math.isclose(offset, .05, abs_tol=1e-12):
            result['issues'].append(
                'Esta vista usa el offset del JSON. El modelador original de Proyecto Puentes '
                'fija 50 mm por extremo; su moldaje CAD puede tener otro largo.')
    except (ValueError, OverflowError) as error:
        result['issues'].append(str(error))
    return result
