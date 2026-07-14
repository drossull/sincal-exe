;;; =========================================================================
;;; COMANDO: SINCAL-ESCALAS
;;; Crea escalas de dibujo estandarizadas para planos trabajados en METROS
;;; =========================================================================
(defun c:SINCAL-ESCALAS (/ SINCAL:CrearEscala listaEscalas)
  (vl-load-com)
  (setvar "CMDECHO" 0)

  ;; Función auxiliar para crear una escala de forma segura y sin bugs
  (defun SINCAL:CrearEscala (nombre proporcion)
    ;; 1. Intentamos borrarla primero por si ya existe (evita el error de "Redefinir")
    (vl-catch-all-apply 'vl-cmdf (list "_.-SCALELISTEDIT" "_Delete" nombre "_Exit"))
    ;; 2. La agregamos limpiamente con la proporción matemática correcta
    (vl-cmdf "_.-SCALELISTEDIT" "_Add" nombre proporcion "_Exit")
  )

  ;; Lista maestra de escalas SINCAL (Nombre . Proporción Papel:Dibujo)
  ;; MATEMÁTICA: Como el Layout (papel) se imprime en mm y el Model en metros,
  ;; 1000 mm de papel equivalen a X metros del modelo real.
  (setq listaEscalas
    '(
      ("1:5 (m)"   . "1000:5")
      ("1:10 (m)"  . "1000:10")
      ("1:20 (m)"  . "1000:20")
      ("1:25 (m)"  . "1000:25")
      ("1:50 (m)"  . "1000:50")
      ("1:75 (m)"  . "1000:75")
      ("1:100 (m)" . "1000:100")
      ("1:200 (m)" . "1000:200")
      ("1:250 (m)" . "1000:250")
      ("1:500 (m)" . "1000:500")
      ("1:1000 (m)". "1000:1000")
    )
  )

  (princ "\n--- GENERANDO ESCALAS SINCAL (METROS) ---")
  
  ;; Bucle de inyección
  (foreach esc listaEscalas
    (SINCAL:CrearEscala (car esc) (cdr esc))
    (princ (strcat "\n[+] Escala inyectada: " (car esc)))
  )

  (setvar "CMDECHO" 1)
  (princ "\n[SINCAL] Escalas generadas correctamente. Ya puedes asignarlas en tus Viewports.")
  (princ)
)

;;; FIN DEL CODIGO