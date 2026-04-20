@echo off
:: Cargar la ruta de la consola detectada por Python
call "%AppData%\Estándar SINCAL\scripts\cad_env.bat"

echo Eliminando Layout2 en todos los planos...
echo Usando consola: %CAD_CONSOLE%
echo ---------------------------------------------------

for %%f in (*.dwg) do (
    echo Procesando: %%f
    "%CAD_CONSOLE%" /i "%%f" /s "%~dp0DL2.scr"
)

echo.
echo ¡Proceso finalizado! Los Layout2 han sido eliminados.
pause