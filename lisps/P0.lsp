;;;------------------------------------------------------------------
;;; LISP: Pegar como Bloque en Origen (Universal)
;;; Comando: P0
;;;
;;; Descripción:
;;; Pega el contenido del portapapeles como un bloque en las 
;;; coordenadas 0,0,0 del espacio actual (sea Modelo o Layout).
;;;------------------------------------------------------------------

(defun c:P0 (/ *error* espacio old-echo before after)
  (setq old-echo (getvar "CMDECHO"))
  (setq *SINCAL_LIVE_RESULT* (list nil "P0 no termino el pegado."))
  (defun *error* (msg)
    (setvar "CMDECHO" old-echo)
    (setq *SINCAL_LIVE_RESULT* (list nil (strcat "P0: " (if msg msg "cancelado"))))
    (princ (strcat "\n" (cadr *SINCAL_LIVE_RESULT*)))
    (princ))
  ;; Guardamos el estado del eco de comandos para que no moleste en la barra
  (setvar "cmdecho" 0)

  ;; 1. Detectamos dónde estamos solo para mostrar el mensaje correcto
  ;; (CVPORT = 1 significa que estamos en Espacio Papel real)
  (if (= (getvar "CVPORT") 1)
      (setq espacio "Layout (Papel)")
      (setq espacio "Modelo")
  )

  (princ (strcat "\n[AutoCAD] Pegando en 0,0 del " espacio "..."))
  
  ;; 2. Ejecutamos el pegado
  ;; Usamos "vl-cmdf" que es más seguro que "command" para verificar si falla.
  ;; "_non" fuerza a ignorar referencias (F3) para que sea el 0,0 exacto.
  (setq before (entlast))
  (vl-cmdf "_.PASTEBLOCK" "_non" (trans '(0.0 0.0 0.0) 0 1))
  (setq after (entlast))
  (setq *SINCAL_LIVE_RESULT*
    (if (and after (not (equal before after)) (= "INSERT" (cdr (assoc 0 (entget after)))))
      (list T "P0: bloque pegado en el origen 0,0,0 del espacio actual. Sin guardar el dibujo.")
      (list nil "P0 no creo un bloque. Copia objetos en CAD con COPYCLIP/Ctrl+C y vuelve a intentar.")))
  (princ (strcat "\n" (cadr *SINCAL_LIVE_RESULT*)))
  
  ;; Restauramos el eco
  (setvar "CMDECHO" old-echo)
  (princ)
)

(princ "\nLISP cargado. Escriba P0 para pegar en el origen (Funciona en Model y Layout).")
(princ)
