# Integration check: ONLY synthetic drawings in a fresh temporary directory.
param(
    [Parameter(Mandatory = $true)][string]$EnginePath,
    [Parameter(Mandatory = $true)][string]$TemplatePath
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$testDirectory = Join-Path ([IO.Path]::GetTempPath()) ('SINCAL-CMD-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testDirectory | Out-Null
Write-Output "TEST_DIRECTORY=$testDirectory"
$env:SINCAL_CAD_ENGINE = (Resolve-Path -LiteralPath $EnginePath).Path
$env:SINCAL_TEST_DIR = $testDirectory.Replace('\', '/')
$env:SINCAL_TEST_REPO = $repoRoot.Replace('\', '/')
. (Join-Path $repoRoot 'scripts/SINCAL_ENGINE.ps1')

function Invoke-TestCore([string]$Drawing, [string]$Script, [string]$Log) {
    $engine=New-SincalCadEngineDescriptor -Path $env:SINCAL_CAD_ENGINE -Headless $true
    Invoke-SincalCadScript -Engine $engine -DrawingPath $Drawing -ScriptPath $Script -TimeoutSeconds 120 -SkipSave *>&1 | Out-File -LiteralPath $Log
}

$fixture = Join-Path $testDirectory 'fixture.dwg'
Copy-Item -LiteralPath $TemplatePath -Destination $fixture
$setupScript = Join-Path $testDirectory 'setup.scr'
@'
(setvar "FILEDIA" 0)
(load (strcat (getenv "SINCAL_TEST_REPO") "/lisps/MARCAS-SC.lsp"))
(load (strcat (getenv "SINCAL_TEST_REPO") "/tests/cad/viewport_snapshot.lsp"))
(command "_.-LAYOUT" "_New" "Layout2")
(command "_.-LAYOUT" "_New" "A1")
(command "_.-SCALELISTEDIT" "_Add" "SINCAL_TEST_CURRENT" "1:37" "_Exit")
(command "_.-SCALELISTEDIT" "_Add" "SINCAL TEST UNUSED" "1:73" "_Exit")
(setvar "CANNOSCALE" "SINCAL_TEST_CURRENT")
(setvar "CTAB" "Model")
(entmakex '((0 . "LINE") (10 0.0 0.0 0.0) (11 10.0 10.0 0.0)))
(setvar "CTAB" "Layout1")
(command "_.MVIEW" '(20.0 20.0) '(100.0 100.0))
(command "_.MSPACE")
(command "_.ZOOM" "_C" '(100.0 50.0) 37.0)
(setvar "CANNOSCALE" "SINCAL_TEST_CURRENT")
(SINCAL:Snapshot (strcat (getenv "SINCAL_TEST_DIR") "/before-viewports.txt"))
_.QSAVE
_.QUIT
_Y

'@ | Set-Content -LiteralPath $setupScript -Encoding Ascii
Invoke-TestCore $fixture $setupScript (Join-Path $testDirectory 'setup.log')

$failures = 0
foreach ($name in @('PURGEALL', 'AUDIT', 'BV', 'DL2', 'ZE', 'PAGESETUP-A1', 'PUBLISH-A1', 'PUBLISH-KEEP')) {
    $caseDir = Join-Path $testDirectory $name
    New-Item -ItemType Directory -Path $caseDir | Out-Null
    $drawing = Join-Path $caseDir 'test drawing.dwg'
    Copy-Item -LiteralPath $fixture -Destination $drawing
    Copy-Item -LiteralPath $fixture -Destination (Join-Path $caseDir 'second drawing.dwg')
    $launcher = Join-Path $repoRoot "scripts/$name.bat"
    if ($name -eq 'PUBLISH-KEEP') { $launcher = Join-Path $repoRoot 'scripts/PUBLISH-A1.bat' }
    $inputHash = (Get-FileHash -LiteralPath $drawing).Hash
    $log = Join-Path $caseDir 'launcher.log'
    $process=New-Object System.Diagnostics.Process
    $process.StartInfo.FileName=$env:ComSpec
    $process.StartInfo.Arguments="/d /c `"`"$launcher`"`""
    if ($name -eq 'PUBLISH-KEEP') { $process.StartInfo.Arguments="/d /c `"`"$launcher`" -KeepSetup`"" }
    $process.StartInfo.WorkingDirectory=$caseDir
    $process.StartInfo.UseShellExecute=$false
    $process.StartInfo.CreateNoWindow=$true
    $process.StartInfo.RedirectStandardOutput=$true
    $process.StartInfo.RedirectStandardError=$true
    $process.StartInfo.StandardOutputEncoding=[Text.Encoding]::UTF8
    $process.StartInfo.StandardErrorEncoding=[Text.Encoding]::UTF8
    if(-not $process.Start()){throw 'Could not launch test'}
    $outTask=$process.StandardOutput.ReadToEndAsync()
    $errTask=$process.StandardError.ReadToEndAsync()
    # The real launcher owns its CAD subprocess and enforces a 900s timeout.
    if(-not $process.WaitForExit(300000)){throw "Launcher timed out: $name"}
    [IO.File]::WriteAllText($log,$outTask.GetAwaiter().GetResult())
    [IO.File]::WriteAllText($log+'.err',$errTask.GetAwaiter().GetResult())
    if ($process.ExitCode -ne 0) {
        Write-Output "FAIL $name launcher: $log"
        $failures++
        continue
    }
    $env:SINCAL_TEST_DIR = $caseDir.Replace('\', '/')
    $verifyScript = Join-Path $caseDir 'verify.scr'
    @'
(setq result (open (strcat (getenv "SINCAL_TEST_DIR") "/result.txt") "w"))
(load (strcat (getenv "SINCAL_TEST_REPO") "/tests/cad/viewport_snapshot.lsp"))
(SINCAL:Snapshot (strcat (getenv "SINCAL_TEST_DIR") "/after-viewports.txt"))
(write-line (strcat "CURRENT=" (getvar "CANNOSCALE")) result)
(setq unused nil current nil)
(foreach item (dictsearch (namedobjdict) "ACAD_SCALELIST") (if (= (car item) 350) (progn (setq name (cdr (assoc 300 (entget (cdr item))))) (if (= name "SINCAL TEST UNUSED") (setq unused T)) (if (= name "SINCAL_TEST_CURRENT") (setq current T)))))
(write-line (strcat "UNUSED=" (if unused "yes" "no")) result)
(write-line (strcat "CURRENT_EXISTS=" (if current "yes" "no")) result)
(write-line (strcat "LINE=" (if (ssget "X" '((0 . "LINE"))) "yes" "no")) result)
(setq layoutDict (cdr (assoc -1 (dictsearch (namedobjdict) "ACAD_LAYOUT"))))
(write-line (strcat "LAYOUT2=" (if (dictsearch layoutDict "Layout2") "yes" "no")) result)
(write-line (strcat "A1=" (if (dictsearch layoutDict "A1") "yes" "no")) result)
(setq layoutData (dictsearch layoutDict "Layout1"))
(write-line (strcat "PRINTER=" (cdr (assoc 2 layoutData))) result)
(write-line (strcat "PAPER=" (cdr (assoc 4 layoutData))) result)
(setq unlocked 0 vps (ssget "X" '((0 . "VIEWPORT"))) i 0)
(if vps (repeat (sslength vps) (setq data (entget (ssname vps i)) i (1+ i)) (if (and (> (cdr (assoc 69 data)) 1) (= 0 (logand 16384 (cdr (assoc 90 data))))) (setq unlocked (1+ unlocked)))))
(write-line (strcat "UNLOCKED=" (itoa unlocked)) result)
(close result)
_.QUIT
_Y

'@ | Set-Content -LiteralPath $verifyScript -Encoding Ascii
    Invoke-TestCore $drawing $verifyScript (Join-Path $caseDir 'verify.log')
    $result = Get-Content -LiteralPath (Join-Path $caseDir 'result.txt')
    if ($result -notcontains 'LINE=yes') { throw "Lost geometry: $name" }
    if ($name -eq 'PURGEALL' -and ($result -notcontains 'UNUSED=no' -or
        $result -notcontains 'CURRENT_EXISTS=yes' -or $result -notcontains 'CURRENT=SINCAL_TEST_CURRENT')) {
        throw "Purge scale verification failed: $caseDir"
    }
    if ($name -eq 'DL2' -and ($result -notcontains 'LAYOUT2=no' -or $result -notcontains 'A1=no')) { throw 'Layout2/A1 were not removed' }
    if ($name -eq 'BV' -and $result -notcontains 'UNLOCKED=0') { throw 'Viewports remain unlocked' }
    if ($name -eq 'PAGESETUP-A1' -and ($result -notcontains 'PRINTER=AutoCAD PDF (High Quality Print).pc3' -or
        $result -notcontains 'PAPER=ISO_full_bleed_A1_(841.00_x_594.00_MM)')) {
        Write-Output "FAIL PAGESETUP-A1: page configuration was not applied: $($result -join ', ')"
        $failures++
        continue
    }
    if ($name -like 'PUBLISH-*') {
        foreach ($base in @('test drawing', 'second drawing')) {
            $pdf = Join-Path $caseDir "$base.pdf"
            if (-not (Test-Path -LiteralPath $pdf) -or (Get-Item -LiteralPath $pdf).Length -eq 0) { throw "Missing PDF with DWG name: $pdf" }
        }
        if ($name -eq 'PUBLISH-KEEP' -and (Get-FileHash -LiteralPath $drawing).Hash -ne $inputHash) { throw 'KeepSetup modified the DWG' }
    }
    $before = Get-Content -LiteralPath (Join-Path $testDirectory 'before-viewports.txt') -Raw
    $after = Get-Content -LiteralPath (Join-Path $caseDir 'after-viewports.txt') -Raw
    if ($before -ne $after) { throw "Floating viewport changed: $name" }
    if (@(Get-ChildItem -LiteralPath $caseDir -File | Where-Object Extension -in '.dwl','.dwl2').Count) { throw "Residual DWG locks: $name" }
    Write-Output "PASS ${name}: $($result -join ', ')"
}
Write-Output "Logs and disposable drawings retained in $testDirectory"
if ($failures) { throw "$failures launcher(s) failed; inspect their logs." }
