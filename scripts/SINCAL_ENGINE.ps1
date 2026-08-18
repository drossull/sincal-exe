function Get-SincalCadEngine {
    [CmdletBinding()]
    param()

    if ($env:SINCAL_CAD_ENGINE -and (Test-Path -LiteralPath $env:SINCAL_CAD_ENGINE -PathType Leaf)) {
        return $env:SINCAL_CAD_ENGINE
    }

    $runtimePath = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "SINCAL\runtime"
    $statePath = Join-Path $runtimePath "cad_engine.json"
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        try {
            $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
            $selected = [string]$state.selected.path
            if ($selected -and (Test-Path -LiteralPath $selected -PathType Leaf)) {
                return $selected
            }
        }
        catch {
            Write-Host "[ADVERTENCIA] No se pudo leer cad_engine.json: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    $legacyWrapper = Join-Path $runtimePath "cad_wrapper.bat"
    if (Test-Path -LiteralPath $legacyWrapper -PathType Leaf) {
        return $legacyWrapper
    }

    throw "No hay un motor CAD configurado. Abre SINCAL, entra a Diagnóstico y soporte y selecciona un motor."
}
