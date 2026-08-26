import unittest
import re
from dataclasses import replace

from sincal.cad.moldajes import MoldajeCandidate
from sincal.rebar.model import Cover, ZapataGeometry, default_zapata_rules
from sincal.cad.zapata_views import ZapataCadError, build_zapata_lisp, inward_offset


class ZapataCadTests(unittest.TestCase):
    def setUp(self):
        self.candidate = MoldajeCandidate(
            "EE_ZAP", "ABC", "OK", 5, 86.97,
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
        for view in ("FR", "AA", "BB", "CC", "EE"):
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
        lisp = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        self.assertIn('"_.FILLET" "_R" 0.066', lisp)

    def test_transverse_bars_are_plain_circles_without_fi_blocks(self):
        lisp = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        self.assertIn('(cons 0 "CIRCLE")', lisp)
        self.assertNotIn('vla-InsertBlock', lisp)
        self.assertNotIn('"fi22" 1.0 1.0 1.0', lisp)
        self.assertNotIn("HATCH", lisp)

    def test_fr_transverse_bars_start_at_bend_tangencies_and_all_groups_exist(self):
        lisp = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        # Ø22: radio 3ϕ = 66 mm; las marcas 3 parten en esa tangencia.
        self.assertIn('(cons 10 (list 0.127 7.428 0.0))', lisp)
        self.assertIn('(cons 10 (list 11.469 7.428 0.0))', lisp)
        # Marca 6: el círculo Ø16 queda tangente a la línea del gancho.
        self.assertIn('(cons 10 (list 0.069 0.152 0.0))', lisp)
        self.assertIn('(cons 10 (list 11.527 7.352 0.0))', lisp)
        self.assertEqual(lisp.count('(cons 0 "CIRCLE")'), 190)

    def test_transverse_groups_receive_aligned_dimensions_on_rebar_layers(self):
        lisp = build_zapata_lisp(
            "AA", self.candidate, self.geometry, self.cover, self.rules, "entrada",
            master_path=r"C:\SINCAL\masters\FORMATOS ANOTATIVOS ACAD_2025.dwg",
        )
        self.assertIn("vla-AddDimAligned", lisp)
        self.assertIn('vla-put-StyleName obj "GSG_COTAS"', lisp)
        self.assertIn(
            '"(1) 58%%c22 @20 + (2) 58%%c22 @20" "fi22" "ENTRADA_AA_ZAP"',
            lisp,
        )
        self.assertIn(
            '"(4) 37%%c16 @20 + (5) 37%%c16 @20" "fi16" "ENTRADA_AA_ZAP"',
            lisp,
        )
        self.assertIn('(vla-put-TextOverride obj text)', lisp)
        self.assertNotIn('(vla-put-TextOverride obj " ")', lisp)
        self.assertNotIn('(vla-get-TextStyles database) "RomanD"', lisp)

    def test_real_length_bars_receive_one_mleader_per_mark(self):
        lisp = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        self.assertIn("vla-AddMLeader", lisp)
        self.assertIn('vla-put-StyleName obj "GSG_MLEADER"', lisp)
        self.assertIn('"(1)" "fi22" "ENTRADA_FR_ZAP"', lisp)
        self.assertIn('"(2)" "fi22" "ENTRADA_FR_ZAP"', lisp)
        self.assertNotIn('"(1-2)"', lisp)

    def test_annotation_styles_are_imported_before_old_view_is_deleted(self):
        lisp = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, self.rules, "entrada",
            master_path=r"C:\SINCAL\master.dwg",
        )
        self.assertIn("ObjectDBX.AxDbDocument", lisp)
        self.assertIn("ZWCAD.ZcDbDocument", lisp)
        self.assertIn('sincal:copy-style dbx source-ml target-ml "GSG_MLEADER"', lisp)
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
        rules = tuple(
            replace(rule, hook_cm=140.0) if rule.key == "mesh_x" else rule
            for rule in self.rules
        )
        lisp = build_zapata_lisp(
            "FR", self.candidate, self.geometry, self.cover, rules, "entrada")
        self.assertIn('(list 0.061 6.039 0.0)', lisp)
        self.assertIn('(list 11.535 6.039 0.0)', lisp)

    def test_ee_draws_short_lap_bar_five_millimetres_toward_negative_y(self):
        lisp = build_zapata_lisp(
            "EE", self.candidate, self.geometry, self.cover, self.rules, "entrada")
        self.assertIn("3.75", lisp)
        self.assertIn("3.745", lisp)

    def test_dd_is_reserved_for_walls(self):
        with self.assertRaisesRegex(ZapataCadError, "muros y alas"):
            build_zapata_lisp("DD", self.candidate, self.geometry, self.cover, self.rules, "entrada")


if __name__ == "__main__":
    unittest.main()
