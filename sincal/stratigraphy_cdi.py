"""CDI field SPT logs: independent horizons, drilling recovery and SPT tables.

Read native documentary tables only. In particular, LONG. (cm) is not renamed
as recovered length, refusal tokens are not numbers, and figure curves never
replace the published tables. Identity is read from captions, not filenames.
"""
from collections import Counter
import re

from sincal.prospecciones import normalized, number
from sincal.stratigraphy import (
    NUM, Borehole, DrillingRecord, Horizon, Spt, StratigraphyReport, material,
)

CAPTION = re.compile(r'\bTabla\s+\d+\s*:[^\n]*?\bSPT\s+en\s+S\s*[-–]\s*(\d+)\b', re.I)
HORIZON = re.compile(rf'\bH\s*(\d+)\s*\(\s*({NUM})\s*m\s*[-–]\s*({NUM})\s*m\s*\)\s*:\s*(.*)', re.I)
HORIZON_HINT = re.compile(r'\bH\s*\d+\s*\(', re.I)
ROW_SUFFIX = re.compile(r'(?<!\S)(?=[\d?+\-])\S+\s+(?=[\d?+\-])\S+(?:\s+\S+)*\s*$')
SPT_ROW = re.compile(r'^(.+?)\s+(HIDR[ÁA]ULICO|MANUAL)\s+(.+)$', re.I)
STROKE = re.compile(rf'(?:{NUM}R?|-)', re.I)


def _company(text, page):
    """Only documentary contact information; never infer a named engineer."""
    info = {'company': 'CDI', 'method': 'SPT', 'source_page': str(page)}
    title = re.search(r'[“"](Estudio[^\n”"]+)[”"]', text, re.I)
    if title:
        info['document'] = title[1].strip()
    email = re.search(r'\bemail\s*:\s*([^\s]+)', text, re.I)
    website = re.search(r'\bURL\s*:\s*(https?://[^\s]+)', text, re.I)
    phone = re.search(r'\bFono\s*:\s*(.+?)\s*Fax\s*:', text, re.I)
    address = re.search(r'^\s*(Paseo\s+.+?)\s*,\s*Fono\s*:', text, re.I | re.M)
    for name, match in [('email', email), ('website', website), ('phone', phone), ('address', address)]:
        if match:
            info[name] = match[1].strip()
    return info


def _error(hole, page, kind, line):
    hole.extraction_errors.append(f'Pág. {page}: {kind} no reconocido o incompleto: {line.strip()}')


def _drilling_row(hole, page, line):
    values = line.split()
    valid = len(values) in (5, 6) and all(re.fullmatch(NUM, v) for v in values[:5])
    if valid and len(values) == 6:
        valid = values[5] == '-' or bool(re.fullmatch(NUM, values[5]))
    if not valid:
        _error(hole, page, 'registro de perforación', line)
        return
    pressure = values[5] if len(values) == 6 else ''
    hole.drilling_records.append(DrillingRecord(*values[:5], pressure, page))
    if not pressure:
        hole.warnings.append(f'Pág. {page}, {values[0]}–{values[1]} m: presión de perforación sin valor publicado; se conserva vacía.')


def _horizons_and_drilling(hole, page, section, seen):
    current = None

    def finish():
        if not current:
            return
        current.description = ' '.join(current.description.split())
        current.material = material(current.description)
        if not current.description:
            _error(hole, page, f'descripción de H{current.index}', '')
        previous = seen.get(current.index)
        if previous:
            # Repeated descriptions at sheet boundaries are a single horizon.
            if ((number(previous.start), number(previous.end)) != (number(current.start), number(current.end))
                    or normalized(previous.description) != normalized(current.description)):
                hole.extraction_errors.append(f'H{current.index}, págs. {previous.page} y {page}: límites o descripción distintos; requiere cotejo. No se reemplazó el horizonte.')
        else:
            seen[current.index] = current
            hole.horizons.append(current)

    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = HORIZON.search(line)
        if match:
            prefix = line[:match.start()].strip()
            if prefix:
                _drilling_row(hole, page, prefix)
            finish()
            index, start, end, description = match.groups()
            current = Horizon(int(index), start, end, '', description, page)
            continue
        if HORIZON_HINT.search(line):
            finish()
            current = None
            _error(hole, page, 'horizonte', line)
            continue
        row = ROW_SUFFIX.search(line)
        if row:
            prefix = line[:row.start()].strip()
            if prefix:
                if current:
                    current.description += ' ' + prefix
                else:
                    _error(hole, page, 'descripción sin horizonte', prefix)
            _drilling_row(hole, page, row[0])
        elif current:
            # A stray numeric token signals a broken row, not prose to append.
            if re.match(r'^[\d?+\-]', line):
                _error(hole, page, 'registro de perforación', line)
            else:
                current.description += ' ' + line
        else:
            _error(hole, page, 'fila de perforación', line)
    finish()


def _spt_rows(hole, page, section):
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = SPT_ROW.fullmatch(line)
        values = match[3].split() if match else []
        valid = (len(values) == 8 and all(re.fullmatch(NUM, v) for v in values[:2])
                 and re.fullmatch(r'\d+', values[2]) and re.fullmatch(NUM, values[3])
                 and all(STROKE.fullmatch(v) for v in values[4:7])
                 and re.fullmatch(rf'(?:{NUM}|R)', values[7], re.I))
        if not valid:
            _error(hole, page, 'registro SPT', line)
            continue
        start, end, sample_number, sample_length, n1, n2, n3, nspt = values
        hole.tests.append(Spt(
            len(hole.tests)+1, start, end, '', '', n1, n2, n3, nspt, page, 'cm',
            sample_number=sample_number, sample_length=sample_length,
            tool=match[1], mechanism=match[2],
        ))


def parse_cdi_report(pages, source='', sha256=''):
    report = StratigraphyReport(source, sha256)
    signatures = [normalized(text) for text in pages]
    all_text = '\n'.join(signatures)
    if not (re.search(r'\bcdi\.cl\b', all_text) and 'registro spt' in all_text
            and 'recuperacion' in all_text and 'presion' in all_text and '[psi]' in all_text):
        return report
    captions = [(page, match) for page, text in enumerate(pages, 1) for match in CAPTION.finditer(text)]
    if not captions:
        return report
    first_page, first_caption = captions[0]
    identifier = int(first_caption[1])
    published_name = f'S-{first_caption[1]}'
    hole = Borehole(f'{published_name}-p{first_page}', published_name, method='cdi-text')
    report.boreholes.append(hole)
    hole.study_info = _company(pages[first_page-1], first_page)
    if any(int(caption[1]) != identifier for _, caption in captions):
        hole.extraction_errors.append('Hay tablas de más de un sondaje en el informe CDI; no se mezclaron sus filas.')
        return report
    seen = {}
    header_warning = False
    active_caption_range = None
    for page, (text, plain) in enumerate(zip(pages, signatures), 1):
        recovery = ('presion' in plain and '[psi]' in plain) or ('perforado' in plain and 'recuperado' in plain)
        spt = 'registro pruebas de penetracion' in plain
        figure = 'grafica del ensayo spt' in plain and 'perfil estratigrafico' in plain
        if CAPTION.search(text) and not (recovery or spt):
            _error(hole, page, 'tabla CDI', 'No se reconocieron sus cabeceras.')
            report.pages[str(page)] = {'text': text, 'image_png': ''}
        if not (recovery or spt or figure):
            continue
        report.pages[str(page)] = {'text': text, 'image_png': ''}
        printed = re.search(r'P[áa]gina\s+(\d+)\s+de\s+(\d+)', text, re.I)
        if printed and (int(printed[1]) != page or int(printed[2]) != len(pages)):
            hole.warnings.append(f'Pág. PDF {page}: el pie impreso dice «Página {printed[1]} de {printed[2]}». Se usa la numeración real del PDF.')
        if figure:
            hole.warnings.append(f'Perfil gráfico en pág. {page}: se conserva como evidencia visual; las curvas no sustituyen los valores publicados en tablas ni se digitalizan automáticamente.')
        if recovery:
            end = re.search(r'REGISTRO\s+PRUEBAS\s+DE\s+PENETRACI[ÓO]N', text, re.I)
            recovery_text = text[:end.start()] if end else text
            units = re.search(r'DESDE\s*\[m\]\s+HASTA\s*\[m\]\s+PERFORADO\s*\[m\]\s+RECUPERADO\s*\[m\]\s+RECUPERACI[ÓO]N\s*\[%\]', recovery_text, re.I)
            if not units or '[psi]' not in plain:
                _error(hole, page, 'columnas/unidades de perforación', 'Se requieren profundidades y longitudes en m, recuperación en % y presión en PSI.')
            else:
                count = len(hole.drilling_records)
                _horizons_and_drilling(hole, page, recovery_text[units.end():], seen)
                if len(hole.drilling_records) == count:
                    _error(hole, page, 'tabla de perforación', 'Sin filas reconocidas.')
        if spt:
            units = re.search(r'DESDE\s*\[m\]\s+HASTA\s*\[m\]\s+N[ÚU]MERO\s+LONG\.\s*\(cm\)\s+N1\s+N2\s+N3\s+Nspt\b', text, re.I)
            if not units:
                _error(hole, page, 'columnas/unidades SPT', 'Se requieren profundidades en m, número, LONG. (cm), N1, N2, N3 y Nspt.')
            else:
                count = len(hole.tests)
                _spt_rows(hole, page, text[units.end():])
                if len(hole.tests) == count:
                    _error(hole, page, 'tabla SPT', 'Sin filas reconocidas.')
            header_warning |= bool(re.search(r'N1\s*\+\s*N3\s*=\s*Nspt', text, re.I))
        caption_range = re.search(rf'\bTabla\s+\d+\s*:[^\n]*?\bdesde\s+({NUM})\s*m\s+hasta\s+({NUM})\s*m', text, re.I)
        if caption_range:
            active_caption_range = (caption_range[1], caption_range[2], page)
        page_rows = [row for row in [*hole.drilling_records, *hole.tests] if row.page == page]
        if active_caption_range and page_rows:
            start, end, caption_page = active_caption_range
            a, b = number(start), number(end)
            if any(number(row.start) < a-1e-9 or number(row.end) > b+1e-9 for row in page_rows):
                hole.warnings.append(f'Pág. {page}: la leyenda indica {start}–{end} m (pág. {caption_page}), pero hay filas fuera de ese tramo. Se conservan las profundidades de las tablas.')
    if header_warning:
        hole.warnings.append('La cabecera impresa indica «N1+N3=Nspt». Se conserva el Nspt oficial de cada fila sin recalcularlo; cotejar esta indicación con el emisor.')
    numbers = [int(row.sample_number) for row in hole.tests]
    if numbers:
        repeated = sorted(n for n, count in Counter(numbers).items() if count > 1)
        missing = sorted(set(range(1, max(numbers)+1))-set(numbers))
        if repeated:
            hole.warnings.append('Numeración de muestras SPT repetida en el informe: '+', '.join(map(str, repeated))+'. Se conservan todas las filas y sus profundidades.')
        if missing:
            hole.warnings.append('No hay filas SPT con los números de muestra '+', '.join(map(str, missing))+'. No se agregaron ensayos ni se interpolaron valores.')
        if numbers != sorted(numbers):
            hole.warnings.append('Los números de muestra SPT retroceden entre hojas. Se conserva el orden y la numeración publicados, identificando cada fila por su profundidad.')
    hole.warnings = hole.audit()
    report.notices = [
        'Formato CDI: horizontes H, registro de perforación/recuperación y pruebas SPT son fuentes independientes; no se derivan unos de otros.',
        'Profundidades y perforado/recuperado en m; recuperación en %; presión en PSI; LONG. de muestra en cm. LONG. no se interpreta como longitud recuperada.',
        'N1, N2, N3 y Nspt son literales oficiales. Se conservan 50R, 59R, R y guiones; no se asigna un Nspt numérico a un rechazo.',
        'Los hatch terminan en los límites de los horizontes descritos; no se extrapola una capa para completar el registro de perforación.',
    ]
    return report
