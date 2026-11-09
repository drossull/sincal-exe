;;; Read-only verification after New Revision, in a disposable CAD copy.
;;; (SRFT:Check "TABLE_HANDLE" "EXPECTED_REVISION") must return T.
(vl-load-com)

(defun SRFT:Tree (field expected seen / data valid pair)
  (setq data (entget field))
  (setq valid (and data (not (member field seen))
                   (= "FIELD" (cdr (assoc 0 data)))
                   (equal expected (cdr (assoc 91 data)))))
  (if valid
    (foreach pair data
      (if (= 360 (car pair))
        (if (not (SRFT:Tree (cdr pair) expected (cons field seen)))
          (setq valid nil)))))
  valid)

(defun SRFT:Check (table-handle expected-revision / doc table valid column id field data)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object))
        table (vla-HandleToObject doc table-handle)
        valid (and (= "AcDbTable" (vla-get-ObjectName table))
                   (= expected-revision (vla-GetText table 0 0))))
  ;; These four cells are the documented CustomDP fields in the revision row.
  (foreach column '(0 1 2 5)
    (setq id (vla-GetFieldId table 0 column))
    (if (and id (/= id 0))
      (progn
        (setq field (handent (vla-get-Handle (vla-ObjectIDToObject doc id)))
              data (entget field))
        ;; This fixture uses an automatic parent. Its embedded evaluator must
        ;; remain automatic as well, including after Save and Reopen.
        (if (not (and (equal 63 (cdr (assoc 91 data))) (SRFT:Tree field 63 nil)))
          (setq valid nil)))
      (setq valid nil)))
  (princ (if valid "\nPASS: revision Fields remain automatic."
                   "\nFAIL: revision text or nested evaluation options differ."))
  valid)

(princ)
