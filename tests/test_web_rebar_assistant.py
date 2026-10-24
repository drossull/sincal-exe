from unittest.mock import Mock, patch

import pytest

from sincal.cad.moldajes import MoldajeContext, parse_moldaje_detection
from sincal.rebar.catalog import BRIDGE_REBAR_CATALOG
from sincal.web.rebar import (
    assistant_catalog,
    defaults,
    resolve_assistant_element,
    summarize_element_detection,
)
from sincal.web.services import Services


def project_data():
    return {
        "estribos": {
            "tipo_estribo_entrada": "muro_lleno",
            "tipo_estribo_salida": "muro_lleno",
            "incluir_consola_frontal_entrada": True,
            "incluir_consola_frontal_salida": False,
        },
        "cepas": {"lista": [{"nombre": "Cepa 1"}]},
        "elementos_comunes": {
            "vigas": {"num_vigas": 1},
            "travesanos": {"espesor_travesano": 250},
        },
        "tableros": [{
            "nombre_grupo_tablero": "Tablero 1",
            "usar_grupo_tablero": True,
        }],
    }


def test_assistant_catalog_serializes_full_hierarchy_and_optional_presence():
    result = assistant_catalog(project_data())
    assert [item["label"] for item in result["structures"]] == [
        "ESTRIBO", "CEPA", "VIGA", "TRAVESAÑO", "LOSA",
    ]
    abutment = result["structures"][0]
    assert [item["key"] for item in abutment["instances"]] == ["entrada", "salida"]
    entry = {item["key"]: item for item in abutment["instances"][0]["elements"]}
    exit_ = {item["key"]: item for item in abutment["instances"][1]["elements"]}
    assert entry["abutment.front_console"]["present"] is True
    assert exit_["abutment.front_console"]["present"] is False
    assert exit_["abutment.front_console"]["optional"] is True
    assert entry["abutment.footing"]["layers"][-1] == {
        "view": "FF", "layer": "FF_ZAP", "contour": "either", "detail": False,
    }
    assert entry["abutment.footing"]["views"] == ['FR', 'AA', 'BB', 'CC', 'EE']
    assert "orthogonal_mesh" in entry["abutment.footing"]["recipes"]


def test_assistant_catalog_keeps_structures_without_instances():
    result = assistant_catalog({})
    assert len(result["structures"]) == 5
    assert all(item["instances"] == [] for item in result["structures"])


def test_context_resolution_rejects_wrong_absent_and_ambiguous_instances():
    with pytest.raises(ValueError, match="no pertenece"):
        resolve_assistant_element(
            project_data(), "beam", "viga_01", "abutment.footing",
        )
    with pytest.raises(ValueError, match="opcional"):
        resolve_assistant_element(
            project_data(), "abutment", "salida", "abutment.front_console",
        )
    duplicated = project_data()
    duplicated["cepas"]["lista"] = [{"nombre": "Cepa 1"}, {"nombre": "Cepa 1"}]
    with pytest.raises(ValueError, match="ambigua"):
        resolve_assistant_element(duplicated, "pier", "cepa_1", "pier.cap")


def test_detection_summary_reports_assignments_missing_ambiguity_and_context():
    context = MoldajeContext("abutment.footing", "entrada")
    detection = parse_moldaje_detection("""SINCAL_MOLDAJES_V2
META|INSUNITS|6
CANDIDATE|FR_ZAP|A1|OK|4|10
CANDIDATE|AA_ZAP|A2|OK|4|10
CANDIDATE|AA_ZAP|A3|OK|4|11
CANDIDATE|CC_ZAP|A4|OPEN|3|0
CANDIDATE|FF_ZAP|A5|ARC|4|12
GEOMETRY|FF_ZAP|A5|CLOSED|1
""", allowed_layers=("FR_ZAP", "AA_ZAP", "BB_ZAP", "CC_ZAP", "FF_ZAP"),
        context=context)
    result = summarize_element_detection(
        BRIDGE_REBAR_CATALOG.element("abutment.footing"), detection, selection="ok",
    )
    assert result["assignments"] == {"FR_ZAP": "A1", "CC_ZAP": "A4", "FF_ZAP": "A5"}
    assert result["missing_layers"] == ["BB_ZAP"]
    assert result["ambiguous_layers"] == ["AA_ZAP"]
    assert result["curved_layers"] == ["FF_ZAP"]
    assert result["detection_complete"] is False
    assert result["generation_ready"] is False
    assert result["candidates"][0]["context"] == {
        "element": "abutment.footing", "instance": "entrada", "view": "",
    }


def test_detection_summary_separates_detection_from_generation_readiness():
    layers = ("FR_ZAP", "AA_ZAP", "BB_ZAP", "CC_ZAP", "FF_ZAP")
    rows = "\n".join(f"CANDIDATE|{layer}|H{index}|OK|4|10"
                     for index, layer in enumerate(layers, 1))
    closed = parse_moldaje_detection(
        f"SINCAL_MOLDAJES_V2\nMETA|INSUNITS|6\n{rows}",
        allowed_layers=layers,
    )
    footing = BRIDGE_REBAR_CATALOG.element("abutment.footing")
    ready = summarize_element_detection(footing, closed, selection="ok")
    assert ready["detection_complete"] is True
    assert ready["generation_ready"] is True
    assert set(ready["assignments"]) == set(layers)

    wrong_units = parse_moldaje_detection(
        f"SINCAL_MOLDAJES_V2\nMETA|INSUNITS|4\n{rows}",
        allowed_layers=layers,
    )
    rejected = summarize_element_detection(footing, wrong_units, selection="ok")
    assert rejected["assignments"] == {}
    assert rejected["detection_complete"] is False
    assert rejected["generation_ready"] is False

    cancelled = summarize_element_detection(footing, closed, selection="cancelled")
    assert cancelled["assignments"] == {}
    assert cancelled["detection_complete"] is False
    assert cancelled["generation_ready"] is False

    beam_layers = ("EL_VIG", "AA_VIG", "BB_VIG", "CC_VIG")
    open_rows = "\n".join(f"CANDIDATE|{layer}|B{index}|OPEN|3|0"
                          for index, layer in enumerate(beam_layers, 1))
    open_beam = parse_moldaje_detection(
        f"SINCAL_MOLDAJES_V2\nMETA|INSUNITS|6\n{open_rows}",
        allowed_layers=beam_layers,
    )
    detected = summarize_element_detection(
        BRIDGE_REBAR_CATALOG.element("beam.beam"), open_beam, selection="ok",
    )
    assert detected["detection_complete"] is True
    assert detected["generation_ready"] is False
    assert set(detected["assignments"]) == set(beam_layers)


def test_prepare_layers_job_uses_catalog_and_existing_cad_guard(tmp_path):
    service = Services(tmp_path)
    job = Mock(id="a" * 32)
    expected = {"status": "ready", "instance": "42"}
    try:
        with patch.object(service, "cad", return_value={"message": "CAD listo"}) as cad:
            result = service.prepare_rebar_layers(job, {
                "project": project_data(), "structure_key": "abutment",
                "instance_key": "entrada", "element_key": "abutment.footing",
                "expected": expected,
            })
        assert result["layers"] == ["FR_ZAP", "AA_ZAP", "BB_ZAP", "CC_ZAP", "FF_ZAP"]
        source = (service.runtime / job.id / "operation.lsp").read_text(encoding="utf-8")
        assert "c:SINCAL-PREPARAR-ARMADURAS" in source
        assert '"FF_ZAP"' in source and '"EE_ZAP"' not in source
        assert cad.call_args.args[1] == expected
    finally:
        service.jobs.close()


def test_contextual_detection_requires_selection_and_keeps_instance_identity(tmp_path):
    service = Services(tmp_path)
    job = Mock(id="b" * 32)
    expected = {"status": "ready", "instance": "42"}
    payload = {
        "project": project_data(), "structure_key": "abutment",
        "instance_key": "entrada", "element_key": "abutment.footing",
        "expected": expected,
    }
    try:
        with pytest.raises(ValueError, match="selección manual"):
            service.detect_rebar_element(job, payload)

        def cad(_job, received, _command, *_args, **_kwargs):
            assert received == expected
            (service.runtime / job.id / "moldajes.txt").write_text("""SINCAL_MOLDAJES_V2
META|INSUNITS|6
META|SELECTION|OK
CANDIDATE|FR_ZAP|A1|OK|4|10
CANDIDATE|AA_ZAP|A2|OK|4|10
CANDIDATE|BB_ZAP|A3|OK|4|10
CANDIDATE|CC_ZAP|A4|OK|4|10
CANDIDATE|FF_ZAP|A5|OK|4|10
""", encoding="utf-8")
            return {"message": "ok"}

        with patch.object(service, "cad", side_effect=cad):
            result = service.detect_rebar_element(job, {**payload, "interactive": True})
        assert result["selection"] == "ok"
        assert result["uses_metres"] is True
        assert result["missing_layers"] == []
        assert result["assignments"]["FF_ZAP"] == "A5"
        assert result["detection_complete"] is True
        assert result["generation_ready"] is True
        assert all(candidate["context"]["instance"] == "entrada"
                   for candidate in result["candidates"])
        source = (service.runtime / job.id / "operation.lsp").read_text(encoding="utf-8")
        assert "Seleccione los moldajes del elemento" in source
        assert "META|INSTANCE|entrada" in source
    finally:
        service.jobs.close()


def test_cad_rebar_accepts_legacy_ee_request_as_ff_only(tmp_path):
    service = Services(tmp_path)
    expected = {"status": "ready", "instance": "42"}
    detection = parse_moldaje_detection("""SINCAL_MOLDAJES_V2
META|INSUNITS|6
CANDIDATE|FF_ZAP|F1|OK|4|10
VERTICES|FF_ZAP|F1|0,0;2,0;2,5;0,5
""", allowed_layers=("FF_ZAP",),
        context=MoldajeContext("abutment.footing", "entrada"))
    service.detections["det"] = (expected, detection)
    job = Mock(id="c" * 32)
    try:
        with patch("sincal.cad.zapata_views.build_zapata_lisp", return_value="(princ)") as build, \
             patch("sincal.runtime.ruta_recurso", return_value="master.dwg"), \
             patch.object(service, "lisp", return_value="operation.lsp"), \
             patch.object(service, "cad", return_value={"message": "ok"}):
            service.rebar(job, {
                "state": defaults(), "abutment": "entrada", "view": "EE",
                "handle": "F1", "detection": "det",
            })
        assert build.call_args.args[0] == "FF"
        assert build.call_args.args[1].layer == "FF_ZAP"
    finally:
        service.jobs.close()
