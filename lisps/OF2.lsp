;;; OF2: offset a ambos lados, conservando el objeto original.
;;; T = ancho total; L = distancia por lado, en unidades del dibujo.
;;; Se recuerda el modo en CAD y la ultima distancia por lado en este dibujo.
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

(defun c:OF2 (/ *error* doc opened ss ent data obj distance result mode reading default)
  (defun *error* (msg)
    (if opened (vl-catch-all-apply 'vla-EndUndoMark (list doc)))
    (if (and msg (not (wcmatch (strcase msg) "*CANCEL*,*QUIT*,*EXIT*,*BREAK*")))
      (princ (strcat "\nOF2: " msg)))
    (princ))
  (setq ss (ssget "_I"))
  (setq mode (if (= (getenv "SINCAL_OF2_MODO") "L") "Lado" "Total"))
  (setenv "SINCAL_OF2_MODO" (if (= mode "Total") "T" "L"))
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
          ;; OF2:last siempre guarda el offset real por lado. Convertir el
          ;; valor sugerido al cambiar de modo evita duplicar/reducir el ancho.
          ;; Pedir directamente la medida. T/L cambian el modo dentro de este
          ;; mismo paso, sin una pregunta de configuracion en cada ejecucion.
          (setq reading T)
          (while reading
            (setq default nil)
            (if (and (numberp OF2:last) (> OF2:last 0.0))
              (setq default (* OF2:last (if (= mode "Total") 2.0 1.0))))
            (initget 6 "Total Lado")
            (setq distance (getdist
              (strcat (if (= mode "Total") "\nAncho TOTAL del muro o columna"
                                           "\nDistancia a CADA lado del eje")
                " [Total/Lado]"
                (if default (strcat " <" (rtos default 2 6) ">") "") ": ")))
            (if (= (type distance) 'STR)
              (progn
                (setq mode distance)
                (setenv "SINCAL_OF2_MODO" (if (= mode "Total") "T" "L")))
              (progn
                (if (null distance) (setq distance default))
                (setq reading nil))))
          (if (and distance (> distance 0.0))
            (progn
              (if (= mode "Total") (setq distance (/ distance 2.0)))
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

(princ)
