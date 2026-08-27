"""Validación de órdenes CAD enviadas sin interacción posterior."""

import re


PATRON_COMANDO_CAD = re.compile(r"^[A-Za-z0-9_.-]+$")


def normalizar_comando_cad_autonomo(valor):
    """Acepta sólo el nombre de una orden CAD, nunca respuestas encadenadas."""
    comando = str(valor or "").strip()
    if not comando:
        raise ValueError("Escribe un comando CAD.")
    if len(comando) > 64 or not PATRON_COMANDO_CAD.fullmatch(comando):
        raise ValueError(
            "Escribe únicamente el nombre del comando, sin espacios, parámetros, "
            "saltos de línea ni expresiones LISP."
        )
    return comando
