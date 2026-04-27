@echo off
:: Forzar consola a leer caracteres especiales (tildes) correctamente
chcp 65001 > nul

:: Cargar la ruta de la consola buscando en la MISMA carpeta del script
call "%~dp0cad_env.bat"

:: Verificación de seguridad
if "%CAD_CONSOLE%"=="" (
    echo [ERROR] No se pudo cargar la ruta de la consola.
    pause
    exit /b
)

:: 1. Buscar el primer DWG de la carpeta
set "primer_dwg="
for %%f in (*.dwg) do (
    set "primer_dwg=%%f"
    goto :encontrado
)
:encontrado
if "%primer_dwg%"=="" (
    echo [ERROR] No hay archivos DWG en esta carpeta.
    pause
    exit /b
)

echo ===================================================
echo   ANALIZANDO PROPIEDADES ACTUALES...
echo   Extrayendo datos de: %primer_dwg%
echo   (Por favor espera unos segundos)
echo ===================================================

:: 2. Generar script temporal de EXTRACCION
set "extract_scr=%~dp0TEMP_EXTRACT.scr"
set "data_file=%~dp0TEMP_DATA.txt"
set "data_file_lisp=%data_file:\=/%"

echo (vl-load-com) > "%extract_scr%"
echo (setq info (vla-get-SummaryInfo (vla-get-ActiveDocument (vlax-get-acad-object)))) >> "%extract_scr%"
echo (setq f (open "%data_file_lisp%" "w")) >> "%extract_scr%"
echo (foreach p '("Nombre_Estructura" "Provincia" "Comuna" "Revision" "Fecha_Rev" "Fecha_Inf" "No_total_planos" "Nombre_Plano") (setq val "") (vl-catch-all-apply 'vla-GetCustomByKey (list info p 'val)) (write-line (strcat p "=" val) f)) >> "%extract_scr%"
echo (close f) >> "%extract_scr%"
echo _.QUIT >> "%extract_scr%"
echo. >> "%extract_scr%"

:: Ejecutar extraccion silenciosa
"%CAD_CONSOLE%" /i "%primer_dwg%" /s "%extract_scr%" > nul 2>&1

:: 3. Leer los datos (CON MODO USEBACKQ PARA EVITAR ERRORES DE ESPACIO)
set "val_Nombre_Estructura="
set "val_Provincia="
set "val_Comuna="
set "val_Revision="
set "val_Fecha_Rev="
set "val_Fecha_Inf="
set "val_No_total_planos="
set "val_Nombre_Plano="

if exist "%data_file%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%data_file%") do (
        set "val_%%A=%%B"
    )
    del "%data_file%"
)
del "%extract_scr%"

:: 4. Captura interactiva
cls
echo ===================================================
echo    ACTUALIZADOR MASIVO DE DWGPROPS (MULTIPLE)
echo ===================================================
echo Datos base leidos de: %primer_dwg%
echo.
echo Presiona ENTER para mantener el valor actual [mostrado entre corchetes].
echo Escribe un nuevo valor para sobrescribirlo.
echo.

set "in_nombre_est="
set /p "in_nombre_est=1. Nombre_Estructura [%val_Nombre_Estructura%]: "
if not defined in_nombre_est set "in_nombre_est=%val_Nombre_Estructura%"

set "in_provincia="
set /p "in_provincia=2. Provincia [%val_Provincia%]: "
if not defined in_provincia set "in_provincia=%val_Provincia%"

set "in_comuna="
set /p "in_comuna=3. Comuna [%val_Comuna%]: "
if not defined in_comuna set "in_comuna=%val_Comuna%"

set "in_revision="
set /p "in_revision=4. Revision [%val_Revision%]: "
if not defined in_revision set "in_revision=%val_Revision%"

set "in_fecha_rev="
set /p "in_fecha_rev=5. Fecha_Rev [%val_Fecha_Rev%]: "
if not defined in_fecha_rev set "in_fecha_rev=%val_Fecha_Rev%"

set "in_fecha_inf="
set /p "in_fecha_inf=6. Fecha_Inf [%val_Fecha_Inf%]: "
if not defined in_fecha_inf set "in_fecha_inf=%val_Fecha_Inf%"

set "in_no_total_planos="
set /p "in_no_total_planos=7. No_total_planos [%val_No_total_planos%]: "
if not defined in_no_total_planos set "in_no_total_planos=%val_No_total_planos%"

set "in_nombre_plano="
set /p "in_nombre_plano=8. Nombre_Plano [%val_Nombre_Plano%]: "
if not defined in_nombre_plano set "in_nombre_plano=%val_Nombre_Plano%"

:: 5. Generacion del Script de INYECCION
set "ruta_script=%~dp0TEMP_PROPS.scr"
echo (vl-load-com) > "%ruta_script%"
echo (setq info (vla-get-SummaryInfo (vla-get-ActiveDocument (vlax-get-acad-object)))) >> "%ruta_script%"

if defined in_nombre_est echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Nombre_Estructura" "%in_nombre_est%"))) (vla-AddCustomInfo info "Nombre_Estructura" "%in_nombre_est%")) >> "%ruta_script%"
if defined in_provincia echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Provincia" "%in_provincia%"))) (vla-AddCustomInfo info "Provincia" "%in_provincia%")) >> "%ruta_script%"
if defined in_comuna echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Comuna" "%in_comuna%"))) (vla-AddCustomInfo info "Comuna" "%in_comuna%")) >> "%ruta_script%"
if defined in_revision echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Revision" "%in_revision%"))) (vla-AddCustomInfo info "Revision" "%in_revision%")) >> "%ruta_script%"
if defined in_fecha_rev echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Fecha_Rev" "%in_fecha_rev%"))) (vla-AddCustomInfo info "Fecha_Rev" "%in_fecha_rev%")) >> "%ruta_script%"
if defined in_fecha_inf echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Fecha_Inf" "%in_fecha_inf%"))) (vla-AddCustomInfo info "Fecha_Inf" "%in_fecha_inf%")) >> "%ruta_script%"
if defined in_no_total_planos echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "No_total_planos" "%in_no_total_planos%"))) (vla-AddCustomInfo info "No_total_planos" "%in_no_total_planos%")) >> "%ruta_script%"
if defined in_nombre_plano echo (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info "Nombre_Plano" "%in_nombre_plano%"))) (vla-AddCustomInfo info "Nombre_Plano" "%in_nombre_plano%")) >> "%ruta_script%"

echo (setvar "WIPEOUTFRAME" 0) >> "%ruta_script%"
echo _.QSAVE >> "%ruta_script%"
echo _.QUIT >> "%ruta_script%"
echo. >> "%ruta_script%"

echo.
echo ---------------------------------------------------
echo Datos capturados. Iniciando procesamiento masivo...
echo ---------------------------------------------------

:: 6. Ejecucion Universal
for %%f in (*.dwg) do (
    echo Procesando: %%f
    "%CAD_CONSOLE%" /i "%%f" /s "%ruta_script%"
)

:: 7. Limpieza
del "%ruta_script%"

echo.
echo ===================================================
echo ¡Proceso finalizado con éxito!
echo ===================================================
pause