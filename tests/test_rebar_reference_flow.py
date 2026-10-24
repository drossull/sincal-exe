from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from sincal.cad.zapata_views import build_zapata_lisp as real_build_zapata_lisp
from sincal.web import cad_worker
from sincal.web.rebar import defaults
from sincal.web.rebar import domain, reference_candidate, reference_sequence, drawing_units_per_m
from sincal.cad.moldajes import MoldajeContext
from sincal.web.services import Services


FR_WITHOUT_PILE = [
    "abutment.footing",
    "abutment.front_wall",
    "abutment.back_wall",
]
FR_WITH_PILE = [
    "abutment.footing",
    "abutment.pile",
    "abutment.front_wall",
    "abutment.back_wall",
]


@pytest.mark.parametrize('view,width,height', [('FR',11.596,1.5),('AA',7.5,1.5),
                                              ('BB',7.5,1.5),('CC',7.5,1.5),('FF',11.596,7.5)])
@pytest.mark.parametrize('factor', [1,100,1000])
def test_reference_preserves_location_and_calculated_dimensions(view,width,height,factor):
    points = [(x*factor,y*factor,0) for x,y in
              [(-100,200+height),(-100+width,200+height),(-100+width,200),(-100,200)]]
    geometry,_,_ = domain(defaults())
    result = reference_candidate(points,factor,MoldajeContext('abutment.footing','entrada',view),geometry,{})
    assert min(p[0] for p in result.vertices) == pytest.approx(-100)
    assert min(p[1] for p in result.vertices) == pytest.approx(200)
    assert result.area_m2 == pytest.approx(width*height)
    assert result.layer == '' and result.handle == ''


def test_skewed_plan_rejects_two_corner_box_instead_of_assuming_json_skew():
    import math
    state = defaults(); state['geometry']['esviaje_grados']=-12
    geometry,_,_ = domain(state)
    delta=7.5*math.tan(math.radians(-12))
    width=11.596+abs(delta)
    points=((0,7.5,0),(width,7.5,0),(width,0,0),(0,0,0))
    project={'estribos':{'orientacion_dado_estribo_entrada':'romboide'}}
    with pytest.raises(ValueError, match='tres'):
        reference_candidate(points,1,MoldajeContext('abutment.footing','entrada','FF'),geometry,project)


def test_unknown_units_and_nonzero_plane_require_explicit_correction():
    with pytest.raises(ValueError,match='Elige'):
        drawing_units_per_m({'active':{'insunits':0}})
    assert drawing_units_per_m({'active':{'insunits':6}},'mm') == 1000
    geometry,_,_=domain(defaults())
    with pytest.raises(ValueError,match='Z = 0'):
        reference_candidate([(0,1.5,2),(11.596,1.5,2),(11.596,0,2),(0,0,2)],1,
                            MoldajeContext('abutment.footing','entrada','FR'),geometry,{})


def test_reference_sequence_is_specific_to_view():
    project={'estribos':{'tipo_estribo_entrada':'muro_lleno','incluir_pilotes_dado_estribo_entrada':True}}
    assert [e['key'] for e in reference_sequence(project,'entrada','FF')] == ['abutment.footing']
    bb=[e['key'] for e in reference_sequence(project,'entrada','BB')]
    cc=[e['key'] for e in reference_sequence(project,'entrada','CC')]
    assert 'abutment.left_wing' in bb and 'abutment.right_wing' not in bb
    assert 'abutment.right_wing' in cc and 'abutment.left_wing' not in cc


def test_reference_sequence_uses_three_only_for_the_skewed_footing_plan():
    project = _project()
    project['estribos']['orientacion_dado_estribo_entrada'] = 'romboide'
    project['parametros_generales'] = {'angulo_esviaje_puente': -12}
    assert reference_sequence(project, 'entrada', 'EE') == [
        {'key': 'abutment.footing', 'label': 'Zapata', 'reference_mode': 'parallelogram'}]
    assert all(item['reference_mode'] == 'rectangle' for item in reference_sequence(project, 'entrada', 'FR'))
    geometry, _, _ = domain(defaults())
    assert reference_sequence(project, 'entrada', 'EE', geometry=geometry)[0]['reference_mode'] == 'rectangle'
    project['estribos']['orientacion_dado_estribo_entrada'] = 'rectangular'
    project['estribos']['tipo_estribo_entrada'] = 'transparente'
    assert reference_sequence(project, 'entrada', 'EE')[0]['reference_mode'] == 'rectangle'


def test_solid_abutment_uses_effective_skew_not_inactive_orientation_option():
    project = _project()
    project['estribos']['orientacion_dado_estribo_entrada'] = 'rectangular_rotado'
    project['parametros_generales'] = {'angulo_esviaje_puente': -12}
    assert reference_sequence(project, 'entrada', 'EE')[0]['reference_mode'] == 'parallelogram'
    project['parametros_generales']['angulo_esviaje_puente'] = 0
    assert reference_sequence(project, 'entrada', 'EE')[0]['reference_mode'] == 'rectangle'


@pytest.fixture
def service(tmp_path):
    value = Services(tmp_path)
    try:
        yield value
    finally:
        value.jobs.close()


def _project(*, pile=False):
    return {
        "estribos": {
            "tipo_estribo_entrada": "muro_lleno",
            "incluir_pilotes_dado_estribo_entrada": pile,
        },
    }


def _expected(insunits=6):
    return {
        "status": "ready",
        "instance": "42",
        "active": {
            "path": r"C:\puentes\prueba.dwg",
            "name": "prueba.dwg",
            "insunits": insunits,
        },
    }


def _payload(*, pile=False, insunits=6, drawing_units="auto"):
    return {
        "state": defaults(),
        "abutment": "entrada",
        "view": "FR",
        "selection_mode": "geometry",
        "project": _project(pile=pile),
        "expected": _expected(insunits),
        "drawing_units": drawing_units,
    }


def _references_text(keys, *, insunits=6, footing_width=11.596, footing_height=1.5,
                     selection="OK", error=None):
    lines = [
        "SINCAL_SELECTED_MOLDAJE_V1",
        f"META|INSUNITS|{insunits}",
        f"META|SELECTION|{selection}",
        "META|ELEMENT|abutment",
        "META|INSTANCE|entrada",
        "META|VIEW|FR",
        f"META|EXPECTED|{len(keys)}",
        f"META|ELEMENTS|{';'.join(keys)}",
    ]
    if error is not None:
        lines.append(f"META|ERROR|{error}")
    if selection == "OK":
        for index, key in enumerate(keys):
            if key == "abutment.footing":
                first = (0.0, footing_height, 0.0)
                opposite = (footing_width, 0.0, 0.0)
            else:
                offset = float(index * 20)
                first = (offset, 3.0, 0.0)
                opposite = (offset + 2.0, 0.0, 0.0)
            encode = lambda point: ";".join(str(value) for value in point)
            lines.append(f"RECTANGLE|{key}|{encode(first)}|{encode(opposite)}")
    return "\n".join(lines) + "\n"


def _job(character="a"):
    job = Mock(id=character * 32)
    job.cancelled.is_set.return_value = False
    return job


def _cad_collector(service, job, reference_text):
    calls = []

    def cad(_job, expected, command, *args, **kwargs):
        operation = service.runtime / job.id / "operation.lsp"
        calls.append({
            "expected": expected,
            "command": command,
            "args": args,
            "kwargs": kwargs,
            "source": operation.read_text(encoding="utf-8"),
        })
        if len(calls) == 1:
            (service.runtime / job.id / "references.txt").write_text(
                reference_text,
                encoding="utf-8",
            )
            return {"message": "Referencias recibidas"}
        return {"message": "Armadura insertada"}

    return calls, cad


def test_fr_flow_collects_references_without_layers_or_handles_and_generates_only_footing(service):
    job = _job("a")
    calls, fake_cad = _cad_collector(
        service,
        job,
        _references_text(FR_WITHOUT_PILE),
    )

    with patch.object(service, "cad", side_effect=fake_cad), \
         patch("sincal.runtime.ruta_recurso", return_value="master.dwg"), \
         patch("sincal.cad.zapata_views.build_zapata_lisp", wraps=real_build_zapata_lisp) as build:
        result = service.rebar(job, _payload())

    assert len(calls) == 2
    collector = calls[0]
    assert "c:SINCAL-SELECCIONAR-MOLDAJE" in collector["command"]
    assert "getpoint" in collector["source"] and "getcorner" in collector["source"]
    assert "ssget" not in collector["source"].lower()
    assert "modelspace" not in collector["source"].lower()
    assert "handle" not in collector["source"].lower()
    assert "FR_ZAP" not in collector["source"]
    assert "META|ELEMENTS|" + ";".join(FR_WITHOUT_PILE) in collector["source"]
    assert collector["kwargs"] == {"reference_mode": True, "focus": True}

    assert "c:SINCAL-ZAPATA-GENERAR" in calls[1]["command"]
    assert calls[1]["kwargs"] == {"reference_mode": True, "completion": "live-v1"}
    candidate = build.call_args.args[1]
    assert candidate.layer == "" and candidate.handle == ""
    assert [value for point in candidate.vertices for value in point] == pytest.approx(
        [0, 0, 11.596, 0, 11.596, 1.5, 0, 1.5],
    )
    assert build.call_args.kwargs["drawing_units_per_m"] == 1.0

    references = result["references"]
    assert result["selection"] == "ok"
    assert result["references_count"] == 3
    assert references["generated"] == ["abutment.footing"]
    assert references["pending"] == ["abutment.front_wall", "abutment.back_wall"]
    assert list(references["rectangles"]) == FR_WITHOUT_PILE


def test_optional_pile_is_collected_second_and_explicit_mm_scales_generation_with_insunits_6(service):
    job = _job("b")
    text = _references_text(
        FR_WITH_PILE,
        insunits=6,
        footing_width=11596,
        footing_height=1500,
    )
    calls, fake_cad = _cad_collector(service, job, text)

    with patch.object(service, "cad", side_effect=fake_cad), \
         patch("sincal.runtime.ruta_recurso", return_value="master.dwg"), \
         patch("sincal.cad.zapata_views.build_zapata_lisp", wraps=real_build_zapata_lisp) as build:
        result = service.rebar(job, _payload(pile=True, drawing_units="mm"))

    assert len(calls) == 2
    assert "META|ELEMENTS|" + ";".join(FR_WITH_PILE) in calls[0]["source"]
    assert list(result["references"]["rectangles"]) == FR_WITH_PILE
    assert result["references"]["drawing_units_per_m"] == 1000.0
    assert result["references"]["generated"] == ["abutment.footing"]
    assert result["references"]["pending"] == [
        "abutment.pile",
        "abutment.front_wall",
        "abutment.back_wall",
    ]
    assert result["references"]["rectangles"]["abutment.footing"][1][0] == 11596.0
    candidate = build.call_args.args[1]
    assert [value for point in candidate.vertices for value in point] == pytest.approx(
        [0, 0, 11.596, 0, 11.596, 1.5, 0, 1.5],
    )
    assert build.call_args.kwargs["drawing_units_per_m"] == 1000.0


def test_cancelled_reference_sequence_does_not_send_generation(service):
    job = _job("c")
    text = _references_text(
        FR_WITHOUT_PILE,
        selection="CANCELLED",
        error="Cancelado en abutment.footing.",
    )
    calls, fake_cad = _cad_collector(service, job, text)

    with patch.object(service, "cad", side_effect=fake_cad), \
         patch("sincal.runtime.ruta_recurso", return_value="master.dwg"), \
         patch("sincal.cad.zapata_views.build_zapata_lisp", wraps=real_build_zapata_lisp) as build:
        result = service.rebar(job, _payload())

    assert result == {
        "selection": "cancelled",
        "message": "Selección cancelada. No se insertaron armaduras.",
    }
    assert len(calls) == 1
    build.assert_not_called()


def test_declared_metres_with_millimetre_sized_rectangle_blocks_before_insertion(service):
    job = _job("d")
    text = _references_text(
        FR_WITHOUT_PILE,
        insunits=6,
        footing_width=11596,
        footing_height=1500,
    )
    calls, fake_cad = _cad_collector(service, job, text)

    with patch.object(service, "cad", side_effect=fake_cad), \
         patch("sincal.runtime.ruta_recurso", return_value="master.dwg"), \
         patch("sincal.cad.zapata_views.build_zapata_lisp", wraps=real_build_zapata_lisp) as build, \
         pytest.raises(ValueError, match="rectángulo mide.*Revisa la unidad"):
        service.rebar(job, _payload())

    assert len(calls) == 1
    build.assert_not_called()


def test_change_in_declared_units_after_confirmation_blocks_before_insertion(service):
    job = _job("e")
    text = _references_text(FR_WITHOUT_PILE, insunits=4)
    calls, fake_cad = _cad_collector(service, job, text)

    with patch.object(service, "cad", side_effect=fake_cad), \
         patch("sincal.runtime.ruta_recurso", return_value="master.dwg"), \
         patch("sincal.cad.zapata_views.build_zapata_lisp", wraps=real_build_zapata_lisp) as build, \
         pytest.raises(ValueError, match="Cambió la unidad declarada"):
        service.rebar(job, _payload(insunits=6))

    assert len(calls) == 1
    build.assert_not_called()


def test_reference_mode_worker_never_reads_modelspace_or_handles(tmp_path):
    class GuardDocument:
        FullName = r"C:\puentes\prueba.dwg"
        Name = "prueba.dwg"

        def __init__(self):
            self.sent = []

        @property
        def ModelSpace(self):
            raise AssertionError("reference_mode no debe leer ModelSpace")

        def HandleToObject(self, _handle):
            raise AssertionError("reference_mode no debe resolver handles")

        def GetVariable(self, name):
            return {"CMDACTIVE": 0, "TILEMODE": 1, "INSUNITS": 6}[name]

        def SendCommand(self, command):
            self.sent.append(command)

    document = GuardDocument()
    application = Mock(HWND=42)
    request = {
        "expected": _expected(6),
        "command": "(princ)",
        "reference_mode": True,
        "marker": str(tmp_path / "done.txt"),
        "token": "token",
    }

    with patch.object(cad_worker, "active_application", return_value=application), \
         patch.object(cad_worker, "active_document", return_value=document), \
         patch.object(cad_worker, "read_when_ready", side_effect=lambda function: function()), \
         patch.object(cad_worker, "read_completion", return_value={"message": "ok"}):
        result = cad_worker.execute(request)

    assert result == {"message": "ok"}
    assert len(document.sent) == 1
    assert "(princ)" in document.sent[0]


@pytest.mark.parametrize('factor,units', [(1, 'm'), (100, 'cm'), (1000, 'mm')])
@pytest.mark.parametrize('skew', [-12, 12])
def test_ee_three_corner_flow_validates_and_inserts_skewed_plan(service, factor, units, skew):
    import math
    payload = _payload(drawing_units=units)
    payload['view'] = 'EE'
    payload['state']['geometry']['esviaje_grados'] = skew
    payload['project']['estribos']['orientacion_dado_estribo_entrada'] = 'romboide'
    payload['project']['parametros_generales'] = {'angulo_esviaje_puente': skew}
    delta = 7.5 * math.tan(math.radians(skew))
    vertices = [(100 + delta, 207.5), (111.596 + delta, 207.5), (111.596, 200)]
    encoded = [';'.join(str(value * factor) for value in (*point, 0)) for point in vertices]
    text = _references_text(['abutment.footing']).split('RECTANGLE|')[0].replace('META|VIEW|FR', 'META|VIEW|EE')
    text += 'PARALLELOGRAM|abutment.footing|' + '|'.join(encoded) + '\n'
    job = _job('f')
    calls, fake_cad = _cad_collector(service, job, text)
    with patch.object(service, 'cad', side_effect=fake_cad), \
         patch('sincal.runtime.ruta_recurso', return_value='master.dwg'), \
         patch('sincal.cad.zapata_views.build_zapata_lisp', wraps=real_build_zapata_lisp) as build:
        result = service.rebar(job, payload)
    assert len(calls) == 2
    assert 'SUPERIOR DERECHA' in calls[0]['source']
    assert 'ssget' not in calls[0]['source'].lower()
    assert build.call_args.args[0] == 'FF'  # existing calculation identity
    candidate = build.call_args.args[1]
    assert [c for p in candidate.vertices for c in p] == pytest.approx(
        [100, 200, 111.596, 200, 111.596 + delta, 207.5, 100 + delta, 207.5])
    assert build.call_args.kwargs['drawing_units_per_m'] == factor
    assert result['references']['view'] == 'EE'
    assert result['references']['reference_modes'] == {'abutment.footing': 'parallelogram'}


@pytest.mark.parametrize('orientation', ['rectangular', 'rectangular_rotado'])
def test_ee_rectangular_plan_still_uses_two_corners(service, orientation):
    payload = _payload()
    payload['project']['estribos']['orientacion_dado_estribo_entrada'] = orientation
    payload['view'] = 'EE'
    text = _references_text(['abutment.footing'], footing_height=7.5).replace('META|VIEW|FR', 'META|VIEW|EE')
    job = _job('g')
    calls, fake_cad = _cad_collector(service, job, text)
    with patch.object(service, 'cad', side_effect=fake_cad), \
         patch('sincal.runtime.ruta_recurso', return_value='master.dwg'):
        result = service.rebar(job, payload)
    assert len(calls) == 2
    assert result['references']['reference_modes'] == {'abutment.footing': 'rectangle'}


def test_ee_rotated_rectangle_blocks_before_any_cad_order(service):
    payload = _payload()
    payload['view'] = 'EE'
    payload['state']['geometry']['esviaje_grados'] = 12
    payload['project']['estribos']['orientacion_dado_estribo_entrada'] = 'rectangular_rotado'
    payload['project']['estribos']['tipo_estribo_entrada'] = 'transparente'
    with patch.object(service, 'cad') as cad, \
         patch('sincal.runtime.ruta_recurso', return_value='master.dwg'), \
         pytest.raises(ValueError, match='girada'):
        service.rebar(_job('i'), payload)
    cad.assert_not_called()


def test_ee_skewed_plan_cannot_accept_stale_rectangle_result(service):
    payload = _payload()
    payload['view'] = 'EE'
    payload['state']['geometry']['esviaje_grados'] = -12
    payload['project']['estribos']['orientacion_dado_estribo_entrada'] = 'romboide'
    text = _references_text(['abutment.footing'], footing_height=7.5).replace('META|VIEW|FR', 'META|VIEW|EE')
    job = _job('h')
    calls, fake_cad = _cad_collector(service, job, text)
    with patch.object(service, 'cad', side_effect=fake_cad), \
         patch('sincal.runtime.ruta_recurso', return_value='master.dwg'), \
         pytest.raises(ValueError, match='cantidad de esquinas'):
        service.rebar(job, payload)
    assert len(calls) == 1
