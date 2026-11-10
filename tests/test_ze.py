from pathlib import Path
import unittest

from tests.test_csv_sc import balanced_lisp
from tools.export_distribution import discover_resources

ROOT = Path(__file__).resolve().parents[1]


class ZeTests(unittest.TestCase):
    def test_current_drawing_command_remains_autonomous(self):
        source = (ROOT / 'lisps/ZE.lsp').read_text(encoding='utf-8')
        balanced_lisp(source)
        current = source.split('(defun c:ZET', 1)[0]
        self.assertIn('(command "_.ZOOM" "_Extents")', current)
        self.assertNotIn('getkword', current)
        self.assertNotIn('getstring', current)

    def test_update_includes_lisp_and_worker(self):
        resources = discover_resources(ROOT)
        self.assertIn('lisps/ZE.lsp', resources)
        self.assertIn('scripts/ZE-TODOS.ps1', resources)


if __name__ == '__main__':
    unittest.main()
