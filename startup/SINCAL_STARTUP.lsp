;;; =========================================================================
;;; SINCAL_STARTUP.lsp
;;; Archivo maestro de inicialización SINCAL
;;; (Variables, Propiedades, Escalas y Atajos de Color)
;;; =========================================================================
(vl-load-com)

;;; =========================================================================
;;; 1. ESCUDO SINCAL (VARIABLES DE ENTORNO)
;;; =========================================================================
(if (/= (getvar "MIRRTEXT") 0) (setvar "MIRRTEXT" 0))
(if (/= (getvar "FIELDEVAL") 31) (setvar "FIELDEVAL" 31))
(setvar "DYNMODE" 3)
(princ "\n[SINCAL] Variables blindadas (MIRRTEXT, FIELDEVAL, DYNMODE).")

;;; =========================================================================
;;; 2. INYECCIÓN DE PROPIEDADES CUSTOM (Filtro Anti-Bug ZWCAD)
;;; =========================================================================
(defun SINCAL:AutoCrearPropiedad (/ acadObj doc props listaProps propName propVal num i k v exists)
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vlax-get-property acadObj 'ActiveDocument))
  (setq props (vlax-get-property doc 'SummaryInfo))

  (setq listaProps
    '(
      ("Nombre_Estructura" . "Ingrese nombre estructura")
      ("Region"            . "Ingrese region")
      ("Provincia"         . "Ingrese provincia")
      ("Comuna"            . "Ingrese comuna")
      ("Sector"            . "Ingrese sector")
      ("Tramo"             . "Ingrese tramo")
      ("Revision"          . "REV")
      ("Comentario-rev"    . "Ingrese comentario revision")
      ("Dibujante"         . "DIBUJANTE")
      ("Fecha_Rev"         . "F_REV")
      ("Fecha_Inf"         . "F_INF")
      ("No_total_planos"   . "Ingrese numero total de planos")
      ("Nombre_Plano"      . "Ingrese nombre plano")
     )
  )

  (foreach prop listaProps
    (setq propName (car prop))
    (setq propVal (cdr prop))
    (setq exists nil)
    (setq num (vla-NumCustomInfo props))
    (setq i 0)
    
    (while (< i num)
      (vla-GetCustomByIndex props i 'k 'v)
      (if (= (strcase k) (strcase propName)) (setq exists T))
      (setq i (1+ i))
    )

    (if (not exists)
      (vl-catch-all-apply 'vla-AddCustomInfo (list props propName propVal))
    )
  )
  (princ "\n[SINCAL] Diccionario de propiedades verificado.")
)

;;; =========================================================================
;;; 3. INYECCIÓN DE ESCALAS EN METROS (Anti-duplicación)
;;; =========================================================================
(defun SINCAL:GenerarEscalas (/ SINCAL:CrearEscala listaEscalas origCmdEcho)
  ;; Apagamos el eco para que la consola no se llene de texto
  (setq origCmdEcho (getvar "CMDECHO"))
  (setvar "CMDECHO" 0)

  (defun SINCAL:CrearEscala (nombre proporcion)
    (vl-catch-all-apply 'vl-cmdf (list "_.-SCALELISTEDIT" "_Delete" nombre "_Exit"))
    (vl-cmdf "_.-SCALELISTEDIT" "_Add" nombre proporcion "_Exit")
  )

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
  
  (foreach esc listaEscalas
    (SINCAL:CrearEscala (car esc) (cdr esc))
  )
  
  (setvar "CMDECHO" origCmdEcho)
  (princ "\n[SINCAL] Escalas oficiales (m) calibradas.")
)

;;; =========================================================================
;;; 4. HERRAMIENTAS DE COLOR ACTIVEX (C0 - C9)
;;; =========================================================================
(defun CambiarColor (col / ss i ent obj)
  (setq ss (ssget "_I"))
  (if (not ss) (setq ss (ssget)))
  (if ss
    (progn
      (setq i 0)
      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (setq obj (vlax-ename->vla-object ent))
        (vl-catch-all-apply 'vla-put-Color (list obj col))
        (setq i (1+ i))
      )
    )
  )
  (princ)
)

(defun c:c1 () (CambiarColor 1))
(defun c:c2 () (CambiarColor 2))
(defun c:c3 () (CambiarColor 3))
(defun c:c4 () (CambiarColor 4))
(defun c:c5 () (CambiarColor 5))
(defun c:c6 () (CambiarColor 6))
(defun c:c7 () (CambiarColor 7))
(defun c:c8 () (CambiarColor 8))
(defun c:c9 () (CambiarColor 9))
(defun c:c0 () (CambiarColor 256))

;;; =========================================================================
;;; EJECUCIÓN AUTOMÁTICA AL ABRIR EL PLANO
;;; =========================================================================
(SINCAL:AutoCrearPropiedad)
(SINCAL:GenerarEscalas)
(princ "\n--- SINCAL STARTUP CARGADO EXITOSAMENTE ---")
(princ)