"""Reference shapes share one station without becoming a fabrication model."""
from copy import deepcopy
import math

import pytest

from sincal.rebar.beam_profiles import resolve_profile
from sincal.web.beam_definition import build_definition


def definition(slope=-.005):
    return build_definition(resolve_profile(6), {'specimen_length_m':.75}, slope)


def test_all_families_share_one_station_without_an_invented_distribution():
    data=definition()
    assert data['available']
    assert not data['fabrication_ready'] and not data['distribution_defined']
    assert {b['mark'] for b in data['bars']}=={'1','2','3','6','7','11'}
    assert {b['station_m'] for b in data['bars']}=={.375}
    for bar in data['bars']:
        ys=[p[1] for p in bar['local_points']]
        assert (min(ys)+max(ys))/2==pytest.approx(.375)
        # Only a bar's own physical closure has a depth offset. No family
        # remains at the old exploded-view stations .11, .24, .39, .53, .65.
        assert max(ys)-min(ys)==pytest.approx(bar['diameter_mm']/1000 if bar['mark'] in ('6','11') else 0)
        assert 'quantity' not in bar and 'spacing_cm' not in bar


@pytest.mark.parametrize('slope',[-.07,0,.025])
def test_same_rigid_rotation_preserves_all_bar_lengths_and_bend_radii(slope):
    for bar in definition(slope)['bars']:
        local,world=bar['local_points'],bar['points']
        alpha=math.atan(-slope)
        for (x,y,z),actual in zip(local,world):
            assert actual==pytest.approx((x,y*math.cos(alpha)-z*math.sin(alpha),y*math.sin(alpha)+z*math.cos(alpha)))
        assert sum(math.dist(a,b) for a,b in zip(local,local[1:]))==pytest.approx(sum(math.dist(a,b) for a,b in zip(world,world[1:])))
        for segment in bar['native_segments']:
            if segment['type']=='arc':
                assert segment['radius_m']==pytest.approx(3*bar['diameter_mm']/1000)


def test_keeps_bulb_correction():
    data=definition()
    bulb=next(b for b in data['bars'] if b['mark']=='6')
    for leg in (bulb['native_segments'][0],bulb['native_segments'][-1]):
        assert abs(leg['start'][0])==pytest.approx(.07)
        assert .1-abs(leg['start'][0])-.005==pytest.approx(.025)
        assert leg['length_m']==pytest.approx(.26)


def test_mark3_matches_approved_green_fit_and_clears_both_sloping_faces():
    data = definition()
    bar = next(b for b in data['bars'] if b['mark'] == '3')
    assert not bar.get('partial_geometry')
    left_tail, left_arc, top, right_arc, right_tail = bar['native_segments']
    assert [s['type'] for s in bar['native_segments']] == ['line', 'arc', 'line', 'arc', 'line']
    radius = bar['diameter_mm'] / 2000
    for arc in (left_arc, right_arc):
        assert arc['sweep_radians'] == pytest.approx(math.pi)
        assert arc['radius_m'] == pytest.approx(.024)
    for tail in (left_tail, right_tail):
        assert tail['length_m'] == pytest.approx(.08)
        assert top['start'][2] - tail['start'][2] == pytest.approx(.048)
    assert left_tail['start'][0] > left_tail['end'][0]
    assert right_tail['end'][0] < right_tail['start'][0]
    xs = [x for x, _, _ in bar['local_points']]
    assert max(xs) - min(xs) + 2 * radius == pytest.approx(.96966273, abs=1e-7)
    assert 2 - top['start'][2] - radius == pytest.approx(.025)
    # H200 outer underside passes through (0.26, 1.87) and (0.76, 1.93).
    for sign in (-1, 1):
        minimum = min((z - 1.87 - .12 * (sign*x - .26)) / math.hypot(1, .12) - radius
                      for x, _, z in bar['local_points'] if sign*x > .26)
        assert minimum == pytest.approx(.025, abs=1e-6)
    assert not any('encaje pendiente' in issue for issue in data['issues'])


def test_no_speculative_forms_for_other_profiles_or_no_interior_section():
    profile=resolve_profile(3)
    original=deepcopy(profile)
    result=build_definition(profile,{'specimen_length_m':.75},0)
    assert not result['available'] and not result['bars']
    assert profile==original
    assert not build_definition(resolve_profile(6),None,0)['available']
    assert not build_definition(resolve_profile(6),{'specimen_length_m':.01},0)['bars']
