@echo off
echo Generando PDFs con el nombre exacto del DWG...

for %%F in (*.dwg) do (
    echo ---------------------------------------------------
    echo Imprimiendo el plano: %%F
    
    :: Ejecutamos AutoCAD para imprimir usando tu script limpio
    "C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe" /i "%%F" /s "C:\Users\Usuario\Documents\SINCAL\SCRIPTS\PUBLISH.scr"
)

echo.
echo ¡Proceso finalizado! PDFs generados y a salvo.