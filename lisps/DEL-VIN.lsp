;;; ============================================================================
;;; DEL-VIN.LSP
;;; Comando: DEL-VIN
;;;
;;; Elimina objetos de la vineta antigua por zonas fijas del layout.
;;; Solo revisa espacio papel y nunca elimina viewports.
;;; Compatible con AutoCAD 2025/2027 y ZWCAD 2026 para Windows.
;;; ============================================================================

(vl-load-com)

;; Zonas de limpieza: (X minima, Y minima, X maxima, Y maxima).
;; Las coordenadas corresponden a la hoja SINCAL de 841 x 605 unidades.
(setq DELVIN:Zonas
  '(
    (0.0   0.0   841.0  45.0)
    (674.0 0.0   841.0 138.0)
    (828.0 0.0   841.0 605.0)
    (0.0   0.0    40.0 605.0)
    (0.0 580.0   841.0 605.0)
  )
)

;; Devuelve T cuando dos rectangulos 2D se tocan o se superponen.
(defun DELVIN:IntersectaRectangulo (minimo maximo zona)
  (and
    (<= (car minimo)  (nth 2 zona))
    (>= (car maximo)  (nth 0 zona))
    (<= (cadr minimo) (nth 3 zona))
    (>= (cadr maximo) (nth 1 zona))
  )
)

;; Comprueba si la caja envolvente de un objeto intersecta alguna zona.
(defun DELVIN:EnZona (objeto / intento minimo maximo encontrado)
  (setq intento
    (vl-catch-all-apply
      'vla-GetBoundingBox
      (list objeto 'minimo 'maximo)
    )
  )
  (if (not (vl-catch-all-error-p intento))
    (progn
      (setq minimo (vlax-safearray->list minimo)
            maximo (vlax-safearray->list maximo)
      )
      (foreach zona DELVIN:Zonas
        (if (DELVIN:IntersectaRectangulo minimo maximo zona)
          (setq encontrado T)
        )
      )
    )
  )
  encontrado
)

;; Identifica los viewports por su clase DWG nativa.
(defun DELVIN:EsViewport (objeto)
  (= "ACDBVIEWPORT" (strcase (vla-get-ObjectName objeto)))
)

(defun c:DEL-VIN (/ *error* app doc layout bloque objeto objetos seleccion cantidad respuesta eliminados fallidos undo-abierto)
  (defun *error* (mensaje)
    (sssetfirst NIL NIL)
    (if undo-abierto
      (vl-catch-all-apply 'vla-EndUndoMark (list doc))
    )
    (if
      (and
        mensaje
        (not (wcmatch (strcase mensaje) "*CANCEL*,*EXIT*,*BREAK*"))
      )
      (princ (strcat "\n[DEL-VIN] Error: " mensaje))
    )
    (princ)
  )

  (cond
    ((= 1 (getvar "TILEMODE"))
      (princ "\n[DEL-VIN] Activa primero el layout que contiene la vineta.")
    )
    (T
      ;; El comando trabaja siempre en espacio papel, incluso si se inicia
      ;; mientras el usuario esta dentro de un viewport.
      (if (> (getvar "CVPORT") 1)
        (vl-cmdf "_.PSPACE")
      )

      (setq app       (vlax-get-acad-object)
            doc       (vla-get-ActiveDocument app)
            layout    (vla-get-ActiveLayout doc)
            bloque    (vla-get-Block layout)
            seleccion (ssadd)
      )

      ;; Se recopilan primero los objetos; no se modifica el dibujo durante
      ;; la deteccion para que sea posible revisar y cancelar.
      (vlax-for objeto bloque
        (if
          (and
            (not (DELVIN:EsViewport objeto))
            (DELVIN:EnZona objeto)
          )
          (progn
            (setq objetos (cons objeto objetos))
            (ssadd (vlax-vla-object->ename objeto) seleccion)
          )
        )
      )

      (setq cantidad (sslength seleccion))
      (if (= cantidad 0)
        (princ "\n[DEL-VIN] No se encontraron objetos en las zonas de limpieza.")
        (progn
          ;; Destaca los candidatos para que el usuario pueda inspeccionarlos.
          (sssetfirst NIL seleccion)
          (initget "Si No")
          (setq respuesta
            (getkword
              (strcat
                "\n[DEL-VIN] Se detectaron "
                (itoa cantidad)
                " objeto(s), sin contar viewports. ¿Eliminar? [Si/No] <No>: "
              )
            )
          )
          (sssetfirst NIL NIL)

          (if (= respuesta "Si")
            (progn
              (vla-StartUndoMark doc)
              (setq undo-abierto T
                    eliminados   0
                    fallidos     0
              )
              (foreach objeto objetos
                (if
                  (vl-catch-all-error-p
                    (vl-catch-all-apply 'vla-Delete (list objeto))
                  )
                  (setq fallidos (1+ fallidos))
                  (setq eliminados (1+ eliminados))
                )
              )
              (vla-EndUndoMark doc)
              (setq undo-abierto NIL)
              (vla-Regen doc 1)
              (princ
                (strcat
                  "\n[DEL-VIN] Limpieza terminada: "
                  (itoa eliminados)
                  " objeto(s) eliminado(s)."
                )
              )
              (if (> fallidos 0)
                (princ
                  (strcat
                    " No se pudieron eliminar "
                    (itoa fallidos)
                    " objeto(s), posiblemente por capas bloqueadas."
                  )
                )
              )
            )
            (princ "\n[DEL-VIN] Operacion cancelada; el dibujo no fue modificado.")
          )
        )
      )
    )
  )
  (princ)
)

(princ "\nDEL-VIN cargado. Escriba DEL-VIN para limpiar la vineta antigua.")
(princ)
