import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows file sharing semantics')
def test_cleanup_only_new_unlocked_drawing_sidecars(tmp_path):
    helper = Path(__file__).resolve().parents[1] / 'scripts/SINCAL_ENGINE.ps1'
    # Synthetic files only: no CAD execution and no real drawings modified.
    script = r'''
$ErrorActionPreference = 'Stop'
. $env:SINCAL_TEST_HELPER
$dwg = Join-Path $env:SINCAL_TEST_ROOT 'Plano prueba.dwg'
$dwl = [IO.Path]::ChangeExtension($dwg, '.dwl')
$dwl2 = [IO.Path]::ChangeExtension($dwg, '.dwl2')
[IO.File]::WriteAllText($dwg, 'synthetic')
[IO.File]::WriteAllText($dwl, 'old')
[IO.File]::WriteAllText($dwl2, 'new')
Remove-SincalResidualDrawingLocks $dwg @($dwl)
if (-not (Test-Path -LiteralPath $dwl) -or (Test-Path -LiteralPath $dwl2)) { throw 'Pre-existing lock handling failed' }
[IO.File]::WriteAllText($dwl2, 'new')
$held = [IO.File]::Open($dwg, 'Open', 'Read', 'Read')
try { Remove-SincalResidualDrawingLocks $dwg } finally { $held.Dispose() }
if (-not (Test-Path -LiteralPath $dwl2)) { throw 'Deleted while DWG was open' }
Remove-SincalResidualDrawingLocks $dwg @($dwl)
if (Test-Path -LiteralPath $dwl2) { throw 'Did not delete residual' }
if ([IO.File]::ReadAllText($dwg) -ne 'synthetic') { throw 'DWG changed' }
# Exercise the shared launcher with a simulated finished CAD process.
function Invoke-SincalCadScriptCore { [IO.File]::WriteAllText($dwl2, 'created'); return 0 }
$engine = [pscustomobject]@{Path='test';Year=2025;Mode='CORE_CONSOLE'}
Invoke-SincalCadScript -Engine $engine -DrawingPath $dwg -ScriptPath 'test.scr'
if (Test-Path -LiteralPath $dwl2) { throw 'Successful launcher did not clean' }
function Invoke-SincalCadScriptCore { [IO.File]::WriteAllText($dwl2, 'created'); throw 'CAD failed' }
try { Invoke-SincalCadScript -Engine $engine -DrawingPath $dwg -ScriptPath 'test.scr' } catch {}
if (-not (Test-Path -LiteralPath $dwl2)) { throw 'Failed execution cleaned locks' }
'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script],
                            env={**os.environ, 'SINCAL_TEST_HELPER': str(helper), 'SINCAL_TEST_ROOT': str(tmp_path)},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
