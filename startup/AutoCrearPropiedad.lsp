;;; INICIO DEL CODIGO (COMPATIBLE AUTOCAD 2025)
(defun c:AutoCrearPropiedad (/ acadObj doc props listaProps err)
  (vl-load-com)

  (setq acadObj (vlax-get-acad-object))
  (setq doc (vlax-get-property acadObj 'ActiveDocument))
  (setq props (vlax-get-property doc 'SummaryInfo))

  ;; --- CONFIGURACION ---
  ;; Lista de propiedades organizada de lo general a lo particular
  (setq listaProps
    '(
      ("Nombre_Estructura" . "Ingrese nombre estructura")
      ("Region"            . "Ingrese region")
      ("Provincia"         . "Ingrese provincia")
      ("Comuna"            . "Ingrese comuna")
      ("Revision"          . "rev")
      ("Dibujante"         . "DIB")
      ("Fecha_Rev"         . "F_REV")
      ("Fecha_Inf"         . "F_INF")
      ("No_total_planos"   . "Ingrese número total de planos")
      ("Nombre_Plano"      . "Ingrese nombre plano")
     )
  )
  ;; ---------------------

  ;; ESTRATEGIA: Recorrer la lista e intentar agregar cada propiedad
  (foreach prop listaProps
    (setq err 
      (vl-catch-all-apply 
        'vlax-invoke-method
        (list props 'AddCustomInfo (car prop) (cdr prop))
      )
    )

    ;; Si se crea con éxito, informa al usuario.
    ;; Si falla (porque ya existe), el programa continúa sin detenerse.
    (if (not (vl-catch-all-error-p err))
       (princ (strcat "\n[AutoCAD] Propiedad '" (car prop) "' creada exitosamente."))
    )
  )
  (princ "\n[AutoCAD] Proceso de creación de propiedades finalizado.")
  (princ)
)

;; Ejecutar al cargar
(c:AutoCrearPropiedad)
;;; FIN DEL CODIGO