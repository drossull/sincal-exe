[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "SINCAL_ENGINE.ps1")

$dwgFiles = Get-ChildItem -Path .\ -Filter *.dwg
if ($dwgFiles.Count -eq 0) {
    Write-Host "[ERROR] No hay archivos DWG en esta carpeta." -ForegroundColor Yellow
    exit
}

try {
    $engine = Get-SincalCadEngine
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    LIMPIEZA PROFUNDA (PURGE ALL + AUDIT)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$errores = 0

$scriptPath = Join-Path ([IO.Path]::GetTempPath()) ("SINCAL-PURGE-" + [guid]::NewGuid().ToString("N") + ".scr")

# Construcción de comandos (Los saltos de línea son obligatorios para CAD)
$scrContent = @"
_.AUDIT
_Y
_.-PURGE
_A
*
_N
_.-PURGE
_R
*
_N
_.-SCALELISTEDIT
_Delete
*
_Exit
_.ZOOM
_E
_.QSAVE
_.QUIT
_Y

"@

# Una respuesta por linea: los nombres de escala admiten espacios y CAD
# interpretaria '* _Exit' como un solo nombre, dejando abierto el comando.
try {
    # Guardado estricto en ASCII para evitar el BOM que rompe accoreconsole.
    Set-Content -LiteralPath $scriptPath -Value $scrContent -Encoding Ascii

    foreach ($file in $dwgFiles) {
        Write-Host "Limpiando: $($file.Name)" -ForegroundColor Green
    
        try {
            Invoke-SincalCadScript -Engine $engine -DrawingPath $file.FullName -ScriptPath $scriptPath | Out-Null
        }
        catch {
            Write-Host "  [ERROR] Proceso CAD falló para $($file.Name): $($_.Exception.Message)" -ForegroundColor Red
            $errores++
        }
    }
}
finally {
    Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue
}

Write-Host "`n===================================================" -ForegroundColor Cyan
if ($errores -gt 0) {
    Write-Host "Proceso terminado con $errores archivo(s) con error." -ForegroundColor Red
    Write-Host "===================================================" -ForegroundColor Cyan
    exit 1
}

Write-Host "Proceso finalizado con éxito." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
