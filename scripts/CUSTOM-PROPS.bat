@echo off
set "primer_dwg="
for %%f in (*.dwg) do (
    set "primer_dwg=%%f"
    goto :found
)
:found
if "%primer_dwg%"=="" exit /b

set "vbs_read=%~dp0READ.vbs"
set "data_file=TEMP_DATA.txt"

(
echo On Error Resume Next
echo Set fso = CreateObject("Scripting.FileSystemObject"^)
echo Set outFile = fso.CreateTextFile("%data_file%", True^)
echo Set dbx = CreateObject("ObjectDBX.AxDbDocument.25"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ObjectDBX.AxDbDocument.24"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ZWCAD.ZcadDbDocument"^)
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

cscript //nologo "%vbs_read%"

for /f "usebackq tokens=1,* delims==" %%A in ("%data_file%") do set "val_%%A=%%B"
del "%data_file%"
del "%vbs_read%"

cls
echo ===================================================
echo    ACTUALIZADOR MASIVO DE DWGPROPS
echo ===================================================
echo.

set /p "in_nombre_est=1. Nombre_Estructura [%val_Nombre_Estructura%]: "
if not defined in_nombre_est set "in_nombre_est=%val_Nombre_Estructura%"

set /p "in_provincia=2. Provincia [%val_Provincia%]: "
if not defined in_provincia set "in_provincia=%val_Provincia%"

set /p "in_comuna=3. Comuna [%val_Comuna%]: "
if not defined in_comuna set "in_comuna=%val_Comuna%"

set /p "in_revision=4. Revision [%val_Revision%]: "
if not defined in_revision set "in_revision=%val_Revision%"

set /p "in_fecha_rev=5. Fecha_Rev [%val_Fecha_Rev%]: "
if not defined in_fecha_rev set "in_fecha_rev=%val_Fecha_Rev%"

set /p "in_fecha_inf=6. Fecha_Inf [%val_Fecha_Inf%]: "
if not defined in_fecha_inf set "in_fecha_inf=%val_Fecha_Inf%"

set /p "in_no_total_planos=7. No_total_planos [%val_No_total_planos%]: "
if not defined in_no_total_planos set "in_no_total_planos=%val_No_total_planos%"

set /p "in_nombre_plano=8. Nombre_Plano [%val_Nombre_Plano%]: "
if not defined in_nombre_plano set "in_nombre_plano=%val_Nombre_Plano%"

set "vbs_write=%~dp0WRITE.vbs"

(
echo On Error Resume Next
echo Set fso = CreateObject("Scripting.FileSystemObject"^)
echo Set folder = fso.GetFolder("."^)
echo Set dbx = CreateObject("ObjectDBX.AxDbDocument.25"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ObjectDBX.AxDbDocument.24"^)
echo If dbx Is Nothing Then Set dbx = CreateObject("ZWCAD.ZcadDbDocument"^)
echo For Each file In folder.Files
echo   If LCase(fso.GetExtensionName(file.Name^)^) = "dwg" Then
echo     WScript.Echo "Procesando: " ^& file.Name
echo     dbx.Open file.Path
echo     Set info = dbx.SummaryInfo
echo     SetCustom dbx, info, "Nombre_Estructura", "%in_nombre_est%"
echo     SetCustom dbx, info, "Provincia", "%in_provincia%"
echo     SetCustom dbx, info, "Comuna", "%in_comuna%"
echo     SetCustom dbx, info, "Revision", "%in_revision%"
echo     SetCustom dbx, info, "Fecha_Rev", "%in_fecha_rev%"
echo     SetCustom dbx, info, "Fecha_Inf", "%in_fecha_inf%"
echo     SetCustom dbx, info, "No_total_planos", "%in_no_total_planos%"
echo     SetCustom dbx, info, "Nombre_Plano", "%in_nombre_plano%"
echo     dbx.SaveAs file.Path
echo   End If
echo Next
echo Sub SetCustom(d, i, k, v^)
echo   Err.Clear
echo   i.SetCustomByKey k, v
echo   If Err.Number ^<^> 0 Then i.AddCustomInfo k, v
echo End Sub
) > "%vbs_write%"

echo.
echo Sincronizando planos...
cscript //nologo "%vbs_write%"
del "%vbs_write%"

echo.
echo Proceso finalizado.
pause