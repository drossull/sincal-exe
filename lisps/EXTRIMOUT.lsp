(defun c:EXTRIMOUT (/ *error* ent entData center radius ptOutside numPts ang step pts ssAll ssKeep i obj oldCmd oldHlt currentTab)
  
  (vl-load-com)

  ;; =========================================================================
  ;; 1. Función de manejo de errores (para garantizar que las variables se restauran)
  ;; =========================================================================
  (defun *error* (msg)
    (if oldCmd (setvar "CMDECHO" oldCmd))
    (if oldHlt (setvar "HIGHLIGHT" oldHlt)) ; Restaurar el resaltado azul obligatoriamente
    (if (and msg (not (member msg '("Function cancelled" "quit / exit abort"))))
      (princ (strcat "\nError: " msg))
    )
    (command "_.UNDO" "_End")
    (princ "\nRestauradas variables del sistema.")
    (princ)
  )

  ;; =========================================================================
  ;; 2. Preparación y Guardado de variables actuales
  ;; =========================================================================
  (command "_.UNDO" "_Begin")
  (setq oldCmd (getvar "CMDECHO"))
  (setq oldHlt (getvar "HIGHLIGHT"))
  (setvar "CMDECHO" 0)
  ;; Forzamos la restauración de HIGHLIGHT a 1 justo al inicio por si ya venía desactivado.
  (setvar "HIGHLIGHT" 1)
  (setq currentTab (getvar "CTAB")) ; Guardamos la pestaña actual (Model/Layout)

  ;; Asegurar que Express Tools esté cargado
  (if (not acet-dxf) (vl-catch-all-apply 'load '("acetutil.fas")))
  (if (not etrim) (load "extrim.lsp"))

  ;; =========================================================================
  ;; 3. Lógica Principal
  ;; =========================================================================
  (setq ent (car (entsel "\nSelecciona el círculo que servirá de límite: ")))

  (if ent
    (progn
      (setq entData (entget ent))
      (if (= (cdr (assoc 0 entData)) "CIRCLE")
        (progn
          (setq center (cdr (assoc 10 entData)))
          (setq radius (cdr (assoc 40 entData)))

          (princ "\nIniciando recorte y limpieza profunda (esto puede tardar si hay muchos bloques)...")

          ;; 3A. ZOOM al objeto para asegurar que AutoCAD vea todo lo necesario
          (command "_.ZOOM" "_Object" ent "")

          ;; 3B. Cortar las líneas que cruzan el círculo (EXTRIM clásico)
          ;; Calculamos un punto afuera lejano.
          (setq ptOutside (polar center 0.0 (* radius 10.0)))
          (etrim ent ptOutside)

          ;; 3C. Crear un polígono virtual de 128 lados para aproximar el círculo
          (setq numPts 128 ang 0.0 step (/ (* pi 2.0) numPts) pts nil)
          (repeat numPts
            (setq pts (cons (polar center ang radius) pts))
            (setq ang (+ ang step))
          )

          ;; 3D. ESCANEO GEOGRÁFICO:
          ;; Seleccionamos todo en el espacio actual.
          (setq ssAll (ssget "X" (list (cons 410 currentTab))))
          ;; Seleccionamos lo que está DENTRO o TOCA el círculo (Crossing Polygon).
          (setq ssKeep (ssget "_CP" pts (list (cons 410 currentTab))))

          ;; 3E. BORRADO SEGURO: Borrar lo que no está dentro del círculo.
          (if ssAll
            (progn
              (setq i 0)
              (repeat (sslength ssAll)
                (setq obj (ssname ssAll i))
                ;; Si la entidad actual NO pertenece al grupo protegido (ssKeep), se borra.
                (if (and ssKeep (not (ssmemb obj ssKeep)))
                  ;; Protección para no borrar el círculo límite en sí mismo
                  (if (not (equal obj ent))
                    (entdel obj)
                  )
                )
                (setq i (1+ i))
              )
            )
          )

          (command "_.ZOOM" "_Previous")
          (princ "\n¡Recorte, limpieza exterior profunda y borrado completados con éxito!")
        )
        (princ "\nError: El objeto seleccionado no es un círculo.")
      )
    )
    (princ "\nNo se seleccionó ningún objeto.")
  )

  ;; =========================================================================
  ;; 4. Limpieza final y Restauración
  ;; =========================================================================
  (*error* nil) ; Llama a la función error para restaurar variables limpia
  (princ)
)