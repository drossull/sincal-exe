@echo off
chcp 65001 > nul

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
echo   (Motor ObjectDBX - 100%% en segundo plano)
echo ===================================================

rem 2. Generar motor de extraccion nativo (VBScript)
set "vbs_read=%~dp0TEMP_READ.vbs"
set "data_file=TEMP_DATA.txt"

(
echo On Error Resume Next
echo Set fso = CreateObject("Scripting.FileSystemObject"^)
echo Set outFile = fso.CreateTextFile("%data_file%", True^)
echo Set dbx = CreateObject("ObjectDBX.AxDbDocument.25"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ObjectDBX.AxDbDocument.24"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ObjectDBX.AxDbDocument.23"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ObjectDBX.AxDbDocument.22"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ZWCAD.ZcadDbDocument"^)
echo If dbx Is Nothing Then
echo   outFile.WriteLine "ERROR=NODBX"
echo   WScript.Quit
echo End If
echo dbx.Open "%primer_dwg%"
echo Set info = dbx.SummaryInfo
echo props = Array("Nombre_Estructura", "Provincia", "Comuna", "Revision", "Fecha_Rev", "Fecha_Inf", "No_total_planos", "Nombre_Plano"^)
echo For Each p In props
echo   val = ""
echo   info.GetCustomByKey p, val
echo   outFile.WriteLine p ^& "=" ^& val
echo Next
echo outFile.Close
) > "%vbs_read%"

rem Ejecutar lectura silenciosa
cscript //nologo "%vbs_read%"

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
del "%vbs_read%"

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

echo.
echo ---------------------------------------------------
echo Datos capturados. Inyectando sin abrir AutoCAD...
echo ---------------------------------------------------

rem 5. Generar motor de INYECCION nativo (VBScript)
set "vbs_write=%~dp0TEMP_WRITE.vbs"

(
echo On Error Resume Next
echo Set fso = CreateObject("Scripting.FileSystemObject"^)
echo Set folder = fso.GetFolder("."^)
echo Set dbx = CreateObject("ObjectDBX.AxDbDocument.25"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ObjectDBX.AxDbDocument.24"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ObjectDBX.AxDbDocument.23"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ObjectDBX.AxDbDocument.22"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ZWCAD.ZcadDbDocument"^)
echo For Each file In folder.Files
echo   If LCase(fso.GetExtensionName(file.Name^)^) = "dwg" Then
echo     WScript.Echo "Procesando de fondo: " ^& file.Name
echo     dbx.Open file.Path
echo     Set info = dbx.SummaryInfo
echo     Sub SetProp(k, v^)
echo       If v ^<^> "" Then
echo         Err.Clear
echo         info.SetCustomByKey k, v
echo         If Err.Number ^<^> 0 Then
echo           Err.Clear
echo           info.AddCustomInfo k, v
echo         End If
echo       End If
echo     End Sub
echo     SetProp "Nombre_Estructura", "%in_nombre_est%"
echo     SetProp "Provincia", "%in_provincia%"
echo     SetProp "Comuna", "%in_comuna%"
echo     SetProp "Revision", "%in_revision%"
echo     SetProp "Fecha_Rev", "%in_fecha_rev%"
echo     SetProp "Fecha_Inf", "%in_fecha_inf%"
echo     SetProp "No_total_planos", "%in_no_total_planos%"
echo     SetProp "Nombre_Plano", "%in_nombre_plano%"
echo     dbx.SaveAs file.Path
echo   End If
echo Next
) > "%vbs_write%"

rem 6. Ejecutar Inyeccion
cscript //nologo "%vbs_write%"

rem 7. Limpieza
del "%vbs_write%"

echo.
echo ===================================================
echo ¡Proceso finalizado con éxito (Sin abrir CAD)!
echo ===================================================
pause