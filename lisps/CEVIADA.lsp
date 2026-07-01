(vl-load-com) ; Carga las funciones de Visual LISP necesarias

(defun c:CEVIADA ( / old_err *error* p1 p2 pre_ent last_ent ent_cursor ang_rad factor acadObj doc util user_ang user_prec loop format_tag _InyectarCampo)
  
  ;; 1. Inicialización de entornos de Visual LISP
  (setq acadObj (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acadObj)
        util (vla-get-Utility doc))

  ;; 2. CONFIGURACIÓN INICIAL (Ángulo y Precisión)
  ;; Si es la primera vez que se ejecuta, pide el ángulo
  (if (not *ang_esviaje*)
    (progn
      (setq *ang_esviaje* (getreal "\nEs la primera vez que usas el comando. Ingrese el ángulo de esviaje en grados: "))
      (if (not *ang_esviaje*) (setq *ang_esviaje* 15.0)) 
    )
  )
  ;; Si es la primera vez que se ejecuta, pide el número de decimales (precisión)
  (if (not *prec_cota_recta*)
    (progn
      (setq *prec_cota_recta* (getint "\nIngrese el número de decimales para la cota recta (0, 1, 2, etc.): "))
      (if (not *prec_cota_recta*) (setq *prec_cota_recta* 0)) 
    )
  )

  ;; Calculamos los valores matemáticos iniciales
  (setq ang_rad (* pi (/ *ang_esviaje* 180.0))
        factor (cos ang_rad))

  ;; ---> FUNCIÓN INTERNA: Inyecta la fórmula a una cota específica
  (defun _InyectarCampo (vla_obj / obj_id f_str format_tag)
    (if (vlax-method-applicable-p util 'GetObjectIdString)
      (setq obj_id (vla-GetObjectIdString util vla_obj :vlax-false))
      (setq obj_id (itoa (vla-get-ObjectId vla_obj)))
    )
    
    ;; Construye el código de formato dinámicamente usando la variable global recordada
    (setq format_tag (strcat "%lu2%pr" (itoa *prec_cota_recta*)))

    (setq f_str (strcat 
      "<>\\X("
      "%<\\AcExpr (%<\\AcObjProp Object(%<\\_ObjId " obj_id ">%).Measurement>% * " (rtos factor 2 8) ") \\f \"" format_tag "\">%"
      ")"
    ))
    (vla-put-TextOverride vla_obj f_str)
  )

  ;; ---> MANEJADOR DE ERRORES: Captura la tecla ESC para no perder el trabajo
  (setq old_err *error*)
  (defun *error* (msg)
    (if (and last_ent (not (eq last_ent (entlast))))
      (progn
        (setq ent_cursor last_ent)
        (while (setq ent_cursor (entnext ent_cursor))
          (if (wcmatch (cdr (assoc 0 (entget ent_cursor))) "*DIMENSION")
            (_InyectarCampo (vlax-ename->vla-object ent_cursor))
          )
        )
        (vla-Regen doc acActiveViewport)
      )
    )
    (setq *error* old_err) 
    (princ "\nComando finalizado.")
    (princ)
  )

  ;; 3. BUCLE DE INTERACCIÓN (Hacer clic, cambiar Ángulo [A] o cambiar Precisión [P])
  (setq loop T)
  (while loop
    ;; Configuramos "Angulo" y "Precision" como palabras clave opcionales
    (initget "Angulo Precision")
    (setq p1 (getpoint (strcat "\nPrimer punto | [Angulo (" (rtos *ang_esviaje* 2 2) "°)/Precision (" (itoa *prec_cota_recta*) " dec)]: ")))

    (cond
      ;; CASO A: Cambiar Ángulo
      ((= p1 "Angulo")
       (setq user_ang (getreal (strcat "\nIngrese el nuevo ángulo en grados <" (rtos *ang_esviaje* 2 2) ">: ")))
       (if user_ang (setq *ang_esviaje* user_ang))
       ;; Recalculamos la matemática
       (setq ang_rad (* pi (/ *ang_esviaje* 180.0)) factor (cos ang_rad))
      )
      
      ;; CASO B: Cambiar Precisión
      ((= p1 "Precision")
       (setq user_prec (getint (strcat "\nIngrese el número de decimales para la cota recta <" (itoa *prec_cota_recta*) ">: ")))
       (if user_prec (setq *prec_cota_recta* user_prec))
       ;; El bucle vuelve a empezar mostrando las opciones actualizadas
      )

      ;; CASO C: El usuario hizo un clic válido en la pantalla
      ((= (type p1) 'LIST) (setq loop nil))
      
      ;; CASO D: El usuario presionó Enter o canceló antes de hacer clic
      (T (setq loop nil))
    )
  )

  ;; 4. Procedimiento Principal de Acotación
  (if (and p1 (= (type p1) 'LIST))
    (if (setq p2 (getpoint p1 "\nSeleccione el segundo punto del elemento esviado: "))
      (progn
        (setq pre_ent (entlast)) 
        
        (princ "\nEspecifique la ubicación de la cota: ")
        (command "_dimaligned" p1 p2 pause)

        (if (not (eq pre_ent (entlast)))
          (progn
            (setq last_ent (entlast))
            (_InyectarCampo (vlax-ename->vla-object last_ent))
            (vla-Regen doc acActiveViewport) 

            (princ "\nMODO CONTINUO -> Seleccione los siguientes puntos (Enter o ESC para terminar)...")
            (command "_dimcontinue")
            
            (while (> (getvar "CMDACTIVE") 0)
              (command pause)
            )

            (setq ent_cursor last_ent)
            (while (setq ent_cursor (entnext ent_cursor))
              (if (wcmatch (cdr (assoc 0 (entget ent_cursor))) "*DIMENSION")
                (_InyectarCampo (vlax-ename->vla-object ent_cursor))
              )
            )
            (vla-Regen doc acActiveViewport)
          )
        )
      )
    )
  )
  
  (setq *error* old_err)
  (princ)
)