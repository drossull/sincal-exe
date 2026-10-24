import unittest

from sincal.cad.armaduras_workflow import (
    build_moldaje_scan_lisp,
    build_prepare_layers_lisp,
)
from sincal.cad.moldajes import MoldajeContext


class ArmadurasWorkflowCadTests(unittest.TestCase):
    def test_prepare_layers_is_idempotent_and_preserves_existing_layers(self):
        lisp = build_prepare_layers_lisp(("FR_ZAP", "AA_ZAP", "FR_ZAP"))
        self.assertIn('(tblsearch "LAYER" name)', lisp)
        self.assertIn('(vla-Add collection name)', lisp)
        self.assertEqual(lisp.count('"FR_ZAP"'), 1)
        self.assertIn('"AA_ZAP"', lisp)

    def test_scan_supports_global_and_contextual_selection(self):
        global_lisp = build_moldaje_scan_lisp(
            r"C:\\tmp\\moldajes.txt", ("FR_MFR", "AA_MFR"),
        )
        contextual = build_moldaje_scan_lisp(
            r"C:\\tmp\\moldajes.txt", ("FR_MFR",),
            context=MoldajeContext("abutment.front_wall", "entrada"),
            interactive=True,
        )
        self.assertIn('ssget "_X"', global_lisp)
        self.assertIn('(cons 8 "FR_MFR,AA_MFR")', global_lisp)
        self.assertIn("Seleccione los moldajes del elemento", contextual)
        self.assertIn("META|ELEMENT|abutment.front_wall", contextual)
        self.assertIn("META|INSTANCE|entrada", contextual)
        self.assertIn("GEOMETRY|", contextual)
        self.assertIn("BULGES|", contextual)
        self.assertIn("LWPOLYLINE,POLYLINE", contextual)
        self.assertIn("sincal:supported-poly-p", contextual)
        self.assertIn("(logand (if flags flags 0) 88)", contextual)
        self.assertLess(
            contextual.index("(setq ss"),
            contextual.index('(setq out (open tmp-path'),
            "El archivo de resultado no debe existir mientras el dibujante selecciona.",
        )
        self.assertIn('moldajes.txt.part', contextual)
        self.assertLess(contextual.index("(close out)"), contextual.index("(vl-file-rename"))

    def test_rejects_unsafe_or_empty_layer_names(self):
        with self.assertRaises(ValueError):
            build_prepare_layers_lisp(())
        with self.assertRaises(ValueError):
            build_prepare_layers_lisp(('FR_ZAP") (alert "x',))


if __name__ == "__main__":
    unittest.main()
