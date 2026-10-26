"""Keep the help catalog complete as new CAD commands are added."""
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from tests.test_csv_sc import balanced_lisp

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'lisps/SINCALISP.lsp'


class SincalispTests(unittest.TestCase):
    def test_catalog_covers_every_distributed_command_and_alias(self):
        source = SOURCE.read_text(encoding='utf-8')
        entries = re.findall(r'^    \("([^"\n]+)" "([^"\n]+)" "([^"\n]+)"\)', source, re.M)
        expected = {}
        for folder in ('lisps', 'startup'):
            for path in (ROOT / folder).glob('*.lsp'):
                text = path.read_text(encoding='utf-8', errors='replace')
                for command in re.findall(r'\(defun\s+c:([^\s()]+)', text, re.I):
                    expected[command.upper()] = path.relative_to(ROOT).as_posix()
        self.assertEqual(len(entries), len({row[0] for row in entries}), 'Duplicate commands')
        self.assertEqual({row[0]: row[2] for row in entries}, expected)
        for name, description, path in entries:
            self.assertGreater(len(description), 15, name)
            self.assertLessEqual(len(description), 180, name)
            self.assertTrue((ROOT / path).is_file())

    def test_syntax_and_read_only_dialog(self):
        source = SOURCE.read_text(encoding='utf-8')
        balanced_lisp(source)
        balanced_lisp((ROOT / 'tests/cad/sincalisp_regression.lsp').read_text())
        self.assertIn('(acad_strlsort', source)
        self.assertIn('start_dialog', source)
        self.assertIn('unload_dialog', source)
        self.assertIn('vl-file-delete path', source)
        for forbidden in ('(command ', '(command-s ', '(entmod ', '(entdel ', '(setvar ', '(load ', '(eval '):
            self.assertNotIn(forbidden, source)
        self.assertNotIn('(c:SINCALISP)', source)

    def test_hot_distribution_and_loaders(self):
        from tools.export_distribution import discover_resources
        from sincal.resources import write_cad_loaders
        self.assertIn('lisps/SINCALISP.lsp', discover_resources(ROOT))
        with tempfile.TemporaryDirectory() as folder:
            with patch('sincal.resources.ruta_cad_usuario',
                       side_effect=lambda *parts: str(Path(folder).joinpath(*parts))):
                write_cad_loaders(['lisps/SINCALISP.lsp'])
            for name in ('acaddoc.lsp', 'zwcaddoc.lsp'):
                self.assertIn('/lisps/SINCALISP.lsp', (Path(folder) / name).read_text())


if __name__ == '__main__':
    unittest.main()
