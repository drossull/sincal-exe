(defun c:CEVIADA ( / p1 p2 p3 ang_rad d_esv d_rect d_rect_cm text_override ent edata user_ang loop)
  
  ;; 1. Si es la PRIMERA VEZ que se ejecuta, obliga a ingresar el ángulo.
  (if (not *ang_esviaje*)
    (progn
      (setq *ang_esviaje* (getreal "\nEs la primera vez que usas el comando. Ingrese el ángulo de esviaje en grados: "))
      ;; Si el usuario presiona Enter sin escribir nada, asignamos 15 por defecto.
      (if (not *ang_esviaje*) (setq *ang_esviaje* 15.0)) 
    )
  )

  ;; 2. Bucle para permitir elegir entre "Hacer Clic" o "Cambiar Ángulo"
  (setq loop T)
  (while loop
    ;; Configuramos "Angulo" como palabra clave permitida
    (initget "Angulo")
    ;; Pedimos el primer punto, mostrando el ángulo actual en la consola
    (setq p1 (getpoint (strcat "\nSeleccione el primer punto o [Angulo para cambiar de " (rtos *ang_esviaje* 2 2) "°]: ")))

    (cond
      ;; CASO A: El usuario escribió "A" o hizo clic en "Angulo"
      ((= p1 "Angulo")
       (setq user_ang (getreal (strcat "\nIngrese el nuevo ángulo de esviaje en grados <" (rtos *ang_esviaje* 2 2) ">: ")))
       (if user_ang (setq *ang_esviaje* user_ang))
       ;; El bucle vuelve a empezar, pidiendo el primer punto nuevamente.
      )

      ;; CASO B: El usuario hizo clic en la pantalla (coordenada válida)
      ((= (type p1) 'LIST)
       (setq loop nil) ;; Rompe el bucle para continuar con la cota
      )

      ;; CASO C: El usuario presionó Enter o Esc sin hacer nada
      (T
       (setq loop nil)
      )
    )
  )

  ;; 3. Si tenemos un punto 1 válido, procedemos con la cota
  (if (and p1 (= (type p1) 'LIST))
    (progn
      (if (and
            (setq p2 (getpoint p1 "\nSeleccione el segundo punto del elemento: "))
            (setq p3 (getpoint "\nSeleccione la ubicación de la línea de cota: "))
          )
        (progn
          ;; 4. Calcula la distancia esviada (real) y la recta (proyectada)
          (setq ang_rad (* pi (/ *ang_esviaje* 180.0)))
          (setq d_esv (distance p1 p2))
          (setq d_rect (* d_esv (cos ang_rad)))
          
          ;; ---> NUEVO: Multiplicamos por 100 para pasar de metros a centímetros
          (setq d_rect_cm (* d_rect 100.0))

          ;; 5. Formatea el texto: <> es el valor original, \X salta la línea
          ;; (rtos d_rect_cm 2 1) muestra el valor en cm con 1 decimal. 
          ;; Si quieres números enteros pon un 0, si quieres 2 decimales pon un 2.
          (setq text_override (strcat "<>\\X(" (rtos d_rect_cm 2 1) ")"))

          ;; 6. Dibuja la cota alineada usando el estilo actual
          (command "_dimaligned" p1 p2 p3)

          ;; 7. Captura la última entidad dibujada (la cota) y le inyecta el nuevo texto
          (setq ent (entlast))
          (setq edata (entget ent))
          (setq edata (subst (cons 1 text_override) (assoc 1 edata) edata))
          (entmod edata)
        )
        (princ "\nComando cancelado o faltan puntos.")
      )
    )
  )
  (princ)
)