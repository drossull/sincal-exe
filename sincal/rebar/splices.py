"""Physical lap intervals between manufactured pieces that still exist."""
from collections import defaultdict
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PhysicalLap:
    piece_id: str
    partner_id: str
    start_m: tuple
    end_m: tuple
    partner_start_m: tuple = ()
    partner_end_m: tuple = ()
    axis_distance_m: float = 0.0

    @property
    def length_cm(self):
        return math.dist(self.start_m, self.end_m) * 100


def physical_laps(bars):
    """Clip each nominal incoming lap to an existing partner's straight steel.

    Ownership stays with the continuation, so callers draw every overlap once.
    The original piece vertices, cut lengths and signatures remain untouched.
    """
    runs = defaultdict(list)
    for bar in bars:
        runs[bar.placement_id].append(bar)
    result = []
    for run in runs.values():
        for bar in run:
            for start, end in bar.lap_segments_m:
                axis = tuple(b-a for a, b in zip(start, end))
                length2 = sum(value*value for value in axis)
                if length2 < 1e-16:
                    continue
                for partner in run:
                    if partner.id == bar.id:
                        continue
                    parameters, offsets = [], []
                    for point in (partner.main_start_m, partner.main_end_m):
                        t = sum((p-a)*u for p, a, u in zip(point, start, axis)) / length2
                        offsets.append(tuple(p-a-t*u for p,a,u in zip(point,start,axis)))
                        parameters.append(t)
                    # Real splice axes are parallel and separated by the sum
                    # of their radii. Legacy synthetic callers without sizes
                    # retain a zero-radius line model, never production steel.
                    distance = math.hypot(*offsets[0])
                    required = (getattr(bar, 'diameter_mm', 0.)+getattr(partner, 'diameter_mm', 0.))/2000
                    if (math.dist(*offsets) > 1e-8 or
                            not math.isclose(distance, required, rel_tol=0., abs_tol=1e-8)):
                        continue
                    lo, hi = max(0., min(parameters)), min(1., max(parameters))
                    if hi-lo <= 1e-9:
                        continue
                    first = tuple(a+lo*u for a, u in zip(start, axis))
                    last = tuple(a+hi*u for a, u in zip(start, axis))
                    result.append(PhysicalLap(bar.id, partner.id, first, last,
                        tuple(a+d for a,d in zip(first,offsets[0])),
                        tuple(a+d for a,d in zip(last,offsets[0])), distance))
    return tuple(result)
