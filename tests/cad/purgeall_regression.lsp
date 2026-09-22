;;; Run ONLY in a disposable drawing; creates scales and test geometry.
;;; With SINCAL_TEST_ROOT set, run purgeall_regression.scr in accoreconsole.
(defun sincal:test-scale-present-p (name / data item found)
  (setq data (dictsearch (namedobjdict) "ACAD_SCALELIST"))
  (foreach item data
    (if (and (= (car item) 350)
             (= (cdr (assoc 300 (entget (cdr item)))) name))
      (setq found T)))
  found)

(defun sincal:test-purgeall (/ entity before first-pass second-pass)
  (command "_.-SCALELISTEDIT" "_Add" "SINCAL_TEST_CURRENT" "1:37" "_Exit")
  (command "_.-SCALELISTEDIT" "_Add" "SINCAL_TEST_UNUSED" "1:73" "_Exit")
  (setvar "CANNOSCALE" "SINCAL_TEST_CURRENT")
  (setq entity (entmakex '((0 . "LINE") (10 0.0 0.0 0.0) (11 10.0 10.0 0.0)))
        before (entget entity))
  (if (not (and (sincal:test-scale-present-p "SINCAL_TEST_CURRENT")
                (sincal:test-scale-present-p "SINCAL_TEST_UNUSED")))
    (princ "\nPURGEALL_REGRESSION: FAIL setup")
    (progn
      (setvar "CMDECHO" 0)
      (c:PURGEALL)
      (setq first-pass
        (and (sincal:test-scale-present-p "SINCAL_TEST_CURRENT")
             (not (sincal:test-scale-present-p "SINCAL_TEST_UNUSED"))
             (= (getvar "CANNOSCALE") "SINCAL_TEST_CURRENT")
             (= (getvar "CMDECHO") 0)
             (equal before (entget entity))))
      (setvar "CMDECHO" 1)
      (c:PURGEALL)
      (setq second-pass
        (and (sincal:test-scale-present-p "SINCAL_TEST_CURRENT")
             (not (sincal:test-scale-present-p "SINCAL_TEST_UNUSED"))
             (= (getvar "CANNOSCALE") "SINCAL_TEST_CURRENT")
             (= (getvar "CMDECHO") 1)
             (equal before (entget entity))))
      (princ (if (and first-pass second-pass)
        "\nPURGEALL_REGRESSION: PASS"
        "\nPURGEALL_REGRESSION: FAIL"))))
  (princ))
