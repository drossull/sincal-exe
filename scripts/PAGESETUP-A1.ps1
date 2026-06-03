$ErrorActionPreference = "Stop"
$appData = [Environment]::GetFolderPath('ApplicationData')
$wrapper = "$appData\Estandar SINCAL\scripts\cad_wrapper.bat"
$scrFile = "$PSScriptRoot\PAGESETUP-A1.scr"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  SINCAL - CONFIGURACION DE PAGINA A1" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Validar que el programa base SINCAL este instalado
if (-not (Test-Path $wrapper)) {
    Write-Host "`n[X] ERROR FATAL: No se encontro el puente de CAD (cad_wrapper.bat)." -ForegroundColor Red
    Write-Host "Por favor, abre SINCAL.exe y presiona 'Instalar / Actualizar Todo'." -ForegroundColor Yellow
    Pause
    exit
}

# 2. Buscar todos los archivos DWG en la carpeta actual (donde se abrio la consola)
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
    
    # Los argumentos /i y /s son vitales para que el cad_wrapper.bat los lea correctamente
    Start-Process -FilePath $wrapper -ArgumentList "/i", "`"$($dwg.FullName)`"", "/s", "`"$scrFile`"" -Wait -NoNewWindow
}

Write-Host "`n[OK] Tarea finalizada exitosamente." -ForegroundColor Green
Pause