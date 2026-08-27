import unittest

from sincal.cad.commands import normalizar_comando_cad_autonomo


class LiveCommandValidationTests(unittest.TestCase):
    def test_accepts_single_autonomous_command_names(self):
        for value in ("BV", "PLOTYA", "SETUP-A1", "_QSAVE", ".ZE", "STO"):
            with self.subTest(value=value):
                self.assertEqual(normalizar_comando_cad_autonomo(value), value)

    def test_trims_surrounding_whitespace(self):
        self.assertEqual(normalizar_comando_cad_autonomo("  ZE  "), "ZE")

    def test_rejects_parameters_multiline_and_lisp_expressions(self):
        for value in ("", "ZOOM E", "ZE\n_QSAVE", '(command "_.zoom" "_e")'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalizar_comando_cad_autonomo(value)


if __name__ == "__main__":
    unittest.main()
