from pathlib import Path
import unittest

from tests.test_csv_sc import balanced_lisp

ROOT = Path(__file__).resolve().parents[1]


class UpdateBlockTests(unittest.TestCase):
    def test_lisp_syntax(self):
        for relative in ('lisps/UPDATEBLOCK.lsp', 'tests/cad/updateblock_regression.lsp'):
            balanced_lisp((ROOT / relative).read_text(encoding='utf-8'))

    def test_distribution_and_eager_loading(self):
        import tempfile
        from unittest.mock import patch
        from tools.export_distribution import discover_resources
        from sincal.resources import write_cad_loaders
        self.assertIn('lisps/UPDATEBLOCK.lsp', discover_resources(ROOT))
        with tempfile.TemporaryDirectory() as folder:
            with patch('sincal.resources.ruta_cad_usuario',
                       side_effect=lambda *p: str(Path(folder).joinpath(*p))):
                write_cad_loaders(['lisps/UPDATEBLOCK.lsp'])
            for loader in ('acaddoc.lsp', 'zwcaddoc.lsp'):
                self.assertIn('/lisps/UPDATEBLOCK.lsp', (Path(folder) / loader).read_text())


if __name__ == '__main__':
    unittest.main()
