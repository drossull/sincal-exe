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


if __name__ == "__main__":
    unittest.main()
