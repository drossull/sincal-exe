from copy import deepcopy
import json
import threading
from urllib.request import Request, urlopen

import pytest

from sincal.web import piles
from sincal.web.rebar import defaults as footing_defaults
from sincal.web.server import Server, Store


def project_data():
    return {"estribos": {
        "incluir_pilotes_dado_estribo_entrada": True,
        "incluir_pilotes_dado_estribo_salida": False,
        "pilotes_dado_estribo_entrada_diametro": 1500,
        "pilotes_dado_estribo_entrada_largo": 10000,
        "dado_muro_frontal_espesor_entrada": 1500,
        "pilotes_dado_estribo_salida_diametro": 1800,
        "pilotes_dado_estribo_salida_largo": 15000,
        "dado_muro_frontal_espesor_salida": 1700,
        "pilotes_dado_estribo_entrada_separacion_transversal": 4000,
    }, "elementos_comunes": {"placas_apoyo": {
        "espesor_recubrimiento_lateral_estribo": 10,
        "espesor_recubrimiento_lateral_cepas": 10,
    }}}


def complete_state():
    state = piles.from_project(project_data(), "entrada")["state"]
    state["cover"].update(lateral_cm=5, inferior_cm=7.5)
    state["longitudinal"].update(diameter_mm=22, spacing_cm=20, hook_cm=40)
    state["ties"].update(diameter_mm=12, hook_90_cm=15, hook_45_cm=12, overrun_cm=20)
    state["confinement_cm"] = 100
    for zone, values in zip(state["zones"], ((None, 250, 10), (250, 900, 20), (900, 1100, 10))):
        zone.update(zip(("from_cm", "to_cm", "spacing_cm"), values))
    return state


def test_import_reads_units_and_keeps_inactive_piles_inactive():
    entry = piles.from_project(project_data(), "entrada")
    exit_ = piles.from_project(project_data(), "salida")
    assert entry["present"] is True
    assert exit_["present"] is False
    assert entry["state"]["geometry"] == {"diameter_cm": 150, "length_cm": 1000, "footing_height_cm": 150}
    assert exit_["state"]["geometry"] == {"diameter_cm": 180, "length_cm": 1500, "footing_height_cm": 170}
    entry["state"]["geometry"]["diameter_cm"] = 99
    assert exit_["state"]["geometry"]["diameter_cm"] == 180


def test_missing_inputs_are_not_filled_from_plates_or_pile_separation():
    state = piles.from_project(project_data(), "entrada")["state"]
    assert state["cover"] == {"lateral_cm": None, "inferior_cm": None}
    assert state["longitudinal"] == {"diameter_mm": None, "spacing_cm": None, "hook_cm": 40}
    assert state["ties"] == {"diameter_mm": None, "hook_90_cm": 15, "hook_45_cm": 25, "overrun_cm": None}
    assert state["confinement_cm"] is None
    assert all(zone["spacing_cm"] is None for zone in state["zones"])
    result = piles.preview(state)
    assert not result["valid"]
    assert result["geometry"]["diameter_cm"] == 150
    assert {"cover.lateral_cm", "cover.inferior_cm"} <= {issue["field"] for issue in result["issues"]}


@pytest.mark.parametrize("flag", [False, None, 0, "false", 1])
def test_only_explicit_boolean_true_activates_pile(flag):
    data = project_data()
    data["estribos"]["incluir_pilotes_dado_estribo_entrada"] = flag
    assert piles.from_project(data, "entrada")["present"] is False


@pytest.mark.parametrize("instance", ["cepa_1", "", None])
def test_import_rejects_other_instances(instance):
    with pytest.raises(ValueError, match="entrada o de salida"):
        piles.from_project(project_data(), instance)


def test_preview_uses_bottom_origin_and_adds_footing_penetration_without_fabrication():
    state = complete_state()
    original = deepcopy(state)
    result = piles.preview(state)
    assert result["valid"] and not result["issues"]
    assert result["configuration_only"] is True
    assert result["calculation_available"] is False
    assert result["zones"][-1]["to_cm"] == 1100
    assert result["first_tie_height_cm"] == pytest.approx(15.2)
    assert result["zones"][0]["from_cm"] == pytest.approx(15.2)
    assert result["geometry"]["length_cm"] == 1000
    assert not {"marks", "details", "quantity", "total_kg"} & result.keys()
    assert state == original


@pytest.mark.parametrize("start,end", [(240, 900), (20, 200)])
def test_overlapping_zones_do_not_reach_preview_geometry(start, end):
    state = complete_state()
    state["zones"][1].update(from_cm=start, to_cm=end)
    result = piles.preview(state)
    assert not result["valid"]
    assert any("superponen" in issue["message"] for issue in result["issues"])
    assert not {"lower", "middle"} & {zone["key"] for zone in result["zones"]}


def test_touching_zones_are_not_an_overlap_or_double_counted_ties():
    result = piles.preview(complete_state())
    assert result["valid"]
    assert len(result["zones"]) == 3
    assert all(set(zone) == {"key", "from_cm", "to_cm", "spacing_cm"} for zone in result["zones"])


def test_gap_warns_without_automatically_filling_or_assigning_ties():
    state = complete_state()
    state["zones"][1]["from_cm"] = 260
    result = piles.preview(state)
    assert result["valid"]
    assert any(item["severity"] == "warning" and "sin separación" in item["message"] for item in result["issues"])
    assert result["zones"][1]["from_cm"] == 260


@pytest.mark.parametrize("field,value", [("from_cm", -1), ("to_cm", 1200), ("spacing_cm", 0)])
def test_zone_bounds_and_positive_spacing_are_checked(field, value):
    state = complete_state()
    state["zones"][2][field] = value
    result = piles.preview(state)
    assert not result["valid"]
    assert "upper" not in {zone["key"] for zone in result["zones"]}
    assert any(item["field"] == "zones.upper" for item in result["issues"])


def test_upside_down_zone_order_is_rejected():
    state = complete_state()
    state["zones"][1].update(from_cm=900, to_cm=1100)
    state["zones"][2].update(from_cm=250, to_cm=900)
    result = piles.preview(state)
    assert not result["valid"]
    assert any("ordenados" in item["message"] for item in result["issues"])


@pytest.mark.parametrize("saved_start", [None, 7.5, 900, -5])
def test_first_tie_overrides_stale_lower_start_without_mutating_input(saved_start):
    state = complete_state()
    state["zones"][0]["from_cm"] = saved_start
    before = deepcopy(state)
    result = piles.preview(state)
    assert result["valid"]
    assert result["first_tie_height_cm"] == pytest.approx(15.2)
    assert result["zones"][0]["from_cm"] == pytest.approx(15.2)
    assert state == before


def test_first_tie_height_does_not_depend_on_horizontal_straight_hook_leg():
    state = complete_state()
    before = piles.preview(state)
    state["longitudinal"]["hook_cm"] = 80
    after = piles.preview(state)
    assert after["first_tie_height_cm"] == before["first_tie_height_cm"]
    assert after["zones"][0]["from_cm"] == before["zones"][0]["from_cm"]


@pytest.mark.parametrize("cover,diameter,expected", [(5, 22, 12.7), (7.5, 12, 11.7), (0, 22, 7.7)])
def test_first_tie_reacts_to_cover_and_longitudinal_diameter(cover, diameter, expected):
    state = complete_state()
    state["cover"]["inferior_cm"] = cover
    state["longitudinal"]["diameter_mm"] = diameter
    result = piles.preview(state)
    assert result["valid"]
    assert result["first_tie_height_cm"] == pytest.approx(expected)
    assert result["zones"][0]["from_cm"] == pytest.approx(expected)


@pytest.mark.parametrize("group,field,value", [
    ("cover", "inferior_cm", None), ("cover", "inferior_cm", -1),
    ("longitudinal", "diameter_mm", None), ("longitudinal", "diameter_mm", 0),
    ("geometry", "length_cm", None),
])
def test_first_tie_stays_pending_without_usable_geometry(group, field, value):
    state = complete_state()
    state[group][field] = value
    state["zones"][0]["from_cm"] = 0  # Must not replace missing prerequisites.
    result = piles.preview(state)
    assert not result["valid"]
    assert result["first_tie_height_cm"] is None
    assert "lower" not in {zone["key"] for zone in result["zones"]}
    assert any(item["field"] == "zones.lower.from_cm" for item in result["issues"])


@pytest.mark.parametrize("length", [10, 15.2])
def test_first_tie_cannot_start_at_or_above_pile_top(length):
    state = complete_state()
    state["geometry"]["length_cm"] = length
    result = piles.preview(state)
    assert not result["valid"]
    assert result["first_tie_height_cm"] is None
    assert result["zones"] == []
    assert any(item["field"] == "first_tie_height_cm" for item in result["issues"])


@pytest.mark.parametrize("index", [1, 2])
def test_no_later_zone_can_begin_below_first_tie(index):
    state = complete_state()
    state["zones"][index]["from_cm"] = 15.1
    result = piles.preview(state)
    assert not result["valid"]
    key = state["zones"][index]["key"]
    assert key not in {zone["key"] for zone in result["zones"]}
    assert any(item["field"] == f"zones.{key}" and "primer estribo" in item["message"] for item in result["issues"])


@pytest.mark.parametrize("end", [10, 15.2])
def test_lower_zone_must_end_above_first_tie(end):
    state = complete_state()
    state["zones"][0]["to_cm"] = end
    result = piles.preview(state)
    assert not result["valid"]
    assert "lower" not in {zone["key"] for zone in result["zones"]}
    assert any(item["field"] == "zones.lower" for item in result["issues"])


def test_penetration_cannot_exceed_footing_height():
    state = complete_state()
    state["confinement_cm"] = 200
    result = piles.preview(state)
    assert not result["valid"]
    assert any(item["field"] == "confinement_cm" for item in result["issues"])


def test_incomplete_cross_field_invalid_drafts_persist_separately(tmp_path):
    payload = {"data": project_data(),
               "identification": {"ot": "TEST", "revision": "A", "structure_name": "Pilotes"},
               "rebar": {"entrada": footing_defaults(), "salida": footing_defaults()}}
    entry = piles.from_project(payload["data"], "entrada")["state"]
    exit_ = piles.from_project(payload["data"], "salida")["state"]
    entry["zones"][0].update(from_cm=300, to_cm=100, spacing_cm=-2)
    entry["longitudinal"]["hook_cm"] = None
    entry["ties"].update(hook_90_cm=0, hook_45_cm=32)
    payload["rebar"]["entrada"]["pile"] = entry
    payload["rebar"]["salida"]["pile"] = exit_
    store = Store(tmp_path / "sessions.db")
    saved = store.save(payload)
    restored = store.get(saved["id"])
    assert restored == payload
    assert restored["rebar"]["entrada"]["pile"]["zones"][0]["spacing_cm"] == -2
    assert restored["rebar"]["salida"]["pile"]["zones"][0]["spacing_cm"] is None


@pytest.mark.parametrize("value", [True, "5", float("nan"), float("inf"), 1e20])
def test_malformed_numbers_cannot_be_saved(value):
    state = piles.defaults()
    state["cover"]["lateral_cm"] = value
    with pytest.raises(ValueError, match="finito"):
        piles.validate_draft(state)


def test_zone_array_is_bounded():
    state = piles.defaults()
    state["zones"].append(deepcopy(state["zones"][0]))
    with pytest.raises(ValueError, match="tres tramos"):
        piles.validate_draft(state)


def test_pile_http_routes_are_configuration_only(tmp_path):
    server = Server(0, tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def post(path, payload):
            request = Request(server.origin + path, data=json.dumps(payload).encode(),
                              headers={"X-Sincal-Token": server.token, "Content-Type": "application/json"})
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read())
        imported = post("/api/rebar/pile/from-project", {"project": project_data(), "instance_key": "entrada"})
        assert imported["present"]
        result = post("/api/rebar/pile/preview", {"state": imported["state"]})
        assert result["configuration_only"] and not result["calculation_available"]
        assert result["geometry"]["length_cm"] == 1000
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
