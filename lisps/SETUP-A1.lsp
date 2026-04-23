(defun c:SETUP-A1 ( / acadObj doc layouts layoutName appName isZWCAD plotterName paperName)
  ;; Cargar funciones de Visual LISP
  (vl-load-com)
  
  ;; Obtener el objeto de la aplicación
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadObj))
  (setq layouts (vla-get-Layouts doc))
  
  ;; --- DETECCIÓN DEL PROGRAMA (AutoCAD vs ZWCAD) ---
  ;; Consultamos el nombre del programa activo
  (setq appName (vla-get-Name acadObj))
  
  ;; Si el nombre contiene la palabra "ZWCAD" o la variable de entorno lo indica
  (if (or (vl-string-search "ZWCAD" (strcase appName)) 
          (and (getvar "PROGRAM") (vl-string-search "ZWCAD" (strcase (getvar "PROGRAM")))))
    (progn
      ;; Variables para ZWCAD (Basado en tu captura)
      (setq plotterName "ZWCAD PDF(High Quality Print).pc5")
      (setq paperName "ISO_full_bleed_A1_(841.00_x_594.00_MM)") 
      (setq isZWCAD T)
    )
    (progn
      ;; Variables para AutoCAD
      (setq plotterName "AutoCAD PDF (High Quality Print).pc3")
      (setq paperName "ISO_full_bleed_A1_(841.00_x_594.00_MM)")
      (setq isZWCAD nil)
    )
  )

  ;; Iniciar la transacción para deshacer
  (vla-StartUndoMark doc)

  ;; Iterar a través de todos los Layouts
  (vlax-for layout layouts
    (setq layoutName (vla-get-Name layout))
    
    ;; Ignorar el espacio Modelo
    (if (/= (strcase layoutName) "MODEL")
      (progn
        ;; 1 y 2. Asignar Impresora y Papel (usamos vl-catch-all-apply para evitar errores críticos si no existe)
        (vl-catch-all-apply 'vla-put-ConfigName (list layout plotterName))
        (vl-catch-all-apply 'vla-put-CanonicalMediaName (list layout paperName))
        
        ;; 3. Asignar Plumillas
        (vl-catch-all-apply 'vla-put-StyleSheet (list layout "SINCAL_A1 (2025).ctb"))
        
        ;; 4. Área de Trazado
        (vla-put-PlotType layout acLayout)
        
        ;; 5. Escala de Impresión (1:1)
        (vla-put-UseStandardScale layout :vlax-true)
        (vla-put-StandardScale layout ac1_1)
        
        ;; 6. Opciones de Trazado (Según las casillas que marcaste)
        (vla-put-PlotWithLineweights layout :vlax-true)  
        (vla-put-PlotWithPlotStyles layout :vlax-true)   
        (vla-put-PlotViewportsFirst layout :vlax-false)  
        
        ;; 7. Orientación (Landscape)
        (vla-put-PlotRotation layout ac0degrees)
        
        (princ (strcat "\n-> Layout configurado: " layoutName))
      )
    )
  )
  
  (vla-EndUndoMark doc)
  
  ;; Mensaje final adaptativo
  (princ "\n=======================================================")
  (if isZWCAD
    (princ (strcat "\n¡Layouts configurados a A1 para ZWCAD con " plotterName "!"))
    (princ (strcat "\n¡Layouts configurados a A1 para AutoCAD con " plotterName "!"))
  )
  (princ "\n=======================================================")
  (princ)
)

(princ "\nEscribe SETUP-A1 para configurar los Layouts. Compatible con AutoCAD y ZWCAD.")
(princ)