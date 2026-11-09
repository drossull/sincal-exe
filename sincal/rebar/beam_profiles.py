"""Catálogo geométrico ligero de Proyecto Puentes, en milímetros.

La viga no incorpora armaduras. Las medidas y el recorrido de la sección
corresponden a vigas_predefinidas.py y vigas.crear_perfil_viga_2d.
"""
from __future__ import annotations

from collections.abc import Mapping
import math


PROFILE_KEYS = ('b1', 'b3', 'b4', 'b5', 'b7', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'ch')
_ROWS = {
    1: ('Viga H101', (1520,160,200,210,720,70,60,150,100,75,170,1010,25)),
    2: ('Viga H135', (1520,160,200,210,720,70,60,150,100,75,170,1350,25)),
    3: ('Viga H151', (1520,160,200,275,850,70,60,150,100,75,200,1510,25)),
    4: ('Viga H170', (1520,160,200,275,850,70,80,150,100,75,200,1700,25)),
    5: ('Viga H185', (1520,160,200,275,850,70,60,150,100,100,200,1850,25)),
    6: ('Viga H200', (1520,160,200,300,950,70,60,200,150,150,230,2000,25)),
    7: ('Viga H220', (1520,160,200,300,950,70,60,200,150,150,200,2200,25)),
    8: ('Viga H135 Orbital', (1530,175,180,225,720,70,40,150,100,75,170,1350,25)),
    9: ('Viga H151 Orbital', (1530,175,180,225,720,70,40,150,125,75,200,1510,25)),
    10: ('Viga H201 Orbital', (1520,160,200,250,840,70,40,200,150,150,150,2010,25)),
    11: ('Viga H186 Orbital', (1530,125,180,225,720,70,40,200,150,150,150,1860,25)),
    12: ('Viga Los Batros', (800,160,200,180,700,70,40,200,150,150,150,1881,25)),
    13: ('viga_acero', (450,0,20,215,450,40,0,0,0,0,40,2600,0)),
    14: ('Viga H225', (1520,160,200,300,940,50,60,200,150,150,200,2250,25)),
}


def _number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def resolve_profile(profile_type, custom_profiles=None):
    """Devuelve una copia del perfil; nunca sustituye un tipo desconocido."""
    if not isinstance(profile_type, int) or isinstance(profile_type, bool):
        raise ValueError('Falta un tipo de viga válido en el tablero.')
    if profile_type in _ROWS:
        name, values = _ROWS[profile_type]
        parameters = dict(zip(PROFILE_KEYS, values))
        source = 'catalog'
    else:
        if not isinstance(custom_profiles, (tuple, list)):
            custom_profiles = []
        matches = [r for r in custom_profiles if isinstance(r, Mapping)
                   and isinstance(r.get('tipo'), int) and not isinstance(r.get('tipo'), bool)
                   and r.get('tipo') == profile_type]
        if profile_type < 101 or len(matches) != 1:
            raise ValueError(f'El tipo de viga {profile_type} no existe en el catálogo ni como perfil personalizado único.')
        record = matches[0]
        name = record.get('nombre')
        if not isinstance(name, str) or not name.strip():
            name = f'Perfil {profile_type}'
        parameters = {key: record.get(key) for key in PROFILE_KEYS}
        source = 'custom'
    positive = {'b1', 'b4', 'b7', 'd1', 'd6', 'd7'}
    for key, value in parameters.items():
        if not _number(value) or value < 0 or (key in positive and value <= 0):
            raise ValueError(f'Completa una medida válida del perfil de viga: {key}.')
    p = parameters
    p['b2'] = p['b1']/2-p['b4']/2-p['b3']
    p['b6'] = p['b7']/2-p['b4']/2-p['b5']
    if p['b2'] < 0 or p['b6'] < 0:
        raise ValueError('Las transiciones de la viga no caben entre el alma y sus alas.')
    if sum(p[f'd{i}'] for i in range(1, 7)) > p['d7']:
        raise ValueError('Las alturas parciales de la viga superan su altura total.')
    if p['ch'] > min(p['d6'], p['b7']/2):
        raise ValueError('El chaflán inferior no cabe dentro del ala de la viga.')
    return {'name': name.strip(), 'type': profile_type, 'source': source, 'parameters_mm': p}


def half_section(parameters):
    """Contorno derecho, de base a coronación; x,z en metros."""
    p = parameters
    points = [
        (p['b7']/2-p['ch'], 0), (p['b7']/2, p['ch']), (p['b7']/2, p['d6']),
        (p['b7']/2-p['b5'], p['d6']+p['d5']),
        (p['b4']/2, p['d6']+p['d5']+p['d4']),
        (p['b4']/2, p['d7']-p['d1']-p['d2']-p['d3']),
        (p['b4']/2+p['b3'], p['d7']-p['d1']-p['d2']),
        (p['b1']/2, p['d7']-p['d1']), (p['b1']/2, p['d7']),
    ]
    result = []
    for x, z in points:
        point = [x/1000, z/1000]
        if not result or point != result[-1]:
            result.append(point)
    return result


def section(parameters):
    half = half_section(parameters)
    return half + [[-x, z] for x, z in reversed(half)]
