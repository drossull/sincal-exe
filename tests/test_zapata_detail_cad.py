import re
import unittest

from sincal_rebar_model import Cover, ZapataGeometry, build_zapata_schedule, default_zapata_rules
from sincal_zapata_detail_cad import build_zapata_detail_lisp


class ZapataDetailCadTests(unittest.TestCase):
    def setUp(self):
        self.geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, 7)
        self.cover = Cover.from_centimetres(7.5, 5, 5)
        self.rules = default_zapata_rules()
        self.schedule = build_zapata_schedule(self.geometry, self.cover, self.rules)
        self.lisp = build_zapata_detail_lisp(
            self.schedule, self.rules, self.geometry, "entrada", r"C:\SINCAL\master.dwg")

    def test_builds_logical_versioned_blocks_and_xdata(self):
        self.assertIn("SINCAL_ZAP_ENTRADA_G12_", self.lisp)
        self.assertIn("SINCAL_ZAP_ENTRADA_G45_", self.lisp)
        self.assertIn("SINCAL_DETAIL|ENTRADA|G12|", self.lisp)
        self.assertIn("defun sincal:find-detail", self.lisp)
        self.assertIn("defun sincal:create-detail-block", self.lisp)
        self.assertIn("defun sincal:planned-block-p", self.lisp)
        self.assertIn("vla-CopyObjects (list doc objects block)", self.lisp)
        self.assertNotIn('command "_.-BLOCK"', self.lisp)

    def test_prompts_before_replacing_changed_groups(self):
        self.assertIn("[Actualizar/Conservar/Todas/Cancelar]", self.lisp)
        self.assertIn("Actualizacion cancelada; no se reemplazo ningun detalle", self.lisp)
        self.assertIn("defun sincal:apply-plan", self.lisp)

    def test_uses_approved_styles_mark_and_description(self):
        self.assertIn('"GSG_ARM-COTAS"', self.lisp)
        self.assertIn('"<>\\\\XALTERNADO"', repr(self.lisp))
        self.assertIn('"MARK" 1.0 1.0 1.0', self.lisp)
        self.assertIn('(vla-get-TagString attribute)) "MARCA"', self.lisp)
        self.assertIn('vla-put-StyleName text "RomanD"', self.lisp)
        self.assertIn('vla-put-Height text 0.0025', self.lisp)
        self.assertIn('%%c22 @20 L=1200', self.lisp)
        self.assertIn("vl-catch-all-apply 'getvar (list \"CANNOSCALEVALUE\")", self.lisp)

    def test_lisp_parentheses_are_balanced(self):
        without_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', self.lisp)
        self.assertEqual(without_strings.count("("), without_strings.count(")"))


if __name__ == "__main__":
    unittest.main()
