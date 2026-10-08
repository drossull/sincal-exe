"""VISAN/Petrus vector-figure adapter. Values are printed labels, not OCR guesses.

Associate figure panels by explicit borehole titles. Calibrate vector limits
against labelled depth ticks, and accept exact depths only when one official
geophysical table agrees with both labels and geometric limits. Never guess a
borehole/profile association just from proximity or reuse a different borehole.
"""
from io import BytesIO
import re
from statistics import mean

from sincal.prospecciones import number, normalized, parse_pages
from sincal.stratigraphy import VsBand


def figure_panels(page, names):
    words = page.extract_words(x_tolerance=3, y_tolerance=3)
    headings = sorted((w for w in words if w['text'].replace('–', '-') in names), key=lambda w: w['x0'])
    for i, heading in enumerate(headings):
        name = heading['text'].replace('–', '-')
        right = headings[i+1]['x0']-20 if i+1 < len(headings) else page.width
        starts = [w for w in words if re.fullmatch(r'V[sS]', w['text']) and heading['x0'] < w['x0'] < right and w['top'] > heading['bottom']]
        if not starts:
            continue
        axes = [l for l in page.lines if abs(l['x1']-l['x0']) < .05 and l['bottom']-l['top'] > 80
                and abs(l['x0']-heading['x0']) < 15 and l['top'] > heading['bottom']]
        if not axes:
            yield name, [], 'No se pudo calibrar el eje de profundidad de los Vs.'
            continue
        axis = max(axes, key=lambda l: l['bottom']-l['top'])
        ticks = [l for l in page.lines if abs(l['top']-l['bottom']) < .05 and abs(l['x1']-axis['x0']) < .1 and 2 < l['x1']-l['x0'] < 10]
        pairs = []
        for w in words:
            if not re.fullmatch(r'\d+(?:[.,]\d+)?', w['text']) or not axis['x0']-18 < w['x0'] < w['x1'] < axis['x0']:
                continue
            center = (w['top']+w['bottom'])/2
            tick = min(ticks, key=lambda l: abs(l['top']-center), default=None)
            if tick and abs(tick['top']-center) < 2:
                pairs.append((tick['top'], number(w['text'])))
        if len(pairs) < 6:
            yield name, [], 'No hay suficientes cotas para calibrar los Vs.'
            continue
        mx, my = mean(x for x,y in pairs), mean(y for x,y in pairs)
        variance = sum((x-mx)**2 for x,y in pairs)
        slope = sum((x-mx)*(y-my) for x,y in pairs)/variance if variance else 0
        intercept = my-slope*mx
        if slope <= 0 or max(abs(slope*x+intercept-y) for x,y in pairs) > .015:
            yield name, [], 'El eje Vs no tiene una calibración lineal inequívoca.'
            continue
        labels, failure = [], ''
        for start in sorted(starts, key=lambda w: w['top']):
            row = sorted((w for w in words if abs(w['top']-start['top']) < .8 and start['x0'] <= w['x0'] < right), key=lambda w: w['x0'])
            label = re.match(r'VS\s*=\s*(\d+(?:[.,]\d+)?)\s*(?:[-–]\s*(\d+(?:[.,]\d+)?))?\s*m/s\b', ' '.join(w['text'] for w in row), re.I)
            bars = sorted(set(round(l['top'],4) for l in page.lines
                              if abs(l['top']-l['bottom']) < .05 and abs(l['x0']-start['x0']) < 2 and 15 < l['x1']-l['x0'] < 80))
            above = [y for y in bars if y < start['top']]
            below = [y for y in bars if y > start['bottom']]
            if not label or not above or not below:
                failure = 'Etiqueta o límites Vs incompletos en la figura.'
                break
            labels.append(dict(low=label[1], high=label[2] or label[1],
                               start=max(0, slope*max(above)+intercept), end=slope*min(below)+intercept))
        yield name, labels, failure


def match_profile(labels, profile):
    """Use figure boundaries to select table layers, never average their Vs."""
    if not labels or profile.errors():
        return None
    result = []
    for label in labels:
        first = [i for i,l in enumerate(profile.layers) if abs(number(l.start)-label['start']) < .025]
        last = [i for i,l in enumerate(profile.layers) if abs(number(l.end)-label['end']) < .025]
        if len(first) != 1 or len(last) != 1 or first[0] > last[0]:
            return None
        layers = profile.layers[first[0]:last[0]+1]
        values = [number(l.vs) for l in layers]
        # Figure labels are printed at integer precision in this adapter.
        if any(not any(abs(number(label[k])-v) < 1 for v in values) for k in ('low','high')):
            return None
        result.append((layers[0].start, layers[-1].end, values))
    return result


def attach_vs_bands(report, pdf_bytes, pages, *, check=lambda: None):
    import pdfplumber
    candidates = [i for i,t in enumerate(pages) if 'estratigraf' in normalized(t) and re.search(r'V\s*S\s*=', t, re.I)]
    if not candidates:
        return
    profiles = parse_pages(pages, allow_empty=True).profiles
    names = {h.name for h in report.boreholes}
    with pdfplumber.open(BytesIO(pdf_bytes)) as document:
        for i in candidates:
            check()
            for name, labels, failure in figure_panels(document.pages[i], names):
                check()
                hole = next(h for h in report.boreholes if h.name == name)
                if failure:
                    hole.extraction_errors.append(f'Vs figura pág. {i+1}: {failure}')
                    continue
                matches = [(p, m) for p in profiles if (m := match_profile(labels, p)) is not None]
                if len(matches) != 1 or hole.vs_bands:
                    hole.extraction_errors.append(f'Vs figura pág. {i+1}: asociación con tabla geofísica ausente o ambigua; no se inventaron profundidades.')
                    continue
                profile, rows = matches[0]
                for label, (start, end, values) in zip(labels, rows):
                    hole.vs_bands.append(VsBand(start, end, label['low'], label['high'], i+1, profile.name, profile.page))
                    if any(v < number(label['low'])-1 or v > number(label['high'])+1 for v in values):
                        hole.warnings.append(f'Vs {start}–{end} m: la figura pág. {i+1} indica {label["low"]}–{label["high"]} m/s, pero la tabla pág. {profile.page} incluye '+', '.join(f'{v:g}' for v in values)+' m/s. Se conserva la etiqueta de la figura.')
                report.pages[str(i+1)] = {'text': pages[i], 'image_png': ''}
                report.pages[str(profile.page)] = {'text': pages[profile.page-1], 'image_png': ''}
    for hole in report.boreholes:
        if not hole.vs_bands:
            hole.warnings.append('No se reconocieron tramos Vs asociados a este sondaje en la figura; no se completan con otro sondaje.')
    report.notices.append('Vs: etiquetas de la figura y profundidades contrastadas con la tabla geofísica. Los Vs pueden superar la profundidad perforada, sin prolongar estratos ni ensayos.')
