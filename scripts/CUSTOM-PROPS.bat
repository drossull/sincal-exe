@echo off
:: Forzar consola a leer caracteres especiales (tildes) correctamente
chcp 65001 > nul

:: Cargar la ruta de la consola buscando en la MISMA carpeta del script
call "%~dp0cad_env.bat"

echo ===================================================
echo    ACTUALIZADOR MASIVO DE DWGPROPS (MULTIPLE)
echo ===================================================
echo.
echo Por favor, ingresa los datos para actualizar las viñetas.
echo (Si dejas un campo en blanco y presionas Enter, el plano
echo  conservará el valor que ya tiene actualmente)
echo.

:: Limpiar variables previas por seguridad para evitar que guarde basura en memoria
set "nombre_est="
set "provincia="
set "comuna="
set "revision="
set "fecha_rev="
set "fecha_inf="
set "no_total_planos="

:: 1. Captura de datos comunes (Ordenados de general a particular)
set /p nombre_est="1. Nombre_Estructura: "
set /p provincia="2. Provincia: "
set /p comuna="3. Comuna: "
set /p revision="4. Revision: "
set /p fecha_rev="5. Fecha_Rev: "
set /p fecha_inf="6. Fecha_Inf: "
set /p no_total_planos="7. No_total_planos: "

:: 2. Ruta del script temporal (Se guarda en la misma carpeta oculta universal)
set "ruta_script=%~dp0TEMP_PROPS.scr"

:: 3. Generación del Script (.scr) con condicionales
echo (vl-load-com) > "%ruta_script%"
echo (setq info (vla-get-SummaryInfo (vla-get-ActiveDocument (vlax-get-acad-object)))) >> "%ruta_script%"

:: Inyectamos las propiedades SOLO si la variable no está vacía
if defined nombre_est echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Nombre_Estructura" "%nombre_est%"))) (vla-AddCustomInfo info "Nombre_Estructura" "%nombre_est%")) >> "%ruta_script%"
if defined provincia echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Provincia" "%provincia%"))) (vla-AddCustomInfo info "Provincia" "%provincia%")) >> "%ruta_script%"
if defined comuna echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Comuna" "%comuna%"))) (vla-AddCustomInfo info "Comuna" "%comuna%")) >> "%ruta_script%"
if defined revision echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Revision" "%revision%"))) (vla-AddCustomInfo info "Revision" "%revision%")) >> "%ruta_script%"
if defined fecha_rev echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Fecha_Rev" "%fecha_rev%"))) (vla-AddCustomInfo info "Fecha_Rev" "%fecha_rev%")) >> "%ruta_script%"
if defined fecha_inf echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Fecha_Inf" "%fecha_inf%"))) (vla-AddCustomInfo info "Fecha_Inf" "%fecha_inf%")) >> "%ruta_script%"
if defined no_total_planos echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "No_total_planos" "%no_total_planos%"))) (vla-AddCustomInfo info "No_total_planos" "%no_total_planos%")) >> "%ruta_script%"

:: Comandos finales de limpieza y guardado
echo (setvar "WIPEOUTFRAME" 0) >> "%ruta_script%"
echo _.QSAVE >> "%ruta_script%"
echo _.QUIT >> "%ruta_script%"
echo. >> "%ruta_script%"

echo.
echo ---------------------------------------------------
echo Datos capturados. Iniciando procesamiento masivo...
echo Consola detectada: %CAD_CONSOLE%
echo ---------------------------------------------------

:: Verificación de seguridad por si no se detectó el CAD
if "%CAD_CONSOLE%"=="" (
    echo [ERROR] No se pudo cargar la ruta de la consola de AutoCAD/ZWCAD.
    echo Asegurate de haber presionado "Actualizar" en el SINCAL.exe
    del "%ruta_script%" 2>nul
    pause
    exit /b
)

:: 4. Ejecución Universal y Silenciosa
for %%f in (*.dwg) do (
    echo Procesando: %%f
    "%CAD_CONSOLE%" /i "%%f" /s "%ruta_script%"
)

:: 5. Eliminación del script temporal
del "%ruta_script%"

echo.
echo ===================================================
echo ¡Proceso finalizado con éxito!
echo ===================================================
pause