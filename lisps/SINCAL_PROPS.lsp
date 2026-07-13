;;; =========================================================================
;;; HERRAMIENTAS DE PROPIEDADES CUSTOM (CUSTOM-PROPS, COPY-PROPS, PASTE-PROPS, REPARAR-PROPS)
;;; =========================================================================

;;; --- FUNCIONES AUXILIARES (NUCLEO) ---
(vl-load-com)

;; Obtener valor de propiedad de forma segura
(defun SINCAL:GetProp (key / props num i k v res)
  (setq props (vla-get-SummaryInfo (vla-get-ActiveDocument (vlax-get-acad-object))))
  (setq num (vla-NumCustomInfo props))
  (setq i 0 res "")
  (while (< i num)
    (vla-GetCustomByIndex props i 'k 'v)
    (if (= (strcase k) (strcase key))
      (setq res v i num) ; Encuentra y sale del bucle
    )
    (setq i (1+ i))
  )
  res
)

;; Modificar (o crear si no existe) valor de propiedad
(defun SINCAL:SetProp (key val / props err)
  (setq props (vla-get-SummaryInfo (vla-get-ActiveDocument (vlax-get-acad-object))))
  (setq err (vl-catch-all-apply 'vla-SetCustomByKey (list props key val)))
  (if (vl-catch-all-error-p err)
    (vl-catch-all-apply 'vla-AddCustomInfo (list props key val))
  )
)

;;; =========================================================================
;;; COMANDO 1: CUSTOM-PROPS 
;;; Pregunta y permite editar las 13 propiedades en el archivo actual
;;; =========================================================================
(defun c:CUSTOM-PROPS (/ listaProps val input)
  (setq listaProps 
    '("Nombre_Estructura" "Region" "Provincia" "Comuna" "Sector" "Tramo" "Revision" "Comentario-rev" "Dibujante" "Fecha_Rev" "Fecha_Inf" "No_total_planos" "Nombre_Plano")
  )
  (princ "\n--- EDITOR DE PROPIEDADES SINCAL ---")
  (foreach prop listaProps
    (setq val (SINCAL:GetProp prop))
    ;; 'getstring T' permite escribir frases con espacios
    (setq input (getstring T (strcat "\nIngrese " prop " <" val ">: ")))
    (if (/= input "")
      (SINCAL:SetProp prop input)
    )
  )
  
  ;; --- PROTOCOLO SINCAL (BLINDAJE DE DATOS) ---
  (command "_.UPDATEFIELD" "_All" "")       ; Actualiza los textos/viñetas visualmente
  (setvar "USERI1" (getvar "USERI1"))       ; Truco DBMOD: Ensuciar el archivo en la RAM
  (command "_.QSAVE")                       ; Forzar el guardado en disco
  
  (princ "\n[SINCAL] Propiedades actualizadas y plano guardado correctamente de forma segura.")
  (princ)
)

;;; =========================================================================
;;; COMANDO 2: COPY-PROPS 
;;; Copia las 12 propiedades generales a la memoria de Windows
;;; =========================================================================
(defun c:COPY-PROPS (/ propsToCopy val regPath)
  ;; Ruta en el registro para que sobreviva entre pestañas
  (setq regPath "HKEY_CURRENT_USER\\Software\\SINCAL\\CopiedProps")
  
  ;; Copia las 12 que se repiten en todo el proyecto
  (setq propsToCopy 
    '("Nombre_Estructura" "Region" "Provincia" "Comuna" "Sector" "Tramo" "Revision" "Comentario-rev" "Dibujante" "Fecha_Rev" "Fecha_Inf" "No_total_planos")
  )
  
  (foreach prop propsToCopy
    (setq val (SINCAL:GetProp prop))
    (vl-registry-write regPath prop val)
  )
  (princ (strcat "\n[SINCAL] " (itoa (length propsToCopy)) " propiedades del proyecto copiadas al portapapeles de SINCAL."))
  (princ)
)

;;; =========================================================================
;;; COMANDO 3: PASTE-PROPS 
;;; Pega las 12 propiedades generales y pregunta solo por el Nombre del Plano
;;; =========================================================================
(defun c:PASTE-PROPS (/ regPath propsToPaste propsToAsk val input)
  (setq regPath "HKEY_CURRENT_USER\\Software\\SINCAL\\CopiedProps")
  
  ;; 12 propiedades maestras
  (setq propsToPaste '("Nombre_Estructura" "Region" "Provincia" "Comuna" "Sector" "Tramo" "Revision" "Comentario-rev" "Dibujante" "Fecha_Rev" "Fecha_Inf" "No_total_planos"))
  
  ;; 1 propiedad variable por plano
  (setq propsToAsk '("Nombre_Plano"))

  (princ "\n--- PEGANDO PROPIEDADES DE PROYECTO ---")
  
  ;; 1. Pegar silenciosamente las copiadas
  (foreach prop propsToPaste
    (setq val (vl-registry-read regPath prop))
    (if val
      (SINCAL:SetProp prop val)
    )
  )
  (princ (strcat "\n[SINCAL] " (itoa (length propsToPaste)) " propiedades generales aplicadas."))

  ;; 2. Preguntar al usuario por la específica 
  (princ "\n--- COMPLETE LA PROPIEDAD ESPECIFICA ---")
  (foreach prop propsToAsk
    (setq val (SINCAL:GetProp prop))
    (setq input (getstring T (strcat "\nIngrese " prop " <" val ">: ")))
    (if (/= input "")
      (SINCAL:SetProp prop input)
    )
  )
  
  ;; --- PROTOCOLO SINCAL (BLINDAJE DE DATOS) ---
  (command "_.UPDATEFIELD" "_All" "")       ; Actualiza los textos/viñetas visualmente
  (setvar "USERI1" (getvar "USERI1"))       ; Truco DBMOD: Ensuciar el archivo en la RAM
  (command "_.QSAVE")                       ; Forzar el guardado en disco
  
  (princ "\n[SINCAL] Configuracion de plano finalizada y guardada en disco.")
  (princ)
)

;;; =========================================================================
;;; COMANDO 4: REPARAR-PROPS 
;;; Limpia las propiedades duplicadas generadas por el bug de ZWCAD
;;; =========================================================================
(defun c:REPARAR-PROPS (/ acadObj doc props num i k v dict)
  (vl-load-com)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq props (vla-get-SummaryInfo doc))
  (setq num (vla-NumCustomInfo props))
  (setq i 0 dict nil)
  
  ;; Rescatar las propiedades sin repetir
  (while (< i num)
    (vla-GetCustomByIndex props i 'k 'v)
    (if (not (assoc (strcase k) dict))
      (setq dict (append dict (list (cons (strcase k) (cons k v)))))
    )
    (setq i (1+ i))
  )
  
  ;; Borrar TODO el registro corrupto
  (while (> (vla-NumCustomInfo props) 0)
    (vl-catch-all-apply 'vla-RemoveCustomByIndex (list props 0))
  )
  
  ;; Inyectarlas de nuevo limpias
  (foreach item dict
    (vla-AddCustomInfo props (cadr item) (cddr item))
  )
  
  ;; --- PROTOCOLO SINCAL (BLINDAJE DE DATOS) ---
  (setvar "USERI1" (getvar "USERI1"))
  (command "_.QSAVE")
  
  (princ "\n[SINCAL] ¡Duplicados eliminados y archivo guardado! Ya puedes usar CUSTOM-PROPS sin errores.")
  (princ)
)

;;; FIN DEL CODIGO