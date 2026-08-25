import unittest

from sincal_cad_moldajes import parse_moldaje_detection


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
        result = parse_moldaje_detection("META|INSUNITS|sin-unidad\nCANDIDATE|EE_ZAP|abc|ARC|3|2.2")

        self.assertFalse(result.uses_metres)
        self.assertEqual(result.for_layer("EE_ZAP")[0].handle, "ABC")
        self.assertFalse(result.for_layer("EE_ZAP")[0].is_valid)


if __name__ == "__main__":
    unittest.main()
