@echo off
echo Purgando elementos no usados (capas, bloques, estilos) en todos los planos...

for %%f in (*.dwg) do (
    echo ---------------------------------------------------
    echo Purgando el plano: %%f
    "C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe" /i "%%f" /s "C:\Users\Usuario\Documents\SINCAL\SCRIPTS\PURGEALL.scr"
)

echo.
echo ¡Limpieza profunda finalizada en todos los archivos!