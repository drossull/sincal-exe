"""CSV-SC native regression; isolated CAD, never opens/saves the user's DWGs."""
import argparse
from pathlib import Path
import tempfile
import time

import win32com.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--xsr', type=Path, help='Equivalent fixed-width Tekla report')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    work = Path(tempfile.mkdtemp(prefix='sincal-csv-test-'))
    report = work / 'report.txt'
    output = work / 'table.dwg'
    app = win32com.client.DispatchEx('AutoCAD.Application.25')
    try:
        for attempt in range(30):
            try:
                app.Visible = False
                doc = app.Documents.Add()
                break
            except Exception:
                if attempt == 29:
                    raise
                time.sleep(1)
        log = Path(doc.GetVariable('LOGFILENAME'))
        command = f'''(progn
          (setq CSVT:report (open "{report.as_posix()}" "w")
                CSVT:csv "{args.csv.resolve().as_posix()}" CSVT:output "{output.as_posix()}"
                CSVT:xsr {('"' + args.xsr.resolve().as_posix() + '"') if args.xsr else 'nil'})
          (setvar "LOGFILEMODE" 1)
          (defun *error* (msg) (write-line (strcat "ERROR: " msg) CSVT:report) (close CSVT:report) (princ))
          (setenv "SINCAL_TEST_ROOT" "{root.as_posix()}")
          (load "{root.as_posix()}/lisps/CSV-SC.lsp")
          (load "{root.as_posix()}/tests/cad/csv_sc_regression.lsp"))'''
        doc.SendCommand(command.replace('\n', ' ') + '\n')
        content = ''
        for _ in range(240):
            content = report.read_text(errors='replace') if report.exists() else ''
            if 'DONE' in content or 'ERROR:' in content:
                break
            time.sleep(.5)
        print('\n'.join(line for line in content.splitlines() if not line.startswith('PASS cell ')))
        if 'DONE failures=0' not in content:
            print(log.read_text(errors='replace')[-9000:])
        print(f'Scratch results: {work}')
        return 0 if 'DONE failures=0' in content else 1
    finally:
        for attempt in range(20):
            try:
                while app.Documents.Count:
                    app.Documents.Item(0).Close(False)
                app.Quit()
                break
            except Exception:
                time.sleep(.5)


if __name__ == '__main__':
    raise SystemExit(main())
