"""Text adapter for individual Puerto Octay-style borehole reports.

Horizons and field samples are independent tables. Never derive strata from
sample spacing, recovery from SPT, or a numerical N from a refusal symbol.
"""
import re
from sincal.prospecciones import normalized
from sincal.stratigraphy import NUM, Borehole, Horizon, Sample, Spt, StratigraphyReport, material

HORIZON = re.compile(rf'^\s*(\d+)\s+({NUM})\s*[-–]\s*({NUM})\s+({NUM})\s*(.*)$')
SAMPLE = re.compile(rf'^\s*(HQ3|SPT\s*N[º°o.]?\s*(\d+))\s+({NUM})\s+({NUM})\s+(.+)$', re.I)


def parse_individual_report(pages, source='', sha256=''):
    report = StratigraphyReport(source, sha256)
    profile_pages = [(i,t) for i,t in enumerate(pages,1)
                     if 'cotas limites' in normalized(t) and 'horizonte' in normalized(t)]
    if not profile_pages:
        return report
    names = re.findall(r'Sondaje\s*:[^\n]*?\bS\s*[-–]\s*(\d+)\b', profile_pages[0][1], re.I)
    if len(set(names)) != 1:
        return report
    identifier = int(names[0])
    hole = Borehole(f'S-{identifier:02d}-p{profile_pages[0][0]}', f'S-{identifier:02d}', method='individual-text')
    report.boreholes.append(hole)
    last = None
    for page, text in profile_pages:
        report.pages[str(page)] = {'text':text, 'image_png':''}
        page_ids = re.findall(r'Sondaje\s*:[^\n]*?\bS\s*[-–]\s*(\d+)\b', text, re.I)
        if any(int(value) != identifier for value in page_ids):
            hole.extraction_errors.append(f'Pág. {page}: otro sondaje en la tabla de horizontes; requiere informes separados.')
            continue
        water = re.search(rf'Prof\.\s*Napa\s*:\s*({NUM})\s*m', text, re.I)
        if water:
            hole.water_depth, hole.water_page = water[1], page
        for line in text.splitlines():
            line = line.strip()
            match = HORIZON.fullmatch(line)
            if match:
                index,a,b,thickness,description = match.groups()
                last = Horizon(int(index),a,b,thickness,description,page)
                hole.horizons.append(last)
            elif normalized(line).startswith('observaciones'):
                break
            elif re.match(r'^\d+\s+\d+[.,]\d+\s*[-–]', line):
                hole.extraction_errors.append(f'Pág. {page}: fila de horizonte no reconocida: {line}')
            elif last and line and not re.match(r'^(?:Página\s+\d+|Horizonte\b|No\s*\(m\)|N[º°]\s*\(m\))', line, re.I):
                last.description = (last.description+' '+line).strip()
    for horizon in hole.horizons:
        # Only clean extraction whitespace for matching, preserve the source description.
        desc = re.sub(r'^(?:Terreno\s+natural|Relleno/Terraplén)\s*\.\s*', '', horizon.description, flags=re.I)
        desc = re.sub(r'^Ar\s+enas', 'Arenas', desc, flags=re.I)
        desc = re.sub(r'^G\s+ravas', 'Gravas', desc, flags=re.I)
        horizon.material = material(desc)
    daily_pages = 0
    for page,text in enumerate(pages,1):
        plain = normalized(text)
        if 'informe diario de terreno' not in plain or 'avance y muestreo en suelo' not in plain:
            continue
        daily_pages += 1
        report.pages[str(page)] = {'text':text,'image_png':''}
        ids = re.findall(r'\bSondaje\s+S\s*[-–]\s*(\d+)\b', text, re.I)
        if len(ids)!=1 or int(ids[0])!=identifier:
            hole.extraction_errors.append(f'Pág. {page}: el sondaje del parte diario no coincide con la cabecera. No se mezclaron los datos.')
            continue
        if 'rec. (cm)' not in plain or 'nf' not in plain or 'rec. (%' not in plain:
            hole.extraction_errors.append(f'Pág. {page}: columnas/unidades del parte diario no compatibles.')
            continue
        count = 0
        for line in text.splitlines():
            if not re.match(r'^\s*(HQ3\b|SPT\s*N)',line,re.I):
                continue
            match = SAMPLE.fullmatch(line.strip())
            # TXT may have observations on the same line. PDF observations are
            # linked by table cells below: extraction order is NOT row order.
            parts = re.split(r'(?<=%)\s+', match[5], maxsplit=1) if match else []
            values = parts[0].split() if parts else []
            description = parts[1].strip() if len(parts) == 2 else ''
            spt = bool(match and match[2])
            valid = (len(values)==(7 if spt else 3) and
                     re.fullmatch(r'\d+',values[-3]) and re.fullmatch(NUM,values[-2]) and re.fullmatch(NUM+'%',values[-1]))
            if spt and valid:
                valid = all(re.fullmatch(r'(?:'+NUM+r'|R|-)',v,re.I) for v in values[:4]) and values[3] != '-'
            if not match or not valid:
                hole.extraction_errors.append(f'Pág. {page}: fila de muestreo no reconocida: {line.strip()}')
                continue
            method,index,a,b,_ = match.groups()
            sample = Sample(int(values[-3]),a,b,method,values[-2],values[-1][:-1],page,description)
            hole.samples.append(sample);count += 1
            if spt:
                n1,n2,n3,nf = values[:4]
                hole.tests.append(Spt(int(index),a,b,'',sample.recovered,n1,n2,n3,nf,page,'cm'))
        if not count:
            hole.extraction_errors.append(f'Pág. {page}: parte diario sin filas reconocidas.')
    if not daily_pages:
        hole.extraction_errors.append('No se encontraron partes diarios con SPT y recuperación.')
    if [r.index for r in hole.tests] != list(range(1,len(hole.tests)+1)):
        hole.extraction_errors.append('Numeración SPT incompleta, duplicada o fuera de orden.')
    # The annex sheet is rasterized: retain it as evidence, never digitize its curve.
    for i,text in enumerate(pages[:-1]):
        if 'anexo c' in normalized(text) and 'perfil estratigrafico' in normalized(text):
            report.pages[str(i+2)] = {'text':pages[i+1],'image_png':''}
            hole.warnings.append(f'Perfil gráfico en pág. {i+2}: cotejar con los partes diarios. Los símbolos R se conservan como rechazo y los NF no se limitan al máximo del eje gráfico.')
    hole.warnings = hole.audit()
    report.notices = [
        'Horizontes: tabla PERFIL ESTRATIGRÁFICO. Recuperación y NF/NSPT: partes diarios. Se conservan como fuentes independientes.',
        'Longitud recuperada en cm, recuperación en %, profundidades en m. No se recalculan los NF ni se asigna un número a R (rechazo).',
        'Los hatch siguen los horizontes, no las pasadas HQ3/SPT. Cotejar la asignación con la descripción; no se deduce del código USCS.',
        'La imagen del Anexo C se conserva como evidencia; no reemplaza los valores de las tablas. No se inventan velocidades Vs.'
    ]
    return report


def match_sample_descriptions(hole, page, rows):
    """Join observations only after the complete numeric row matches its source."""
    from sincal.prospecciones import number
    candidates = {}
    for row in rows:
        if len(row) < 11 or not re.fullmatch(r'(?:HQ3|SPT\s*N[º°o.]?\s*\d+)', row[0] or '', re.I):
            continue
        try:
            sample = next(s for s in hole.samples if s.page == page and s.index == int(row[7]))
            if normalized(row[0]) != normalized(sample.method):
                continue
            if any(number(a) != number(b) for a,b in zip(
                    (row[1],row[2],row[8],(row[9] or '').replace('%','')),
                    (sample.start,sample.end,sample.recovered,sample.recovery))):
                continue
            if sample.method.upper().startswith('SPT'):
                index = int(re.search(r'\d+', sample.method)[0])
                test = next(t for t in hole.tests if t.index == index and t.page == page)
                if [v.strip() for v in row[3:7]] != [test.n1,test.n2,test.n3,test.nspt]:
                    continue
            description = ' '.join((row[10] or '').split())
            # Extra populated cells signal an unexpected table structure.
            if description and not any(row[11:]):
                candidates.setdefault(sample.index, []).append(description)
        except (ValueError, TypeError, StopIteration, AttributeError):
            continue
    for sample in hole.samples:
        if sample.page == page:
            descriptions = candidates.get(sample.index, [])
            if len(descriptions) == 1:
                sample.description = descriptions[0]
            else:
                sample.description = ''
                hole.warnings.append(f'Muestra {sample.index}, pág. {page}: descripción ausente o ambigua; cotejar la página original.')


def attach_sample_descriptions(report, data, *, check):
    from io import BytesIO
    import pdfplumber
    with pdfplumber.open(BytesIO(data)) as document:
        for hole in report.boreholes:
            for page in sorted({s.page for s in hole.samples}):
                check()
                rows = [row for table in document.pages[page-1].extract_tables() for row in table]
                match_sample_descriptions(hole, page, rows)
            hole.warnings = hole.audit()
