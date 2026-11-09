;;; ROMAND - configura RomanD y lo aplica a TEXT/MTEXT seleccionados.
;;; romand.shx, anotativo, papel 2.5, ancho 0.8, sin efectos.
;;; Conserva contenido, campos, anclaje, giro y justificacion de los textos.
;;; Enter sin seleccion configura solo el estilo. No requiere el master.

(defun SRD:AppData (data app / pair entry found)
  (foreach pair data
    (if (= (car pair) -3)
      (foreach entry (cdr pair)
        (if (= (strcase (car entry)) (strcase app)) (setq found entry)))))
  found)

(defun SRD:Flag (data app / item value)
  (foreach item (cdr (SRD:AppData data app))
    (if (= (car item) 1070) (setq value (cdr item))))
  value)

(defun SRD:Valid (/ data)
  (and (setq data (tblobjname "STYLE" "RomanD"))
    (setq data (entget data '("*")))
    (= (strcase (strcat (vl-filename-base (cdr (assoc 3 data)))
                        (vl-filename-extension (cdr (assoc 3 data))))) "ROMAND.SHX")
    (= (cdr (assoc 4 data)) "")
    (equal (cdr (assoc 40 data)) 2.5 1e-9)
    (equal (cdr (assoc 41 data)) 0.8 1e-9)
    (equal (cdr (assoc 50 data)) 0.0 1e-9)
    (= (logand (cdr (assoc 70 data)) 5) 0)
    (= (cdr (assoc 71 data)) 0)
    (= (SRD:Flag data "AcadAnnotative") 1)
    (not (equal (SRD:Flag data "AcadAnnoPO") 1))))

(defun SRD:Put (code value data / old)
  (if (setq old (assoc code data))
    (subst (cons code value) old data)
    (append data (list (cons code value)))))

;; El filtro de aplicaciones de entget en ZWCAD distingue ciertos nombres
;; heredados de APPID. Leer toda la XDATA y comparar sin distinguir mayusculas.
(defun SRD:Configure ()
  (command "_.-STYLE" "RomanD" "romand.shx"
    "_Annotative" "_Yes" "_No" 2.5 0.8 0.0 "_No" "_No" "_No")
  (SRD:Valid))

;; Quita solo fuente, altura, ancho e inclinacion internos de MTEXT.
;; Conserva parrafos, colores, fracciones, escapes, grupos y campos completos.
(defun SRD:UniformMText (text / i n out ch next depth end)
  (setq i 1 n (strlen text) out "" depth 0)
  (while (<= i n)
    (setq ch (substr text i 1) next (substr text i 2))
    (cond
      ((= next "%<")
       (setq depth (1+ depth) out (strcat out next) i (+ i 2)))
      ((and (> depth 0) (= next ">%"))
       (setq depth (1- depth) out (strcat out next) i (+ i 2)))
      ((> depth 0) (setq out (strcat out ch) i (1+ i)))
      ((and (= ch "\\") (member (substr text (1+ i) 1) '("\\" "{" "}")))
       (setq out (strcat out next) i (+ i 2)))
      ((and (= ch "\\") (member (substr text (1+ i) 1) '("f" "F" "H" "W" "Q"))
            (setq end (vl-string-search ";" text (+ i 1))))
       (setq i (+ end 2)))
      (T (setq out (strcat out ch) i (1+ i)))))
  out)

(defun SRD:RawText (data / text pair)
  (setq text "")
  (foreach pair data
    (if (member (car pair) '(1 3)) (setq text (strcat text (cdr pair)))))
  text)

(defun SRD:HasFields (data / dict)
  (and (setq dict (cdr (assoc 360 data))) (dictsearch dict "ACAD_FIELD")))

(defun SRD:SetMText (data text / chunks)
  (while (> (strlen text) 250)
    (setq chunks (cons (cons 3 (substr text 1 250)) chunks)
          text (substr text 251)))
  (append (vl-remove-if '(lambda (pair) (member (car pair) '(1 3))) data)
          (reverse chunks) (list (cons 1 text))))

(defun SRD:Prepare (en / data kind anchor content layer)
  (setq data (entget en '("*")) kind (cdr (assoc 0 data))
        layer (tblsearch "LAYER" (cdr (assoc 8 data))))
  (if (and (member kind '("TEXT" "MTEXT")) (= 0 (logand 4 (cdr (assoc 70 layer)))))
    (cond
      ;; En Alineado/Ajustado, los dos extremos mandan sobre altura/ancho.
      ;; Omitirlos evita desplazar extremos o cambiar su justificacion.
      ((and (= kind "TEXT") (member (cdr (assoc 72 data)) '(3 5))) nil)
      ;; ZWCAD puede convertir campos MTEXT en texto literal al reescribir
      ;; su formato. Conservar estos objetos completos y avisar al usuario.
      ((and (= kind "MTEXT") (SRD:HasFields data)) nil)
      ((= kind "TEXT")
       (setq anchor (if (and (= 0 (cdr (assoc 72 data))) (= 0 (cdr (assoc 73 data)))) 10 11))
       (list en data anchor nil))
      ((setq content (SRD:RawText data))
       (list en data 10 (SRD:UniformMText content))))))

(defun SRD:Apply (item / en original anchor data kind scale)
  (setq en (car item) original (cadr item) anchor (caddr item)
        kind (cdr (assoc 0 original)) data (entget en))
  (if (entmod (SRD:Put 7 "RomanD" data))
    (progn
      (command "_.ANNOUPDATE" en "")
      (setq data (entget en)
            scale (if (= (cdr (assoc 67 data)) 1) 1.0 (getvar "CANNOSCALEVALUE")))
      (setq data (SRD:Put 40 (/ 2.5 scale) data))
      (if (= kind "TEXT")
        (setq data (SRD:Put 41 0.8 (SRD:Put 51 0.0 (SRD:Put 71 0 data))))
        (setq data (SRD:SetMText data (cadddr item))))
      ;; Guardar el anclaje, no el extremo calculado de un texto justificado.
      (setq data (SRD:Put anchor (cdr (assoc anchor original)) data))
      (if (entmod data)
        (progn
          (entupd en)
          (setq data (entget en '("*")))
          (and (= (strcase (cdr (assoc 7 data))) "ROMAND")
               (equal (cdr (assoc anchor data)) (cdr (assoc anchor original)) 1e-8)
               (equal (cdr (assoc 40 data)) (/ 2.5 scale) 1e-8)
               (or (= (cdr (assoc 67 data)) 1) (= (SRD:Flag data "AcadAnnotative") 1))))))))

(defun SRD:Run (selection / *error* echo begun items skipped i item result failed)
  (setq echo (getvar "CMDECHO") items nil skipped 0 i 0)
  (defun *error* (msg)
    (if begun
      (progn (command-s "_.UNDO" "_End") (setq begun nil) (command-s "_.U")))
    (setvar "CMDECHO" echo)
    (if (and msg (not (wcmatch (strcase msg) "*CANCEL*,*QUIT*,*EXIT*")))
      (princ (strcat "\nROMAND: " msg " Se revirtieron los cambios.")))
    (princ))
  (cond
    ((not (findfile "romand.shx"))
     (princ "\nROMAND: no se encuentra romand.shx. No se modifico el dibujo."))
    (T
     (vl-load-com)
     ;; Capturar posiciones y campos antes de cambiar el estilo existente.
     (if selection
       (repeat (sslength selection)
         (setq item (vl-catch-all-apply 'SRD:Prepare (list (ssname selection i))) i (1+ i))
         (if (and item (not (vl-catch-all-error-p item)))
           (setq items (cons item items)) (setq skipped (1+ skipped)))))
     (setvar "CMDECHO" 0)
     (command "_.UNDO" "_Begin") (setq begun T)
     (if (SRD:Configure)
       (progn
         (while (and items (not failed))
           (setq result (vl-catch-all-apply 'SRD:Apply (list (car items))))
           (if (or (not result) (vl-catch-all-error-p result))
             (setq failed T)
             (setq items (cdr items))))
         (if failed
           (*error* "No se pudo aplicar la configuracion conservando el anclaje")
           (progn
             (setvar "TEXTSTYLE" "RomanD")
             (command "_.REGENALL")
             (command "_.UNDO" "_End") (setq begun nil)
             (setvar "CMDECHO" echo)
             (princ "\nRomanD actual: romand.shx, anotativo, papel 2.5, ancho 0.8, angulo 0.")
             (if selection
               (princ (strcat "\nTextos configurados: " (itoa (- (sslength selection) skipped))
                              ". Contenido, anclaje y giro conservados.")))
             (if (> skipped 0)
               (princ (strcat "\nOmitidos: " (itoa skipped)
                 " (capa bloqueada, texto Alineado/Ajustado o MTEXT con campos)."))))))
       (*error* "No se pudo verificar la configuracion del estilo"))))
  (princ))

(defun c:ROMAND (/ selection)
  (setq selection (ssget "_I" '((0 . "TEXT,MTEXT"))))
  (if (not selection)
    (progn
      (princ "\nSeleccione TEXT/MTEXT para aplicar RomanD <Enter: solo configurar el estilo>: ")
      (setq selection (ssget '((0 . "TEXT,MTEXT"))))))
  (SRD:Run selection)
  (princ))

(princ)
