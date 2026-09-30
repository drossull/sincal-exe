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

function Invoke-TestCore([string]$Drawing, [string]$Script, [string]$Log) {
    $process = Start-Process -FilePath $env:SINCAL_CAD_ENGINE `
        -ArgumentList "/i `"$Drawing`" /s `"$Script`"" -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $Log -RedirectStandardError ($Log + '.err')
    if (-not $process.WaitForExit(120000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw "Timeout: $Log"
    }
    $process.Refresh()
    if ($process.ExitCode -ne 0) { throw "CAD exit $($process.ExitCode): $Log" }
}

$fixture = Join-Path $testDirectory 'fixture.dwg'
Copy-Item -LiteralPath $TemplatePath -Destination $fixture
$setupScript = Join-Path $testDirectory 'setup.scr'
@'
(setvar "FILEDIA" 0)
(command "_.-SCALELISTEDIT" "_Add" "SINCAL_TEST_CURRENT" "1:37" "_Exit")
(command "_.-SCALELISTEDIT" "_Add" "SINCAL TEST UNUSED" "1:73" "_Exit")
(setvar "CANNOSCALE" "SINCAL_TEST_CURRENT")
(setvar "CTAB" "Model")
(entmakex '((0 . "LINE") (10 0.0 0.0 0.0) (11 10.0 10.0 0.0)))
(setvar "CTAB" "Layout1")
(command "_.MVIEW" '(20.0 20.0) '(100.0 100.0))
(setvar "CTAB" "Model")
(setvar "CANNOSCALE" "SINCAL_TEST_CURRENT")
_.QSAVE
_.QUIT
_Y

'@ | Set-Content -LiteralPath $setupScript -Encoding Ascii
Invoke-TestCore $fixture $setupScript (Join-Path $testDirectory 'setup.log')

$failures = 0
foreach ($name in @('PURGEALL', 'AUDIT', 'BV', 'DL2', 'ZE', 'PAGESETUP-A1', 'PUBLISH-A1')) {
    $caseDir = Join-Path $testDirectory $name
    New-Item -ItemType Directory -Path $caseDir | Out-Null
    $drawing = Join-Path $caseDir 'test drawing.dwg'
    Copy-Item -LiteralPath $fixture -Destination $drawing
    $launcher = Join-Path $repoRoot "scripts/$name.bat"
    $log = Join-Path $caseDir 'launcher.log'
    $process = Start-Process -FilePath $env:ComSpec -ArgumentList "/d /c `"`"$launcher`"`"" `
        -WorkingDirectory $caseDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $log -RedirectStandardError ($log + '.err')
    # The real launcher owns its CAD subprocess and enforces a 900s timeout.
    $process.WaitForExit()
    $process.Refresh()
    if ($process.ExitCode -ne 0) {
        Write-Output "FAIL $name launcher: $log"
        $failures++
        continue
    }
    $env:SINCAL_TEST_DIR = $caseDir.Replace('\', '/')
    $verifyScript = Join-Path $caseDir 'verify.scr'
    @'
(setq result (open (strcat (getenv "SINCAL_TEST_DIR") "/result.txt") "w"))
(write-line (strcat "CURRENT=" (getvar "CANNOSCALE")) result)
(setq unused nil current nil)
(foreach item (dictsearch (namedobjdict) "ACAD_SCALELIST") (if (= (car item) 350) (progn (setq name (cdr (assoc 300 (entget (cdr item))))) (if (= name "SINCAL TEST UNUSED") (setq unused T)) (if (= name "SINCAL_TEST_CURRENT") (setq current T)))))
(write-line (strcat "UNUSED=" (if unused "yes" "no")) result)
(write-line (strcat "CURRENT_EXISTS=" (if current "yes" "no")) result)
(write-line (strcat "LINE=" (if (ssget "X" '((0 . "LINE"))) "yes" "no")) result)
(setq layoutDict (cdr (assoc -1 (dictsearch (namedobjdict) "ACAD_LAYOUT"))))
(write-line (strcat "LAYOUT2=" (if (dictsearch layoutDict "Layout2") "yes" "no")) result)
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
    if ($name -eq 'DL2' -and $result -notcontains 'LAYOUT2=no') { throw 'Layout2 was not removed' }
    if ($name -eq 'BV' -and $result -notcontains 'UNLOCKED=0') { throw 'Viewports remain unlocked' }
    if ($name -eq 'PAGESETUP-A1' -and ($result -notcontains 'PRINTER=AutoCAD PDF (High Quality Print).pc3' -or
        $result -notcontains 'PAPER=ISO_full_bleed_A1_(841.00_x_594.00_MM)')) {
        Write-Output "FAIL PAGESETUP-A1: page configuration was not applied: $($result -join ', ')"
        $failures++
        continue
    }
    if ($name -eq 'PUBLISH-A1' -and @(Get-ChildItem -LiteralPath $caseDir -Filter *.pdf).Count -eq 0) { throw 'No PDF output' }
    Write-Output "PASS ${name}: $($result -join ', ')"
}
Write-Output "Logs and disposable drawings retained in $testDirectory"
if ($failures) { throw "$failures launcher(s) failed; inspect their logs." }
