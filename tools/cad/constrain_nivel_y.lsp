;;; Authoring helper: run only on a disposable copy of the master.
;;; Keeps the Point parameter (id 85) and its signed UpdatedY fields intact.
;;; acYDistance=2 makes the associated Move action use only the Y delta.
(vl-load-com)
(defun SNY:Author (/ name ss i obj move point)
  (foreach name '("NIVEL" "NIVEL_MM")
    (command-s "_.BEDIT" name)
    (setq ss (ssget "_X") move nil point nil)
    (repeat (setq i (sslength ss))
      (setq obj (vlax-ename->vla-object (ssname ss (setq i (1- i)))))
      (cond
        ((= "AcDbBlockMoveActionEntity" (vla-get-ObjectName obj))
         (if move (progn (princ "Multiple Move actions; aborting.") (exit)))
         (setq move obj))
        ((= "AcDbBlockPointParameterEntity" (vla-get-ObjectName obj))
         (if (= "BASE A NIVEL" (vlax-get obj 'PositionName)) (setq point obj)))))
    (if (not (and move point)) (progn (princ "Unexpected NIVEL definition.") (exit)))
    (vlax-put-property move 'DistanceType 2)
    (if (/= 2 (vlax-get move 'DistanceType)) (exit))
    (command-s "_.BCLOSE" "_Save"))
  (princ))
