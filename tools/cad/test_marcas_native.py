"""Run native CAD tests in an isolated, disposable AutoCAD instance (Windows)."""
import argparse
from pathlib import Path
import tempfile
import time

import win32com.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-open", action="store_true", help="Leave scratch drawing for visual QA")
    parser.add_argument("--workflow", choices=("dynamic", "workflow"), default="dynamic")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = Path(tempfile.gettempdir()) / f"marcas-dynamic-{time.time_ns()}.txt"
    app = win32com.client.DispatchEx("AutoCAD.Application.25")
    app.Visible = False
    for attempt in range(20):
        try:
            doc = app.Documents.Add()
            break
        except Exception:
            if attempt == 19:
                raise
            time.sleep(1)
    try:
        log = Path(doc.GetVariable("LOGFILENAME"))
        script = root / f"tests/cad/marcas_sc_{args.workflow}.scr"
        command = f'''(progn
          (setq SCMT:Report (open "{report.as_posix()}" "w"))
          (setvar "LOGFILEMODE" 1)
          (defun *error* (msg) (write-line (strcat "ERROR: " msg) SCMT:Report) (close SCMT:Report) (princ))
          (setenv "SINCAL_TEST_ROOT" "{root.as_posix()}")
          (command "_.SCRIPT" "{script.as_posix()}"))'''
        doc.SendCommand(command.replace("\n", " ") + "\n")
        for _ in range(120):
            content = report.read_text(errors="replace") if report.exists() else ""
            if "DONE" in content or "ERROR:" in content:
                break
            time.sleep(.5)
        print(content, flush=True)
        for attempt in range(30):
            try:
                doc.SetVariable("LOGFILEMODE", 0)
                break
            except Exception:
                time.sleep(.5)
        print(log.read_text(errors="replace")[-14000:], flush=True)
        if args.keep_open:
            app.Visible = True
            print("Scratch AutoCAD left open for visual QA; close without saving.")
        return 0 if "DONE failures=0" in content else 1
    finally:
        if not args.keep_open:
            doc.Close(False)
            for extra in list(app.Documents):
                extra.Close(False)
            try:
                app.Quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
