# Opt-in only. Do not build without the user's compilation approval.
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

project_root = os.path.abspath(os.path.join(SPECPATH, '..', '..'))
web_data = collect_data_files('webview') + [
    (os.path.join(project_root, 'sincal', 'web', 'static'), 'sincal/web/static'),
    (os.path.join(project_root, 'assets', 'fonts'), 'assets/fonts'),
    (os.path.join(project_root, 'assets', 'icons'), 'assets/icons'),
]
a = Analysis([os.path.join(project_root, 'desktop_main.py')], pathex=[project_root],
             binaries=[], datas=web_data,
             hiddenimports=collect_submodules('webview') + ['clr', 'pythoncom', 'win32com.client'],
             hookspath=[], runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='SINCAL', debug=False,
          strip=False, upx=True, console=False,
          manifest=os.path.join(project_root, 'packaging', 'windows', 'SINCAL.manifest'),
          icon=[os.path.join(project_root, 'assets', 'icons', 'logo.ico')])
