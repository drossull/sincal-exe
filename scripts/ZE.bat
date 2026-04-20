@echo off
:: Cargar la ruta de la consola detectada por Python
call "%AppData%\Estándar SINCAL\scripts\cad_env.bat"

echo Ejecutando Zoom Extents y guardando en todos los planos...
echo Usando consola: %CAD_CONSOLE%
echo ---------------------------------------------------

for %%f in (*.dwg) do (
    echo Procesando: %%f
    "%CAD_CONSOLE%" /i "%%f" /s "%~dp0ZE.scr"
)

echo.
echo ¡Proceso finalizado!
pause
