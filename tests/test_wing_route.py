import math

import pytest

from sincal.rebar.wing_route import horizontal_face_path


def profile(rotation=0, skew=0, right=False, exit_=False):
    rotation = math.radians(rotation)
    so = 1 if exit_ else -1
    n = -1 if right else 1
    return {'frame': {'origin_m': (0, 0, 1.5), 'axis_u': (-so*math.sin(rotation), so*math.cos(rotation), 0),
                      'inward': (n*math.cos(rotation), n*math.sin(rotation), 0),
                      'front_axis_u': (0, so, 0), 'front_inward': (n, 0, 0)},
            'geometry': {'front_depth_cm': 230, 'back_thickness_cm': 50},
            'source': {'skew_degrees': skew}}


@pytest.mark.parametrize('angle', [-12, -5, 0, 5, 12])
@pytest.mark.parametrize('right', [False, True])
@pytest.mark.parametrize('exit_', [False, True])
def test_route_follows_both_offset_faces(angle, right, exit_):
    data = profile(angle, 12, right, exit_)
    frame = data['frame']; depth = .09
    start = tuple(frame['origin_m'][i]+4*frame['axis_u'][i]+depth*frame['inward'][i] for i in range(3))
    end = tuple(frame['origin_m'][i]-2.2*frame['front_axis_u'][i]+depth*frame['front_inward'][i] for i in range(3))
    route = horizontal_face_path(data, start, end)
    assert len(route) == (2 if angle == 0 else 3)
    if angle:
        first = tuple(a-b for a, b in zip(route[1], route[0]))
        last = tuple(a-b for a, b in zip(route[-1], route[-2]))
        assert first[0]*frame['axis_u'][1]-first[1]*frame['axis_u'][0] == pytest.approx(0)
        assert last[0] == pytest.approx(0)
