# Content receipts are saved only after successful builds and signing.
function New-ComponentReceipt([string]$Name, [string[]]$Inputs, [string[]]$Outputs, [string]$Context) {
    $cacheTool = Join-Path $projectRoot 'tools\build_cache.py'
    $arguments = @($cacheTool, 'key', '--context', $Context, '--input', $cacheTool,
        '--input', (Join-Path $projectRoot 'tools\build_components.ps1'),
        '--input', (Join-Path $projectRoot 'tools\build_release.ps1'))
    foreach ($inputPath in $Inputs) { $arguments += @('--input', $inputPath) }
    # Shared MSBuild settings affect all native projects, when present.
    foreach ($settings in @('Directory.Build.*', 'Directory.Packages.props', 'global.json', 'NuGet.Config')) {
        Get-ChildItem -Path (Join-Path $projectRoot $settings) -File -ErrorAction SilentlyContinue | ForEach-Object {
            $arguments += @('--input', $_.FullName)
        }
    }
    $key = & python @arguments
    if ($LASTEXITCODE -ne 0) { throw "No se pudo calcular la huella de $Name." }
    return [pscustomobject]@{
        Name = $Name; Key = [string]$key; Outputs = $Outputs
        Receipt = Join-Path $projectRoot "build\component-cache\$Name.json"
    }
}

function Test-ComponentReceipt($Component) {
    if ($CleanBuild) { return $false }
    $arguments = @((Join-Path $projectRoot 'tools\build_cache.py'), 'check', '--key', $Component.Key,
        '--receipt', $Component.Receipt)
    foreach ($outputPath in $Component.Outputs) { $arguments += @('--output', $outputPath) }
    & python @arguments
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Reutilizando $($Component.Name): fuentes y archivos verificados." -ForegroundColor DarkCyan
        return $true
    }
    return $false
}

function Save-ComponentReceipt($Component) {
    $arguments = @((Join-Path $projectRoot 'tools\build_cache.py'), 'record', '--key', $Component.Key,
        '--receipt', $Component.Receipt)
    foreach ($outputPath in $Component.Outputs) { $arguments += @('--output', $outputPath) }
    & python @arguments
    if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar $($Component.Name)." }
}

function Get-CadSdkInputs([int]$Year, [string]$AutoCAD2025SdkDir = '') {
    $folder = if ($Year -eq 2025 -and $AutoCAD2025SdkDir) { $AutoCAD2025SdkDir } else { Join-Path $env:ProgramFiles "Autodesk\AutoCAD $Year" }
    return @('acdbmgd.dll', 'accoremgd.dll', 'acmgd.dll', 'AcWindows.dll', 'AdWindows.dll') |
        ForEach-Object { Join-Path $folder $_ }
}
