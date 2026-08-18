[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "SINCAL_ENGINE.ps1")

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

try {
    $enginePath = Get-SincalCadEngine
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    LIMPIEZA PROFUNDA (PURGE ALL + AUDIT)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$errores = 0

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
    
    $argList = "/i `"$($file.FullName)`" /s `"$scriptPath`""
    $proc = Start-Process -FilePath $enginePath -ArgumentList $argList -Wait -NoNewWindow -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Host "  [ERROR] Proceso CAD falló para $($file.Name) con código $($proc.ExitCode)." -ForegroundColor Red
        $errores++
    }
}

Remove-Item -Path $scriptPath -Force

Write-Host "`n===================================================" -ForegroundColor Cyan
if ($errores -gt 0) {
    Write-Host "Proceso terminado con $errores archivo(s) con error." -ForegroundColor Red
    Write-Host "===================================================" -ForegroundColor Cyan
    exit 1
}

Write-Host "Proceso finalizado con éxito." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
