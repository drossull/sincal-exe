"""Exercise PNDMAKE in an isolated AutoCAD 2025 document, never a user DWG."""
from pathlib import Path
import tempfile
import time
import win32com.client
import argparse
import sys
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--via-loader", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2].as_posix()
    sys.path.insert(0, root)
    scratch = tempfile.TemporaryDirectory(prefix="pndmake-loader-")
    loader = f"{root}/lisps/PNDMAKE.lsp"
    if args.via_loader:
        from sincal.resources import write_cad_loaders
        def cad_path(*parts):
            if parts and parts[0] == "lisps":
                return str(Path(root).joinpath(*parts))
            return str(Path(scratch.name).joinpath(*parts))
        with patch("sincal.resources.ruta_cad_usuario", side_effect=cad_path):
            # Missing first resource must not stop registration of PNDMAKE.
            write_cad_loaders(["lisps/AAA_MISSING_TEST.lsp", "lisps/PNDMAKE.lsp"])
        loader = (Path(scratch.name) / "acaddoc.lsp").as_posix()
    report = Path(tempfile.gettempdir()) / f"pndmake-{time.time_ns()}.txt"
    app = win32com.client.DispatchEx("AutoCAD.Application.25")
    doc = None
    try:
        for attempt in range(30):
            try:
                doc = app.Documents.Add()
                break
            except Exception:
                if attempt == 29:
                    raise
                time.sleep(1)
        doc.SendCommand(
            f'(setq PNDMT:Report (open "{report.as_posix()}" "w"))\n'
            f'(load "{loader}")\n'
            f'(load "{root}/tests/cad/pndmake_regression.lsp")\n'
            'PNDMAKE\n\n10\n'
            '(setq r (entget entity) p (cdr (assoc 10 r)) q (cdr (assoc 11 r)))\n'
            '(PNDMT:Assert (equal 0.1 (/ (- (cadr q) (cadr p)) (- (car q) (car p))) 1e-8) "real command")\n'
            '(write-line (strcat "DONE failures=" (itoa PNDMT:Failures)) PNDMT:Report)\n'
            '(close PNDMT:Report)\n'
        )
        for _ in range(120):
            content = report.read_text(errors="replace") if report.exists() else ""
            if "DONE" in content:
                print(content)
                return 0 if "DONE failures=0" in content else 1
            time.sleep(.5)
        print("Timed out waiting for native PNDMAKE tests.")
        return 1
    finally:
        if doc is not None:
            doc.Close(False)
        try:
            app.Quit()
        except Exception:
            pass
        scratch.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
