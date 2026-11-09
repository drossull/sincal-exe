import unittest
from dataclasses import replace
import math
from types import SimpleNamespace

from sincal.rebar.detail import (
    _build_piece,
    DETAIL_GROUP_ORDER,
    build_detail_groups,
    detail_dimension_metadata,
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

    def test_partial_dimensions_use_cut_length_without_stretching_the_physical_shape(self):
        for group in build_detail_groups(self.schedule, self.rules, self.geometry):
            for piece in group.pieces:
                self.assertEqual(sum(piece.partials_cm), piece.total_cm)
                self.assertAlmostEqual(
                    polyline_developed_length_m(piece) * 100.0,
                    piece.developed_length_cm,
                    places=6,
                )
                self.assertGreaterEqual(piece.total_cm - piece.developed_length_cm, -1e-7)
                self.assertLess(piece.total_cm - piece.developed_length_cm, 1 + 1e-7)

    def test_exact_assembly_shape_is_preserved_instead_of_rebuilt_from_rounded_length(self):
        # Use a shape shorter than its integer cut and deliberately nonstandard
        # origin, proving the detail keeps its geometry and frame verbatim.
        source = next(mark for mark in self.schedule.marks if mark.key == "mesh_x")
        rule = next(rule for rule in self.rules if rule.key == "mesh_x")
        from sincal.rebar.detail import _fillet_polyline
        raw = ((2.0, -1.066), (2.0, 0.0), (5.233, 0.0), (5.233, -1.066))
        vertices, bulges = _fillet_polyline(raw, .066)
        exact_cm = (3.233 - 2 * .066 + 2 + math.pi * .066) * 100
        cut_cm = math.ceil(exact_cm - 1e-9)
        shape = {
            "vertices_m": vertices, "bulges": bulges, "raw_m": raw,
            "main_start_x_m": 2.066, "main_end_x_m": 5.167,
            "developed_length_cm": exact_cm, "cut_length_cm": cut_cm,
            "partials_cm": (100, cut_cm - 200, 100),
        }
        mark = SimpleNamespace(**{**vars(source), "unit_length_cm": cut_cm,
                                  "hook_count": 2, "piece_role": "completa",
                                  "shape_data": shape})
        piece = _build_piece(mark, rule, 150, -12)
        self.assertEqual(piece.vertices_m, vertices)
        self.assertEqual(piece.bulges, bulges)
        self.assertEqual(piece.partial_segments_m, tuple(zip(raw, raw[1:])))
        self.assertEqual((piece.main_start_x_m, piece.main_end_x_m), (2.066, 5.167))
        self.assertEqual(piece.partials_cm, shape["partials_cm"])
        self.assertAlmostEqual(polyline_developed_length_m(piece) * 100, exact_cm)
        self.assertGreater(piece.total_cm, piece.developed_length_cm)

    def test_individual_variant_does_not_reuse_a_different_representative_shape(self):
        self.geometry = replace(self.geometry, esviaje_grados=12)
        self.schedule = build_zapata_schedule(self.geometry, self.cover, self.rules)
        mark = next(mark for mark in self.schedule.marks if mark.key == "mesh_y")
        rule = next(rule for rule in self.rules if rule.key == "mesh_y")
        shortest = min(mark.length_variants, key=lambda variant: variant.length_cm)
        changed = SimpleNamespace(**{**vars(mark), "unit_length_cm": shortest.length_cm,
                                     "length_variants": (shortest,),
                                     "shape_data": {"cut_length_cm": mark.unit_length_cm}})
        piece = _build_piece(changed, rule, 150, self.geometry.esviaje_grados)
        self.assertEqual(piece.total_cm, shortest.length_cm)
        self.assertAlmostEqual(polyline_developed_length_m(piece) * 100, shortest.length_cm)

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
            replace(rule, hook_cm=120) if rule.key == "mesh_x" else rule
            for rule in self.rules
        )
        changed_schedule = build_zapata_schedule(
            self.geometry, self.cover, changed_rules)
        default_piece = build_detail_groups(
            self.schedule, self.rules, self.geometry)[0].pieces[1]
        changed_piece = build_detail_groups(
            changed_schedule, changed_rules, self.geometry)[0].pieces[1]
        self.assertEqual(default_piece.partials_cm[-1], 100)
        self.assertEqual(changed_piece.partials_cm[-1], 120)
        self.assertEqual(
            changed_piece.partials_cm[-1] - default_piece.partials_cm[-1], 20)
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

    def test_composite_groups_use_contact_diameter_offsets_and_laps(self):
        groups = {group.group_id: group for group in build_detail_groups(
            self.schedule, self.rules, self.geometry)}
        for group_id in ("G12", "G45"):
            group = groups[group_id]
            self.assertEqual(group.offsets_m[0][1], 0.0)
            self.assertEqual(group.offsets_m[1][1], -group.pieces[1].diameter_mm / 1000)
            self.assertEqual(len(group.laps_m), 1)
            self.assertGreater(group.laps_m[0][1] - group.laps_m[0][0], 0)

    def test_fingerprint_changes_when_a_mark_changes(self):
        first = build_detail_groups(self.schedule, self.rules, self.geometry)
        changed_geometry = ZapataGeometry.from_centimetres(750, 1165, 150, 7)
        changed_schedule = build_zapata_schedule(changed_geometry, self.cover, self.rules)
        second = build_detail_groups(changed_schedule, self.rules, changed_geometry)
        self.assertNotEqual(first[0].fingerprint, second[0].fingerprint)

    def test_three_piece_group_uses_two_laps_and_alternating_contact_lanes(self):
        geometry = ZapataGeometry.from_centimetres(750, 2300, 150, 7)
        schedule = build_zapata_schedule(geometry, self.cover, self.rules)
        groups = {group.group_id: group for group in build_detail_groups(
            schedule, self.rules, geometry)}
        group = groups["G12"]
        self.assertEqual(tuple(piece.mark for piece in group.pieces), ("1", "2", "2A"))
        self.assertEqual(tuple(offset[1] for offset in group.offsets_m), (0.0, -.022, 0.0))
        self.assertEqual(len(group.laps_m), 2)

    def test_removing_initial_mark_keeps_survivors_in_their_original_contact_lanes(self):
        from sincal.rebar.assembly import build_footing_assembly
        from sincal.rebar.model import RemovedPiece
        geometry = ZapataGeometry.from_centimetres(750, 2300, 150, 7)
        before = build_footing_assembly(geometry, self.cover, self.rules)
        self.assertTrue(before.is_valid, before.schedule.issues)
        removed = [bar for bar in before.bars if bar.key == 'mesh_x' and bar.piece_role == 'inicial']
        rules = tuple(replace(rule, removed_pieces=tuple(RemovedPiece(bar.id,bar.signature) for bar in removed))
                      if rule.key == 'mesh_x' else rule for rule in self.rules)
        after = build_footing_assembly(geometry, self.cover, rules)
        self.assertTrue(after.is_valid, after.schedule.issues)
        original = next(group for group in build_detail_groups(before.schedule,self.rules,geometry) if group.group_id=='G12')
        remaining = next(group for group in build_detail_groups(after.schedule,rules,geometry) if group.group_id=='G12')
        original_offsets = {piece.mark:offset for piece,offset in zip(original.pieces,original.offsets_m)}
        self.assertEqual(tuple(piece.mark for piece in remaining.pieces),('2','2A'))
        for piece,offset in zip(remaining.pieces,remaining.offsets_m):
            self.assertEqual(offset,original_offsets[piece.mark])

    def test_optional_suple_creates_its_own_logical_group(self):
        rules = tuple(
            replace(rule, enabled=True) if rule.key == "suple" else rule
            for rule in self.rules
        )
        schedule = build_zapata_schedule(self.geometry, self.cover, rules)
        groups = {group.group_id: group for group in build_detail_groups(
            schedule, rules, self.geometry)}
        self.assertEqual(tuple(piece.mark for piece in groups["G3A"].pieces), ("3A",))

    def test_skew_series_uses_one_representative_without_false_laps_or_quantities(self):
        self.geometry = replace(self.geometry, esviaje_grados=12)
        self.schedule = build_zapata_schedule(self.geometry, self.cover, self.rules)
        group = next(group for group in build_detail_groups(self.schedule, self.rules, self.geometry)
                     if group.group_id == 'G3')
        self.assertEqual(len(group.pieces), 1)
        piece = group.pieces[0]
        mark = next(mark for mark in self.schedule.marks if mark.key == 'mesh_y')
        self.assertEqual(piece.mark, mark.mark)
        self.assertEqual(piece.length_variants, mark.length_variants)
        self.assertGreater(len(piece.length_variants), 1)
        self.assertEqual(sum(v.quantity for v in piece.length_variants), piece.quantity)
        self.assertEqual(sum(v.quantity * v.length_cm for v in piece.length_variants), mark.total_length_cm)
        self.assertEqual(piece.total_cm, max(v.length_cm for v in piece.length_variants))
        self.assertEqual(piece.variable_partial_index, 1)
        self.assertEqual(group.laps_m, ())
        # The plan skew must not tilt the hooks in the vertical bar plane.
        sweeps = [abs(4 * math.atan(b)) for b in piece.bulges if abs(b) > 1e-12]
        self.assertEqual(len(sweeps), 2)
        for sweep in sweeps:
            self.assertAlmostEqual(sweep, math.pi / 2)

    def test_series_fingerprint_includes_the_full_length_distribution(self):
        self.geometry = replace(self.geometry, esviaje_grados=12)
        self.schedule = build_zapata_schedule(self.geometry, self.cover, self.rules)
        before = next(group for group in build_detail_groups(self.schedule, self.rules, self.geometry)
                      if group.group_id == 'G3')
        mark = next(mark for mark in self.schedule.marks if mark.key == 'mesh_y')
        variants = list(mark.length_variants)
        # Preserve the maximum, total count and shape while moving one piece
        # between two lengths. It still must invalidate the existing detail.
        source = next(i for i, variant in enumerate(variants) if variant.quantity > 1)
        target = (source + 1) % len(variants)
        variants[source] = replace(variants[source], quantity=variants[source].quantity - 1)
        variants[target] = replace(variants[target], quantity=variants[target].quantity + 1)
        changed = replace(mark, length_variants=tuple(variants),
                          total_length_cm=sum(v.length_cm * v.quantity for v in variants))
        schedule = replace(self.schedule, marks=tuple(changed if item is mark else item for item in self.schedule.marks))
        after = next(group for group in build_detail_groups(schedule, self.rules, self.geometry)
                     if group.group_id == 'G3')
        self.assertEqual(before.pieces[0].vertices_m, after.pieces[0].vertices_m)
        self.assertNotEqual(before.fingerprint, after.fingerprint)

    def test_every_series_length_including_shortest_builds_with_real_bend_arcs(self):
        geometry = replace(self.geometry, esviaje_grados=-12)
        schedule = build_zapata_schedule(geometry, self.cover, self.rules)
        mark = next(mark for mark in schedule.marks if mark.key == 'mesh_y')
        rule = next(rule for rule in self.rules if rule.key == 'mesh_y')
        for variant in mark.length_variants:
            with self.subTest(length_cm=variant.length_cm):
                item = replace(mark, unit_length_cm=variant.length_cm, quantity=variant.quantity,
                               length_variants=(variant,))
                piece = _build_piece(item, rule, geometry.alto_m * 100, geometry.esviaje_grados)
                self.assertAlmostEqual(polyline_developed_length_m(piece) * 100,
                                       piece.developed_length_cm, places=6)
                self.assertGreaterEqual(variant.length_cm - piece.developed_length_cm, -1e-7)
                self.assertLess(variant.length_cm - piece.developed_length_cm, 1 + 1e-7)
                self.assertTrue(all(math.isfinite(v) for point in piece.vertices_m for v in point))
                self.assertEqual(sum(piece.partials_cm), variant.length_cm)

    def test_preview_variable_range_is_the_partial_not_the_total_length(self):
        for hook in (100, 120):
            with self.subTest(hook=hook):
                geometry = replace(self.geometry, esviaje_grados=-12)
                rules = tuple(replace(rule, hook_cm=hook) if rule.key == 'mesh_y' else rule
                              for rule in self.rules)
                schedule = build_zapata_schedule(geometry, self.cover, rules)
                groups = build_detail_groups(schedule, rules, geometry)
                piece = next(group.pieces[0] for group in groups if group.group_id == 'G3')
                before = repr(groups)
                dimensions = detail_dimension_metadata(piece)
                self.assertEqual(dimensions['partial_ranges_cm'], [
                    {'min_cm': hook, 'max_cm': hook},
                    {'min_cm': min(v.length_cm for v in piece.length_variants) - 2 * hook,
                     'max_cm': max(v.length_cm for v in piece.length_variants) - 2 * hook},
                    {'min_cm': hook, 'max_cm': hook},
                ])
                if hook == 100:
                    self.assertEqual(dimensions['partial_ranges_cm'][1],
                                     {'min_cm': 21, 'max_cm': 743})
                self.assertEqual(repr(groups), before)
                self.assertTrue(all(bend['bend_degrees'] == 90 and not bend['skewed']
                                    for bend in dimensions['bends']))

    def test_preview_angles_follow_each_real_bend_for_both_skew_signs(self):
        for skew in (-12, 0, 12):
            with self.subTest(skew=skew):
                geometry = replace(self.geometry, esviaje_grados=skew)
                schedule = build_zapata_schedule(geometry, self.cover, self.rules)
                groups = build_detail_groups(schedule, self.rules, geometry)
                pieces = {piece.mark: piece for group in groups for piece in group.pieces}
                first = detail_dimension_metadata(pieces['1'])['bends']
                last = detail_dimension_metadata(pieces['2'])['bends']
                both = detail_dimension_metadata(pieces['6'])['bends']
                self.assertEqual([item['bend_degrees'] for item in first], [90])
                self.assertEqual([item['interior_degrees'] for item in first], [90])
                self.assertEqual([item['bend_degrees'] for item in last], [90])
                self.assertEqual([item['interior_degrees'] for item in last], [90])
                self.assertEqual(sorted(item['bend_degrees'] for item in both),
                                 sorted([90 + skew, 90 - skew]))
                for piece in pieces.values():
                    dimensions = detail_dimension_metadata(piece)
                    actual_arcs = [abs(math.degrees(4 * math.atan(b)))
                                   for b in piece.bulges if abs(b) > 1e-12]
                    self.assertEqual(len(dimensions['bends']), len(actual_arcs))
                    for index, bend in enumerate(dimensions['bends']):
                        self.assertAlmostEqual(bend['bend_degrees'], actual_arcs[index])
                        self.assertAlmostEqual(math.hypot(*bend['incoming_unit']), 1)
                        self.assertAlmostEqual(math.hypot(*bend['outgoing_unit']), 1)
                        self.assertEqual(bend['vertex_m'], list(piece.partial_segments_m[index][1]))
                        self.assertEqual(bend['skewed'], abs(actual_arcs[index] - 90) > 1e-7)

    def test_preview_straight_piece_has_no_bend_dimension(self):
        geometry = replace(self.geometry, ancho_m=23)
        schedule = build_zapata_schedule(geometry, self.cover, self.rules)
        groups = build_detail_groups(schedule, self.rules, geometry)
        straight = next(piece for group in groups for piece in group.pieces
                        if len(piece.partial_segments_m) == 1)
        dimensions = detail_dimension_metadata(straight)
        self.assertEqual(dimensions['bends'], [])
        self.assertEqual(dimensions['partial_ranges_cm'], [
            {'min_cm': straight.total_cm, 'max_cm': straight.total_cm}])


if __name__ == "__main__":
    unittest.main()
