import unittest

from sincal_cad_moldajes import MoldajeCandidate
from sincal_rebar_model import Cover, ZapataGeometry, default_zapata_rules
from sincal_zapata_cad import ZapataCadError, build_zapata_lisp, inward_offset


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

    def test_dd_is_reserved_for_walls(self):
        with self.assertRaisesRegex(ZapataCadError, "muros y alas"):
            build_zapata_lisp("DD", self.candidate, self.geometry, self.cover, self.rules, "entrada")


if __name__ == "__main__":
    unittest.main()
