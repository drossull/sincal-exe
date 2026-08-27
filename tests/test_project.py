import json

from sincal.project import (
    ProjectContext, format_project_value, project_sections, project_text,
)


def sample_project():
    return {
        "version": "1.0",
        "parametros_generales": {
            "angulo_esviaje_puente": 7.0,
            "coord_norte": 3277783.572,
        },
        "elementos_comunes": {
            "losa": {"espesor_losa": 220.0},
        },
        "cepas": {
            "parametros_globales": {"altura_cabezal": 2100.0},
            "lista": [{"nombre": "Cepa_01", "largo_columnas": 4000.0}],
        },
        "estribos": {
            "tipo_estribo_entrada": "transparente",
            "dado_muro_frontal_ancho_entrada": 11800.0,
            "tipo_estribo_salida": "muro lleno",
            "dado_muro_frontal_ancho_salida": 12000.0,
            "incluir_losas_acceso": True,
        },
        "tableros": [{"nombre_grupo_tablero": "Tablero_01", "largo_losa": 25676.0}],
        "materiales": {"hormigon_losa": "G30"},
        "planos": {"modo_cotas_estribo": "semantico"},
        "meta": {"modified": "2026-08-06"},
    }


def test_project_context_persists_identification_without_touching_source(tmp_path):
    source = tmp_path / "bridge.json"
    original = sample_project()
    source.write_text(json.dumps(original), encoding="utf-8")
    state = tmp_path / "project_state.json"
    context = ProjectContext(state)
    context.load(source, {
        "ot": "G130", "revision": "F", "structure_name": "Puente Primavera",
    })
    context.update_identification(revision="G")

    assert json.loads(source.read_text(encoding="utf-8")) == original
    assert context.complete_identification
    assert ProjectContext(state).last_project_path() == str(source)
    assert ProjectContext(state).identification_for(source)["revision"] == "G"


def test_project_sections_cover_semantic_hierarchy_and_both_abutments():
    sections = project_sections(sample_project())
    anchors = [section["anchor"] for section in sections]
    assert anchors == [
        "resumen", "generales", "superestructura", "estribo_entrada",
        "estribo_salida", "cepas", "materiales", "planos", "metadatos",
    ]
    entry_rows = sections[3]["groups"][0]["rows"]
    exit_rows = sections[4]["groups"][0]["rows"]
    assert any("11\u00a0800 mm · 11,8 m" in row[2] for row in entry_rows)
    assert any("12\u00a0000 mm · 12 m" in row[2] for row in exit_rows)
    assert any("Tablero 1" in group["title"] for group in sections[2]["groups"])


def test_units_keep_original_value_and_add_conversion():
    assert format_project_value("estribos.ancho", 11800.0) == "11\u00a0800 mm · 11,8 m"
    assert format_project_value("parametros.coord_norte", 3277783.572).endswith(" PTL")
    assert format_project_value("tablero.pendiente_longitudinal", 0.0035) == "0,0035 · 0,35 %"


def test_text_export_contains_identity_source_and_all_major_sections(tmp_path):
    source = tmp_path / "bridge.json"
    source.write_text(json.dumps(sample_project()), encoding="utf-8")
    context = ProjectContext(tmp_path / "state.json").load(source, {
        "ot": "OT-42", "revision": "B", "structure_name": "Puente Norte",
    })
    report = project_text(context)
    assert "OT: OT-42" in report
    assert "Nombre de estructura: Puente Norte" in report
    assert "sistema local PTL" in report
    assert "SUPERESTRUCTURA" in report
    assert "ESTRIBO DE ENTRADA" in report
    assert "Cepa 1 · Cepa_01" in report
