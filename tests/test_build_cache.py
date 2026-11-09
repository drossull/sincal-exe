import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tools.build_cache import fingerprint, matches, record


def test_reuse_requires_same_inputs_context_and_intact_outputs(tmp_path):
    source, binary, receipt = (tmp_path/name for name in ('source.py', 'app.exe', 'receipt.json'))
    source.write_text('version one')
    binary.write_bytes(b'compiled one')
    key = fingerprint([source], 'toolchain-1')
    assert not matches(receipt, key, [binary])
    record(receipt, key, [binary])
    assert matches(receipt, fingerprint([source], 'toolchain-1'), [binary])
    assert not matches(receipt, fingerprint([source], 'toolchain-2'), [binary])
    source.write_text('version two')
    assert not matches(receipt, fingerprint([source], 'toolchain-1'), [binary])
    binary.write_bytes(b'corrupted')
    assert not matches(receipt, key, [binary])
    binary.unlink()
    assert not matches(receipt, key, [binary])


def test_added_and_deleted_sources_invalidate_without_bin_obj_or_bytecode_churn(tmp_path):
    project = tmp_path/'src'
    project.mkdir()
    source = project/'One.cs'
    source.write_text('one')
    initial = fingerprint([project])
    for folder in ('bin', 'obj', '__pycache__'):
        (project/folder).mkdir()
        (project/folder/'generated').write_text('generated')
    assert fingerprint([project]) == initial
    added = project/'Two.cs'
    added.write_text('two')
    assert fingerprint([project]) != initial
    added.unlink()
    assert fingerprint([project]) == initial
    with pytest.raises(FileNotFoundError):
        fingerprint([project/'missing.cs'])


@pytest.mark.parametrize('data', ['broken', '{}', 'null', '[]', '{"schema":1,"key":"a"}'])
def test_invalid_receipt_never_authorizes_reuse(tmp_path, data):
    receipt = tmp_path/'receipt.json'
    receipt.write_text(data)
    assert not matches(receipt, 'a', [tmp_path/'anything.exe'])


def test_powershell_receipt_roundtrip_and_source_change(tmp_path):
    pwsh = shutil.which('pwsh')
    if not pwsh:
        pytest.skip('PowerShell is required for the build wrapper test')
    root = Path(__file__).resolve().parents[1]
    tools = tmp_path/'tools'
    tools.mkdir()
    for name in ('build_cache.py', 'build_components.ps1', 'build_release.ps1'):
        shutil.copy2(root/'tools'/name, tools/name)
    source, binary = tmp_path/'native.cs', tmp_path/'native.dll'
    source.write_text('original')
    binary.write_text('compiled')
    script = tmp_path/'check.ps1'
    script.write_text('''param([string]$projectRoot)
$ErrorActionPreference = 'Stop'
$CleanBuild = $false
. (Join-Path $projectRoot 'tools/build_components.ps1')
$source = Join-Path $projectRoot 'native.cs'
$binary = Join-Path $projectRoot 'native.dll'
$c = New-ComponentReceipt -Name 'test-native' -Inputs @($source) -Outputs @($binary) -Context 'compiler-1'
if (Test-ComponentReceipt $c) { throw 'Unexpected cache hit' }
Save-ComponentReceipt $c
if (-not (Test-ComponentReceipt $c)) { throw 'Expected reuse' }
Set-Content -LiteralPath $source -Value 'edited'
$changed = New-ComponentReceipt -Name 'test-native' -Inputs @($source) -Outputs @($binary) -Context 'compiler-1'
if (Test-ComponentReceipt $changed) { throw 'Stale reuse' }
$CleanBuild = $true
if (Test-ComponentReceipt $c) { throw 'Clean build ignored' }
exit 0
''', encoding='utf-8')
    result = subprocess.run([pwsh, '-NoProfile', '-File', str(script), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout+result.stderr
