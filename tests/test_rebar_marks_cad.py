"""Contract checks for the table/mark bridge; these do not run native AutoCAD."""

from dataclasses import replace
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from sincal.cad.rebar_marks import build_marks_support
from sincal.rebar.model import Cover, ZapataGeometry, build_zapata_schedule, default_zapata_rules


def lisp_forms(source):
    """Read top-level forms, ignoring comments/strings, to catch nesting errors."""
    token = re.compile(r';[^\n]*|"(?:\\.|[^"\\])*"|[()]|[^\s()]+')
    depth, forms, start = 0, [], None
    for match in token.finditer(source):
        value = match.group()
        if value.startswith(';') or value.startswith('"'):
            continue
        if value == '(':
            if depth == 0:
                start = match.start()
            depth += 1
        elif value == ')':
            depth -= 1
            if depth < 0:
                raise AssertionError("Closing parenthesis without a form")
            if depth == 0:
                forms.append(source[start:match.end()])
    if depth:
        raise AssertionError("Unclosed form")
    return forms


class RebarMarksCadTests(unittest.TestCase):
    def setUp(self):
        self.geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, 7)
        self.cover = Cover.from_centimetres(7.5, 5, 5)
        self.rules = default_zapata_rules()
        self.schedule = build_zapata_schedule(self.geometry, self.cover, self.rules)
        self.source = self.build()

    def build(self, schedule=None, rules=None, scope="entrada", units=1, element="footing"):
        with patch("sincal.cad.rebar_marks.ruta_recurso", side_effect=lambda *parts: "C:/SINCAL/" + "/".join(parts)):
            return build_marks_support(schedule or self.schedule, rules or self.rules,
                                       scope, drawing_units_per_m=units, element_key=element)

    def test_all_bridge_definitions_are_top_level_and_balanced(self):
        names = [re.match(r'\(defun\s+([^\s(]+)', form).group(1)
                 for form in lisp_forms(self.source) if form.startswith('(defun ')]
        for name in ('srb:prepare', 'srb:sync-table', 'srb:label', 'srb:finish', 'srb:run'):
            self.assertEqual(names.count(name), 1)
        self.assertNotIn('*error*', names)  # dynamically scoped inside the wrapper

    def test_runtime_loader_and_latest_native_templates(self):
        self.assertIn('srb:source "C:/SINCAL/lisps/MARCAS-SC.lsp"', self.source)
        self.assertIn('srb:master "C:/SINCAL/masters/FORMATOS ANOTATIVOS ACAD_2025.dwg"', self.source)
        self.assertIn('(SCM:DefinitionNamed "SINCAL_MARCA_SC_V3")', self.source)
        self.assertIn('(SCM:DefinitionNamed "SINCAL_MARCA_DE_V2")', self.source)
        self.assertIn('(SCM:Bind obj srb:table-object row)', self.source)
        self.assertIn('(vlax-get prop \'AllowedValues)', self.source)
        self.assertNotIn('"MARK"', self.source)

    def test_rows_contain_calculated_totals_exactly_once(self):
        payload = self.source.split('(defun srb:fail', 1)[0]
        for mark in self.schedule.marks:
            spacing = next(r.spacing_cm for r in self.rules if r.key == mark.key)
            self.assertEqual(payload.count(f'"{mark.mark}" {mark.quantity} {mark.diameter_mm:g} {spacing:g})'), 1)
        self.assertNotIn('placement_multiplier', self.source)

    def test_base_and_continuation_row_ids_survive_piece_role_changes(self):
        mark = self.schedule.marks[0]
        for role in ('completa', 'inicial'):
            schedule = replace(self.schedule, marks=(replace(mark, piece_role=role),))
            self.assertIn(f'"footing:{mark.key}:base"', self.build(schedule))
        rule = self.rules[0]
        for role in ('terminal', 'intermedia'):
            schedule = replace(self.schedule, marks=(replace(mark, mark=rule.continuation_mark, piece_role=role),))
            self.assertIn(f'"footing:{mark.key}:continuation"', self.build(schedule))
        # Renumbering the input family must not change its owned row identity.
        rules = (replace(rule, mark="99"), *self.rules[1:])
        schedule = replace(self.schedule, marks=(replace(mark, mark="99"),))
        self.assertIn(f'"footing:{mark.key}:base"', self.build(schedule, rules))

    def test_registered_target_is_not_the_xrecord_owner_pointer(self):
        self.assertIn('(cons 340 (vlax-vla-object->ename table))', self.source)
        self.assertIn('(cdr (assoc 340 record))', self.source)
        self.assertNotIn('(assoc 330 record)', self.source)
        self.assertIn('"ESTRIBO_ENTRADA"', self.source)
        self.assertIn('"ESTRIBO_SALIDA"', self.build(scope="salida"))

    def test_table_belongs_to_abutment_while_rows_are_namespaced_by_element(self):
        # This exercises the table contract, not a reinforcement recipe for a
        # second element: only the footing recipe is currently defined.
        second = self.build(element="seismic_stop")
        for source in (self.source, second):
            self.assertIn('srb:scope "ESTRIBO_ENTRADA"', source)
        self.assertIn('"footing:mesh_x:base"', self.source)
        self.assertIn('"seismic_stop:mesh_x:base"', second)
        self.assertNotIn('"footing:mesh_x:base"', second)

    def test_partial_recalculation_never_claims_other_element_rows(self):
        forms = {re.match(r'\(defun\s+([^\s(]+)', form).group(1): form
                 for form in lisp_forms(self.source) if form.startswith('(defun ')}
        own = forms['srb:our-row']
        self.assertIn('"SINCAL_REBAR_OWNER_V1"', own)
        self.assertIn('"SINCAL_REBAR_ELEMENT_V1"', own)
        self.assertIn('(srb:our-row table row)', forms['srb:owned-row'])
        # The two guards protect deletion of obsolete rows and reuse of blanks.
        self.assertEqual(forms['srb:sync-table'].count('(srb:our-row srb:table-object row)'), 2)
        # Even an identical mark in the same abutment must not be taken from a
        # different element. Global duplicate/ID checks still cover the table.
        self.assertIn('(srb:our-row table row)', forms['srb:preflight'])
        self.assertIn('Hay marcas duplicadas en la tabla', forms['srb:preflight'])
        self.assertIn('ya pertenece a otro elemento', forms['srb:preflight'])

    def test_full_dwg_copy_and_hidden_views_do_not_change_table_identity(self):
        registration = next(f for f in lisp_forms(self.source)
                            if f.startswith('(defun srb:registered '))
        self.assertIn('(assoc 340 record)', registration)
        self.assertNotIn('DWGNAME', self.source)
        self.assertNotIn('DWGPREFIX', self.source)
        self.assertNotIn('Visible', self.source)
        self.assertNotIn('Freeze', self.source)

    def test_conflicts_are_checked_before_adoption_deletion_or_updates(self):
        form = next(f for f in lisp_forms(self.source) if f.startswith('(defun srb:sync-table '))
        check = form.index('(srb:preflight')
        for mutation in ('(srb:adopt-rows)', '(vla-DeleteRows', '(vla-SetText'):
            self.assertLess(check, form.index(mutation))
        self.assertIn('(setq srb:adopt-table (and selected (not owner)))', self.source)
        self.assertIn('(and srb:adopt-table (not owner))', self.source)
        self.assertIn('(srb:values-match table row entry)', self.source)
        self.assertIn('[Actualizar/Cancelar] <Cancelar>', self.source)
        self.assertIn('(SCM:EnsureID srb:table-object row)', self.source)
        self.assertNotIn('SINCAL_MARCA_ID_V1" (vlax-make-variant', self.source)

    def test_preserved_families_are_not_updated_or_deleted(self):
        self.assertIn('(member (cadr entry) srb:preserve-keys)', self.source)
        self.assertIn('(not (srb:preserved srb:table-object row))', self.source)
        self.assertIn('SINCAL_REBAR_OWNER_V1', self.source)
        self.assertIn('SINCAL_REBAR_PIECE_V1', self.source)

    def test_no_drawing_search_and_one_successful_reactor_initialization(self):
        self.assertNotIn('ssget', self.source)
        self.assertNotIn('vlax-for', self.source)
        self.assertIn('(entsel "', self.source)
        finish = next(f for f in lisp_forms(self.source) if f.startswith('(defun srb:finish '))
        self.assertEqual(finish.count('(SCM:EnableAuto)'), 1)
        self.assertIn('(SCM:SyncOne obj)', finish)
        loader = Path('lisps/MARCAS-SC.lsp').read_text(encoding='utf-8')
        self.assertIn("(boundp 'SCM:defer-auto)", loader)

    def test_new_table_is_the_scaled_master_prototype_not_current_table_style(self):
        form = next(f for f in lisp_forms(self.source) if f.startswith('(defun srb:new-table '))
        self.assertIn('(getvar "CANNOSCALEVALUE")', form)
        self.assertIn('(srb:clear-template-data (srb:copy-table-template))', form)
        self.assertIn('(vla-ScaleEntity table origin (/ 10.0 ratio))', form)
        self.assertIn('(vla-Move table origin (vlax-3d-point (trans point 1 0)))', form)
        self.assertIn('(vla-RecomputeTableBlock table :vlax-true)', form)
        self.assertIn('"ARMADURA ESTRIBO ENTRADA" "ARMADURA ESTRIBO SALIDA"', form)
        self.assertNotIn('vla-AddTable', self.source)
        self.assertNotIn('vla-put-StyleName', form)

    def test_template_copy_is_bounded_to_its_named_block_and_releases_dbx(self):
        form = next(f for f in lisp_forms(self.source) if f.startswith('(defun srb:copy-table-from-dbx '))
        self.assertIn('(vla-Item (vla-get-Blocks dbx) "TABLA-FIERROS")', form)
        self.assertIn('(repeat (vla-get-Count block)', form)
        self.assertIn('(vla-CopyObjects dbx objects (vla-get-ModelSpace (SCM:Doc)))', form)
        self.assertIn('(SCM:TableP candidate)', form)
        outer = next(f for f in lisp_forms(self.source) if f.startswith('(defun srb:copy-table-template '))
        self.assertIn("(vl-catch-all-apply 'srb:copy-table-from-dbx (list dbx))", outer)
        self.assertIn("(vl-catch-all-apply 'vlax-release-object (list dbx))", outer)
        self.assertIn('No se pudo copiar TABLA-FIERROS', outer)

    def test_template_data_and_ownership_are_cleared_before_registration(self):
        form = next(f for f in lisp_forms(self.source) if f.startswith('(defun srb:clear-template-data '))
        self.assertIn('(vla-DeleteRows table 3 (- (vla-get-Rows table) 3))', form)
        self.assertIn('(setq model (vla-Copy table))', form)
        self.assertIn("(vl-catch-all-apply 'srb:reset-template-row (list table model))", form)
        self.assertIn('(vla-Delete model)', form)
        self.assertIn('(SCM:RowID table 2)', form)
        reset = next(f for f in lisp_forms(self.source) if f.startswith('(defun srb:reset-template-row '))
        self.assertIn('(vla-DeleteRows table 2 1)', reset)
        self.assertIn('(vla-InsertRows table 2 (vla-GetRowHeight model 2) 1)', reset)
        self.assertIn('(srb:copy-cell-format model table 2 2 column)', reset)
        self.assertIn('(vla-SetRowHeight table 2 (vla-GetRowHeight model 2))', reset)
        self.assertNotIn('vla-SetCustomData', reset)
        lookup=next(f for f in lisp_forms(self.source) if f.startswith('(defun srb:table '))
        self.assertIn('(if selected (vlax-ename->vla-object (car selected)) (srb:new-table))', lookup)
        self.assertNotIn('srb:copy-table-template', lookup)

    def test_transaction_handles_cancel_and_restores_cad_variables(self):
        wrapper = next(f for f in lisp_forms(self.source) if f.startswith('(defun srb:run '))
        self.assertIn('(command-s "_.UNDO" "_End")', wrapper)
        self.assertIn('(if touched (command-s "_.U"))', wrapper)
        self.assertIn('SINCAL_REBAR_TRANSACTION_V1', wrapper)
        self.assertIn('(if (not (car *SINCAL_LIVE_RESULT*))', wrapper)
        self.assertEqual(wrapper.count('(srb:restore-vars)'), 2)
        self.assertIn('(if srb:failure srb:failure', wrapper)
        self.assertNotIn('(or srb:failure', wrapper)
        self.assertNotIn('(or (cadr *SINCAL_LIVE_RESULT*)', wrapper)

    def test_rejects_incompatible_or_duplicate_mark_names(self):
        mark = self.schedule.marks[0]
        for name in ('3-A', 'A3', '3 A', '3;quit'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'incompatible'):
                self.build(replace(self.schedule, marks=(replace(mark, mark=name),)))
        duplicate = replace(self.schedule, marks=(replace(mark, mark='5a'), replace(mark, mark='5A')))
        with self.assertRaisesRegex(ValueError, 'duplicadas'):
            self.build(duplicate)

    def test_rejects_invalid_scope_units_and_quantities(self):
        for units in (True, 0, 2, float('nan'), 'mm'):
            with self.subTest(units=units), self.assertRaises(ValueError):
                self.build(units=units)
        with self.assertRaises(ValueError):
            self.build(scope='cepa')
        for element in ('', 'footing;quit', '1footing', None):
            with self.subTest(element=element), self.assertRaises(ValueError):
                self.build(element=element)
        mark = self.schedule.marks[0]
        for quantity in (True, 0, -1, 1.5):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                self.build(replace(self.schedule, marks=(replace(mark, quantity=quantity),)))


if __name__ == '__main__':
    unittest.main()
