"""Regression guards for the three PURGEALL entry points."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PurgeAllTests(unittest.TestCase):
    def test_all_entry_points_delete_unused_scales_without_reset(self):
        for relative in ("lisps/PURGEALL.lsp", "scripts/PURGEALL.scr",
                         "scripts/PURGEALL.ps1"):
            with self.subTest(path=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                normalized = re.sub(r'["\s]+', ' ', source).upper()
                self.assertIn("_.-SCALELISTEDIT _DELETE * _EXIT", normalized)
                self.assertNotIn("_RESET", normalized)
                self.assertNotIn("DICTREMOVE", normalized)

    def test_lisp_restores_original_command_echo_on_success_and_error(self):
        source = (ROOT / "lisps/PURGEALL.lsp").read_text(encoding="utf-8")
        self.assertIn('(setq old-cmdecho (getvar "CMDECHO"))', source)
        self.assertIn('(defun *error* (msg)', source)
        self.assertEqual(source.count('(setvar "CMDECHO" old-cmdecho)'), 2)

    def test_cmd_script_keeps_scale_answers_on_separate_lines(self):
        source = (ROOT / "scripts/PURGEALL.ps1").read_text(encoding="utf-8")
        generated = re.search(r'\$scrContent = @"\n(.*?)\n"@', source, re.S).group(1)
        self.assertIn("_.-SCALELISTEDIT\n_Delete\n*\n_Exit\n", generated)
        self.assertNotIn("* _Exit", generated)
        self.assertIn("_.AUDIT\n_Y\n", generated)
        self.assertIn("_.QSAVE\n_.QUIT\n_Y", generated)
        self.assertIn('[guid]::NewGuid()', source)
        self.assertIn('finally {', source)

    def test_other_scr_command_answers_are_not_concatenated(self):
        # AutoLISP expressions intentionally stay on one line. Raw command
        # prompts must not combine a free-text response and the next option.
        for path in (ROOT / "scripts").glob("*.scr"):
            with self.subTest(script=path.name):
                source = path.read_text(encoding="utf-8")
                for line in source.splitlines():
                    if line.startswith("_"):
                        self.assertNotRegex(line, r"\s", path.name)
                self.assertTrue(source.endswith("\n"), path.name)


if __name__ == "__main__":
    unittest.main()
