(defun c:PLOTYA ( / doc plotObj dwgPath dwgName pdfPath oldBgPlot)
  (vl-load-com)
  
  ;; Obtener el documento actual
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  
  ;; 1. Verificar si el dibujo ha sido guardado (para tener una ruta de origen)
  (if (= (vla-get-Path doc) "")
    (princ "\nError: Debes guardar el archivo DWG al menos una vez para tener una ruta de destino.")
    (progn
      ;; 2. Obtener ruta del DWG y nombre sin extensión
      (setq dwgPath (vla-get-Path doc))
      (setq dwgName (vl-filename-base (vla-get-Name doc)))
      
      ;; 3. Construir la ruta final del PDF (RutaDwg \ NombreDwg .pdf)
      (setq pdfPath (strcat dwgPath "\\" dwgName ".pdf"))
      
      ;; 4. Desactivar temporalmente el ploteo en segundo plano (evita conflictos)
      (setq oldBgPlot (getvar "BACKGROUNDPLOT"))
      (setvar "BACKGROUNDPLOT" 0)
      
      ;; 5. Iniciar proceso de ploteo
      (setq plotObj (vla-get-Plot doc))
      (princ (strcat "\nGenerando PDF silenciosamente en: " pdfPath " ..."))
      
      ;; 6. Ejecutar impresión a archivo (saltando todos los cuadros)
      (if (vl-catch-all-error-p 
            (vl-catch-all-apply 'vla-PlotToFile (list plotObj pdfPath))
          )
        (princ "\n[X] Error: No se pudo plotear. Verifica que la impresora actual del Layout sea PDF.")
        (princ "\n[OK] ¡PDF generado con éxito con el mismo nombre del DWG!")
      )
      
      ;; 7. Restaurar configuración original de ploteo
      (setvar "BACKGROUNDPLOT" oldBgPlot)
    )
  )
  (princ)
)