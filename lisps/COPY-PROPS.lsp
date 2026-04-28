(vl-load-com)

;;; ==========================================================================
;;; FUNCIONES AUXILIARES GLOBALES
;;; ==========================================================================

;; Obtiene el valor de una Custom Property o devuelve ""
(defun getCustomProp (summaryInfo key / val)
  (setq val "")
  (vl-catch-all-apply 'vla-GetCustomByKey (list summaryInfo key 'val))
  val
)

;; Establece o crea una Custom Property
(defun setCustomProp (summaryInfo key val / temp)
  (setq temp "")
  (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-GetCustomByKey (list summaryInfo key 'temp)))
    (vla-AddCustomInfo summaryInfo key val)
    (vla-SetCustomByKey summaryInfo key val)
  )
)

;; Pregunta al usuario por una propiedad (con memoria del valor actual)
(defun askCustomProp (summaryInfo key promptTxt / curVal newVal)
  (setq curVal (getCustomProp summaryInfo key))
  (setq newVal (getstring T (strcat "\nIngrese " promptTxt " <" (if (= curVal "") "Vacío" curVal) ">: ")))
  (if (/= newVal "")
    (setCustomProp summaryInfo key newVal)
  )
)

;;; ==========================================================================
;;; COMANDO: COPY-PROPS (Copia solo las 6 propiedades generales)
;;; ==========================================================================
(defun c:COPY-PROPS ( / doc summaryInfo propsToCopy propList val )
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq summaryInfo (vla-get-SummaryInfo doc))

  ;; Lista restringida según tu solicitud
  (setq propsToCopy '("Nombre_estructura" "Revision" "Fecha_Rev" "Fecha_Inf" "Provincia" "Comuna"))
  (setq propList nil)

  (foreach key propsToCopy
    (setq val (getCustomProp summaryInfo key))
    (setq propList (cons (cons key val) propList))
  )

  (vl-bb-set 'CustomPropsClipboard propList)
  (princ "\n--- Propiedades generales copiadas (Estructura, Rev, Fechas, Ubicación) ---")
  (princ)
)

;;; ==========================================================================
;;; COMANDO: PASTE-PROPS (Pega las 6 y pregunta por las 2 específicas)
;;; ==========================================================================
(defun c:PASTE-PROPS ( / doc summaryInfo propList )
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq summaryInfo (vla-get-SummaryInfo doc))
  (setq propList (vl-bb-ref 'CustomPropsClipboard))

  (if propList
    (progn
      ;; 1. Pegar las propiedades generales desde la memoria
      (foreach item propList
        (setCustomProp summaryInfo (car item) (cdr item))
      )
      (princ "\n--- Propiedades generales pegadas correctamente. ---")

      ;; 2. Preguntar por las propiedades específicas de este plano
      (askCustomProp summaryInfo "Nombre_Plano" "Nombre_Plano")
      (askCustomProp summaryInfo "No_total_planos" "No_total_planos")

      ;; 3. Regenerar el dibujo
      (command "_.REGENALL")
      (princ "\n--- Proceso completado y dibujo regenerado. ---")
    )
    (princ "\n--- Error: El portapapeles está vacío. Usa COPY-PROPS primero. ---")
  )
  (princ)
)

(princ "\nComandos cargados: COPY-PROPS (Copia 6) y PASTE-PROPS (Pega 6 + pregunta 2).")
(princ)