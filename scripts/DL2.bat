@echo off
echo Eliminando Layout2 en todos los planos...
for %%f in (*.dwg) do (
    "C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe" /i "%%f" /s "C:\Users\Usuario\Documents\SINCAL\SCRIPTS\DL2.scr"
)
echo.
echo ¡Proceso finalizado! Los Layout2 han sido eliminados.