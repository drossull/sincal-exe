import unittest
from dataclasses import replace
import math

from sincal.rebar.detail import (
    DETAIL_GROUP_ORDER,
    build_detail_groups,
    polyline_developed_length_m,
    polyline_render_points,
)
from sincal.rebar.model import Cover, ZapataGeometry, build_zapata_schedule, default_zapata_rules


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

    def test_phi22_bends_keep_the_approved_66_millimetre_radius(self):
        piece = build_detail_groups(self.schedule, self.rules, self.geometry)[0].pieces[0]
        radii = []
        for index, bulge in enumerate(piece.bulges[:-1]):
            if abs(bulge) < 1e-12:
                continue
            first, last = piece.vertices_m[index:index + 2]
            chord = math.dist(first, last)
            sweep = 4.0 * math.atan(abs(bulge))
            radii.append(chord / (2.0 * math.sin(sweep / 2.0)))
        self.assertTrue(radii)
        self.assertTrue(all(abs(radius - 0.066) < 1e-9 for radius in radii))
        rendered = polyline_render_points(piece)
        self.assertGreater(len(rendered), len(piece.vertices_m))

    def test_manual_hook_length_reaches_the_detail_preview_model(self):
        changed_rules = tuple(
            replace(rule, hook_cm=140) if rule.key == "mesh_x" else rule
            for rule in self.rules
        )
        changed_schedule = build_zapata_schedule(
            self.geometry, self.cover, changed_rules)
        default_piece = build_detail_groups(
            self.schedule, self.rules, self.geometry)[0].pieces[1]
        changed_piece = build_detail_groups(
            changed_schedule, changed_rules, self.geometry)[0].pieces[1]
        self.assertEqual(default_piece.partials_cm[-1], 100)
        self.assertEqual(changed_piece.partials_cm[-1], 140)
        self.assertEqual(
            changed_piece.partials_cm[-1] - default_piece.partials_cm[-1], 40)
        self.assertNotEqual(default_piece.vertices_m, changed_piece.vertices_m)

    def test_nominal_hook_is_not_inflated_by_the_bend_arc(self):
        for group in build_detail_groups(
            self.schedule, self.rules, self.geometry
        ):
            for piece in group.pieces:
                if piece.mark in {"1", "3", "4", "6"}:
                    self.assertEqual(piece.partials_cm[0], 100)
                if piece.mark in {"2", "5"}:
                    self.assertEqual(piece.partials_cm[-1], 100)

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
