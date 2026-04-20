;;; ==========================================================================
;;; COMANDO: NOMBRAR
;;; DESCRIPCIÓN: 
;;;   Permite editar rápidamente el valor de la propiedad personalizada
;;;   "Nombre_Plano" (o la que tú configures).
;;;
;;; ¿PARA QUÉ SIRVE?
;;;   Si usas "Campos" (Fields) en tus carátulas o textos para leer 
;;;   automáticamente el nombre del plano desde las propiedades del archivo
;;;   (DWGPROPS), este comando te ahorra tener que ir al menú Archivo > 
;;;   Propiedades > Personalizar.
;;;
;;; CARACTERÍSTICAS:
;;;   1. Te muestra el valor actual entre <paréntesis angulares>.
;;;   2. Si escribes un nuevo nombre y das Enter, lo actualiza.
;;;   3. Si solo das Enter, mantiene el nombre anterior.
;;;   4. REGENERA (REGEN) automáticamente para actualizar los textos en pantalla.
;;;
;;; CONFIGURACIÓN:
;;;   Busca la sección "CONFIGURACIÓN" más abajo para cambiar "Nombre_Plano"
;;;   por el nombre de la propiedad que tú uses (ej: "Lamina", "Codigo", etc).
;;; ==========================================================================

(defun c:Nombrar (/ key val acadObj doc props oldVal newVal err)
  (vl-load-com)

  ;;; --- CONFIGURACIÓN (EDITAR AQUÍ) ---
  (setq key "Nombre_Plano") ;; El nombre exacto de la propiedad a editar
  ;;; -----------------------------------

  (setq acadObj (vlax-get-acad-object))
  (setq doc (vlax-get-property acadObj 'ActiveDocument))
  (setq props (vlax-get-property doc 'SummaryInfo))

  ;; 1. OBTENER VALOR ACTUAL
  ;; Intentamos leer qué dice la propiedad ahora mismo para mostrártelo
  (setq oldVal "---") 
  (vl-catch-all-apply 
    '(lambda () 
       (vla-getcustombykey props key 'oldVal)
     )
  )

  ;; 2. PEDIR NUEVO VALOR
  ;; getstring T permite escribir frases con espacios
  (setq newVal (getstring T (strcat "\nNuevo nombre para el plano <" oldVal ">: ")))

  ;; 3. VALIDAR Y GUARDAR
  ;; Solo guardamos si escribiste algo Y si es diferente a lo que ya estaba
  (if (and (/= newVal "") (/= newVal oldVal))
    (progn
      ;; Usamos el metodo SetCustomByKey para guardar el dato en las propiedades
      (setq err 
        (vl-catch-all-apply 
          'vlax-invoke-method
          (list props 'SetCustomByKey key newVal)
        )
      )
      
      ;; Verificamos si hubo error (ej: si la propiedad no existía)
      (if (not (vl-catch-all-error-p err))
        (progn
          (princ "\n[AutoCAD] Nombre actualizado. Regenerando Fields...")
          
          ;; 4. REGENERAR
          ;; Forzamos un REGEN para que los textos (Fields) cambien visualmente
          (vla-regen doc acAllViewports)
        )
        (princ "\n[Error] No se encontró la propiedad. ¿Ejecutaste el comando de creación primero?")
      )
    )
    ;; Si el usuario solo dio Enter o escribió lo mismo
    (princ "\n[AutoCAD] Sin cambios.")
  )
  (princ)
)

;;; Mensaje de carga
(princ "\nComando NOMBRAR cargado. Escribe NOMBRAR para editar la propiedad del plano.")
(princ)