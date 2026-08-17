[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

$appDataPath = [Environment]::GetFolderPath("LocalApplicationData")
$runtimePath = Join-Path $appDataPath "SINCAL\runtime"
$wrapperPath = Join-Path $runtimePath "cad_wrapper.bat"
$appPath = if ($PSScriptRoot) { Split-Path $PSScriptRoot -Parent } else { (Get-Location).Path }
$scrPath = Join-Path $appPath "scripts\ZE.scr"

if (-not (Test-Path $wrapperPath)) {
    Write-Host "[ERROR] Consola CAD no detectada. Abre SINCAL y presiona 'Preparar integración CAD'." -ForegroundColor Red
    exit
}

if (-not (Test-Path $scrPath)) {
    Write-Host "[ERROR] Archivo ZE.scr no encontrado en la instalación de SINCAL." -ForegroundColor Red
    exit
}

Write-Host "---------------------------------------------------" -ForegroundColor Cyan
Write-Host "Aplicación masiva de Zoom Extents" -ForegroundColor Cyan
Write-Host "---------------------------------------------------" -ForegroundColor Cyan

$errores = 0

foreach ($file in $dwgFiles) {
    Write-Host "Aplicando Zoom Extents a: $($file.Name)" -ForegroundColor Green
    
    $argList = "/i `"$($file.FullName)`" /s `"$scrPath`""
    $proc = Start-Process -FilePath $wrapperPath -ArgumentList $argList -Wait -NoNewWindow -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Host "  [ERROR] Proceso CAD falló para $($file.Name) con código $($proc.ExitCode)." -ForegroundColor Red
        $errores++
    }
}

if ($errores -gt 0) {
    Write-Host "`n[ERROR] Zoom Extents terminó con $errores archivo(s) con error." -ForegroundColor Red
    exit 1
}

Write-Host "`n[OK] Zoom Extents finalizado sin errores." -ForegroundColor Cyan