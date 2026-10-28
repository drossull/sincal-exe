"""Exercise CEV/CEVIADA chains, fields and grip-equivalent edits in scratch CAD.

python tools/cad/test_ceviada_native.py --progid AutoCAD.Application.25
python tools/cad/test_ceviada_native.py --progid AutoCAD.Application.26
python tools/cad/test_ceviada_native.py --progid ZWCAD.Application.2026
"""
import argparse
import math
from pathlib import Path
import tempfile

import pythoncom
import win32api
import win32com.client
import win32con
import win32process

from test_nivel_base_native import retry, close_owned, lisp_string
from test_of2_native import send


# Read real entity types, dimension placement and evaluated field caches.
INSPECT = r'''
(defun CEVT:Dump (path / out debug obj e d a b p dx dy len off q fd expr target pair blockent)
  (setq out (open path "w") debug (open (strcat path ".dxf") "w"))
  (vlax-for obj (vla-get-ModelSpace (vla-get-ActiveDocument (vlax-get-acad-object)))
    (setq e (vlax-vla-object->ename obj) d (entget e))
    (if (= "DIMENSION" (cdr (assoc 0 d)))
      (progn
        (setq a (trans (cdr (assoc 13 d)) 0 1)
              b (trans (cdr (assoc 14 d)) 0 1)
              p (trans (cdr (assoc 10 d)) 0 1)
              dx (- (car b) (car a)) dy (- (cadr b) (cadr a))
              len (sqrt (+ (* dx dx) (* dy dy)))
              off (/ (- (* dx (- (cadr p) (cadr b)))
                        (* dy (- (car p) (car b)))) len)
              q (list e) expr nil target nil)
        ;; ZWCAD stores dimension fields on the anonymous block's MTEXT.
        (setq blockent (tblobjname "BLOCK" (cdr (assoc 2 d))))
        (while (and (setq blockent (entnext blockent))
                    (/= "ENDBLK" (cdr (assoc 0 (entget blockent)))))
          (setq q (cons blockent q)))
        (while q
          (setq fd (entget (car q)) q (cdr q))
          (write-line (vl-prin1-to-string fd) debug)
          (if (= "FIELD" (cdr (assoc 0 fd)))
            (progn
              (if (= "AcExpr" (cdr (assoc 1 fd)))
                (setq expr (cdr (assoc 140 fd))))
              (if (assoc 331 fd)
                (setq target (cdr (assoc 5 (entget (cdr (assoc 331 fd)))))))))
          (foreach pair fd
            (if (member (car pair) '(350 360))
              (setq q (cons (cdr pair) q)))))
        (write-line (strcat (vla-get-Handle obj) "|"
          (itoa (logand 7 (cdr (assoc 70 d)))) "|"
          (rtos (vla-get-Measurement obj) 2 8) "|" (rtos off 2 8) "|"
          (if expr (rtos expr 2 8) "nil") "|" (if target target "nil")) out))))
  (close out) (close debug) (princ))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--progid', default='AutoCAD.Application.25')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    folder = Path(tempfile.mkdtemp(prefix='sincal-ceviada-test-'))
    helper = folder / 'inspect.lsp'
    helper.write_text(INSPECT, encoding='ascii')
    print(f'Report: {folder}', flush=True)
    before = set(win32process.EnumProcesses())
    app = win32com.client.DispatchEx(args.progid)
    pid = retry(lambda: win32process.GetWindowThreadProcessId(app.HWND)[1], 60)
    if pid in before:
        raise RuntimeError('Refusing to touch an existing CAD process.')
    handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE | win32con.SYNCHRONIZE, False, pid)
    try:
        retry(lambda: setattr(app, 'Visible', False))
        doc = retry(lambda: app.Documents.Add(), 60)
        # A new document can be returned before its automation methods are ready.
        retry(lambda: getattr(doc, 'SendCommand'), 60)
        send(doc, '(vl-load-com) (setvar "OSMODE" 0) (setvar "ORTHOMODE" 0) '
                  '(setvar "DYNMODE" 0) (setvar "DIMLFAC" 100.0) '
                  '(setvar "FIELDEVAL" 31)\n')
        # Reproduce the native cause in this same disposable process.
        send(doc, '(command "_.dimaligned" "_non" \'(0 0 0) "_non" \'(3 4 0) '
                  '"_non" \'(1.4 5.2 0))\n'
                  '(command "_.dimcontinue" "_non" \'(6 8 0) "" "")\n')
        old_types = retry(lambda: [obj.ObjectName for obj in list(doc.ModelSpace)])
        print(f'Native DIMALIGNED + DIMCONTINUE: {old_types}', flush=True)
        for obj in retry(lambda: list(doc.ModelSpace)):
            obj.Delete()
        send(doc, f'(load {lisp_string(root / "lisps/CEVIADA.lsp")})\n'
                  f'(load {lisp_string(helper)})\n'
                  '(setq *ang_esviaje* nil *prec_cota_recta* nil)\n')

        def dimensions():
            return retry(lambda: {obj.Handle: obj for obj in list(doc.ModelSpace)
                                  if 'Dimension' in obj.ObjectName})

        def inspect(label, objects, lengths, offset):
            output = folder / f'{label}.txt'
            send(doc, '_.REGEN\n' + f'(CEVT:Dump {lisp_string(output)})\n')
            rows = retry(lambda: [line.split('|') for line in output.read_text().splitlines()])
            selected = [row for row in rows if row[0] in objects]
            assert len(selected) == len(lengths), (label, selected, lengths)
            for row, length in zip(selected, lengths):
                h, kind, measure, off, field, target = row
                assert kind == '1', (label, 'not aligned', row)
                assert objects[h].ObjectName == 'AcDbAlignedDimension', (label, row)
                assert math.isclose(float(measure), length * 100, abs_tol=1e-6), (label, row)
                assert math.isclose(float(off), offset, abs_tol=1e-6), (label, row)
                assert target == h, (label, 'field references wrong dimension', row)
                expected = length * 100 * round(math.cos(math.radians(30)), 8)
                assert math.isclose(float(field), expected, abs_tol=1e-5), (label, row, expected)
            print(f'PASS {label}: {len(selected)} aligned dimensions, distances, placement and fields', flush=True)

        existing = dimensions()
        send(doc, 'CEV\n30\n2\n0,0\n3,4\n1.4,5.2\n6,8\n10,8\n10,8\n10,12\n\n')
        created = {h: obj for h, obj in dimensions().items() if h not in existing}
        inspect('bent-chain-and-duplicate-point', created, [5, 5, 4, 4], 2)

        # Moving an endpoint must change actual length/direction and its field.
        last = list(created.values())[-1]
        last.ExtLine2Point = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (13., 12., 0.))
        send(doc, f'(command "_.updatefield" (handent "{last.Handle}") "")\n')
        # The changed dimension's offset is adjusted by CAD; inspect the field
        # separately from the initial placement assertion.
        assert math.isclose(last.Measurement, 500, abs_tol=1e-6)
        assert last.ObjectName == 'AcDbAlignedDimension'
        output = folder / 'endpoint-edit.txt'
        send(doc, f'(CEVT:Dump {lisp_string(output)})\n')
        row = next(line.split('|') for line in output.read_text().splitlines() if line.startswith(last.Handle + '|'))
        assert row[5] == last.Handle and math.isclose(float(row[4]), 433.0127, abs_tol=1e-5), row
        print('PASS endpoint edit: aligned type, true length and updated self-linked field', flush=True)

        existing = dimensions()
        send(doc, 'CEVIADA\n20,0\n15,0\n15,2\n15,4\n\n')
        created = {h: obj for h, obj in dimensions().items() if h not in existing}
        inspect('reversed-points-negative-offset', created, [5, 4], -2)

        send(doc, '(command "_.ucs" "_z" 37.0) (command "_.ucs" "_x" 25.0)\n')
        existing = dimensions()
        send(doc, 'CEV\n0,0\n3,4\n1.4,5.2\n6,8\n\n')
        created = {h: obj for h, obj in dimensions().items() if h not in existing}
        inspect('rotated-and-tilted-ucs', created, [5, 5], 2)

        # Enter before the first point must finish without creating a dimension.
        existing = set(dimensions())
        send(doc, 'CEV\n\n')
        assert set(dimensions()) == existing
        assert retry(lambda: doc.GetVariable('CMDACTIVE')) == 0
        print('DONE failures=0', flush=True)
        return 0
    finally:
        close_owned(app, handle, pid)


if __name__ == '__main__':
    raise SystemExit(main())
