"""Verified legend in master FORMATOS ANOTATIVOS ACAD_2025, PROSPECCIONES.

Names, angles and relative density come from the labelled master samples.
CAD reads the live pattern definitions from that block, not from a PAT file.
"""
HATCHES = {
    'grava': dict(label='Grava', pattern='GRAVEL', scale=.03, angle=0),
    'arena': dict(label='Arena', pattern='AR-SAND', scale=.004, angle=0),
    'arcilla': dict(label='Arcilla', pattern='ANSI31', scale=.05, angle=0),
    'limo': dict(label='Limo', pattern='ANSI36', scale=.05, angle=0),
    'hormigon': dict(label='Hormigón y acero', pattern='SQUARE', scale=.05, angle=45),
    'organico': dict(label='Orgánicos', pattern='HOUND', scale=.043, angle=45),
    'bolones': dict(label='Bolones', pattern='HONEY', scale=.03, angle=45),
    'bloque': dict(label='Bloque', pattern='GRATE', scale=.089, angle=45),
    'clastos': dict(label='Clastos', pattern='ANGLE', scale=.04, angle=45),
    'cementacion': dict(label='Cementación', pattern='AR-CONC', scale=.0015, angle=0),
    'vegetal': dict(label='Suelo vegetal', pattern='SWAMP', scale=.023, angle=0),
    'roca': dict(label='Roca no clasificada', pattern='EARTH', scale=.05, angle=45),
}
