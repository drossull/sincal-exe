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
;;; Pregunta y permite editar las propiedades (Incluye DM, excluye Coordenadas)
;;; =========================================================================
(defun c:CUSTOM-PROPS (/ listaProps val input)
  ;; Se omiten las coordenadas para no tener que tipearlas a mano.
  (setq listaProps 
    '("Region" "Provincia" "Comuna" "Sector" "Tramo" "Nombre_Estructura" "DM_Inicio" "DM_Fin" "Dibujante" "Fecha_Inf" "Fecha_Rev" "Revision" "Comentario-rev" "No_total_planos" "Nombre_Plano")
  )
  (princ "\n--- EDITOR DE PROPIEDADES SINCAL ---")
  (foreach prop listaProps
    (setq val (SINCAL:GetProp prop))
    (setq input (getstring T (strcat "\nIngrese " prop " <" val ">: ")))
    (if (/= input "")
      (SINCAL:SetProp prop input)
    )
  )
  
  ;; --- PROTOCOLO SINCAL (BLINDAJE DE DATOS) ---
  (command "_.UPDATEFIELD" "_All" "")       
  (setvar "USERI1" (getvar "USERI1"))       
  (command "_.QSAVE")                       
  
  (princ "\n[SINCAL] Propiedades actualizadas y plano guardado correctamente de forma segura.")
  (princ)
)

;;; =========================================================================
;;; COMANDO 2: COPY-PROPS 
;;; Copia TODAS las propiedades (incluyendo las coordenadas extraidas)
;;; =========================================================================
(defun c:COPY-PROPS (/ propsToCopy val regPath)
  (setq regPath "HKEY_CURRENT_USER\\Software\\SINCAL\\CopiedProps")
  
  (setq propsToCopy 
    '("Nombre_Estructura" "Region" "Provincia" "Comuna" "Sector" "Tramo" "Revision" "Comentario-rev" "Dibujante" "Fecha_Rev" "Fecha_Inf" "No_total_planos" "DM_Inicio" "DM_Fin" "Coordenada_Este_Inicio" "Coordenada_Norte_Inicio" "Coordenada_Este_Fin" "Coordenada_Norte_Fin")
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
;;; Pega silenciosamente y pregunta SOLO por el Nombre del Plano
;;; =========================================================================
(defun c:PASTE-PROPS (/ regPath propsToPaste propsToAsk val input)
  (setq regPath "HKEY_CURRENT_USER\\Software\\SINCAL\\CopiedProps")
  
  (setq propsToPaste '("Nombre_Estructura" "Region" "Provincia" "Comuna" "Sector" "Tramo" "Revision" "Comentario-rev" "Dibujante" "Fecha_Rev" "Fecha_Inf" "No_total_planos" "DM_Inicio" "DM_Fin" "Coordenada_Este_Inicio" "Coordenada_Norte_Inicio" "Coordenada_Este_Fin" "Coordenada_Norte_Fin"))
  (setq propsToAsk '("Nombre_Plano"))

  (princ "\n--- PEGANDO PROPIEDADES DE PROYECTO ---")
  
  (foreach prop propsToPaste
    (setq val (vl-registry-read regPath prop))
    (if val
      (SINCAL:SetProp prop val)
    )
  )
  (princ (strcat "\n[SINCAL] " (itoa (length propsToPaste)) " propiedades generales (incluyendo coordenadas) aplicadas."))

  (princ "\n--- COMPLETE LA PROPIEDAD ESPECIFICA ---")
  (foreach prop propsToAsk
    (setq val (SINCAL:GetProp prop))
    (setq input (getstring T (strcat "\nIngrese " prop " <" val ">: ")))
    (if (/= input "")
      (SINCAL:SetProp prop input)
    )
  )
  
  (command "_.UPDATEFIELD" "_All" "")       
  (setvar "USERI1" (getvar "USERI1"))       
  (command "_.QSAVE")                       
  
  (princ "\n[SINCAL] Configuracion de plano finalizada y guardada en disco.")
  (princ)
)

;;; =========================================================================
;;; COMANDO 4: REPARAR-PROPS 
;;; =========================================================================
(defun c:REPARAR-PROPS (/ acadObj doc props num i k v dict)
  (vl-load-com)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq props (vla-get-SummaryInfo doc))
  (setq num (vla-NumCustomInfo props))
  (setq i 0 dict nil)
  
  (while (< i num)
    (vla-GetCustomByIndex props i 'k 'v)
    (if (not (assoc (strcase k) dict))
      (setq dict (append dict (list (cons (strcase k) (cons k v)))))
    )
    (setq i (1+ i))
  )
  
  (while (> (vla-NumCustomInfo props) 0)
    (vl-catch-all-apply 'vla-RemoveCustomByIndex (list props 0))
  )
  
  (foreach item dict
    (vla-AddCustomInfo props (cadr item) (cddr item))
  )
  
  (setvar "USERI1" (getvar "USERI1"))
  (command "_.QSAVE")
  
  (princ "\n[SINCAL] ¡Duplicados eliminados y archivo guardado!")
  (princ)
)

;;; =========================================================================
;;; FUNCION MAESTRA PARA EXTRAER COORDENADAS (USADA POR C-INICIO Y C-FIN)
;;; =========================================================================
(defun SINCAL:ExtraerCoordBloc (mapeo mensaje / ss blkObj atts attTag attVal propName procesados)
  (vl-load-com)
  (princ (strcat "\n" mensaje))
  
  (setq ss (ssget "_+.:E:S" '((0 . "INSERT") (66 . 1)))) 
  
  (if ss
    (progn
      (setq blkObj (vlax-ename->vla-object (ssname ss 0)))
      (setq atts (vlax-invoke blkObj 'GetAttributes))
      (setq procesados 0)
      
      (foreach att atts
        (setq attTag (strcase (vla-get-TagString att)))
        (setq attVal (vla-get-TextString att))
        (if (setq propName (cdr (assoc attTag mapeo)))
          (progn
            (SINCAL:SetProp propName attVal)
            (princ (strcat "\n[OK] Transferido: " propName " -> " attVal))
            (setq procesados (1+ procesados))
          )
        )
      )
      
      (if (> procesados 0)
        (progn
          (command "_.UPDATEFIELD" "_All" "")
          (setvar "USERI1" (getvar "USERI1"))
          (command "_.QSAVE")
          (princ "\n[SINCAL] Coordenadas inyectadas al archivo exitosamente.")
        )
        (princ "\n[!] El bloque no tiene los atributos requeridos (Revise los Tags).")
      )
    )
    (princ "\n[X] No seleccionó un bloque válido.")
  )
  (princ)
)

;;; =========================================================================
;;; COMANDO 5: C-INICIO (Extrae tags ESTE-IN y NORTE-IN)
;;; =========================================================================
(defun c:C-INICIO ()
  (SINCAL:ExtraerCoordBloc 
    '(("ESTE-IN" . "Coordenada_Este_Inicio") ("NORTE-IN" . "Coordenada_Norte_Inicio"))
    "Seleccione el bloque con las coordenadas de INICIO: "
  )
)

;;; =========================================================================
;;; COMANDO 6: C-FIN (Extrae tags ESTE-FIN y NORTE-FIN)
;;; =========================================================================
(defun c:C-FIN ()
  (SINCAL:ExtraerCoordBloc 
    '(("ESTE-FIN" . "Coordenada_Este_Fin") ("NORTE-FIN" . "Coordenada_Norte_Fin"))
    "Seleccione el bloque con las coordenadas de FIN: "
  )
)

;;; FIN DEL CODIGO