;;; ROMAND - configura solamente el estilo RomanD del dibujo actual.
;;; romand.shx, anotativo, papel 2.5, ancho 0.8, sin efectos.
;;; No convierte textos existentes ni elimina sus formatos particulares.
;;; Usa -STYLE nativo; no requiere ActiveX ni el master.

(defun SRD:Flag (data app / item value)
  (foreach item (cdr (assoc app (cdr (assoc -3 data))))
    (if (= (car item) 1070) (setq value (cdr item))))
  value)

(defun SRD:Valid (/ data)
  (and (setq data (tblobjname "STYLE" "RomanD"))
    (setq data (entget data '("AcadAnnotative" "AcadAnnoPO")))
    (= (strcase (cdr (assoc 3 data))) "ROMAND.SHX")
    (= (cdr (assoc 4 data)) "")
    (equal (cdr (assoc 40 data)) 2.5 1e-9)
    (equal (cdr (assoc 41 data)) 0.8 1e-9)
    (equal (cdr (assoc 50 data)) 0.0 1e-9)
    (= (logand (cdr (assoc 70 data)) 5) 0)
    (= (cdr (assoc 71 data)) 0)
    (= (SRD:Flag data "AcadAnnotative") 1)
    (not (equal (SRD:Flag data "AcadAnnoPO") 1))))

(defun c:ROMAND (/ *error* echo oldstyle previous apps)
  (setq echo (getvar "CMDECHO") oldstyle (getvar "TEXTSTYLE"))
  ;; Snapshot only the style and the two annotation applications we change.
  (if (setq previous (tblobjname "STYLE" "RomanD"))
    (progn
      (setq previous (entget previous '("AcadAnnotative" "AcadAnnoPO"))
            apps (cdr (assoc -3 previous)))
      (setq previous
        (append (vl-remove-if '(lambda (item) (= (car item) -3)) previous)
          (list (list -3
            (if (assoc "AcadAnnotative" apps) (assoc "AcadAnnotative" apps) '("AcadAnnotative"))
            (if (assoc "AcadAnnoPO" apps) (assoc "AcadAnnoPO" apps) '("AcadAnnoPO"))))))))
  (defun *error* (msg)
    (if previous (entmod previous))
    (setvar "TEXTSTYLE" oldstyle)
    (setvar "CMDECHO" echo)
    (if msg (princ (strcat "\nROMAND: " msg)))
    (princ "\nNo se completo la configuracion. Revise el estilo RomanD.")
    (princ))
  (cond
    ((not (findfile "romand.shx"))
      (princ "\nROMAND: no se encuentra romand.shx. No se modifico el dibujo."))
    (T
      (setvar "CMDECHO" 0)
      ;; RomanD admite orientacion vertical: responder No a los tres efectos.
      (command "_.-STYLE" "RomanD" "romand.shx"
        "_Annotative" "_Yes" "_No" 2.5 0.8 0.0 "_No" "_No" "_No")
      (if (not (SRD:Valid))
        (*error* "No se pudo verificar la configuracion.")
        (progn
          (setvar "TEXTSTYLE" "RomanD")
          (command "_.REGENALL")
          (setvar "CMDECHO" echo)
          (princ "\nRomanD actual: romand.shx, anotativo, papel 2.5, ancho 0.8, angulo 0; sin volteos ni orientacion al layout.")))))
  (princ))

(princ "\nROMAND cargado: configurar el estilo RomanD anotativo (2.5 / 0.8).")
(princ)
