(defun c:VRAP ( / p1 p2 pCentro dict item scaleList dcl_file file dcl_id chosenScale dcl_status listalayouts layoutElegido )
  (vl-load-com)

  ;; 1. Verificar que estamos en el espacio Modelo
  (if (/= (getvar "CTAB") "Model")
    (progn
      (alert "Por favor, ejecuta el comando VRAP desde la pestaña 'Model'.")
      (exit)
    )
  )

  ;; 2. Seleccionar el área en el Modelo
  (setq p1 (getpoint "\nSelecciona la primera esquina del rectángulo de selección: "))
  (if (not p1) (progn (princ "\nComando cancelado.") (exit)))
  
  (setq p2 (getcorner p1 "\nSelecciona la esquina contraria: "))
  (if (not p2) (progn (princ "\nComando cancelado.") (exit)))
  
  ;; Calcular el punto medio (centro)
  (setq pCentro (list 
                  (/ (+ (car p1) (car p2)) 2.0)
                  (/ (+ (cadr p1) (cadr p2)) 2.0)
                  0.0
                )
  )

  ;; 3. Obtener la lista de escalas (MÉTODO INFALIBLE)
  (setq scaleList nil)
  (if (setq dict (dictsearch (namedobjdict) "ACAD_SCALES"))
    (foreach item dict
      ;; El código 3 guarda directamente el nombre de la escala en el índice
      (if (and item (listp item) (= (car item) 3))
        (setq scaleList (cons (cdr item) scaleList))
      )
    )
  )
  
  ;; Invertir la lista para mantener el orden de AutoCAD
  (if scaleList
    (setq scaleList (reverse scaleList))
  )

  ;; PARACAÍDAS: Si la lista sigue vacía por un error de AutoCAD, usar lista por defecto
  (if (not scaleList)
    (setq scaleList '("1:1" "1:10" "1:20" "1:50" "1:100" "1:250 m" "1:500" "1:1000"))
  )

  ;; 4. Crear la ventana de diálogo (Menú Desplegable)
  (setq dcl_file (vl-filename-mktemp "escalas.dcl"))
  (setq file (open dcl_file "w"))
  (write-line "EscalasVRAP : dialog { label = \"Escala del Viewport\"; " file)
  (write-line "  : text { label = \"Selecciona la escala para tu plano:\"; } " file)
  (write-line "  : popup_list { key = \"lista_escalas\"; width = 40; } " file)
  (write-line "  ok_cancel; " file)
  (write-line "} " file)
  (close file)

  ;; Cargar la interfaz
  (setq dcl_id (load_dialog dcl_file))
  (if (not (new_dialog "EscalasVRAP" dcl_id))
    (progn
      (alert "Error al cargar la interfaz visual.")
      (exit)
    )
  )

  ;; Llenar el menú desplegable con las escalas
  (start_list "lista_escalas")
  (mapcar 'add_list scaleList)
  (end_list)

  ;; Valores por defecto y acciones al hacer clic
  (set_tile "lista_escalas" "0")
  (setq chosenScale (nth 0 scaleList))
  (action_tile "lista_escalas" "(setq chosenScale (nth (atoi $value) scaleList))")
  (action_tile "accept" "(done_dialog 1)")
  (action_tile "cancel" "(done_dialog 0)")

  ;; Mostrar diálogo
  (setq dcl_status (start_dialog))
  (unload_dialog dcl_id)
  (vl-file-delete dcl_file)

  ;; Si presionas Cancelar o la "X"
  (if (= dcl_status 0)
    (progn (princ "\nComando VRAP cancelado por el usuario.") (exit))
  )

  ;; 5. Cambiar al layout
  (setq listalayouts (layoutlist))
  (if listalayouts
    (progn
      (setq layoutElegido (car listalayouts))
      (setvar "CTAB" layoutElegido)
      
      ;; 6. Cambiar a la capa "Viewport layer"
      (if (tblsearch "LAYER" "Viewport layer")
        (setvar "CLAYER" "Viewport layer")
      )

      ;; 7. Crear Viewport estándar de 300x100 mm centrado
      (command "_.MVIEW" '(-150.0 -50.0 0.0) '(150.0 50.0 0.0))
      
      ;; 8. Entrar al Viewport
      (command "_.MSPACE")
      
      ;; 9. Centrar vista
      (command "_.ZOOM" "_C" pCentro "")
      
      ;; 10. Forzar la escala sincronizada desde adentro del Viewport
      (command "_.CANNOSCALE" chosenScale)
      
      ;; 11. Salir al Layout y bloquear
      (command "_.PSPACE")
      (command "_.MVIEW" "_L" "_ON" "_L")
      
      (princ (strcat "\n¡Éxito total! Viewport creado, escalado a " chosenScale " y bloqueado."))
    )
    (alert "No se encontró ninguna pestaña de Layout.")
  )
  (princ)
)