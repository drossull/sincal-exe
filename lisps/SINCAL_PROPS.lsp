;;; =========================================================================
;;; HERRAMIENTAS DE PROPIEDADES CUSTOM (CUSTOM-PROPS, COPY-PROPS, PASTE-PROPS)
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
;;; Pregunta y permite editar las 10 propiedades en el archivo actual
;;; =========================================================================
(defun c:CUSTOM-PROPS (/ listaProps val input)
  (setq listaProps 
    '("Nombre_Estructura" "Region" "Provincia" "Comuna" "Revision" "Dibujante" "Fecha_Rev" "Fecha_Inf" "No_total_planos" "Nombre_Plano")
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
  (princ "\n[SINCAL] Propiedades del plano actualizadas correctamente.")
  (princ)
)

;;; =========================================================================
;;; COMANDO 2: COPY-PROPS 
;;; Copia las 6 propiedades generales a la memoria de Windows
;;; =========================================================================
(defun c:COPY-PROPS (/ propsToCopy val regPath)
  ;; Ruta en el registro para que sobreviva entre pestañas
  (setq regPath "HKEY_CURRENT_USER\\Software\\SINCAL\\CopiedProps")
  
  ;; Solo copia las 6 que se repiten en todo el proyecto
  (setq propsToCopy 
    '("Nombre_Estructura" "Region" "Provincia" "Comuna" "Fecha_Rev" "Fecha_Inf")
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
;;; Pega las 6 propiedades generales y pregunta por las 4 especificas
;;; =========================================================================
(defun c:PASTE-PROPS (/ regPath propsToPaste propsToAsk val input)
  (setq regPath "HKEY_CURRENT_USER\\Software\\SINCAL\\CopiedProps")
  
  ;; 6 propiedades maestras
  (setq propsToPaste '("Nombre_Estructura" "Region" "Provincia" "Comuna" "Fecha_Rev" "Fecha_Inf"))
  
  ;; 4 propiedades variables por plano
  (setq propsToAsk '("Revision" "Dibujante" "No_total_planos" "Nombre_Plano"))

  (princ "\n--- PEGANDO PROPIEDADES DE PROYECTO ---")
  
  ;; 1. Pegar silenciosamente las copiadas
  (foreach prop propsToPaste
    (setq val (vl-registry-read regPath prop))
    (if val
      (SINCAL:SetProp prop val)
    )
  )
  (princ (strcat "\n[SINCAL] " (itoa (length propsToPaste)) " propiedades generales aplicadas."))

  ;; 2. Preguntar al usuario por las específicas 
  (princ "\n--- COMPLETE LAS PROPIEDADES ESPECIFICAS ---")
  (foreach prop propsToAsk
    (setq val (SINCAL:GetProp prop))
    (setq input (getstring T (strcat "\nIngrese " prop " <" val ">: ")))
    (if (/= input "")
      (SINCAL:SetProp prop input)
    )
  )
  (princ "\n[SINCAL] Configuracion de plano finalizada. Recuerde regenerar (RE) para actualizar los textos.")
  (princ)
)

;;; FIN DEL CODIGO