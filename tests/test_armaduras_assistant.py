import inspect
import unittest
from pathlib import Path

from sincal.ui.tabs.armaduras_assistant import (
    ArmaturesAssistantCallbacks,
    ArmaturesAssistantDashboard,
    ArmaturesAssistantModel,
    STATUS_ERROR,
    STATUS_READY,
    StructuralElement,
    default_bridge_elements,
    project_bridge_elements,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sincal" / "ui" / "tabs" / "armaduras_assistant.py"


class ArmaturesAssistantModelTests(unittest.TestCase):
    def test_default_hierarchy_contains_the_complete_bridge_outline(self):
        model = ArmaturesAssistantModel(default_bridge_elements())

        self.assertEqual(
            [element.id for element in model.roots()],
            ["abutments", "piers", "beams", "crossbeams", "slab"],
        )
        self.assertIn(
            "abutment.entry.footing",
            [element.id for element in model.children("abutment.entry")],
        )
        self.assertTrue(model.get("abutment.exit.counterfort").optional)
        self.assertIn(
            "crossbeams.intermediate",
            [element.id for element in model.children("crossbeams")],
        )

    def test_model_updates_status_and_lists_only_ready_elements(self):
        model = ArmaturesAssistantModel((
            StructuralElement("root", "Estribo"),
            StructuralElement("zapata", "Zapata", parent_id="root"),
            StructuralElement("muro", "Muro", parent_id="root"),
        ))

        model.update("zapata", status=STATUS_READY, message="Moldajes confirmados")
        model.update("muro", status=STATUS_ERROR)

        self.assertEqual([element.id for element in model.ready_elements()], ["zapata"])
        self.assertEqual(model.status_counts()[STATUS_ERROR], 1)
        self.assertEqual(model.get("zapata").message, "Moldajes confirmados")

    def test_model_rejects_missing_parents_duplicates_and_cycles(self):
        with self.assertRaisesRegex(ValueError, "no existe"):
            ArmaturesAssistantModel((StructuralElement("child", "Hijo", "missing"),))
        with self.assertRaisesRegex(ValueError, "duplicado"):
            ArmaturesAssistantModel((
                StructuralElement("same", "Uno"),
                StructuralElement("same", "Dos"),
            ))
        with self.assertRaisesRegex(ValueError, "cíclica"):
            ArmaturesAssistantModel((
                StructuralElement("a", "A", "b"),
                StructuralElement("b", "B", "a"),
            ))

    def test_project_tree_resolves_instances_and_optional_elements(self):
        elements = project_bridge_elements({
            "estribos": {
                "tipo_estribo_entrada": "muro_lleno",
                "tipo_estribo_salida": "muro_lleno",
                "incluir_pilotes_dado_estribo_entrada": False,
                "incluir_pilotes_dado_estribo_salida": True,
            },
            "cepas": {"lista": [{"nombre": "Cepa_01"}]},
            "elementos_comunes": {
                "vigas": {"num_vigas": 2},
                "travesanos": {"espesor_travesano": 250},
            },
            "tableros": [{
                "nombre_grupo_tablero": "Tablero_01",
                "usar_grupo_tablero": True,
            }],
        })
        model = ArmaturesAssistantModel(elements)
        self.assertIn("instance:beam:viga_02", {item.id for item in model.elements})
        self.assertEqual(
            model.get("element:abutment:entrada:abutment.pile").status,
            "not_applicable",
        )
        self.assertEqual(
            model.get("element:abutment:salida:abutment.pile").status,
            "pending",
        )
        self.assertEqual(
            model.get("element:abutment:entrada:abutment.left_wing").status,
            "pending",
        )


class ArmaturesAssistantStructureTests(unittest.TestCase):
    def test_dashboard_exposes_injected_actions_without_creating_a_tk_root(self):
        signature = inspect.signature(ArmaturesAssistantDashboard.__init__)
        callback_fields = ArmaturesAssistantCallbacks.__dataclass_fields__

        self.assertIn("model", signature.parameters)
        self.assertIn("callbacks", signature.parameters)
        self.assertEqual(
            set(callback_fields),
            {"prepare_drawing", "analyze_moldajes", "generate_ready", "select_element"},
        )

    def test_dashboard_source_contains_the_three_primary_actions_and_status_tree(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("ttk.Treeview(", source)
        self.assertIn('text="Preparar dibujo"', source)
        self.assertIn('text="Analizar moldajes"', source)
        self.assertIn('text="Revisar y generar"', source)
        self.assertIn('detail.bind("<Configure>", self._resize_detail_wrap', source)
        self.assertIn("ShadowButton(", source)
        self.assertIn("def set_summary(", source)
        self.assertIn("def update_element(", source)


if __name__ == "__main__":
    unittest.main()
