@echo off
echo Configurando la hoja de impresion en todos los planos...
for %%f in (*.dwg) do (
    "C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe" /i "%%f" /s "C:\Users\Usuario\Documents\SINCAL\SCRIPTS\PAGESETUP-A1.scr"
)
echo.
echo ¡Todas las hojas de impresion fueron configuradas y guardadas!