from copy import deepcopy
import json
import math
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from sincal.web.abutment_scene import build_scene
from sincal.web.rebar import from_project
from sincal.web.server import Server


def example():
    es={}
    for key in ('entrada','salida'):
        es.update({f'tipo_estribo_{key}':'muro_lleno',f'dado_muro_frontal_ancho_{key}':11596,
                   f'dado_muro_frontal_largo_{key}':7500,f'dado_muro_frontal_espesor_{key}':1500,
                   f'dado_muro_frontal_avance_{key}':1500,f'ancho_mesa_apoyo_estribo_{key}':1800,
                   f'altura_muro_frontal_estribo_{key}':1000,f'espesor_muro_espaldar_{key}':500,
                   f'espesor_muro_ala_{key}':500,f'largo_muro_ala_{key}':3200,
                   f'rotacion_muro_ala_{key}_izq':0,f'rotacion_muro_ala_{key}_der':0,
                   f'incluir_pilotes_dado_estribo_{key}':False,f'pilotes_dado_estribo_{key}_diametro':1500,
                   f'pilotes_dado_estribo_{key}_largo':10000,f'pilotes_dado_estribo_{key}_cantidad_transversal':3,
                   f'pilotes_dado_estribo_{key}_cantidad_longitudinal':2,
                   f'pilotes_dado_estribo_{key}_separacion_transversal':3000,
                   f'pilotes_dado_estribo_{key}_separacion_longitudinal':3000,
                   f'incluir_consola_frontal_{key}':False,f'consola_frontal_{key}_largo':500,
                   f'consola_frontal_{key}_profundidad_borde':300})
    es.update(incluir_topes_interiores_estribos=True,ancho_tope_interior_estribos=500,
              junta_dilatacion_estribos=160,incluir_losas_acceso=True,tipo_losa_acceso=1,
              espesor_losa_acceso=250,largo_losa_acceso=3000)
    return {'parametros_generales':{'angulo_esviaje_puente':-12},'estribos':es,
            'cepas':{'parametros_globales':{'ancho_tope_exterior':500,'num_topes_interiores':2,'offset_cabezal_bajo_placa':20}},
            'elementos_comunes':{
                'pavimento':{'ancho_izq_pav':4000,'ancho_der_pav':3500,'pend_izq_pav':-.02,'pend_der_pav':.02,'espesor_pav':50},
                'pasillos':{'incluir_pasillo_izq':False,'incluir_pasillo_der':True,'tipo_barrera_izquierda':'SIN','tipo_barrera_derecha':'SIN','ancho_pasillo_der':2505,'pend_pasillo_der':.01},
                'losa':{'espesor_losa':220},'vigas':{'num_vigas':4,'separacion_vigas':2600,'offset_y_vigas':50},
                'travesanos':{'offset_travesano_extremo_desde_borde_losa':800,'altura_recorte_travesano_sobre_cepa':400},
                'placas_apoyo':{'ancho_total_neopreno_estribo':500,'longitud_total_neopreno_estribo':500,
                                'num_placas_acero_internas_3mm_estribo':5,'espesor_capa_neopreno_pura_estribo':12,
                                'sin_inserto_inferior_estribo':False}},
            'tableros':[{'tipo_viga_seleccionado':6,'pendiente_longitudinal':-.005}]}


def find(scene, key):
    return next(e for e in scene['elements'] if e['key']=='abutment.'+key)


def points(element):
    return [p for m in element['meshes'] for p in m['vertices']]


def test_full_instance_meshes_are_finite_and_source_is_immutable():
    data=example();before=deepcopy(data)
    scene=build_scene(data,'entrada')
    assert data==before
    assert {e['key'] for e in scene['elements']}=={'abutment.footing','abutment.front_wall','abutment.back_wall','abutment.left_wing','abutment.right_wing','abutment.front_stop','abutment.back_console','abutment.access_slab'}
    assert scene['units']=='m' and scene['bars']==[]
    for e in scene['elements']:
        for mesh in e['meshes']:
            assert all(len(p)==3 and all(math.isfinite(v) for v in p) for p in mesh['vertices'])
            assert all(len(face)>=3 and all(0<=i<len(mesh['vertices']) for i in face) for face in mesh['faces'])
    assert find(scene,'back_wall')['quality']=='schematic'
    assert find(scene,'front_stop')['quality']=='schematic'
    assert any('nominal' in issue for issue in scene['issues'])


def test_footing_geometry_uses_project_puentes_skew_and_origin():
    scene=build_scene(example(),'entrada');vertices=points(find(scene,'footing'))
    theta=math.radians(-12);c=math.cos(theta);t=math.tan(theta)
    assert max(p[0] for p in vertices)-min(p[0] for p in vertices)==pytest.approx(11.596*c)
    ss=[y-x*t for x,y,z in vertices]
    assert max(ss)-min(ss)==pytest.approx(7.5/c)
    assert set(p[2] for p in vertices)=={0,1.5}
    assert sum(p[0] for p in vertices)==pytest.approx(0)
    assert sum(p[1] for p in vertices)==pytest.approx(0)


def test_missing_field_omits_geometry_without_substitution():
    data=example();del data['estribos']['dado_muro_frontal_largo_entrada']
    scene=build_scene(data,'entrada')
    assert scene['elements']==[] and scene['bars']==[]
    assert 'dado_muro_frontal_largo_entrada' in scene['issues'][0]
    data=example();del data['elementos_comunes']['placas_apoyo']['longitud_total_neopreno_estribo']
    scene=build_scene(data,'entrada')
    assert find(scene,'front_wall')
    assert not any(e['key']=='abutment.back_wall' for e in scene['elements'])
    assert any('longitud_total_neopreno_estribo' in s for s in scene['issues'])


@pytest.mark.parametrize('active',[False,None,0,1,'true','false'])
def test_piles_require_boolean_activation(active):
    data=example();data['estribos']['incluir_pilotes_dado_estribo_entrada']=active
    scene=build_scene(data,'entrada')
    assert not any(e['key']=='abutment.pile' for e in scene['elements'])


def test_piles_have_grid_centres_and_full_length_below_foundation():
    data=example();data['estribos']['incluir_pilotes_dado_estribo_entrada']=True
    scene=build_scene(data,'entrada');pile=find(scene,'pile')
    assert len(pile['meshes'])==6
    assert {p[2] for p in points(pile)}=={-10,0}
    centres=[[sum(p[i] for p in mesh['vertices'])/len(mesh['vertices']) for i in (0,1)] for mesh in pile['meshes']]
    assert sum(p[0] for p in centres)==pytest.approx(0)
    assert sum(p[1] for p in centres)==pytest.approx(0)
    assert not any(e['key']=='abutment.pile' for e in build_scene(data,'salida')['elements'])


def test_state_mismatch_does_not_deform_mouldage_or_draw_rebar():
    data=example();state=from_project(data)['entrada'];state['geometry']['ancho_cm']=999
    scene=build_scene(data,'entrada',state)
    assert scene['bars']==[]
    assert scene['footing']['width_m']==11.596
    assert any('difiere del JSON' in issue for issue in scene['issues'])


def test_matching_state_draws_only_existing_footing_distribution():
    data=example();state=from_project(data)['entrada'];before=deepcopy(state)
    scene=build_scene(data,'entrada',state)
    assert state==before
    assert scene['bars'] and all(b['element_key']=='abutment.footing' for b in scene['bars'])
    assert 'ganchos' in scene['reinforcement_note']
    assert not scene['geometry_only']


@pytest.mark.parametrize('field,value,source',[
    ('ancho_cm',1100,'dado_muro_frontal_ancho_entrada'),
    ('largo_cm',650,'dado_muro_frontal_largo_entrada'),
    ('alto_cm',180,'dado_muro_frontal_espesor_entrada'),
    ('esviaje_grados',18,'angulo_esviaje_puente'),
])
def test_editor_scene_rebuilds_changed_dimensions_and_keeps_source_immutable(field,value,source):
    data=example();state=from_project(data)['entrada'];state['geometry'][field]=value
    before_data,before_state=deepcopy(data),deepcopy(state)
    scene=build_scene(data,'entrada',state,use_state_geometry=True)
    assert data==before_data and state==before_state
    assert scene['geometry_source']=='parameters' and scene['geometry_edited']
    assert any('dimensiones editadas' in issue for issue in scene['issues'])
    assert scene['bars'] and not any('difiere del JSON' in issue for issue in scene['issues'])
    # Rebuilding an independent reference JSON must produce exactly the same
    # complete mouldage and calculated steel, rather than scaling old lines.
    expected_data=deepcopy(data)
    expected_data['parametros_generales' if field=='esviaje_grados' else 'estribos'][source]=value if field=='esviaje_grados' else value*10
    expected=build_scene(expected_data,'entrada',state)
    assert scene['elements']==expected['elements']
    assert scene['bars']==expected['bars']
    g=state['geometry'];angle=math.radians(g['esviaje_grados']);c=math.cos(angle);t=math.tan(angle)
    footprint=points(find(scene,'footing'))
    assert max(p[0] for p in footprint)-min(p[0] for p in footprint)==pytest.approx(g['ancho_cm']/100*c)
    assert max(y-x*t for x,y,z in footprint)-min(y-x*t for x,y,z in footprint)==pytest.approx(g['largo_cm']/100/c)
    assert {p[2] for p in footprint}=={0,g['alto_cm']/100}
    for bar in scene['bars']:
        for x,y,z in bar['points']:
            assert abs(x)<g['ancho_cm']/200*c
            assert abs(y-x*t)<g['largo_cm']/200/c
            assert 0<z<g['alto_cm']/100
    # A draft for entry must not leak into another instance or later JSON view.
    assert build_scene(data,'salida')['footing']['height_m']==1.5
    assert build_scene(data,'entrada')['footing']['width_m']==11.596


def test_editor_height_moves_wall_base_but_not_pile_bottom_or_length():
    data=example();data['estribos']['incluir_pilotes_dado_estribo_entrada']=True
    state=from_project(data)['entrada'];state['geometry']['alto_cm']=180
    scene=build_scene(data,'entrada',state,use_state_geometry=True)
    assert min(p[2] for p in points(find(scene,'front_wall')))==1.8
    assert {p[2] for p in points(find(scene,'pile'))}=={-10,0}


@pytest.mark.parametrize('value',[None,True,-1,0,20000,'150',float('nan'),float('inf')])
def test_invalid_editor_geometry_never_falls_back_to_the_json(value):
    data=example();state=from_project(data)['entrada'];state['geometry']['alto_cm']=value
    scene=build_scene(data,'entrada',state,use_state_geometry=True)
    assert scene['elements']==[] and scene['bars']==[]
    assert scene['issues'] and any('alto_cm' in issue for issue in scene['issues'])
    assert 'footing' not in scene


def test_editor_requires_explicit_geometry_but_allows_missing_json_measure():
    data=example();state=from_project(data)['entrada']
    assert build_scene(data,'entrada',None,use_state_geometry=True)['elements']==[]
    del data['estribos']['dado_muro_frontal_largo_entrada']
    assert build_scene(data,'entrada',state)['elements']==[]
    scene=build_scene(data,'entrada',state,use_state_geometry=True)
    assert scene['footing']['length_m']==7.5 and scene['bars']


def test_editor_cover_change_updates_steel_without_changing_mouldage():
    data=example();state=from_project(data)['entrada']
    original=build_scene(data,'entrada',state,use_state_geometry=True)
    state['cover']['superior_cm']=10
    updated=build_scene(data,'entrada',state,use_state_geometry=True)
    assert updated['elements']==original['elements']
    assert updated['bars']!=original['bars']
    assert updated['geometry_source']=='parameters' and not updated['geometry_edited']
    original_by_id={bar['id']:bar for bar in original['bars']}
    for after in updated['bars']:
        before=original_by_id[after['id']]
        if before['level']=='superior':
            assert after['points'][0][2]==pytest.approx(before['points'][0][2]-.05)
        elif before['level']=='inferior':
            assert after==before
        radius=after['diameter_mm']/2000
        assert min(p[2] for p in after['points'])-radius>=state['cover']['inferior_cm']/100-1e-9
        assert max(p[2] for p in after['points'])+radius<=updated['footing']['height_m']-.10+1e-9
    for key in ('lateral_x','lateral_y'):
        before=[bar for bar in original['bars'] if bar['key']==key]
        after=[bar for bar in updated['bars'] if bar['key']==key]
        assert before and after and after!=before
        assert len(after)<=len(before)
        # Inicio follows the upper bend tangency. Its fixed spacing may move
        # the last row too; the lower mesh itself remains unchanged above.
        assert max(bar['main_start'][2] for bar in after)==pytest.approx(
            max(bar['main_start'][2] for bar in before)-.05)
        mesh_key='mesh_y' if key=='lateral_x' else 'mesh_x'
        lower_mesh=next(bar for bar in updated['bars']
                        if bar['key']==mesh_key and bar['level']=='inferior')
        lower_tangent=lower_mesh['main_start'][2]+3*lower_mesh['diameter_mm']/1000
        assert -1e-9<=min(bar['main_start'][2] for bar in after)-lower_tangent<.1+1e-9


def test_entry_and_exit_mirror_longitudinal_position_without_reusing_instance():
    data=example();entry=build_scene(data,'entrada');exit_=build_scene(data,'salida')
    def mean_s(scene):
        pts=points(find(scene,'front_wall'));t=math.tan(math.radians(-12))
        return sum(y-x*t for x,y,z in pts)/len(pts)
    assert mean_s(entry)==pytest.approx(-mean_s(exit_))
    data['estribos']['dado_muro_frontal_espesor_salida']=2000
    assert build_scene(data,'salida')['footing']['height_m']==2
    assert build_scene(data,'entrada')['footing']['height_m']==1.5


def test_explicit_consoles_and_counterforts_are_supported():
    data=example();es=data['estribos']
    es.update(incluir_consola_losa_acceso=True,consola_losa_acceso_ancho_apoyo=250,consola_losa_acceso_canto_vertical=250,
              incluir_consola_frontal_entrada=True,incluir_contrafuertes_mura_ala_entrada=True,
              contrafuerte_entrada_espesor=300,contrafuerte_entrada_ancho_superior=100,
              contrafuerte_entrada_ancho_inferior=350,contrafuerte_entrada_distancia_libre=500,
              contrafuerte_entrada_altura_zona_pendiente=1200,contrafuerte_entrada_offset_inferior=200)
    scene=build_scene(data,'entrada')
    assert find(scene,'back_console') and find(scene,'front_console') and find(scene,'counterfort')
    assert all(b['element_key']=='abutment.footing' for b in scene['bars'])


@pytest.mark.parametrize('instance',[None,'','cepa','Entrada'])
def test_rejects_unknown_instance(instance):
    with pytest.raises(ValueError):build_scene(example(),instance)


def test_scene_http_is_local_authenticated_read_only_and_static_is_served(tmp_path):
    server=Server(0,tmp_path);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        body=json.dumps({'project':example(),'instance_key':'entrada'}).encode()
        path=server.origin+'/api/rebar/abutment/scene'
        with pytest.raises(HTTPError) as failed:
            urlopen(Request(path,data=body,headers={'Content-Type':'application/json'}),timeout=5)
        assert failed.value.code==401
        headers={'Content-Type':'application/json','X-Sincal-Token':server.token}
        with urlopen(Request(path,data=body,headers=headers),timeout=5) as response:
            assert find(json.loads(response.read()),'footing')
        state=from_project(example())['entrada'];state['geometry']['alto_cm']=180
        draft={'project':example(),'instance_key':'entrada','state':state,'use_state_geometry':True}
        with urlopen(Request(path,data=json.dumps(draft).encode(),headers=headers),timeout=5) as response:
            scene=json.loads(response.read())
            assert scene['footing']['height_m']==1.8 and scene['bars']
            assert scene['geometry_source']=='parameters'
        draft['use_state_geometry']='true'
        with urlopen(Request(path,data=json.dumps(draft).encode(),headers=headers),timeout=5) as response:
            scene=json.loads(response.read())
            assert scene['footing']['height_m']==1.5 and not scene['bars']
            assert scene['geometry_source']=='project'
        with urlopen(server.origin+'/rebar_isometric.js',timeout=5) as response:
            assert 'openAbutmentIsometric' in response.read().decode()
        with pytest.raises(HTTPError) as failed:
            urlopen(Request(path,data=json.dumps({'project':{},'instance_key':'cepa'}).encode(),headers=headers),timeout=5)
        assert failed.value.code==400
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
