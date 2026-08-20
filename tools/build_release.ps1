[CmdletBinding()]
param(
    [string]$CertificateSubject = 'Gonzalo Mardones',
    [string]$CertificateThumbprint = '',
    [string]$InnoSetupPath = '',
    [switch]$SkipSigning
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Get-ProjectRoot {
    return (Split-Path -Parent $PSScriptRoot)
}

function Read-Version([string]$ProjectRoot) {
    $versionJson = Join-Path $ProjectRoot 'version.json'
    $data = Get-Content $versionJson -Raw | ConvertFrom-Json
    return [string]$data.version
}

function Assert-VersionConsistency([string]$ProjectRoot, [string]$Version) {
    $installer = Get-Content (Join-Path $ProjectRoot 'SINCAL_Installer.iss') -Raw
    $normalizedVersion = $Version.TrimStart('v', 'V')
    if ($Version -notmatch '^v\d+\.\d+\.\d+$') {
        throw "La versión '$Version' no cumple el formato vMAJOR.MINOR.PATCH."
    }
    if ($installer -notmatch '#error AppVersion must be supplied by the build script\.') {
        throw 'SINCAL_Installer.iss no está parametrizado para AppVersion.'
    }
    if ($installer -notmatch '#error AppVersionTag must be supplied by the build script\.') {
        throw 'SINCAL_Installer.iss no está parametrizado para AppVersionTag.'
    }
    foreach ($define in @(
        'AppPayloadUrl', 'AppPayloadHash', 'AppPayloadSize',
        'PluginPayloadUrl', 'PluginPayloadHash', 'PluginPayloadSize'
    )) {
        if ($installer -notmatch ("#error " + [regex]::Escape($define) + " must be supplied by the build script\.")) {
            throw "SINCAL_Installer.iss no está parametrizado para $define."
        }
    }

    $bundle = Get-Content (Join-Path $ProjectRoot 'cad-packages\Autodesk\SINCAL.bundle\PackageContents.xml') -Raw
    if ($bundle -notmatch ('AppVersion="' + [regex]::Escape($normalizedVersion) + '"')) {
        throw "PackageContents.xml no coincide con la versión $normalizedVersion."
    }

    $plugin = Get-Content (Join-Path $ProjectRoot 'src\Sincal.AutoCAD2025\PluginEntry.cs') -Raw
    if ($plugin -notmatch ('release ' + [regex]::Escape($normalizedVersion))) {
        throw "PluginEntry.cs no muestra la versión técnica $normalizedVersion."
    }

    $updateConfig = Get-Content (Join-Path $ProjectRoot 'sincal_update_config.py') -Raw
    if ($updateConfig -notmatch 'DISTRIBUTION_REPOSITORY\s*=\s*"sincal-updates"') {
        throw 'El canal público no apunta a drossull/sincal-updates.'
    }
}

function Invoke-PythonCompile([string]$ProjectRoot) {
    $pythonFiles = @(
        'main.py',
        'core_sincal.py',
        'sincal_ui.py',
        'sincal_runtime.py',
        'sincal_resource_sync.py',
        'sincal_cad_integration.py',
        'sincal_cad_engine.py',
        'sincal_diagnostics.py',
        'sincal_update_config.py',
        'tools\export_distribution.py',
        'modulos\tab_armaduras.py',
        'modulos\tab_docs.py',
        'modulos\tab_diagnostico.py',
        'modulos\tab_ubicacion.py',
        'tests\selfcheck_runtime.py'
    ) | ForEach-Object { Join-Path $ProjectRoot $_ }

    & python -m py_compile @pythonFiles
    if ($LASTEXITCODE -ne 0) {
        throw 'Falló py_compile.'
    }
}

function Invoke-PowerShellParse([string]$ProjectRoot) {
    $errors = @()
    foreach ($folder in @('scripts', 'tools')) {
        Get-ChildItem (Join-Path $ProjectRoot $folder) -Filter *.ps1 -ErrorAction SilentlyContinue | ForEach-Object {
            $tokens = $null
            $parseErrors = $null
            [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$parseErrors) | Out-Null
            if ($parseErrors) {
                $errors += $parseErrors
            }
        }
    }
    if ($errors.Count -gt 0) {
        $errors | ForEach-Object { Write-Error $_ }
        throw 'Falló el parseo de scripts PowerShell.'
    }
}

function Invoke-SelfCheck([string]$ProjectRoot) {
    Push-Location $ProjectRoot
    try {
        & python 'tests\selfcheck_runtime.py'
        if ($LASTEXITCODE -ne 0) {
            throw 'Falló selfcheck_runtime.py.'
        }
        & python -m unittest discover -s tests -p 'test_*.py'
        if ($LASTEXITCODE -ne 0) {
            throw 'Fallaron las pruebas unitarias.'
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-AutoCAD2025PluginBuild([string]$ProjectRoot) {
    $project = Join-Path $ProjectRoot 'src\Sincal.AutoCAD2025\Sincal.AutoCAD2025.csproj'
    $buildOutput = Join-Path $ProjectRoot 'src\Sincal.AutoCAD2025\bin\Release\net8.0-windows\Sincal.AutoCAD2025.dll'
    $bundleDir = Join-Path $ProjectRoot 'cad-packages\Autodesk\SINCAL.bundle\Contents\AutoCAD2025'
    $bundleDll = Join-Path $bundleDir 'Sincal.AutoCAD2025.dll'
    $bundleManifest = Join-Path $ProjectRoot 'cad-packages\Autodesk\SINCAL.bundle\PackageContents.xml'

    if (-not (Test-Path $bundleManifest)) {
        throw "No existe el manifiesto del bundle: $bundleManifest"
    }

    & dotnet build $project -c Release
    if ($LASTEXITCODE -ne 0) {
        throw 'Falló la compilación del plugin AutoCAD 2025.'
    }
    if (-not (Test-Path $buildOutput)) {
        throw "No se generó la DLL del plugin: $buildOutput"
    }

    New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null
    Copy-Item $buildOutput $bundleDll -Force
    if (-not (Test-Path $bundleDll)) {
        throw "No se ensambló la DLL en el bundle: $bundleDll"
    }
}

function Get-SigningCertificate([string]$Subject, [string]$Thumbprint) {
    $certs = Get-ChildItem Cert:\CurrentUser\My |
        Where-Object {
            $_.HasPrivateKey -and
            $_.NotAfter -gt (Get-Date) -and
            (
                ($Thumbprint -and $_.Thumbprint -eq $Thumbprint) -or
                ((-not $Thumbprint) -and $_.Subject -match $Subject)
            )
        } |
        Sort-Object NotAfter -Descending

    if (-not $certs) {
        if ($Thumbprint) {
            throw "No se encontró un certificado válido con thumbprint '$Thumbprint'."
        }
        throw "No se encontró un certificado válido para '$Subject'."
    }

    return $certs | Select-Object -First 1
}

function Sign-File([string]$Path, $Certificate, [int]$MaxAttempts = 3) {
    $lastError = $null

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        Start-Sleep -Seconds 2
        try {
            $result = Set-AuthenticodeSignature -FilePath $Path -Certificate $Certificate -TimestampServer 'http://timestamp.digicert.com'
            $actual = Get-AuthenticodeSignature $Path

            Write-Host ("Intento de firma {0}/{1}: Result={2} / Actual={3} / Timestamp={4}" -f $attempt, $MaxAttempts, $result.Status, $actual.Status, ($null -ne $actual.TimeStamperCertificate)) -ForegroundColor DarkGray

            if (($actual.Status -eq 'Valid') -and ($null -ne $actual.TimeStamperCertificate)) {
                return $actual
            }

            $lastError = "Result=$($result.Status) Message=$($result.StatusMessage) Actual=$($actual.Status) Timestamp=$($null -ne $actual.TimeStamperCertificate)"
        }
        catch {
            $lastError = $_.Exception.Message
        }

        if ($attempt -lt $MaxAttempts) {
            Write-Host "Reintentando firma de '$Path'..." -ForegroundColor Yellow
            Start-Sleep -Seconds 3
        }
    }

    throw "La firma de '$Path' no quedó válida tras $MaxAttempts intentos. Detalle: $lastError"
}

function Resolve-InnoSetupPath([string]$Provided) {
    if ($Provided) {
        if (-not (Test-Path $Provided)) {
            throw "No existe ISCC en '$Provided'."
        }
        return $Provided
    }

    $candidates = @(
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw 'No se encontró Inno Setup (ISCC.exe).'
}

function Remove-ArtifactIfExists([string]$Path) {
    if (-not (Test-Path $Path)) {
        return
    }

    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            Remove-Item $Path -Force -Recurse -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -eq 5) {
                throw "No se pudo eliminar '$Path'. Asegúrate de que no esté en uso y vuelve a intentarlo. Detalle: $($_.Exception.Message)"
            }
            Start-Sleep -Seconds 2
        }
    }
}

function Assert-ArtifactExists([string]$Path) {
    if (-not (Test-Path $Path)) {
        throw "No se generó el artefacto esperado: $Path"
    }
}

function Assert-AppPayloadContents([string]$Path) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $entries = @($archive.Entries | ForEach-Object { $_.FullName.Replace('\', '/') })
        $required = @(
            'SINCAL.exe',
            'version.json',
            'tutoriales.json',
            'lisps/SINCAL.lsp',
            'startup/SINCAL_STARTUP.lsp',
            'scripts/AUDIT.ps1',
            'scripts/SINCAL_ENGINE.ps1',
            'plotstyles/SINCAL_A1 (2025).ctb',
            'masters/FORMATOS ANOTATIVOS ACAD_2025.dwg',
            'mapas/mapas_calibrados.json',
            'mapas/ayuda_travesano.png',
            'assets/fonts/RobotoMono.ttf'
        )
        $missing = @($required | Where-Object { $_ -notin $entries })
        if ($missing.Count -gt 0) {
            throw "El paquete de aplicación no contiene recursos esenciales: $($missing -join ', ')"
        }

        $regionalMaps = @($entries | Where-Object { $_ -match '^mapas/Region_.*\.png$' })
        if ($regionalMaps.Count -gt 0) {
            throw "El paquete de aplicación contiene mapas regionales que deben quedar bajo demanda: $($regionalMaps -join ', ')"
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Write-Checksums([string]$ProjectRoot, [string[]]$Paths) {
    $outputPath = Join-Path $ProjectRoot 'installer_output\SHA256SUMS.txt'
    $lines = foreach ($path in $Paths) {
        $hash = (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash *$([IO.Path]::GetFileName($path))"
    }
    Set-Content -Path $outputPath -Value $lines -Encoding UTF8
    return $outputPath
}

function New-ReleasePayloads(
    [string]$ProjectRoot,
    [string]$Version,
    [string]$DistExe,
    [string]$AppPayload,
    [string]$PluginPayload,
    [string]$StageRoot
) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $appStage = Join-Path $StageRoot 'app'
    $pluginStage = Join-Path $StageRoot 'plugin'
    New-Item -ItemType Directory -Force -Path $appStage, $pluginStage | Out-Null

    foreach ($relative in @('logo.ico', 'version.json', 'README.md', 'tutoriales.json')) {
        Copy-Item (Join-Path $ProjectRoot $relative) (Join-Path $appStage $relative) -Force
    }
    Copy-Item $DistExe (Join-Path $appStage 'SINCAL.exe') -Force
    $fontStage = Join-Path $appStage 'assets\fonts'
    New-Item -ItemType Directory -Force -Path $fontStage | Out-Null
    foreach ($relative in @('RobotoMono.ttf', 'OFL-RobotoMono.txt', 'README.md')) {
        Copy-Item (Join-Path $ProjectRoot "assets\fonts\$relative") (Join-Path $fontStage $relative) -Force
    }

    # La primera apertura debe ser funcional incluso antes de crear el estado de
    # sincronización. Se incluyen sólo los recursos esenciales y livianos; cada
    # mapa regional continúa descargándose bajo demanda desde el canal público.
    $coreResourcePolicies = @(
        [pscustomobject]@{ Directory = 'lisps'; Extensions = @('.lsp') },
        [pscustomobject]@{ Directory = 'startup'; Extensions = @('.lsp') },
        [pscustomobject]@{ Directory = 'scripts'; Extensions = @('.bat', '.ps1', '.scr') },
        [pscustomobject]@{ Directory = 'plotstyles'; Extensions = @('.ctb') },
        [pscustomobject]@{ Directory = 'masters'; Extensions = @('.dwg') }
    )
    foreach ($policy in $coreResourcePolicies) {
        $sourceDirectory = Join-Path $ProjectRoot $policy.Directory
        Get-ChildItem $sourceDirectory -Recurse -File | Where-Object {
            $_.Extension.ToLowerInvariant() -in $policy.Extensions
        } | ForEach-Object {
            $relative = [IO.Path]::GetRelativePath($ProjectRoot, $_.FullName)
            $destination = Join-Path $appStage $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            Copy-Item $_.FullName $destination -Force
        }
    }
    foreach ($relative in @('mapas\mapas_calibrados.json', 'mapas\ayuda_travesano.png')) {
        $destination = Join-Path $appStage $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item (Join-Path $ProjectRoot $relative) $destination -Force
    }

    $bundleSource = Join-Path $ProjectRoot 'cad-packages\Autodesk\SINCAL.bundle'
    Copy-Item (Join-Path $bundleSource '*') $pluginStage -Recurse -Force

    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $appStage,
        $AppPayload,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $pluginStage,
        $PluginPayload,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )

    return [pscustomobject]@{
        AppHash = (Get-FileHash $AppPayload -Algorithm SHA256).Hash.ToLowerInvariant()
        AppInstalledBytes = [int64](Get-ChildItem $appStage -Recurse -File | Measure-Object Length -Sum).Sum
        PluginHash = (Get-FileHash $PluginPayload -Algorithm SHA256).Hash.ToLowerInvariant()
        PluginInstalledBytes = [int64](Get-ChildItem $pluginStage -Recurse -File | Measure-Object Length -Sum).Sum
    }
}

function Write-ReleaseManifest(
    [string]$Path,
    [string]$Version,
    [string]$Installer,
    [string]$AppPayload,
    [string]$PluginPayload,
    [string]$AppUrl,
    [string]$PluginUrl
) {
    $manifest = [ordered]@{
        schema = 1
        product = 'SINCAL 2.0'
        release = $Version
        assets = [ordered]@{
            installer = [ordered]@{
                name = [IO.Path]::GetFileName($Installer)
                bytes = (Get-Item $Installer).Length
                sha256 = (Get-FileHash $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
            }
            application = [ordered]@{
                name = [IO.Path]::GetFileName($AppPayload)
                url = $AppUrl
                bytes = (Get-Item $AppPayload).Length
                sha256 = (Get-FileHash $AppPayload -Algorithm SHA256).Hash.ToLowerInvariant()
            }
            autocad_plugin = [ordered]@{
                name = [IO.Path]::GetFileName($PluginPayload)
                url = $PluginUrl
                bytes = (Get-Item $PluginPayload).Length
                sha256 = (Get-FileHash $PluginPayload -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        }
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $Path -Encoding UTF8
    return $Path
}

$projectRoot = Get-ProjectRoot
$version = Read-Version $projectRoot
$distExe = Join-Path $projectRoot 'dist\SINCAL.exe'
$pluginDll = Join-Path $projectRoot 'cad-packages\Autodesk\SINCAL.bundle\Contents\AutoCAD2025\Sincal.AutoCAD2025.dll'
$installerExe = Join-Path $projectRoot ("installer_output\Setup_SINCAL_{0}.exe" -f $version)
$appPayload = Join-Path $projectRoot ("installer_output\SINCAL_App_{0}.zip" -f $version)
$pluginPayload = Join-Path $projectRoot ("installer_output\SINCAL_AutoCAD_{0}.zip" -f $version)
$releaseManifest = Join-Path $projectRoot ("installer_output\release-manifest_{0}.json" -f $version)
$payloadStage = Join-Path $projectRoot 'payload_stage'

Write-Step "Validando versión"
Assert-VersionConsistency -ProjectRoot $projectRoot -Version $version

Write-Step "Validando código"
Invoke-PythonCompile -ProjectRoot $projectRoot
Invoke-PowerShellParse -ProjectRoot $projectRoot
Invoke-SelfCheck -ProjectRoot $projectRoot

Write-Step "Compilando plugin AutoCAD 2025"
Invoke-AutoCAD2025PluginBuild -ProjectRoot $projectRoot

Write-Step "Limpiando artefactos previos"
Remove-ArtifactIfExists (Join-Path $projectRoot 'build')
Remove-ArtifactIfExists $distExe
Remove-ArtifactIfExists $installerExe
Remove-ArtifactIfExists $appPayload
Remove-ArtifactIfExists $pluginPayload
Remove-ArtifactIfExists $releaseManifest
Remove-ArtifactIfExists $payloadStage
Remove-ArtifactIfExists (Join-Path $projectRoot 'installer_output\SHA256SUMS.txt')

Write-Step "Compilando ejecutable"
Push-Location $projectRoot
try {
    & python -m PyInstaller --noconfirm 'SINCAL.spec'
    if ($LASTEXITCODE -ne 0) {
        throw 'PyInstaller terminó con error.'
    }
}
finally {
    Pop-Location
}
Assert-ArtifactExists $distExe

$certificate = $null
if (-not $SkipSigning) {
    Write-Step "Buscando certificado de firma"
    $certificate = Get-SigningCertificate -Subject $CertificateSubject -Thumbprint $CertificateThumbprint
    Write-Host ("Certificado seleccionado: {0} | {1} | Expira: {2}" -f $certificate.Subject, $certificate.Thumbprint, $certificate.NotAfter) -ForegroundColor DarkCyan

    Write-Step "Firmando ejecutable"
    Sign-File -Path $distExe -Certificate $certificate

    Write-Step "Firmando plugin AutoCAD 2025"
    Sign-File -Path $pluginDll -Certificate $certificate
}

Write-Step "Creando paquetes remotos"
$payloadInfo = New-ReleasePayloads `
    -ProjectRoot $projectRoot `
    -Version $version `
    -DistExe $distExe `
    -AppPayload $appPayload `
    -PluginPayload $pluginPayload `
    -StageRoot $payloadStage
Assert-AppPayloadContents -Path $appPayload
Remove-ArtifactIfExists $payloadStage
$releaseBaseUrl = "https://github.com/drossull/sincal-updates/releases/download/$version"
$appPayloadUrl = "$releaseBaseUrl/$([IO.Path]::GetFileName($appPayload))"
$pluginPayloadUrl = "$releaseBaseUrl/$([IO.Path]::GetFileName($pluginPayload))"

Write-Step "Compilando instalador"
$iscc = Resolve-InnoSetupPath -Provided $InnoSetupPath
$normalizedVersion = $version.TrimStart('v', 'V')
Push-Location $projectRoot
try {
    & $iscc `
        "/DAppVersion=$normalizedVersion" `
        "/DAppVersionTag=$version" `
        "/DAppPayloadUrl=$appPayloadUrl" `
        "/DAppPayloadHash=$($payloadInfo.AppHash)" `
        "/DAppPayloadSize=$($payloadInfo.AppInstalledBytes)" `
        "/DPluginPayloadUrl=$pluginPayloadUrl" `
        "/DPluginPayloadHash=$($payloadInfo.PluginHash)" `
        "/DPluginPayloadSize=$($payloadInfo.PluginInstalledBytes)" `
        'SINCAL_Installer.iss'
    if ($LASTEXITCODE -ne 0) {
        throw 'ISCC terminó con error.'
    }
}
finally {
    Pop-Location
}
Assert-ArtifactExists $installerExe

if (-not $SkipSigning) {
    Write-Step "Firmando instalador"
    Sign-File -Path $installerExe -Certificate $certificate
}

Write-Step "Generando manifiesto de release"
Write-ReleaseManifest `
    -Path $releaseManifest `
    -Version $version `
    -Installer $installerExe `
    -AppPayload $appPayload `
    -PluginPayload $pluginPayload `
    -AppUrl $appPayloadUrl `
    -PluginUrl $pluginPayloadUrl | Out-Null

Write-Step "Generando checksums"
$checksumFile = Write-Checksums -ProjectRoot $projectRoot -Paths @(
    $installerExe,
    $appPayload,
    $pluginPayload,
    $releaseManifest
)

Write-Step "Resumen"
Get-Item $distExe, $pluginDll, $installerExe, $appPayload, $pluginPayload, $releaseManifest, $checksumFile | Select-Object FullName,Length,LastWriteTime | Format-List
if (-not $SkipSigning) {
    Get-AuthenticodeSignature $distExe, $pluginDll, $installerExe | Select-Object Path,Status,StatusMessage,@{n='Subject';e={$_.SignerCertificate.Subject}},@{n='NotAfter';e={$_.SignerCertificate.NotAfter}},@{n='Timestamp';e={$_.TimeStamperCertificate.Subject}} | Format-List
}

Write-Host "`nRelease lista para publicar: $version" -ForegroundColor Green
