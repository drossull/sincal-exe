;;; RPUENTE -- Radio geometrico de una curva en planta.
;;; AutoCAD 2025/2027 y ZWCAD 2026 Windows; no requiere Express Tools.
;;; Marca opcional del centro con POINT y cruz, sin alterar la curva original.
;;; No calcula el radio de giro
;;; de una seccion (sqrt(I/A)), ni verifica el trazado o el diseno estructural.
;;; Resultado: alist RPUENTE-RESULTADO, radios en unidades reales del dibujo.
(vl-load-com)

(defun RP:Get (key data fallback / pair)
  (if (setq pair (assoc key data)) (cdr pair) fallback)
)

(defun RP:Failure (message) (list (cons 'error message)))

(defun RP:Result (radius center method)
  (list (cons 'radio radius) (cons 'centro center) (cons 'metodo method))
)

(defun RP:Three (a b c / ux uy vx vy scale uu vv det cx cy radius result)
  ;; Circuncentro con origen trasladado y escala normalizada, para coordenadas UTM.
  ;; Se calcula la proyeccion XY mundial; las cotas Z no intervienen.
  (setq ux (- (car b) (car a)) uy (- (cadr b) (cadr a))
        vx (- (car c) (car a)) vy (- (cadr c) (cadr a))
        scale (max (abs ux) (abs uy) (abs vx) (abs vy)))
  (cond
    ((<= scale 1.0e-12) (RP:Failure "Puntos coincidentes."))
    (T
      (setq ux (/ ux scale) uy (/ uy scale)
            vx (/ vx scale) vy (/ vy scale)
            uu (+ (* ux ux) (* uy uy)) vv (+ (* vx vx) (* vy vy))
            det (* 2.0 (- (* ux vy) (* uy vx))))
      (if (< (abs det) 1.0e-8)
        (RP:Failure "Puntos alineados o demasiado proximos a una recta; no hay radio fiable.")
        (progn
          (setq cx (/ (- (* uu vy) (* vv uy)) det)
                cy (/ (- (* ux vv) (* vx uu)) det)
                radius (* scale (sqrt (+ (* cx cx) (* cy cy))))
                result (RP:Result radius
                  (list (+ (car a) (* cx scale)) (+ (cadr a) (* cy scale)) 0.0)
                  "Estimacion por 3 puntos en planta"))
          (if (< (abs det) 0.001)
            (setq result (cons '(aviso . "Curva muy tendida: pequenas diferencias en los puntos cambian mucho el radio.") result)))
          result
        )
      )
    )
  )
)

(defun RP:Bulge (a b bulge / dx dy chord k)
  (setq dx (- (car b) (car a)) dy (- (cadr b) (cadr a))
        chord (sqrt (+ (* dx dx) (* dy dy))))
  (cond
    ((< (abs bulge) 1.0e-12)
      (RP:Failure "El tramo elegido es recto: no tiene radio circular finito. Use Trespuntos para estimar una curva segmentada."))
    ((< chord 1.0e-12) (RP:Failure "Tramo degenerado: vertices coincidentes."))
    (T
      (setq k (/ (- 1.0 (* bulge bulge)) (* 4.0 bulge)))
      (RP:Result
        (/ (* chord (+ 1.0 (* bulge bulge))) (* 4.0 (abs bulge)))
        (list (- (/ (+ (car a) (car b)) 2.0) (* dy k))
              (+ (/ (+ (cadr a) (cadr b)) 2.0) (* dx k))
              (if (caddr a) (caddr a) 0.0))
        "Radio exacto del tramo circular seleccionado")
    )
  )
)

(defun RP:Vertices (ent / d kind elev rev pair vertex p)
  (setq d (entget ent) kind (cdr (assoc 0 d)))
  (if (= kind "LWPOLYLINE")
    (progn
      (setq elev (RP:Get 38 d 0.0))
      (foreach pair d
        (cond
          ((= (car pair) 10)
            (setq p (cdr pair) rev (cons (list (list (car p) (cadr p) elev) 0.0) rev)))
          ((and (= (car pair) 42) rev)
            (setq rev (cons (list (caar rev) (cdr pair)) (cdr rev))))
        )
      )
    )
    (progn
      (setq elev (caddr (cdr (assoc 10 d))) vertex (entnext ent))
      (while (and vertex (/= (cdr (assoc 0 (entget vertex))) "SEQEND"))
        (setq p (cdr (assoc 10 (entget vertex))))
        (if (= "VERTEX" (cdr (assoc 0 (entget vertex))))
          (setq rev (cons
            (list (list (car p) (cadr p) elev) (RP:Get 42 (entget vertex) 0.0)) rev)))
        (setq vertex (entnext vertex))
      )
    )
  )
  (reverse rev)
)

(defun RP:Segment (vertices closed param / n lastindex nearest index a b)
  (setq n (length vertices) lastindex (if closed (1- n) (- n 2))
        nearest (fix (+ param 0.5)))
  (cond
    ((< n 2) (RP:Failure "Polilinea sin suficientes vertices."))
    ((and (< (abs (- param nearest)) 1.0e-6)
          (or closed (and (> nearest 0) (< nearest (1- n)))))
      (RP:Failure "Seleccion sobre un vertice: vuelva a seleccionar en medio del tramo curvo."))
    (T
      (setq index (max 0 (min lastindex (fix param)))
            a (nth index vertices)
            b (nth (rem (1+ index) n) vertices))
      (cons (cons 'tramo (1+ index)) (RP:Bulge (car a) (car b) (cadr a)))
    )
  )
)

(defun RP:Measure (ent pick / d kind normal result closest param flags)
  ;; PICK in WCS. Reject non-horizontal circles: their plan projection is elliptical.
  (setq d (entget ent) kind (cdr (assoc 0 d))
        normal (RP:Get 210 d '(0.0 0.0 1.0)) flags (RP:Get 70 d 0))
  (cond
    ((not (member kind '("ARC" "CIRCLE" "LWPOLYLINE" "POLYLINE")))
      (RP:Failure "Seleccione ARC, CIRCLE o polilinea 2D. Para spline, bloque o curva segmentada use Trespuntos (estimacion)."))
    ((or (> (abs (car normal)) 1.0e-8) (> (abs (cadr normal)) 1.0e-8))
      (RP:Failure "La entidad no esta en un plano horizontal. Use Trespuntos para estimar su proyeccion en planta."))
    ((and (= kind "POLYLINE") (/= 0 (logand flags (+ 2 4 8 16 64))))
      (RP:Failure "Polilinea 3D, malla o ajustada: use Trespuntos para una estimacion en planta."))
    ((member kind '("ARC" "CIRCLE"))
      (RP:Result (cdr (assoc 40 d)) (trans (cdr (assoc 10 d)) ent 0)
        "Radio exacto de la entidad circular"))
    (T
      (setq closest (vlax-curve-getClosestPointTo ent pick)
            param (if closest (vlax-curve-getParamAtPoint ent closest)))
      (if param
        (progn
          (setq result (RP:Segment (RP:Vertices ent) (/= 0 (logand flags 1)) param))
          (if (assoc 'centro result)
            (setq result (subst
              (cons 'centro (trans (cdr (assoc 'centro result)) ent 0))
              (assoc 'centro result) result)))
          result
        )
        (RP:Failure "No se pudo localizar el tramo; seleccione mas cerca de la curva.")
      )
    )
  )
)

(defun RP:Metres (radius units)
  (cond ((= units "Metros") radius)
        ((= units "Centimetros") (/ radius 100.0))
        ((= units "Milimetros") (/ radius 1000.0)))
)

(defun RP:MarkCenter (center radius / *error* layer data halfsize specs entities spec ent undo-open failed)
  (defun *error* (msg)
    (foreach ent entities (if (entget ent) (entdel ent)))
    (setq entities nil)
    (if undo-open (progn (setq undo-open nil) (command-s "_.UNDO" "_End")))
    (princ (strcat "\n[RPUENTE] No se completo la marca: " msg))
    (princ))
  (setq layer (getvar "CLAYER") data (tblsearch "LAYER" layer))
  (if (or (/= 0 (logand 5 (RP:Get 70 data 0))) (< (RP:Get 62 data 7) 0))
    (progn (princ "\n[RPUENTE] La capa actual esta bloqueada, apagada o congelada. No se creo la marca.") nil)
    (progn
      ;; POINT admite referencia NODO. La cruz es visible sin modificar PDMODE.
      ;; Todos los puntos DXF estan en WCS y en unidades de dibujo, no en metros.
      (setq halfsize (/ radius 200.0)
            specs (list
              (list '(0 . "POINT") (cons 10 center))
              (list '(0 . "LINE")
                (cons 10 (list (- (car center) halfsize) (cadr center) (caddr center)))
                (cons 11 (list (+ (car center) halfsize) (cadr center) (caddr center))))
              (list '(0 . "LINE")
                (cons 10 (list (car center) (- (cadr center) halfsize) (caddr center)))
                (cons 11 (list (car center) (+ (cadr center) halfsize) (caddr center))))))
      (command "_.UNDO" "_Begin")
      (setq undo-open T)
      (foreach spec specs
        (if (not failed)
          (if (entmake (append spec (list (cons 8 layer) '(62 . 1) '(6 . "Continuous"))))
            (setq entities (cons (entlast) entities))
            (setq failed T))))
      (if failed
        (progn
          (foreach ent entities (entdel ent))
          (setq entities nil)
          (princ "\n[RPUENTE] No se pudo crear la marca completa; se retiro la marca parcial.")))
      (command "_.UNDO" "_End")
      (setq undo-open nil)
      (reverse entities))))

(defun RP:Report (result / units radius metres center mark entities)
  (if (assoc 'error result)
    (princ (strcat "\n[RPUENTE] " (cdr (assoc 'error result))))
    (progn
      (setq radius (cdr (assoc 'radio result)) center (cdr (assoc 'centro result)))
      (princ (strcat "\n[RPUENTE] " (cdr (assoc 'metodo result))
        (if (assoc 'tramo result) (strcat " (tramo " (itoa (cdr (assoc 'tramo result))) ")") "")
        "\nR = " (rtos radius 2 6) " unidades de dibujo."))
      (initget "Metros Centimetros Milimetros Dibujo")
      (setq units (getkword "\nUnidades REALES del dibujo [Metros/Centimetros/Milimetros/Dibujo] <Dibujo>: "))
      (if (null units) (setq units "Dibujo"))
      (setq metres (RP:Metres radius units)
            RPUENTE-RESULTADO (append result (list (cons 'unidades units) (cons 'radio-metros metres))))
      (if metres (princ (strcat "\nR = " (rtos metres 2 6) " m.")))
      (princ (strcat "\nCentro XY (WCS, unidades de dibujo): "
        (rtos (car center) 2 6) ", " (rtos (cadr center) 2 6)))
      (if (assoc 'aviso result) (princ (strcat "\nAVISO: " (cdr (assoc 'aviso result)))))
      (princ "\nEl radio corresponde a la curva elegida, no necesariamente al eje del puente.")
      (princ (strcat "\nZ del centro: " (rtos (caddr center) 2 6)
        ". En Trespuntos el centro se proyecta a Z=0."))
      (initget "Si No")
      (setq mark (getkword "\nMarcar el centro calculado [Si/No] <Si>: "))
      (if (/= mark "No")
        (if (setq entities (RP:MarkCenter center radius))
          (progn
            (setq RPUENTE-RESULTADO (append RPUENTE-RESULTADO (list (cons 'marca entities))))
            (princ "\nCentro marcado con un PUNTO y una cruz roja en la capa actual.")
            (princ "\nUse ID con referencia NODO o INTERSECCION; las coordenadas mostradas arriba son WCS.")
            (princ "\nSi el centro queda fuera de pantalla, use ZOOM Extension para localizarlo."))))
      (princ "\nResultado guardado en RPUENTE-RESULTADO. La curva original se conserva.")
    )
  )
)

(defun c:RPUENTE (/ *error* selection a b c result)
  (defun *error* (msg)
    (setq RPUENTE-RESULTADO nil)
    (if (and msg (not (wcmatch (strcase msg) "*CANCEL*,*QUIT*,*EXIT*,*BREAK*")))
      (princ (strcat "\n[RPUENTE] " msg)))
    (princ)
  )
  (setq RPUENTE-RESULTADO nil)
  (princ "\n[RPUENTE] Radio de curvatura en planta; seleccione en espacio modelo o dentro del viewport.")
  (initget "Trespuntos")
  (setq selection (entsel "\nSeleccione curva cerca del tramo a medir [Trespuntos]: "))
  (cond
    ((= (type selection) 'STR)
      (princ "\nEstimacion circular: elija inicio, punto intermedio y final sobre LA MISMA curva.")
      (princ "\nUse referencias a objetos. Una spline o curva compuesta puede tener radio variable.")
      (if (and
            (setq a (getpoint "\nPrimer punto: "))
            (setq b (getpoint a "\nPunto intermedio: "))
            (setq c (getpoint b "\nUltimo punto: ")))
        (RP:Report (RP:Three (trans a 1 0) (trans b 1 0) (trans c 1 0)))
        (princ "\n[RPUENTE] Cancelado."))
    )
    (selection
      (setq result (vl-catch-all-apply 'RP:Measure
        (list (car selection) (trans (cadr selection) 1 0))))
      (if (vl-catch-all-error-p result)
        (princ (strcat "\n[RPUENTE] No se pudo leer la entidad: " (vl-catch-all-error-message result)))
        (RP:Report result))
    )
    (T (princ "\n[RPUENTE] Sin seleccion."))
  )
  (princ)
)

(princ "\nRPUENTE cargado. Seleccione una curva o use Trespuntos para estimar su radio.")
(princ)
