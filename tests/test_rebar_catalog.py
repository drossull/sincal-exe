import dataclasses
import unittest

from sincal.rebar.catalog import (
    BRIDGE_REBAR_CATALOG,
    ContourPolicy,
    PresenceKind,
    RecipeFamily,
)


def sample_project():
    return {
        "estribos": {
            "tipo_estribo_entrada": "muro_lleno",
            "tipo_estribo_salida": "muro_lleno",
            "incluir_topes_interiores_estribos": True,
            "incluir_consola_frontal_entrada": True,
            "incluir_consola_frontal_salida": False,
            "incluir_aletas_estribo_entrada": True,
            "incluir_aletas_estribo_salida": False,
            "incluir_pilotes_dado_estribo_entrada": False,
            "incluir_pilotes_dado_estribo_salida": True,
            "incluir_contrafuertes_mura_ala_entrada": True,
            "incluir_contrafuertes_mura_ala_salida": False,
        },
        "cepas": {"lista": [{"nombre": "Cepa_01"}, {"nombre": "Cepa Norte"}]},
        "elementos_comunes": {
            "vigas": {"num_vigas": 3},
            "travesanos": {"espesor_travesano": 250},
        },
        "tableros": [
            {"nombre_grupo_tablero": "Tablero_01", "usar_grupo_tablero": True},
            {"nombre_grupo_tablero": "Descartado", "usar_grupo_tablero": False},
        ],
    }


class BridgeRebarCatalogTests(unittest.TestCase):
    def test_catalog_is_immutable_and_has_the_five_bridge_families(self):
        self.assertTrue(dataclasses.is_dataclass(BRIDGE_REBAR_CATALOG))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            BRIDGE_REBAR_CATALOG.structures = ()
        self.assertEqual(
            tuple(item.label for item in BRIDGE_REBAR_CATALOG.structures),
            ("ESTRIBO", "CEPA", "VIGA", "TRAVESAÑO", "LOSA"),
        )
        self.assertEqual(
            tuple(item.folder for item in BRIDGE_REBAR_CATALOG.structures),
            ("1-ESTRIBO", "2-CEPA", "3-VIGA", "4-TRAVESAÑO", "5-LOSA"),
        )

    def test_resolves_instances_from_the_project_json(self):
        data = sample_project()
        self.assertEqual(
            tuple(item.key for item in BRIDGE_REBAR_CATALOG.resolve_instances("abutment", data)),
            ("entrada", "salida"),
        )
        self.assertEqual(
            tuple(item.label for item in BRIDGE_REBAR_CATALOG.resolve_instances("pier", data)),
            ("Cepa_01", "Cepa Norte"),
        )
        self.assertEqual(
            tuple(item.key for item in BRIDGE_REBAR_CATALOG.resolve_instances("beam", data)),
            ("viga_01", "viga_02", "viga_03"),
        )
        self.assertEqual(len(BRIDGE_REBAR_CATALOG.resolve_instances("crossbeam", data)), 1)
        self.assertEqual(
            tuple(item.label for item in BRIDGE_REBAR_CATALOG.resolve_instances("slab", data)),
            ("Tablero_01",),
        )

    def test_optional_abutment_elements_follow_each_json_side(self):
        data = sample_project()
        entry = {
            item.key for item in BRIDGE_REBAR_CATALOG.elements_for(
                "abutment", data, "entrada", present_only=True
            )
        }
        exit_ = {
            item.key for item in BRIDGE_REBAR_CATALOG.elements_for(
                "abutment", data, "salida", present_only=True
            )
        }
        self.assertIn("abutment.front_console", entry)
        self.assertNotIn("abutment.front_console", exit_)
        self.assertIn("abutment.left_wing", entry)
        self.assertIn("abutment.left_wing", exit_)
        self.assertIn("abutment.right_wing", entry)
        self.assertIn("abutment.right_wing", exit_)
        self.assertIn("abutment.front_stop", entry)
        self.assertIn("abutment.front_stop", exit_)
        self.assertNotIn("abutment.pile", entry)
        self.assertIn("abutment.pile", exit_)
        self.assertIn("abutment.counterfort", entry)
        self.assertNotIn("abutment.counterfort", exit_)
        self.assertIn("abutment.front_wall", entry)
        self.assertIn("abutment.back_console", exit_)

    def test_layer_matrix_matches_the_approved_names(self):
        footing = BRIDGE_REBAR_CATALOG.element("abutment.footing")
        self.assertEqual(
            footing.layer_names,
            ("FR_ZAP", "AA_ZAP", "BB_ZAP", "CC_ZAP", "FF_ZAP"),
        )
        self.assertNotIn("DD_ZAP", footing.layer_names)
        self.assertNotIn("EE_ZAP", footing.layer_names)
        self.assertEqual(
            BRIDGE_REBAR_CATALOG.element("abutment.front_wall").layer_names,
            ("FR_MFR", "AA_MFR", "BB_MFR", "CC_MFR", "DD_MFR"),
        )
        self.assertEqual(
            BRIDGE_REBAR_CATALOG.element("abutment.back_wall").layer_names,
            ("FR_ESP", "AA_ESP", "BB_ESP", "CC_ESP", "EE_ESP"),
        )
        self.assertEqual(
            BRIDGE_REBAR_CATALOG.element("beam.beam").layer_names,
            ("EL_VIG", "AA_VIG", "BB_VIG", "CC_VIG"),
        )
        self.assertEqual(
            BRIDGE_REBAR_CATALOG.element("slab.slab").layer_names,
            ("PLAN_LOS", "SECC_LOS"),
        )

    def test_shared_layers_are_unique_only_in_the_creation_list(self):
        self.assertIn("FR_PIL", BRIDGE_REBAR_CATALOG.element("abutment.pile").layer_names)
        self.assertIn("FR_PIL", BRIDGE_REBAR_CATALOG.element("pier.pile").layer_names)
        layers = BRIDGE_REBAR_CATALOG.layer_names()
        self.assertEqual(len(layers), len(set(layers)))
        self.assertEqual(layers.count("FR_PIL"), 1)

    def test_elements_advertise_generic_recipes_without_design_values(self):
        footing = BRIDGE_REBAR_CATALOG.element("abutment.footing")
        pile = BRIDGE_REBAR_CATALOG.element("pier.pile")
        beam = BRIDGE_REBAR_CATALOG.element("beam.beam")
        self.assertIn(RecipeFamily.ORTHOGONAL_MESH, footing.recipes)
        self.assertIn(RecipeFamily.TRANSVERSE_TIES, pile.recipes)
        self.assertIn(RecipeFamily.CLOSED_STIRRUPS, beam.recipes)
        self.assertTrue(all(layer.contour is ContourPolicy.EITHER for layer in footing.layers))

    def test_pending_and_manual_optional_definitions_are_explicit(self):
        counterfort = BRIDGE_REBAR_CATALOG.element("abutment.counterfort")
        console = BRIDGE_REBAR_CATALOG.element("pier.console")
        self.assertTrue(counterfort.definition_pending)
        self.assertEqual(counterfort.layers, ())
        self.assertTrue(counterfort.optional)
        self.assertEqual(console.presence.kind, PresenceKind.MANUAL)
        self.assertFalse(console.presence.resolve(sample_project(), "cepa_01"))

    def test_unknown_keys_fail_explicitly(self):
        with self.assertRaises(KeyError):
            BRIDGE_REBAR_CATALOG.structure("desconocido")
        with self.assertRaises(KeyError):
            BRIDGE_REBAR_CATALOG.element("desconocido")


if __name__ == "__main__":
    unittest.main()
