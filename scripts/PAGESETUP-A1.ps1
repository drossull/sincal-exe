[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$appDataPath = [Environment]::GetFolderPath('ApplicationData')
$wrapperPath = Join-Path $appDataPath "Estandar SINCAL\cad_wrapper.bat"
$scrPath = Join-Path $appDataPath "Estandar SINCAL\scripts\PAGESETUP-A1.scr"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  SINCAL - CONFIGURACION DE PAGINA A1" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Validar que el programa base SINCAL este instalado
if (-not (Test-Path $wrapperPath)) {
    Write-Host "`n[X] ERROR FATAL: No se encontro el puente de CAD (cad_wrapper.bat)." -ForegroundColor Red
    Write-Host "Por favor, abre SINCAL.exe y presiona 'Instalar / Actualizar Todo'." -ForegroundColor Yellow
    Pause
    exit
}

if (-not (Test-Path $scrPath)) {
    Write-Host "`n[X] ERROR FATAL: Archivo PAGESETUP-A1.scr no encontrado en AppData." -ForegroundColor Red
    Pause
    exit
}

# 2. Buscar todos los archivos DWG en la carpeta actual
$rutaActual = (Get-Location).Path
$archivos = @(Get-ChildItem -Path $rutaActual -Filter *.dwg)

if ($archivos.Count -eq 0) {
    Write-Host "`n[!] No se encontraron archivos DWG en: $rutaActual" -ForegroundColor Yellow
    Pause
    exit
}

Write-Host "`nSe encontraron $($archivos.Count) planos. Iniciando procesamiento en segundo plano...`n" -ForegroundColor Green

# 3. Enviar cada plano a la consola invisible de CAD
foreach ($dwg in $archivos) {
    Write-Host "> Aplicando a: $($dwg.Name)..." -ForegroundColor White
    
    $argList = "/i `"$($dwg.FullName)`" /s `"$scrPath`""
    Start-Process -FilePath $wrapperPath -ArgumentList $argList -Wait -NoNewWindow
}

Write-Host "`n[OK] Tarea finalizada exitosamente." -ForegroundColor Green
Pause