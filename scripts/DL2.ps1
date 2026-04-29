[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

$PSScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$wrapperPath = Join-Path $PSScriptRoot "cad_wrapper.bat"
$scrPath = Join-Path $PSScriptRoot "DL2.scr"

if (-not (Test-Path $wrapperPath)) {
    Write-Host "[ERROR] Consola CAD no detectada. Actualiza SINCAL.exe." -ForegroundColor Red
    exit
}

if (-not (Test-Path $scrPath)) {
    Write-Host "[ERROR] Archivo DL2.scr no encontrado." -ForegroundColor Red
    exit
}

Write-Host "---------------------------------------------------" -ForegroundColor Cyan
Write-Host "Eliminación masiva de Layout2" -ForegroundColor Cyan
Write-Host "---------------------------------------------------" -ForegroundColor Cyan

foreach ($file in $dwgFiles) {
    Write-Host "Eliminando Layout2 en: $($file.Name)" -ForegroundColor Green
    
    $argList = "/i `"$($file.FullName)`" /s `"$scrPath`""
    Start-Process -FilePath $wrapperPath -ArgumentList $argList -Wait -NoNewWindow
}

Write-Host "`n¡Proceso finalizado!" -ForegroundColor Cyan