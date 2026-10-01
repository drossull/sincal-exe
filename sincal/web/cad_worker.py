"""Isolated COM execution. Never retry a potentially accepted SendCommand."""
import json
from pathlib import Path
import sys
import time


def execute_all(request):
    app = active_application()
    expected = request['expected']
    targets = expected.get('documents', [])
    if not targets or len(targets) > 100:
        raise ValueError('La selección debe contener entre 1 y 100 dibujos.')
    if str(app.HWND) != expected['instance'] or str(app.ActiveDocument.FullName) != expected['active']['path'] or str(app.ActiveDocument.Name) != expected['active']['name']:
        raise ValueError('Cambió la instancia o el dibujo activo antes de iniciar el recorrido.')
    documents = app.Documents
    opened = {(str(documents.Item(i).Name), str(documents.Item(i).FullName)) for i in range(documents.Count)}
    if opened != {(item['name'], item['path']) for item in targets}:
        raise ValueError('Cambió la lista de dibujos abiertos. Confirma nuevamente los destinos.')
    completed = []
    for index, target in enumerate(targets):
        if int(app.ActiveDocument.GetVariable('CMDACTIVE')):
            raise ValueError('Hay un comando activo; se detuvo el recorrido sin enviar otra orden.')
        documents = app.Documents
        doc = next((documents.Item(i) for i in range(documents.Count)
                    if str(documents.Item(i).Name) == target['name'] and str(documents.Item(i).FullName) == target['path']), None)
        if doc is None:
            raise ValueError('Se cerró o cambió uno de los dibujos pendientes.')
        doc.Activate()
        child = dict(request, expected={**expected, 'active':target}, scope='active',
                     marker=str(Path(request['marker']).with_name(f'done-{index}.txt')), token=request['token']+str(index))
        execute(child)
        completed.append(target['name'])
        progress = Path(request['marker']).with_name('progress.json')
        temporary = progress.with_suffix('.tmp')
        temporary.write_text(json.dumps({'message':f"{index+1}/{len(targets)}: {target['name']} devolvió el control",
                                         'progress':(index+1)*100/len(targets)}), encoding='utf-8')
        temporary.replace(progress)
    return {'documents': completed, 'message':f'{len(completed)} dibujos devolvieron el control. Revisa el resultado y la línea de comandos; la orden elegida puede guardar por sí misma.'}


def active_application():
    import win32com.client
    processes = list(win32com.client.GetObject('winmgmts:').ExecQuery(
        "SELECT Name FROM Win32_Process WHERE Name='acad.exe' OR Name='zwcad.exe'"))
    if len(processes) != 1:
        raise ValueError('Debe existir una sola instancia AutoCAD/ZWCAD abierta.')
    family = 'ZWCAD' if str(processes[0].Name).lower() == 'zwcad.exe' else 'AutoCAD'
    for identifier in [family + '.Application'] + [f'{family}.Application.{v}' for v in range(15, 36)]:
        try:
            return win32com.client.GetActiveObject(identifier)
        except Exception:
            pass
    raise ValueError('COM no está disponible.')


def execute(request):
    app = active_application()
    doc = app.ActiveDocument
    expected = request['expected']
    if (str(app.HWND) != expected['instance'] or str(doc.FullName) != expected['active']['path']
            or str(doc.Name) != expected['active']['name']):
        raise ValueError('Cambió el dibujo o la instancia activa. Comprueba la conexión otra vez.')
    if int(doc.GetVariable('CMDACTIVE')):
        raise ValueError('CAD está ocupado. Termina el comando actual primero.')
    if request.get('metres') and (int(doc.GetVariable('INSUNITS')) != 6 or int(doc.GetVariable('TILEMODE')) != 1):
        raise ValueError('Abre Model en un dibujo con INSUNITS = 6 (metros).')
    if request.get('candidate'):
        candidate = request['candidate']
        entity = doc.HandleToObject(candidate['handle'])
        coords = list(entity.Coordinates)
        vertices = candidate['vertices']
        if (str(entity.Layer) != candidate['layer'] or not entity.Closed or len(coords) != len(vertices) * 2
                or any(abs(coords[i * 2 + j] - point[j]) > 1e-7 for i, point in enumerate(vertices) for j in (0, 1))
                or any(abs(float(entity.GetBulge(i))) > 1e-7 for i in range(len(vertices)))):
            raise ValueError('El moldaje cambió. Detecta y confirma nuevamente.')
    marker = Path(request['marker'])
    token = request['token']
    # This expression only comes from our Python generators, never browser input.
    suffix = '(progn (setq f (open "' + str(marker).replace('\\', '/') + '" "w")) (if f (progn (write-line "' + token + '" f) (close f))) (princ))\n'
    try:
        doc.SendCommand(request['command'] + suffix)
    except Exception as error:
        raise RuntimeError('CAD puede haber recibido la orden. No se reenvió. Revisa el dibujo antes de repetir.') from error
    deadline = time.monotonic() + request.get('timeout', 180)
    while time.monotonic() < deadline:
        if marker.exists() and marker.read_text(encoding='utf-8').strip() == token:
            return {'message': 'CAD devolvió el control. Revisa la línea de comandos y el resultado. SINCAL no añade un guardado; la orden elegida puede guardar por sí misma.'}
        time.sleep(.25)
    raise TimeoutError('CAD no confirmó el fin. Puede estar esperando un punto/opción o haber fallado. No se reenviará ni se cerrará CAD.')


def convert(request):
    import win32com.client
    # Own only this new instance; never use or close an existing one.
    app = win32com.client.DispatchEx(request['engine'] + '.Application')
    try:
        app.Visible = False
        destination = Path(request['destination'])
        if destination.exists():
            raise ValueError('El DWG de destino existe; no se sobrescribirá.')
        doc = app.Documents.Open(request['source'])
        try:
            doc.SaveAs(str(destination), 64)
        finally:
            doc.Close(False)
        if not destination.exists() or not destination.stat().st_size:
            raise ValueError('No se generó un DWG válido.')
        return {'message': 'DWG generado', 'name': destination.name}
    finally:
        app.Quit()


def main():
    import pythoncom
    pythoncom.CoInitialize()
    try:
        request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        result = (convert(request) if request.get('operation') == 'convert' else
                  execute_all(request) if request.get('scope') == 'all' else execute(request))
        response = {'ok': True, 'result': result}
    except Exception as error:
        response = {'ok': False, 'error': str(error)}
    finally:
        pythoncom.CoUninitialize()
    Path(sys.argv[1]).with_name('result.json').write_text(json.dumps(response, ensure_ascii=True), encoding='utf-8')
    if sys.stdout is not None:
        print(json.dumps(response, ensure_ascii=True))


if __name__ == '__main__':
    main()
