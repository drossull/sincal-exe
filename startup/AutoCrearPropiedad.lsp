;;; INICIO DEL CODIGO (COMPATIBLE AUTOCAD Y ZWCAD)
(defun c:AutoCrearPropiedad (/ acadObj doc props listaProps propName propVal num i k v exists)
  (vl-load-com)

  ;; --- 1. AJUSTE DE VARIABLES DE ENTORNO ---
  (if (/= (getvar "MIRRTEXT") 0)
    (progn
      (setvar "MIRRTEXT" 0)
      (princ "\n[SINCAL] Variable MIRRTEXT ajustada a 0 (Textos no se invierten al hacer Mirror).")
    )
  )

  ;; --- 2. INYECCION DE PROPIEDADES CUSTOM SEGURA ---
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vlax-get-property acadObj 'ActiveDocument))
  (setq props (vlax-get-property doc 'SummaryInfo))

  ;; Lista de propiedades organizada de lo general a lo particular
  (setq listaProps
    '(
      ("Nombre_Estructura" . "Ingrese nombre estructura")
      ("Region"            . "Ingrese region")
      ("Provincia"         . "Ingrese provincia")
      ("Comuna"            . "Ingrese comuna")
      ("Sector"            . "Ingrese sector")
      ("Tramo"             . "Ingrese tramo")
      ("Revision"          . "REV")
      ("Comentario-rev"    . "Ingrese comentario revision")
      ("Dibujante"         . "DIBUJANTE")
      ("Fecha_Rev"         . "F_REV")
      ("Fecha_Inf"         . "F_INF")
      ("No_total_planos"   . "Ingrese numero total de planos")
      ("Nombre_Plano"      . "Ingrese nombre plano")
     )
  )

  ;; ESTRATEGIA: Revisar manualmente si existe antes de agregar (Filtro Anti-Bug ZWCAD)
  (foreach prop listaProps
    (setq propName (car prop))
    (setq propVal (cdr prop))
    (setq exists nil)
    
    (setq num (vla-NumCustomInfo props))
    (setq i 0)
    
    ;; Buscar si la llave ya existe
    (while (< i num)
      (vla-GetCustomByIndex props i 'k 'v)
      (if (= (strcase k) (strcase propName))
        (setq exists T)
      )
      (setq i (1+ i))
    )

    ;; Solo agregar si no fue encontrada en el bucle anterior
    (if (not exists)
      (progn
        (vl-catch-all-apply 'vla-AddCustomInfo (list props propName propVal))
        (princ (strcat "\n[SINCAL] Propiedad '" propName "' creada exitosamente."))
      )
    )
  )
  (princ "\n[SINCAL] Proceso de inicializacion y propiedades finalizado.")
  (princ)
)

;; Ejecutar al cargar
(c:AutoCrearPropiedad)
;;; FIN DEL CODIGO