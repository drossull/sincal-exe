"""Opt-in regression: different bootstrap/viewports, never original writes."""
import os
from pathlib import Path
import shutil
import sys

import pytest
from sincal.cad.dwgprops import CadBatch, autocad_engines

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from inspect_viewport_copies import inspect, digest


@pytest.mark.skipif(not all(os.environ.get(k) for k in ('SINCAL_TEST_VIEWPORT_DWG','SINCAL_TEST_VIEWPORT_BOOTSTRAP')),
                    reason='Requires explicit drawing pair; disposable copies only')
@pytest.mark.parametrize('year',[2025,2027])
def test_heterogeneous_batch_preserves_viewports(tmp_path,year):
    source=Path(os.environ['SINCAL_TEST_VIEWPORT_DWG'])
    bootstrap=Path(os.environ['SINCAL_TEST_VIEWPORT_BOOTSTRAP'])
    hashes=[digest(source),digest(bootstrap)]
    engine=next((e['id'] for e in autocad_engines() if e['year']==year),None)
    if engine is None: pytest.skip('CAD engine unavailable')
    before=inspect(source,tmp_path,'before')
    job=tmp_path/'job';directory=job/'file';directory.mkdir(parents=True)
    copy=directory/'copy.dwg';shutil.copy2(source,copy)
    batch=CadBatch(job,engine)
    try:
        batch._start(bootstrap)
        batch(copy,{'SINCAL_DIAGNOSTIC_TEMP':'temporary'},directory)
    finally:
        batch.close()
    after=inspect(copy,tmp_path,'after')
    assert after['viewports']==before['viewports']
    assert hashes==[digest(source),digest(bootstrap)]
