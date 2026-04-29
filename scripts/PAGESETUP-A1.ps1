[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

# Obtener rutas absolutas de los scripts base
$PSScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$wrapperPath = Join-Path $PSScriptRoot "cad_wrapper.bat"
$scrPath = Join-Path $PSScriptRoot "PAGESETUP-A1.scr"

if (-not (Test-Path $wrapperPath)) {
    Write-Host "[ERROR] Consola CAD no detectada. Actualiza SINCAL.exe." -ForegroundColor Red
    exit
}

if (-not (Test-Path $scrPath)) {
    Write-Host "[ERROR] Archivo PAGESETUP-A1.scr no encontrado." -ForegroundColor Red
    exit
}

Write-Host "---------------------------------------------------" -ForegroundColor Cyan
Write-Host "Configuración masiva de página A1 iniciada" -ForegroundColor Cyan
Write-Host "---------------------------------------------------" -ForegroundColor Cyan

foreach ($file in $dwgFiles) {
    Write-Host "Configurando página A1 en: $($file.Name)" -ForegroundColor Green
    
    # Ejecución controlada invocando el wrapper
    $procArgs = "/c `"$wrapperPath`" /i `"$($file.FullName)`" /s `"$scrPath`""
    Start-Process -FilePath "cmd.exe" -ArgumentList $procArgs -Wait -NoNewWindow
}

Write-Host "`n¡Proceso finalizado!" -ForegroundColor Cyan