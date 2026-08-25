import unittest
from dataclasses import replace

from sincal_rebar_detail import (
    DETAIL_GROUP_ORDER,
    build_detail_groups,
    polyline_developed_length_m,
)
from sincal_rebar_model import Cover, ZapataGeometry, build_zapata_schedule, default_zapata_rules


class RebarDetailTests(unittest.TestCase):
    def setUp(self):
        self.geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, 7)
        self.cover = Cover.from_centimetres(7.5, 5, 5)
        self.rules = default_zapata_rules()
        self.schedule = build_zapata_schedule(self.geometry, self.cover, self.rules)

    def test_builds_stable_groups_in_approved_order(self):
        groups = build_detail_groups(self.schedule, self.rules, self.geometry)
        self.assertEqual(tuple(group.group_id for group in groups), ("G12", "G3", "G45", "G6"))
        self.assertEqual(
            tuple(sorted([group.group_id for group in groups], key=DETAIL_GROUP_ORDER.index)),
            tuple(group.group_id for group in groups),
        )
        self.assertEqual(tuple(piece.mark for piece in groups[0].pieces), ("1", "2"))

    def test_partial_dimensions_and_polyline_equal_total_length(self):
        for group in build_detail_groups(self.schedule, self.rules, self.geometry):
            for piece in group.pieces:
                self.assertEqual(sum(piece.partials_cm), piece.total_cm)
                self.assertAlmostEqual(
                    polyline_developed_length_m(piece) * 100.0,
                    piece.total_cm,
                    places=6,
                )

    def test_composite_groups_use_five_millimetre_offsets_and_laps(self):
        groups = {group.group_id: group for group in build_detail_groups(
            self.schedule, self.rules, self.geometry)}
        for group_id in ("G12", "G45"):
            group = groups[group_id]
            self.assertEqual(group.offsets_m[0][1], 0.0)
            self.assertEqual(group.offsets_m[1][1], -0.005)
            self.assertEqual(len(group.laps_m), 1)
            self.assertGreater(group.laps_m[0][1] - group.laps_m[0][0], 0)

    def test_fingerprint_changes_when_a_mark_changes(self):
        first = build_detail_groups(self.schedule, self.rules, self.geometry)
        changed_geometry = ZapataGeometry.from_centimetres(750, 1165, 150, 7)
        changed_schedule = build_zapata_schedule(changed_geometry, self.cover, self.rules)
        second = build_detail_groups(changed_schedule, self.rules, changed_geometry)
        self.assertNotEqual(first[0].fingerprint, second[0].fingerprint)

    def test_three_piece_group_uses_two_laps_and_five_millimetre_steps(self):
        geometry = ZapataGeometry.from_centimetres(750, 2300, 150, 7)
        schedule = build_zapata_schedule(geometry, self.cover, self.rules)
        groups = {group.group_id: group for group in build_detail_groups(
            schedule, self.rules, geometry)}
        group = groups["G12"]
        self.assertEqual(tuple(piece.mark for piece in group.pieces), ("1", "2", "2-A"))
        self.assertEqual(tuple(offset[1] for offset in group.offsets_m), (0.0, -0.005, -0.01))
        self.assertEqual(len(group.laps_m), 2)

    def test_optional_suple_creates_its_own_logical_group(self):
        rules = tuple(
            replace(rule, enabled=True) if rule.key == "suple" else rule
            for rule in self.rules
        )
        schedule = build_zapata_schedule(self.geometry, self.cover, rules)
        groups = {group.group_id: group for group in build_detail_groups(
            schedule, rules, self.geometry)}
        self.assertEqual(tuple(piece.mark for piece in groups["G3A"].pieces), ("3-A",))


if __name__ == "__main__":
    unittest.main()
