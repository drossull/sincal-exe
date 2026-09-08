import unittest
from pathlib import Path

from sincal.cad.commands import normalizar_comando_cad_autonomo


ROOT = Path(__file__).resolve().parents[1]


class LiveCommandValidationTests(unittest.TestCase):
    def test_accepts_single_autonomous_command_names(self):
        for value in ("BV", "PLOTYA", "SETUP-A1", "_QSAVE", ".ZE", "STO", "VPTOGGLE"):
            with self.subTest(value=value):
                self.assertEqual(normalizar_comando_cad_autonomo(value), value)

    def test_trims_surrounding_whitespace(self):
        self.assertEqual(normalizar_comando_cad_autonomo("  ZE  "), "ZE")

    def test_rejects_parameters_multiline_and_lisp_expressions(self):
        for value in ("", "ZOOM E", "ZE\n_QSAVE", '(command "_.zoom" "_e")'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalizar_comando_cad_autonomo(value)

    def test_vptoggle_is_autonomous_and_handles_the_current_layer(self):
        source = (ROOT / "lisps" / "VPTOGGLE.lsp").read_text(encoding="utf-8")
        self.assertIn('(defun c:VPTOGGLE', source)
        self.assertIn('(setq layerName "Viewport layer")', source)
        self.assertIn("'vla-put-LayerOn (list layerObj :vlax-false)", source)
        self.assertIn("'vla-put-LayerOn (list layerObj :vlax-true)", source)
        self.assertIn('(setvar "CLAYER" "0")', source)


if __name__ == "__main__":
    unittest.main()
