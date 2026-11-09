import unittest
import re
import math
from dataclasses import replace

from sincal.cad.moldajes import MoldajeCandidate
from sincal.rebar.model import Cover, RemovedPiece, ZapataGeometry, default_zapata_rules
from sincal.cad.zapata_views import ZapataCadError, build_zapata_lisp, inward_offset, project_footing_assembly, footing_drawing_projection
from sincal.rebar.assembly import build_footing_assembly
from tests.test_rebar_marks_cad import lisp_forms


class ZapataCadTests(unittest.TestCase):
    def setUp(self):
        self.candidate = MoldajeCandidate(
            "FF_ZAP", "ABC", "OK", 5, 86.97,
            ((0, 0), (5, 0), (11.596, 0), (11.596, 7.5), (0, 7.5)),
        )
        self.geometry = ZapataGeometry.from_centimetres(750, 1159.6, 150, 7)
        self.cover = Cover.from_centimetres(7.5, 5, 5)
        self.rules = default_zapata_rules()

    def test_offset_ignores_collinear_vertex_count(self):
        offset = inward_offset(self.candidate.vertices, 0.05)
        self.assertEqual(len(offset), 4)
        self.assertAlmostEqual(min(point[0] for point in offset), 0.05)

    def test_rejects_concave_moldaje_explicitly(self):
        with self.assertRaisesRegex(ZapataCadError, "cóncavo"):
            inward_offset(((0, 0), (2, 0), (1, 1), (2, 2), (0, 2)), 0.05)

    def test_builds_each_approved_view_and_preserves_tag_scope(self):
        for view in ("FR", "AA", "BB", "CC", "FF"):
            candidate = MoldajeCandidate(
                f"{view}_ZAP", "ABC", "OK", self.candidate.vertex_count,
                self.candidate.area_m2, self.candidate.vertices,
            )
            lisp = build_zapata_lisp(
                view, candidate, self.geometry, self.cover, self.rules, "entrada")
            self.assertIn(f'ENTRADA_{view}_ZAP', lisp)
            self.assertIn('(sincal:layer "fi22")', lisp)
            self.assertIn("Moldaje preservado", lisp)
            without_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', lisp)
            self.assertEqual(without_strings.count("("), without_strings.count(")"))

    def test_diameter_22_bends_use_a_66_millimetre_radius(self):
        assembly = build_footing_assembly(self.geometry, self.cover, self.rules)
        shapes = [p for p in project_footing_assembly(assembly, "FR") if p.key == "mesh_x"]
        self.assertTrue(shapes)
        radii = []
        for piece in shapes:
            for a, b, bulge in zip(piece.vertices_m, piece.vertices_m[1:], piece.bulges):
                if abs(bulge) > 1e-9:
                    radii.append(math.dist(a, b)/(2*math.sin(2*math.atan(abs(bulge)))))
        self.assertTrue(radii)
        for radius in radii:
            self.assertAlmostEqual(radius, .066)
        lisp = build_zapata_lisp("FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        self.assertIn('(cons 42 ', lisp)
        self.assertNotIn('"_.FILLET"', lisp)

    def test_transverse_bars_are_plain_circles_without_fi_blocks(self):
        lisp = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        self.assertIn('(cons 0 "CIRCLE")', lisp)
        self.assertNotIn('"fi22" 1.0 1.0 1.0', lisp)
        self.assertNotIn("HATCH", lisp)

    def test_fr_transverse_bars_are_real_sections_of_the_shared_assembly(self):
        assembly = build_footing_assembly(self.geometry, self.cover, self.rules)
        sections = [p for p in project_footing_assembly(assembly, "FR") if p.kind == "circle"]
        self.assertEqual({p.key for p in sections}, {"mesh_y", "lateral_y"})
        lisp = build_zapata_lisp("FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        self.assertEqual(lisp.count('(cons 0 "CIRCLE")'), len(sections))
        for section in sections:
            x, z = section.vertices_m[0]
            self.assertGreaterEqual(z, self.cover.inferior_m)
            self.assertLessEqual(z, self.geometry.alto_m-self.cover.superior_m)
            self.assertLess(abs(x), self.geometry.ancho_m/2)
        # The two faces remain separately dimensioned; no diagonal dimension
        # may join circles on opposing faces merely because they share a mark.
        dimensions = [line for line in lisp.splitlines() if line.strip().startswith('(sincal:marked-dim ')]
        self.assertTrue(dimensions)

    def test_transverse_groups_receive_aligned_dimensions_on_rebar_layers(self):
        lisp = build_zapata_lisp(
            "AA", self.candidate, self.geometry, self.cover, self.rules, "entrada",
            master_path=r"C:\SINCAL\masters\FORMATOS ANOTATIVOS ACAD_2025.dwg",
        )
        self.assertIn("vla-AddDimAligned", lisp)
        self.assertIn('vla-put-StyleName obj "GSG_COTAS"', lisp)
        self.assertIn('"1" "SIN_CANTIDAD_SUP" "fi22" "ENTRADA_AA_ZAP"', lisp)
        self.assertIn('"1" "SIN_CANTIDAD_INF" "fi22" "ENTRADA_AA_ZAP"', lisp)
        self.assertNotIn('"2" "SIN_CANTIDAD_INF" "fi22" "ENTRADA_AA_ZAP"', lisp)
        self.assertIn('"4" "SIN_CANTIDAD" "fi16" "ENTRADA_AA_ZAP"', lisp)
        # Dimensions retain their measured value; the native linked blocks carry
        # mark, diameter and spacing instead of a second unlinked text copy.
        self.assertNotIn('(vla-put-TextOverride obj text)', lisp)
        self.assertNotIn('(vla-put-TextOverride obj " ")', lisp)
        self.assertNotIn('(vla-get-TextStyles database) "RomanD"', lisp)

    def test_real_length_bars_receive_linked_native_mark_and_associative_leader(self):
        lisp = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        self.assertIn('vla-AddLeader ms points (vlax-ename->vla-object label)', lisp)
        self.assertIn('(srb:label landing mark state nil nil nil layer tag 2.5)', lisp)
        self.assertIn('"1" "SIN_CANTIDAD_SUP" "fi22" "ENTRADA_FR_ZAP"', lisp)
        self.assertIn('"2" "SIN_CANTIDAD_INF" "fi22" "ENTRADA_FR_ZAP"', lisp)
        self.assertNotIn('vla-AddMLeader', lisp)
        self.assertNotIn('GSG_MLEADER', lisp)

    def test_annotation_styles_are_imported_before_old_view_is_deleted(self):
        lisp = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, self.rules, "entrada",
            master_path=r"C:\SINCAL\master.dwg",
        )
        self.assertIn("ObjectDBX.AxDbDocument", lisp)
        self.assertIn("ZWCAD.ZcDbDocument", lisp)
        self.assertIn('(vla-get-DimStyles doc) "GSG_COTAS"', lisp)
        self.assertLess(
            lisp.index("sincal:ensure-annotation-styles acad doc"),
            lisp.index('(sincal:delete-old "ENTRADA_FR_ZAP")'),
        )
        self.assertNotIn('(setvar "CANNOSCALE', lisp)
        self.assertIn(
            "(vl-catch-all-apply 'vlax-release-object (list dbx))))))",
            lisp,
        )

    def test_manual_hook_length_is_used_by_cad_geometry(self):
        rules = tuple(replace(rule, hook_cm=120.0) if rule.key == "mesh_x" else rule for rule in self.rules)
        assembly = build_footing_assembly(self.geometry, self.cover, rules)
        shapes = [p for p in project_footing_assembly(assembly, "FR") if p.key == "mesh_x"]
        self.assertTrue(shapes)
        # A straight hook is the end segment adjoining the first/last curve.
        lengths = []
        roles = {bar.id: bar.piece_role for bar in assembly.bars}
        for piece in shapes:
            if roles[piece.source_id] in ("inicial", "completa"):
                lengths.append(math.dist(*piece.vertices_m[:2]))
            if roles[piece.source_id] in ("terminal", "completa"):
                lengths.append(math.dist(*piece.vertices_m[-2:]))
        self.assertTrue(lengths)
        for length in lengths:
            self.assertAlmostEqual(length, 1.2, places=6)

    def test_ff_preserves_the_actual_contacting_lap_without_graphic_offsets(self):
        assembly = build_footing_assembly(self.geometry, self.cover, self.rules)
        pieces = [p for p in project_footing_assembly(assembly, "FF") if p.key == "mesh_x"]
        self.assertGreaterEqual(len(pieces), 2)
        lanes = sorted({round(point[1],9) for piece in pieces for point in piece.vertices_m})
        self.assertEqual(len(lanes), 2)
        self.assertAlmostEqual(lanes[1]-lanes[0], .022)
        self.assertTrue(any(piece.lap_segments_m for piece in pieces))

    def test_fr_retains_real_representative_lap_pieces_beside_the_cut_plane(self):
        assembly = build_footing_assembly(self.geometry, self.cover, self.rules)
        physical = [p for p in project_footing_assembly(assembly,"FR") if p.key=="mesh_x"]
        drawing = [p for p in footing_drawing_projection(assembly,"FR") if p.key=="mesh_x"]
        self.assertEqual(len(physical),2)
        self.assertEqual(len(drawing),4)
        by_id = {bar.id:bar for bar in assembly.bars}
        station = by_id[drawing[0].source_id].coordinate_m
        origin = math.tan(math.radians(self.geometry.esviaje_grados))*station
        for piece in drawing:
            bar = by_id[piece.source_id]
            self.assertEqual(piece.mark,bar.mark)
            for actual,world in zip(piece.vertices_m,bar.vertices_m):
                self.assertAlmostEqual(actual[0],world[0]-origin)
                self.assertAlmostEqual(actual[1],world[2])
        for role in ("inicial","terminal"):
            with self.subTest(role=role):
                chosen = next(by_id[p.source_id] for p in drawing if by_id[p.source_id].piece_role==role)
                rules = tuple(replace(rule,removed_pieces=(RemovedPiece(chosen.id,chosen.signature),))
                              if rule.key==chosen.key else rule for rule in self.rules)
                after = build_footing_assembly(self.geometry,self.cover,rules)
                self.assertTrue(after.is_valid)
                remaining = [p for p in footing_drawing_projection(after,"FR") if p.key=="mesh_x"]
                self.assertEqual(remaining,[p for p in drawing if p.source_id!=chosen.id])

    def test_dd_is_reserved_for_walls(self):
        with self.assertRaisesRegex(ZapataCadError, "muros y alas"):
            build_zapata_lisp("DD", self.candidate, self.geometry, self.cover, self.rules, "entrada")

    def test_ee_is_not_a_current_footing_view(self):
        with self.assertRaisesRegex(ZapataCadError, "no corresponde"):
            build_zapata_lisp("EE", self.candidate, self.geometry, self.cover, self.rules, "entrada")

    def test_all_created_geometry_uses_requested_drawing_units(self):
        # The input rectangle and domain remain in metres. Every emitted point,
        # including leaders and dimensions, must be converted exactly once.
        def emitted_points(source):
            return [tuple(map(float, match)) for match in re.findall(
                r'\(list (-?[\d.]+) (-?[\d.]+)(?: 0\.0)?\)', source)]

        for view in ("FR", "AA", "BB", "CC", "FF"):
            baseline = build_zapata_lisp(
                view, self.candidate, self.geometry, self.cover, self.rules, "entrada")
            reference = emitted_points(baseline)
            self.assertTrue(reference)
            for factor in (1, 100, 1000):
                with self.subTest(view=view, units_per_m=factor):
                    result = build_zapata_lisp(
                        view, self.candidate, self.geometry, self.cover, self.rules,
                        "entrada", drawing_units_per_m=factor)
                    converted = emitted_points(result)
                    self.assertEqual(len(reference), len(converted))
                    for point_m, point_cad in zip(reference, converted):
                        for value_m, value_cad in zip(point_m, point_cad):
                            self.assertAlmostEqual(value_cad, value_m * factor, delta=1e-6)
                    self.assertNotIn('"_.SCALE"', result)
                    # A table prototype is scaled for paper presentation;
                    # physical reinforcement geometry is never fitted/scaled.
                    for form in lisp_forms(result):
                        if 'vla-ScaleEntity' in form:
                            self.assertTrue(form.startswith(('(defun srb:new-table ',
                                                             '(defun srb:restore-generated-format ')))
                    self.assertNotIn('handent "ABC"', result)
                    # Native annotative blocks receive paper height, not model
                    # units. CAD already applies the actual annotation ratio.
                    self.assertIn('(srb:label landing mark state nil nil nil layer tag 2.5)', result)
                    # Quantities and mark text do not change with drawing units.
                    self.assertEqual(re.findall(r'"\([1-9][^"\n]*"', baseline),
                                     re.findall(r'"\([1-9][^"\n]*"', result))

    def test_millimetre_output_scales_bends_and_bar_sections(self):
        metre = build_zapata_lisp("FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        result = build_zapata_lisp("FR", self.candidate, self.geometry, self.cover, self.rules, "entrada", drawing_units_per_m=1000)
        # Bulges are dimensionless; changing units must leave each real curve
        # unchanged while scaling coordinates and section radii exactly once.
        self.assertEqual(re.findall(r'\(cons 42 ([^)]*)\)', metre), re.findall(r'\(cons 42 ([^)]*)\)', result))
        self.assertIn('(cons 40 11)', result)
        self.assertIn('(cons 40 8)', result)

    def test_entity_geometry_uses_world_coordinates_independent_of_current_ucs(self):
        source = build_zapata_lisp("FR", self.candidate, self.geometry, self.cover, self.rules, "entrada", drawing_units_per_m=1000)
        self.assertIn('(cons 0 "LWPOLYLINE")', source)
        self.assertNotIn('(command "_.PLINE"', source)
        self.assertNotIn('(cons 10 (trans ', source)
        self.assertNotIn('(sincal:marked-dim (trans ', source)
        self.assertNotIn('(sincal:linked-mark (trans ', source)
        self.assertNotIn('"_.UCS"', source)

    def test_invalid_drawing_units_are_rejected_before_generating(self):
        for factor in (0, -1, 2, float('nan'), float('inf'), True, 'mm', None):
            with self.subTest(factor=factor):
                with self.assertRaisesRegex(ZapataCadError, 'unidades'):
                    build_zapata_lisp(
                        "FR", self.candidate, self.geometry, self.cover, self.rules,
                        "entrada", drawing_units_per_m=factor)

    def test_completion_reports_success_only_after_geometry_and_regeneration(self):
        source = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        command = source[source.index('(defun sincal:generate-view'):]
        self.assertIn("(srb:run 'sincal:generate-view)", command)
        self.assertLess(command.index('(srb:sync-table)'),
                        command.index('(sincal:delete-old'))
        self.assertLess(command.index('(vla-Regen doc 1)'),
                        command.index('(setq *SINCAL_LIVE_RESULT* (list T'))
        self.assertLess(command.index('(srb:finish)'),
                        command.index("(apply 'sincal:place-mark entry)"))
        self.assertIn('(setq *SINCAL_LIVE_RESULT* (list nil', command)
        self.assertNotIn('(alert ', command)

    def test_plan_and_supplement_use_native_presentation_without_total_as_face_count(self):
        rules = tuple(replace(rule, enabled=True) if rule.key == 'suple' else rule
                      for rule in self.rules)
        source = build_zapata_lisp('FF', self.candidate, self.geometry, self.cover, rules, 'entrada')
        calls = [line for line in source.splitlines() if line.strip().startswith('(sincal:linked-mark ')]
        self.assertTrue(calls)
        self.assertTrue(any('"3A" "SIN_CANTIDAD_SUP_SUPLE"' in line for line in calls))
        self.assertTrue(any('"1" "SIN_CANTIDAD_SUP"' in line for line in calls))
        self.assertFalse(any('CON_CANTIDAD' in line or '_INF' in line for line in calls))


if __name__ == "__main__":
    unittest.main()
