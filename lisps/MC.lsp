;;; ==========================================================================
;;; COMANDO: MC (Middle Center)
;;; DESCRIPCIÓN: 
;;;   Cambia la justificación de Textos (DText) y Textos Múltiples (MText)
;;;   a "Medio Centro" (Middle Center).
;;;
;;; ¿POR QUÉ USAR ESTO?
;;;   Si cambias la justificación desde la paleta de "Propiedades", el texto
;;;   se mueve y salta de lugar.
;;;   Esta rutina usa el comando interno "JUSTIFYTEXT", lo que permite cambiar
;;;   el punto de inserción SIN que el texto se mueva visualmente de su sitio.
;;;
;;; INSTRUCCIONES:
;;;   1. Cargue el archivo con APPLOAD.
;;;   2. Escriba el comando MC y presione Enter.
;;;   3. Seleccione todos los textos que quiera centrar.
;;; ==========================================================================

(defun c:MC (/ ss)
  (princ "\nSelecciona los textos o MText para centrar (Middle Center): ")
  
  ;; Filtramos la selección para aceptar solo TEXT y MTEXT
  ;; Evitamos que selecciones líneas o bloques por error.
  (if (setq ss (ssget '((0 . "*TEXT"))))
    (progn
      ;; Ejecutamos el comando nativo para que el texto no se mueva de sitio
      ;; "MC" corresponde a Middle Center (Medio Centro)
      (command "_.JUSTIFYTEXT" ss "" "MC")
      (princ (strcat "\nExito: Se han centrado " (itoa (sslength ss)) " textos."))
    )
    ;; Si el usuario cancela o no selecciona textos
    (princ "\nNo se seleccionaron textos válidos.")
  )
  (princ)
)

;;; Mensaje al cargar
(princ "\nComando MC cargado. Escriba MC para centrar textos.")
(princ)