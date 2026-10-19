"""Benchmark the real runner against a quiet second pipe, without CAD/DWGs."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell')


def test_asymmetric_output_is_not_throttled(tmp_path):
    helper = str(ROOT / 'scripts/SINCAL_ENGINE.ps1').replace("'", "''")
    directory = str(tmp_path).replace("'", "''")
    script = tmp_path / 'throughput.ps1'
    script.write_text(r'''
$ErrorActionPreference = 'Stop'
. 'HELPER'
$fake = Join-Path 'DIRECTORY' 'accoreconsole.exe'
Add-Type -OutputAssembly $fake -OutputType ConsoleApplication -TypeDefinition @'
using System;
using System.IO;
using System.Threading;
class FakeCAD {
    static void Main(string[] args) {
        Console.OutputEncoding = System.Text.Encoding.Unicode;
        var output = args[1] == "stdout" ? Console.Out : Console.Error;
        for (int i=0; i<1500; i++) output.WriteLine("line-" + i);
        output.Flush();
        // Keep the unused pipe open until the reader consumed every line.
        string ack = Environment.GetEnvironmentVariable("SINCAL_TEST_ACK");
        var until = DateTime.UtcNow.AddSeconds(45);
        while (!File.Exists(ack) && DateTime.UtcNow < until) Thread.Sleep(10);
        if (!File.Exists(ack)) Environment.Exit(8);
        File.WriteAllText(Environment.GetEnvironmentVariable("SINCAL_COMPLETION_PATH"),
                          Environment.GetEnvironmentVariable("SINCAL_COMPLETION_TOKEN"));
    }
}
'@
$engine = New-SincalCadEngineDescriptor -Path $fake
$dummy = Join-Path 'DIRECTORY' 'dummy.scr'
Set-Content -LiteralPath $dummy -Value "_.QSAVE`n_.QUIT`n_Y`n"
foreach ($channel in @('stdout', 'stderr')) {
    $env:SINCAL_TEST_ACK = Join-Path 'DIRECTORY' ($channel + '.ack')
    $script:lines = 0
    # Isolate pipe throughput from terminal rendering and transcript disk speed.
    function Write-SincalCadOutput {
        param([string]$Text, [string]$Channel)
        if ($Text -ne ('line-' + $script:lines)) { throw "Lost/reordered output: $Text" }
        $script:lines++
        if ($script:lines -eq 1500) { [IO.File]::WriteAllText($env:SINCAL_TEST_ACK, 'ok') }
    }
    $clock = [Diagnostics.Stopwatch]::StartNew()
    Invoke-SincalCadScriptCore -Engine $engine -DrawingPath $channel -ScriptPath $dummy | Out-Null
    $clock.Stop()
    Write-Output "$channel seconds=$($clock.Elapsed.TotalSeconds) lines=$script:lines"
    if ($script:lines -ne 1500) { throw 'Missing output' }
    if ($clock.Elapsed.TotalSeconds -ge 8) { throw 'Output reader is throttled by a quiet pipe' }
}
'''.replace('HELPER', helper).replace('DIRECTORY', directory), encoding='utf-8-sig')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy',
                             'Bypass', '-File', str(script)], capture_output=True,
                            timeout=100)
    output = result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace')
    print(output)
    assert result.returncode == 0, output
