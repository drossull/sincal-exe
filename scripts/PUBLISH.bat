@echo off
:: Cargar la ruta de la consola detectada por Python
call "%AppData%\Estándar SINCAL\scripts\cad_env.bat"

echo Generando PDFs con el nombre exacto del DWG...
echo Usando consola: %CAD_CONSOLE%

for %%F in (*.dwg) do (
    echo ---------------------------------------------------
    echo Imprimiendo el plano: %%F
    
    :: Ejecutamos la consola CAD de forma silenciosa para imprimir
    "%CAD_CONSOLE%" /i "%%F" /s "%~dp0PUBLISH.scr"
)

echo.
echo ¡Proceso finalizado! PDFs generados y a salvo.
pause