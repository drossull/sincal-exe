@echo off
echo Ejecutando Zoom Extents y guardando en todos los planos...
for %%f in (*.dwg) do (
    "C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe" /i "%%f" /s "C:\Users\Usuario\Documents\SINCAL\SCRIPTS\ZE.scr"
)
echo.
echo ¡Proceso finalizado!