@echo off
:: Cargar la ruta de la consola detectada por Python
call "%AppData%\Estándar SINCAL\scripts\cad_env.bat"

echo Configurando la hoja de impresion en todos los planos...
echo Usando consola detectada: %CAD_CONSOLE%
echo ---------------------------------------------------

for %%f in (*.dwg) do (
    echo Procesando: %%f
    "%CAD_CONSOLE%" /i "%%f" /s "%~dp0PAGESETUP-A1.scr"
)

echo.
echo ¡Todas las hojas de impresion fueron configuradas y guardadas!
pause