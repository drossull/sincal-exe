"""Isolated COM execution. Never retry a potentially accepted SendCommand."""
import json
from pathlib import Path
import sys
import time
from .cad_readiness import active_document, read_when_ready, wait_for_document


def ensure_cad_clipboard():
    """Inspect format names only; never consume, replace or persist clipboard data."""
    import win32clipboard
    try:
        win32clipboard.OpenClipboard()
    except Exception as error:
        raise ValueError('No se pudo consultar el portapapeles. Espera un momento y vuelve a intentar P0.') from error
    try:
        format_id = 0
        while True:
            format_id = win32clipboard.EnumClipboardFormats(format_id)
            if not format_id:
                break
            if format_id < 0xc000:
                continue
            name = win32clipboard.GetClipboardFormatName(format_id).lower()
            if name.startswith(('autocad.', 'zwcad.')):
                return
        raise ValueError('P0 requiere objetos copiados desde CAD con COPYCLIP/Ctrl+C. '
                         'El portapapeles no contiene un dibujo CAD; no se envió la orden.')
    finally:
        win32clipboard.CloseClipboard()


def command_with_completion(request):
    """Keep Lisp continuations in the same form, never in getpoint's input queue."""
    from sincal.cad.prospecciones import lisp_string
    marker = lisp_string(str(request['marker']).replace('\\', '/'))
    token = lisp_string(request['token'])
    command = request['command'].strip()
    if request.get('completion') == 'live-v1':
        if not command.startswith('(') or not command.endswith(')'):
            raise ValueError('El comando de catálogo requiere una expresión LISP.')
        return (
            '(progn (setq *SINCAL_LIVE_RESULT* nil) '
            f"(setq SINCAL_LIVE_ERROR (vl-catch-all-apply '(lambda () {command}) nil)) "
            f'(setq SINCAL_LIVE_OUT (open {marker} "w")) '
            '(if SINCAL_LIVE_OUT (progn '
            f'(write-line {token} SINCAL_LIVE_OUT) '
            '(cond ((vl-catch-all-error-p SINCAL_LIVE_ERROR) '
            '(write-line "error" SINCAL_LIVE_OUT) '
            '(write-line (vl-catch-all-error-message SINCAL_LIVE_ERROR) SINCAL_LIVE_OUT)) '
            '(*SINCAL_LIVE_RESULT* '
            '(write-line (if (car *SINCAL_LIVE_RESULT*) "ok" "error") SINCAL_LIVE_OUT) '
            '(write-line (cadr *SINCAL_LIVE_RESULT*) SINCAL_LIVE_OUT)) '
            '(T (write-line "ok" SINCAL_LIVE_OUT) '
            '(write-line "CAD devolvio el control; revisa el resultado en el dibujo." SINCAL_LIVE_OUT))) '
            '(close SINCAL_LIVE_OUT))) (princ))\n')
    if request.get('completion') == 'stratigraphy-v1':
        if not command.startswith('(') or not command.endswith(')'):
            raise ValueError('La confirmación de estratigrafía requiere una expresión LISP.')
        return f'(progn (setq *SINCAL_ESTRAT_COMPLETION* (list {marker} {token})) {command})\n'
    suffix = f'(progn (setq f (open {marker} "w")) (if f (progn (write-line {token} f) (close f))) (princ))'
    if command.startswith('(') and command.endswith(')'):
        return f'(progn {command} {suffix})\n'
    return request['command'] + suffix + '\n'


def read_completion(request):
    marker = Path(request['marker'])
    if not marker.exists():
        return None
    lines = marker.read_text(encoding='utf-8', errors='replace').splitlines()
    if not lines or lines[0] != request['token']:
        return None
    if request.get('completion') in ('stratigraphy-v1', 'live-v1'):
        if len(lines) < 3:
            return None  # Writer may not have closed the marker yet.
        if lines[1] != 'ok':
            raise RuntimeError(lines[2] or 'CAD no completó la estratigrafía.')
        return {'message': lines[2]}
    return {'message': 'CAD devolvió el control. Revisa la línea de comandos y el resultado. SINCAL no añade un guardado; la orden elegida puede guardar por sí misma.'}


def execute_all(request):
    app = active_application()
    expected = request['expected']
    targets = expected.get('documents', [])
    if not targets or len(targets) > 100:
        raise ValueError('La selección debe contener entre 1 y 100 dibujos.')
    initial = active_document(app)
    if read_when_ready(lambda: (str(app.HWND), str(initial.FullName), str(initial.Name))) != (expected['instance'], expected['active']['path'], expected['active']['name']):
        raise ValueError('Cambió la instancia o el dibujo activo antes de iniciar el recorrido.')
    documents = read_when_ready(lambda: app.Documents)
    opened = read_when_ready(lambda: {(str(documents.Item(i).Name), str(documents.Item(i).FullName)) for i in range(documents.Count)})
    if opened != {(item['name'], item['path']) for item in targets}:
        raise ValueError('Cambió la lista de dibujos abiertos. Confirma nuevamente los destinos.')
    completed = []
    for index, target in enumerate(targets):
        if read_when_ready(lambda: int(active_document(app).GetVariable('CMDACTIVE'))):
            raise ValueError('Hay un comando activo; se detuvo el recorrido sin enviar otra orden.')
        documents = read_when_ready(lambda: app.Documents)
        doc = read_when_ready(lambda: next((documents.Item(i) for i in range(documents.Count)
                    if str(documents.Item(i).Name) == target['name'] and str(documents.Item(i).FullName) == target['path']), None))
        if doc is None:
            raise ValueError('Se cerró o cambió uno de los dibujos pendientes.')
        doc.Activate()
        wait_for_document(app, target)
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
    if request.get('clipboard'):
        ensure_cad_clipboard()
    app = active_application()
    doc = active_document(app)
    expected = request['expected']
    if read_when_ready(lambda: (str(app.HWND), str(doc.FullName), str(doc.Name))) != (expected['instance'], expected['active']['path'], expected['active']['name']):
        raise ValueError('Cambió el dibujo o la instancia activa. Comprueba la conexión otra vez.')
    if read_when_ready(lambda: int(doc.GetVariable('CMDACTIVE'))):
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
    try:
        doc.SendCommand(command_with_completion(request))
    except Exception as error:
        raise RuntimeError('CAD puede haber recibido la orden. No se reenvió. Revisa el dibujo antes de repetir.') from error
    deadline = time.monotonic() + request.get('timeout', 180)
    while time.monotonic() < deadline:
        result = read_completion(request)
        if result is not None:
            return result
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
        import traceback
        response = {'ok': False, 'error': str(error), 'details': traceback.format_exc()}
    finally:
        pythoncom.CoUninitialize()
    Path(sys.argv[1]).with_name('result.json').write_text(json.dumps(response, ensure_ascii=True), encoding='utf-8')
    if sys.stdout is not None:
        print(json.dumps(response, ensure_ascii=True))


if __name__ == '__main__':
    main()
