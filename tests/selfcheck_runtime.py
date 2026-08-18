import os
import sys
import json
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sincal_runtime import VERSION_ACTUAL, ruta_recurso, ruta_runtime, asegurar_directorios
from sincal_resource_sync import git_blob_sha
from modulos.tab_ubicacion import _leer_kml_desde_kmz, _parsear_kml_puntos


def main() -> int:
    asegurar_directorios()
    with open(ruta_recurso("version.json"), encoding="utf-8") as archivo_version:
        version_esperada = json.load(archivo_version)["version"]
    assert VERSION_ACTUAL == version_esperada, f"Versión inesperada: {VERSION_ACTUAL}"
    requeridos = [
        ruta_recurso("version.json"),
        ruta_recurso("tutoriales.json"),
        ruta_recurso("scripts", "AUDIT.ps1"),
        ruta_recurso("scripts", "AUDIT.scr"),
        ruta_recurso("mapas", "mapas_calibrados.json"),
        ruta_recurso("lisps", "SINCAL.lsp"),
        ruta_recurso("masters", "FORMATOS ANOTATIVOS ACAD_2025.dwg"),
    ]
    faltantes = [ruta for ruta in requeridos if not os.path.exists(ruta)]
    assert not faltantes, f"Faltan recursos: {faltantes}"
    with open(ruta_recurso("masters", "FORMATOS ANOTATIVOS ACAD_2025.dwg"), "rb") as master:
        cabecera_master = master.read(6)
    assert len(cabecera_master) == 6 and cabecera_master.startswith(b"AC"), "Master DWG inválido"
    assert git_blob_sha(b"test") == "30d74d258442c7c65512eafab474568dd706c430"
    runtime = ruta_runtime()
    assert os.path.isdir(runtime), f"Runtime no disponible: {runtime}"
    with open(ruta_recurso("mapas", "mapas_calibrados.json"), encoding="utf-8") as archivo:
        mapas = json.load(archivo)
    validos = []
    for nombre, cfg in mapas.items():
        try:
            lat1, lon1 = cfg["pt1_geo"]
            x1, y1 = cfg["pt1_pixel"]
            lat2, lon2 = cfg["pt2_geo"]
            x2, y2 = cfg["pt2_pixel"]
        except Exception:
            continue
        if all(delta != 0 for delta in (lat2 - lat1, lon2 - lon1, x2 - x1, y2 - y1)):
            validos.append(nombre)
    assert "Región de Valparaíso" in validos, "Falta el único mapa calibrado esperado"
    assert len(validos) >= 1, "No hay mapas calibrados válidos"

    with open(ruta_recurso("SINCAL_Installer.iss"), encoding="utf-8") as archivo:
        instalador = archivo.read()
    assert instalador.count("external download extractarchive") == 2, "Faltan paquetes del instalador web"
    assert 'Hash: "{#AppPayloadHash}"' in instalador, "Falta validar el paquete de aplicación"
    assert 'Hash: "{#PluginPayloadHash}"' in instalador, "Falta validar el paquete del plugin"

    with tempfile.TemporaryDirectory() as tmp:
        kmz_ok = os.path.join(tmp, "ok.kmz")
        with zipfile.ZipFile(kmz_ok, "w") as zf:
            zf.writestr("doc.kml", """<?xml version='1.0' encoding='UTF-8'?>
<kml><Document>
<Placemark><name>Puente</name><Point><coordinates>-71.0,-32.0,0</coordinates></Point></Placemark>
<Placemark><name>Puente</name><Point><coordinates>-70.5,-32.5,0</coordinates></Point></Placemark>
</Document></kml>""")
        kml_data, kml_name = _leer_kml_desde_kmz(kmz_ok)
        estructuras, ignorados = _parsear_kml_puntos(kml_data)
        assert kml_name.lower().endswith("doc.kml")
        assert "Puente" in estructuras and "Puente (2)" in estructuras
        assert ignorados == 0

        kmz_bad = os.path.join(tmp, "bad.kmz")
        with zipfile.ZipFile(kmz_bad, "w") as zf:
            zf.writestr("a.kml", "<kml></kml>")
            zf.writestr("b.kml", "<kml></kml>")
        try:
            _leer_kml_desde_kmz(kmz_bad)
            raise AssertionError("Se esperaba error por múltiples KML ambiguos")
        except ValueError:
            pass

        kmz_invalid = os.path.join(tmp, "invalid.kmz")
        with zipfile.ZipFile(kmz_invalid, "w") as zf:
            zf.writestr("doc.kml", """<kml><Document>
<Placemark><name>X</name><Point><coordinates>-190,-95,0</coordinates></Point></Placemark>
<Placemark><name>Y</name><Point><coordinates>-71,-32,0</coordinates></Point></Placemark>
</Document></kml>""")
        data_invalid, _ = _leer_kml_desde_kmz(kmz_invalid)
        estructuras_invalid, ignorados_invalid = _parsear_kml_puntos(data_invalid)
        assert "Y" in estructuras_invalid
        assert ignorados_invalid == 1

    print("OK: runtime local, recursos y configuración web válidos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
