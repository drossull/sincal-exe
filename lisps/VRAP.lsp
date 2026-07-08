(defun c:VRAP ( / p1 p2 pCentro dict scEntData scNameItem pUnitsItem dUnitsItem scName pUnits dUnits factor scaleList scaleDataList dcl_file file dcl_id chosenScale chosenFactor dcl_status listalayouts layoutElegido vpEnt vpObj )
  (vl-load-com)

  ;; 1. Verificar Model Space
  (if (/= (getvar "CTAB") "Model")
    (progn (alert "Por favor, ejecuta el comando VRAP desde la pestaña 'Model'.") (exit))
  )

  ;; 2. Selección del área
  (setq p1 (getpoint "\nSelecciona la primera esquina del rectángulo de selección: "))
  (if (not p1) (progn (princ "\nComando cancelado.") (exit)))
  
  (setq p2 (getcorner p1 "\nSelecciona la esquina contraria: "))
  (if (not p2) (progn (princ "\nComando cancelado.") (exit)))
  
  (setq pCentro (list 
                  (/ (+ (car p1) (car p2)) 2.0)
                  (/ (+ (cadr p1) (cadr p2)) 2.0)
                  0.0
                )
  )

  ;; 3. LECTURA PROFUNDA DE ESCALAS (Extrae Nombre Real y Valor Matemático)
  (setq scaleList nil)
  (setq scaleDataList nil)
  (if (setq dict (dictsearch (namedobjdict) "ACAD_SCALES"))
    (foreach item dict
      ;; 350 es el código que apunta a la entidad física de la escala, nunca falla.
      (if (and item (listp item) (= (car item) 350))
        (if (setq scEntData (entget (cdr item)))
          (progn
            (setq scNameItem (assoc 300 scEntData))
            (setq pUnitsItem (assoc 140 scEntData))
            (setq dUnitsItem (assoc 143 scEntData))
            (if (and scNameItem pUnitsItem dUnitsItem)
              (progn
                (setq scName (cdr scNameItem))
                (setq pUnits (cdr pUnitsItem))
                (setq dUnits (cdr dUnitsItem))
                ;; Verificar que los datos existan y no sea una escala corrupta
                (if (and (numberp pUnits) (numberp dUnits) (> dUnits 0.0) scName (not (equal scName "")))
                  (progn
                    ;; Calcular el factor exacto de acercamiento
                    (setq factor (/ (float pUnits) (float dUnits)))
                    ;; Evitar escalas duplicadas fantasma en la lista
                    (if (not (member scName scaleList))
                      (progn
                        (setq scaleList (cons scName scaleList))
                        ;; Guardamos el nombre y su valor matemático juntos
                        (setq scaleDataList (cons (cons scName factor) scaleDataList))
                      )
                    )
                  )
                )
              )
            )
          )
        )
      )
    )
  )

  ;; Invertir listas para respetar el orden visual de AutoCAD
  (if scaleList
    (progn
      (setq scaleList (reverse scaleList))
      (setq scaleDataList (reverse scaleDataList))
    )
    (progn (alert "Fallo crítico: No se encontraron escalas en este archivo.") (exit))
  )

  ;; 4. CREAR LA INTERFAZ (DCL)
  (setq dcl_file (vl-filename-mktemp "escalas.dcl"))
  (setq file (open dcl_file "w"))
  (write-line "EscalasVRAP : dialog { label = \"Escala del Viewport\"; " file)
  (write-line "  : text { label = \"Selecciona la escala para tu plano:\"; } " file)
  (write-line "  : popup_list { key = \"lista_escalas\"; width = 40; } " file)
  (write-line "  ok_cancel; " file)
  (write-line "} " file)
  (close file)

  (setq dcl_id (load_dialog dcl_file))
  (if (not (new_dialog "EscalasVRAP" dcl_id))
    (progn (alert "Error al cargar la interfaz visual.") (exit))
  )

  (start_list "lista_escalas")
  (mapcar 'add_list scaleList)
  (end_list)

  (set_tile "lista_escalas" "0")
  (setq chosenScale (nth 0 scaleList))
  
  (action_tile "lista_escalas" "(setq chosenScale (nth (atoi $value) scaleList))")
  (action_tile "accept" "(done_dialog 1)")
  (action_tile "cancel" "(done_dialog 0)")

  (setq dcl_status (start_dialog))
  (unload_dialog dcl_id)
  (vl-file-delete dcl_file)

  (if (= dcl_status 0)
    (progn (princ "\nComando VRAP cancelado por el usuario.") (exit))
  )

  ;; 5. CREACIÓN Y AJUSTE MATEMÁTICO DEL VIEWPORT
  (setq listalayouts (layoutlist))
  (if listalayouts
    (progn
      (setq layoutElegido (car listalayouts))
      (setvar "CTAB" layoutElegido)
      
      (if (tblsearch "LAYER" "Viewport layer")
        (setvar "CLAYER" "Viewport layer")
      )

      ;; Crear Viewport de 300x100
      (command "_.MVIEW" '(-150.0 -50.0 0.0) '(150.0 50.0 0.0))
      
      ;; Capturar el objeto ActiveX del Viewport
      (setq vpEnt (entlast))
      (setq vpObj (vlax-ename->vla-object vpEnt))

      ;; Entrar y buscar las coordenadas
      (command "_.MSPACE")
      (command "_.ZOOM" "_C" pCentro "")
      
      ;; Aplicar Etiqueta de Escala de Anotación
      (vl-catch-all-apply 'setvar (list "CANNOSCALE" chosenScale))
      
      ;; Salir al espacio papel
      (command "_.PSPACE")
      
      ;; INYECTAR EL ZOOM FÍSICO (El fix definitivo)
      (setq chosenFactor (cdr (assoc chosenScale scaleDataList)))
      (if chosenFactor
        (vl-catch-all-apply 'vla-put-CustomScale (list vpObj chosenFactor))
      )
      
      ;; Bloquear el viewport
      (vla-put-DisplayLocked vpObj :vlax-true)
      
      (princ (strcat "\n¡Éxito total! Viewport creado, escalado a " chosenScale " y bloqueado."))
    )
    (alert "No se encontró ninguna pestaña de Layout.")
  )
  (princ)
)