"""VG regression in a disposable AutoCAD instance; never opens user DWGs."""
from pathlib import Path
import tempfile
import time
import win32com.client


def main():
    root = Path(__file__).resolve().parents[2].as_posix()
    report = Path(tempfile.gettempdir()) / f"vg-{time.time_ns()}.txt"
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
            f'(setq vg-report (open "{report.as_posix()}" "w"))\n'
            f'(load "{root}/lisps/PURGEALL.lsp")\n'
            f'(load "{root}/lisps/VG.lsp")\n'
            f'(load "{root}/tests/cad/vg_regression.lsp")\n'
            'VG\n'
            '(VGT:Assert (null (tblsearch "BLOCK" vg-name)) "real VG purges target definition")\n'
            '(VGT:Assert (not (vlax-erased-p vg-other)) "other reference survives purge")\n'
            '(write-line (strcat "DONE failures=" (itoa vg-failures)) vg-report)\n'
            '(close vg-report)\n'
        )
        for _ in range(120):
            content = report.read_text(errors="replace") if report.exists() else ""
            if "DONE" in content:
                print(content)
                return 0 if "DONE failures=0" in content else 1
            time.sleep(.5)
        print("VG native test timed out")
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
