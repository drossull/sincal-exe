import re
import unittest

from sincal.rebar.model import Cover, ZapataGeometry, build_zapata_schedule, default_zapata_rules
from sincal.cad.zapata_detail import build_zapata_detail_lisp


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

    def test_objectdbx_release_remains_inside_the_valid_if_branch(self):
        self.assertIn(
            "(vl-catch-all-apply 'vlax-release-object (list dbx))))))",
            self.lisp,
        )

    def test_detail_block_definitions_stay_in_metres_for_all_drawing_units(self):
        metre_definitions = [line for line in self.lisp.splitlines()
                             if '(entmakex (list (cons 0 "LWPOLYLINE")' in line]
        self.assertTrue(metre_definitions)
        for factor in (1, 100, 1000):
            with self.subTest(units_per_m=factor):
                source = build_zapata_detail_lisp(
                    self.schedule, self.rules, self.geometry, 'entrada', '',
                    drawing_units_per_m=factor)
                self.assertEqual(metre_definitions, [line for line in source.splitlines()
                    if '(entmakex (list (cons 0 "LWPOLYLINE")' in line])
                self.assertIn(f'block-name {factor} {factor} {factor} 0.0)', source)
                self.assertIn(f'(* slot {3 * factor})', source)
                self.assertIn(f'(+ (cadr ip) {3 * factor})', source)
                self.assertIn('"MARK" 1.0 1.0 1.0', source)
                self.assertNotIn('"_.SCALE"', source)

    def test_update_retains_world_position_and_detects_changed_insert_scale(self):
        source = build_zapata_detail_lisp(
            self.schedule, self.rules, self.geometry, 'entrada', '',
            drawing_units_per_m=1000)
        self.assertIn('(and old (= oldtag exact) (sincal:detail-scale-p old))', source)
        self.assertIn('point (if old (trans (cdr (assoc 10 (entget old))) old 0)', source)
        apply_plan = source[source.index('(defun sincal:apply-plan'):source.index('(defun c:SINCAL-ZAPATA-DESPIECE')]
        insertion_branch = apply_plan[apply_plan.index('((tblsearch "BLOCK" block-name)'):]
        self.assertLess(insertion_branch.index('(vla-InsertBlock'), insertion_branch.index('(if old (entdel old))'))
        self.assertIn('(setq base (trans base 1 0))', source)
        self.assertNotIn('"_.UCS"', source)

    def test_invalid_drawing_units_are_rejected(self):
        for factor in (0, -1, 2, float('nan'), float('inf'), True, 'mm', None):
            with self.subTest(factor=factor):
                with self.assertRaisesRegex(ValueError, 'unidades'):
                    build_zapata_detail_lisp(
                        self.schedule, self.rules, self.geometry, 'entrada', '',
                        drawing_units_per_m=factor)

    def test_completion_covers_cancel_and_style_failure_without_modal(self):
        command = self.lisp[self.lisp.index('(defun c:SINCAL-ZAPATA-DESPIECE'):]
        self.assertIn('(setq *SINCAL_LIVE_RESULT* nil)', command)
        self.assertIn('(list nil "Despiece cancelado;', command)
        self.assertIn('(list nil "Actualizacion cancelada;', command)
        self.assertIn('(list nil "SINCAL no pudo importar', command)
        self.assertLess(command.index('(vla-Regen doc 1)'),
                        command.index('(list T "Despiece de zapata'))
        self.assertNotIn('(alert ', self.lisp)

    def test_lisp_conditionals_have_only_a_then_and_optional_else(self):
        root = []
        stack = [root]
        for token in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', self.lisp):
            if token == '(':
                nested = []
                stack[-1].append(nested)
                stack.append(nested)
            elif token == ')':
                self.assertGreater(len(stack), 1)
                stack.pop()
            else:
                stack[-1].append(token)
        self.assertEqual(len(stack), 1)

        def check(form):
            if not isinstance(form, list):
                return
            if form and form[0] == 'if':
                self.assertIn(len(form), (3, 4), repr(form[:3]))
            for child in form:
                check(child)
        check(root)


if __name__ == "__main__":
    unittest.main()
