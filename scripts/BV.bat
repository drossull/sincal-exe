@echo off
echo Ejecutando comando BV en todos los planos...
for %%f in (*.dwg) do (
    "C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe" /i "%%f" /s "C:\Users\Usuario\Documents\SINCAL\SCRIPTS\BV.scr"
)
echo.
echo ¡Proceso finalizado!