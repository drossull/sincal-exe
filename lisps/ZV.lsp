;;; ============================================================================
;;; ZV.LSP
;;; Comando: ZV
;;;
;;; Encuadra el tercio inferior derecho de la hoja del layout actual.
;;; Si el usuario está dentro de un viewport, vuelve primero a espacio papel.
;;; Compatible con AutoCAD 2025/2027 y ZWCAD 2026 para Windows.
;;; ============================================================================

(vl-load-com)

(defun c:ZV (/ *error* app doc layout ancho alto rotacion temporal intento p1 p2)
  (defun *error* (mensaje)
    (if
      (and
        mensaje
        (not (wcmatch (strcase mensaje) "*CANCEL*,*EXIT*,*BREAK*"))
      )
      (princ (strcat "\n[ZV] Error: " mensaje))
    )
    (princ)
  )

  (cond
    ((= 1 (getvar "TILEMODE"))
      (princ "\n[ZV] Activa primero una pestaña de Layout.")
    )
    (T
      ;; CVPORT > 1 indica que el usuario está trabajando dentro de un viewport.
      (if (> (getvar "CVPORT") 1)
        (vl-cmdf "_.PSPACE")
      )

      (setq app    (vlax-get-acad-object)
            doc    (vla-get-ActiveDocument app)
            layout (vla-get-ActiveLayout doc)
            intento
              (vl-catch-all-apply
                'vla-GetPaperSize
                (list layout 'ancho 'alto)
              )
      )

      (cond
        ((vl-catch-all-error-p intento)
          (princ
            "\n[ZV] No se pudo leer el tamaño de papel. Revisa la configuración de página del layout."
          )
        )
        ((or (not (numberp ancho)) (not (numberp alto)) (<= ancho 0.0) (<= alto 0.0))
          (princ "\n[ZV] El layout no tiene un tamaño de papel válido.")
        )
        (T
          ;; En rotaciones de 90 y 270 grados, ancho y alto se intercambian en pantalla.
          (setq rotacion (vla-get-PlotRotation layout))
          (if (or (= rotacion 1) (= rotacion 3))
            (setq temporal ancho
                  ancho    alto
                  alto     temporal
            )
          )

          ;; Cuadricula 3 x 3: columna derecha y fila inferior.
          (setq p1 (vlax-3d-point (list (* ancho (/ 2.0 3.0)) 0.0 0.0))
                p2 (vlax-3d-point (list ancho (/ alto 3.0) 0.0))
                intento (vl-catch-all-apply 'vla-ZoomWindow (list app p1 p2))
          )

          (if (vl-catch-all-error-p intento)
            (princ "\n[ZV] No fue posible aplicar el zoom en este layout.")
            (princ "\n[ZV] Zoom aplicado al tercio inferior derecho del layout.")
          )
        )
      )
    )
  )
  (princ)
)

(princ "\nZV cargado. Escriba ZV para ampliar el tercio inferior derecho del layout.")
(princ)
