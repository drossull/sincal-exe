;;; TXT-JOIN -- Reconstruye TEXT fragmentados en un MTEXT, sin Express Tools.
;;; Seleccionar un solo bloque de lectura/columna cada vez.
;;; No hace OCR: LINE, LWPOLYLINE, bloques, atributos y MTEXT se omiten.
;;; Orden geometrico, no correccion linguistica: revisar cifras y espacios.
;;; API nativa AutoLISP para AutoCAD 2025/2027 y ZWCAD 2026.
;;;
;;; Registro: (entidad cadena izquierda derecha base inferior superior altura dxf).
;;; Coordenadas de lectura = WCS girado por -angulo del texto de referencia.

(defun TXU:Get (key data fallback / pair)
  (if (setq pair (assoc key data)) (cdr pair) fallback)
)

(defun TXU:Rotate (p a)
  (list (- (* (car p) (cos a)) (* (cadr p) (sin a)))
        (+ (* (car p) (sin a)) (* (cadr p) (cos a)))
        (if (caddr p) (caddr p) 0.0))
)

(defun TXU:Compatible (d ref / style)
  (setq style (tblsearch "STYLE" (TXU:Get 7 d "Standard")))
  (and
    (= (TXU:Get 0 d "") "TEXT")
    (> (TXU:Get 40 d 0.0) 0.0)
    (equal (TXU:Get 210 d '(0.0 0.0 1.0)) '(0.0 0.0 1.0) 1.0e-8)
    (= 0 (logand 6 (TXU:Get 71 d 0))) ; sin espejo
    (= 0 (logand 4 (TXU:Get 70 style 0))) ; sin escritura vertical
    (not (member (TXU:Get 72 d 0) '(3 4 5))) ; alineado/ajustado requieren otro calculo
    (not (wcmatch (TXU:Get 1 d "") "*%<*")) ; no convertir campos en texto literal
    (or (null ref)
      (and
        (> (cos (- (TXU:Get 50 d 0.0) (TXU:Get 50 ref 0.0))) 0.99999999)
        (equal (caddr (cdr (assoc 10 d))) (caddr (cdr (assoc 10 ref))) 1.0e-6)
        (= (TXU:Get 410 d "") (TXU:Get 410 ref ""))
      )
    )
  )
)

(defun TXU:Read (ent a / d box origin lo hi)
  (setq d (entget ent) box (textbox d))
  (if box
    (progn
      ;; TEXT group 10 is the computed baseline origin, also for justified text.
      (setq origin (TXU:Rotate (cdr (assoc 10 d)) (- a))
            lo (car box) hi (cadr box))
      (list ent (cdr (assoc 1 d))
        (+ (car origin) (car lo)) (+ (car origin) (car hi))
        (cadr origin)
        (+ (cadr origin) (cadr lo)) (+ (cadr origin) (cadr hi))
        (cdr (assoc 40 d)) d)
    )
  )
)

(defun TXU:Reference (ss / i d ref score best)
  (setq i 0 best -1)
  (repeat (sslength ss)
    (setq d (entget (ssname ss i)) i (1+ i))
    (if (TXU:Compatible d nil)
      (progn
        (setq score (strlen (TXU:Get 1 d "")))
        (if (> score best) (setq ref d best score))
      )
    )
  )
  ref
)

(defun TXU:Collect (ss ref / i ent d records omitted r)
  (setq i 0 omitted 0)
  (repeat (sslength ss)
    (setq ent (ssname ss i) d (entget ent) i (1+ i))
    (if (and (TXU:Compatible d ref)
             (setq r (TXU:Read ent (TXU:Get 50 ref 0.0))))
      (setq records (cons r records))
      (setq omitted (1+ omitted))
    )
  )
  (list records omitted)
)

(defun TXU:Rows (records tolerance / sorted rows row anchor r)
  ;; Sort indices, not records: VL-SORT may remove equal items/characters.
  (setq sorted
    (mapcar '(lambda (i) (nth i records))
      (vl-sort-i records
        '(lambda (a b)
          (if (equal (nth 4 a) (nth 4 b) 1.0e-9)
            (< (nth 2 a) (nth 2 b))
            (> (nth 4 a) (nth 4 b)))))))
  (foreach r sorted
    (if (and anchor
        (> (abs (- (nth 4 anchor) (nth 4 r)))
           (* tolerance (min (nth 7 anchor) (nth 7 r)))))
      (progn (setq rows (cons row rows) row nil anchor nil))
    )
    (if (null anchor) (setq anchor r))
    (setq row (cons r row))
  )
  (if row (setq rows (cons row rows)))
  (mapcar
    '(lambda (line)
      (mapcar '(lambda (i) (nth i line))
        (vl-sort-i line '(lambda (a b) (< (nth 2 a) (nth 2 b))))))
    (reverse rows))
)

(defun TXU:Escape (s / i ch code out under over strike digits)
  ;; TEXT control codes translated explicitly; braces/backslashes kept literal.
  (setq i 1 out "")
  (while (<= i (strlen s))
    (setq ch (substr s i 1))
    (cond
      ((and (= ch "\\") (= (strcase (substr s i 3)) "\\U+")
            (<= (+ i 6) (strlen s)))
        (setq out (strcat out (substr s i 7)) i (+ i 7)))
      ((= ch "\\") (setq out (strcat out "\\\\") i (1+ i)))
      ((member ch '("{" "}")) (setq out (strcat out "\\" ch) i (1+ i)))
      ((and (= (substr s i 2) "%%") (<= (+ i 2) (strlen s)))
        (setq code (strcase (substr s (+ i 2) 1))
              digits (substr s (+ i 2) 3))
        (cond
          ((= code "D") (setq out (strcat out "\\U+00B0") i (+ i 3)))
          ((= code "P") (setq out (strcat out "\\U+00B1") i (+ i 3)))
          ((= code "C") (setq out (strcat out "\\U+2205") i (+ i 3)))
          ((= code "U")
            (setq under (not under) out (strcat out (if under "\\L" "\\l")) i (+ i 3)))
          ((= code "O")
            (setq over (not over) out (strcat out (if over "\\O" "\\o")) i (+ i 3)))
          ((= code "K")
            (setq strike (not strike) out (strcat out (if strike "\\K" "\\k")) i (+ i 3)))
          ((= code "%") (setq out (strcat out "%") i (+ i 3)))
          ((wcmatch digits "###")
            (setq out (strcat out (TXU:Escape (chr (atoi digits)))) i (+ i 5)))
          (T (setq out (strcat out ch) i (1+ i)))
        ))
      (T (setq out (strcat out ch) i (1+ i)))
    )
  )
  (strcat out (if under "\\l" "") (if over "\\o" "") (if strike "\\k" ""))
)

(defun TXU:Real (n / text)
  ;; DIMZIN and locale must not turn 0.5 into .5 or a decimal comma.
  (setq text (rtos n 2 8))
  (vl-string-translate "," "." text)
)

(defun TXU:Format (r base / d)
  (setq d (nth 8 r))
  ;; Uniform font/style, layer and color from reference; retain size/width/slant.
  (strcat "{\\H" (TXU:Real (/ (nth 7 r) base)) "x;\\W"
    (TXU:Real (TXU:Get 41 d 1.0)) ";\\Q"
    (TXU:Real (* (/ 180.0 pi) (TXU:Get 51 d 0.0))) ";"
    (TXU:Escape (nth 1 r)) "}")
)

(defun TXU:Spaces (count / out)
  (setq out "")
  (repeat (min 80 (max 0 count)) (setq out (strcat out "\\~")))
  out
)

(defun TXU:JoinRow (row threshold base left / out prev r gap h amount s p)
  (setq out (TXU:Spaces (fix (+ 0.5 (/ (- (nth 2 (car row)) left) (* 0.5 base))))))
  (foreach r row
    (if prev
      (progn
        (setq h (min (nth 7 prev) (nth 7 r))
              gap (- (nth 2 r) (nth 3 prev))
              s (nth 1 r) p (nth 1 prev))
        ;; Existing spaces remain; do not add another inferred space around them.
        (if (and (> gap (* threshold h))
                 (/= (substr s 1 1) " ")
                 (/= (substr p (max 1 (strlen p)) 1) " "))
          (progn
            (setq amount (max 1 (fix (+ 0.5 (/ gap (* 0.5 h))))))
            (setq out (strcat out (if (= amount 1) " " (TXU:Spaces amount))))
          )
        )
      )
    )
    (setq out (strcat out (TXU:Format r base)) prev r)
  )
  out
)

(defun TXU:Build (rows threshold base left / out previous row dy height)
  (setq out "")
  (foreach row rows
    (if previous
      (progn
        (setq out (strcat out "\\P")
              dy (- (nth 4 (car previous)) (nth 4 (car row)))
              height (max (apply 'max (mapcar '(lambda (r) (nth 7 r)) previous))
                          (apply 'max (mapcar '(lambda (r) (nth 7 r)) row))))
        (if (> dy (* 2.0 height)) (setq out (strcat out "\\P")))
      )
    )
    (setq out (strcat out (TXU:JoinRow row threshold base left))
          previous row)
  )
  out
)

;;; Structured mode: geometry -> cells -> paragraphs -> editable indentation.
;;; Number inference is optional. It never renumbers existing explicit labels.
(defun TXU:Trim (s) (vl-string-trim " \t\r\n" s))

(defun TXU:Compact (s / out ch space)
  (setq out "")
  (foreach ch (vl-string->list s)
    (if (member ch '(9 10 13 32))
      (setq space T)
      (progn
        (if (and space (/= out "")) (setq out (strcat out " ")))
        (setq out (strcat out (chr ch)) space nil))))
  out)

(defun TXU:Prefix (s / i ch lastdot digits)
  ;; Require a trailing period: 1.2. is a label, 1.2 mm is a measurement.
  (setq s (TXU:Trim s) i 1 digits nil)
  (while (and (<= i (strlen s))
              (or (wcmatch (setq ch (substr s i 1)) "#") (= ch ".")))
    (if (= ch ".") (if digits (setq lastdot i digits nil) (setq lastdot nil))
      (setq digits T))
    (setq i (1+ i)))
  (if (and lastdot (= lastdot (1- i)))
    (list (substr s 1 lastdot) (TXU:Trim (substr s i)))))

(defun TXU:Cells (row threshold base / cells text x prev r gap)
  (setq text "" x (TXU:AnchorX (car row)))
  (foreach r row
    (setq gap (if prev (- (nth 2 r) (nth 3 prev)) 0.0))
    (cond
      ((and prev (> gap (* 1.8 base)))
        (setq cells (cons (list x (TXU:Compact text)) cells)
              x (TXU:AnchorX r) text ""))
      ((and prev (> gap (* threshold (min (nth 7 prev) (nth 7 r)))))
        (setq text (strcat text " "))))
    (setq text (strcat text (nth 1 r)) prev r))
  (reverse (cons (list x (TXU:Compact text)) cells)))

(defun TXU:AnchorX (r / d)
  ;; Ink side bearings vary by first glyph; column anchors must not vary with it.
  (setq d (nth 8 r))
  (car (TXU:Rotate (cdr (assoc 10 d)) (- (TXU:Get 50 d 0.0)))))

(defun TXU:RowInfo (row threshold base / cells text title r cell)
  (setq cells (TXU:Cells row threshold base) text "")
  (foreach cell cells (setq text (strcat text (if (= text "") "" " ") (cadr cell))))
  (foreach r row
    (if (or (vl-string-search "%%U" (strcase (nth 1 r)))
            (> (nth 7 r) (* base 1.25))) (setq title T)))
  (list (cons 'text (TXU:Trim text)) (cons 'cells cells) (cons 'title title)
    (cons 'x (nth 2 (car row))) (cons 'y (nth 4 (car row)))
    (cons 'right (apply 'max (mapcar '(lambda (r) (nth 3 r)) row)))
    (cons 'height (apply 'max (mapcar '(lambda (r) (nth 7 r)) row)))))

(defun TXU:TableRow (p / cells)
  (setq cells (cdr (assoc 'cells p)))
  (and (> (length cells) 1)
    (not (TXU:Prefix (cdr (assoc 'text p))))
    (not (vl-string-search ":" (cdr (assoc 'text p))))
    (vl-every '(lambda (c) (< (strlen (cadr c)) 45)) cells)))

(defun TXU:Ends (s ending)
  (and (>= (strlen s) (strlen ending))
    (= (substr s (1+ (- (strlen s) (strlen ending)))) ending)))

(defun TXU:Paragraphs (rows threshold base left / result p prev s old width expanded split row key)
  (setq width (- (apply 'max (mapcar '(lambda (r) (nth 3 r)) (apply 'append rows))) left))
  (foreach row rows
    (setq p (TXU:RowInfo row threshold base) s (cdr (assoc 'text p)) prev (car result))
    (if (and prev (not (cdr (assoc 'title p))) (not (cdr (assoc 'title prev)))
             (not (TXU:Prefix s)) (not (TXU:TableRow p)) (not (TXU:TableRow prev))
             (or (null (vl-string-search ":" s))
                 (and (TXU:Ends s ":")
                   (vl-string-search "DEBE CUMPLIR CON" (strcase (cdr (assoc 'text prev))))))
             (< (- (cdr (assoc 'y prev)) (cdr (assoc 'y p))) (* 2.0 base))
             (> (- (cdr (assoc 'right prev)) left) (* 0.65 width))
             (not (wcmatch (cdr (assoc 'text prev)) "*[.:;]"))
             (>= (cdr (assoc 'x p)) (- (cdr (assoc 'x prev)) (* 0.5 base))))
      (progn
        (setq old (cdr (assoc 'text prev)))
        (setq prev (subst (cons 'text (strcat old " " s)) (assoc 'text prev) prev))
        ;; Track last physical row to support continuations of any length.
        (foreach key '(y right)
          (setq prev (subst (assoc key p) (assoc key prev) prev)))
        (setq result (cons prev (cdr result))))
      (setq result (cons p result))))
  ;; A normative clause glued to an engineering unit is a separate paragraph.
  ;; Keep every source character; only insert a paragraph boundary.
  (foreach p (reverse result)
    (setq s (cdr (assoc 'text p)) split (vl-string-search "DEBE CUMPLIR CON" (strcase s)))
    (if (and split (> split 0) (not (cdr (assoc 'title p)))
             (not (TXU:Prefix s)) (TXU:Ends s ":"))
      (setq expanded (append expanded
        (list (subst (cons 'text (TXU:Trim (substr s 1 split))) (assoc 'text p) p)
              (subst (cons 'text (substr s (1+ split))) (assoc 'text p) p))))
      (setq expanded (append expanded (list p)))))
  expanded)

(defun TXU:Field (s / pos)
  (setq pos (vl-string-search ":" s))
  (and pos (< (strlen s) 65) (not (TXU:Ends s ":"))))

(defun TXU:Decorate (p label level)
  (if label
    (setq level (max level (1- (length (vl-remove-if-not '(lambda (ch) (= ch 46)) (vl-string->list label)))))))
  (append (list (cons 'label label) (cons 'level level)) p))

(defun TXU:Group (head children infer / prefix body output count subcount parent p s label fields)
  (setq prefix (TXU:Prefix (cdr (assoc 'text head))))
  (if (null prefix)
    (cons (TXU:Decorate head nil 0)
      (mapcar '(lambda (p) (TXU:Decorate p nil 0)) children))
    (progn
      (setq body (cadr prefix) head (subst (cons 'text body) (assoc 'text head) head))
      (cond
        ;; A single narrative after a heading belongs to that same item.
        ((and (= (length children) 1) (TXU:Ends body ":")
              (not (TXU:Field (cdr (assoc 'text (car children)))))
              (not (TXU:TableRow (car children)))
              (not (TXU:Ends (cdr (assoc 'text (car children))) ":")))
          (list (TXU:Decorate
            (subst (cons 'text (strcat body " " (cdr (assoc 'text (car children)))))
              (assoc 'text head) head) (car prefix) 0)))
        (T
          (setq output (list (TXU:Decorate head (car prefix) 0)) count 0 subcount 0
                fields (and (> (length children) 1)
                  (vl-every '(lambda (p) (TXU:Field (cdr (assoc 'text p)))) children)))
          (foreach p children
            (setq s (cdr (assoc 'text p)) label nil)
            (if (and infer (TXU:Ends body ":") (not fields) (not (TXU:TableRow p)))
              (if parent
                (progn (setq subcount (1+ subcount) label (strcat parent (itoa subcount) "."))
                  (setq output (append output (list (TXU:Decorate p label 2)))))
                (progn
                  (setq count (1+ count) label (strcat (car prefix) (itoa count) "."))
                  (setq output (append output (list (TXU:Decorate p label 1))))
                  (if (TXU:Ends s ":") (setq parent label))))
              (setq output (append output (list (TXU:Decorate p nil 1))))))
          output)))))

(defun TXU:Hierarchy (paragraphs infer / out head children p)
  (foreach p paragraphs
    (if (or (cdr (assoc 'title p)) (TXU:Prefix (cdr (assoc 'text p))))
      (progn
        (if head (setq out (append out (TXU:Group head (reverse children) infer))))
        (setq head p children nil))
      (if head (setq children (cons p children)) (setq head p))))
  (if head (setq out (append out (TXU:Group head (reverse children) infer))))
  out)

(defun TXU:Units (s / i token found out before after)
  ;; Only exponent typography changes; numeric values and unit names survive.
  (setq i 1 out "")
  (while (<= i (strlen s))
    (setq found nil before (if (> i 1) (substr s (1- i) 1) " "))
    (foreach token '("mm2" "cm2" "km2" "m2" "mm3" "cm3" "m3")
      (setq after (substr s (+ i (strlen token)) 1))
      (if (and (null found) (= (substr s i (strlen token)) token)
               (not (wcmatch before "[a-zA-Z]")) (not (wcmatch after "[a-zA-Z0-9]")))
        (setq found token)))
    (if found
      (setq out (strcat out (substr found 1 (1- (strlen found)))
              "{\\H0.7x;\\S" (substr found (strlen found)) "^;}")
            i (+ i (strlen found)))
      (setq out (strcat out (substr s i 1)) i (1+ i))))
  out)

(defun TXU:Structured (rows threshold base left infer / paragraphs out p s label level indent first tabs content cell x title previous pos)
  (setq paragraphs (TXU:Hierarchy (TXU:Paragraphs rows threshold base left) infer) out "")
  (foreach p paragraphs
    (setq s (cdr (assoc 'text p)) label (cdr (assoc 'label p))
          level (cdr (assoc 'level p)) title (cdr (assoc 'title p)))
    (if (/= out "")
      (setq out (strcat out "\\P" (if (and (or title previous) (not (and title previous))) "\\P" ""))))
    (cond
      ((and (not title) (not label) (TXU:TableRow p))
        (setq tabs "" content "")
        (foreach cell (cdr (assoc 'cells p))
          (setq x (max 0.0 (/ (- (car cell) left) base)))
          (if (/= content "")
            (setq tabs (strcat tabs (if (= tabs "") "" ",") (TXU:Real x))
                  content (strcat content "\t")))
          (setq content (strcat content (TXU:Units (TXU:Escape (cadr cell))))))
        (setq out (strcat out "\\pxi0,l"
          (TXU:Real (max 0.0 (/ (- (caar (cdr (assoc 'cells p))) left) base)))
          ",r0,ql,t" tabs ";" content)))
      (T
        (setq indent (cond (title 0) (label (+ 4 (* 3 level))) ((> level 0) 4) (T 0))
              first (if label (- (+ 3 (* 2 level))) 0)
              content (TXU:Units (TXU:Escape s)) tabs (itoa indent))
        (if (and (not title) (TXU:Field s))
          (progn
            (setq pos (vl-string-search ":" s)
                  content (strcat (TXU:Units (TXU:Escape (TXU:Trim (substr s 1 (1+ pos)))))
                    "\t" (TXU:Units (TXU:Escape (TXU:Trim (substr s (+ pos 2))))))
                  tabs (strcat tabs "," (itoa (+ indent 16))))))
        (setq out (strcat out "\\pxi" (itoa first) ",l" (itoa indent) ",r0,ql,t"
          tabs ";" (if label (strcat label "\t") "") content))))
    (setq previous title))
  out)

(defun TXU:Chunks (text / chunks)
  (while (> (strlen text) 250)
    (setq chunks (cons (cons 3 (substr text 1 250)) chunks)
          text (substr text 251)))
  (append (reverse chunks) (list (cons 1 text)))
)

(defun TXU:Create (ref point text height)
  (TXU:CreateWidth ref point text height 0.0))

(defun TXU:CreateWidth (ref point text height width / props code)
  (foreach code '(8 62 420 430 440)
    (if (assoc code ref) (setq props (cons (assoc code ref) props))))
  (if
    (entmake
      (append
        (list '(0 . "MTEXT") '(100 . "AcDbEntity"))
        props
        (list '(100 . "AcDbMText") (cons 10 point) (cons 40 height)
          (cons 41 width) '(71 . 1) '(72 . 1)
          (cons 7 (TXU:Get 7 ref "Standard")) '(210 0.0 0.0 1.0)
          (cons 11 (list (cos (TXU:Get 50 ref 0.0)) (sin (TXU:Get 50 ref 0.0)) 0.0))
          '(73 . 1) '(44 . 1.0))
        (TXU:Chunks text)))
    (entlast)
  )
)

(defun TXU:Locked (ent / data)
  (setq data (tblsearch "LAYER" (cdr (assoc 8 (entget ent)))))
  (/= 0 (logand 4 (TXU:Get 70 data 0)))
)

(defun c:TXT-JOIN (/ *error* ss ref collected records rows rowtol gap base left top
                   point defaultpoint text new action undo-open deleted r failed ent mode width infer)
  (defun *error* (msg)
    ;; Roll back only entities touched by this command, even on Escape.
    (foreach ent deleted (if (null (entget ent)) (entdel ent)))
    (if (and new (entget new)) (entdel new))
    (if undo-open (command-s "_.UNDO" "_End"))
    (if (and msg (not (wcmatch (strcase msg) "*CANCEL*,*QUIT*,*EXIT*,*BREAK*")))
      (princ (strcat "\n[TXT-JOIN] " msg)))
    (princ)
  )
  (princ "\n[TXT-JOIN] Seleccione una columna de TEXT: lineas, palabras o caracteres.")
  (princ "\nNo reconoce letras convertidas en geometria. MTEXT y otros objetos se omiten.")
  (setq ss (ssget "_I"))
  (if (null ss) (setq ss (ssget)))
  (cond
    ((null ss) (princ "\n[TXT-JOIN] Sin seleccion."))
    ((null (setq ref (TXU:Reference ss)))
      (princ "\n[TXT-JOIN] No hay TEXT compatibles; LINE/POLYLINE requieren OCR."))
    ((TXU:Locked (cdr (assoc -1 ref)))
      (princ "\n[TXT-JOIN] Desbloquee la capa del texto de referencia y repita."))
    (T
      (setq collected (TXU:Collect ss ref) records (car collected))
      (princ (strcat "\n[TXT-JOIN] " (itoa (length records)) " textos; "
        (itoa (cadr collected)) " objetos omitidos (tipo, plano u orientacion incompatible)."))
      (initget "Parrafos Lineas")
      (setq mode (getkword "\nReconstruccion [Parrafos/Lineas] <Parrafos>: "))
      (if (null mode) (setq mode "Parrafos"))
      (initget 6)
      (setq rowtol (getreal "\nTolerancia entre bases de una linea / altura <0.35>: "))
      (if (null rowtol) (setq rowtol 0.35))
      (initget 6)
      (setq gap (getreal "\nSeparacion minima entre palabras / altura <0.35>: "))
      (if (null gap) (setq gap 0.35))
      (setq rows (TXU:Rows records rowtol)
            base (cdr (assoc 40 ref))
            left (apply 'min (mapcar '(lambda (r) (nth 2 r)) records))
            top (apply 'max (mapcar '(lambda (r) (nth 6 r)) records))
            defaultpoint
              (TXU:Rotate (list left top (caddr (cdr (assoc 10 ref)))) (TXU:Get 50 ref 0.0))
            width 0.0)
      (if (= mode "Parrafos")
        (progn
          (initget "Si No")
          (setq infer (getkword "\nProponer subniveles numerados [Si/No] <Si>: "))
          (princ "\n[TXT-JOIN] Revise la jerarquia propuesta: se infiere de titulos, sangrias y continuidad.")
          (setq width (- (apply 'max (mapcar '(lambda (r) (nth 3 r)) records)) left))
          (initget 6)
          (setq action (getdist (strcat "\nAncho del MTEXT <" (rtos width 2 3) ">: ")))
          (if action (setq width action))
          (setq text (TXU:Structured rows gap base left (/= infer "No"))))
        (setq text (TXU:Build rows gap base left)))
      (princ (strcat "\n[TXT-JOIN] " (itoa (length rows))
        " lineas ordenadas. Se unifica la fuente, capa y color del texto de referencia."))
      (setq point (getpoint "\nUbicacion del MTEXT para revisar <ubicacion original>: "))
      (setq point (if point (trans point 1 0) defaultpoint))
      (command "_.UNDO" "_Begin")
      (setq undo-open T new (TXU:CreateWidth ref point text base width))
      (if new
        (progn
          (entupd new)
          (initget "Conservar Reemplazar Cancelar")
          (setq action (getkword "\nOriginales [Conservar/Reemplazar/Cancelar] <Conservar>: "))
          (cond
            ((= action "Cancelar") (entdel new) (setq new nil)
              (princ "\n[TXT-JOIN] Cancelado; originales conservados."))
            ((= action "Reemplazar")
              ;; Preflight every layer. A partial deletion is rolled back in full.
              (setq failed nil)
              (foreach r records (if (TXU:Locked (car r)) (setq failed T)))
              (if failed
                (princ "\n[TXT-JOIN] Hay capas bloqueadas. Se conservan TODOS los originales.")
                (progn
                  (foreach r records
                    (if (not failed)
                      (if (entdel (car r))
                        (setq deleted (cons (car r) deleted))
                        (setq failed T))))
                  (if failed
                    (progn
                      (foreach ent deleted (entdel ent))
                      (setq deleted nil)
                      (princ "\n[TXT-JOIN] Fallo al borrar. Se restauraron TODOS los originales."))
                    (princ "\n[TXT-JOIN] Textos originales reemplazados."))
                )
              ))
            (T (princ "\n[TXT-JOIN] MTEXT creado; originales conservados."))
          )
          (setq new nil deleted nil)
        )
        (princ "\n[TXT-JOIN] No se pudo crear el MTEXT; originales conservados.")
      )
      (command "_.UNDO" "_End")
      (setq undo-open nil)
    )
  )
  (princ)
)

(princ "\nTXT-JOIN cargado. Reconstruye TEXT fragmentados en un MTEXT.")
(princ)
