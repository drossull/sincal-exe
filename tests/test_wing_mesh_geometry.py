"""Physical cover checks against the actual concrete faces, in world metres."""
from copy import deepcopy
import math

import pytest

from sincal.web.rebar import from_project as footing_states
from sincal.web.wing_exterior import from_project, preview
from sincal.web.wing_geometry import build_wing_profile, extract_geometry
from tests.test_web_wing_geometry import project


def configured(side='left', skew=-12, extension=True, rotation=0, instance='entrada'):
    data = project(extension=extension, skew=skew, rotation=rotation)
    data['estribos'][f'espesor_muro_ala_{instance}'] = 800
    abutment = footing_states(data)[instance]
    state = from_project(data, instance, side, abutment)['state']
    # Exercise the mesh geometry independently of the later mandatory edge family.
    state.pop('edge_rebar', None)
    state['geometry_confirmed'] = True
    state['cover'] = dict.fromkeys(state['cover'], 5.)
    state['vertical'].update(diameter_mm=16, spacing_cm=20, mark_main='11', mark_extension='12')
    state['horizontal'].update(diameter_mm=12, spacing_cm=20, hook_join_cm=40,
                               mark_main='13', mark_upper='14')
    state.update(outer_family='vertical', horizontal_start='wall')
    profile = build_wing_profile(extract_geometry(data, instance, side, abutment), state['geometry'])
    return data, abutment, state, profile


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def inward_plane(mesh, indices):
    vertices = mesh['vertices']
    a, b, c = (vertices[index] for index in indices[:3])
    ab, ac = tuple(y-x for x,y in zip(a,b)), tuple(y-x for x,y in zip(a,c))
    normal = (ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0])
    size = math.hypot(*normal)
    normal = tuple(value/size for value in normal)
    center = tuple(sum(point[i] for point in vertices)/len(vertices) for i in range(3))
    if dot(normal, tuple(value-zero for value, zero in zip(center, a))) < 0:
        normal = tuple(-value for value in normal)
    return lambda point: dot(normal, tuple(value-zero for value, zero in zip(point, a)))


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('instance', ['entrada', 'salida'])
@pytest.mark.parametrize('skew', [0, -12, 12])
@pytest.mark.parametrize('extension', [False, True])
def test_verticals_and_whole_hooks_respect_each_actual_face(side, instance, skew, extension):
    data, abutment, state, profile = configured(side, skew, extension, instance=instance)
    original = deepcopy((data, abutment, state))
    result = preview(data, instance, side, state, abutment)
    assert result['valid'], result['issues']
    assert (data, abutment, state) == original
    foundation_top = profile['frame']['origin_m'][2]
    main_count = extension_count = 0
    for bar in result['bars']:
        if 'vertical' not in bar['key']:
            continue
        short = bar['key'].endswith('vertical_extension')
        mesh = profile['meshes'][1 if short else 0]
        radius = bar['diameter_mm']/2000
        if short:
            extension_count += 1
        else:
            main_count += 1
            assert min(point[2] for point in bar['points']) == pytest.approx(abutment['cover']['inferior_cm']/100+radius)
        checks = [((0, 1, 2, 3), 'outside_cm'), ((4, 5, 6, 7), 'inside_cm'),
                  ((1, 2, 6, 5), 'end_cm'), ((0, 3, 7, 4), 'end_cm'),
                  ((3, 2, 6, 7), 'top_cm')]
        if short:
            checks.append(((0, 1, 5, 4), 'diagonal_cm'))
        for indices, cover in checks:
            distance = inward_plane(mesh, indices)
            for point in bar['points']:
                if not short and point[2] < foundation_top:
                    continue
                assert distance(point) >= state['cover'][cover]/100+radius-1e-8, (bar['id'], cover, point)
    assert main_count > 0
    assert bool(extension_count) == extension


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('skew', [-12, 12])
def test_all_lower_vertical_hooks_stay_inside_footing_clear_cover(side, skew):
    data, abutment, state, profile = configured(side, skew)
    result = preview(data, 'entrada', side, state, abutment)
    assert result['valid'], result['issues']
    theta = math.radians(skew)
    half_x = abutment['geometry']['ancho_cm']/200*math.cos(theta)
    half_s = abutment['geometry']['largo_cm']/200
    for bar in result['bars']:
        if not bar['key'].endswith('vertical_main'):
            continue
        required = abutment['cover']['lateral_cm']/100+bar['diameter_mm']/2000
        for x, y, z in bar['points']:
            if z >= profile['frame']['origin_m'][2]:
                continue
            assert half_x-abs(x) >= required-1e-8
            assert half_s-abs(y*math.cos(theta)-x*math.sin(theta)) >= required-1e-8


def contains_xy(mesh, point):
    vertices = mesh['vertices'][:len(mesh['vertices'])//2]
    center = tuple(sum(p[i] for p in vertices)/len(vertices) for i in range(2))
    for a, b in zip(vertices, (*vertices[1:], vertices[0])):
        normal = (b[1]-a[1], a[0]-b[0])
        bound = dot(normal, a)
        if dot(normal, center) > bound:
            normal, bound = tuple(-value for value in normal), -bound
        if dot(normal, point) > bound+1e-8:
            return False
    return True


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('skew', [-12, 0, 12])
def test_horizontal_front_hooks_below_actual_transverse_sloping_roof(side, skew):
    data, abutment, state, profile = configured(side, skew)
    result = preview(data, 'entrada', side, state, abutment)
    assert result['valid'], result['issues']
    tested = 0
    for bar in result['bars']:
        if 'horizontal' not in bar['key']:
            continue
        meshes = profile['back_wall_meshes' if bar['key'].endswith('horizontal_upper') else 'front_wall_meshes']
        for point in bar['points']:
            # The front hook is the final straight segment of the bracket.
            if math.dist(point, bar['points'][-1]) > .40000001:
                continue
            matches = [mesh for mesh in meshes if contains_xy(mesh, point)]
            assert matches, (bar['id'], point)
            required = state['cover']['top_cm']/100+bar['diameter_mm']/2000
            distances = [inward_plane(mesh, (4, 5, 6, 7))(point) for mesh in matches]
            assert min(distances) >= required-1e-8
            tested += 1
    assert tested > 0


@pytest.mark.parametrize('extension', [False, True])
def test_rotated_main_wing_outside_footing_is_rejected_without_shortening(extension):
    data, abutment, state, profile = configured('right', -12, extension, rotation=15)
    saved = deepcopy((state, profile))
    result = preview(data, 'entrada', 'right', state, abutment)
    assert not result['valid'] and not result['bars']
    assert any('huella de la zapata' in issue['message'] for issue in result['issues'])
    assert (state, profile) == saved


def test_nonplanar_nominal_roof_requires_review_instead_of_invented_surface():
    data, abutment, state, _ = configured(extension=False)
    state['geometry']['top_edge_cm'] += 60
    result = preview(data, 'entrada', 'left', state, abutment)
    # A skewed rear/front shear plus changing one exterior height can make
    # the four supplied roof corners noncoplanar.
    assert not result['valid']
    assert any('no es plana' in issue['message'] for issue in result['issues'])


def test_hooks_that_do_not_fit_are_rejected_and_nominal_confirmation_is_required():
    data, abutment, state, _ = configured()
    state['geometry_confirmed'] = False
    result = preview(data, 'entrada', 'left', state, abutment)
    assert not result['valid'] and not result['bars']
    assert any('confirma' in issue['message'] for issue in result['issues'])
    state['geometry_confirmed'] = True
    state['vertical']['hook_top_cm'] = 80
    result = preview(data, 'entrada', 'left', state, abutment)
    assert not result['valid'] and not result['bars']
    assert any('no cabe' in issue['message'] for issue in result['issues'])
    assert state['vertical']['hook_top_cm'] == 80
