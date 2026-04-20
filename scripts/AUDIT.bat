@echo off
echo Ejecutando AUDIT (reparacion de errores) en todos los planos...

for %%F in (*.dwg) do (
    echo ---------------------------------------------------
    echo Auditando el plano: %%F
    
    "C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe" /i "%%F" /s "C:\Users\Usuario\Documents\SINCAL\SCRIPTS\AUDIT.scr"
)

echo.
echo ¡Proceso finalizado! Todos los archivos han sido auditados, reparados y guardados.