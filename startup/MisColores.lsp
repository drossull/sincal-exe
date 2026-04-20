;;; ==========================================================================
;;; COMANDOS DE COLOR (C1 - C9) - VERSIÓN ACTIVEX (BLINDADA)
;;; Esta versión no usa la barra de comandos, por lo que no falla con
;;; "Invalid option keyword" ni problemas de idioma.
;;; ==========================================================================

;;; --- MOTOR INTERNO (MODIFICA LA BASE DE DATOS DIRECTAMENTE) ---
(defun CambiarColor (col / ss i ent obj)
  (vl-load-com) ; Cargar motor Visual Lisp
  
  ;; 1. GESTIÓN DE SELECCIÓN (Previa o Nueva)
  (setq ss (ssget "_I"))
  (if (not ss)
      (setq ss (ssget))
  )

  ;; 2. PROCESO DE CAMBIO
  (if ss
    (progn
      (setq i 0)
      ;; Recorremos cada objeto seleccionado uno por uno
      (repeat (sslength ss)
        (setq ent (ssname ss i))                 ; Nombre de entidad
        (setq obj (vlax-ename->vla-object ent))  ; Convertir a Objeto VLA
        
        ;; EL TRUCO: Cambiamos la propiedad directamente sin usar comandos
        ;; Si hay error (ej: objeto bloqueado), lo ignoramos y seguimos
        (vl-catch-all-apply 'vla-put-Color (list obj col))
        
        (setq i (1+ i))
      )
      (princ (strcat "\nExito: Objetos pasados a color " (itoa col) "."))
    )
    (princ "\nCancelado o sin selección.")
  )
  (princ)
)

;;; --- LISTA DE COMANDOS ---
(defun c:c1 () (CambiarColor 1))   ; Rojo
(defun c:c2 () (CambiarColor 2))   ; Amarillo
(defun c:c3 () (CambiarColor 3))   ; Verde
(defun c:c4 () (CambiarColor 4))   ; Cian
(defun c:c5 () (CambiarColor 5))   ; Azul
(defun c:c6 () (CambiarColor 6))   ; Magenta
(defun c:c7 () (CambiarColor 7))   ; Blanco/Negro
(defun c:c8 () (CambiarColor 8))   ; Gris
(defun c:c9 () (CambiarColor 9))   ; Gris Claro
(defun c:c0 () (CambiarColor 256)) ; PorCapa (ByLayer)

(princ "\n[AutoCAD] Colores ActiveX cargados. Intenta usar C4 ahora.")
(princ)