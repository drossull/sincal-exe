from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from tests.test_csv_sc import balanced_lisp

ROOT = Path(__file__).resolve().parents[1]


class RomanDTests(unittest.TestCase):
    def test_lisp_syntax(self):
        for path in ('lisps/ROMAND.lsp', 'tests/cad/romand_regression.lsp'):
            balanced_lisp((ROOT / path).read_text(encoding='utf-8'))

    def test_distribution_and_both_loaders(self):
        from tools.export_distribution import discover_resources
        from sincal.resources import write_cad_loaders
        self.assertIn('lisps/ROMAND.lsp', discover_resources(ROOT))
        with tempfile.TemporaryDirectory() as folder:
            with patch('sincal.resources.ruta_cad_usuario',
                       side_effect=lambda *parts: str(Path(folder).joinpath(*parts))):
                write_cad_loaders(['lisps/ROMAND.lsp'])
            for name in ('acaddoc.lsp', 'zwcaddoc.lsp'):
                self.assertIn('/lisps/ROMAND.lsp', (Path(folder) / name).read_text())

    def test_does_not_auto_run_or_save(self):
        source = (ROOT / 'lisps/ROMAND.lsp').read_text()
        self.assertEqual(source.count('(defun c:ROMAND'), 1)
        self.assertNotIn('(c:ROMAND)', source)
        self.assertNotIn('QSAVE', source)


if __name__ == '__main__':
    unittest.main()
