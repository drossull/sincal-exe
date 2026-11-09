"""Exact intersections of physical rebar centre lines with a vertical plane.

The plane is ``nx*x + ny*y = station_m``.  Coordinates stay in metres and
belong to the original bar; this module neither projects nor changes steel.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SectionSegment:
    start_m: tuple[float, float, float]
    end_m: tuple[float, float, float]
    bulge: float = 0.0


@dataclass(frozen=True)
class SectionResult:
    points_m: tuple[tuple[float, float, float], ...]
    contained_segments: tuple[SectionSegment, ...]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def intersect_bar_plane(bar, normal_xy, station_m, *, tolerance=1e-9):
    """Return isolated hits and whole segments contained in a vertical plane.

    Bulged segments use the bar's oriented ``axis_u``/``axis_v`` plane and
    analytic circle roots, including negative sweeps and tangencies.  Normal
    and station are normalized together, so ``tolerance`` is always metres.
    Repeated hits at joints are returned once per physical piece. Endpoints
    already represented by contained segments are not separate point symbols.
    """
    nx, ny = normal_xy
    if (not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) for value in (nx, ny, station_m, tolerance))
            or tolerance <= 0):
        raise ValueError("El plano de corte requiere valores finitos y tolerancia positiva.")
    norm = math.hypot(nx, ny)
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError("La normal del plano de corte no puede ser nula.")
    nx, ny, station = nx / norm, ny / norm, station_m / norm

    def dot(point):
        return nx * point[0] + ny * point[1]

    points, contained = [], []

    def add(point):
        point = tuple(point)
        if not any(math.dist(point, previous) <= tolerance for previous in points):
            points.append(point)

    bar_normal = None
    for first, last, bulge in zip(bar.vertices_m, bar.vertices_m[1:], bar.bulges):
        first, last = tuple(first), tuple(last)
        chord = tuple(b - a for a, b in zip(first, last))
        chord_length = math.dist(first, last)
        f0, f1 = dot(first) - station, dot(last) - station
        if chord_length <= tolerance:
            if abs(f0) <= tolerance:
                add(first)
            continue
        if abs(bulge) < 1e-12:
            if abs(f0) <= tolerance and abs(f1) <= tolerance:
                contained.append(SectionSegment(first, last))
            elif abs(f0) <= tolerance:
                add(first)
            elif abs(f1) <= tolerance:
                add(last)
            elif (f0 < 0) != (f1 < 0):
                fraction = f0 / (f0 - f1)
                add(tuple(a + fraction * delta for a, delta in zip(first, chord)))
            continue

        if bar_normal is None:
            cross = _cross(bar.axis_u, bar.axis_v)
            length = math.sqrt(sum(value * value for value in cross))
            if not math.isfinite(length) or length <= 1e-12:
                raise ValueError("El plano del doblez no tiene una orientación válida.")
            bar_normal = tuple(value / length for value in cross)
        left = tuple(value / chord_length for value in _cross(bar_normal, chord))
        offset = chord_length * (1 - bulge * bulge) / (4 * bulge)
        centre = tuple((a + b) / 2 + offset * side
                       for a, b, side in zip(first, last, left))
        radial = tuple(a - c for a, c in zip(first, centre))
        quarter_turn = _cross(bar_normal, radial)
        radius = math.sqrt(sum(value * value for value in radial))
        sweep = 4 * math.atan(bulge)
        coefficient_a, coefficient_b = dot(radial), dot(quarter_turn)
        amplitude = math.hypot(coefficient_a, coefficient_b)
        centre_offset = dot(centre) - station
        if amplitude <= tolerance:
            if abs(centre_offset) <= tolerance:
                contained.append(SectionSegment(first, last, bulge))
            continue
        ratio = -centre_offset / amplitude
        if abs(ratio) > 1 + tolerance / amplitude:
            continue
        phase = math.atan2(coefficient_b, coefficient_a)
        delta = math.acos(max(-1.0, min(1.0, ratio)))
        lower, upper = min(0.0, sweep), max(0.0, sweep)
        angle_tolerance = tolerance / radius
        for base_angle in (phase - delta, phase + delta):
            first_turn = math.ceil((lower - base_angle - angle_tolerance) / math.tau)
            last_turn = math.floor((upper - base_angle + angle_tolerance) / math.tau)
            for turn in range(first_turn, last_turn + 1):
                angle = base_angle + turn * math.tau
                if abs(angle) <= angle_tolerance:
                    add(first)
                elif abs(angle - sweep) <= angle_tolerance:
                    add(last)
                else:
                    add(tuple(c + a * math.cos(angle) + b * math.sin(angle)
                              for c, a, b in zip(centre, radial, quarter_turn)))

    endpoints = [point for segment in contained for point in (segment.start_m, segment.end_m)]
    isolated = tuple(point for point in points
                     if not any(math.dist(point, end) <= tolerance for end in endpoints))
    return SectionResult(isolated, tuple(contained))
