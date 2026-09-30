"""Keep Tk's process-global state isolated from other UI tests."""
from pathlib import Path
import subprocess
import sys


def test_tooltip_lifecycle_in_isolated_tk_process():
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests",
         "-p", "tooltip_ui_smoke.py", "-v"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
