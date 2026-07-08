(defun c:VRAP ( / p1 p2 pCentro dict item scaleList dcl_file file dcl_id chosenScale dcl_status layoutElegido )
  (vl-load-com)

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

  ;; 3. Obtener la lista de TODAS las escalas del dibujo
  (setq scaleList (list))
  (if (setq dict (dictsearch (namedobjdict) "ACAD_SCALES"))
    (foreach item dict
      (if (= (car item) 350)
        (setq scaleList (append scaleList (list (cdr (assoc 300 (entget (cdr item)))))))
      )
    )
  )

  ;; 4. Crear una ventana de diálogo (DCL) temporal para el menú desplegable
  (setq dcl_file (vl-filename-mktemp "escalas.dcl"))
  (setq file (open dcl_file "w"))
  (write-line "EscalasVRAP : dialog { label = \"Escala del Viewport\"; " file)
  (write-line "  : text { label = \"Selecciona la escala para el plano:\"; } " file)
  (write-line "  : popup_list { key = \"lista_escalas\"; width = 40; } " file)
  (write-line "  ok_cancel; " file)
  (write-line "} " file)
  (close file)

  ;; Cargar la ventana de diálogo
  (setq dcl_id (load_dialog dcl_file))
  (if (not (new_dialog "EscalasVRAP" dcl_id))
    (progn
      (alert "Error al cargar la interfaz de escalas.")
      (exit)
    )
  )

  ;; Llenar el menú desplegable con la lista de escalas
  (start_list "lista_escalas")
  (mapcar 'add_list scaleList)
  (end_list)

  ;; Establecer el primer valor por defecto
  (set_tile "lista_escalas" "0")
  (setq chosenScale (nth 0 scaleList))

  ;; Acciones al seleccionar y aceptar
  (action_tile "lista_escalas" "(setq chosenScale (nth (atoi $value) scaleList))")
  (action_tile "accept" "(done_dialog 1)")
  (action_tile "cancel" "(done_dialog 0)")

  ;; Mostrar diálogo y capturar respuesta
  (setq dcl_status (start_dialog))
  (unload_dialog dcl_id)
  (vl-file-delete dcl_file)

  ;; Si el usuario presiona Cancelar, salir del comando
  (if (= dcl_status 0)
    (progn (princ "\nComando VRAP cancelado.") (exit))
  )

  ;; 5. Cambiar al único layout existente
  (setq layoutElegido (car (layoutlist)))
  (if layoutElegido
    (progn
      (setvar "CTAB" layoutElegido)
      
      ;; 6. Cambiar a la capa "Viewport layer"
      (if (tblsearch "LAYER" "Viewport layer")
        (setvar "CLAYER" "Viewport layer")
      )

      ;; 7. Crear el Viewport de 300x100 mm centrado en la coordenada (0,0)
      (command "_.MVIEW" '(-150.0 -50.0 0.0) '(150.0 50.0 0.0))
      
      ;; 8. Entrar al Viewport (ESTE ES EL PASO CLAVE PARA LA ESCALA)
      (command "_.MSPACE")
      
      ;; Centrar el dibujo en las coordenadas capturadas
      (command "_.ZOOM" "_C" pCentro "")
      
      ;; 9. Aplicar la escala DESDE ADENTRO del viewport (Sincroniza zoom y anotación)
      (command "_.CANNOSCALE" chosenScale)
      
      ;; 10. Salir al Layout (Espacio Papel) y bloquear el viewport
      (command "_.PSPACE")
      (command "_.MVIEW" "_L" "_ON" "_L") ;; Bloquea el último viewport seleccionado
      
      (princ (strcat "\n¡Éxito! Viewport creado con escala " chosenScale " y bloqueado."))
    )
    (alert "No se encontró ninguna pestaña de Layout en este dibujo.")
  )
  (princ)
)