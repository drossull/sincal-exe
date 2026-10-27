from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_csv_sc import balanced_lisp
from tools.export_distribution import discover_resources

ROOT = Path(__file__).resolve().parents[1]


class Of2Tests(unittest.TestCase):
    def test_lisp_syntax(self):
        for path in ('lisps/OF2.lsp', 'tests/cad/of2_regression.lsp'):
            balanced_lisp((ROOT / path).read_text(encoding='utf-8'))

    def test_published_and_loaded_after_resource_update(self):
        from sincal.resources import write_cad_loaders
        self.assertIn('lisps/OF2.lsp', discover_resources(ROOT))
        with tempfile.TemporaryDirectory() as folder:
            with patch('sincal.resources.ruta_cad_usuario',
                       side_effect=lambda *parts: str(Path(folder).joinpath(*parts))):
                write_cad_loaders(['lisps/OF2.lsp'])
            for loader in ('acaddoc.lsp', 'zwcaddoc.lsp'):
                self.assertIn('/lisps/OF2.lsp', (Path(folder) / loader).read_text())
