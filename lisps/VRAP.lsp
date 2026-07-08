(defun c:VRAP ( / p1 p2 pCentro escala layoutElegido )
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
  
  ;; Calcular el punto medio (centro) de la selección
  (setq pCentro (list 
                  (/ (+ (car p1) (car p2)) 2.0)
                  (/ (+ (cadr p1) (cadr p2)) 2.0)
                  0.0
                )
  )

  ;; 3. Solicitar la escala
  (setq escala (getstring t "\nIngresa el nombre de la escala (ej. 1:250 m): "))

  ;; 4. Cambiar al único layout existente
  (setq layoutElegido (car (layoutlist)))
  (if layoutElegido
    (progn
      (setvar "CTAB" layoutElegido)
      
      ;; 5. Cambiar a la capa "Viewport layer" si existe
      (if (tblsearch "LAYER" "Viewport layer")
        (setvar "CLAYER" "Viewport layer")
        (princ "\nNota: La capa 'Viewport layer' no se encontró, usando la actual.")
      )

      ;; 6. Crear el Viewport de 300x100 mm centrado en (0,0)
      (command "_.MVIEW" '(-150.0 -50.0 0.0) '(150.0 50.0 0.0))
      
      ;; 7. Entrar al Viewport
      (command "_.MSPACE")
      
      ;; 8. Centrar la vista en las coordenadas seleccionadas
      (command "_.ZOOM" "_C" pCentro "")
      
      ;; 9. Aplicar la escala exacta buscando en tu lista de escalas (nativas o personalizadas)
      (if (vl-catch-all-error-p (vl-catch-all-apply 'setvar (list "CANNOSCALE" escala)))
        (princ (strcat "\nADVERTENCIA: La escala '" escala "' no existe. El viewport quedó centrado pero sin escala."))
        (princ (strcat "\nEscala " escala " aplicada correctamente."))
      )
      
      ;; 10. Volver al espacio Papel y bloquear el viewport
      (command "_.PSPACE")
      (command "_.MVIEW" "_L" "_ON" "_L") ;; Bloquea el último viewport creado
      
      (princ "\n¡Comando VRAP finalizado con éxito!")
    )
    (alert "No se encontró ninguna pestaña de Layout en este dibujo.")
  )
  (princ)
)