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

function Get-SincalScriptLogDirectory {
    return Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'SINCAL\logs\scripts'
}

function Start-SincalScriptLog {
    param([string]$Name)
    $root = Get-SincalScriptLogDirectory
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    # Only our own logs; active processes and unrelated files are never removed.
    $logs = @(Get-ChildItem -LiteralPath $root -File | Where-Object {
        $_.Name -match '^SINCAL-\d{8}-\d{6}-\d+-[a-f0-9]{32}\.log$'
    } | Sort-Object LastWriteTime -Descending)
    $index = 0
    foreach ($log in $logs) {
        $ownerId = [int]($log.BaseName.Split('-')[3])
        if (Get-Process -Id $ownerId -ErrorAction SilentlyContinue) { continue }
        $index++
        if ($index -ge 100 -or $log.LastWriteTime -lt (Get-Date).AddDays(-30)) {
            Remove-Item -LiteralPath $log.FullName -Force -ErrorAction SilentlyContinue
        }
    }
    $script:SincalLogPath = Join-Path $root ('SINCAL-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + "-$PID-" + [guid]::NewGuid().ToString('N') + '.log')
    $script:SincalLogStart = Get-Date
    $script:SincalRawCharacters = 0
    $script:SincalLogTruncated = $false
    $script:SincalCompletedDrawings = 0
    $script:SincalFailedDrawings = 0
    Start-Transcript -LiteralPath $script:SincalLogPath -ErrorAction Stop | Out-Null
    Write-Host "Registro: $script:SincalLogPath"
    Write-Host "Script: $Name | Carpeta: $((Get-Location).Path)"
}

function Stop-SincalScriptLog {
    if ($script:SincalLogPath) {
        Write-Host "Resumen CAD: $script:SincalCompletedDrawings procesos terminados; $script:SincalFailedDrawings fallidos."
        Write-Host "Fin del lanzador. Duracion: $([math]::Round(((Get-Date) - $script:SincalLogStart).TotalSeconds, 2)) s. Consulte el resumen y los errores anteriores."
        Stop-Transcript | Out-Null
        Write-Host "Registro guardado: $script:SincalLogPath"
        $script:SincalLogPath = $null
    }
}

function Write-SincalCadOutput {
    param([string]$Text, [string]$Channel)
    # Keep draining both pipes after the log limit to avoid blocking CAD.
    if ($script:SincalRawCharacters -lt 5000000) {
        $remaining = 5000000 - $script:SincalRawCharacters
        if ($Text.Length -gt $remaining) { $Text = $Text.Substring(0, $remaining) }
        $script:SincalRawCharacters += $Text.Length + 1
        Write-Host "[$Channel] $Text"
    } elseif (-not $script:SincalLogTruncated) {
        $script:SincalLogTruncated = $true
        Write-Host '[AVISO] Salida CAD truncada a 5 millones de caracteres. Se conservan estados y errores del lanzador.'
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
    $source = [regex]::Replace(
        $source,
        '(?ims)\r?\n\s*_?\.?\s*(CLOSE|QUIT)\s*(?:\r?\n\s*_?[YN]\s*)?\z',
        ''
    )
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
    param($Engine, [string]$DrawingPath, [string]$ScriptPath, [int]$TimeoutSeconds = 900, [switch]$SkipSave)

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
        if (-not $SkipSave) { $document.Save() }
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

function Invoke-SincalCadScriptCore {
    [CmdletBinding()]
    param($Engine, [string]$DrawingPath, [string]$ScriptPath, [int]$TimeoutSeconds = 900, [switch]$SkipSave)
    if ($Engine.Mode -eq "ZWCAD_COM") {
        return Invoke-SincalZwcadScript -Engine $Engine -DrawingPath $DrawingPath -ScriptPath $ScriptPath -TimeoutSeconds $TimeoutSeconds -SkipSave:$SkipSave
    }
    $arguments = "/i `"$DrawingPath`" /s `"$ScriptPath`""
    # Windows PowerShell 5.1 puede devolver ExitCode=$null con Start-Process
    # -NoNewWindow -PassThru, aun si CAD termina bien. Process.Start conserva
    # el handle real y permite distinguir un error de CAD de una salida normal.
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo.FileName = $Engine.Path
    $process.StartInfo.Arguments = $arguments
    $process.StartInfo.WorkingDirectory = (Get-Location).Path
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    # Core Console writes redirected text as UTF-16LE, without a BOM.
    if ([IO.Path]::GetFileName($Engine.Path) -ieq 'accoreconsole.exe') {
        $process.StartInfo.StandardOutputEncoding = [Text.Encoding]::Unicode
        $process.StartInfo.StandardErrorEncoding = [Text.Encoding]::Unicode
    }
    try {
        if (-not $process.Start()) { throw "No se pudo iniciar AutoCAD Core Console." }
        $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
        $stdout = $process.StandardOutput.ReadLineAsync()
        $stderr = $process.StandardError.ReadLineAsync()
        while ($stdout -or $stderr -or -not $process.HasExited) {
            if ($stdout -and $stdout.IsCompleted) {
                $line = $stdout.GetAwaiter().GetResult()
                $stdout = $null
                if ($null -ne $line) {
                    Write-SincalCadOutput $line 'CAD'
                    $stdout = $process.StandardOutput.ReadLineAsync()
                }
            }
            if ($stderr -and $stderr.IsCompleted) {
                $line = $stderr.GetAwaiter().GetResult()
                $stderr = $null
                if ($null -ne $line) {
                    Write-SincalCadOutput $line 'CAD STDERR'
                    $stderr = $process.StandardError.ReadLineAsync()
                }
            }
            if ([DateTime]::UtcNow -ge $deadline) { break }
            if (($stdout -and -not $stdout.IsCompleted) -or ($stderr -and -not $stderr.IsCompleted)) {
                Start-Sleep -Milliseconds 10
            }
        }
        if (-not $process.HasExited) {
            # El PID pertenece exclusivamente al Core Console iniciado arriba.
            # Evita que un prompt inesperado bloquee todo el lote indefinidamente.
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            throw "AutoCAD Core Console no terminó antes de $TimeoutSeconds segundos. Se cerró sólo el proceso de este DWG; revisa si el SCR dejó una pregunta sin responder."
        }
        Write-Host "Codigo de salida CAD: $($process.ExitCode)"
        if ($process.ExitCode -ne 0) { throw "AutoCAD Core Console terminó con código $($process.ExitCode)." }
        return 0
    }
    finally {
        $process.Dispose()
    }
}

function Get-SincalDrawingLockFiles {
    param([string]$DrawingPath)
    $fullPath = [IO.Path]::GetFullPath($DrawingPath)
    return @([IO.Path]::ChangeExtension($fullPath, '.dwl'), [IO.Path]::ChangeExtension($fullPath, '.dwl2'))
}

function Remove-SincalResidualDrawingLocks {
    param([string]$DrawingPath, [string[]]$ExistingBefore = @())
    $drawing = $null
    try {
        $fullPath = [IO.Path]::GetFullPath($DrawingPath)
        $item = Get-Item -LiteralPath $fullPath -ErrorAction Stop
        if ($item.Extension -ine '.dwg' -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return }
        # Keep the DWG exclusively open throughout cleanup: another CAD cannot
        # acquire it between the availability check and deletion of its sidecars.
        $drawing = [IO.File]::Open($fullPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
        foreach ($lockPath in (Get-SincalDrawingLockFiles $fullPath)) {
            if ($lockPath -in $ExistingBefore -or -not (Test-Path -LiteralPath $lockPath -PathType Leaf)) { continue }
            $lockFile = Get-Item -LiteralPath $lockPath -Force -ErrorAction Stop
            if ($lockFile.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            try {
                Remove-Item -LiteralPath $lockPath -Force -ErrorAction Stop
                Write-Host "[LIMPIEZA] Residuo eliminado: $lockPath"
            } catch {
                Write-Host "[AVISO] Se conserva el residuo $lockPath : $($_.Exception.Message)"
            }
        }
    } catch {
        Write-Host "[AVISO] Sin limpieza DWL: el DWG no admite acceso exclusivo o no esta disponible. $DrawingPath"
    } finally {
        if ($drawing) { $drawing.Dispose() }
    }
}

function Invoke-SincalCadScript {
    [CmdletBinding()]
    param($Engine, [string]$DrawingPath, [string]$ScriptPath, [int]$TimeoutSeconds = 900, [switch]$SkipSave)
    $started = Get-Date
    $existingLocks = @(Get-SincalDrawingLockFiles $DrawingPath | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
    Write-Host "INICIO DWG: $DrawingPath"
    Write-Host "Motor: $($Engine.Path) | Version: $($Engine.Year) | Modo: $($Engine.Mode) | SCR: $ScriptPath"
    if ($Engine.Mode -eq 'ZWCAD_COM') {
        Write-Host 'ZWCAD: registro de automatizacion COM; no incluye la consola interna del dibujo.'
    }
    try {
        $result = Invoke-SincalCadScriptCore @PSBoundParameters
        # Only a successful, finished invocation may clean its new sidecars.
        # Pre-existing files are never claimed as belonging to this execution.
        Remove-SincalResidualDrawingLocks -DrawingPath $DrawingPath -ExistingBefore $existingLocks
        $script:SincalCompletedDrawings++
        Write-Host 'PROCESO TERMINADO: no certifica ausencia de corrupcion ni verifica todos los cambios del dibujo.'
        return $result
    } catch {
        $script:SincalFailedDrawings++
        Write-Host "FALLO DWG: $DrawingPath | $($_.Exception.Message)" -ForegroundColor Red
        throw
    } finally {
        Write-Host "FIN DWG: $DrawingPath | Duracion: $([math]::Round(((Get-Date) - $started).TotalSeconds, 2)) s"
    }
}
