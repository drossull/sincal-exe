"""Exercise PNDMAKE in an isolated AutoCAD 2025 document, never a user DWG."""
from pathlib import Path
import tempfile
import time
import win32com.client


def main():
    root = Path(__file__).resolve().parents[2].as_posix()
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
            f'(load "{root}/lisps/PNDMAKE.lsp")\n'
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


if __name__ == "__main__":
    raise SystemExit(main())
