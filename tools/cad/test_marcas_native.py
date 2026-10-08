"""Run native CAD tests in an isolated, disposable AutoCAD instance (Windows)."""
import argparse
from pathlib import Path
import tempfile
import time

import win32com.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-open", action="store_true", help="Leave scratch drawing for visual QA")
    parser.add_argument("--workflow", choices=("dynamic", "workflow", "detail", "build_detail", "build_presentation", "presentation"), default="dynamic")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if args.workflow == "build_presentation" and any((root / "masters" / name).exists() for name in ("SINCAL_MARCA_SC_V3.dwg", "SINCAL_MARCA_DE_V2.dwg")):
        parser.error("Presentation masters already exist; refusing to overwrite.")
    if args.workflow == "build_detail" and (root / "masters/SINCAL_MARCA_DE_V1.dwg").exists():
        parser.error("Detail master already exists; refusing to overwrite it.")
    report = Path(tempfile.gettempdir()) / f"marcas-dynamic-{time.time_ns()}.txt"
    app = win32com.client.DispatchEx("AutoCAD.Application.25")
    for attempt in range(20):
        try:
            app.Visible = False
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
            # WBLOCK can keep the isolated instance busy briefly after SCRIPT.
            for attempt in range(20):
                try:
                    while app.Documents.Count:
                        app.Documents.Item(0).Close(False)
                    app.Quit()
                    break
                except Exception:
                    if attempt == 19:
                        print("Warning: scratch CAD could not be closed; no user drawing was opened.")
                    time.sleep(.5)


if __name__ == "__main__":
    raise SystemExit(main())
