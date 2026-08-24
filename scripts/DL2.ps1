[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "SINCAL_ENGINE.ps1")

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

$appPath = if ($PSScriptRoot) { Split-Path $PSScriptRoot -Parent } else { (Get-Location).Path }
$scrPath = Join-Path $appPath "scripts\DL2.scr"

try {
    $engine = Get-SincalCadEngine
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $scrPath)) {
    Write-Host "[ERROR] Archivo DL2.scr no encontrado en la instalación de SINCAL." -ForegroundColor Red
    exit
}

Write-Host "---------------------------------------------------" -ForegroundColor Cyan
Write-Host "Eliminación masiva de Layout2" -ForegroundColor Cyan
Write-Host "---------------------------------------------------" -ForegroundColor Cyan

$errores = 0

foreach ($file in $dwgFiles) {
    Write-Host "Eliminando Layout2 en: $($file.Name)" -ForegroundColor Green
    
    try {
        Invoke-SincalCadScript -Engine $engine -DrawingPath $file.FullName -ScriptPath $scrPath | Out-Null
    }
    catch {
        Write-Host "  [ERROR] Proceso CAD falló para $($file.Name): $($_.Exception.Message)" -ForegroundColor Red
        $errores++
    }
}

if ($errores -gt 0) {
    Write-Host "`n[ERROR] Eliminación de Layout2 terminada con $errores archivo(s) con error." -ForegroundColor Red
    exit 1
}

Write-Host "`n[OK] Eliminación de Layout2 finalizada sin errores." -ForegroundColor Cyan
