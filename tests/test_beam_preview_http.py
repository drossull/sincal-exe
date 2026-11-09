"""The beam preview is a local read of project geometry, never a CAD job."""
from copy import deepcopy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from sincal.web import server as web_server


def test_beam_preview_http_and_asset_are_local_only(tmp_path, monkeypatch):
    server = web_server.Server(0, tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("La vista previa no debe consultar CAD ni iniciar trabajos.")

    monkeypatch.setattr(web_server, "connection_status", forbidden)
    monkeypatch.setattr(server.services.jobs, "submit", forbidden)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    project = {
        "parametros_generales": {"angulo_esviaje_puente": -12},
        "elementos_comunes": {"vigas": {"num_vigas": 4, "separacion_vigas": 2600,
                                          "offset_y_vigas": 50}},
        "tableros": [{"nombre_grupo_tablero": "Tablero_05", "tipo_viga_seleccionado": 6,
                      "largo_losa": 35734.19145, "pendiente_longitudinal": -.005}],
    }
    before = deepcopy(project)
    try:
        payload = json.dumps({"project": project, "board_index": 0, "beam_index": 3}).encode()
        request = Request(server.origin + "/api/rebar/beam/preview", data=payload,
                          headers={"X-Sincal-Token": server.token,
                                   "Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            data = json.loads(response.read())
        assert data["valid"] and data["beam_index"] == 3
        assert data["geometry"]["length_projected_m"] == pytest.approx(35.63419145)
        assert data["views"]["plan"]["outline"]
        assert data["views"]["elevation"]["outline"]
        assert project == before
        with urlopen(server.origin + "/rebar_beam.js", timeout=5) as response:
            assert "javascript" in response.headers["Content-Type"]
            assert "style-src 'self'" in response.headers["Content-Security-Policy"]
            assert b"renderBeamPreview" in response.read()
        with pytest.raises(HTTPError) as error:
            urlopen(Request(server.origin + "/api/rebar/beam/preview", data=payload,
                            headers={"Content-Type": "application/json"}), timeout=5)
        assert error.value.code == 401
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
