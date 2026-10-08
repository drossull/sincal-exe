"""Bounded retries for COM reads only. Never wrap SendCommand in a retry."""
import time


def read_when_ready(read, timeout=8, interval=.2):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return read()
        except Exception as error:
            # pywin32 may hide a rejected property read as AttributeError.
            values = [getattr(error, 'hresult', 0)]
            info = getattr(error, 'excepinfo', None)
            if info and len(info) > 5:
                values.append(info[5])
            transient = isinstance(error, AttributeError) or any(
                isinstance(v, int) and (v & 0xffffffff) in (0x80010001, 0x8001010A) for v in values)
            if not transient:
                raise
            if time.monotonic() >= deadline:
                raise RuntimeError('AutoCAD no permitió consultar el dibujo activo. '
                                   'Termina los comandos o diálogos abiertos y comprueba la conexión. '
                                   'No se envió otra orden.') from error
            time.sleep(interval)


def active_document(app):
    return read_when_ready(lambda: app.ActiveDocument)


def wait_for_document(app, target, timeout=8):
    deadline = time.monotonic() + timeout
    while True:
        doc = active_document(app)
        identity = read_when_ready(lambda: (str(doc.Name), str(doc.FullName)))
        if identity == (target['name'], target['path']):
            return doc
        if time.monotonic() >= deadline:
            raise ValueError('CAD no activó el dibujo confirmado. Se detuvo el lote sin enviar otra orden.')
        time.sleep(.2)
