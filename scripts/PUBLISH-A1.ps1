param([string]$DrawingListFile, [switch]$KeepSetup, [switch]$OverwritePdf)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'SINCAL_ENGINE.ps1')
. (Join-Path $PSScriptRoot 'SINCAL_SELECTION.ps1')
Start-SincalScriptLog 'PUBLISH-A1'
try {
    $dwgFiles = @(Get-SincalDrawingSelection $DrawingListFile)
    if (-not $dwgFiles.Count) { throw 'No hay archivos DWG.' }
    $engine = Get-SincalCadEngine
    $appPath = Split-Path $PSScriptRoot -Parent
    $template = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'PUBLISH-A1.scr') -Raw -Encoding UTF8
    $errors = 0
    foreach ($file in $dwgFiles) {
        $target = [IO.Path]::ChangeExtension($file.FullName, '.pdf')
        $temp = Join-Path ([IO.Path]::GetTempPath()) ('SINCAL-plot-' + [guid]::NewGuid().ToString('N'))
        try {
            if ((Test-Path -LiteralPath $target) -and -not $OverwritePdf) {
                throw "El PDF ya existe: $target. Usa -OverwritePdf para autorizar su reemplazo."
            }
            New-Item -ItemType Directory -Path $temp | Out-Null
            $out = ($temp.Replace('\','/') + '/').Replace('"','\"')
            $keep = if ($KeepSetup) { 'T' } else { 'nil' }
            $script = Join-Path $temp 'publish.scr'
            $source = '(setq sincalOutputDir "' + $out + '" sincalKeepSetup ' + $keep + ')' + [Environment]::NewLine + $template
            [IO.File]::WriteAllText($script, $source, (New-Object Text.UTF8Encoding($false)))
            Invoke-SincalCadScript -Engine $engine -DrawingPath $file.FullName -ScriptPath $script -SkipSave:$KeepSetup | Out-Null
            $status = @(Get-Content -LiteralPath (Join-Path $temp 'status.txt') -Encoding UTF8)
            $pages = @($status | Where-Object { $_ -like 'PDF|*' } | ForEach-Object { $_.Substring(4) })
            $completion = @($status | Where-Object { $_ -match '^OK\|[1-9][0-9]*$' })
            if (-not $pages.Count -or $completion.Count -ne 1 -or
                @($status | Where-Object { $_ -like 'ERROR|*' }).Count) { throw 'No se generaron todas las paginas PDF.' }
            if ([int]$completion[0].Substring(3) -ne $pages.Count -or
                @($pages | Select-Object -Unique).Count -ne $pages.Count) { throw 'La cantidad de paginas PDF no coincide con los layouts publicados.' }
            foreach ($page in $pages) {
                if (-not (Test-Path -LiteralPath $page) -or (Get-Item -LiteralPath $page).Length -eq 0) { throw 'Pagina PDF ausente o vacia.' }
            }
            $request = Join-Path $temp 'merge.json'
            $pdfClock = [Diagnostics.Stopwatch]::StartNew()
            @{target=$target;pages=$pages;overwrite=[bool]$OverwritePdf} | ConvertTo-Json | Set-Content -LiteralPath $request -Encoding UTF8
            $exe = Join-Path $appPath 'SINCAL.exe'
            if (-not (Test-Path -LiteralPath $exe) -and -not (Test-Path -LiteralPath (Join-Path $appPath 'desktop_main.py'))) {
                $installed = Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SINCAL Suite_is1' -ErrorAction Stop
                $exe = Join-Path $installed.InstallLocation 'SINCAL.exe'
                if ([version]$installed.DisplayVersion -lt [version]'3.0.4') { throw 'Actualiza SINCAL a la version con ensamblado PDF (3.0.4 o posterior).' }
            }
            if (Test-Path -LiteralPath $exe) {
                $process = Start-Process -FilePath $exe -ArgumentList @('--merge-pdfs', ('"' + $request + '"')) -WindowStyle Hidden -PassThru -Wait
                $mergeExit = $process.ExitCode
            } else {
                & python (Join-Path $appPath 'desktop_main.py') --merge-pdfs $request
                $mergeExit = $LASTEXITCODE
            }
            $resultPath = [IO.Path]::ChangeExtension($request, '.result.json')
            if (-not (Test-Path -LiteralPath $resultPath)) { throw 'El ensamblador no confirmo la validacion PDF. Actualiza la aplicacion junto con los scripts.' }
            $mergeResult = Get-Content -LiteralPath $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($mergeExit -ne 0 -or $mergeResult.ok -ne $true) { throw "PDF no publicado: $($mergeResult.error)" }
            $pdfClock.Stop()
            Write-Host "Validacion/publicacion PDF: $([math]::Round($pdfClock.Elapsed.TotalSeconds, 2)) s | Archivos de entrada: $($pages.Count)"
            Write-Host "[OK] PDF: $target"
        } catch {
            $errors++
            Write-Host "[ERROR] $($file.Name): $($_.Exception.Message)"
        } finally {
            $resolvedTemp = [IO.Path]::GetFullPath($temp)
            $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
            if ($resolvedTemp.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($resolvedTemp) -match '^SINCAL-plot-[a-f0-9]{32}$') {
                Remove-Item -LiteralPath $resolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
    if ($errors) { throw "Publicacion finalizada con $errors errores." }
} finally {
    Stop-SincalScriptLog
}
