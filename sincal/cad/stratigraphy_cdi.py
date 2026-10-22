"""CDI documentary intervals, keeping SPT and drilling recovery independent.

Depths are paper coordinates scaled from published model metres. The shared
CAD writer restores real model depths and applies the current annotation scale.
Company/study metadata deliberately does not participate in this scene.
"""
import math
import textwrap

from sincal.cad.stratigraphy import annotation_scale_value, drawing_label
from sincal.prospecciones import number
from sincal.stratigraphy_hatches import HATCHES


def cdi_scene(hole, include_table=False, annotation_scale=10.0):
    annotation_scale = annotation_scale_value(annotation_scale)
    items = []

    def line(a, b, color=8, **metadata):
        items.append(dict(kind='line', points=[a, b], color=color, **metadata))

    def text(x, y, label, anchor='center', **metadata):
        items.append(dict(kind='text', point=[x, y], text=drawing_label(label),
                          anchor=anchor, color=3, height=2.5, **metadata))

    strata = hole.horizons
    drilling = hole.drilling_records
    soil_depth = max(number(row.end) for row in strata)
    depth = max(number(row.end) for row in [*strata, *drilling, *hole.tests])
    top, gx, width, rx, rw, description_x = 27, 42, 80, 154, 60, 234

    def y(value):
        return top + number(value) * annotation_scale

    nmax = max(100, math.ceil(max((number(t.nspt) for t in hole.tests if not t.refusal),
                                  default=0) / 10) * 10)
    text(0, 0, f'Sondaje {hole.name}', 'left')
    text(0, 7, 'Registro de sondaje · ensayos por intervalo', 'left')
    text(0, 19, 'Prof. (m)', 'left')
    text(gx + width / 2, 14, 'NSPT (golpes/pie)')
    text(rx + rw / 2, 14, 'Recuperación (%)')
    text(description_x, 14, 'Descripción del horizonte', 'left')

    for start, span, maximum, panel in [(gx, width, nmax, 'nspt'),
                                        (rx, rw, 100, 'recovery')]:
        for i in range(11):
            xx = start + span * i / 10
            line([xx, top], [xx, y(depth)], panel=panel)
            if i % 2 == 0:
                text(xx, 23, f'{maximum * i / 10:g}')
                line([xx, top - 2], [xx, top], 1)
    step = max(1, math.ceil(depth / 40), math.ceil(4 / annotation_scale))
    for d in sorted(set([*range(0, math.ceil(depth), step), depth])):
        yy = y(d)
        line([gx, yy], [gx + width, yy])
        line([rx, yy], [rx + rw, yy])
        line([9, yy], [12, yy], 1)
        if d == depth or depth - d >= step * .45:
            text(7, yy, f'{d:g}', 'right')

    last_bottom = top - 3
    for row in strata:
        a, b = y(row.start), y(row.end)
        if b <= a:
            continue
        for name in [row.material, *row.inclusions]:
            items.append(dict(kind='hatch', bounds=[12, a, 26, b], material=name,
                              color=8, horizon=row.index))
        for u, v in [([12, a], [26, a]), ([12, b], [26, b]),
                     ([12, a], [12, b]), ([26, a], [26, b])]:
            line(u, v, 1, series='strata', horizon=row.index)
        label = f'{row.index}. {row.start}–{row.end} m: {row.description}'
        lines = textwrap.wrap(label, 62) or ['']
        centre, half = (a + b) / 2, max(2, 2 * len(lines))
        yy = max(centre, last_bottom + 1.5 + half)
        text(description_x, yy, '\n'.join(lines), 'left', horizon=row.index)
        # The leader identifies the true interval if a long description moves.
        if yy - centre > .2:
            line([description_x - 7, centre], [description_x - 2, yy], 8,
                 series='description-leader', horizon=row.index)
        last_bottom = yy + half

    for test in hole.tests:
        a, b = y(test.start), y(test.end)
        if test.refusal:
            xx = gx + width + 7
            if b > a:
                line([xx, a], [xx, b], 1, series='refusal', test=test.index)
                line([xx - 1, a], [xx + 1, a], 1, series='refusal', test=test.index)
                line([xx - 1, b], [xx + 1, b], 1, series='refusal', test=test.index)
            else:
                line([xx - 1, a], [xx + 1, a], 1, series='refusal', test=test.index)
            text(xx + 3, (a + b) / 2, 'R', 'left', test=test.index)
            continue
        xx = gx + width * number(test.nspt) / nmax
        if b > a:
            line([xx, a], [xx, b], 5, series='nspt', test=test.index)
        # Independent measured intervals: never bridge gaps or a refusal.
        for yy in dict.fromkeys((a, b)):
            items.append(dict(kind='circle', point=[xx, yy], radius=.65,
                              color=1, series='nspt-marker', test=test.index))

    previous = None
    for row in drilling:
        a, b = number(row.start), number(row.end)
        if b <= a:
            previous = None
            continue
        xx = rx + rw * number(row.recovery) / 100
        if previous is not None and abs(a - previous[1]) < .001:
            line([previous[0], y(a)], [xx, y(a)], 5, series='recovery')
        line([xx, y(a)], [xx, y(b)], 5, series='recovery')
        previous = (xx, b)

    bottom = max(y(depth), last_bottom) + 10
    text(0, bottom, 'Azul: NSPT por intervalo; recuperación en panel independiente.', 'left')
    text(0, bottom + 6, 'R: rechazo sin equivalencia numérica. No se unen ensayos separados.', 'left')
    text(0, bottom + 12, 'LONG. cm es longitud de muestra; no se presenta como longitud recuperada.', 'left')
    text(0, bottom + 18, 'Límites y valores publicados sin recalcular ni extrapolar.', 'left')
    bottom += 28
    for name in dict.fromkeys(n for r in strata for n in [r.material, *r.inclusions]):
        items.append(dict(kind='hatch', bounds=[0, bottom, 14, bottom + 5],
                          material=name, color=8))
        text(18, bottom + 2.5, HATCHES[name]['label'], 'left')
        bottom += 8
    if soil_depth < depth:
        text(0, bottom + 3, f'Horizontes hasta {soil_depth:g} m; sin extrapolar.', 'left')
        bottom += 8
    pages = sorted({r.page for r in [*strata, *drilling, *hole.tests]})
    text(0, bottom + 3, 'Fuente: tablas del informe, págs. ' + ', '.join(map(str, pages)), 'left')
    bottom += 12
    if include_table:
        bottom = _tables(hole, bottom + 10, line, text)
    return dict(items=items, viewbox=[-5, -6, 350, bottom + 15], depth=depth,
                nspt_max=nmax, format=hole.drawing_format, depth_scale=annotation_scale,
                depth_origin=top, annotation_scale=annotation_scale,
                accessible_label='CDI: horizontes, NSPT por intervalo, rechazos y recuperación independiente')


def _tables(hole, cursor, line, text):
    """Preserve published table fields; do not derive absent thickness/lengths."""
    def table(title, headers, widths, rows):
        nonlocal cursor
        text(0, cursor, title, 'left')
        cursor += 6
        columns = [0]
        for width in widths:
            columns.append(columns[-1] + width)
        for row in [headers, *rows]:
            labels = [textwrap.wrap(str(value), max(4, int((width - 2) / 1.45))) or ['']
                      for value, width in zip(row, widths)]
            height = max(8, 4 * max(map(len, labels)) + 2)
            line([0, cursor], [columns[-1], cursor])
            for x, label in zip(columns, labels):
                text(x + 1, cursor + height / 2, '\n'.join(label), 'left')
            for x in columns:
                line([x, cursor], [x, cursor + height])
            cursor += height
            line([0, cursor], [columns[-1], cursor])
        cursor += 12

    table('Horizontes · espesor no publicado: se muestran únicamente las cotas',
          ['N.º', 'Desde m', 'Hasta m', 'Descripción oficial', 'Página'],
          [18, 25, 25, 239, 23],
          [[r.index, r.start, r.end, r.description, r.page] for r in hole.horizons])
    table('Registro de perforación y recuperación',
          ['Desde m', 'Hasta m', 'Perforado m', 'Recuperado m', 'Recuperación %', 'Presión PSI', 'Página'],
          [32, 32, 40, 40, 45, 40, 25],
          [[r.start, r.end, r.drilled, r.recovered, r.recovery, r.pressure, r.page]
           for r in hole.drilling_records])
    table('Ensayos SPT · numeración y longitud de muestra originales',
          ['N.º muestra', 'Desde m', 'Hasta m', 'LONG. cm', 'Herramienta', 'Mecanismo',
           'N1', 'N2', 'N3', 'NSPT', 'Página'],
          [24, 25, 25, 27, 50, 50, 25, 25, 25, 29, 25],
          [[r.sample_number, r.start, r.end, r.sample_length, r.tool, r.mechanism,
            r.n1, r.n2, r.n3, r.nspt, r.page] for r in hole.tests])
    return cursor
