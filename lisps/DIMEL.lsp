;;; =========================================================================
;;; COMANDO: DIMEL
;;; Traza una línea de corte, genera cotas automáticas y las aísla en su capa
;;; =========================================================================
(defun c:DIMEL (/ origOrtho origOsmode origCmdecho origLayer pt1 pt2 tempLine 
                vlaTempLine ss i obj intVar err bnd ptsArr allPts 
                cleanPts isHoriz dimLoc pA pB)
  (vl-load-com)
  
  ;; 1. Guardar variables y capa del usuario
  (setq origOrtho (getvar "ORTHOMODE"))
  (setq origOsmode (getvar "OSMODE"))
  (setq origCmdecho (getvar "CMDECHO"))
  (setq origLayer (getvar "CLAYER"))
  (setvar "CMDECHO" 0)

  (princ "\n--- HERRAMIENTA DE ACOTADO AUTOMÁTICO (DIMEL) ---")
  (setq pt1 (getpoint "\n1. Especifique el primer punto de la línea de corte: "))

  (if pt1
    (progn
      (setvar "ORTHOMODE" 1) ; Forzamos ortogonalidad
      (setq pt2 (getpoint pt1 "\n2. Especifique el punto final de la línea de corte: "))
    )
  )

  (if (and pt1 pt2)
    (progn
      ;; 2. Gestión de Capa ES-ACOTADO
      (if (not (tblsearch "LAYER" "ES-ACOTADO"))
        ;; Si no existe, la crea (color 3 - Verde por defecto)
        (command "_.-LAYER" "_Make" "ES-ACOTADO" "_Color" "3" "" "")
        ;; Si ya existe, simplemente la define como actual
        (setvar "CLAYER" "ES-ACOTADO")
      )

      ;; 3. Crear línea temporal invisible
      (entmake (list '(0 . "LINE") (cons 10 pt1) (cons 11 pt2)))
      (setq tempLine (entlast))
      (setq vlaTempLine (vlax-ename->vla-object tempLine))

      ;; 4. Seleccionar objetos que cruzan (Fence)
      (setq ss (ssget "F" (list pt1 pt2)))
      (setq allPts nil)

      (if ss
        (progn
          (setq i 0)
          (while (< i (sslength ss))
            (setq obj (vlax-ename->vla-object (ssname ss i)))
            (if (not (equal (ssname ss i) tempLine))
              (progn
                (setq intVar (vla-IntersectWith vlaTempLine obj 0)) 
                (setq err (vl-catch-all-apply 'vlax-variant-value (list intVar)))
                
                (if (not (vl-catch-all-error-p err))
                  (progn
                    (setq bnd (vl-catch-all-apply 'vlax-safearray-get-u-bound (list err 1)))
                    (if (and (not (vl-catch-all-error-p bnd)) (>= bnd 0))
                      (progn
                        (setq ptsArr (vlax-safearray->list err))
                        (while ptsArr
                          (setq allPts (cons (list (car ptsArr) (cadr ptsArr) (caddr ptsArr)) allPts))
                          (setq ptsArr (cdddr ptsArr))
                        )
                      )
                    )
                  )
                )
              )
            )
            (setq i (1+ i))
          )
        )
      )

      ;; 5. Borrar la línea temporal
      (entdel tempLine)

      ;; 6. Filtrar y ordenar los puntos encontrados
      (if allPts
        (progn
          ;; Eliminar duplicados (Tolerancia 0.001)
          (setq cleanPts nil)
          (foreach pt allPts
            (if (not (vl-some '(lambda (p) (equal p pt 0.001)) cleanPts))
              (setq cleanPts (cons pt cleanPts))
            )
          )

          ;; Determinar eje y ordenar
          (setq isHoriz (equal (cadr pt1) (cadr pt2) 0.001))

          (if isHoriz
            (setq cleanPts (vl-sort cleanPts '(lambda (p1 p2) (< (car p1) (car p2))))) 
            (setq cleanPts (vl-sort cleanPts '(lambda (p1 p2) (< (cadr p1) (cadr p2))))) 
          )

          ;; 7. Generar las cotas
          (if (>= (length cleanPts) 2)
            (progn
              (setvar "OSMODE" origOsmode)
              (setq dimLoc (getpoint pt1 "\n3. Haga clic para ubicar la línea de cotas: "))

              (if dimLoc
                (progn
                  (setvar "OSMODE" 0) 
                  (setq i 0)
                  (while (< i (1- (length cleanPts)))
                    (setq pA (nth i cleanPts))
                    (setq pB (nth (1+ i) cleanPts))
                    (command "_.DIMLINEAR" "_non" pA "_non" pB "_non" dimLoc)
                    (setq i (1+ i))
                  )
                  (princ (strcat "\n[SINCAL] " (itoa i) " cotas generadas en la capa ES-ACOTADO."))
                )
                (princ "\n[!] Operación cancelada.")
              )
            )
            (princ "\n[!] No hay suficientes intersecciones para acotar (mínimo 2).")
          )
        )
        (princ "\n[!] La línea de corte no cruza con ningún objeto válido.")
      )
    )
  )

  ;; 8. Restaurar entorno original
  (setvar "ORTHOMODE" origOrtho)
  (setvar "OSMODE" origOsmode)
  (setvar "CMDECHO" origCmdecho)
  (setvar "CLAYER" origLayer) ; Devuelve al usuario a su capa original
  (princ)
)