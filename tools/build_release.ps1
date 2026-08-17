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
    if ($installer -notmatch '#error AppVersion must be supplied by the build script\.') {
        throw 'SINCAL_Installer.iss no está parametrizado para AppVersion.'
    }
    if ($installer -notmatch '#error AppVersionTag must be supplied by the build script\.') {
        throw 'SINCAL_Installer.iss no está parametrizado para AppVersionTag.'
    }
}

function Invoke-PythonCompile([string]$ProjectRoot) {
    $pythonFiles = @(
        'main.py',
        'core_sincal.py',
        'sincal_runtime.py',
        'modulos\tab_armaduras.py',
        'modulos\tab_docs.py',
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

function Write-Checksums([string]$ProjectRoot, [string[]]$Paths) {
    $outputPath = Join-Path $ProjectRoot 'installer_output\SHA256SUMS.txt'
    $lines = foreach ($path in $Paths) {
        $hash = (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash *$([IO.Path]::GetFileName($path))"
    }
    Set-Content -Path $outputPath -Value $lines -Encoding UTF8
    return $outputPath
}

$projectRoot = Get-ProjectRoot
$version = Read-Version $projectRoot
$distExe = Join-Path $projectRoot 'dist\SINCAL.exe'
$pluginDll = Join-Path $projectRoot 'cad-packages\Autodesk\SINCAL.bundle\Contents\AutoCAD2025\Sincal.AutoCAD2025.dll'
$installerExe = Join-Path $projectRoot ("installer_output\Setup_SINCAL_{0}.exe" -f $version)

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
Remove-ArtifactIfExists (Join-Path $projectRoot 'installer_output\SHA256SUMS.txt')

Write-Step "Compilando ejecutable"
Push-Location $projectRoot
try {
    & pyinstaller --noconfirm 'SINCAL.spec'
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

Write-Step "Compilando instalador"
$iscc = Resolve-InnoSetupPath -Provided $InnoSetupPath
$normalizedVersion = $version.TrimStart('v', 'V')
Push-Location $projectRoot
try {
    & $iscc "/DAppVersion=$normalizedVersion" "/DAppVersionTag=$version" 'SINCAL_Installer.iss'
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

Write-Step "Generando checksums"
$checksumFile = Write-Checksums -ProjectRoot $projectRoot -Paths @($installerExe)

Write-Step "Resumen"
Get-Item $distExe, $pluginDll, $installerExe, $checksumFile | Select-Object FullName,Length,LastWriteTime | Format-List
if (-not $SkipSigning) {
    Get-AuthenticodeSignature $distExe, $pluginDll, $installerExe | Select-Object Path,Status,StatusMessage,@{n='Subject';e={$_.SignerCertificate.Subject}},@{n='NotAfter';e={$_.SignerCertificate.NotAfter}},@{n='Timestamp';e={$_.TimeStamperCertificate.Subject}} | Format-List
}

Write-Host "`nRelease lista para publicar: $version" -ForegroundColor Green
