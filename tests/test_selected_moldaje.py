import pytest

from sincal.cad.moldajes import MoldajeContext
from sincal.cad.selected_moldaje import (
    build_selection_lisp,
    parse_selected_moldaje,
)


CONTEXT = MoldajeContext("abutment", "entrada", "FR")


def _header(*, units=6, selection="OK", expected=1, error=None, keys=None):
    if keys is None:
        keys = ["abutment.footing"] if expected == 1 else [
            "abutment.footing",
            "abutment.front_wall",
        ]
    lines = [
        "SINCAL_SELECTED_MOLDAJE_V1",
        f"META|INSUNITS|{units}",
        f"META|SELECTION|{selection}",
        "META|ELEMENT|abutment",
        "META|INSTANCE|entrada",
        "META|VIEW|FR",
        f"META|EXPECTED|{expected}",
        f"META|ELEMENTS|{';'.join(keys)}",
    ]
    if error is not None:
        lines.append(f"META|ERROR|{error}")
    return "\n".join(lines)


def test_lisp_guides_two_wcs_corners_per_element_without_scanning_or_com():
    lisp = build_selection_lisp(
        r"C:\tmp\seleccion.txt",
        CONTEXT,
        [
            {"key": "abutment.footing", "label": "Zapata"},
            {"key": "abutment.pile", "label": "Pilote opcional"},
        ],
    )

    assert "(defun c:SINCAL-SELECCIONAR-MOLDAJE" in lisp
    assert "SUPERIOR IZQUIERDA" in lisp
    assert "INFERIOR DERECHA" in lisp
    assert "getpoint" in lisp
    assert "getcorner" in lisp
    assert "(trans first 1 0)" in lisp
    assert "(trans opposite 1 0)" in lisp
    assert '("abutment.footing" "Zapata")' in lisp
    assert '("abutment.pile" "Pilote opcional")' in lisp
    assert "META|EXPECTED|2" in lisp
    assert "META|ELEMENTS|abutment.footing;abutment.pile" in lisp
    assert "ssget" not in lisp.lower()
    assert "modelspace" not in lisp.lower()
    assert "vla-" not in lisp.lower()
    assert "vlax-" not in lisp.lower()
    assert "(cons 8" not in lisp
    assert "seleccion.txt.part" in lisp


def test_lisp_escapes_labels_and_context_and_has_safe_abort_result():
    lisp = build_selection_lisp(
        r'C:\tmp\vista "fr".txt',
        MoldajeContext("abutment", "entrada", "A-A"),
        [{"key": "abutment.footing", "label": 'Zapata "norte" \\ principal\nA'}],
    )

    assert r'Zapata \"norte\" \\ principal A' in lisp
    assert r'C:\\tmp\\vista \"fr\".txt.part' in lisp
    assert "META|SELECTION|ERROR" in lisp
    assert "META|ERROR|COMMAND_ABORTED" in lisp
    assert "META|ELEMENT|abutment" in lisp
    assert "META|INSTANCE|entrada" in lisp
    assert "META|VIEW|A-A" in lisp


def test_parse_rectangle_in_metres_builds_four_raw_wcs_vertices_without_assuming_scale():
    text = _header() + "\nRECTANGLE|abutment.footing|0;5;2|10;0;2"

    result = parse_selected_moldaje(text, CONTEXT)

    assert result.selection == "ok"
    assert result.uses_metres is True
    assert result.rectangles["abutment.footing"] == (
        (0.0, 5.0, 2.0),
        (10.0, 5.0, 2.0),
        (10.0, 0.0, 2.0),
        (0.0, 0.0, 2.0),
    )
    assert result.candidate is None


@pytest.mark.parametrize(("units", "uses_metres"), [(0, False), (4, False), (6, True)])
def test_parse_preserves_scale_without_conversion_or_generation(units, uses_metres):
    text = _header(units=units) + "\nRECTANGLE|abutment.footing|0;7500;0|11596;0;0"

    result = parse_selected_moldaje(text, CONTEXT)

    assert result.insunits == units
    assert result.uses_metres is uses_metres
    assert result.rectangles["abutment.footing"][1][0] == 11596.0
    assert result.rectangles["abutment.footing"][2][1] == 0.0
    assert result.candidate is None


def test_parse_preserves_sequence_for_multiple_elements():
    text = _header(expected=2) + "\n" + "\n".join([
        "RECTANGLE|abutment.footing|0;5;0|10;0;0",
        "RECTANGLE|abutment.front_wall|2;9;0|8;5;0",
    ])

    result = parse_selected_moldaje(text, CONTEXT)

    assert list(result.rectangles) == ["abutment.footing", "abutment.front_wall"]
    assert result.rectangles["abutment.front_wall"] == (
        (2.0, 9.0, 0.0),
        (8.0, 9.0, 0.0),
        (8.0, 5.0, 0.0),
        (2.0, 5.0, 0.0),
    )


@pytest.mark.parametrize(
    ("selection", "error"),
    [
        ("CANCELLED", "Cancelado en abutment.footing."),
        ("INVALID", "Las esquinas son inválidas."),
        ("ERROR", "COMMAND_ABORTED"),
    ],
)
def test_cancel_invalid_or_abort_never_returns_geometry(selection, error):
    result = parse_selected_moldaje(
        _header(selection=selection, error=error),
        CONTEXT,
    )

    assert result.selection == selection.lower()
    assert result.error == error
    assert result.rectangles == {}
    assert result.candidate is None


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ("RECTANGLE|abutment.footing|1;5;0|1;0;0", "degenerado"),
        ("RECTANGLE|abutment.footing|10;5;0|0;0;0", "superior izquierda"),
        ("RECTANGLE|abutment.footing|0;0;0|10;5;0", "superior izquierda"),
        ("RECTANGLE|abutment.footing|0;5;0|10;0;1", "plano XY"),
    ],
)
def test_ok_protocol_rejects_degenerate_reversed_or_non_planar_rectangle(record, message):
    with pytest.raises(ValueError, match=message):
        parse_selected_moldaje(_header() + "\n" + record, CONTEXT)


def test_ok_protocol_rejects_incomplete_or_wrong_context_result():
    with pytest.raises(ValueError, match="incompleta"):
        parse_selected_moldaje(
            _header(expected=2) + "\nRECTANGLE|abutment.footing|0;5;0|10;0;0",
            CONTEXT,
        )

    wrong_context = _header().replace("META|VIEW|FR", "META|VIEW|AA")
    with pytest.raises(ValueError, match="otra view"):
        parse_selected_moldaje(
            wrong_context + "\nRECTANGLE|abutment.footing|0;5;0|10;0;0",
            CONTEXT,
        )

    wrong_sequence = _header(
        expected=2,
        keys=["abutment.footing", "abutment.pile"],
    ) + "\n" + "\n".join([
        "RECTANGLE|abutment.footing|0;5;0|10;0;0",
        "RECTANGLE|abutment.front_wall|2;9;0|8;5;0",
    ])
    with pytest.raises(ValueError, match="secuencia"):
        parse_selected_moldaje(wrong_sequence, CONTEXT)


def test_builder_rejects_empty_duplicate_or_protocol_unsafe_keys():
    with pytest.raises(ValueError, match="al menos"):
        build_selection_lisp("result.txt", CONTEXT, [])
    with pytest.raises(ValueError, match="repite"):
        build_selection_lisp(
            "result.txt",
            CONTEXT,
            [
                {"key": "abutment.footing", "label": "Zapata"},
                {"key": "ABUTMENT.FOOTING", "label": "Otra"},
            ],
        )
    with pytest.raises(ValueError, match="no permitid"):
        build_selection_lisp(
            "result.txt",
            CONTEXT,
            [{"key": "abutment|footing", "label": "Zapata"}],
        )
