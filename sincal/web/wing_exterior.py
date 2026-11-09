"""Editable wing meshes; the imported project remains immutable."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
import re


GEOMETRY_FIELDS = (
    'thickness_cm', 'main_length_cm', 'extension_length_cm', 'top_join_cm',
    'top_edge_cm', 'top_tip_cm', 'tip_height_cm', 'front_height_cm',
    'front_depth_cm', 'back_thickness_cm',
)
COVER_FIELDS = ('outside_cm', 'inside_cm', 'top_cm', 'end_cm', 'diagonal_cm')
VERTICAL_FIELDS = ('diameter_mm', 'spacing_cm', 'hook_bottom_cm', 'hook_top_cm',
                   'mark_main', 'mark_extension')
HORIZONTAL_FIELDS = ('diameter_mm', 'spacing_cm', 'hook_ala_cm', 'hook_join_cm',
                     'mark_main', 'mark_upper')
RANGE_FIELDS = ('start_cm', 'end_cm', 'diameter_mm', 'spacing_cm')
SUPPLEMENT_FIELDS = ('diameter_mm', 'spacing_cm', 'hook_cm', 'straight_cm', 'mark')
EDGE_FIELDS = ('quantity', 'diameter_mm', 'top_hook_cm', 'total_cm', 'min_extension_cm', 'mark')
_MARK = re.compile(r'[0-9]+[A-Za-z]*', re.ASCII)


def _steel_defaults():
    return {
        'vertical': {'diameter_mm': None, 'spacing_cm': None, 'hook_bottom_cm': 40.,
                     'hook_top_cm': 40., 'mark_main': '', 'mark_extension': ''},
        'horizontal': {'diameter_mm': None, 'spacing_cm': None, 'hook_ala_cm': 40.,
                       'hook_join_cm': 40., 'mark_main': '', 'mark_upper': ''},
        'removed_pieces': [],
    }


def defaults():
    return {
        'geometry': dict.fromkeys(GEOMETRY_FIELDS), 'geometry_confirmed': False,
        'cover': dict.fromkeys(COVER_FIELDS),
        **_steel_defaults(),
        'outer_family': 'vertical', 'horizontal_start': 'wall',
        'interior': {'enabled': False, 'parameters_initialized': False, **_steel_defaults()},
        'supplements': {name: {'enabled': False, **dict.fromkeys(SUPPLEMENT_FIELDS), 'hook_cm': 40., 'mark': '',
                              'removed_pieces': [], **({'range_height_cm': None} if name == 'front' else {})}
                        for name in ('front', 'back')},
        'edge_rebar': {'quantity': None, 'diameter_mm': None, 'top_hook_enabled': True,
                       'top_hook_cm': 20., 'total_cm': None, 'min_extension_cm': 100.,
                       'mark': '', 'removed_pieces': []},
    }


def normalize_draft(state, *, add_controls=False):
    normalized = deepcopy(state)
    if not isinstance(normalized, Mapping):
        return normalized
    supplements = normalized.get('supplements')
    if isinstance(supplements, Mapping) and set(supplements) == {'axilla', 'upper'}:
        _validate_legacy_ranges(supplements)
        if 'supplements_legacy' in normalized and normalized['supplements_legacy'] != supplements:
            raise ValueError('Hay dos versiones distintas de los rangos antiguos; revisa el borrador.')
        normalized['supplements_legacy'] = deepcopy(supplements)
        normalized['supplements'] = defaults()['supplements']
        for old, new in (('axilla', 'front'), ('upper', 'back')):
            for key in ('enabled', 'diameter_mm', 'spacing_cm'):
                normalized['supplements'][new][key] = supplements[old][key]
    if add_controls:
        for key in ('supplements', 'edge_rebar'):
            normalized.setdefault(key, defaults()[key])
    return normalized


def _validate_legacy_ranges(supplements):
    if not isinstance(supplements, Mapping) or set(supplements) != {'axilla', 'upper'}:
        raise ValueError('Los rangos anteriores del ala no tienen el formato esperado.')
    for name, values in supplements.items():
        if (not isinstance(values, Mapping) or set(values) != {'enabled', *RANGE_FIELDS}
                or not isinstance(values['enabled'], bool)):
            raise ValueError('Los datos de los rangos anteriores no son válidos.')
        _validate_groups({name: {key: values[key] for key in RANGE_FIELDS}}, ((name, RANGE_FIELDS),))


def validate_draft(state):
    state = normalize_draft(state)
    optional = {'interior', 'supplements', 'edge_rebar', 'supplements_legacy'}
    required = set(defaults()) - optional
    if (not isinstance(state, Mapping) or not required <= set(state)
            or set(state) - required - optional):
        raise ValueError('La configuración de las mallas del ala no tiene el formato esperado.')
    if not isinstance(state['geometry_confirmed'], bool):
        raise ValueError('La revisión de geometría del ala debe ser explícita.')
    _validate_groups(state, (('geometry', GEOMETRY_FIELDS), ('cover', COVER_FIELDS),
                             ('vertical', VERTICAL_FIELDS), ('horizontal', HORIZONTAL_FIELDS)))
    if state['outer_family'] not in (None, 'vertical', 'horizontal'):
        raise ValueError('Orden de los fierros de la malla exterior no válido.')
    if state['horizontal_start'] not in (None, 'wall', 'footing'):
        raise ValueError('Inicio de los horizontales no válido.')
    _validate_removals(state['removed_pieces'])
    if 'interior' in state:
        interior = state['interior']
        required_inner = {'enabled', 'vertical', 'horizontal', 'removed_pieces'}
        if (not isinstance(interior, Mapping) or not required_inner <= set(interior)
                or set(interior) - required_inner - {'parameters_initialized'}):
            raise ValueError('La configuración de malla interior del ala no tiene el formato esperado.')
        if not isinstance(interior['enabled'], bool):
            raise ValueError('La activación de la malla interior debe ser explícita.')
        if ('parameters_initialized' in interior
                and not isinstance(interior['parameters_initialized'], bool)):
            raise ValueError('El estado de los parámetros de malla interior no es válido.')
        _validate_groups(interior, (('vertical', VERTICAL_FIELDS), ('horizontal', HORIZONTAL_FIELDS)))
        _validate_removals(interior['removed_pieces'])
    if 'supplements' in state:
        supplements = state['supplements']
        if not isinstance(supplements, Mapping) or set(supplements) != {'front', 'back'}:
            raise ValueError('Los grupos de suples interiores no tienen el formato esperado.')
        for name, values in supplements.items():
            fields = (*SUPPLEMENT_FIELDS, *(('range_height_cm',) if name == 'front' else ()))
            if (not isinstance(values, Mapping) or set(values) != {'enabled', 'removed_pieces', *fields}
                    or not isinstance(values['enabled'], bool)):
                raise ValueError('La activación y los campos del grupo de suples no son válidos.')
            _validate_groups({name: {key: values[key] for key in fields}}, ((name, fields),))
            _validate_removals(values['removed_pieces'])
    if 'edge_rebar' in state:
        edge = state['edge_rebar']
        if (not isinstance(edge, Mapping) or set(edge) != {'top_hook_enabled', 'removed_pieces', *EDGE_FIELDS}
                or not isinstance(edge['top_hook_enabled'], bool)):
            raise ValueError('Los campos del fierro de canto no son válidos.')
        _validate_groups({'edge': {key: edge[key] for key in EDGE_FIELDS}}, (('edge', EDGE_FIELDS),))
        if edge['quantity'] is not None and edge['quantity'] != int(edge['quantity']):
            raise ValueError('La cantidad de fierros de canto debe ser entera.')
        _validate_removals(edge['removed_pieces'])
    if 'supplements_legacy' in state:
        _validate_legacy_ranges(state['supplements_legacy'])


def _validate_groups(state, groups):
    for group, fields in groups:
        values = state[group]
        if not isinstance(values, Mapping) or set(values) != set(fields):
            raise ValueError(f'Campos de {group} del ala no válidos.')
        for key, value in values.items():
            if key == 'mark' or key.startswith('mark_'):
                if not isinstance(value, str) or len(value) > 32:
                    raise ValueError('La marca debe ser un texto de hasta 32 caracteres.')
            elif value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                       or not math.isfinite(value) or abs(value) > 1e7):
                raise ValueError(f'{group}.{key}: ingresa un número finito o deja el campo vacío.')


def _validate_removals(records):
    if not isinstance(records, list) or len(records) > 50000:
        raise ValueError('Lista de fierros eliminados del ala no válida.')
    seen = set()
    for record in records:
        if not isinstance(record, Mapping) or set(record) != {'id', 'signature'}:
            raise ValueError('Cada baja debe conservar identificador y firma de geometría.')
        identity, signature = record['id'], record['signature']
        if (not isinstance(identity, str) or not re.fullmatch(r'wing:(left|right):[a-z_]+:[0-9]{1,6}', identity)
                or identity in seen or not isinstance(signature, str)
                or not re.fullmatch(r'[a-f0-9]{64}', signature)):
            raise ValueError('Identidad o firma de un fierro del ala no válida.')
        seen.add(identity)


def from_project(project, instance_key, side, abutment_state=None):
    from .wing_geometry import extract_geometry
    if instance_key not in ('entrada', 'salida') or side not in ('left', 'right'):
        raise ValueError('Selecciona el estribo y el lado del ala.')
    metadata = extract_geometry(project, instance_key, side, abutment_state)
    state = defaults()
    state['geometry'].update({key: metadata.get('geometry', {}).get(key) for key in GEOMETRY_FIELDS})
    result = {'present': metadata.get('present', True), 'state': state,
              'issues': metadata.get('issues', []), 'geometry_source': metadata.get('quality', 'nominal')}
    saved = (abutment_state or {}).get('wings', {}).get(side)
    result['normalized_state'] = normalize_draft(saved, add_controls=True) if saved is not None else None
    try:
        from .wing_geometry import build_wing_profile
        working = result['normalized_state'] or state
        result['range_preview'] = _range_preview(build_wing_profile(metadata, working['geometry']))
    except (ValueError, TypeError, KeyError):
        result['range_preview'] = None
    return result


def _range_preview(profile):
    """Reviewed side profile for editing zones, never fabricated steel."""
    geometry = profile['geometry']
    return {
        'profile_cm': [[u*100, z*100] for u, z in profile['exterior_profile_m']],
        **{key: geometry[key] for key in ('main_length_cm', 'extension_length_cm',
                                          'front_height_cm', 'back_thickness_cm')},
        'reference': 'footing_top', 'extension_enabled': bool(profile.get('extension_enabled')),
    }


def mesh_marks(state):
    """Reserve saved marks even while the interior mesh is disabled."""
    meshes = [state]
    if 'interior' in state:
        interior = state['interior']
        if not isinstance(interior, Mapping):
            raise ValueError('Configuración de malla interior del ala no válida.')
        meshes.append(interior)
    names = []
    for mesh in meshes:
        for group in ('vertical', 'horizontal'):
            values = mesh.get(group, {})
            if not isinstance(values, Mapping):
                raise ValueError('Configuración de fierros de ala no válida.')
            names.extend(value.strip().upper() for key, value in values.items()
                         if key.startswith('mark_') and isinstance(value, str) and value.strip())
    for values in state.get('supplements', {}).values():
        if isinstance(values, Mapping) and isinstance(values.get('mark'), str) and values['mark'].strip():
            names.append(values['mark'].strip().upper())
    edge = state.get('edge_rebar', {})
    if isinstance(edge, Mapping) and isinstance(edge.get('mark'), str) and edge['mark'].strip():
        names.append(edge['mark'].strip().upper())
    return names


def conflicting_marks(state, abutment_state, side):
    """Check the entire abutment, independently of which view is visible."""
    reserved = set()
    abutment_state = abutment_state if isinstance(abutment_state, Mapping) else {}
    for rule in abutment_state.get('rules', ()):
        if rule.get('enabled') is not False:
            reserved.update(str(rule.get(field, '')).strip().upper()
                            for field in ('mark', 'continuation_mark', 'terminal_mark'))
    for other_side, other_state in abutment_state.get('wings', {}).items():
        if other_side != side:
            reserved.update(mesh_marks(other_state))
    names = mesh_marks(state)
    return sorted({name for name in names if name in reserved or names.count(name) > 1})


def preview(project, instance_key, side, state, abutment_state=None):
    from .wing_geometry import extract_geometry
    metadata = extract_geometry(project, instance_key, side, abutment_state)
    return preview_from_metadata(metadata, side, state, abutment_state)


def preview_from_metadata(metadata, side, state, abutment_state=None):
    from .wing_geometry import build_wing_profile
    from sincal.rebar.wing_mesh import build_wing_mesh, opposed_mesh_issues
    validate_draft(state)
    state = normalize_draft(state)
    abutment_state = {**(abutment_state or {}),
                      'wings': {**(abutment_state or {}).get('wings', {}), side: state}}
    profile = build_wing_profile(metadata, deepcopy(state['geometry']))
    result = build_wing_mesh(profile, state, abutment_state, side)
    def merge(other):
        result['valid'] = result['valid'] and other['valid']
        for key in ('issues', 'marks', 'details', 'bars', 'removed_bars'):
            result[key].extend(other[key])
        result['total_kg'] += other['total_kg']
    blocked = False
    inner_result = None
    interior = state.get('interior', {})
    if interior.get('enabled'):
        inner_state = {**state, **{key: interior[key] for key in ('vertical', 'horizontal', 'removed_pieces')}}
        inner_result = build_wing_mesh(profile, inner_state, abutment_state, side, mesh='interior')
        merge(inner_result)
        layer_issues = opposed_mesh_issues(profile, state, inner_state)
        result['issues'].extend(layer_issues)
        blocked = bool(layer_issues)
    if any(item.get('enabled') for item in state.get('supplements', {}).values()):
        from sincal.rebar.wing_supplements import build_wing_supplements
        supplement_result = build_wing_supplements(profile, state, abutment_state, side, inner_result)
        merge(supplement_result)
        if 'supplement_ranges_cm' in supplement_result:
            result['supplement_ranges_cm'] = supplement_result['supplement_ranges_cm']
    if 'edge_rebar' in state:
        from sincal.rebar.wing_edge import build_wing_edge
        edge_result = build_wing_edge(profile, state['edge_rebar'], abutment_state, side)
        merge(edge_result)
        result['edge_extensions_cm'] = edge_result.get('edge_extensions_cm', [])
    elif profile.get('extension_enabled'):
        result['issues'].append({'severity': 'warning', 'message':
            'Este borrador anterior no tiene configurado el fierro de canto obligatorio de la aleta. Abre los parámetros del ala para incorporarlo.'})
    if state['outer_family'] != 'vertical' or state['horizontal_start'] != 'wall':
        result['issues'].append({'severity': 'error', 'message':
            'Esta malla lleva los verticales por fuera y los horizontales pegados por dentro, desde la base del muro sobre la zapata.'})
        blocked = True
    conflicts = conflicting_marks(state, abutment_state, side)
    if conflicts:
        result['issues'].append({'severity': 'error', 'message':
            'Estas marcas ya están reservadas en el estribo: ' + ', '.join(conflicts) + '. Usa marcas únicas.'})
        blocked = True
    if not state['geometry_confirmed']:
        result['issues'].append({'severity': 'error', 'message':
            'Revisa las cotas del moldaje del ala y confirma su geometría antes de calcular la armadura.'})
        blocked = True
    if blocked:
        result.update(valid=False, bars=[], marks=[], details=[], total_kg=0.)
        if 'edge_extensions_cm' in result:
            result['edge_extensions_cm'] = []
    result['range_preview'] = _range_preview(profile)
    return result
