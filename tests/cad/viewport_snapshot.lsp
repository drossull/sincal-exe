;; Snapshot the retained layout's floating viewports, without modifying anything.
(defun SINCAL:Snapshot (path / out ss i data pair)
  ;; Core Console does not materialize inactive layout viewports until activated.
  (setvar "CTAB" "Layout1")
  (setq out (open path "w") ss (ssget "X" '((0 . "VIEWPORT") (410 . "Layout1"))) i 0)
  (if ss (repeat (sslength ss)
    (setq data (entget (ssname ss i)) i (1+ i))
    (if (> (cdr (assoc 69 data)) 1)
      (foreach pair data
        (if (member (car pair) '(5 10 40 41 12 16 17 45 51 331 340))
          (write-line (vl-prin1-to-string pair) out))))))
  (close out))
