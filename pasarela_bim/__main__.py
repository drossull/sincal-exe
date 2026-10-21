"""Arranque de la aplicación local o generación por consola."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generador topológico de pasarelas")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--sin-navegador", action="store_true")
    parser.add_argument("--launch-info", type=Path, help="Escribir URL y PID del servidor al quedar disponible")
    parser.add_argument("--data-dir", type=Path, help="Carpeta escribible de datos del módulo (reemplaza PASARELA_DATA_DIR)")
    accion = parser.add_mutually_exclusive_group()
    accion.add_argument("--validar", type=Path, help="Validar un archivo de topología")
    accion.add_argument("--generar", type=Path, help="Generar un archivo de topología en FreeCAD")
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("El puerto debe estar entre 0 y 65535; 0 selecciona un puerto disponible")
    if args.data_dir:
        os.environ["PASARELA_DATA_DIR"] = str(args.data_dir.expanduser().resolve())
    if args.validar or args.generar:
        from .topologia import validar

        modelo = json.loads((args.validar or args.generar).read_text(encoding="utf-8-sig"))
        resultado = validar(modelo)
        if args.generar and resultado["valido"]:
            from .ejecucion import generar_aislado

            resultado = generar_aislado(modelo, args.salida)
        if sys.stdout is not None:
            print(json.dumps(resultado, ensure_ascii=True, indent=2))
        return 0 if resultado.get("valido", resultado.get("estado") == "completado") else 1
    from .servidor import servir

    servir(args.port, abrir_navegador=not args.sin_navegador, launch_info=args.launch_info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
