(vl-load-com) ; Carga las funciones de Visual LISP necesarias

;; Normal unitaria en el plano del UCS. NIL si los puntos coinciden en XY.
(defun CEVIADA:normal (p1 p2 / dx dy len)
  (setq dx (- (car p2) (car p1))
        dy (- (cadr p2) (cadr p1))
        len (sqrt (+ (* dx dx) (* dy dy))))
  (if (> len 1e-9) (list (/ (- dy) len) (/ dx len) 0.0))
)

(defun c:CEVIADA ( / old_err *error* p1 p2 p3 pre_ent last_ent normal dim_pt offset ang_rad factor acadObj doc util user_ang user_prec loop format_tag _InyectarCampo)
  
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
    ;; Cada cota recibe su campo antes de solicitar el siguiente punto.
    ;; ESC conserva las cotas terminadas sin recorrer otras entidades.
    (if last_ent
      (vl-catch-all-apply 'vla-Regen (list doc acActiveViewport)))
    (setq *error* old_err) 
    (if (and msg (not (wcmatch (strcase msg) "*CANCEL*,*QUIT*,*EXIT*,*BREAK*")))
      (princ (strcat "\nCEVIADA: " msg)))
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
        (command "_.dimaligned" "_non" p1 "_non" p2 pause)

        (if (not (eq pre_ent (entlast)))
          (progn
            (setq last_ent (entlast))
            (_InyectarCampo (vlax-ename->vla-object last_ent))
            (vla-Regen doc acActiveViewport) 

            ;; DIMCONTINUE convierte los tramos siguientes en cotas rotadas.
            ;; Crear cada tramo con DIMALIGNED mantiene su longitud y permite
            ;; que siga a los extremos al mover los pinzamientos.
            ;; DXF 10 esta en WCS; los puntos seleccionados estan en UCS.
            (setq normal (CEVIADA:normal p1 p2)
                  dim_pt (trans (cdr (assoc 10 (entget last_ent))) 0 1))
            (if normal
              (progn
                (setq offset (apply '+ (mapcar '* normal (mapcar '- dim_pt p2))))
                (princ "\nMODO CONTINUO ALINEADO -> Seleccione los siguientes puntos (Enter o ESC para terminar)...")
                (while (setq p3 (getpoint p2 "\nSiguiente punto <Terminar>: "))
                  (if (setq normal (CEVIADA:normal p2 p3))
                    (progn
                      ;; Conserva la separacion perpendicular y el lado de la
                      ;; primera cota, incluso si el siguiente tramo gira.
                      (setq dim_pt (mapcar '+ p3
                                     (mapcar '(lambda (n) (* offset n)) normal))
                            pre_ent (entlast))
                      (command "_.dimaligned" "_non" p2 "_non" p3 "_non" dim_pt)
                      (if (not (eq pre_ent (entlast)))
                        (progn
                          (setq last_ent (entlast))
                          (_InyectarCampo (vlax-ename->vla-object last_ent))
                          (vla-Update (vlax-ename->vla-object last_ent))
                          (setq p2 p3)))
                    )
                    (princ "\nSeleccione un punto distinto del anterior.")
                  )
                )
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
