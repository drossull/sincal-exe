(defun c:SETUP-A1 ( / acadObj doc layouts layoutName appName isZWCAD plotterName paperName xType xData)
  ;; Cargar funciones de Visual LISP
  (vl-load-com)
  
  ;; Obtener el objeto de la aplicación
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadObj))
  (setq layouts (vla-get-Layouts doc))
  
  ;; --- DETECCIÓN DEL PROGRAMA ---
  (setq appName (vla-get-Name acadObj))
  (if (or (vl-string-search "ZWCAD" (strcase appName)) 
          (and (getvar "PROGRAM") (vl-string-search "ZWCAD" (strcase (getvar "PROGRAM")))))
    (progn
      (setq plotterName "ZWCAD PDF(High Quality Print).pc5")
      (setq paperName "ISO_full_bleed_A1_(841.00_x_594.00_MM)") 
      (setq isZWCAD T)
    )
    (progn
      (setq plotterName "AutoCAD PDF (High Quality Print).pc3")
      (setq paperName "ISO_full_bleed_A1_(841.00_x_594.00_MM)")
      (setq isZWCAD nil)
    )
  )

  ;; Registrar la aplicación para la transparencia si no existe en el archivo
  (if (not (tblsearch "APPID" "PLOTTRANSPARENCY"))
    (regapp "PLOTTRANSPARENCY")
  )

  (vla-StartUndoMark doc)

  (vlax-for layout layouts
    (setq layoutName (vla-get-Name layout))
    
    ;; Ignorar el espacio Modelo
    (if (/= (strcase layoutName) "MODEL")
      (progn
        ;; 1 y 2. Impresora y Papel
        (vl-catch-all-apply 'vla-put-ConfigName (list layout plotterName))
        (vl-catch-all-apply 'vla-put-CanonicalMediaName (list layout paperName))
        
        ;; 3. Plumillas
        (vl-catch-all-apply 'vla-put-StyleSheet (list layout "SINCAL_A1 (2025).ctb"))
        
        ;; 4 y 5. Área y Escala (1:1)
        (vla-put-PlotType layout acLayout)
        (vla-put-UseStandardScale layout :vlax-true)
        (vla-put-StandardScale layout ac1_1)
        
        ;; 6. Opciones de Trazado Regulares
        (vla-put-PlotWithLineweights layout :vlax-true)  
        (vla-put-PlotWithPlotStyles layout :vlax-true)   
        (vla-put-PlotViewportsFirst layout :vlax-false)  
        
        ;; 7. Orientación (Landscape)
        (vla-put-PlotRotation layout ac0degrees)

        ;; --- FIX: CALIDAD CUSTOM A 300 DPI ---
        ;; 5 equivale a "acShadePlotResCustom"
        (vl-catch-all-apply 'vla-put-ShadePlotResolutionLevel (list layout 5))
        (vl-catch-all-apply 'vla-put-ShadePlotCustomDPI (list layout 300))
        
        ;; --- FIX: PLOT TRANSPARENCY MEDIANTE XDATA ---
        (vl-catch-all-apply
          (function
            (lambda ()
              ;; Crear matrices seguras (Safearrays) para inyectar datos
              (setq xType (vlax-make-safearray vlax-vbInteger '(0 . 1)))
              (vlax-safearray-fill xType '(1001 1071))
              (setq xData (vlax-make-safearray vlax-vbVariant '(0 . 1)))
              (vlax-safearray-fill xData (list (vlax-make-variant "PLOTTRANSPARENCY") (vlax-make-variant 1)))
              
              ;; Aplicar el dato oculto al Layout
              (vla-SetXdata layout xType xData)
              ;; Refrescar la entidad para que AutoCAD actualice el cuadro de diálogo
              (entmod (entget (vlax-vla-object->ename layout) '("*")))
            )
          )
        )
        
        (princ (strcat "\n-> Layout configurado: " layoutName))
      )
    )
  )
  
  (vla-EndUndoMark doc)
  
  (princ "\n=======================================================")
  (if isZWCAD
    (princ (strcat "\n¡Layouts configurados a A1 para ZWCAD con " plotterName "!"))
    (princ (strcat "\n¡Layouts configurados a A1 para AutoCAD con " plotterName "!"))
  )
  (princ "\n=======================================================")
  (princ)
)

(princ "\nEscribe SETUP-A1 para configurar los Layouts.")
(princ)