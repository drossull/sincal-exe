"""Non-destructive import of installed-app session snapshots."""
from .rebar import defaults


def normalize_session(document):
    if 'data' in document and 'identification' in document:
        if document.get('schema_version', 1) != 1:
            raise ValueError('Esta sesión usa una versión de formato no compatible.')
        return document
    if document.get('schema_version') != 1 or not isinstance(document.get('workspace'), dict):
        raise ValueError('Formato de sesión no reconocido.')
    data = document.get('source_json', {}).get('snapshot')
    if not isinstance(data, dict):
        raise ValueError('La sesión antigua no contiene el JSON del proyecto; cárgalo primero en la aplicación original.')
    project = document.get('project', {})
    result = {'data': data, 'identification': {key: str(project.get(key, '')) for key in ('ot', 'revision', 'structure_name')},
              'rebar': {}, 'prospecciones': document.get('prospecciones'), 'legacy_snapshot': document}
    workspace = document['workspace']
    for key in ('entrada', 'salida'):
        saved = workspace.get('abutments', {}).get(key)
        if not saved:
            continue
        state = defaults()
        for field, original in [('largo_cm', 'largo'), ('ancho_cm', 'ancho'), ('alto_cm', 'alto')]:
            state['geometry'][field] = float(str(saved['entries'][original]).replace(',', '.'))
        state['geometry']['esviaje_grados'] = float(str(workspace.get('skew', 0)).replace(',', '.'))
        for field, original in [('inferior_cm', 'rec_inf'), ('superior_cm', 'rec_sup'), ('lateral_cm', 'rec_lat')]:
            state['cover'][field] = float(str(saved['entries'][original]).replace(',', '.'))
        for rule in state['rules']:
            values = saved.get('rules', {}).get(rule['key'], {})
            for field, original in [('diameter_mm', 'diameter'), ('spacing_cm', 'spacing'), ('hook_cm', 'hook')]:
                if original in values:
                    rule[field] = float(str(values[original]).replace(',', '.'))
            rule['enabled'] = values.get('enabled', rule['enabled'])
            rule['mark'] = values.get('mark', rule['mark'])
            rule['origin'] = str(values.get('origin', 'inicio')).lower()
        result['rebar'][key] = state
    # Live handles intentionally not restored: they may identify another drawing.
    return result
