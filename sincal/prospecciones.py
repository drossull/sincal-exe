"""Perfiles Vs documentales: extracción local, trazabilidad y comprobaciones.

Los importadores producen el mismo modelo; nunca sustituyen un valor oficial
por uno calculado. No se interpreta contenido del informe como instrucciones.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import math
from pathlib import Path
import re
import unicodedata


NUMBER = r"[+-]?\d+(?:[.,]\d+)*"
ROW = re.compile(rf"^\s*(\d+)\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})(?:\s+[IVX]+\s+[A-F])?\s*$")
ARRANGEMENT = re.compile(r"arreglo\s*(?:n[º°o.]?\s*)?([\w]+\s*[-–]\s*[\w]+)", re.I)
OFFICIAL = re.compile(rf"v\s*s\s*[, _]?\s*30\s*[:=]\s*({NUMBER})", re.I)


def number(value: str) -> float:
    value = str(value).strip()
    if ',' in value and '.' in value:
        decimal, thousands = (',', '.') if value.rfind(',') > value.rfind('.') else ('.', ',')
        value = value.replace(thousands, '').replace(decimal, '.')
    else:
        value = value.replace(',', '.')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("El informe contiene un número no finito.")
    return result


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower())
                   if not unicodedata.combining(c))


@dataclass(frozen=True)
class VsLayer:
    index: int
    start: str
    end: str
    vs: str


@dataclass
class VsProfile:
    key: str
    name: str
    page: int
    layers: list[VsLayer]
    official_vs30: str = ""
    source_text: str = ""
    references: list[dict] = field(default_factory=list)

    def errors(self) -> list[str]:
        errors = []
        previous = 0.0
        if not self.layers:
            return ["No se extrajeron estratos."]
        for i, layer in enumerate(self.layers, 1):
            try:
                start, end, vs = number(layer.start), number(layer.end), number(layer.vs)
                if layer.index != i:
                    errors.append(f"Numeración discontinua en el estrato {layer.index}.")
                if start < 0 or end <= start or vs <= 0:
                    errors.append(f"Valores no representables en el estrato {layer.index}.")
                if not math.isclose(start, previous, abs_tol=0.001):
                    errors.append(f"Hueco o solape antes del estrato {layer.index}.")
                previous = end
            except ValueError:
                errors.append(f"Número no interpretable en el estrato {layer.index}.")
        return errors

    def check_vs30(self) -> float | None:
        """Sólo control interno, con corte exacto a los primeros 30 m."""
        if self.errors() or number(self.layers[-1].end) < 30:
            return None
        travel_time = sum(max(0, min(30, number(row.end)) - number(row.start))
                          / number(row.vs) for row in self.layers)
        return 30 / travel_time

    def warnings(self) -> list[str]:
        warnings = list(self.errors())
        if not self.official_vs30:
            warnings.append("No se identificó el Vs,30 oficial; no se completará por cálculo.")
        calculated = self.check_vs30()
        if calculated is None:
            warnings.append("No se puede comprobar Vs,30 con los estratos extraídos.")
        elif self.official_vs30:
            # Margen para los redondeos de profundidades y velocidades publicados.
            if abs(calculated - number(self.official_vs30)) > max(1, calculated * .005):
                warnings.append(f"Vs,30 oficial: {self.official_vs30} m/s (p. {self.page}); "
                                f"control con estratos: {calculated:.2f} m/s. Se conserva el oficial.")
        for ref in self.references:
            if self.official_vs30 and abs(number(ref['value']) - number(self.official_vs30)) > .05:
                warnings.append(f"El resumen de la p. {ref['page']} publica {ref['value']} m/s; "
                                f"la tabla de la p. {self.page} publica {self.official_vs30} m/s.")
        return warnings


@dataclass
class VsReport:
    path: str
    sha256: str
    profiles: list[VsProfile]
    notices: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or not isinstance(data.get('profiles'), list):
            raise ValueError("Datos de Prospecciones no válidos.")
        profiles = []
        for item in data['profiles']:
            profile = VsProfile(
                key=str(item['key']), name=str(item['name']), page=int(item['page']),
                layers=[VsLayer(int(r['index']), str(r['start']), str(r['end']), str(r['vs']))
                        for r in item['layers']],
                official_vs30=str(item.get('official_vs30', '')),
                source_text=str(item.get('source_text', '')),
                references=list(item.get('references', [])),
            )
            if profile.official_vs30:
                number(profile.official_vs30)
            for ref in profile.references:
                number(ref['value'])
                int(ref['page'])
            profiles.append(profile)
        if len({p.key for p in profiles}) != len(profiles):
            raise ValueError("Identificadores de arreglos duplicados en la sesión.")
        return cls(str(data.get('path', '')), str(data.get('sha256', '')), profiles,
                   list(map(str, data.get('notices', []))))


def parse_pages(pages: list[str], path="", sha256="") -> VsReport:
    """Tablas con N°, Inicio/Desde, Final/Hasta y Vs; coma o punto decimal.

    Se conservan por separado las tablas repetidas y su página. Las tablas de
    resumen se contrastan por sus estratos, nunca por su posición en el PDF.
    """
    profiles, notices = [], []
    pending = None
    for page_index, text in enumerate(pages, 1):
        plain = normalized(text)
        if 'resumen' in plain and 'resultado' in plain:
            continue
        matches = list(ARRANGEMENT.finditer(text))
        if matches:
            pending = (re.sub(r'\s+', '', matches[-1][1]).replace('–', '-'), page_index)
        if not re.search(r'\bvs\b', plain) or not (
            re.search(r'\b(inicio|desde)\b', plain) and re.search(r'\b(final|hasta|fin)\b', plain)
        ):
            continue
        rows = []
        for line in text.splitlines():
            match = ROW.fullmatch(line)
            if match:
                rows.append(VsLayer(int(match[1]), match[2], match[3], match[4]))
        if not rows:
            notices.append(f"Página {page_index}: tabla Vs no reconocida; revisar el PDF.")
            continue
        # Una página con varios bloques requiere otro adaptador, no mezclarlos.
        if sum(row.index == 1 for row in rows) > 1:
            notices.append(f"Página {page_index}: varios bloques de estratos; extracción ambigua.")
            continue
        official = OFFICIAL.search(text)
        arrangement = pending[0] if pending and page_index - pending[1] <= 1 else None
        name = f"Arreglo {arrangement}" if arrangement else f"Perfil Vs · página {page_index}"
        profiles.append(VsProfile(
            key=f"p{page_index}-{arrangement or 'vs'}", name=name, page=page_index,
            layers=rows, official_vs30=official[1] if official else '', source_text=text,
        ))
    if not profiles:
        raise ValueError("No se reconocieron tablas de estratos Vs. Esta versión admite PDF con "
                         "texto o TXT con columnas N°, Inicio, Final y Vs. Los escaneos y otras "
                         "disposiciones necesitan un importador adicional; no se estiman valores desde la imagen.")
    return VsReport(path, sha256, profiles, notices)


def compare_summary(report: VsReport, text: str, page: int):
    """Lee resúmenes diagramados con clases opcionales y Vs30 en celda combinada."""
    pattern = re.compile(rf"(?:^|\s)(\d+)\s+({NUMBER})\s+({NUMBER})\s+({NUMBER})"
                         rf"\s+[IVX]+\s+[A-F](?:\s+({NUMBER}))?\s*$")
    groups, rows, value = [], [], ''
    for line in text.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        if int(match[1]) == 1 and rows:
            groups.append((rows, value))
            rows, value = [], ''
        rows.append(VsLayer(int(match[1]), match[2], match[3], match[4]))
        if match[5]:
            value = match[5]
    if rows:
        groups.append((rows, value))

    def signature(layers):
        return [(r.index, number(r.start), number(r.end), number(r.vs)) for r in layers]

    for rows, value in groups:
        if value:
            matching = [p for p in report.profiles if signature(p.layers) == signature(rows)]
            if len(matching) == 1:
                matching[0].references.append({'page': page, 'value': value})


def read_report(path: str) -> VsReport:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in ('.pdf', '.txt'):
        raise ValueError("Formato no admitido todavía. Selecciona un PDF o TXT.")
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if suffix == '.txt':
        return parse_pages(raw.decode('utf-8-sig').split('\f'), str(source), digest)
    from io import BytesIO
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(raw))
    if reader.is_encrypted and not reader.decrypt(''):
        raise ValueError("El PDF está protegido con contraseña.")
    pages = [page.extract_text() or '' for page in reader.pages]
    report = parse_pages(pages, str(source), digest)
    for i, text in enumerate(pages):
        plain = normalized(text)
        if 'resumen' in plain and 'resultado' in plain and 'vs' in plain:
            compare_summary(report, reader.pages[i].extract_text(extraction_mode='layout'), i + 1)
    empty = [str(i + 1) for i, text in enumerate(pages) if len(text.strip()) < 20]
    if empty:
        report.notices.append("Páginas sin texto suficiente (no se aplica OCR): " + ', '.join(empty))
    return report
