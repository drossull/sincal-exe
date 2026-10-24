import unittest

from sincal.cad.moldajes import MoldajeContext, parse_moldaje_detection


class MoldajeDetectionTests(unittest.TestCase):
    def test_parses_only_expected_footing_layers(self):
        result = parse_moldaje_detection("""SINCAL_MOLDAJES_V1
META|INSUNITS|6
CANDIDATE|FR_ZAP|1A2B|OK|4|18.500000
VERTICES|FR_ZAP|1A2B|0,0;10,0;10,2;0,2
CANDIDATE|AA_ZAP|1A2C|OPEN|4|0.000000
CANDIDATE|OTRA_CAPA|1A2D|OK|4|10.000000
""")

        self.assertTrue(result.uses_metres)
        self.assertEqual(len(result.candidates), 2)
        self.assertTrue(result.for_layer("FR_ZAP")[0].is_valid)
        self.assertEqual(result.for_layer("FR_ZAP")[0].vertices[2], (10.0, 2.0))
        self.assertFalse(result.for_layer("AA_ZAP")[0].is_valid)

    def test_rejects_invalid_metadata_without_crashing(self):
        result = parse_moldaje_detection("META|INSUNITS|sin-unidad\nCANDIDATE|FF_ZAP|abc|ARC|3|2.2")

        self.assertFalse(result.uses_metres)
        self.assertEqual(result.for_layer("FF_ZAP")[0].handle, "ABC")
        self.assertFalse(result.for_layer("FF_ZAP")[0].is_valid)

    def test_accepts_dynamic_layers_and_filters_them_case_insensitively(self):
        result = parse_moldaje_detection("""SINCAL_MOLDAJES_V2
META|INSUNITS|6
CANDIDATE|fr_mfr|20aa|OK|5|12.5
CANDIDATE|FR_ZAP|20ab|OK|4|8.0
""", allowed_layers=("FR_MFR", "AA_MFR"))

        self.assertEqual(result.protocol_version, 2)
        self.assertEqual(result.allowed_layers, ("FR_MFR", "AA_MFR"))
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.for_layer("fr_mfr")[0].handle, "20AA")

    def test_models_open_closed_and_curved_contours_without_breaking_legacy_validity(self):
        result = parse_moldaje_detection("""SINCAL_MOLDAJES_V2
CANDIDATE|AA_MFR|A1|OPEN|4|0
VERTICES|AA_MFR|A1|0,0;0,2;1,2;1,0
GEOMETRY|AA_MFR|A1|OPEN|1
BULGES|AA_MFR|A1|0;0.25;0;0
CANDIDATE|BB_MFR|B2|OK|4|7.5
GEOMETRY|BB_MFR|B2|CLOSED|0
""", allowed_layers=("AA_MFR", "BB_MFR"))

        open_candidate = result.for_layer("AA_MFR")[0]
        self.assertEqual(open_candidate.contour_kind, "open")
        self.assertTrue(open_candidate.has_arcs)
        self.assertEqual(open_candidate.bulges, (0.0, 0.25, 0.0, 0.0))
        self.assertFalse(open_candidate.is_valid)
        self.assertFalse(open_candidate.is_usable(allow_open=True))
        self.assertTrue(open_candidate.is_usable(allow_open=True, allow_arcs=True))

        closed_candidate = result.for_layer("BB_MFR")[0]
        self.assertEqual(closed_candidate.contour_kind, "closed")
        self.assertTrue(closed_candidate.is_valid)
        self.assertTrue(closed_candidate.is_usable())

    def test_attaches_detection_and_candidate_context_with_caller_precedence(self):
        result = parse_moldaje_detection("""SINCAL_MOLDAJES_V2
META|ELEMENT|muro
META|INSTANCE|salida-antigua
META|VIEW|FR
CANDIDATE|FR_MFR|C3|OK|4|20
CONTEXT|FR_MFR|C3|muro-frontal|salida|AA
CANDIDATE|AA_MFR|C4|OPEN|3|0
CONTEXT|AA_MFR|C4|muro-frontal|salida|AA
""", allowed_layers=("FR_MFR", "AA_MFR"), context={
            "element": "muro-frontal",
            "instance": "entrada",
        })

        self.assertEqual(
            result.context,
            MoldajeContext(element="muro-frontal", instance="entrada", view="FR"),
        )
        fr = result.for_layer("FR_MFR")[0]
        aa = result.for_layer("AA_MFR")[0]
        self.assertEqual(fr.context, MoldajeContext("muro-frontal", "entrada", "AA"))
        self.assertEqual(aa.context, MoldajeContext("muro-frontal", "entrada", "AA"))
        self.assertEqual(result.for_context(instance="ENTRADA", view="aa"), (fr, aa))

    def test_ignores_bad_optional_geometry_records(self):
        result = parse_moldaje_detection("""CANDIDATE|PLAN_LOS|D1|OPEN|2|0
VERTICES|PLAN_LOS|D1|0,0;invalido
BULGES|PLAN_LOS|D1|0;no-numero
""", allowed_layers=("PLAN_LOS",))

        candidate = result.candidates[0]
        self.assertEqual(candidate.vertices, ())
        self.assertEqual(candidate.bulges, ())
        self.assertTrue(candidate.is_usable(allow_open=True))


if __name__ == "__main__":
    unittest.main()
