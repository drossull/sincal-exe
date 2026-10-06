"""Exact Explorer selections, never a directory scan. CAD work remains sequential."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

OPERATIONS = {'setup': 'PAGESETUP-A1', 'plot': 'PUBLISH-A1',
              'publish': 'PUBLISH-A1', 'ze': 'ZE', 'purge': 'PURGEALL'}


def request_root():
    return Path(os.environ['LOCALAPPDATA']) / 'SINCAL/shell-requests'


def read_shell_request(filename):
    path = Path(filename).resolve(strict=True)
    if path.parent != request_root().resolve() or path.suffix != '.json' or path.stat().st_size > 4*1024*1024:
        raise ValueError('Solicitud del Explorador no válida.')
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    selection = validate_selection(data)
    path.unlink()  # Only the consumed request, not drawings or prior sessions.
    return selection


def validate_selection(data):
    if data.get('operation') not in OPERATIONS or not isinstance(data.get('files'), list) or not 1 <= len(data['files']) <= 1000:
        raise ValueError('Selecciona entre 1 y 1000 DWG y una operación permitida.')
    files = []
    for name in data['files']:
        path = Path(name)
        if not path.is_absolute() or path.is_symlink() or path.suffix.lower() != '.dwg' or not path.is_file():
            raise ValueError('La selección contiene un archivo que no es un DWG regular.')
        name = str(path.resolve())
        if name not in files:
            files.append(name)
    return {'operation': data['operation'], 'files': files}


def drawing_available(path):
    if path.with_suffix('.dwl').exists() or path.with_suffix('.dwl2').exists():
        raise ValueError('Plano abierto o con bloqueo DWL; se omite.')
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(path), 0x80000000 | 0x40000000, 0, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ValueError('Plano abierto, bloqueado o sin permiso de escritura; se omite.')
        kernel.CloseHandle(handle)


def execute(job, selection, overwrite, runtime):
    from sincal.runtime import ruta_recurso
    import msvcrt
    selection = validate_selection(selection)
    if type(overwrite) is not bool:
        raise ValueError('Confirmación PDF no válida.')
    lock_path = request_root().parent / 'explorer-batch.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise ValueError('Hay otro lote contextual en curso. Espera a que termine.')
        try:
            results = []
            folder = runtime / uuid.uuid4().hex
            folder.mkdir()
            for index, filename in enumerate(selection['files']):
                job.check()  # Cancellation is deliberately only between drawings.
                path = Path(filename)
                job.update(f'{index+1}/{len(selection["files"])} · {path.name}', index*100/len(selection['files']))
                try:
                    drawing_available(path)
                    operation = selection['operation']
                    if operation in ('plot', 'publish') and path.with_suffix('.pdf').exists() and not overwrite:
                        raise ValueError('El PDF ya existe; no se autorizó reemplazarlo.')
                    if operation != 'plot':
                        backup = path.parent / 'SINCAL_Backups' / folder.name
                        backup.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, backup / path.name)
                    manifest = folder / f'{index}.json'
                    manifest.write_text(json.dumps({'schema':1,'files':[str(path)]}), encoding='utf-8')
                    script = Path(ruta_recurso('scripts/' + OPERATIONS[operation] + '.ps1'))
                    command = ['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),'-DrawingListFile',str(manifest)]
                    if operation == 'plot': command.append('-KeepSetup')
                    if operation in ('plot','publish') and overwrite: command.append('-OverwritePdf')
                    with (folder / f'{index}.log').open('wb') as output:
                        process = subprocess.Popen(command, cwd=path.parent, stdout=output, stderr=subprocess.STDOUT,
                                                   creationflags=subprocess.CREATE_NO_WINDOW)
                        while process.poll() is None:
                            time.sleep(.25)
                    if process.returncode:
                        raise ValueError('Falló el script. Revisa el registro de scripts CAD; no se reintentó.')
                    results.append({'file':filename,'status':'completed'})
                except (OSError, ValueError) as error:
                    results.append({'file':filename,'status':'skipped_or_failed','message':str(error)})
                job.update(json.dumps(results[-1], ensure_ascii=False), (index+1)*100/len(selection['files']))
            return {'files': results}
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
