[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

# Leer la ruta del wrapper de la misma carpeta donde está instalado el script
$PSScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$wrapperPath = Join-Path $PSScriptRoot "cad_wrapper.bat"

if (-not (Test-Path $wrapperPath)) {
    Write-Host "[ERROR] Consola CAD no detectada. Actualiza SINCAL.exe." -ForegroundColor Red
    exit
}

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    LIMPIEZA PROFUNDA (PURGE ALL + AUDIT)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$scriptPath = Join-Path (Get-Location) "TEMP_PURGE.scr"

# Construcción de comandos (Los saltos de línea son obligatorios para CAD)
$scrContent = @"
_.AUDIT _Y
_.-PURGE _A * _N
_.-PURGE _R * _N
_.ZOOM _E
_.QSAVE
_.QUIT

"@

# Guardado estricto en ASCII para evitar el BOM que rompe accoreconsole
Set-Content -Path $scriptPath -Value $scrContent -Encoding Ascii

foreach ($file in $dwgFiles) {
    Write-Host "Limpiando: $($file.Name)" -ForegroundColor Green
    
    # Ejecución controlada invocando el wrapper
    # SOLUCIÓN: Se agregan comillas al principio y al final de todos los argumentos (`" ... `") 
    # para evitar que cmd.exe elimine las comillas internas de las rutas con espacios.
    $procArgs = "/c `"`"$wrapperPath`" /i `"$($file.FullName)`" /s `"$scriptPath`"`""
    Start-Process -FilePath "cmd.exe" -ArgumentList $procArgs -Wait -NoNewWindow
}

Remove-Item -Path $scriptPath -Force

Write-Host "`n===================================================" -ForegroundColor Cyan
Write-Host "Proceso finalizado con éxito." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan