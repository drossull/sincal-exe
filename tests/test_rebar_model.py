import unittest

from sincal_rebar_model import (
    Cover,
    RebarRule,
    ZapataGeometry,
    build_zapata_schedule,
    default_zapata_rules,
)


class ZapataScheduleTests(unittest.TestCase):
    def setUp(self):
        self.geometry = ZapataGeometry.from_centimetres(1200, 600, 150, 7)
        self.cover = Cover.from_centimetres(5, 5, 5)

    def test_calculates_each_physical_mesh_once(self):
        rules = (
            RebarRule("sup_long", "Superior longitudinal", "1", 22, 20, 50, "superior", "longitudinal"),
            RebarRule("sup_trans", "Superior transversal", "2", 22, 20, 50, "superior", "transversal"),
        )
        schedule = build_zapata_schedule(self.geometry, self.cover, rules)

        self.assertTrue(schedule.is_valid)
        longitudinal, transversal = schedule.marks
        self.assertEqual(longitudinal.quantity, 30)
        self.assertEqual(longitudinal.unit_length_cm, 1240)
        self.assertEqual(transversal.quantity, 60)
        self.assertEqual(transversal.unit_length_cm, 640)
        self.assertEqual(longitudinal.views, ("FR", "AA", "EE"))
        self.assertIn("debajo", longitudinal.projection_notes["AA"])
        self.assertGreater(schedule.total_kg, 0)

    def test_rejects_cover_that_leaves_no_space(self):
        cover = Cover.from_centimetres(5, 5, 400)
        schedule = build_zapata_schedule(self.geometry, cover, default_zapata_rules())

        self.assertFalse(schedule.is_valid)
        self.assertTrue(any("espacio útil" in issue.message for issue in schedule.issues))

    def test_requires_manual_definition_for_optional_groups(self):
        rule = RebarRule("suple", "Suple", "6", 16, 20, 0, "suple", "longitudinal", automatic=False)
        schedule = build_zapata_schedule(self.geometry, self.cover, (rule,))

        self.assertEqual(schedule.marks, ())
        self.assertTrue(any(issue.severity == "warning" for issue in schedule.issues))


if __name__ == "__main__":
    unittest.main()
