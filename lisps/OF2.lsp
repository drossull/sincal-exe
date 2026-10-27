;;; OF2: offset a ambos lados, conservando el objeto original.
;;; La distancia indicada es POR LADO, en unidades del dibujo.
(vl-load-com)

(defun OF2:Pair (obj distance / created result signed batch item)
  ;; Un offset puede devolver varias curvas. Conservarlas todas y retirar
  ;; cualquier resultado parcial si el otro lado no se puede construir.
  (setq result
    (vl-catch-all-apply
      '(lambda ()
        (foreach signed (list distance (- distance))
          (setq batch (vlax-safearray->list
                        (vlax-variant-value (vla-Offset obj signed))))
          (setq created (append created batch))
          (if (null batch) (quit))))
      nil))
  (if (vl-catch-all-error-p result)
    (progn
      (foreach item created (vl-catch-all-apply 'vla-Delete (list item)))
      (list nil (vl-catch-all-error-message result)))
    (list T created)))

(defun c:OF2 (/ *error* doc opened ss ent data obj distance result)
  (defun *error* (msg)
    (if opened (vl-catch-all-apply 'vla-EndUndoMark (list doc)))
    (if (and msg (not (wcmatch (strcase msg) "*CANCEL*,*QUIT*,*EXIT*,*BREAK*")))
      (princ (strcat "\nOF2: " msg)))
    (princ))
  (setq ss (ssget "_I"))
  (if (and ss (= (sslength ss) 1))
    (setq ent (ssname ss 0))
    (progn
      (sssetfirst nil nil)
      (setq ent (car (entsel "\nSeleccione una linea o curva para offset a ambos lados: ")))))
  (if ent
    (progn
      (setq data (entget ent) obj (vlax-ename->vla-object ent))
      (cond
        ((or (not (vlax-method-applicable-p obj 'Offset))
             (and (= (cdr (assoc 0 data)) "POLYLINE")
                  (/= 0 (logand 88 (cdr (assoc 70 data))))))
          (princ "\nOF2 admite lineas, polilineas 2D y curvas compatibles con OFFSET; no bloques ni mallas."))
        ((/= 0 (logand 4 (cdr (assoc 70 (tblsearch "LAYER" (cdr (assoc 8 data)))))))
          (princ "\nLa capa del objeto esta bloqueada. Desbloqueela antes de usar OF2."))
        (T
          (initget 6)
          (setq distance (getdist
            (strcat "\nDistancia a CADA lado del eje"
              (if (and (numberp OF2:last) (> OF2:last 0.0))
                (strcat " <" (rtos OF2:last 2 6) ">") "") ": ")))
          (if (and (null distance) (numberp OF2:last)) (setq distance OF2:last))
          (if (and distance (> distance 0.0))
            (progn
              (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
              (vla-StartUndoMark doc)
              (setq opened T result (OF2:Pair obj distance))
              (vla-EndUndoMark doc)
              (setq opened nil)
              (if (car result)
                (progn
                  (setq OF2:last distance)
                  (princ (strcat "\nOF2: offset creado a ambos lados. Distancia por lado: "
                    (rtos distance 2 6) ". El original se conserva.")))
                (princ (strcat
                  "\nNo se pudieron generar ambos lados; no se dejan offsets parciales."
                  " Pruebe una distancia menor o revise la geometria. Detalle: " (cadr result))))))))))
  (princ))

(princ "\nOF2 cargado: offset a cada lado de una linea o curva.")
(princ)
