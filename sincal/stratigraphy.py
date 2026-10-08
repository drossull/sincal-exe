"""Borehole records: published intervals, recovery and SPT are distinct data.

The VISAN summary adapter reads tables, never digitizes curves or recalculates
official numbers. Unrecognized reports fail closed, rather than inventing soil.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from pathlib import Path
import re

from sincal.prospecciones import normalized, number
from sincal.prospecciones_ocr import ImportCancelled, evidence_png
from sincal.stratigraphy_hatches import HATCHES

NUM = r'\d+(?:[.,]\d+)?'
DRILL = re.compile(rf'^\s*({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+(.+)$')
SPT = re.compile(rf'^\s*(\d+)\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+(.+)$')
MATERIALS = (*HATCHES, 'sin_asignar')


def material(description):
    text = normalized(re.sub(r'^SPT\s*N[º°o.]?\s*\d+\s*:\s*', '', description, flags=re.I))
    if 'hormigon' in text:
        return 'hormigon'
    if text.startswith('suelo vegetal'):
        return 'vegetal'
    for word in MATERIALS[:-1]:
        if text.startswith(word):
            return word
    return 'sin_asignar'


@dataclass
class Interval:
    start: str
    end: str
    drilled: str
    recovered: str
    recovery: str
    description: str
    page: int
    material: str = 'sin_asignar'

    @property
    def inclusions(self):
        """Explicit inclusions only; no soil classification or inferred amounts."""
        text = normalized(self.description)
        return [name for name, term in [('bolones', r'\bbolon(?:es)?\b'), ('bloque', r'\bbloques?\b'),
                                       ('clastos', r'\bclastos?\b'), ('cementacion', r'\bcementacion\b')]
                if name != self.material and re.search(term, text)]


@dataclass
class Spt:
    index: int
    start: str
    end: str
    driven: str
    recovered: str
    n1: str
    n2: str
    n3: str
    nspt: str
    page: int

    @property
    def refusal(self):
        return self.nspt.upper().startswith('R')


@dataclass
class VsBand:
    start: str
    end: str
    low: str
    high: str
    page: int
    profile: str
    table_page: int

    @property
    def label(self):
        value = self.low if self.low == self.high else f'{self.low} - {self.high}'
        return f'Vs = {value} m/s'


@dataclass
class Borehole:
    key: str
    name: str
    intervals: list[Interval] = field(default_factory=list)
    tests: list[Spt] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extraction_errors: list[str] = field(default_factory=list)
    reviewed: bool = False
    method: str = 'text'
    vs_bands: list[VsBand] = field(default_factory=list)

    def errors(self):
        result = list(self.extraction_errors)
        if not self.intervals:
            result.append('No se reconocieron intervalos de perforación.')
        if not self.tests:
            result.append('No se reconoció la tabla NSPT; no se deduce de la recuperación.')
        previous = 0.0
        for i, row in enumerate(self.intervals, 1):
            try:
                a, b, drilled, recovered, recovery = map(number, (row.start, row.end, row.drilled, row.recovered, row.recovery))
                if not 0 <= a <= b <= 1000 or drilled < 0 or recovered < 0 or not 0 <= recovery <= 100:
                    raise ValueError()
                if abs(a - previous) > .011:
                    result.append(f'Intervalo {i}: vacío o solapamiento a {row.start} m; revisar fuente.')
                previous = b
                if b > a and row.material not in MATERIALS[:-1]:
                    result.append(f'Intervalo {i}: confirma el material y su hatch.')
            except (ValueError, TypeError):
                result.append(f'Intervalo {i}: magnitudes no válidas.')
        if previous <= 0:
            result.append('El sondaje debe tener profundidad positiva.')
        vs_previous = 0.0
        for band in self.vs_bands:
            try:
                a, b, lo, hi = map(number, (band.start, band.end, band.low, band.high))
                if not 0 <= a < b <= 1000 or not 0 < lo <= hi <= 20000 or abs(a-vs_previous) > .001:
                    raise ValueError()
                vs_previous = b
            except (ValueError, TypeError):
                result.append('Tramos Vs no válidos, discontinuos o solapados.')
        seen = set()
        for row in self.tests:
            try:
                if type(row.index) is not int or row.index < 1 or row.index in seen or not 0 <= number(row.start) <= number(row.end) <= previous + .011:
                    raise ValueError()
                seen.add(row.index)
                if row.refusal:
                    if not re.fullmatch(r'R\s*:?\s*N[123]', row.nspt, re.I):
                        raise ValueError()
                elif not 0 <= number(row.nspt) <= 1000:
                    raise ValueError()
            except (ValueError, TypeError):
                result.append(f'SPT {row.index}: profundidad, rechazo o NSPT no válido.')
        return list(dict.fromkeys(result))

    def audit(self):
        """Diagnostics only: keep published numbers, including discrepancies."""
        warnings = list(self.warnings)
        for row in self.intervals:
            a, b, drilled, recovered, pct = map(number, (row.start, row.end, row.drilled, row.recovered, row.recovery))
            if abs(b-a-drilled) > .011:
                warnings.append(f'Pág. {row.page}, {row.start}–{row.end} m: espesor y perforado no coinciden.')
            if drilled > 0 and abs(100*recovered/drilled-pct) > 1.01:
                warnings.append(f'Pág. {row.page}, {row.start}–{row.end} m: recuperación publicada {row.recovery}% difiere del cociente. No se corrigió.')
            match = re.search(r'SPT\s*N[º°o.]?\s*(\d+)', row.description, re.I)
            if match:
                test = next((t for t in self.tests if t.index == int(match[1])), None)
                if test and (abs(number(test.start)-a) > .011 or abs(number(test.end)-b) > .011):
                    warnings.append(f'SPT {test.index}: perforación pág. {row.page}: {row.start}–{row.end} m; tabla SPT pág. {test.page}: {test.start}–{test.end} m. Se conservan ambas fuentes.')
        return list(dict.fromkeys(warnings))


@dataclass
class StratigraphyReport:
    source: str
    sha256: str
    boreholes: list[Borehole] = field(default_factory=list)
    pages: dict = field(default_factory=dict)
    notices: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        def strings(items):
            if not isinstance(items, list) or len(items) > 2000 or any(not isinstance(s, str) or len(s) > 5000 for s in items):
                raise ValueError('Lista de avisos no válida.')
            return list(items)

        if not isinstance(value, dict) or not isinstance(value.get('boreholes'), list) or len(value['boreholes']) > 200:
            raise ValueError('Informe de estratigrafía no válido.')
        report = cls(str(value.get('source', ''))[:2000], str(value.get('sha256', ''))[:64],
                     pages=value.get('pages', {}), notices=strings(value.get('notices', [])))
        if not isinstance(report.pages, dict) or len(report.pages) > 500:
            raise ValueError('Evidencia no válida.')
        for page, evidence in report.pages.items():
            if not str(page).isdigit() or not 1 <= int(page) <= 2000 or not isinstance(evidence, dict):
                raise ValueError('Página de evidencia no válida.')
            for attr, limit in [('text', 200000), ('image_png', 12000000)]:
                field_value = evidence.get(attr, '')
                if not isinstance(field_value, str) or len(field_value) > limit:
                    raise ValueError('Contenido de evidencia no válido.')
        keys = set()
        for item in value['boreholes']:
            if not isinstance(item, dict) or not isinstance(item.get('intervals'), list) or not isinstance(item.get('tests'), list):
                raise ValueError('Sondaje no válido.')
            if len(item['intervals']) > 2000 or len(item['tests']) > 2000:
                raise ValueError('Demasiadas filas en un sondaje.')
            try:
                hole = Borehole(str(item['key']), str(item['name']),
                                [Interval(**r) for r in item['intervals']], [Spt(**r) for r in item['tests']],
                                strings(item.get('warnings', [])), strings(item.get('extraction_errors', [])),
                                item.get('reviewed') is True, str(item.get('method', 'text')))
                bands = item.get('vs_bands', [])
                if not isinstance(bands, list) or len(bands) > 200:
                    raise ValueError('Tramos Vs no válidos.')
                hole.vs_bands = [VsBand(**row) for row in bands]
                for band in hole.vs_bands:
                    if any(not isinstance(getattr(band, name), str) or len(getattr(band, name)) > 200
                           for name in ('start', 'end', 'low', 'high', 'profile')):
                        raise ValueError('Valores Vs no válidos.')
                    if any(type(p) is not int or not 1 <= p <= 2000 for p in (band.page, band.table_page)):
                        raise ValueError('Páginas Vs no válidas.')
                for row in [*hole.intervals, *hole.tests]:
                    if type(row.page) is not int or not 1 <= row.page <= 2000:
                        raise ValueError('Página no válida.')
                    for attr, field_value in vars(row).items():
                        if attr not in ('page', 'index') and (not isinstance(field_value, str) or len(field_value) > 5000):
                            raise ValueError('Los valores publicados deben conservarse como texto.')
                    for attr in ('start', 'end', 'recovered'):
                        number(getattr(row, attr))
                if any(type(row.index) is not int or row.index < 1 for row in hole.tests):
                    raise ValueError('Número de ensayo no válido.')
                if hole.key in keys or not hole.key or len(hole.key) > 200 or len(hole.name) > 200:
                    raise ValueError('Identificador repetido o no válido.')
                keys.add(hole.key)
            except (TypeError, KeyError) as error:
                raise ValueError('Filas del sondaje no válidas.') from error
            report.boreholes.append(hole)
        return report


def parse_spt(line, page, daily=False):
    match = SPT.match(line)
    if not match:
        return None
    index, a, b, driven, recovered, tail = match.groups()
    values = tail.split()
    if len(values) == 4 and all(re.fullmatch(NUM, v) for v in values):
        n1, n2, n3, nspt = values
    elif 2 <= len(values) <= 4 and re.fullmatch(r'R:N[123]', values[-1], re.I):
        nspt = values[-1]
        n1, n2, n3 = (values[:-1] + ['']*3)[:3]
    else:
        return None
    # Daily logs have sample number instead of driven length in column 4.
    return Spt(int(index), a, b, '' if daily else driven, recovered, n1, n2, n3, nspt, page)


def parse_pages(pages, source='', sha256=''):
    report = StratigraphyReport(source, sha256)
    current = None
    mode = None
    for page, text in enumerate(pages, 1):
        plain = normalized(text)
        heading = re.search(r'(?:3\.1\s*\.?\s*[-.]\s*sondaje|sondaje\s+geotecnico[,\s]*)\s*[“"«]?\s*(S\s*[-–]\s*\d+)\b', text, re.I)
        if heading:
            name = re.sub(r'\s+', '', heading[1]).replace('–', '-').upper()
            if not current or current.name != name:
                current = Borehole(f'{name}-p{page}', name)
                report.boreholes.append(current)
            mode = None
        if not current:
            continue
        daily = 'informe diario de sondaje' in plain
        if daily:
            # Compare, never silently replace the official summary by a daily log.
            for line in text.splitlines():
                other = parse_spt(line, page, daily=True)
                if other:
                    official = next((r for r in current.tests if r.index == other.index), None)
                    if official and (official.start, official.end, official.nspt) != (other.start, other.end, other.nspt):
                        current.warnings.append(f'SPT {other.index}: tabla pág. {official.page}: {official.start}–{official.end} m / {official.nspt}; parte diario pág. {page}: {other.start}–{other.end} m / {other.nspt}. No se reemplazó la tabla.')
                        report.pages[str(page)] = {'text': text, 'image_png': ''}
            mode = None
            continue
        if re.search(r'tabla\s*n[º°o.]?\s*3\s*:', plain) and 'perforacion' in plain:
            mode = 'drill'
        elif 'listado de ensayos de penetracion estandar' in plain or (re.search(r'tabla\s*n[º°o.]?\s*4\s*:', plain) and 'ensayos de penetracion' in plain):
            mode = 'spt'
        elif any(word in plain for word in ('fotografias de cajas', 'informes de perforacion', 'tabla n°5')):
            mode = None
        before = (len(current.intervals), len(current.tests))
        last = None
        for line in text.splitlines():
            if mode == 'drill':
                match = DRILL.match(line)
                if match and re.search('[a-záéíóúñ]', match[6], re.I):
                    a, b, drilled, recovered, pct, description = match.groups()
                    last = Interval(a, b, drilled, recovered, pct, description.strip(), page, material(description))
                    current.intervals.append(last)
                elif last and line.strip() and not any(word in normalized(line) for word in ('estratigrafia del sondaje', 'profundidad descripcion', 'campana de')):
                    last.description += ' ' + line.strip()
            elif mode == 'spt':
                row = parse_spt(line, page)
                if row:
                    current.tests.append(row)
        if before != (len(current.intervals), len(current.tests)):
            report.pages[str(page)] = {'text': text, 'image_png': ''}
        if mode == 'spt':
            declared = re.search(r'se ejecutaron\s+(\d+)\s+ensayos', plain)
            if declared and int(declared[1]) != len(current.tests):
                current.warnings.append(f'Pág. {page}: el texto declara {declared[1]} ensayos, pero la tabla contiene {len(current.tests)}.')
            mode = None
    report.boreholes = [h for h in report.boreholes if h.intervals or h.tests]
    for hole in report.boreholes:
        hole.warnings = hole.audit()
    report.notices = [
        'Azul: recuperación (%) de la tabla de perforación. NSPT (golpes/pie) es una magnitud independiente. R indica rechazo, no un valor numérico.',
        'Estratos según la descripción del operador, por intervalo; confirma la asignación de hatch. No se extrapolan estratos a partir de Vs ni se copian límites estimados de figuras.',
        'Se priorizan las tablas resumen oficiales y se advierten diferencias con los partes diarios; las cifras originales no se corrigen.'
    ]
    return report


def read_report(path, *, progress=None, cancel=None):
    path = Path(path)
    if path.suffix.lower() not in ('.pdf', '.txt') or path.stat().st_size > 100*1024*1024:
        raise ValueError('Selecciona un PDF/TXT de hasta 100 MB.')
    def check():
        if cancel and cancel.is_set():
            raise ImportCancelled('Lectura cancelada; se conserva el informe anterior.')
    data = path.read_bytes()
    check()
    if path.suffix.lower() == '.txt':
        pages = data.decode('utf-8-sig').split('\f')
    else:
        from pypdf import PdfReader
        from io import BytesIO
        reader = PdfReader(BytesIO(data))
        if len(reader.pages) > 2000:
            raise ValueError('El informe supera 2000 páginas.')
        pages = []
        for index, page in enumerate(reader.pages, 1):
            check()
            if progress:
                progress(f'Leyendo estratigrafía: página {index}/{len(reader.pages)}')
            pages.append(page.extract_text() or '')
    report = parse_pages(pages, path.name, hashlib.sha256(data).hexdigest())
    if not report.boreholes:
        raise ValueError('No se reconocieron tablas de perforación/SPT del formato VISAN. No se estiman valores desde dibujos. Los escaneos sin texto y otros formatos requieren un adaptador de extracción.')
    check()
    if path.suffix.lower() == '.pdf':
        import pypdfium2 as pdfium
        from sincal.stratigraphy_vs import attach_vs_bands
        attach_vs_bands(report, data, pages, check=check)
        # Keep source pages (including the overview figure) available for review.
        for index, text in enumerate(pages, 1):
            if 'estratigraf' in normalized(text) and 'fig.' in normalized(text) and 'sondaje' in normalized(text):
                report.pages.setdefault(str(index), {'text': text, 'image_png': ''})
        with pdfium.PdfDocument(data) as document:
            for page, evidence in report.pages.items():
                check()
                if progress:
                    progress(f'Preparando evidencia: página {page}')
                original = document[int(page)-1]
                try:
                    bitmap = original.render(scale=min(2.5, 2200/max(original.get_size())))
                    try:
                        evidence['image_png'] = evidence_png(bitmap.to_pil())
                    finally:
                        bitmap.close()
                finally:
                    original.close()
    check()
    return report
