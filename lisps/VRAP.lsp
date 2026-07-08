(defun c:VRAP ( / p1 p2 pCentro dict item obj objData scaleName scaleList dcl_file file dcl_id chosenScale dcl_status listalayouts layoutElegido )
  (vl-load-com)

  ;; 1. Verificar que estamos en el espacio Modelo
  (if (/= (getvar "CTAB") "Model")
    (progn
      (alert "Por favor, ejecuta el comando VRAP desde la pestaña 'Model'.")
      (exit)
    )
  )

  ;; 2. Seleccionar el área en el Modelo de forma segura
  (setq p1 (getpoint "\nSelecciona la primera esquina del rectángulo de selección: "))
  (if (not p1) (progn (princ "\nComando cancelado.") (exit)))
  
  (setq p2 (getcorner p1 "\nSelecciona la esquina contraria: "))
  (if (not p2) (progn (princ "\nComando cancelado.") (exit)))
  
  ;; Calcular el punto medio (centro) de la selección
  (setq pCentro (list 
                  (/ (+ (car p1) (car p2)) 2.0)
                  (/ (+ (cadr p1) (cadr p2)) 2.0)
                  0.0
                )
  )

  ;; 3. Obtener la lista de escalas de forma BLINDADA
  (setq scaleList nil)
  (if (setq dict (dictsearch (namedobjdict) "ACAD_SCALES"))
    (foreach item dict
      ;; Verificar que el ítem sea una lista válida y sea una referencia de objeto (código 350)
      (if (and item (listp item) (= (car item) 350))
        (progn
          (setq objData (entget (cdr item)))
          ;; Si el objeto existe en la base de datos, extraer su nombre (código 300)
          (if objData
            (progn
              (setq scaleName (assoc 300 objData))
              (if scaleName
                ;; Insertar el nombre de la escala a la lista de forma segura
                (setq scaleList (cons (cdr scaleName) scaleList))
              )
            )
          )
        )
      )
    )
  )
  
  ;; Si la lista está vacía, detener el programa antes de que AutoCAD lance un error
  (if (not scaleList)
    (progn
      (alert "No se encontraron escalas válidas en este dibujo.")
      (exit)
    )
  )
  
  ;; Invertir la lista para que quede en el orden original del diccionario
  (setq scaleList (reverse scaleList))

  ;; 4. Crear una ventana de diálogo (DCL) temporal
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

  ;; Llenar el menú desplegable
  (start_list "lista_escalas")
  (mapcar 'add_list scaleList)
  (end_list)

  ;; Valores por defecto y acciones
  (set_tile "lista_escalas" "0")
  (setq chosenScale (nth 0 scaleList))
  (action_tile "lista_escalas" "(setq chosenScale (nth (atoi $value) scaleList))")
  (action_tile "accept" "(done_dialog 1)")
  (action_tile "cancel" "(done_dialog 0)")

  ;; Mostrar diálogo y capturar respuesta
  (setq dcl_status (start_dialog))
  (unload_dialog dcl_id)
  (vl-file-delete dcl_file)

  ;; Si el usuario presiona Cancelar
  (if (= dcl_status 0)
    (progn (princ "\nComando VRAP cancelado por el usuario.") (exit))
  )

  ;; 5. Cambiar al primer layout disponible de manera segura
  (setq listalayouts (layoutlist))
  (if listalayouts
    (progn
      (setq layoutElegido (car listalayouts))
      (setvar "CTAB" layoutElegido)
      
      ;; 6. Cambiar a la capa "Viewport layer"
      (if (tblsearch "LAYER" "Viewport layer")
        (setvar "CLAYER" "Viewport layer")
      )

      ;; 7. Crear el Viewport de 300x100 mm centrado en la coordenada (0,0)
      (command "_.MVIEW" '(-150.0 -50.0 0.0) '(150.0 50.0 0.0))
      
      ;; 8. Entrar al Viewport
      (command "_.MSPACE")
      
      ;; Centrar el dibujo en las coordenadas capturadas
      (command "_.ZOOM" "_C" pCentro "")
      
      ;; 9. Aplicar la escala DESDE ADENTRO del viewport (Sincroniza zoom y anotación)
      (command "_.CANNOSCALE" chosenScale)
      
      ;; 10. Salir al Layout (Espacio Papel) y bloquear el viewport
      (command "_.PSPACE")
      (command "_.MVIEW" "_L" "_ON" "_L")
      
      (princ (strcat "\n¡Éxito! Viewport creado con escala " chosenScale " y bloqueado."))
    )
    (alert "No se encontró ninguna pestaña de Layout en este dibujo.")
  )
  (princ)
)