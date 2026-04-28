(vl-load-com)

(defun c:CUSTOM-PROPS ( / doc summaryInfo getProp setProp askProp choice loop kwds prmpt)
  ;; Obtenemos el documento activo y su objeto SummaryInfo (DWGPROPS)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq summaryInfo (vla-get-SummaryInfo doc))

  ;; Función auxiliar: Obtiene el valor actual o devuelve "" si no existe
  (defun getProp (key / val)
    (setq val "")
    (vl-catch-all-apply 'vla-GetCustomByKey (list summaryInfo key 'val))
    val
  )

  ;; Función auxiliar: Modifica el valor. Si la propiedad no existe, la crea.
  (defun setProp (key val / temp)
    (setq temp "")
    (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-GetCustomByKey (list summaryInfo key 'temp)))
      (vla-AddCustomInfo summaryInfo key val)
      (vla-SetCustomByKey summaryInfo key val)
    )
  )

  ;; Función auxiliar: Pregunta al usuario mostrando el valor actual por defecto
  (defun askProp (key promptTxt / curVal newVal)
    (setq curVal (getProp key))
    ;; getstring T permite introducir espacios en el texto
    (setq newVal (getstring T (strcat "\nIngrese " promptTxt " <" (if (= curVal "") "Vacío" curVal) ">: ")))
    
    ;; Si el usuario escribe algo, actualiza. Si presiona Enter (en blanco), mantiene el valor.
    (if (/= newVal "")
      (setProp key newVal)
    )
  )

  (setq loop T)
  (while loop
    ;; Configuramos las palabras clave (las mayúsculas son los atajos)
    (setq kwds "Nombre Provincia Comuna Revision fEcha_rev fecha_Inf Total pLano secUencia Salir")
    (initget 0 kwds)
    
    ;; Mostramos el prompt estilo FILLET
    (setq prmpt "\nPropiedad a editar [Nombre / Provincia / Comuna / Revision / fEcha_rev / fecha_Inf / Total / pLano / secUencia / Salir] <secUencia>: ")
    (setq choice (getkword prmpt))

    (cond
      ;; Si se presiona Enter o se elige "secUencia", hace el paso a paso
      ((or (not choice) (= choice "secUencia"))
       (askProp "Nombre_estructura" "Nombre_estructura")
       (askProp "Provincia" "Provincia")
       (askProp "Comuna" "Comuna")
       (askProp "Revision" "Revision")
       (askProp "Fecha_Rev" "Fecha_Rev")
       (askProp "Fecha_Inf" "Fecha_Inf")
       (askProp "No_total_planos" "No_total_planos")
       (askProp "Nombre_Plano" "Nombre_Plano")
       (setq loop nil) ;; Sale del bucle al terminar la secuencia
      )
      ;; Opciones individuales
      ((= choice "Nombre")   (askProp "Nombre_estructura" "Nombre_estructura"))
      ((= choice "Provincia")(askProp "Provincia" "Provincia"))
      ((= choice "Comuna")   (askProp "Comuna" "Comuna"))
      ((= choice "Revision") (askProp "Revision" "Revision"))
      ((= choice "fEcha_rev")(askProp "Fecha_Rev" "Fecha_Rev"))
      ((= choice "fecha_Inf")(askProp "Fecha_Inf" "Fecha_Inf"))
      ((= choice "Total")    (askProp "No_total_planos" "No_total_planos"))
      ((= choice "pLano")    (askProp "Nombre_Plano" "Nombre_Plano"))
      ((= choice "Salir")    (setq loop nil))
    )
  )
  
  (princ "\n--- Propiedades (DWGPROPS) actualizadas correctamente ---")
  (princ)
)

(princ "\nComando CUSTOM-PROPS cargado. Escribe CUSTOM-PROPS para ejecutar.")
(princ)