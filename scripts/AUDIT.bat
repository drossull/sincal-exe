@echo off
:: 1. Cargar la ruta de la consola detectada por Python
call "%AppData%\Estándar SINCAL\scripts\cad_env.bat"

echo Ejecutando AUDIT con: %CAD_CONSOLE%

for %%F in (*.dwg) do (
    echo ---------------------------------------------------
    echo Auditando el plano: %%F
    
    :: 2. Usar la variable detectada dinámicamente
    "%CAD_CONSOLE%" /i "%%F" /s "%~dp0AUDIT.scr"
)

echo.
echo ¡Proceso finalizado!
pause