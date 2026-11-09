"""Interior cage uses real inside faces and the agreed hook directions."""
from copy import deepcopy
import math

import pytest

from sincal.rebar.wing_mesh import build_wing_mesh, opposed_mesh_issues
from sincal.web.wing_geometry import build_wing_profile
from tests.test_wing_mesh_geometry import configured, dot, inward_plane


def build(side='left', skew=-12, extension=True, rotation=0, instance='entrada'):
    data, abutment, state, profile = configured(side, skew, extension, rotation, instance)
    state['vertical'].update(mark_main='21', mark_extension='22')
    state['horizontal'].update(mark_main='23', mark_upper='24')
    before = deepcopy((data, abutment, state, profile))
    result = build_wing_mesh(profile, state, abutment, side, mesh='interior')
    assert result['valid'], result['issues']
    assert (data, abutment, state, profile) == before
    return result, abutment, state, profile


def offset(point, zero):
    return tuple(a-b for a, b in zip(point, zero))


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('instance', ['entrada', 'salida'])
@pytest.mark.parametrize('skew,rotation', [(0, 0), (-12, 0), (12, 0), (-12, 5), (12, -5)])
@pytest.mark.parametrize('extension', [False, True])
def test_interior_has_own_depths_hook_directions_and_normal_covers(side, instance, skew, rotation, extension):
    result, abutment, state, profile = build(side, skew, extension, rotation, instance)
    frame = profile['frame']
    origin, inward, front_inward = frame['origin_m'], frame['inward'], frame['front_inward']
    dv, dh = state['vertical']['diameter_mm']/1000, state['horizontal']['diameter_mm']/1000
    vertical_depth = profile['geometry']['thickness_cm']/100-state['cover']['inside_cm']/100-dv/2
    horizontal_depth = vertical_depth-(dv+dh)/2
    front_depth = dot(profile['side_offset_m'], front_inward)-state['cover']['inside_cm']/100-dv-dh/2
    assert horizontal_depth < vertical_depth
    concrete = profile['meshes']+profile['front_wall_meshes']+profile['back_wall_meshes']+profile['footing_meshes']
    solid_faces = [tuple(inward_plane(m, face) for face in m['faces']) for m in concrete]
    for bar in result['bars']:
        assert bar['id'].startswith(f'wing:{side}:inner_')
        assert bar['key'].startswith(f'wing_{side}_inner_')
        assert bar['level'] == 'interior' and 'interior' in bar['label']
        assert bar['bend_radius_cm'] == pytest.approx(3*bar['diameter_mm']/10)
        assert bar['length_cm'] <= 1200
        first, last = bar['points'][0], bar['points'][-1]
        if '_vertical_' in bar['key']:
            assert dot(offset(bar['main_start'], origin), inward) == pytest.approx(vertical_depth)
            assert dot(offset(bar['main_end'], origin), inward) == pytest.approx(vertical_depth)
            lower_direction = dot(offset(first, bar['main_start']), inward)
            if bar['key'].endswith('vertical_main'):
                assert lower_direction > 0  # Common direction only inside footing.
                assert min(p[2] for p in bar['points']) == pytest.approx(abutment['cover']['inferior_cm']/100+dv/2)
            else:
                assert lower_direction < 0  # Cantilever lower hook stays in wall.
            assert dot(offset(last, bar['main_end']), inward) < 0
            short = bar['key'].endswith('vertical_extension')
            mouldage = profile['meshes'][1 if short else 0]
            checks = [((0, 1, 2, 3), 'outside_cm'), ((4, 5, 6, 7), 'inside_cm'),
                      ((1, 2, 6, 5), 'end_cm'), ((0, 3, 7, 4), 'end_cm'),
                      ((3, 2, 6, 7), 'top_cm')]
            if short:
                checks.append(((0, 1, 5, 4), 'diagonal_cm'))
            for indices, cover in checks:
                distance = inward_plane(mouldage, indices)
                for point in bar['points']:
                    if not short and point[2] < origin[2]:
                        continue
                    assert distance(point) >= state['cover'][cover]/100+dv/2-1e-8, (bar['id'], cover, point)
        else:
            assert dot(offset(bar['main_start'], origin), inward) == pytest.approx(horizontal_depth)
            assert dot(offset(bar['main_end'], origin), front_inward) == pytest.approx(front_depth)
            assert dot(offset(first, bar['main_start']), inward) < 0
            assert dot(offset(last, bar['main_end']), front_inward) > 0
            # The whole real route, including its corner arc and both end
            # hooks, lies in the union of the existing concrete solids.
            for point in bar['points']:
                assert any(all(distance(point) >= -1e-8 for distance in faces)
                           for faces in solid_faces), (bar['id'], point)


def test_negative_u_vertical_station_keeps_rotated_wing_frame():
    result, _, _, profile = build('right', -12, False, 5)
    frame = profile['frame']
    first = next(bar for bar in result['bars'] if bar['key'].endswith('vertical_main'))
    local = offset(first['main_start'], frame['origin_m'])
    assert dot(local, frame['axis_u']) < 0
    expected_depth = profile['geometry']['thickness_cm']/100-.05-.016/2
    assert dot(local, frame['inward']) == pytest.approx(expected_depth)


@pytest.mark.parametrize('side', ['left', 'right'])
def test_interior_lower_hooks_fit_footing_beyond_wing_inside_face(side):
    result, abutment, state, profile = build(side, -12, True, 5)
    theta = math.radians(abutment['geometry']['esviaje_grados'])
    half_x = abutment['geometry']['ancho_cm']/200*math.cos(theta)
    half_s = abutment['geometry']['largo_cm']/200
    found_beyond_wing = False
    for bar in result['bars']:
        if not bar['key'].endswith('vertical_main'):
            continue
        radius = bar['diameter_mm']/2000
        required = abutment['cover']['lateral_cm']/100+radius
        for point in bar['points']:
            if point[2] >= profile['frame']['origin_m'][2]:
                continue
            x, y, _ = point
            assert half_x-abs(x) >= required-1e-8
            assert half_s-abs(y*math.cos(theta)-x*math.sin(theta)) >= required-1e-8
            depth = dot(offset(point, profile['frame']['origin_m']), profile['frame']['inward'])
            found_beyond_wing |= depth > profile['geometry']['thickness_cm']/100
    assert found_beyond_wing


def test_interior_quantities_and_individual_removals_do_not_change_exterior():
    _, abutment, state, profile = configured(extension=True)
    exterior = build_wing_mesh(profile, state, abutment, 'left')
    assert exterior == build_wing_mesh(profile, state, abutment, 'left', mesh='exterior')
    state['vertical'].update(mark_main='21', mark_extension='22')
    state['horizontal'].update(mark_main='23', mark_upper='24')
    initial = build_wing_mesh(profile, state, abutment, 'left', mesh='interior')
    assert initial['valid'], initial['issues']
    assert sum(m['quantity'] for m in initial['marks']) == len(initial['bars'])
    assert sum(m['total_length_cm'] for m in initial['marks']) == sum(b['length_cm'] for b in initial['bars'])
    assert not ({b['id'] for b in exterior['bars']} & {b['id'] for b in initial['bars']})
    assert not ({b['signature'] for b in exterior['bars']} & {b['signature'] for b in initial['bars']})
    removed = next(b for b in initial['bars'] if b['key'].endswith('vertical_extension'))
    state['removed_pieces'] = [{key: removed[key] for key in ('id', 'signature')}]
    reduced = build_wing_mesh(profile, state, abutment, 'left', mesh='interior')
    assert reduced['valid'], reduced['issues']
    assert {b['id'] for b in reduced['bars']} == {b['id'] for b in initial['bars']}-{removed['id']}
    assert sum(m['total_length_cm'] for m in initial['marks'])-sum(m['total_length_cm'] for m in reduced['marks']) == removed['length_cm']
    state['vertical']['mark_extension'] = '32'
    renamed = build_wing_mesh(profile, state, abutment, 'left', mesh='interior')
    assert renamed['valid'] and renamed['removed_bars'][0]['status'] == 'removed'
    state['vertical']['spacing_cm'] = 23
    # Use a noninitial removal to make its changed physical location explicit.
    removed = [b for b in initial['bars'] if b['key'].endswith('vertical_extension')][1]
    state['removed_pieces'] = [{key: removed[key] for key in ('id', 'signature')}]
    stale = build_wing_mesh(profile, state, abutment, 'left', mesh='interior')
    assert not stale['valid'] and not stale['bars']
    assert stale['removed_bars'][0]['status'] == 'unresolved'


@pytest.mark.parametrize('field', ['hook_top_cm', 'hook_bottom_cm'])
def test_interior_hook_that_cannot_fit_is_not_reversed_or_shortened(field):
    _, abutment, state, profile = configured(extension=True)
    state['vertical'][field] = 100
    result = build_wing_mesh(profile, state, abutment, 'left', mesh='interior')
    assert not result['valid'] and not result['bars']
    assert any('no cabe' in issue['message'] for issue in result['issues'])
    assert state['vertical'][field] == 100


def test_invalid_mesh_selector_does_not_fall_back_to_exterior():
    _, abutment, state, profile = configured()
    result = build_wing_mesh(profile, state, abutment, 'left', mesh='middle')
    assert not result['valid'] and not result['bars']


def test_edited_thickness_updates_inner_front_face_in_its_own_frame():
    _, abutment, state, original = configured('left', -12, True, 5)
    state['geometry']['thickness_cm'] += 20
    profile = build_wing_profile(original, state['geometry'])
    result = build_wing_mesh(profile, state, abutment, 'left', mesh='interior')
    assert result['valid'], result['issues']
    frame = profile['frame']
    shear = dot(profile['side_offset_m'], frame['axis_u'])
    actual_offset = tuple(shear*u+profile['geometry']['thickness_cm']/100*n
                          for u,n in zip(frame['axis_u'], frame['inward']))
    front_depth = dot(actual_offset, frame['front_inward'])-.05-.016-.012/2
    original_depth = dot(profile['side_offset_m'], frame['front_inward'])-.05-.016-.012/2
    assert abs(front_depth-original_depth) > .19
    for bar in result['bars']:
        if '_horizontal_' in bar['key']:
            assert dot(offset(bar['main_end'], frame['origin_m']), frame['front_inward']) == pytest.approx(front_depth)


@pytest.mark.parametrize('skew,cover_cm,expected', [(12, 37.5, 'frontal/espaldar'), (-12, 36.7, 'ala')])
def test_opposed_layers_check_normal_and_front_offsets_independently(skew, cover_cm, expected):
    _, _, exterior, profile = configured('left', skew, False, 5)
    interior = deepcopy(exterior)
    exterior['cover']['outside_cm'] = cover_cm
    interior['cover']['inside_cm'] = cover_cm
    before = deepcopy((profile, exterior, interior))
    issues = opposed_mesh_issues(profile, exterior, interior)
    assert len(issues) == 1 and expected in issues[0]['message']
    assert issues[0]['severity'] == 'error'
    assert (profile, exterior, interior) == before


def test_opposed_layer_contact_is_allowed_and_hooks_do_not_change_that_test():
    _, _, exterior, profile = configured('left', 0, False, 0)
    interior = deepcopy(exterior)
    exterior['cover']['outside_cm'] = interior['cover']['inside_cm'] = 37.2
    assert opposed_mesh_issues(profile, exterior, interior) == []
    # Hook collisions/staggering are separate engineering rules. This helper
    # does not invent those rules or reject a long crossing anchorage.
    interior['vertical']['hook_bottom_cm'] = 300
    exterior['horizontal']['hook_join_cm'] = 300
    assert opposed_mesh_issues(profile, exterior, interior) == []
    interior['horizontal']['diameter_mm'] += 1
    assert len(opposed_mesh_issues(profile, exterior, interior)) == 2


def test_opposed_layers_do_not_substitute_missing_inputs():
    _, _, exterior, profile = configured()
    interior = deepcopy(exterior)
    interior['vertical']['diameter_mm'] = None
    assert opposed_mesh_issues(profile, exterior, interior) == []
