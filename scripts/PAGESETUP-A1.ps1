[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$appDataPath = [Environment]::GetFolderPath('LocalApplicationData')
$runtimePath = Join-Path $appDataPath "SINCAL\runtime"
$wrapperPath = Join-Path $runtimePath "cad_wrapper.bat"
$appPath = if ($PSScriptRoot) { Split-Path $PSScriptRoot -Parent } else { (Get-Location).Path }
$scrPath = Join-Path $appPath "scripts\PAGESETUP-A1.scr"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  SINCAL - CONFIGURACION DE PAGINA A1" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Validar que el programa base SINCAL este instalado
if (-not (Test-Path $wrapperPath)) {
    Write-Host "`n[X] ERROR FATAL: No se encontro el puente de CAD (cad_wrapper.bat)." -ForegroundColor Red
    Write-Host "Por favor, abre SINCAL.exe y presiona 'Preparar integración CAD'." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $scrPath)) {
    Write-Host "`n[X] ERROR FATAL: Archivo PAGESETUP-A1.scr no encontrado en la instalación de SINCAL." -ForegroundColor Red
    exit 1
}

# 2. Buscar todos los archivos DWG en la carpeta actual
$rutaActual = (Get-Location).Path
$archivos = @(Get-ChildItem -Path $rutaActual -Filter *.dwg)

if ($archivos.Count -eq 0) {
    Write-Host "`n[!] No se encontraron archivos DWG en: $rutaActual" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nSe encontraron $($archivos.Count) planos. Iniciando procesamiento en segundo plano...`n" -ForegroundColor Green

$errores = 0

# 3. Enviar cada plano a la consola invisible de CAD
foreach ($dwg in $archivos) {
    Write-Host "> Aplicando a: $($dwg.Name)..." -ForegroundColor White
    
    $argList = "/i `"$($dwg.FullName)`" /s `"$scrPath`""
    $proc = Start-Process -FilePath $wrapperPath -ArgumentList $argList -Wait -NoNewWindow -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Host "  [ERROR] Proceso CAD falló para $($dwg.Name) con código $($proc.ExitCode)." -ForegroundColor Red
        $errores++
    }
}

if ($errores -gt 0) {
    Write-Host "`n[ERROR] Page Setup A1 terminó con $errores archivo(s) con error." -ForegroundColor Red
    exit 1
}

Write-Host "`n[OK] Tarea finalizada exitosamente." -ForegroundColor Green