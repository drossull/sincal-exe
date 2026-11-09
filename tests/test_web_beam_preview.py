"""Moldaje de viga: proyecciones fieles y lectura sin mutar el proyecto."""
from copy import deepcopy
import math

import pytest

from sincal.rebar.beam_profiles import PROFILE_KEYS, resolve_profile
from sincal.web.beam_preview import preview


def project():
    # Valores geométricos comprobados en T34; no depende de archivos del usuario.
    return {
        'parametros_generales': {'angulo_esviaje_puente': -12.},
        'elementos_comunes': {'vigas': {'num_vigas': 4, 'separacion_vigas': 2600., 'offset_y_vigas': 50.}},
        'tableros': [{'nombre_grupo_tablero': f'Tablero_0{5-i}', 'largo_losa': 35734.19145,
                      'tipo_viga_seleccionado': 6, 'pendiente_longitudinal': -.005,
                      'usar_grupo_tablero': True} for i in range(5)],
    }


def test_t34_reads_catalog_and_keeps_every_board_and_original_data():
    data = project()
    before = deepcopy(data)
    result = preview(data)
    assert result['valid'] and not result['issues']
    assert result['profile']['name'] == 'Viga H200'
    assert result['profile']['source'] == 'catalog'
    assert result['profile']['parameters_mm']['d7'] == 2000
    assert len(result['boards']) == 5
    assert sum(b['beam_count'] for b in result['boards']) == 20
    geometry = result['geometry']
    assert geometry['length_projected_m'] == pytest.approx(35.63419145)
    assert geometry['offset_m'] == .05
    assert geometry['beam_spacing_m'] == 2.6
    assert geometry['beam_center_offset_m'] == pytest.approx(-3.9)
    assert result['scene']['specimen_length_m'] == .75
    assert result['scene']['scope'] == 'interior_sample'
    assert result['full_scene']['scope'] == 'full_beam'
    assert data == before
    result['profile']['parameters_mm']['d7'] = -1
    assert preview(data)['profile']['parameters_mm']['d7'] == 2000


def test_group_flag_is_not_board_activation():
    data = project()
    data['tableros'][0]['usar_grupo_tablero'] = False
    result = preview(data)
    assert result['valid'] and len(result['boards']) == 5


@pytest.mark.parametrize('skew', (-25., 0., 12.))
@pytest.mark.parametrize('slope', (-.07, 0., .025))
def test_projection_reconstructs_rotated_extrusion_and_cut_planes(skew, slope):
    data = project()
    data['parametros_generales']['angulo_esviaje_puente'] = skew
    data['tableros'][0]['pendiente_longitudinal'] = slope
    result = preview(data)
    assert result['valid']
    length = result['geometry']['length_projected_m']
    shear = math.tan(math.radians(skew))
    alpha = math.atan(-slope)
    c, s = math.cos(alpha), math.sin(alpha)
    for u, x in result['views']['plan']['outline']:
        assert min(abs(u-x*shear), abs(u-x*shear-length)) < 1e-10
    # Reconstruct in 3D independently: rotate (x,q,z), then intersect the
    # extrusion ray with each vertical cut plane. Its outer-side projection
    # must be present in the exact (possibly concave) elevation boundary.
    elevation = result['views']['elevation']['outline']
    profile = result['profile']['section_m']
    for x, z in profile:
        for end in (0., length):
            if (end == 0 and x*shear > 1e-12) or (end == length and x*shear < -1e-12):
                continue
            target_y = end+x*shear
            q = (target_y+z*s)/c
            rotated_y = q*c-z*s
            rotated_z = q*s+z*c
            assert min(math.dist(p, (rotated_y, rotated_z)) for p in elevation) < 1e-9
    # Same scale: change along a projected longitudinal edge is exactly -pΔu.
    for (u1, z1), (u2, z2) in result['views']['elevation']['lines']:
        assert z2-z1 == pytest.approx(-slope*(u2-u1))
    # The complete 3D scene has those same cut planes; it is not an uncut or
    # rescaled extrusion fitted to the extent of the previous 2D drawings.
    n = len(profile)
    for end_index, end in enumerate((0., length)):
        for i, (x, z) in enumerate(profile):
            vx, vy, vz = result['full_scene']['vertices'][end_index*n+i]
            q = (end+x*shear+z*s)/c
            assert [vx, vy, vz] == pytest.approx([x, q*c-z*s, q*s+z*c])


@pytest.mark.parametrize('slope', (-.07, 0., .025))
@pytest.mark.parametrize('skew', (-25., 0., 12.))
def test_short_scene_is_a_rigid_interior_sample_not_a_skewed_or_compressed_beam(slope, skew):
    data = project()
    data['tableros'][0].update(pendiente_longitudinal=slope, angulo_esviaje_puente=skew)
    result = preview(data)
    scene = result['scene']
    n = len(result['profile']['section_m'])
    assert scene['specimen_length_m'] == .75
    assert len(scene['vertices']) == 2*n
    assert len(scene['edges']) == 3*n
    assert len(scene['faces']) == n+2
    c, s = math.cos(math.atan(-slope)), math.sin(math.atan(-slope))
    for i, (x, z) in enumerate(result['profile']['section_m']):
        near, far = scene['vertices'][i], scene['vertices'][i+n]
        assert near == pytest.approx([x, -z*s, z*c])
        assert far == pytest.approx([x, .75*c-z*s, .75*s+z*c])
        assert math.dist(near, far) == pytest.approx(.75)
    # Place the translated sample back along the original beam axis: all of
    # its vertices must lie between the actual two skewed end planes.
    for x, y, z in scene['vertices']:
        actual_y = y+scene['start_station_m']*c
        cut_y = x*math.tan(math.radians(skew))
        assert cut_y-1e-10 <= actual_y <= cut_y+result['geometry']['length_projected_m']+1e-10


def test_front_and_isometric_views_project_the_same_native_scene_without_amplifying_slope():
    data = project()
    data['tableros'][0]['pendiente_longitudinal'] = .07
    result = preview(data)
    scene = result['scene']
    for view in ('front', 'isometric'):
        item = result['views'][view]
        assert item['scope'] == 'interior_sample'
        assert item['projection'] == 'orthographic'
        assert len(item['vertices']) == len(scene['vertices'])
        for (x, y, z), actual in zip(scene['vertices'], item['vertices']):
            expected = ([x, z] if view == 'front' else
                        [(x+y)/math.sqrt(2), z*math.sqrt(2/3)+(y-x)/math.sqrt(6)])
            assert actual == pytest.approx(expected)
        assert item['outline'] == [item['vertices'][i] for i in scene['faces'][0]]
        assert item['lines'] == [[item['vertices'][i], item['vertices'][j]] for i, j in scene['edges']]
    # A front view must retain all shoulders and recesses, not a rectangle.
    assert len(result['views']['front']['outline']) == len(result['profile']['section_m'])


def test_sample_length_is_limited_by_available_interior_and_missing_interior_preserves_full_view():
    data = project()
    data['tableros'][0].update(largo_losa=400, pendiente_longitudinal=0, angulo_esviaje_puente=0)
    result = preview(data)
    assert result['valid']
    assert result['scene']['specimen_length_m'] == pytest.approx(.3)
    data['tableros'][0]['angulo_esviaje_puente'] = 60
    result = preview(data)
    assert result['valid'] and result['full_scene']['vertices']
    assert result['scene'] is None
    assert result['views']['front'] == {'outline': [], 'lines': []}
    assert result['views']['isometric'] == {'outline': [], 'lines': []}
    assert result['views']['plan']['outline'] and result['views']['elevation']['outline']
    assert any('tramo interior' in issue for issue in result['issues'])


def test_skewed_elevation_keeps_the_web_recess_instead_of_convex_hull():
    result = preview(project())
    points = result['views']['elevation']['outline']
    web_start = result['profile']['parameters_mm']['d6']+result['profile']['parameters_mm']['d5']+result['profile']['parameters_mm']['d4']
    shear = math.tan(math.radians(-12))
    u = -abs(shear)*.1
    z = web_start/1000*math.hypot(1, -.005)+.005*u
    assert any(math.dist(p, (u, z)) < 1e-10 for p in points)
    assert len(points) > 4


def test_board_overrides_and_beam_number_preserve_common_values():
    data = project()
    data['tableros'][1].update(num_vigas=2, separacion_vigas=3000, offset_y_vigas=120,
                                tipo_viga_seleccionado=7, pendiente_longitudinal=.01,
                                angulo_esviaje_puente=8)
    before = deepcopy(data)
    result = preview(data, 1, 1)
    assert result['valid']
    assert result['profile']['name'] == 'Viga H220'
    assert result['geometry']['beam_count'] == 2
    assert result['geometry']['beam_center_offset_m'] == 1.5
    assert result['geometry']['beam_spacing_m'] == 3.
    assert result['geometry']['offset_m'] == .12
    assert result['geometry']['skew_degrees'] == 8
    assert result['geometry']['length_projected_m'] == pytest.approx(35.49419145)
    assert preview(data, 0, 3)['geometry']['beam_center_offset_m'] == pytest.approx(3.9)
    assert data == before


@pytest.mark.parametrize('key', ('num_vigas', 'separacion_vigas', 'offset_y_vigas'))
def test_missing_common_measure_is_reported_without_defaulting(key):
    data = project()
    del data['elementos_comunes']['vigas'][key]
    result = preview(data)
    assert not result['valid'] and result['issues']
    assert result['geometry'] is None
    assert not result['views']['plan']['outline']


@pytest.mark.parametrize('key', ('largo_losa', 'tipo_viga_seleccionado', 'pendiente_longitudinal'))
def test_missing_board_measure_is_not_invented(key):
    data = project()
    del data['tableros'][0][key]
    result = preview(data)
    assert not result['valid'] and result['issues']
    assert result['profile'] is None


@pytest.mark.parametrize('type_value', (999, 6.5, True, None))
def test_unknown_or_invalid_profile_never_falls_back_to_h200(type_value):
    data = project()
    data['tableros'][0]['tipo_viga_seleccionado'] = type_value
    result = preview(data)
    assert not result['valid'] and result['profile'] is None


def test_zero_vigas_and_invalid_indexes_keep_boards_available():
    data = project()
    data['tableros'][0]['num_vigas'] = 0
    result = preview(data)
    assert not result['valid'] and result['boards'][0]['beam_count'] == 0
    assert preview(data, 1)['valid']
    for board, beam in ((-1, 0), (5, 0), (0, -1), (1, 4), (True, 0)):
        result = preview(data, board, beam)
        assert not result['valid'] and result['issues']
        assert len(result['boards']) == 5


@pytest.mark.parametrize('skew', (-90, 90, float('nan')))
def test_invalid_skew_has_no_preview(skew):
    data = project()
    data['parametros_generales']['angulo_esviaje_puente'] = skew
    assert not preview(data)['valid']


def test_custom_profile_geometry_is_read_from_json_and_validated():
    data = project()
    original = resolve_profile(6)['parameters_mm']
    custom = {'tipo': 101, 'nombre': 'Sección particular', **{key: original[key] for key in PROFILE_KEYS}}
    custom['d7'] = 2150
    data['elementos_comunes']['vigas']['perfiles_viga_personalizados'] = [custom]
    data['tableros'][0]['tipo_viga_seleccionado'] = 101
    before = deepcopy(data)
    result = preview(data)
    assert result['valid'] and result['profile']['source'] == 'custom'
    assert max(z for x, z in result['profile']['section_m']) == 2.15
    assert data == before
    custom['b1'] = 150
    assert not preview(data)['valid']


@pytest.mark.parametrize('beam_type', range(1, 15))
def test_all_catalog_profiles_have_finite_symmetric_section(beam_type):
    data = project()
    data['tableros'][0]['tipo_viga_seleccionado'] = beam_type
    result = preview(data)
    assert result['valid'], result['issues']
    points = result['profile']['section_m']
    assert all([-x, z] in points for x, z in points)
    assert min(z for x, z in points) == 0
    assert max(z for x, z in points)*1000 == pytest.approx(result['profile']['parameters_mm']['d7'])


@pytest.mark.parametrize('value', (None, {}, {'tableros': []}, {'tableros': [None]}))
def test_incomplete_project_returns_consistent_empty_contract(value):
    result = preview(value)
    assert not result['valid'] and result['issues']
    assert result['views'] == {key: {'outline': [], 'lines': []}
                               for key in ('plan', 'elevation', 'front', 'isometric')}
    assert result['scene'] is None and result['full_scene'] is None
