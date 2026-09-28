"""OCR conservador: localizar candidatos, transcribir celdas y conservar evidencia.

No contiene páginas, valores ni nombres de archivos particulares de Loreto.
Las tablas ambiguas no se completan y nunca se estiman cifras desde una curva.
"""
from __future__ import annotations

import base64
from io import BytesIO
import re
import statistics

from sincal.prospecciones import ARRANGEMENT, NUMBER, OFFICIAL, VsLayer, VsProfile, normalized, number


class ImportCancelled(Exception):
    pass


def contexts(pages):
    result = []
    structure = profile = ''
    arrangement = None
    for page, text in enumerate(pages, 1):
        # Header identifies the annex, not the coincident arrangement numbers.
        header = re.search(r'VS\s*[, ]?30\s*[-–:]\s*(P\s*-?\s*\d+)\b', text, re.I)
        if header:
            current = re.sub(r'[\s-]', '', header[1]).upper()
            if current != structure:
                profile, arrangement = '', None
            structure = current
        heading = re.search(r'^\s*\d+(?:\.\d+)+\.?\s+PERFIL\s+GEOF[IÍ]SICO\s*N[º°o.]?\s*(\d+)', text, re.I | re.M)
        if heading:
            profile = heading[1]
            arrangement = None
        matches = list(ARRANGEMENT.finditer(text))
        if matches:
            arrangement = (re.sub(r'\s+', '', matches[-1][1]).replace('–', '-'), page)
        name = arrangement[0] if arrangement and page - arrangement[1] <= 1 else ''
        result.append((structure, profile, name))
    return result


def identify(profile, context):
    structure, section, arrangement = context
    profile.context = ' · '.join(x for x in (structure, f'Perfil {section}' if section else '') if x)
    if arrangement:
        profile.name = f'Arreglo {arrangement}'
    if profile.context:
        profile.name = profile.context + ' · ' + profile.name
    if section and arrangement and arrangement.split('-')[0] != section:
        profile.extraction_warnings.append(
            f'El rótulo dice Arreglo {arrangement}, pero está dentro de la sección Perfil {section}. '
            'Se conservan ambos identificadores; confirmar con el informe.')


def enrich_context(report, pages):
    context = contexts(pages)
    for profile in report.profiles:
        identify(profile, context[profile.page - 1])


def parse_ocr(result):
    """Agrupa por coordenadas, sin referencia numérica ni correcciones heurísticas."""
    result = result.get('res', result)
    if not len(result['rec_texts']) == len(result['rec_scores']) == len(result['rec_boxes']):
        raise ValueError('Respuesta OCR incompleta: textos, confianzas y coordenadas no coinciden.')
    tokens = []
    for text, score, box in zip(result['rec_texts'], result['rec_scores'], result['rec_boxes']):
        tokens.append(dict(text=str(text).strip(), confidence=float(score), box=list(map(float, box)),
                           x=(box[0]+box[2])/2, y=(box[1]+box[3])/2, h=box[3]-box[1]))
    starts = [t for t in tokens if re.fullmatch(r'(inicio|desde)(\s*\[?m\]?)?', normalized(t['text']))]
    ends = [t for t in tokens if re.fullmatch(r'(final|hasta|fin)(\s*\[?m\]?)?', normalized(t['text']))]
    # No matching headers means this is a photo, logo, spectrum, etc., not a Vs table.
    if not starts or not ends or not any(re.search(r'\bvs\b', normalized(t['text'])) for t in tokens):
        return None
    errors, rows, cells, official = [], [], [], ''
    if len(starts) != 1 or len(ends) != 1:
        return dict(rows=[], official='', cells=[], tokens=tokens,
                    errors=['Varios bloques de tabla en una imagen: requieren revisión; no se mezclan.'])
    top = max(starts[0]['y'], ends[0]['y'])
    labels = [t for t in tokens if t['y'] > top and
              re.search(r'v\s*s\s*[, _]?\s*30', t['text'], re.I)]
    bottom = min((t['y'] + 2*t['h'] for t in labels), default=float('inf'))
    # Bound by the four column centers so page numbers and neighbouring plots
    # do not get mixed into the table when a whole scanned page is recognized.
    gap = ends[0]['x'] - starts[0]['x']
    left = starts[0]['x'] - 1.7*gap
    right = ends[0]['x'] + 1.7*gap
    if gap <= 0:
        return dict(rows=[], official='', cells=[], tokens=tokens,
                    errors=['Orden de columnas no reconocido.'])
    numeric = [t for t in tokens if top < t['y'] <= bottom and left <= t['x'] <= right
               and re.fullmatch(NUMBER, t['text'])]
    tolerance = statistics.median(t['h'] for t in numeric) * .42 if numeric else 5
    groups = []
    for token in sorted(numeric, key=lambda t: t['y']):
        if groups and abs(token['y'] - statistics.mean(t['y'] for t in groups[-1])) <= tolerance:
            groups[-1].append(token)
        else:
            groups.append([token])
    # A combined Vs30 label may contain the number; retain it verbatim.
    for token in tokens:
        match = OFFICIAL.search(token['text'])
        if match and top < token['y'] <= bottom:
            if official:
                errors.append('Más de un valor Vs30 reconocido.')
            official = match[1]
            cells.append(token)
    for group in groups:
        group.sort(key=lambda t: t['x'])
        texts = [t['text'] for t in group]
        if len(group) == 4 and re.fullmatch(r'\d+', texts[0]) and not official:
            rows.append(texts)
            cells.extend(group)
        elif len(group) == 4 and re.fullmatch(r'\d+', texts[0]) and any(OFFICIAL.search(t['text']) for t in tokens):
            rows.append(texts)
            cells.extend(group)
        elif len(group) == 1 and rows and number(texts[0]) > 30 and not official:
            # Require an explicit label near the number, not merely a footer number.
            labels = [t for t in tokens if re.search(r'v\s*s\s*[, _]?\s*30', t['text'], re.I)
                      and abs(t['y'] - group[0]['y']) <= max(t['h'], group[0]['h'])*2]
            if labels:
                official = texts[0]
                cells.extend(group)
            else:
                errors.append('Valor aislado sin rótulo Vs30: ' + texts[0])
        else:
            errors.append('Fila numérica ambigua: ' + ' | '.join(texts))
    if not rows:
        errors.append('No se pudieron reconstruir las filas de estratos.')
    return dict(rows=rows, official=official, errors=errors, cells=cells, tokens=tokens)


def candidate_page(text, exhaustive):
    plain = normalized(text)
    if 'resumen' in plain and 'resultado' in plain:
        return False
    return exhaustive or len(plain.strip()) < 100 or (
        bool(re.search(r'\bvs(?:\b|30)', plain)) and
        any(word in plain for word in ('estrato', 'perfil de suelo', 'velocidad de onda', 'onda de corte')))


def image_input(image):
    from PIL import ImageOps
    image = image.convert('RGB')
    image.thumbnail((2400, 3200))
    return ImageOps.expand(image, border=24, fill='white')


def evidence_png(image):
    # Exact input pixels, retained inside the session for review without the PDF.
    stream = BytesIO()
    image.save(stream, format='PNG')
    return base64.b64encode(stream.getvalue()).decode('ascii')


def extract_images(reader, pages, report, pdf_bytes, *, exhaustive=False, progress=None, cancel=None, engine_factory=None):
    from sincal.ocr_runtime import PaddleWorker
    context = contexts(pages)
    engine = None
    attempts = found = 0
    summary_skipped = 0
    has_vs_context = any(re.search(r'\bvs(?:\b|30)', normalized(text)) for text in pages)
    deferred_scans = 0

    def check_cancel():
        if cancel and cancel.is_set():
            raise ImportCancelled('Lectura cancelada; se conserva el informe anterior.')

    try:
        for page_number, (page, text) in enumerate(zip(reader.pages, pages), 1):
            check_cancel()
            if not exhaustive and has_vs_context and len(text.strip()) < 100:
                # A mixed IMS contains many scanned borehole/photos annexes. The
                # exhaustive option inspects these too, without guessing relevance.
                deferred_scans += 1
                continue
            if not candidate_page(text, exhaustive):
                continue
            if progress:
                progress(f'Buscando imágenes: página {page_number}/{len(pages)} · {found} tablas OCR')
            candidates = []
            try:
                for image in page.images:
                    bitmap = image.image
                    width, height = bitmap.size
                    # Exclude tiny headers and portrait plots on pages with native text.
                    if width < 200 or height < 100 or width / height > 7:
                        continue
                    if not exhaustive and len(text.strip()) >= 100 and width / height < 1.15:
                        continue
                    # Repeated letterhead is normally short and very wide.
                    if not exhaustive and len(text.strip()) >= 100 and height < 220 and width / height > 3:
                        continue
                    candidates.append((image.name, image_input(bitmap)))
                if not candidates and (len(text.strip()) < 100 or exhaustive):
                    import pypdfium2 as pdfium
                    with pdfium.PdfDocument(pdf_bytes) as document:
                        with document[page_number - 1] as rendered_page:
                            bitmap = rendered_page.render(scale=2.5)
                            try:
                                candidates.append(('página completa', image_input(bitmap.to_pil())))
                            finally:
                                bitmap.close()
            except Exception as error:
                report.notices.append(f'Página {page_number}: no se pudo preparar la imagen ({error}).')
                continue
            for index, (image_name, bitmap) in enumerate(candidates, 1):
                check_cancel()
                if progress:
                    progress(f'OCR: página {page_number}/{len(pages)}, imagen {index}/{len(candidates)} · {found} tablas')
                if engine is None:
                    engine = (engine_factory or PaddleWorker)(cancel=cancel)
                attempts += 1
                raw = engine.recognize(bitmap)
                check_cancel()
                parsed = parse_ocr(raw)
                if parsed is None:
                    continue
                recognized_text = '\n'.join(t['text'] for t in sorted(parsed['tokens'], key=lambda t: (t['y'], t['x'])))
                plain = normalized(recognized_text)
                if 'resumen' in plain and 'resultado' in plain:
                    summary_skipped += 1
                    continue
                layers = [VsLayer(int(r[0]), *r[1:]) for r in parsed['rows']]
                # Prefer native text on the same page, only if every value agrees.
                duplicate = next((p for p in report.profiles if p.page == page_number and
                                  p.layers == layers and p.official_vs30 == parsed['official']), None)
                if duplicate:
                    continue
                profile = VsProfile(f'p{page_number}-ocr-{index}', f'Perfil Vs · página {page_number}',
                    page_number, layers, parsed['official'], text + '\n\nOCR:\n' + recognized_text,
                    method='ocr', extraction_errors=parsed['errors'],
                    evidence={'image_png': evidence_png(bitmap), 'image_name': image_name,
                              'size': list(bitmap.size), 'cells': parsed['cells'],
                              'engine': 'PaddleOCR 3.7.0 / PP-OCRv6 medium'})
                page_context = context[page_number - 1]
                if not page_context[2]:
                    recognized_context = contexts([recognized_text])[0]
                    page_context = tuple(a or b for a, b in zip(page_context, recognized_context))
                identify(profile, page_context)
                doubtful = [t['text'] for t in parsed['cells'] if t['confidence'] < .98]
                if doubtful:
                    profile.extraction_warnings.append('Confianza OCR inferior al 98 %: ' + ', '.join(doubtful) +
                                                       '. Verificar cada cifra en el original.')
                report.profiles.append(profile)
                found += 1
        check_cancel()
        report.notices.append(f'OCR local: {attempts} imágenes examinadas, {found} tablas añadidas. '
                              'Los perfiles OCR requieren revisión antes de insertar; no se corrigen valores.')
        if summary_skipped:
            report.notices.append(f'{summary_skipped} resúmenes en imagen omitidos: revisar sus discrepancias en el PDF.')
        if not exhaustive:
            report.notices.append('Búsqueda OCR automática por contexto Vs y tamaño de imagen. '
                                  'Si faltan tablas, activa OCR en todas las páginas y vuelve a cargar.')
        if deferred_scans:
            report.notices.append(f'{deferred_scans} páginas sin contexto textual Vs pendientes del modo OCR en todas las páginas.')
    except ImportCancelled:
        raise
    except Exception as error:
        # Do not disguise an incomplete OCR run as a complete import.
        report.notices.append(f'OCR INCOMPLETO: {error}. Se conservan las tablas extraídas; faltan imágenes por revisar.')
        if not report.profiles:
            raise ValueError('\n'.join(report.notices)) from error
    finally:
        if engine is not None:
            engine.close()
