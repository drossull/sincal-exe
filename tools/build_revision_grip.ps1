param(
    [string[]]$AutoCADDirectories = @(),
    [string[]]$ZWCADDirectories = @(),
    [switch]$InstallForCurrentUser
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $projectRoot 'src\Sincal.RevisionGrip\Sincal.RevisionGrip.csproj'
$distribution = Join-Path $projectRoot 'src\Sincal.RevisionGrip\bin\distribution'
New-Item -ItemType Directory -Path $distribution -Force | Out-Null

if ($AutoCADDirectories.Count -eq 0) {
    $AutoCADDirectories = @(Get-ChildItem -LiteralPath (Join-Path $env:ProgramFiles 'Autodesk') -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^AutoCAD 20\d{2}$' -and (Test-Path -LiteralPath (Join-Path $_.FullName 'acmgd.dll')) } |
        Select-Object -ExpandProperty FullName)
}
if ($ZWCADDirectories.Count -eq 0) {
    $ZWCADDirectories = @(Get-ChildItem -LiteralPath (Join-Path $env:ProgramFiles 'ZWSOFT') -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^ZWCAD 20\d{2}$' -and (Test-Path -LiteralPath (Join-Path $_.FullName 'ZwManaged.dll')) } |
        Select-Object -ExpandProperty FullName)
}
if ($AutoCADDirectories.Count -eq 0 -or $ZWCADDirectories.Count -eq 0) {
    throw 'Se necesitan SDK instalados de AutoCAD y ZWCAD para compilar ambos complementos.'
}

$built = @()
foreach ($platform in @('AutoCAD', 'ZWCAD')) {
    $directories = if ($platform -eq 'AutoCAD') { $AutoCADDirectories } else { $ZWCADDirectories }
    foreach ($directory in $directories) {
        $directory = (Resolve-Path -LiteralPath $directory).Path
        if ($platform -eq 'AutoCAD') {
            $version = (Get-Item -LiteralPath (Join-Path $directory 'acad.exe')).VersionInfo.ProductVersion
            if ($version -notmatch '^R(\d+\.\d+)') { throw "Version de AutoCAD no reconocida: $version" }
            $release = "R$($Matches[1])"
            $runtimePath = Join-Path $directory 'acdbmgd.runtimeconfig.json'
            if (-not (Test-Path -LiteralPath $runtimePath)) { throw "Falta runtimeconfig para $directory" }
            $runtime = (Get-Content -LiteralPath $runtimePath -Raw | ConvertFrom-Json).runtimeOptions.tfm
            if ($runtime -notmatch '^net\d+\.0$') { throw "Runtime no compatible: $runtime" }
            $framework = "$runtime-windows"
        } else {
            $version = (Get-Item -LiteralPath (Join-Path $directory 'zwcad.exe')).VersionInfo.FileMajorPart
            if ($version -lt 25 -or $version -gt 99) { throw "Version de ZWCAD no reconocida: $version" }
            $release = [string](2000 + $version)
            $framework = 'net48'
        }
        $output = Join-Path $projectRoot "src\Sincal.RevisionGrip\bin\$platform-$release"
        & dotnet build $project -c Release "-p:CadPlatform=$platform" "-p:CadDir=$directory" "-p:CadTargetFramework=$framework" -o $output --nologo
        if ($LASTEXITCODE -ne 0) { throw "Fallo la compilacion para $platform $release." }
        $source = Join-Path $output "Sincal.RevisionGrip.$platform.dll"
        $target = Join-Path $distribution "Sincal.RevisionGrip.$platform.$release.dll"
        Copy-Item -LiteralPath $source -Destination $target -Force
        $built += $target
    }
}

if ($InstallForCurrentUser) {
    $cadRoot = Join-Path $env:APPDATA 'Estandar SINCAL'
    New-Item -ItemType Directory -Path $cadRoot -Force | Out-Null
    foreach ($binary in $built) { Copy-Item -LiteralPath $binary -Destination $cadRoot -Force }
    $lispRoot = Join-Path $cadRoot 'lisps'
    New-Item -ItemType Directory -Path $lispRoot -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot 'lisps\REV-EDIT.lsp') -Destination $lispRoot -Force
    $startupRoot = Join-Path $cadRoot 'startup'
    New-Item -ItemType Directory -Path $startupRoot -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot 'startup\SINCAL_STARTUP.lsp') -Destination $startupRoot -Force
    Write-Host 'Editor instalado. Carga REV-EDIT.lsp en los dibujos abiertos; al reiniciar CAD se carga mediante el startup de SINCAL.'
}
$built | ForEach-Object { Write-Host $_ }
