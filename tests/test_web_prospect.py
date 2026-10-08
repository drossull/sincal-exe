"""Exercise the web job -> real PDF reader boundary, not a mocked read_report."""
import time

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from sincal.web.services import Services
from test_prospecciones import PAGE


def make_pdf(path):
    writer = PdfWriter()
    page = writer.add_blank_page(600, 800)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    lines = ['BT /F1 12 Tf 20 760 Td 16 TL']
    for line in PAGE.splitlines():
        escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        lines.append(f'({escaped}) Tj T*')
    stream.set_data(('\n'.join(lines) + '\nET').encode('latin-1'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.write(path)


@pytest.mark.parametrize('cancel_during_read', [False, True])
def test_pdf_job_and_cancellation(tmp_path, monkeypatch, cancel_during_read):
    path = tmp_path / 'synthetic-ims.pdf'
    make_pdf(path)
    original = path.read_bytes()
    service = Services(tmp_path / 'service')
    grant = service.files.grant(path, 'report')
    if cancel_during_read:
        from pypdf._page import PageObject
        extract = PageObject.extract_text
        def cancelling_extract(page, *args, **kwargs):
            for job in service.jobs.items.values():
                job.cancelled.set()
            return extract(page, *args, **kwargs)
        monkeypatch.setattr(PageObject, 'extract_text', cancelling_extract)
    try:
        key = service.jobs.submit('prospect', lambda job: service.prospect(job, {'file': grant['id']}))['id']
        deadline = time.monotonic() + 15
        job = service.jobs.get(key)
        while job.state in ('queued', 'running') and time.monotonic() < deadline:
            time.sleep(.01)
        assert job.state == ('cancelled' if cancel_during_read else 'completed'), job.message
        if not cancel_during_read:
            assert len(job.result['report']['profiles']) == 1
            assert len(job.result['report']['profiles'][0]['layers']) == 7
        assert path.read_bytes() == original
        assert 'is_set' not in job.path.read_text(encoding='utf-8')
    finally:
        service.jobs.close()
