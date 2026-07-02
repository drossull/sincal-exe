[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

$appDataPath = [Environment]::GetFolderPath("ApplicationData")
$wrapperPath = Join-Path $appDataPath "Estandar SINCAL\cad_wrapper.bat"
$scrPath = Join-Path $appDataPath "Estandar SINCAL\scripts\PUBLISH.scr"

if (-not (Test-Path $wrapperPath)) {
    Write-Host "[ERROR] Consola CAD no detectada. Abre SINCAL y presiona 'Instalar / Actualizar Todo'." -ForegroundColor Red
    exit
}

if (-not (Test-Path $scrPath)) {
    Write-Host "[ERROR] Archivo PUBLISH.scr no encontrado en AppData." -ForegroundColor Red
    exit
}

Write-Host "---------------------------------------------------" -ForegroundColor Cyan
Write-Host "Publicación masiva de PDF" -ForegroundColor Cyan
Write-Host "---------------------------------------------------" -ForegroundColor Cyan

foreach ($file in $dwgFiles) {
    Write-Host "Publicando PDF de: $($file.Name)" -ForegroundColor Green
    
    $argList = "/i `"$($file.FullName)`" /s `"$scrPath`""
    Start-Process -FilePath $wrapperPath -ArgumentList $argList -Wait -NoNewWindow
}

Write-Host "`n¡Proceso finalizado!" -ForegroundColor Cyan