import re
import unittest
from dataclasses import replace

from sincal.rebar.model import Cover, ZapataGeometry, build_zapata_schedule, default_zapata_rules
from sincal.cad.zapata_detail import _group_definition, _label_recipe, build_zapata_detail_lisp
from sincal.rebar.detail import build_detail_groups


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

    def test_uses_native_detail_marks_and_only_geometry_dimension_styles(self):
        self.assertIn('"GSG_ARM-COTAS"', self.lisp)
        self.assertIn('"<>\\\\XALTERNADO"', repr(self.lisp))
        self.assertIn('"SINCAL_MARCA_DE_V2"', self.lisp)
        self.assertIn('(srb:label point (nth 1 recipe) (nth 2 recipe) T', self.lisp)
        self.assertNotIn('"MARK"', self.lisp)
        self.assertNotIn('vla-AddMText', self.lisp)
        self.assertNotIn('sincal:set-mark', self.lisp)
        self.assertNotIn('sincal:detail-label (', self.lisp)

    def test_dynamic_marks_are_not_nested_and_recipe_uses_calculated_totals(self):
        for group in build_detail_groups(self.schedule, self.rules, self.geometry):
            name, definition = _group_definition(group, 'entrada')
            self.assertIn('_DE2_', name)
            self.assertNotIn('srb:label', definition)
            self.assertNotIn('MARK', definition)
            recipe = _label_recipe(group)
            for piece in group.pieces:
                if len(piece.length_variants) > 1:
                    self.assertIn(f'"{piece.mark}" "NORMAL" {piece.quantity} "VAR.', recipe)
                else:
                    self.assertIn(f'"{piece.mark}" "NORMAL" {piece.quantity} {piece.total_cm}', recipe)
        self.assertIn('SINCAL_DETAIL|ENTRADA|G12|DE2|', self.lisp)

    def test_suple_uses_native_superior_supplement_visibility(self):
        rules = tuple(replace(rule, enabled=True) if rule.key == 'suple' else rule
                      for rule in self.rules)
        schedule = build_zapata_schedule(self.geometry, self.cover, rules)
        group = next(g for g in build_detail_groups(schedule, rules, self.geometry)
                     if g.group_id == 'G3A')
        self.assertIn('"SUP_SUPLE"', _label_recipe(group))

    def test_existing_manual_values_are_kept_until_update_is_accepted(self):
        self.assertIn('((and previous (not replace-values)) (setq label previous))', self.lisp)
        self.assertIn('(sincal:sync-detail-labels old nil nil)', self.lisp)
        self.assertIn('(sincal:sync-detail-labels (vlax-vla-object->ename obj) old T)', self.lisp)
        self.assertIn('(setq srb:preserve-keys (cons rule-key srb:preserve-keys))', self.lisp)
        command = self.lisp[self.lisp.index('(defun sincal:generate-detail'):]
        self.assertLess(command.index('(sincal:plan-detail'), command.index('(srb:sync-table)'))

    def test_accepted_update_changes_native_values_in_place_preserving_presentation(self):
        native_branch = self.lisp[self.lisp.index('((and previous\n            (= "SINCAL_MARCA_DE_V2"'):]
        native_branch = native_branch[:native_branch.index('(setq label previous))')]
        self.assertIn('(SCM:PutText (cdr (assoc "CANT_TOTAL" attrs))', native_branch)
        self.assertIn('(SCM:PutText (cdr (assoc "LARGO" attrs))', native_branch)
        self.assertIn('(SCM:Bind obj srb:table-object', native_branch)
        self.assertNotIn('entdel', native_branch)
        self.assertNotIn('InsertBlock', native_branch)
        self.assertNotIn('srb:state', native_branch)
        self.assertNotIn('Rotation', native_branch)
        self.assertNotIn('ScaleFactor', native_branch)
        self.assertNotIn('sincal:rescale-detail-mark', self.lisp)

    def test_cleanup_is_limited_to_explicitly_owned_top_level_marks(self):
        self.assertIn('SINCAL_DETAIL_LABELS_V1', self.lisp)
        self.assertIn('(sincal:label-owner-p label owner)', self.lisp)
        self.assertIn('(foreach label (sincal:detail-label-refs owner)', self.lisp)
        self.assertIn('(SCM:WritableMark (vlax-ename->vla-object label))', self.lisp)
        self.assertNotIn('"_.PURGE"', self.lisp)

    def test_lisp_parentheses_are_balanced(self):
        without_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', self.lisp)
        self.assertEqual(without_strings.count("("), without_strings.count(")"))

    def test_variable_series_keeps_one_native_mark_and_documents_every_length(self):
        self.geometry = replace(self.geometry, esviaje_grados=12)
        self.schedule = build_zapata_schedule(self.geometry, self.cover, self.rules)
        group = next(group for group in build_detail_groups(self.schedule, self.rules, self.geometry)
                     if group.group_id == 'G3')
        self.assertEqual(len(group.pieces), 1)
        piece = group.pieces[0]
        self.assertGreater(len(piece.length_variants), 1)
        self.assertEqual(group.laps_m, ())
        _, definition = _group_definition(group, 'entrada')
        self.assertIn('SERIE VARIABLE - CANT. x L DESARROLLADO (cm)', definition)
        self.assertIn('Geometria representativa: largo maximo', definition)
        self.assertIn('"VAR.', definition)
        for variant in piece.length_variants:
            self.assertIn(f'"{variant.quantity} x {variant.length_cm:g}"', definition)
        # The length list belongs to the geometry block; the only mark stays
        # linked through the top-level MARCA-DE, with its total quantity.
        self.assertNotIn('srb:label', definition)
        recipe = _label_recipe(group)
        self.assertEqual(recipe.count(f'"{piece.mark}" "NORMAL"'), 1)
        lower = min(v.length_cm for v in piece.length_variants)
        upper = max(v.length_cm for v in piece.length_variants)
        self.assertIn(f'"VAR. {lower:g}-{upper:g} cm"', recipe)
        self.assertNotIn(f' {piece.quantity} {piece.total_cm} "', recipe)

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
                # InsertBlock takes paper-sized factors, including for metres;
                # the annotation context applies its actual paper/drawing ratio.
                self.assertIn('(sincal:xdata-value owner)) 2.5)', source)
                self.assertIn('(sincal:detail-world-point owner (car recipe))', source)
                self.assertNotIn('sincal:annotation-scale', source)
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
        command = self.lisp[self.lisp.index('(defun sincal:generate-detail'):]
        self.assertIn("(srb:run 'sincal:generate-detail)", command)
        self.assertIn('(srb:fail "Despiece cancelado;', command)
        self.assertIn('(srb:fail "Actualizacion cancelada;', command)
        self.assertIn('(srb:fail "SINCAL no pudo importar', command)
        self.assertLess(command.index('(srb:finish)'),
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
