;;; VRAP - Dos esquinas en Model, una esquina de colocacion en Layout.
;;; Conserva el encuadre y la escala anotativa real (tambien escalas en metros).
;;; AutoCAD / ZWCAD para Windows.
(vl-load-com)

(defun VRAP:Frame (a b / da db center)
  ;; DCS mide el rectangulo tal como se ve, incluso con UCS/vista girados.
  (setq da (trans a 1 2)
        db (trans b 1 2)
        center (list (/ (+ (car da) (car db)) 2.0)
                     (/ (+ (cadr da) (cadr db)) 2.0) 0.0))
  (list (abs (- (car db) (car da)))
        (abs (- (cadr db) (cadr da)))
        (trans center 2 0)
        (trans (getvar "VIEWDIR") 1 0 T)
        (getvar "VIEWTWIST")))

(defun VRAP:Activate (doc vp)
  (vla-put-MSpace doc :vlax-true)
  (vla-put-ActivePViewport doc vp))

(defun VRAP:ZoomCenter (center height)
  ;; ZWCAD puede no exponer ZoomCenter por ActiveX. Su comando nativo sirve
  ;; como alternativa; command-s permite usarlo tambien al restaurar por error.
  (if (vl-catch-all-error-p
        (vl-catch-all-apply 'vla-ZoomCenter
          (list (vlax-get-acad-object) (vlax-3d-point center) height)))
    (command-s "_.ZOOM" "_Center" "_non" (trans center 0 1) height)))

(defun VRAP:Configure (doc vp frame scaleName scaleValue)
  (vla-put-Direction vp (vlax-3d-point (nth 3 frame)))
  (vla-put-Target vp (vlax-3d-point (nth 2 frame)))
  (vla-put-TwistAngle vp (nth 4 frame))
  (vla-Display vp :vlax-true)
  ;; AutoCAD no activa viewports demasiado pequenos en pantalla. Acercar el
  ;; papel temporalmente permite configurar incluso esos casos, sin agrandarlos.
  (if (vl-catch-all-error-p (vl-catch-all-apply 'VRAP:Activate (list doc vp)))
    (progn
      (vla-put-MSpace doc :vlax-false)
      (VRAP:ZoomCenter (vlax-get vp 'Center) (* 1.5 (vla-get-Height vp)))
      (VRAP:Activate doc vp)))
  ;; Cambiar CANNOSCALE con ANNOAUTOSCALE=0 no agrega escalas a los objetos.
  (setvar "ANNOAUTOSCALE" 0)
  (setvar "CANNOSCALE" scaleName)
  (VRAP:ZoomCenter (nth 2 frame) (cadr frame))
  (vla-put-MSpace doc :vlax-false)
  (vla-put-StandardScale vp 0) ; acVpCustomScale
  (vla-put-CustomScale vp scaleValue)
  (vla-put-DisplayLocked vp :vlax-true)
  (vla-Update vp))

(defun c:VRAP (/ *error* doc oldEcho oldAnno oldTile oldTab oldViewport
                undoOpen vp destination a b frame scaleName scaleValue
                anchor width height center paperView)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object))
        oldEcho (getvar "CMDECHO")
        oldAnno (getvar "ANNOAUTOSCALE")
        oldTile (getvar "TILEMODE")
        oldTab (getvar "CTAB"))
  (if (and (= oldTile 0) (> (getvar "CVPORT") 1))
    (setq oldViewport (vla-get-ActivePViewport doc)))

  (defun *error* (msg)
    (if (= (getvar "TILEMODE") 0)
      (progn
        (vl-catch-all-apply 'vla-put-MSpace (list doc :vlax-false))
        (if paperView
          (vl-catch-all-apply 'VRAP:ZoomCenter paperView))))
    (if vp (vl-catch-all-apply 'vla-Delete (list vp)))
    (vl-catch-all-apply 'setvar (list "ANNOAUTOSCALE" oldAnno))
    (vl-catch-all-apply 'setvar (list "TILEMODE" oldTile))
    (if (= oldTile 0)
      (progn
        (vl-catch-all-apply 'setvar (list "CTAB" oldTab))
        (if oldViewport
          (progn
            (vl-catch-all-apply 'vla-put-MSpace (list doc :vlax-true))
            (vl-catch-all-apply 'vla-put-ActivePViewport (list doc oldViewport))))))
    (if undoOpen (vla-EndUndoMark doc))
    (setvar "CMDECHO" oldEcho)
    (if (and msg (not (wcmatch (strcase msg) "*CANCEL*,*QUIT*,*EXIT*,*BREAK*")))
      (princ (strcat "\nVRAP: " msg))
      (princ "\nVRAP cancelado. No se creo el viewport."))
    (princ))

  (setvar "CMDECHO" 0)
  ;; PaperSpace pertenece al ultimo layout usado, aun estando en Model.
  (setq destination (vla-get-Name (vla-get-Layout (vla-get-PaperSpace doc))))
  (vla-StartUndoMark doc)
  (setq undoOpen T)
  (if (= oldTile 0) (setvar "TILEMODE" 1))
  (if (= (getvar "PERSPECTIVE") 1)
    (progn
      (princ "\nVRAP requiere una vista paralela; desactive la perspectiva antes de usarlo.")
      (exit)))
  ;; Leer el factor, nunca deducirlo del nombre: 1:100 (m) puede valer 10.
  (setq scaleName (getvar "CANNOSCALE")
        scaleValue (getvar "CANNOSCALEVALUE"))
  (if (or (not (numberp scaleValue)) (<= scaleValue 0.0))
    (progn (princ "\nLa escala anotativa actual no es valida.") (exit)))
  (princ (strcat "\nVRAP: escala " scaleName "; destino " destination "."))
  (if (not (setq a (getpoint "\nPrimera esquina del area en Model: "))) (exit))
  (if (not (setq b (getcorner a "\nEsquina opuesta: "))) (exit))
  (setq frame (VRAP:Frame a b))
  (if (or (< (car frame) 1e-8) (< (cadr frame) 1e-8))
    (progn (princ "\nEl area debe tener ancho y alto mayores que cero.") (exit)))

  (setvar "TILEMODE" 0)
  (setvar "CTAB" destination)
  (vla-put-MSpace doc :vlax-false)
  (if (not (setq anchor (getpoint "\nEsquina inferior izquierda del viewport en el layout: ")))
    (exit))
  (setq anchor (trans anchor 1 0)
        paperView (list (trans (getvar "VIEWCTR") 1 0) (getvar "VIEWSIZE"))
        width (* (car frame) scaleValue)
        height (* (cadr frame) scaleValue)
        center (list (+ (car anchor) (/ width 2.0))
                     (+ (cadr anchor) (/ height 2.0)) 0.0))
  (setq vp (vla-AddPViewport (vla-get-PaperSpace doc)
                           (vlax-3d-point center) width height))
  (VRAP:Configure doc vp frame scaleName scaleValue)
  (VRAP:ZoomCenter (car paperView) (cadr paperView))
  (setvar "ANNOAUTOSCALE" oldAnno)
  (vla-EndUndoMark doc)
  (setq undoOpen nil vp nil)
  (setvar "CMDECHO" oldEcho)
  (princ (strcat "\nViewport creado en " destination " a escala " scaleName
                 " y bloqueado. Enter repite VRAP para otra area."))
  (princ))

(princ "\nVRAP cargado. Dos esquinas en Model y un punto en Layout, a la escala anotativa actual.")
(princ)
