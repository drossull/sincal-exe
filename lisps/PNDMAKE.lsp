;;; PNDMAKE: pendiente absoluta en el plano XY del UCS actual.
;;; Rota el objeto completo; no estira ni asigna pendientes Z de obra civil.
(vl-load-com)

(defun PNDM:Fail (msg) (princ (strcat "\n[PNDMAKE] " msg)) (quit))

(defun PNDM:Delta (p q percent / dx dy a)
  (setq dx (- (car q) (car p)) dy (- (cadr q) (cadr p)))
  (cond
    ((not (equal (caddr p) (caddr q) 1e-8))
      (PNDM:Fail "El eje de referencia debe ser paralelo al plano XY del UCS."))
    ((< (sqrt (+ (* dx dx) (* dy dy))) 1e-10)
      (PNDM:Fail "Los puntos de referencia deben ser distintos.")))
  ;; Orientacion de eje, no de vector: evitar giros innecesarios de 180 grados.
  (setq a (- (atan (/ percent 100.0)) (atan dy dx)))
  (while (> a (/ pi 2.0)) (setq a (- a pi)))
  (while (< a (- (/ pi 2.0))) (setq a (+ a pi)))
  a)

(defun PNDM:Apply (obj base p q percent / a axis)
  (setq a (PNDM:Delta p q percent)
        axis (mapcar '+ base '(0.0 0.0 1.0)))
  (vla-Rotate3D obj (vlax-3d-point (trans base 1 0))
    (vlax-3d-point (trans axis 1 0)) a))

(defun c:PNDMAKE (/ *error* ss ent ed obj doc opened p q base percent)
  (defun *error* (msg)
    (if opened (vl-catch-all-apply 'vla-EndUndoMark (list doc)))
    (if (and msg (not (wcmatch (strcase msg) "*CANCEL*,*QUIT*,*EXIT*,*BREAK*")))
      (princ (strcat "\n[PNDMAKE] " msg)))
    (princ))
  (setq ss (ssget "_I"))
  (cond
    ((and ss (= 1 (sslength ss))) (setq ent (ssname ss 0)))
    (T (setq ent (car (entsel "\n[PNDMAKE] Seleccione un objeto: ")))))
  (if ent
    (progn
      (setq ed (entget ent) obj (vlax-ename->vla-object ent))
      (if (= 4 (logand 4 (cdr (assoc 70 (tblsearch "LAYER" (cdr (assoc 8 ed)))))))
        (PNDM:Fail "La capa del objeto esta bloqueada."))
      (if (or (= "VIEWPORT" (cdr (assoc 0 ed)))
              (not (vlax-method-applicable-p obj 'Rotate3D)))
        (PNDM:Fail "Este tipo de objeto no admite esta rotacion."))
      (if (= "LINE" (cdr (assoc 0 ed)))
        (setq p (trans (cdr (assoc 10 ed)) 0 1)
              q (trans (cdr (assoc 11 ed)) 0 1))
        (progn
          (setq p (getpoint "\nPrimer punto del eje o tramo de referencia: "))
          (if p (setq q (getpoint p "\nSegundo punto del eje o tramo de referencia: ")))))
      (if (and p q)
        (progn
          ;; Validate before any write. No changes to ANGBASE, ANGDIR or UCS.
          (PNDM:Delta p q 0.0)
          (setq base (getpoint p "\nPunto fijo de giro <primer punto del eje>: "))
          (if (null base) (setq base p))
          (setq percent (getreal "\nPendiente final en porcentaje (10, -10, 0; sin %): "))
          (if percent
            (progn
              (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
              (vla-StartUndoMark doc)
              (setq opened T)
              (PNDM:Apply obj base p q percent)
              (vla-EndUndoMark doc)
              (setq opened nil)
              (princ (strcat "\n[PNDMAKE] Pendiente aplicada: " (rtos percent 2 4)
                "%. Se conserva la forma y longitud del objeto."))))))))
  (princ))

(princ "\nPNDMAKE cargado: orientar un objeto mediante pendiente porcentual.")
(princ)
