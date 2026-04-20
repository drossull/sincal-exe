@echo off
echo ===================================================
echo     ACTUALIZADOR MASIVO DE DWGPROPS (MULTIPLE)
echo ===================================================
echo.
echo Por favor, ingresa los datos para actualizar las viñetas.
echo (Se omitió "Nombre_Plano" para preservar la identidad de cada lámina)
echo.

:: 1. Captura de datos comunes
set /p nombre_est="1. Nombre_Estructura: "
set /p revision="2. Revision: "
set /p fecha_rev="3. Fecha_Rev: "
set /p fecha_inf="4. Fecha_Inf: "
set /p no_total_planos="5. No_total_planos: "

:: 2. Ruta del script temporal
set "ruta_script=C:\Users\Usuario\Documents\SINCAL\SCRIPTS\TEMP_PROPS.scr"

:: 3. Generación del Script (.scr) con las 5 propiedades restantes
echo (vl-load-com) > "%ruta_script%"
echo (setq info (vla-get-SummaryInfo (vla-get-ActiveDocument (vlax-get-acad-object)))) >> "%ruta_script%"

:: Inyectamos las propiedades
echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Nombre_Estructura" "%nombre_est%"))) (vla-AddCustomInfo info "Nombre_Estructura" "%nombre_est%")) >> "%ruta_script%"
echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Revision" "%revision%"))) (vla-AddCustomInfo info "Revision" "%revision%")) >> "%ruta_script%"
echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Fecha_Rev" "%fecha_rev%"))) (vla-AddCustomInfo info "Fecha_Rev" "%fecha_rev%")) >> "%ruta_script%"
echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Fecha_Inf" "%fecha_inf%"))) (vla-AddCustomInfo info "Fecha_Inf" "%fecha_inf%")) >> "%ruta_script%"
echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "No_total_planos" "%no_total_planos%"))) (vla-AddCustomInfo info "No_total_planos" "%no_total_planos%")) >> "%ruta_script%"

:: Comandos finales de limpieza y guardado
echo (setvar "WIPEOUTFRAME" 0) >> "%ruta_script%"
echo _.QSAVE >> "%ruta_script%"
echo _.QUIT >> "%ruta_script%"
echo. >> "%ruta_script%"

echo.
echo ---------------------------------------------------
echo Datos capturados. Iniciando procesamiento masivo...
echo ---------------------------------------------------

:: 4. Ejecución en AutoCAD 2025
for %%f in (*.dwg) do (
    echo Procesando: %%f
    start /wait "" "C:\Program Files\Autodesk\AutoCAD 2025\acad.exe" /nologo "%%~ff" /b "%ruta_script%"
)

:: 5. Eliminación del script temporal
del "%ruta_script%"

echo.
echo ===================================================
echo ¡Proceso finalizado con éxito!
echo ===================================================
pause