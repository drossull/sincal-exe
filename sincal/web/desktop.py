"""Native Windows shell for the local UI. No external browser or public server."""
import os
from pathlib import Path
import threading

from .server import ROOT, Server


def run(webview, directory, selection=None):
    server = Server(0, directory)
    server.services.shell_selection = selection
    worker = threading.Thread(target=server.serve_forever, name="sincal-local-api", daemon=True)
    worker.start()
    try:
        webview.settings['ALLOW_DOWNLOADS'] = True
        webview.settings['ALLOW_FILE_URLS'] = False
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False
        window = webview.create_window(
            'SINCAL Suite 3.0',
            url=f'{server.origin}/#token={server.token}',
            width=1360, height=900, min_size=(850, 600),
            background_color='#1e1f25', text_select=True,
            confirm_close=True,
        )
        def picker(kind):
            if kind == 'folder':
                return window.create_file_dialog(webview.FileDialog.FOLDER)
            extensions = server.services.files.TYPES[kind]
            pattern = ';'.join('*' + ext for ext in extensions)
            return window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=kind in ('dxf','dwg','report','location','reference'),
                                             file_types=(f'Archivos compatibles ({pattern})',))
        server.services.files.picker = picker
        # No Python JS bridge: only the token-protected, typed local HTTP API.
        webview.start(
            gui='edgechromium', debug=False, private_mode=True,
            icon=str(ROOT / 'assets/icons/logo.ico'),
            localization={'global.quitConfirmation': '¿Cerrar SINCAL Suite? El trabajo cargado no se guarda y se descartará.'},
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def main(selection=None):
    if os.name != 'nt':
        raise SystemExit('Esta vista previa de escritorio requiere Windows y Microsoft Edge WebView2.')
    try:
        import webview
    except ImportError as error:
        raise SystemExit('Instala las dependencias: python -m pip install -r requirements-desktop-web.txt') from error
    directory = Path(os.environ['LOCALAPPDATA']) / 'SINCAL/web-pilot'
    try:
        run(webview, directory, selection)
    except Exception as error:
        # No automatic browser fallback; show actionable native feedback.
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,
            'No se pudo iniciar la interfaz de escritorio. Comprueba Microsoft Edge WebView2 Runtime.\n\n' + str(error),
            'SINCAL Suite', 0x10)
        raise


if __name__ == '__main__':
    main()
