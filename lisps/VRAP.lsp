(defun c:VRAP ( / p1 p2 pCentro escala layoutElegido vpEnt vpObj scaleFactor get-scale-factor )
  (vl-load-com)

  ;; Función interna para buscar el factor de zoom matemático en el diccionario de AutoCAD
  (defun get-scale-factor ( scaleName / dict factor item obj pUnits dUnits )
    (setq factor nil)
    (if (setq dict (dictsearch (namedobjdict) "ACAD_SCALES"))
      (foreach item dict
        (if (= (car item) 350)
          (progn
            (setq obj (entget (cdr item)))
            (if (= (strcase (cdr (assoc 300 obj))) (strcase scaleName))
              (progn
                (setq pUnits (cdr (assoc 140 obj)))
                (setq dUnits (cdr (assoc 143 obj)))
                (if (and pUnits dUnits (> dUnits 0.0))
                  ;; Convertimos a float para asegurar precisión con decimales
                  (setq factor (/ (float pUnits) (float dUnits)))
                )
              )
            )
          )
        )
      )
    )
    factor
  )

  ;; 1. Verificar que estamos en el espacio Modelo
  (if (/= (getvar "CTAB") "Model")
    (progn
      (alert "Por favor, ejecuta el comando VRAP desde la pestaña 'Model'.")
      (exit)
    )
  )

  ;; 2. Seleccionar el área en el Modelo y calcular su centro
  (setq p1 (getpoint "\nSelecciona la primera esquina del rectángulo de selección: "))
  (setq p2 (getcorner p1 "\nSelecciona la esquina contraria: "))
  
  (setq pCentro (list 
                  (/ (+ (car p1) (car p2)) 2.0)
                  (/ (+ (cadr p1) (cadr p2)) 2.0)
                  0.0
                )
  )

  ;; 3. Solicitar la escala (la letra 't' permite escribir espacios)
  (setq escala (getstring t "\nIngresa el nombre de la escala (ej. 1:250 m): "))

  ;; 4. Cambiar al único layout existente
  (setq layoutElegido (car (layoutlist)))
  (if layoutElegido
    (progn
      (setvar "CTAB" layoutElegido)
      
      ;; 5. Cambiar a la capa "Viewport layer"
      (if (tblsearch "LAYER" "Viewport layer")
        (setvar "CLAYER" "Viewport layer")
        (princ "\nNota: La capa 'Viewport layer' no se encontró, usando la actual.")
      )

      ;; 6. Crear el Viewport de 300x100 mm centrado en la coordenada (0,0) del Layout
      (command "_.MVIEW" '(-150.0 -50.0 0.0) '(150.0 50.0 0.0))
      
      ;; Capturar el Viewport recién creado para manipular sus propiedades directamente
      (setq vpEnt (entlast))
      (setq vpObj (vlax-ename->vla-object vpEnt))

      ;; 7. Entrar al Viewport y fijar el centro exacto
      (command "_.MSPACE")
      (command "_.ZOOM" "_C" pCentro "")
      
      ;; Actualizar la escala anotativa interna
      (vl-catch-all-apply 'setvar (list "CANNOSCALE" escala))
      
      ;; 8. Salir al Layout (Espacio Papel) para aplicar el zoom de forma segura
      (command "_.PSPACE")
      
      ;; 9. Buscar el factor de escala real y forzar el tamaño en el Viewport
      (setq scaleFactor (get-scale-factor escala))
      
      (if scaleFactor
        (progn
          ;; Forzar físicamente el acercamiento/zoom del Viewport
          (vla-put-CustomScale vpObj scaleFactor)
          
          ;; Bloquear el Viewport para que la escala no se pierda al hacer doble clic
          (vla-put-DisplayLocked vpObj :vlax-true)
          
          (princ (strcat "\n¡Éxito! Escala '" escala "' aplicada correctamente al zoom y Viewport bloqueado."))
        )
        (progn
          ;; Si te equivocas tipeando, te avisa en lugar de lanzar error
          (princ (strcat "\nADVERTENCIA: La escala '" escala "' no se encontró en tu lista. El centro está listo pero la escala no se ajustó."))
        )
      )
    )
    (alert "No se encontró ninguna pestaña de Layout en este dibujo.")
  )
  (princ)
)