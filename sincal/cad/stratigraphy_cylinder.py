"""Standalone pictorial cylinder; source depths remain true model metres."""
import math
import re

from sincal.cad.stratigraphy import drawing_label
from sincal.prospecciones import number


_USCS = r'(?:GW|GP|GM|GC|SW|SP|SM|SC|ML|CL|OL|MH|CH|OH|PT)'
_CODE = re.compile(rf'(?<![A-Z]){_USCS}(?:\s*[-–]\s*{_USCS})?(?![A-Z])', re.I)


def published_uscs(description):
    """Require a named classification field, not a soil-to-code inference."""
    fields = re.findall(r'\b(?:USCS|SUCS)\s*[:=]?\s*([^\n.;]+)', description, re.I)
    codes = []
    for field in fields:
        found = _CODE.findall(field)
        if (len(found) != 1 or not re.match(rf'^\s*[\("\']?\s*{_USCS}\b', field, re.I)
                or re.search(r'\?|posible|probable|estimad|aproximad', field, re.I)):
            return ''
        codes.append(re.sub(r'\s+', '', found[0]).replace('–', '-').upper())
    return codes[0] if codes and len(set(codes)) == 1 else ''


def cylinder_scene(hole, annotation_scale):
    rows = [row for row in hole.strata if number(row.end) > number(row.start)]
    depth = max(number(row.end) for row in rows)
    cx, rx, ry, top = 19, 7, 3.5, 14
    items, outlines, labels = [], [], []

    def y(value):
        return top + number(value) * annotation_scale

    def line(a, b):
        return dict(kind='line', points=[a, b], color=1)

    def ellipse(yy, start=0, end=math.pi):
        return dict(kind='ellipse', point=[cx, yy], rx=rx, ry=ry,
                    start=start, end=end, color=1)

    def text(x, yy, label, anchor):
        labels.append(dict(kind='text', point=[x, yy], text=drawing_label(label),
                           anchor=anchor, height=2.5, color=3))

    text(cx, 0, f'Sondaje {hole.name}', 'center')
    previous = None
    bounds = {}
    last_code_y = -math.inf
    for row in rows:
        a, b = y(row.start), y(row.end)
        boundary = [ellipse(a, math.pi, 0), line([cx + rx, a], [cx + rx, b]),
                    ellipse(b), line([cx - rx, b], [cx - rx, a])]
        materials = [row.material, *row.inclusions]
        for material in materials:
            items.append(dict(kind='hatch', bounds=[cx-rx, a, cx+rx, b+ry],
                              boundary=boundary, material=material, color=8))
        # A gap is kept open, never spanned by a hatch or a side wall.
        if previous is None or abs(number(row.start)-previous) > 1e-9:
            cap = ellipse(a, 0, 2*math.pi)
            for material in materials:
                items.append(dict(kind='hatch', bounds=[cx-rx, a-ry, cx+rx, a+ry],
                                  boundary=[cap], material=material, color=8))
            outlines.append(cap)
        # The preceding band's lower arc already marks a shared interface.
        outlines.extend([line([cx-rx, a], [cx-rx, b]),
                         line([cx+rx, a], [cx+rx, b]), ellipse(b)])
        for value in (row.start, row.end):
            bounds.setdefault(number(value), value)
        code = published_uscs(row.description)
        if code:
            actual = (a+b)/2 + ry
            yy = max(actual, last_code_y+4)
            text(cx+rx+6, yy, code, 'left')
            if yy > actual+.1:
                outlines.append(line([cx+rx+1, actual], [cx+rx+5, yy]))
            last_code_y = yy
        previous = number(row.end)
    last_y = -math.inf
    for value, published in sorted(bounds.items()):
        actual = y(value)
        yy = max(actual, last_y+4)
        text(cx-rx-4, yy, published+' m', 'right')
        outlines.append(line([cx-rx-3, yy], [cx-rx, actual]))
        last_y = yy
    items.extend(outlines)
    items.extend(labels)
    bottom = max(y(depth)+ry, last_y, last_code_y)+5
    return dict(items=items, viewbox=[-8, -5, 65, bottom+5], depth=depth,
                format=hole.drawing_format, output_mode='isometric-cylinder',
                depth_scale=annotation_scale, depth_origin=top,
                annotation_scale=annotation_scale,
                accessible_label='Solo cilindro estratigráfico isométrico, límites y clasificación USCS publicada')
