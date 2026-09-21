;;; ============================================================================
;;; BTORIENT.LSP
;;; Comando: BTORIENT
;;;
;;; Orienta una referencia de bloque completa mediante dos puntos.
;;; El sentido del primer punto al segundo define la nueva rotacion absoluta.
;;; Solo cambia la insercion seleccionada; no modifica la definicion del bloque.
;;; Compatible con AutoCAD 2025/2027 y ZWCAD 2026 para Windows.
;;; ============================================================================

(vl-load-com)

(defun BTO:SeleccionarBloque (/ preseleccion seleccion)
  ;; Aprovecha una preseleccion valida de un unico bloque.
  (setq preseleccion (ssget "_I" '((0 . "INSERT"))))
  (cond
    ((and preseleccion (= 1 (sslength preseleccion)))
      (ssname preseleccion 0)
    )
    (T
      (while
        (and
          (setq seleccion
            (entsel "\n[BTORIENT] Seleccione el bloque que desea orientar: ")
          )
          (/= "INSERT" (cdr (assoc 0 (entget (car seleccion)))))
        )
        (princ "\n[BTORIENT] El objeto seleccionado no es una referencia de bloque.")
      )
      (if seleccion (car seleccion))
    )
  )
)

(defun c:BTORIENT (/ *error* app doc entidad objeto punto-1 punto-2 punto-1-ocs punto-2-ocs angulo intento undo-abierto)
  (defun *error* (mensaje)
    (if undo-abierto
      (vl-catch-all-apply 'vla-EndUndoMark (list doc))
    )
    (if
      (and
        mensaje
        (not (wcmatch (strcase mensaje) "*CANCEL*,*EXIT*,*BREAK*"))
      )
      (princ (strcat "\n[BTORIENT] Error: " mensaje))
    )
    (princ)
  )

  (if (setq entidad (BTO:SeleccionarBloque))
    (progn
      (setq punto-1
        (getpoint "\n[BTORIENT] Primer punto de alineacion: ")
      )
      (if punto-1
        (setq punto-2
          (getpoint punto-1 "\n[BTORIENT] Segundo punto de alineacion: ")
        )
      )

      (cond
        ((or (null punto-1) (null punto-2))
          (princ "\n[BTORIENT] Operacion cancelada.")
        )
        ((equal punto-1 punto-2 1.0e-12)
          (princ "\n[BTORIENT] Los dos puntos deben ser diferentes.")
        )
        (T
          ;; TRANS convierte los puntos desde el UCS actual al OCS del bloque.
          ;; Esto permite obtener el angulo correcto incluso con un UCS girado.
          (setq punto-1-ocs (trans punto-1 1 entidad)
                punto-2-ocs (trans punto-2 1 entidad)
                angulo      (angle punto-1-ocs punto-2-ocs)
                app         (vlax-get-acad-object)
                doc         (vla-get-ActiveDocument app)
                objeto      (vlax-ename->vla-object entidad)
          )

          (vla-StartUndoMark doc)
          (setq undo-abierto T
                intento
                  (vl-catch-all-apply
                    'vla-put-Rotation
                    (list objeto angulo)
                  )
          )
          (vla-EndUndoMark doc)
          (setq undo-abierto NIL)

          (if (vl-catch-all-error-p intento)
            (princ
              "\n[BTORIENT] No fue posible rotar el bloque; revisa si su capa esta bloqueada."
            )
            (progn
              (vla-Update objeto)
              (vla-Regen doc 1)
              (princ
                (strcat
                  "\n[BTORIENT] Bloque orientado a "
                  (angtos angulo (getvar "AUNITS") (getvar "AUPREC"))
                  "."
                )
              )
            )
          )
        )
      )
    )
    (princ "\n[BTORIENT] No se selecciono ningun bloque.")
  )
  (princ)
)

(princ "\nBTORIENT cargado. Escriba BTORIENT para alinear un bloque mediante dos puntos.")
(princ)
