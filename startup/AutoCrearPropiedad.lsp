;;; INICIO DEL CODIGO (COMPATIBLE AUTOCAD 2025)
(defun c:AutoCrearPropiedad (/ acadObj doc props listaProps err)
  (vl-load-com)

  (setq acadObj (vlax-get-acad-object))
  (setq doc (vlax-get-property acadObj 'ActiveDocument))
  (setq props (vlax-get-property doc 'SummaryInfo))

  ;; --- CONFIGURACION ---
  ;; Lista de propiedades a crear (formato: "Nombre" . "Valor por defecto")
  (setq listaProps
    '(
      ("Nombre_Plano"      . "Ingrese nombre plano")
      ("Nombre_Estructura" . "Ingrese nombre estructura")
      ("Revision"	   . "rev")
      ("Fecha_Rev"	   . "F_REV")
      ("Fecha_Inf"	   . "F_INF")
      ("No_total_planos"   . "Ingrese número total de planos")
     )
  )
  ;; ---------------------

  ;; ESTRATEGIA: Recorrer la lista e intentar agregar cada propiedad
  (foreach prop listaProps
    ;; El metodo interno en ActiveX se llama "AddCustomInfo"
    (setq err 
      (vl-catch-all-apply 
        'vlax-invoke-method
        ;; (car prop) extrae el nombre, (cdr prop) extrae el valor
        (list props 'AddCustomInfo (car prop) (cdr prop))
      )
    )

    ;; Si no hubo error, significa que se creo. 
    ;; Si hubo error, probablemente ya existia, asi que pasamos a la siguiente.
    (if (not (vl-catch-all-error-p err))
       (princ (strcat "\n[AutoCAD] Propiedad '" (car prop) "' creada exitosamente."))
    )
  )
  (princ)
)

;; Ejecutar al cargar
(c:AutoCrearPropiedad)
;;; FIN DEL CODIGO