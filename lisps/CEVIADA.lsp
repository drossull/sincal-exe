(vl-load-com) ; Carga las funciones de Visual LISP necesarias

(defun c:CEVIADA ( / old_err *error* p1 p2 pre_ent last_ent ent_cursor ang_rad factor acadObj doc util user_ang loop _InyectarCampo)
  
  ;; 1. Inicialización de entornos de Visual LISP
  (setq acadObj (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acadObj)
        util (vla-get-Utility doc))

  ;; 2. Lógica del ángulo de esviaje
  (if (not *ang_esviaje*)
    (progn
      (setq *ang_esviaje* (getreal "\nEs la primera vez que usas el comando. Ingrese el ángulo de esviaje en grados: "))
      (if (not *ang_esviaje*) (setq *ang_esviaje* 15.0)) 
    )
  )
  (setq ang_rad (* pi (/ *ang_esviaje* 180.0))
        factor (cos ang_rad))

  ;; ---> FUNCIÓN INTERNA: Inyecta la fórmula a una cota específica
  (defun _InyectarCampo (vla_obj / obj_id f_str)
    (if (vlax-method-applicable-p util 'GetObjectIdString)
      (setq obj_id (vla-GetObjectIdString util vla_obj :vlax-false))
      (setq obj_id (itoa (vla-get-ObjectId vla_obj)))
    )
    (setq f_str (strcat 
      "<>\\X("
      "%<\\AcExpr (%<\\AcObjProp Object(%<\\_ObjId " obj_id ">%).Measurement>% * " (rtos factor 2 8) ") \\f \"%lu2%pr0\">%"
      ")"
    ))
    (vla-put-TextOverride vla_obj f_str)
  )

  ;; ---> MANEJADOR DE ERRORES: Captura la tecla ESC para no perder el trabajo
  (setq old_err *error*)
  (defun *error* (msg)
    ;; Si existe una cota base y se crearon nuevas cotas continuas, aplícales el cálculo
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
    (setq *error* old_err) ; Restaurar AutoCAD a la normalidad
    (princ "\nComando finalizado.")
    (princ)
  )

  ;; 3. Bucle para interactuar (Hacer clic o cambiar ángulo)
  (setq loop T)
  (while loop
    (initget "Angulo")
    (setq p1 (getpoint (strcat "\nSeleccione el primer punto (Medida Esviada) o [Angulo para cambiar de " (rtos *ang_esviaje* 2 2) "°]: ")))

    (cond
      ((= p1 "Angulo")
       (setq user_ang (getreal (strcat "\nIngrese el nuevo ángulo en grados <" (rtos *ang_esviaje* 2 2) ">: ")))
       (if user_ang (setq *ang_esviaje* user_ang))
       ;; Se actualiza la matemática por si cambió el ángulo
       (setq ang_rad (* pi (/ *ang_esviaje* 180.0)) factor (cos ang_rad))
      )
      ((= (type p1) 'LIST) (setq loop nil))
      (T (setq loop nil))
    )
  )

  ;; 4. Procedimiento Principal
  (if (and p1 (= (type p1) 'LIST))
    (if (setq p2 (getpoint p1 "\nSeleccione el segundo punto del elemento esviado: "))
      (progn
        (setq pre_ent (entlast)) ; Tomamos una "foto" de la base de datos antes de dibujar
        
        ;; ---> COTA INICIAL CON PREVISUALIZACIÓN (PAUSE)
        (princ "\nEspecifique la ubicación de la cota: ")
        (command "_dimaligned" p1 p2 pause)

        ;; Verificamos si el usuario realmente colocó la cota (no canceló)
        (if (not (eq pre_ent (entlast)))
          (progn
            (setq last_ent (entlast)) ; Esta es nuestra primera cota
            (_InyectarCampo (vlax-ename->vla-object last_ent))
            (vla-Regen doc acActiveViewport) ; Actualizamos la pantalla al instante

            ;; ---> MODO CONTINUO CON PREVISUALIZACIÓN NATIVA
            (princ "\nMODO CONTINUO -> Seleccione los siguientes puntos (Enter o ESC para terminar)...")
            (command "_dimcontinue")
            
            ;; Pausa indefinida mientras la cota continua esté activa
            (while (> (getvar "CMDACTIVE") 0)
              (command pause)
            )

            ;; Si el usuario termina presionando Enter (en vez de ESC), procesamos todo aquí:
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
  
  (setq *error* old_err) ; Si todo salió bien, restauramos los errores al salir
  (princ)
)