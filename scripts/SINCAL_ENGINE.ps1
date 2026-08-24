function New-SincalCadEngineDescriptor {
    param([string]$Path, [string]$Product = "", [int]$Year = 0, [bool]$Headless = $false)
    $leaf = [IO.Path]::GetFileName($Path)
    if (-not $Product) {
        $Product = if ($leaf -ieq "zwcad.exe") { "ZWCAD" } else { "AutoCAD Core Console" }
    }
    if (-not $Year -and $Path -match '(?<!\d)(20\d{2})(?!\d)') { $Year = [int]$Matches[1] }
    [pscustomobject]@{
        Path = $Path
        Product = $Product
        Year = $Year
        Headless = $Headless
        Mode = if ($leaf -ieq "zwcad.exe") { "ZWCAD_COM" } else { "CORE_CONSOLE" }
    }
}

function Get-SincalCadEngine {
    [CmdletBinding()]
    param()

    if ($env:SINCAL_CAD_ENGINE -and (Test-Path -LiteralPath $env:SINCAL_CAD_ENGINE -PathType Leaf)) {
        $leaf = [IO.Path]::GetFileName($env:SINCAL_CAD_ENGINE)
        if ($leaf -ieq "accoreconsole.exe" -or $leaf -ieq "zwcad.exe") {
            return New-SincalCadEngineDescriptor -Path $env:SINCAL_CAD_ENGINE -Headless ($leaf -ieq "accoreconsole.exe")
        }
        throw "SINCAL_CAD_ENGINE debe apuntar a accoreconsole.exe o ZWCAD.exe."
    }

    $statePath = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "SINCAL\runtime\cad_engine.json"
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        try {
            $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($candidate in (@($state.selected) + @($state.candidates))) {
                $candidatePath = [string]$candidate.path
                $leaf = [IO.Path]::GetFileName($candidatePath)
                if (($leaf -ieq "accoreconsole.exe" -or $leaf -ieq "zwcad.exe") -and
                    $candidatePath -and (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
                    return New-SincalCadEngineDescriptor -Path $candidatePath `
                        -Product ([string]$candidate.product) -Year ([int]$candidate.year) `
                        -Headless ([bool]$candidate.headless)
                }
            }
        }
        catch {
            Write-Host "[ADVERTENCIA] No se pudo leer cad_engine.json: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
    throw "No se encontró un motor CAD compatible. Abre SINCAL > Diagnóstico, selecciona AutoCAD Core Console o ZWCAD y pulsa 'Usar este motor'."
}

function New-SincalZwcadScript {
    param([string]$SourcePath, [string]$MarkerPath, [string]$Token)
    $source = Get-Content -LiteralPath $SourcePath -Raw -Encoding Default
    # El controlador COM administra el cierre después de comprobar el resultado.
    $source = [regex]::Replace($source, '(?im)^\s*_?\.?\s*(CLOSE|QUIT)\s*$\r?\n?', '')
    $markerForLisp = $MarkerPath.Replace('\', '/').Replace('"', '\"')
    $completion = @"

(setq SINCAL_MARKER (open "$markerForLisp" "w"))
(if SINCAL_MARKER
  (progn
    (write-line "$Token" SINCAL_MARKER)
    (close SINCAL_MARKER)
  )
)
(princ)
"@
    $temporary = Join-Path ([IO.Path]::GetTempPath()) ("SINCAL-ZWCAD-" + [guid]::NewGuid().ToString("N") + ".scr")
    Set-Content -LiteralPath $temporary -Value ($source.TrimEnd() + $completion) -Encoding Ascii
    return $temporary
}

function Invoke-SincalZwcadScript {
    [CmdletBinding()]
    param($Engine, [string]$DrawingPath, [string]$ScriptPath, [int]$TimeoutSeconds = 900)

    if (@(Get-Process -Name ZWCAD -ErrorAction SilentlyContinue).Count -gt 0) {
        throw "Cierra ZWCAD antes de iniciar el procesamiento masivo. SINCAL usa una instancia invisible aislada para no interferir con dibujos abiertos."
    }

    $token = [guid]::NewGuid().ToString("N")
    $marker = Join-Path ([IO.Path]::GetTempPath()) ("SINCAL-ZWCAD-" + $token + ".done")
    $temporaryScript = New-SincalZwcadScript -SourcePath $ScriptPath -MarkerPath $marker -Token $token
    $application = $null
    $document = $null
    $completedSuccessfully = $false
    $createdProcessIds = @()
    try {
        $beforeProcessIds = @(Get-Process -Name ZWCAD -ErrorAction SilentlyContinue | ForEach-Object Id)
        $progIds = @()
        if ($Engine.Year) { $progIds += "ZWCAD.Application.$($Engine.Year)" }
        $progIds += "ZWCAD.Application"
        $lastError = $null
        foreach ($progId in ($progIds | Select-Object -Unique)) {
            try { $application = New-Object -ComObject $progId; break } catch { $lastError = $_ }
        }
        if (-not $application) {
            throw "No fue posible iniciar la automatización COM de ZWCAD. Verifica instalación y licencia. $($lastError.Exception.Message)"
        }
        $application.Visible = $false
        $createdProcessIds = @(Get-Process -Name ZWCAD -ErrorAction SilentlyContinue |
            Where-Object { $_.Id -notin $beforeProcessIds } | ForEach-Object Id)
        $document = $application.Documents.Open([IO.Path]::GetFullPath($DrawingPath), $false)
        try { $document.SetVariable("FILEDIA", 0) } catch {}
        try { $document.SetVariable("CMDDIA", 0) } catch {}
        $scriptForCommand = $temporaryScript.Replace('\', '/')
        # ZWCAD 2026 puede descartar la ruta si SCRIPT y su argumento se
        # entregan como dos entradas COM consecutivas. Una única expresión
        # AutoLISP permanece en la cola hasta que el documento está listo.
        $document.SendCommand("(command `"_.SCRIPT`" `"$scriptForCommand`")`n")

        $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
        $completed = $false
        while ([DateTime]::UtcNow -lt $deadline) {
            if (Test-Path -LiteralPath $marker -PathType Leaf) {
                $actual = (Get-Content -LiteralPath $marker -Raw -ErrorAction SilentlyContinue).Trim()
                if ($actual -eq $token) { $completed = $true; break }
            }
            Start-Sleep -Milliseconds 250
        }
        if (-not $completed) {
            throw "ZWCAD no confirmó el término antes de $TimeoutSeconds segundos. Puede existir un diálogo oculto, una licencia pendiente o un comando incompleto."
        }
        $document.Save()
        $document.Close($false)
        $document = $null
        $completedSuccessfully = $true
        return 0
    }
    finally {
        if ($completedSuccessfully -and $application) {
            try { $application.Quit() } catch {}
        }
        if ($document) { try { [Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) | Out-Null } catch {} }
        if ($application) { try { [Runtime.InteropServices.Marshal]::FinalReleaseComObject($application) | Out-Null } catch {} }
        foreach ($createdProcessId in $createdProcessIds) {
            if ($completedSuccessfully) {
                $exitDeadline = [DateTime]::UtcNow.AddSeconds(10)
                while ((Get-Process -Id $createdProcessId -ErrorAction SilentlyContinue) -and
                    [DateTime]::UtcNow -lt $exitDeadline) {
                    Start-Sleep -Milliseconds 200
                }
            }
            if (Get-Process -Id $createdProcessId -ErrorAction SilentlyContinue) {
                # Los PID se capturan después de comprobar que no había una sesión
                # previa: sólo se termina la instancia invisible creada por SINCAL.
                Stop-Process -Id $createdProcessId -Force -ErrorAction SilentlyContinue
            }
        }
        Remove-Item -LiteralPath $temporaryScript -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-SincalCadScript {
    [CmdletBinding()]
    param($Engine, [string]$DrawingPath, [string]$ScriptPath, [int]$TimeoutSeconds = 900)
    if ($Engine.Mode -eq "ZWCAD_COM") {
        return Invoke-SincalZwcadScript -Engine $Engine -DrawingPath $DrawingPath -ScriptPath $ScriptPath -TimeoutSeconds $TimeoutSeconds
    }
    $arguments = "/i `"$DrawingPath`" /s `"$ScriptPath`""
    $process = Start-Process -FilePath $Engine.Path -ArgumentList $arguments -Wait -NoNewWindow -PassThru
    if ($process.ExitCode -ne 0) { throw "AutoCAD Core Console terminó con código $($process.ExitCode)." }
    return 0
}
