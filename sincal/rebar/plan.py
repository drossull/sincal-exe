"""Shared footing mesh axes in the local CAD plan, in metres.

These axes are physical distributions, not drawing-only fill. The local
concrete polygon is (x + y*tan(skew), y), centred on the footing. Below ten
degrees, Y follows the lateral faces; from ten degrees it remains perpendicular
and spans its entire usable projection, including both end wedges.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


def mesh_y_parallel_to_skew(skew_degrees: float) -> bool:
    """Use the unrounded angle to choose the longitudinal mesh direction."""
    return abs(skew_degrees) < 10.0


@dataclass(frozen=True)
class FootingMeshAxis:
    # For inclined Y this is x - tan(skew)*y, the transverse intercept at y=0.
    coordinate_m: float
    start_m: tuple[float, float]
    end_m: tuple[float, float]

    @property
    def length_m(self):
        return math.dist(self.start_m, self.end_m)


def footing_mesh_axes(geometry, cover, rule, reference=None, *, side_insets_m=(0.0, 0.0)):
    """Return covered mesh chords in deterministic distribution order.

    For ``suple``, pass the Y-mesh rule as reference: the existing half-sum
    diameter displacement is applied without exceeding the feasible boundary.
    ``side_insets_m`` gives the thickness occupied by exterior lateral bars on
    the skewed X faces and the Y faces respectively. Mesh hooks sit inside
    those bars; the rectangular distribution starts at the matching tangency.
    The endpoint range in skewed Y families excludes only chords too short for
    the two 90-degree bends (length < 2*bend_radius); this is a geometric
    constraint, not an invented edge tolerance. The Y mesh also anchors at
    the two tangencies of the central X representative used by the frontal
    view. This fixes that selected section, not every row along a skewed edge.
    """
    from .model import bend_radius_cm, distribution_positions_cm

    reference = reference or rule
    if rule.key not in ("mesh_x", "mesh_y", "suple"):
        raise ValueError("La familia no corresponde a una malla de zapata.")
    extra_x, extra_y = side_insets_m
    values = (geometry.ancho_m, geometry.largo_m, geometry.esviaje_grados,
              cover.lateral_m, rule.diameter_mm, rule.spacing_cm, reference.diameter_mm,
              extra_x, extra_y)
    if not all(isinstance(v, (float, int)) and not isinstance(v, bool)
               and math.isfinite(v) for v in values):
        raise ValueError("Las dimensiones de la malla deben ser números finitos.")
    if (geometry.ancho_m <= 0 or geometry.largo_m <= 0 or cover.lateral_m < 0
            or rule.diameter_mm <= 0 or reference.diameter_mm <= 0
            or rule.spacing_cm <= 0 or min(extra_x, extra_y) < 0 or abs(geometry.esviaje_grados) >= 90):
        raise ValueError("Las dimensiones no permiten distribuir la malla de zapata.")
    if rule.origin not in ("inicio", "final"):
        raise ValueError("Origen de reparto no válido.")

    angle = math.radians(geometry.esviaje_grados)
    slope = math.tan(angle)
    inset = cover.lateral_m + rule.diameter_mm / 2000.0
    # Interior half-width in the x-y*t coordinate, and interior y half-range.
    half_width = geometry.ancho_m / 2.0 - (inset + extra_x) * math.hypot(1.0, slope)
    half_depth = geometry.largo_m / 2.0 - inset - extra_y
    if half_width <= 0 or half_depth <= 0:
        raise ValueError("El recubrimiento no deja un contorno útil de malla.")
    horizontal = rule.key == "mesh_x"
    radius = bend_radius_cm(rule.diameter_mm) / 100.0
    inclined_mesh = (abs(geometry.esviaje_grados) > 1e-9
                     and mesh_y_parallel_to_skew(geometry.esviaje_grados))
    parallel_y = not horizontal and inclined_mesh
    skewed_y = not horizontal and abs(geometry.esviaje_grados) > 1e-9 and not parallel_y

    if parallel_y:
        # X's straight tangencies have a constant intercept on every inclined
        # side. Keep that real contact, with equal full-length Y runs.
        tangent_cover = ((cover.lateral_m + extra_x + reference.diameter_mm / 2000.0)
                         * math.hypot(1.0, slope)
                         + bend_radius_cm(reference.diameter_mm) / 100.0)
        start = -geometry.ancho_m / 2.0 + tangent_cover
        end = geometry.ancho_m / 2.0 - tangent_cover
    elif skewed_y:
        maximum_chord = min(2.0 * half_depth, 2.0 * half_width / abs(slope))
        if maximum_chord < 2.0 * radius - 1e-10:
            raise ValueError("La cuña no permite alojar los dos dobleces de la malla.")
        extent = half_width + abs(slope) * (half_depth - 2.0 * radius)
        start, end = -extent, extent
    else:
        tangent_radius = bend_radius_cm(reference.diameter_mm) / 100.0
        if horizontal and inclined_mesh:
            # The longitudinal 90-degree bend remains in its vertical plane;
            # its projection onto the X-mesh distribution direction is R*cos.
            tangent_radius *= math.cos(angle)
        tangent_cover = (cover.lateral_m + (extra_y if horizontal else extra_x)
                         + reference.diameter_mm / 2000.0 + tangent_radius)
        span = geometry.largo_m if horizontal else geometry.ancho_m
        start, end = -span / 2.0 + tangent_cover, span / 2.0 - tangent_cover
    if end < start:
        raise ValueError("No existe rango útil para distribuir la malla.")
    if (end - start) * 100.0 / rule.spacing_cm > 25000:
        raise ValueError("La distribución supera 25.000 ejes por malla; revisa dimensiones y separación.")

    offset = (rule.diameter_mm + reference.diameter_mm) / 2000.0 if rule.key == "suple" else 0.0
    start = min(end, start + offset)
    def distribute(first, last, origin):
        positions = distribution_positions_cm((last - first) * 100.0, rule.spacing_cm, origin,
                                              include_endpoints=True,
                                              minimum_spacing_cm=rule.diameter_mm / 10
                                              / (math.cos(angle) if parallel_y else 1.0))
        return tuple(first + position / 100.0 for position in positions)

    section = None
    if skewed_y and rule.key == "mesh_y" and reference.key == "mesh_x":
        cross_axes = footing_mesh_axes(geometry, cover, reference, rule,
                                       side_insets_m=side_insets_m)
        cross_axis = min(cross_axes, key=lambda axis: abs(axis.coordinate_m))
        cross_radius = bend_radius_cm(reference.diameter_mm) / 100.0
        left = cross_axis.start_m[0] + cross_radius
        right = cross_axis.end_m[0] - cross_radius
        if not start <= left < right <= end:
            raise ValueError("Las tangencias de la vista frontal quedan fuera del reparto útil de la malla Y.")
        # Start each wedge at the tangency and work outwards. A single global
        # phase could put another Y between that tangency and the selected X
        # bend. Keep both wedge limits and the ordinary maximum pitch.
        coordinates = (distribute(start, left, "final")
                       + distribute(left, right, rule.origin)
                       + distribute(right, end, "inicio"))
        section = (cross_axis.coordinate_m, left, right)
    else:
        coordinates = distribute(start, end, rule.origin)
    result = []
    for coordinate in coordinates:
        if result and abs(coordinate - result[-1].coordinate_m) < 1e-10:
            continue
        if horizontal:
            if not -half_depth - 1e-10 <= coordinate <= half_depth + 1e-10:
                raise ValueError("El reparto de la malla X queda fuera del contorno útil.")
            first = (slope * coordinate - half_width, coordinate)
            last = (slope * coordinate + half_width, coordinate)
        elif parallel_y:
            if abs(coordinate) > half_width + 1e-10:
                raise ValueError("El reparto de la malla Y paralela queda fuera del contorno útil.")
            first = (coordinate - slope * half_depth, -half_depth)
            last = (coordinate + slope * half_depth, half_depth)
        else:
            low, high = -half_depth, half_depth
            if abs(slope) > 1e-12:
                a, b = sorted(((coordinate - half_width) / slope,
                               (coordinate + half_width) / slope))
                low, high = max(low, a), min(high, b)
            elif abs(coordinate) > half_width + 1e-10:
                raise ValueError("El reparto de la malla Y queda fuera del contorno útil.")
            first, last = (coordinate, low), (coordinate, high)
        axis = FootingMeshAxis(coordinate, first, last)
        if axis.length_m < 2.0 * radius - 1e-9:
            raise ValueError("Una barra de la malla no admite sus dos dobleces.")
        if section is not None:
            station, left, right = section
            if coordinate < left - 1e-9 or coordinate > right + 1e-9:
                if first[1] - 1e-9 <= station <= last[1] + 1e-9:
                    raise ValueError(
                        "La separación de la malla Y sitúa un fierro de la cuña sobre el doblez "
                        "de la sección frontal. Revisa la separación; no se recortaron ni desplazaron sus piezas.")
            elif math.isclose(coordinate, left, abs_tol=1e-9) or math.isclose(coordinate, right, abs_tol=1e-9):
                if not first[1] + radius - 1e-9 <= station <= last[1] - radius + 1e-9:
                    raise ValueError(
                        "El fierro del extremo no alcanza la tangencia frontal con su tramo recto; "
                        "revisa las dimensiones y diámetros de ambas mallas.")
        result.append(axis)
    return tuple(result)
