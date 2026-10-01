"""Exercise the real Windows PowerShell 5.1 runner without touching CAD files."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell integration")


def test_batch_log_streams_failure_timeout_and_retention(tmp_path):
    helper = str(ROOT / "scripts/SINCAL_ENGINE.ps1").replace("'", "''")
    directory = str(tmp_path).replace("'", "''")
    script = tmp_path / "test.ps1"
    script.write_text("""
$ErrorActionPreference = 'Stop'
. 'HELPER'
function Get-SincalScriptLogDirectory { return 'DIRECTORY' }
$fake = Join-Path 'DIRECTORY' 'accoreconsole.exe'
Add-Type -OutputAssembly $fake -OutputType ConsoleApplication -TypeDefinition @'
using System;
using System.Threading;
class FakeCAD {
    static int Main(string[] args) {
        Console.OutputEncoding = System.Text.Encoding.Unicode;
        Console.WriteLine("OUTPUT-START");
        Console.Error.WriteLine("ERROR-CHANNEL");
        if (args[1] == "timeout") { Thread.Sleep(10000); }
        for (int i=0; i<2000; i++) {
            Console.WriteLine("normal-" + i);
            Console.Error.WriteLine("error-" + i);
        }
        Console.WriteLine("OUTPUT-END");
        return args[1] == "fail" ? 7 : 0;
    }
}
'@
$engine = New-SincalCadEngineDescriptor -Path $fake
Start-SincalScriptLog 'test'
$first = $script:SincalLogPath
try {
    Invoke-SincalCadScript -Engine $engine -DrawingPath ok -ScriptPath dummy | Out-Null
    try { Invoke-SincalCadScript -Engine $engine -DrawingPath fail -ScriptPath dummy | Out-Null } catch { Write-Host $_ }
    try { Invoke-SincalCadScript -Engine $engine -DrawingPath timeout -ScriptPath dummy -TimeoutSeconds 1 | Out-Null } catch { Write-Host $_ }
} finally { Stop-SincalScriptLog }
Copy-Item -LiteralPath $first -Destination (Join-Path 'DIRECTORY' 'verified.txt')
# Seed only owned log names and unrelated files; preserve a log of this active PID.
$old = Join-Path 'DIRECTORY' ('SINCAL-20000101-000000-2147483647-' + [guid]::NewGuid().ToString('N') + '.log')
Set-Content -LiteralPath $old -Value old
(Get-Item -LiteralPath $old).LastWriteTime = (Get-Date).AddDays(-40)
$active = Join-Path 'DIRECTORY' ('SINCAL-20000101-000000-' + $PID + '-' + [guid]::NewGuid().ToString('N') + '.log')
Set-Content -LiteralPath $active -Value active
(Get-Item -LiteralPath $active).LastWriteTime = (Get-Date).AddDays(-40)
Set-Content -LiteralPath (Join-Path 'DIRECTORY' 'manual.log') -Value keep
1..105 | ForEach-Object {
    $p = Join-Path 'DIRECTORY' ('SINCAL-20260930-000000-2147483647-' + [guid]::NewGuid().ToString('N') + '.log')
    Set-Content -LiteralPath $p -Value test
}
Start-SincalScriptLog 'retention'
Stop-SincalScriptLog
if (Test-Path -LiteralPath $old) { throw 'Expired log survived' }
if (-not (Test-Path -LiteralPath $active)) { throw 'Active log removed' }
if (-not (Test-Path -LiteralPath (Join-Path 'DIRECTORY' 'manual.log'))) { throw 'Unrelated log removed' }
$remaining = @(Get-ChildItem -LiteralPath 'DIRECTORY' -Filter '*2147483647*.log')
if ($remaining.Count -ne 99) { throw "Retention count $($remaining.Count)" }
""".replace("HELPER", helper).replace("DIRECTORY", directory), encoding="utf-8-sig")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")
    log = (tmp_path / "verified.txt").read_text(encoding="utf-8-sig")
    for expected in ("OUTPUT-START", "OUTPUT-END", "normal-1999", "error-1999",
                     "ERROR-CHANNEL", "Codigo de salida CAD: 7", "FALLO DWG: timeout",
                     "1 procesos terminados; 2 fallidos", "Duracion:"):
        assert expected in log


def test_all_launchers_finalize_logs():
    for path in (ROOT / "scripts").glob("*.ps1"):
        if path.name == "SINCAL_ENGINE.ps1":
            continue
        source = path.read_text(encoding="utf-8-sig")
        assert "Start-SincalScriptLog" in source
        assert "finally {\n    Stop-SincalScriptLog\n}" in source
