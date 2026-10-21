"""Ejecuta FreeCAD en un proceso propio, con una instantánea de la topología."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from .runtime import carpeta_generados, raiz_codigo_motor, entorno_externo, bibliotecas_sistema


def localizar_freecad():
    configurado = os.environ.get("PASARELA_FREECAD")
    candidatos = [Path(configurado)] if configurado else []
    for nombre in ("FreeCAD", "freecad", "FreeCAD.exe"):
        encontrado = shutil.which(nombre)
        if encontrado:
            candidatos.append(Path(encontrado))
    if os.name == "nt":
        programas = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        candidatos += sorted(programas.glob("FreeCAD*/bin/FreeCAD.exe"), reverse=True)
    return next((p.resolve() for p in candidatos if p.is_file()), None)


def nueva_salida():
    return carpeta_generados() / (datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])


def generar_aislado(modelo, salida=None, timeout=300):
    from .topologia import validar
    from .proyecto import convertir_a_interno, convertir_a_portable

    validacion = validar(modelo)
    if not validacion["valido"]:
        raise ValueError("La topología contiene errores: " + "; ".join(e["mensaje"] for e in validacion["errores"]))
    ejecutable = localizar_freecad()
    if not ejecutable:
        raise RuntimeError("No se encontró FreeCAD. Configura PASARELA_FREECAD con la ruta de su ejecutable.")
    codigo_motor = raiz_codigo_motor()
    destino = Path(salida).resolve() if salida else nueva_salida()
    # Cada ejecución es independiente: nunca sustituir un modelo generado previamente.
    destino.mkdir(parents=True, exist_ok=False)
    (destino / "topologia.json").write_text(
        json.dumps(convertir_a_portable(modelo), ensure_ascii=False, indent=2), encoding="utf-8")
    # La entrada privada conserva la procedencia legacy, mientras que el archivo
    # intercambiable siempre usa metros y se vuelve a validar al importarlo.
    entrada = destino / "entrada_motor.json"
    entrada.write_text(json.dumps(convertir_a_interno(modelo), ensure_ascii=False, indent=2), encoding="utf-8")
    resultado = destino / "resultado_proceso.json"
    macro = destino / "generar.FCMacro"
    macro.write_text(
        "import sys, json, traceback\n"
        "from pathlib import Path\n"
        "from PySide6 import QtCore, QtWidgets\n"
        f"sys.path.insert(0, {str(codigo_motor)!r})\n"
        "def construir_pasarela():\n"
        "    try:\n"
        "        import FreeCAD as App\n"
        "        if App.listDocuments():\n"
        "            raise RuntimeError('El proceso de generación debe iniciar sin documentos abiertos')\n"
        "        App.ParamGet('User parameter:BaseApp/Preferences/Document').SetBool('AutoSaveEnabled', False)\n"
        "        from pasarela_bim.worker import ejecutar\n"
        f"        datos = ejecutar({str(entrada)!r}, {str(destino)!r}, con_vistas=True)\n"
        "        if not datos.get('valido', False):\n"
        "            raise RuntimeError(datos.get('error', 'FreeCAD no confirmó la validez del modelo'))\n"
        "        respuesta = {'estado': 'completado', 'resultado': datos}\n"
        "    except Exception as exc:\n"
        "        respuesta = {'estado': 'error', 'mensaje': str(exc), 'detalle': traceback.format_exc()}\n"
        f"    Path({str(resultado)!r}).write_text(json.dumps(respuesta, ensure_ascii=False, indent=2, default=str), encoding='utf-8')\n"
        "    QtCore.QTimer.singleShot(250, QtWidgets.QApplication.instance().quit)\n"
        "QtCore.QTimer.singleShot(500, construir_pasarela)\n",
        encoding="utf-8",
    )
    entorno = entorno_externo()
    entorno["QT_QPA_PLATFORM"] = "offscreen"
    if os.name == "nt":
        entorno["QT_QPA_FONTDIR"] = str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts")
    entorno["PYTHONNOUSERSITE"] = "1"
    entorno["PYTHONDONTWRITEBYTECODE"] = "1"
    opciones = {}
    if os.name == "nt":
        opciones["creationflags"] = subprocess.CREATE_NO_WINDOW
    with (destino / "freecad.log").open("wb") as registro:
        with bibliotecas_sistema():
            proceso = subprocess.Popen([str(ejecutable), "-u", str(destino / "user.cfg"),
                                        "-s", str(destino / "system.cfg"), str(macro)], cwd=str(destino), env=entorno,
                                       stdout=registro, stderr=subprocess.STDOUT, **opciones)
        try:
            codigo = proceso.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            proceso.kill()  # Sólo el proceso creado para este trabajo.
            proceso.wait(timeout=15)
            raise RuntimeError("FreeCAD excedió el tiempo de generación. Se conservó el registro del trabajo.") from exc
    if not resultado.is_file():
        raise RuntimeError(f"FreeCAD terminó sin confirmar el modelo (código {codigo}). Registro: {destino / 'freecad.log'}")
    respuesta = json.loads(resultado.read_text(encoding="utf-8"))
    if respuesta["estado"] != "completado":
        raise RuntimeError(respuesta.get("mensaje", "FreeCAD no pudo generar el modelo"))
    modelos = list(destino.glob("*.FCStd"))
    if not modelos or any(p.stat().st_size == 0 for p in modelos):
        raise RuntimeError("La generación no produjo un archivo FreeCAD válido.")
    respuesta["carpeta"] = str(destino)
    respuesta["archivos"] = [p.name for p in sorted(destino.iterdir())
                              if p.is_file() and p.suffix.lower() in {".fcstd", ".svg", ".png", ".csv", ".json"}
                              and p.name not in {"resultado_proceso.json", "entrada_motor.json"}]
    return respuesta
