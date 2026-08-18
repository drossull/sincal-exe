[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "SINCAL_ENGINE.ps1")

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

$appPath = if ($PSScriptRoot) { Split-Path $PSScriptRoot -Parent } else { (Get-Location).Path }
$scrPath = Join-Path $appPath "scripts\PUBLISH-A1.scr"

try {
    $enginePath = Get-SincalCadEngine
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $scrPath)) {
    Write-Host "[ERROR] Archivo PUBLISH-A1.scr no encontrado en la instalación de SINCAL." -ForegroundColor Red
    exit
}

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  CONFIGURACION DE PAGINA A1 + EXPORTACION A PDF" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

Write-Host "`nSe encontraron $($dwgFiles.Count) planos. Iniciando procesamiento unificado...`n" -ForegroundColor Green

$errores = 0

foreach ($file in $dwgFiles) {
    Write-Host "> Procesando y Exportando: $($file.Name)" -ForegroundColor White
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $statusPath = Join-Path $file.DirectoryName ($baseName + "__publish_status.txt")
    if (Test-Path $statusPath) {
        Remove-Item $statusPath -Force -ErrorAction SilentlyContinue
    }

    $argList = "/i `"$($file.FullName)`" /s `"$scrPath`""
    $proc = Start-Process -FilePath $enginePath -ArgumentList $argList -Wait -NoNewWindow -PassThru

    if ($proc.ExitCode -ne 0) {
        Write-Host "  [ERROR] El proceso CAD terminó con código $($proc.ExitCode)." -ForegroundColor Red
        $errores++
        continue
    }

    if (-not (Test-Path $statusPath)) {
        Write-Host "  [ERROR] No se generó archivo de estado de publicación." -ForegroundColor Red
        $errores++
        continue
    }

    $lineas = Get-Content $statusPath -ErrorAction SilentlyContinue
    $pdfs = @($lineas | Where-Object { $_ -like 'PDF|*' } | ForEach-Object { $_.Substring(4) })
    $erroresEstado = @($lineas | Where-Object { $_ -like 'ERROR|*' })

    foreach ($linea in $erroresEstado) {
        Write-Host "  [ERROR] $linea" -ForegroundColor Red
    }

    $faltantes = @()
    foreach ($pdf in $pdfs) {
        if (-not (Test-Path $pdf)) {
            $faltantes += $pdf
            continue
        }
        $item = Get-Item $pdf -ErrorAction SilentlyContinue
        if (-not $item -or $item.Length -le 0) {
            $faltantes += $pdf
        }
    }

    if ($erroresEstado.Count -gt 0 -or $faltantes.Count -gt 0 -or $pdfs.Count -eq 0) {
        if ($faltantes.Count -gt 0) {
            foreach ($pdf in $faltantes) {
                Write-Host "  [ERROR] PDF faltante o vacío: $pdf" -ForegroundColor Red
            }
        }
        if ($pdfs.Count -eq 0) {
            Write-Host "  [ERROR] No se generó ningún PDF para este DWG." -ForegroundColor Red
        }
        $errores++
    }
    else {
        Write-Host "  [OK] PDFs generados: $($pdfs.Count)" -ForegroundColor Green
    }

    Remove-Item $statusPath -Force -ErrorAction SilentlyContinue
}

if ($errores -gt 0) {
    Write-Host "`n[ERROR] La publicación terminó con $errores archivo(s) DWG con problemas." -ForegroundColor Red
    exit 1
}

Write-Host "`n[OK] Tarea finalizada exitosamente." -ForegroundColor Cyan
