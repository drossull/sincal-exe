"""Explicit horizontal continuity along the two exterior wall faces."""
from __future__ import annotations

def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def horizontal_face_path(profile, start, end):
    """Intersect the two offset bar axes, retaining the actual corner.

    The caller places both endpoints at their covers. No bar is rotated or
    scaled to fit a CAD reference and no unknown bend is substituted.
    """
    axis = profile['frame']['axis_u']
    front = profile['frame']['front_axis_u']
    denominator = axis[0]*front[1]-axis[1]*front[0]
    if abs(denominator) < 1e-10:
        if _dot(axis, front) < 0 or abs((end[0]-start[0])*axis[1]-(end[1]-start[1])*axis[0]) > 1e-8:
            raise ValueError('Las caras del ala y el frontal no tienen una continuidad compatible.')
        return (tuple(start), tuple(end))
    delta = (end[0]-start[0], end[1]-start[1])
    along_wing = (delta[0]*front[1]-delta[1]*front[0])/denominator
    corner = tuple(start[i]+along_wing*axis[i] for i in range(3))
    along_front = _dot(tuple(a-b for a, b in zip(corner, end)), front)
    if along_wing >= -1e-9 or along_front <= 1e-9:
        raise ValueError('El encuentro de las caras queda fuera del recorrido del horizontal.')
    return (tuple(start), corner, tuple(end))
