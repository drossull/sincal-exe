"""Read-only CAD probe, isolated so a blocked COM call cannot freeze the UI."""
import json
from .cad_readiness import read_when_ready


def inspect_application(app):
    documents = app.Documents
    opened = []
    for index in range(documents.Count):
        doc = documents.Item(index)
        opened.append({"name": str(doc.Name), "path": str(doc.FullName)})
    if not opened:
        return {"status": "no_document", "message": "CAD está abierto sin dibujos.", "documents": []}
    active = app.ActiveDocument
    busy = int(active.GetVariable("CMDACTIVE")) != 0
    return {"status": "busy" if busy else "ready", "product": str(app.Name),
            "version": str(app.Version), "documents": opened,
            "active": {"name": str(active.Name), "path": str(active.FullName),
                       "insunits": int(active.GetVariable("INSUNITS")),
                       "layout": str(active.GetVariable("CTAB"))},
            "message": "CAD tiene un comando activo." if busy else "Conexión disponible. No se modificó ningún dibujo."}


def probe():
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    app = wmi = processes = None
    try:
        # Do not create a CAD instance. Multiple running instances are ambiguous.
        wmi = win32com.client.GetObject('winmgmts:')
        processes = list(wmi.ExecQuery("SELECT ProcessId,Name FROM Win32_Process WHERE Name='acad.exe' OR Name='zwcad.exe'"))
        if not processes:
            return {"status": "disconnected", "message": "Abre AutoCAD o ZWCAD y un dibujo para conectar."}
        if len(processes) > 1:
            return {"status": "ambiguous", "message": "Hay varias instancias CAD abiertas. Deja una sola para conectar con seguridad."}
        family = 'ZWCAD' if str(processes[0].Name).lower() == 'zwcad.exe' else 'AutoCAD'
        ids = [family + '.Application'] + [f'{family}.Application.{version}' for version in range(15, 36)]
        for prog_id in ids:
            try:
                app = win32com.client.GetActiveObject(prog_id)
            except Exception:
                continue
            result = read_when_ready(lambda: inspect_application(app))
            result['instance'] = read_when_ready(lambda: str(app.HWND))
            return result
        return {"status": "unavailable", "message": "CAD está abierto pero COM no está accesible. Comprueba que ambas aplicaciones usen el mismo usuario y nivel de permisos."}
    finally:
        # Release COM wrappers while this thread's apartment still exists.
        app = wmi = processes = None
        pythoncom.CoUninitialize()


if __name__ == '__main__':
    try:
        result = probe()
    except Exception:
        result = {"status": "unavailable", "message": "CAD no pudo responder. Puede estar ocupado o tener un diálogo abierto; inténtalo de nuevo."}
    print(json.dumps(result, ensure_ascii=True))
