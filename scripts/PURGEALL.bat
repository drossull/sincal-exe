@echo off
:: Cargar la ruta de la consola detectada por Python
call "%AppData%\Estándar SINCAL\scripts\cad_env.bat"

echo Purgando elementos no usados (capas, bloques, estilos) en todos los planos...
echo Usando consola: %CAD_CONSOLE%

for %%f in (*.dwg) do (
    echo ---------------------------------------------------
    echo Purgando el plano: %%f
    "%CAD_CONSOLE%" /i "%%f" /s "%~dp0PURGEALL.scr"
)

echo.
echo ¡Limpieza profunda finalizada en todos los archivos!
pause