"""Native-text GEOIBERICA ReMi tables. Never derive velocities from images."""
import re
from decimal import Decimal

from sincal.prospecciones import NUMBER, OFFICIAL, VsLayer, VsProfile, normalized


FIELDS = ('start','end','vs','thickness','density','poisson','shear','bulk','young')
ROW = re.compile(rf'^\s*({NUMBER})\s*[-–−]\s*({NUMBER})\s+' +
                 r'\s+'.join([rf'({NUMBER})']*7) + r'\s*$')
HEADING = re.compile(r'LOCALIZACI[OÓ]N\s*:\s*([^\n]+)', re.I)
PROFILE = re.compile(r'\bPERFIL\s+(\d+)\s+EN\s+SENTIDO\s+([NSEWO]{1,2})\s*[-–−]\s*([NSEWO]{1,2})\b', re.I)


def study_info(text):
    """Only explicit document fields; no company inference from file names."""
    info = {}
    if re.search(r'\bGEOIBERICA\s+SpA\b', text, re.I):
        info['company'] = 'GEOIBERICA SpA'
    else:
        match = re.search(r'^\s*(?:Empresa|Consultora|Raz[oó]n social)\s*:\s*([^\n]+)', text, re.I|re.M)
        if match: info['company'] = match[1].strip()
    if not info: return info
    for key, pattern in {
        'document':r'\bDocumento\s+([^\n]+)',
        'date':r'\bFecha\s+(\d{2}/\d{2}/\d{4})',
        'prepared_by':r'Elaborado por\s+([^\n]+)',
        'approved_by':r'Aprobado por\s+([^\n]+)',
        'email':r'([\w.+-]+@[\w.-]+?\.(?:com|cl|net|org))(?=\b|Celular)',
        'phone':r'Celular\s*:\s*([+\d][\d ()+-]+)',
        'website':r'\b(www\.[\w.-]+)',
        'address':r'GEOIBERICA\s+SpA\s*[-–]\s*([^\n]+)',
    }.items():
        match = re.search(pattern, text, re.I)
        if match: info[key] = match[1].strip()
    if re.search(r'ESTUDIO\s+GEOF[IÍ]SICO\s*[-–]\s*ReMi', text, re.I):
        info['method'] = 'ReMi'
    return info


def parse_table(text, page):
    plain = normalized(text)
    if not ('geoiberica' in plain and 'remi' in plain and 'profundidad' in plain
            and re.search(r'\bvs\s*\(m/s\)', plain) and 'espesor capa' in plain):
        return None
    headings = HEADING.findall(text)
    matches = [PROFILE.search(h) for h in headings]
    matches = [m for m in matches if m]
    errors, warnings, rows = [], [], []
    if len(matches) != 1:
        errors.append('Identificación de perfil ambigua o ausente; no se permite insertar.')
    for line in text.splitlines():
        if re.match(rf'^\s*{NUMBER}\s*[-–−]', line):
            match = ROW.fullmatch(line)
            if not match:
                errors.append('Fila incompleta o ambigua: '+line.strip())
                continue
            rows.append(dict(zip(FIELDS, match.groups())))
    if not rows:
        errors.append('No se extrajeron filas completas de la tabla GEOIBERICA.')
    for i,row in enumerate(rows,1):
        dec = lambda key: Decimal(row[key].replace(',','.'))
        difference = dec('end')-dec('start')
        if difference != dec('thickness'):
            warnings.append(f'Capa {i}: límites {row["start"]}–{row["end"]} m '
                            f'({difference} m); espesor publicado {row["thickness"]} m. '
                            'Se conservan ambos; el dibujo usa los límites publicados.')
    official = OFFICIAL.findall(text)
    if len(official)>1:
        errors.append('Varios valores Vs30 en una misma tabla; extracción ambigua.')
    name = f'Perfil {matches[0][1]} · {matches[0][2].upper()}–{matches[0][3].upper()}' if len(matches)==1 else f'Perfil sin identificar · p. {page}'
    return VsProfile(key=f'geoiberica-p{page}',name=name,page=page,
        layers=[VsLayer(i,r['start'],r['end'],r['vs']) for i,r in enumerate(rows,1)],
        official_vs30=official[0] if len(official)==1 else '',source_text=text,
        context=headings[0].strip() if len(headings)==1 else '',
        source_format='geoiberica-remi-v1',study_info={**study_info(text),'source_page':str(page)},
        documentary_rows=rows,extraction_errors=errors,extraction_warnings=warnings)


def compare_model_maxima(pages, profiles):
    """Compare a narrative maximum only within the same explicit study/profile."""
    current = None
    maxima = {}
    by_page = {p.page:p for p in profiles if p.source_format=='geoiberica-remi-v1'}
    for page,text in enumerate(pages,1):
        if 'geoiberica' not in normalized(text) or 'remi' not in normalized(text):
            current = None
            continue
        document = study_info(text).get('document','')
        heading = PROFILE.search(text)
        if heading:
            current = (document,heading[1],heading[2].upper(),heading[3].upper())
        if not current or current[0]!=document: continue
        maximum = re.search(rf'velocidades\s+m[áa]ximas\s+de\s+({NUMBER})\s*m/s',text,re.I)
        if maximum: maxima[current]=(maximum[1],page)
        profile = by_page.get(page)
        if profile and profile.layers and not profile.errors() and current in maxima:
            value,source_page = maxima[current]
            highest = max(profile.layers,key=lambda row:Decimal(row.vs.replace(',','.'))).vs
            if Decimal(value.replace(',','.'))!=Decimal(highest.replace(',','.')):
                profile.extraction_warnings.append(f'El modelo 2D se describe con máximo {value} m/s (p. {source_page}); '
                    f'la tabla publica un máximo de {highest} m/s (p. {page}). No se sustituyen valores entre fuentes.')
