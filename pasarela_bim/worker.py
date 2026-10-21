"""Entrada del trabajador: importar desde una macro de FreeCAD o su Python."""

import argparse
import json
import traceback
from pathlib import Path


def ejecutar(ruta_entrada, carpeta_salida, con_vistas=True):
    """Lee JSON y escribe resultado.json tanto si concluye como si falla."""
    salida = Path(carpeta_salida).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    try:
        from .freecad_backend import generar
        modelo = json.loads(Path(ruta_entrada).read_text(encoding="utf-8-sig"))
        resultado = generar(modelo, salida, con_vistas=con_vistas)
    except Exception as exc:
        resultado = {"valido":False,"error":str(exc),"traza":traceback.format_exc()}
    (salida/"resultado.json").write_text(json.dumps(resultado,ensure_ascii=False,indent=2),encoding="utf-8")
    return resultado


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generar modelo conceptual en FreeCAD")
    parser.add_argument("--entrada",required=True)
    parser.add_argument("--salida",required=True)
    parser.add_argument("--sin-vistas",action="store_true")
    args = parser.parse_args(argv)
    resultado = ejecutar(args.entrada,args.salida,con_vistas=not args.sin_vistas)
    print(json.dumps(resultado,ensure_ascii=False))
    return 0 if resultado["valido"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
