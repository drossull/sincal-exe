;;;------------------------------------------------------------------
;;; LISP: Pegar como Bloque en Origen (Universal)
;;; Comando: P0
;;;
;;; Descripción:
;;; Pega el contenido del portapapeles como un bloque en las 
;;; coordenadas 0,0,0 del espacio actual (sea Modelo o Layout).
;;;------------------------------------------------------------------

(defun c:P0 (/ espacio)
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
  (if (vl-cmdf "_.PASTEBLOCK" "_non" "0,0,0")
      (princ "\n-> Éxito: Bloque pegado en el origen.")
      (princ "\n-> Error: No hay nada en el portapapeles o comando cancelado.")
  )
  
  ;; Restauramos el eco
  (setvar "cmdecho" 1)
  (princ)
)

(princ "\nLISP cargado. Escriba P0 para pegar en el origen (Funciona en Model y Layout).")
(princ)