from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def balanced_lisp(source):
    depth, string, escape, comment = 0, False, False, False
    stack = []
    for line_number, line in enumerate(source.splitlines(), 1):
        comment = False
        for char in line:
            if comment:
                continue
            if string:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"':
                    string = False
            elif char == ';':
                comment = True
            elif char == '"':
                string = True
            elif char == '(':
                depth += 1
                stack.append(line_number)
            elif char == ')':
                depth -= 1
                assert depth >= 0, f'extra closing parenthesis, line {line_number}'
                stack.pop()
    assert depth == 0 and not string, f'unclosed form: lines={stack}, string={string}'


class CsvScTests(unittest.TestCase):
    def test_lisp_syntax(self):
        for path in (ROOT / 'lisps/CSV-SC.lsp', ROOT / 'tests/cad/csv_sc_regression.lsp'):
            balanced_lisp(path.read_text(encoding='utf-8'))

    def test_import_contract(self):
        source = (ROOT / 'lisps/CSV-SC.lsp').read_text(encoding='utf-8')
        for required in ('(defun c:CSV-SC', 'TENSIONES', 'vla-CopyObjects',
                         'vla-AddTable', 'vla-SetCellDataType', 'windows-1252',
                         'utf-8', 'vla-get-PaperSpace', 'vla-StartUndoMark',
                         'SCSV:ParseFixed', 'SCSV:FixedCells', '".XSR"'):
            self.assertIn(required, source)
        self.assertNotIn('vla-Save', source)

    def test_published_as_hot_resource(self):
        from tools.export_distribution import discover_resources
        self.assertIn('lisps/CSV-SC.lsp', discover_resources(ROOT))


if __name__ == '__main__':
    unittest.main()
