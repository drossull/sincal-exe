;;; ==========================================================================
;;; COMANDO: ESTRUCTURA
;;; DESCRIPCIÓN: 
;;;   Permite editar rápidamente el valor de la propiedad personalizada
;;;   "Nombre_Estructura".
;;; ==========================================================================

(defun c:Estructura (/ key acadObj doc props oldVal newVal err)
  (vl-load-com)

  ;;; --- CONFIGURACIÓN ---
  (setq key "Nombre_Estructura") ;; La propiedad a editar
  ;;; ---------------------

  (setq acadObj (vlax-get-acad-object))
  (setq doc (vlax-get-property acadObj 'ActiveDocument))
  (setq props (vlax-get-property doc 'SummaryInfo))

  ;; 1. OBTENER VALOR ACTUAL
  (setq oldVal "---") 
  (vl-catch-all-apply 
    '(lambda () 
       (vla-getcustombykey props key 'oldVal)
     )
  )

  ;; 2. PEDIR NUEVO VALOR
  (setq newVal (getstring T (strcat "\nNuevo nombre para la estructura <" oldVal ">: ")))

  ;; 3. VALIDAR Y GUARDAR
  (if (and (/= newVal "") (/= newVal oldVal))
    (progn
      (setq err 
        (vl-catch-all-apply 
          'vlax-invoke-method
          (list props 'SetCustomByKey key newVal)
        )
      )
      
      (if (not (vl-catch-all-error-p err))
        (progn
          (princ "\n[AutoCAD] Estructura actualizada. Regenerando Fields...")
          ;; 4. REGENERAR
          (vla-regen doc acAllViewports)
        )
        (princ "\n[Error] No se encontró la propiedad. ¿Ejecutaste el comando de creación primero?")
      )
    )
    (princ "\n[AutoCAD] Sin cambios.")
  )
  (princ)
)


;;; ==========================================================================
;;; COMANDO: NOTOTAL
;;; DESCRIPCIÓN: 
;;;   Permite editar rápidamente el valor de la propiedad personalizada
;;;   "No_total_planos".
;;; ==========================================================================

(defun c:NoTotal (/ key acadObj doc props oldVal newVal err)
  (vl-load-com)

  ;;; --- CONFIGURACIÓN ---
  (setq key "No_total_planos") ;; La propiedad a editar
  ;;; ---------------------

  (setq acadObj (vlax-get-acad-object))
  (setq doc (vlax-get-property acadObj 'ActiveDocument))
  (setq props (vlax-get-property doc 'SummaryInfo))

  ;; 1. OBTENER VALOR ACTUAL
  (setq oldVal "---") 
  (vl-catch-all-apply 
    '(lambda () 
       (vla-getcustombykey props key 'oldVal)
     )
  )

  ;; 2. PEDIR NUEVO VALOR
  (setq newVal (getstring T (strcat "\nNuevo número total de planos <" oldVal ">: ")))

  ;; 3. VALIDAR Y GUARDAR
  (if (and (/= newVal "") (/= newVal oldVal))
    (progn
      (setq err 
        (vl-catch-all-apply 
          'vlax-invoke-method
          (list props 'SetCustomByKey key newVal)
        )
      )
      
      (if (not (vl-catch-all-error-p err))
        (progn
          (princ "\n[AutoCAD] Total de planos actualizado. Regenerando Fields...")
          ;; 4. REGENERAR
          (vla-regen doc acAllViewports)
        )
        (princ "\n[Error] No se encontró la propiedad. ¿Ejecutaste el comando de creación primero?")
      )
    )
    (princ "\n[AutoCAD] Sin cambios.")
  )
  (princ)
)

;;; Mensajes de carga
(princ "\nComando ESTRUCTURA cargado. (Edita 'Nombre_Estructura')")
(princ "\nComando NOTOTAL cargado. (Edita 'No_total_planos')")
(princ)