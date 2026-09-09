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


def construir_comando_cad_con_marcador(comando, ruta_marcador, token):
    """Encadena confirmaciones de recepción y término alrededor del comando.

    ``SendCommand`` puede devolver el control antes de que AutoCAD haya
    terminado, e incluso lanzar una excepción COM después de haber aceptado la
    cadena. El primer valor evita reenviar el comando en ese caso; el segundo
    permite esperar sin cambiar de dibujo mientras aún está activo.
    """
    comando = normalizar_comando_cad_autonomo(comando)
    ruta_lisp = str(ruta_marcador).replace("\\", "/").replace('"', '\\"')
    token_lisp = str(token).replace('"', '\\"')

    def escribir_marcador(valor):
        return (
            f'(progn (setq SINCAL_LIVE_FILE (open "{ruta_lisp}" "w")) '
            f'(if SINCAL_LIVE_FILE (progn (write-line "{valor}" '
            'SINCAL_LIVE_FILE) (close SINCAL_LIVE_FILE))) (princ))'
        )

    recibido = escribir_marcador(f"RECIBIDO:{token_lisp}")
    completado = escribir_marcador(token_lisp)
    return f"{recibido}\n{comando}\n{completado}\n"
