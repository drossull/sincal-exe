# Módulo independiente. FreeCAD y AutoCAD se ejecutan como aplicaciones externas.
from pathlib import Path

root = Path(SPECPATH).resolve().parents[1]
package = root / "pasarela_bim"
data = [(str(package / "web"), "pasarela_bim/web"),
        (str(package / "ejemplos"), "pasarela_bim/ejemplos")]
# FreeCAD necesita importar el motor con SU Python. No puede leer el PYZ del
# ejecutable; se incluye sólo el código propio, nunca sus binarios o librerías.
data += [(str(path), "runtime/pasarela_bim") for path in sorted(package.glob("*.py"))]

a = Analysis([str(root / "packaging/windows/pasarela_entry.py")],
             pathex=[str(root)], binaries=[], datas=data, hiddenimports=[],
             hookspath=[], runtime_hooks=[],
             excludes=["sincal", "FreeCAD", "FreeCADGui", "Part", "TechDraw",
                       "PySide6", "PySide2", "PyQt5", "PyQt6", "paddle", "paddleocr"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="SINCAL-Pasarela",
          debug=False, strip=False, upx=False, console=False,
          icon=[str(root / "assets/icons/logo.ico")])
