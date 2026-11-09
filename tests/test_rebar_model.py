import unittest
from dataclasses import replace

from sincal.rebar.model import (
    Cover,
    RebarRule,
    ZapataGeometry,
    automatic_hook_cm,
    bend_radius_cm,
    build_zapata_schedule,
    default_zapata_rules,
    distribution_positions_cm,
)


class ZapataScheduleTests(unittest.TestCase):
    def setUp(self):
        self.geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, 7)
        self.cover = Cover.from_centimetres(7.5, 5, 5)

    def test_hook_rule_and_bend_radius(self):
        self.assertEqual(automatic_hook_cm(150), 100)
        self.assertEqual(automatic_hook_cm(180), 100)
        self.assertEqual(automatic_hook_cm(205), 110)
        self.assertEqual(automatic_hook_cm(250), 130)
        self.assertAlmostEqual(bend_radius_cm(12), 3.6)
        self.assertAlmostEqual(bend_radius_cm(22), 6.6)

    def test_fixed_spacing_and_end_residue(self):
        self.assertEqual(distribution_positions_cm(175, 20), (0, 20, 40, 60, 80, 100, 120, 140, 160, 175))
        self.assertEqual(distribution_positions_cm(168, 20), (0, 20, 40, 60, 80, 100, 120, 140, 160))
        self.assertEqual(distribution_positions_cm(175, 20, "final"), (0, 15, 35, 55, 75, 95, 115, 135, 155, 175))

    def test_builds_agreed_marks_once_for_all_views(self):
        schedule = build_zapata_schedule(self.geometry, self.cover, default_zapata_rules())
        self.assertTrue(schedule.is_valid, schedule.issues)
        marks = {mark.mark: mark for mark in schedule.marks}
        self.assertEqual(set(marks), {"1", "2", "3", "4", "5", "6"})
        self.assertEqual(marks["1"].unit_length_cm, 1200)
        self.assertEqual(marks["1"].quantity, marks["2"].quantity)
        self.assertEqual(marks["4"].quantity, marks["5"].quantity)
        self.assertNotIn("DD", marks["1"].views)
        self.assertNotIn("FR", marks["4"].views)
        self.assertEqual(marks["6"].views, ("FR", "FF"))
        self.assertGreater(schedule.total_kg, 0)

    def test_single_piece_keeps_base_mark_and_two_hooks(self):
        short = ZapataGeometry.from_centimetres(500, 500, 150)
        schedule = build_zapata_schedule(short, self.cover, default_zapata_rules())
        marks = {mark.mark: mark for mark in schedule.marks}
        self.assertNotIn("2", marks)
        self.assertNotIn("5", marks)
        self.assertEqual(marks["1"].hook_count, 2)
        self.assertLessEqual(marks["1"].unit_length_cm, 1200)

    def test_three_piece_run_uses_approved_terminal_variant(self):
        very_wide = ZapataGeometry.from_centimetres(750, 2300, 150)
        schedule = build_zapata_schedule(very_wide, self.cover, default_zapata_rules())
        marks = {mark.mark: mark for mark in schedule.marks}
        self.assertIn("2A", marks)
        self.assertIn("5A", marks)
        self.assertEqual(marks["2"].piece_role, "intermedia")
        self.assertEqual(marks["2A"].piece_role, "terminal")

    def test_optional_suple_has_complete_range_when_enabled(self):
        rules = list(default_zapata_rules())
        template = rules[2]
        rules[2] = RebarRule(
            template.key, template.label, template.mark, template.diameter_mm,
            15, template.hook_cm, template.level, template.direction,
            enabled=True,
        )
        schedule = build_zapata_schedule(self.geometry, self.cover, tuple(rules))
        suple = next(mark for mark in schedule.marks if mark.mark == "3A")
        self.assertEqual(suple.views, ("FR", "AA", "BB", "CC", "FF"))
        self.assertEqual(suple.hook_count, 2)

    def test_rejects_cover_that_leaves_no_space(self):
        schedule = build_zapata_schedule(
            self.geometry, Cover.from_centimetres(5, 5, 400), default_zapata_rules())
        self.assertFalse(schedule.is_valid)
        self.assertTrue(any("espacio útil" in issue.message for issue in schedule.issues))

    def test_mark_contract_matches_native_table(self):
        original = default_zapata_rules()[0]
        for mark in ("1", "3A", "3a", "12AB", "01", "0"):
            with self.subTest(mark=mark):
                self.assertFalse(replace(original, mark=mark).validate())
        for mark in ("", "3-A", "1 2", "1A2", "1\n", "1İ", "１", '1\") (quit)', None):
            with self.subTest(mark=mark):
                self.assertTrue(replace(original, mark=mark).validate())

    def test_duplicate_marks_ignore_case(self):
        rules = list(default_zapata_rules())
        rules[1] = replace(rules[1], mark="3a")
        rules[2] = replace(rules[2], enabled=True)
        schedule = build_zapata_schedule(self.geometry, self.cover, rules)
        self.assertFalse(schedule.is_valid)
        self.assertTrue(any("Marca duplicada '3A'" in issue.message for issue in schedule.issues))

    def test_duplicate_generated_continuation_and_terminal_marks_are_blocked(self):
        rules = list(default_zapata_rules())
        rules[0] = replace(rules[0], continuation_mark="3")
        schedule = build_zapata_schedule(self.geometry, self.cover, rules)
        self.assertFalse(schedule.is_valid)
        rules = list(default_zapata_rules())
        rules[0] = replace(rules[0], continuation_mark="2a", terminal_mark="2A")
        schedule = build_zapata_schedule(
            ZapataGeometry.from_centimetres(750, 2300, 150), self.cover, rules)
        self.assertFalse(schedule.is_valid)
        self.assertTrue(any("Marca duplicada '2A'" in issue.message for issue in schedule.issues))

    def test_fallback_terminal_uses_native_suffix(self):
        rules = tuple(replace(rule, terminal_mark="") for rule in default_zapata_rules())
        schedule = build_zapata_schedule(
            ZapataGeometry.from_centimetres(750, 2300, 150), self.cover, rules)
        self.assertTrue(schedule.is_valid, schedule.issues)
        self.assertIn("2A", {mark.mark for mark in schedule.marks})
        self.assertIn("5A", {mark.mark for mark in schedule.marks})

    def test_rectangular_schedule_counts_the_usable_lateral_cage_and_same_meshes(self):
        # Both mesh and lateral distributions include both real tangencies;
        # the extra closing bars also belong to the schedule quantities.
        rectangular = replace(self.geometry, esviaje_grados=0)
        schedule = build_zapata_schedule(rectangular, self.cover, default_zapata_rules())
        self.assertEqual([(mark.mark, mark.quantity, mark.unit_length_cm) for mark in schedule.marks], [
            ("1", 76, 1200), ("2", 76, 302), ("3", 116, 943),
            ("4", 14, 1200), ("5", 14, 264), ("6", 16, 944),
        ])
        self.assertAlmostEqual(schedule.total_kg, sum(mark.total_length_cm / 100 * mark.area_m2 * 7850 for mark in schedule.marks))


if __name__ == "__main__":
    unittest.main()
