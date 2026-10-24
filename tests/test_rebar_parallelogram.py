import math

import pytest

from sincal.cad.moldajes import MoldajeContext
from sincal.rebar.model import ZapataGeometry
from sincal.web.rebar import reference_candidate


def fixture(skew=12, instance="entrada"):
    geometry = ZapataGeometry(7.5, 11.596, 1.5, skew)
    context = MoldajeContext("abutment.footing", instance, "FF")
    project = {"estribos": {f"orientacion_dado_estribo_{instance}": "romboide"}}
    return geometry, context, project


def corners(geometry, *, factor=1, width=None, depth=None, delta=None,
            origin=(-179.942, 64.438)):
    width = geometry.ancho_m if width is None else width
    depth = geometry.largo_m if depth is None else depth
    delta = depth * math.tan(math.radians(geometry.esviaje_grados)) if delta is None else delta
    x, y = origin
    return tuple((px * factor, py * factor, 0.0) for px, py in (
        (x + delta, y + depth), (x + width + delta, y + depth),
        (x + width, y), (x, y)))


@pytest.mark.parametrize("factor", [1, 100, 1000])
@pytest.mark.parametrize("skew", [-12, 0, 12])
def test_three_corners_preserve_real_world_parallelogram_for_both_skew_signs(factor, skew):
    geometry, context, project = fixture(skew)
    supplied = corners(geometry, factor=factor)
    candidate = reference_candidate(
        supplied, factor, context, geometry, project, reference_mode="parallelogram")
    expected = tuple((p[0] / factor, p[1] / factor) for p in reversed(supplied))
    assert candidate.vertices == expected
    assert candidate.area_m2 == pytest.approx(geometry.ancho_m * geometry.largo_m)
    assert candidate.context == context
    assert candidate.layer == candidate.handle == ""
    assert candidate.is_valid


def test_base_is_not_the_axis_aligned_bounding_box_width():
    geometry, context, project = fixture(20)
    supplied = corners(geometry)
    assert max(p[0] for p in supplied) - min(p[0] for p in supplied) > geometry.ancho_m
    candidate = reference_candidate(
        supplied, 1, context, geometry, project, reference_mode="parallelogram")
    assert math.dist(candidate.vertices[0], candidate.vertices[1]) == pytest.approx(11.596)


def test_small_accepted_measurement_tolerance_never_stretches_reference_to_json():
    geometry, context, project = fixture()
    delta = geometry.largo_m * math.tan(math.radians(geometry.esviaje_grados))
    supplied = corners(geometry, width=geometry.ancho_m + .005,
                       depth=geometry.largo_m - .005, delta=delta + .005)
    candidate = reference_candidate(
        supplied, 1, context, geometry, project, reference_mode="parallelogram")
    assert candidate.vertices == tuple(p[:2] for p in reversed(supplied))
    assert math.dist(candidate.vertices[0], candidate.vertices[1]) != geometry.ancho_m


@pytest.mark.parametrize("change", [
    {"width": 12.0}, {"depth": 8.0}, {"delta": -1.594174212525166},
])
def test_incompatible_base_depth_or_signed_skew_rejects_insertion(change):
    geometry, context, project = fixture()
    with pytest.raises(ValueError, match="No se insertaron armaduras"):
        reference_candidate(corners(geometry, **change), 1, context, geometry, project,
                            reference_mode="parallelogram")


@pytest.mark.parametrize("angle", [5, 90, 180])
def test_rotated_plan_has_explicit_limit_before_inserting(angle):
    geometry, context, project = fixture()
    theta = math.radians(angle)
    rotated = tuple((x * math.cos(theta) - y * math.sin(theta),
                     x * math.sin(theta) + y * math.cos(theta), 0.0)
                    for x, y, _ in corners(geometry))
    with pytest.raises(ValueError, match="planta está girada"):
        reference_candidate(rotated, 1, context, geometry, project,
                            reference_mode="parallelogram")


def test_two_opposite_corner_box_cannot_reconstruct_a_skewed_plan():
    geometry, context, project = fixture()
    supplied = corners(geometry)
    minx, maxx = min(p[0] for p in supplied), max(p[0] for p in supplied)
    miny, maxy = min(p[1] for p in supplied), max(p[1] for p in supplied)
    box = ((minx, maxy), (maxx, maxy), (maxx, miny), (minx, miny))
    with pytest.raises(ValueError, match="requiere tres esquinas"):
        reference_candidate(box, 1, context, geometry, project)


def test_parallelogram_must_match_orientation_for_selected_abutment():
    geometry, context, project = fixture(instance="salida")
    project["estribos"]["orientacion_dado_estribo_entrada"] = "rectangular"
    assert reference_candidate(corners(geometry), 1, context, geometry, project,
                               reference_mode="parallelogram").is_valid
    project["estribos"]["orientacion_dado_estribo_salida"] = "rectangular"
    with pytest.raises(ValueError, match="JSON define una zapata rectangular"):
        reference_candidate(corners(geometry), 1, context, geometry, project,
                            reference_mode="parallelogram")


def test_wrong_corner_order_degenerate_and_non_parallelogram_are_rejected():
    geometry, context, project = fixture()
    supplied = corners(geometry)
    invalid = (
        (supplied[1], supplied[0], supplied[3], supplied[2]),
        (supplied[0], supplied[0], supplied[2], supplied[3]),
        (*supplied[:3], (supplied[3][0] + .001, supplied[3][1], 0)),
    )
    for points in invalid:
        with pytest.raises(ValueError):
            reference_candidate(points, 1, context, geometry, project,
                                reference_mode="parallelogram")


@pytest.mark.parametrize("points", [[], [(0, 0)], [(0, 0)] * 3,
                                    [(0, 0)] * 3 + [(float("nan"), 1)],
                                    [(0, 0, float("inf"))] * 4,
                                    [(0, 0, 1)] * 4, [(0,)] * 4])
def test_invalid_vertices_fail_cleanly(points):
    geometry, context, project = fixture()
    with pytest.raises(ValueError):
        reference_candidate(points, 1, context, geometry, project,
                            reference_mode="parallelogram")


@pytest.mark.parametrize("view,width", [("FR", 11.596), ("AA", 7.5),
                                       ("BB", 7.5), ("CC", 7.5)])
def test_existing_rectangular_section_reference_is_preserved(view, width):
    geometry, _, project = fixture()
    context = MoldajeContext("abutment.footing", "entrada", view)
    rectangle = ((0, 0), (width, 0), (width, 1.5), (0, 1.5))
    candidate = reference_candidate(rectangle, 1, context, geometry, project)
    assert candidate.vertices == rectangle


def test_three_corner_mode_is_not_allowed_for_a_section():
    geometry, _, project = fixture()
    context = MoldajeContext("abutment.footing", "entrada", "FR")
    with pytest.raises(ValueError, match="corresponde a la planta"):
        reference_candidate(corners(geometry), 1, context, geometry, project,
                            reference_mode="parallelogram")


def test_rectangular_rotado_with_zero_skew_accepts_rectangle_reference():
    geometry, context, project = fixture(0)
    project["estribos"]["orientacion_dado_estribo_entrada"] = "rectangular_rotado"
    supplied = corners(geometry)
    candidate = reference_candidate(supplied, 1, context, geometry, project)
    assert candidate.vertices == tuple(p[:2] for p in reversed(supplied))
    assert candidate.is_valid


def test_rectangular_rotado_with_nonzero_skew_rejects_before_creating_candidate():
    geometry, context, project = fixture(12)
    project["estribos"]["orientacion_dado_estribo_entrada"] = "rectangular_rotado"
    with pytest.raises(ValueError, match="rectangular girada con esviaje distinto de 0°"):
        reference_candidate(corners(geometry, delta=0), 1, context, geometry, project)
