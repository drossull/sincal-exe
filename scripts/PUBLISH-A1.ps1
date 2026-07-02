[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

$appDataPath = [Environment]::GetFolderPath("ApplicationData")
$wrapperPath = Join-Path $appDataPath "Estandar SINCAL\cad_wrapper.bat"
$scrPath = Join-Path $appDataPath "Estandar SINCAL\scripts\PUBLISH-A1.scr"

if (-not (Test-Path $wrapperPath)) {
    Write-Host "[ERROR] Consola CAD no detectada. Abre SINCAL y presiona 'Instalar / Actualizar Todo'." -ForegroundColor Red
    exit
}

if (-not (Test-Path $scrPath)) {
    Write-Host "[ERROR] Archivo PUBLISH-A1.scr no encontrado en AppData." -ForegroundColor Red
    exit
}

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  CONFIGURACION DE PAGINA A1 + EXPORTACION A PDF" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

Write-Host "`nSe encontraron $($dwgFiles.Count) planos. Iniciando procesamiento unificado...`n" -ForegroundColor Green

foreach ($file in $dwgFiles) {
    Write-Host "> Procesando y Exportando: $($file.Name)" -ForegroundColor White
    
    $argList = "/i `"$($file.FullName)`" /s `"$scrPath`""
    Start-Process -FilePath $wrapperPath -ArgumentList $argList -Wait -NoNewWindow
}

Write-Host "`n[OK] Tarea finalizada exitosamente." -ForegroundColor Cyan
Pause