@echo off
rem Cargar la ruta de la consola
call "%~dp0cad_env.bat"

rem Verificacion de seguridad
if "%CAD_CONSOLE%"=="" (
    echo [ERROR] No se pudo cargar la ruta de la consola.
    echo Asegurate de presionar "Actualizar" en el SINCAL.exe
    pause
    exit /b
)

rem 1. Buscar el primer DWG de la carpeta
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
echo   (100%% SEGUNDO PLANO - SILENCIOSO)
echo   Extrayendo datos de: %primer_dwg%
echo ===================================================

rem 2. Generar script temporal de EXTRACCION
set "extract_scr=%~dp0TEMP_EXTRACT.scr"
set "data_file=%~dp0TEMP_DATA.txt"
set "data_file_lisp=%data_file:\=/%"

echo (vl-load-com) > "%extract_scr%"
rem TRUCO MAESTRO: Obtener el documento desde la base de datos, ignorando si la App esta apagada
echo (setq acadObj (vlax-get-acad-object)) >> "%extract_scr%"
echo (setq doc (if acadObj (vla-get-ActiveDocument acadObj) (vla-get-Document (vlax-ename-^>vla-object (namedobjdict))))) >> "%extract_scr%"
echo (setq info (vla-get-SummaryInfo doc)) >> "%extract_scr%"
echo (setq f (open "%data_file_lisp%" "w")) >> "%extract_scr%"
echo (foreach p '("Nombre_Estructura" "Provincia" "Comuna" "Revision" "Fecha_Rev" "Fecha_Inf" "No_total_planos" "Nombre_Plano") (setq val "") (vl-catch-all-apply 'vla-GetCustomByKey (list info p 'val)) (if (= val nil) (setq val "")) (write-line (strcat p "=" val) f)) >> "%extract_scr%"
echo (close f) >> "%extract_scr%"
echo _.QSAVE >> "%extract_scr%"
echo _.QUIT >> "%extract_scr%"
echo. >> "%extract_scr%"

rem Ejecutar extraccion silenciosa
call "%CAD_CONSOLE%" /i "%primer_dwg%" /s "%extract_scr%" > nul 2>&1

rem 3. Leer los datos
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

rem 4. Captura interactiva
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

rem 5. Generacion del Script de INYECCION
set "ruta_script=%~dp0TEMP_PROPS.scr"
echo (vl-load-com) > "%ruta_script%"
echo (setq acadObj (vlax-get-acad-object)) >> "%ruta_script%"
echo (setq doc (if acadObj (vla-get-ActiveDocument acadObj) (vla-get-Document (vlax-ename-^>vla-object (namedobjdict))))) >> "%ruta_script%"
echo (setq info (vla-get-SummaryInfo doc)) >> "%ruta_script%"
echo (defun setProp (k v) (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-SetCustomByKey (list info k v))) (vl-catch-all-apply 'vla-AddCustomInfo (list info k v)))) >> "%ruta_script%"

if defined in_nombre_est echo (setProp "Nombre_Estructura" "%in_nombre_est%") >> "%ruta_script%"
if defined in_provincia echo (setProp "Provincia" "%in_provincia%") >> "%ruta_script%"
if defined in_comuna echo (setProp "Comuna" "%in_comuna%") >> "%ruta_script%"
if defined in_revision echo (setProp "Revision" "%in_revision%") >> "%ruta_script%"
if defined in_fecha_rev echo (setProp "Fecha_Rev" "%in_fecha_rev%") >> "%ruta_script%"
if defined in_fecha_inf echo (setProp "Fecha_Inf" "%in_fecha_inf%") >> "%ruta_script%"
if defined in_no_total_planos echo (setProp "No_total_planos" "%in_no_total_planos%") >> "%ruta_script%"
if defined in_nombre_plano echo (setProp "Nombre_Plano" "%in_nombre_plano%") >> "%ruta_script%"

echo (vl-catch-all-apply 'vla-put-Subject (list info "SINCAL")) >> "%ruta_script%"
echo (setvar "USERI1" (if (= (getvar "USERI1") 1) 2 1)) >> "%ruta_script%"
echo (setvar "WIPEOUTFRAME" 0) >> "%ruta_script%"
echo _.QSAVE >> "%ruta_script%"
echo _.QUIT >> "%ruta_script%"
echo. >> "%ruta_script%"

echo.
echo ---------------------------------------------------
echo Datos capturados. Iniciando procesamiento masivo...
echo ---------------------------------------------------

rem 6. Ejecucion Universal Silenciosa
for %%f in (*.dwg) do (
    echo Procesando: %%f
    call "%CAD_CONSOLE%" /i "%%f" /s "%ruta_script%"
)

rem 7. Limpieza
del "%ruta_script%"

echo.
echo ===================================================
echo Proceso finalizado con exito!
echo ===================================================
pause