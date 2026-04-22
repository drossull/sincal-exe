@echo off
chcp 65001 > nul
call "%~dp0cad_env.bat"

echo ---------------------------------------------------
echo Consola detectada: %CAD_CONSOLE%
echo ---------------------------------------------------

if "%CAD_CONSOLE%"=="" (
    echo [ERROR] No se pudo cargar la ruta de la consola.
    pause
    exit /b
)

for %%f in (*.dwg) do (
    echo Configurando pagina A1 en: %%f
    "%CAD_CONSOLE%" /i "%%f" /s "%~dp0PAGESETUP-A1.scr"
)

echo.
echo ¡Proceso finalizado!
pause