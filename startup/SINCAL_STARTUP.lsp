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
;;; 2. INYECCIÓN Y ORDENAMIENTO DE PROPIEDADES CUSTOM (Macro a Micro)
;;; =========================================================================
(defun SINCAL:AutoCrearPropiedad (/ acadObj doc props listaProps num i k v existingProps propName propDefault existingData valToAdd)
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vlax-get-property acadObj 'ActiveDocument))
  (setq props (vlax-get-property doc 'SummaryInfo))

  ;; A. ORDEN JERÁRQUICO MAESTRO (Macro a Micro)
  (setq listaProps
    '(
      ("Region"                  . "Ingrese region")
      ("Provincia"               . "Ingrese provincia")
      ("Comuna"                  . "Ingrese comuna")
      ("Sector"                  . "Ingrese sector")
      ("Tramo"                   . "Ingrese tramo")
      ("Nombre_Estructura"       . "Ingrese nombre estructura")
      ("DM_Inicio"               . "Ingrese DM inicio")
      ("DM_Fin"                  . "Ingrese DM fin")
      ("Coordenada_Este_Inicio"  . "Ingrese Este inicio")
      ("Coordenada_Norte_Inicio" . "Ingrese Norte inicio")
      ("Coordenada_Este_Fin"     . "Ingrese Este fin")
      ("Coordenada_Norte_Fin"    . "Ingrese Norte fin")
      ("Dibujante"               . "DIBUJANTE")
      ("Fecha_Inf"               . "F_INF")
      ("Fecha_Rev"               . "F_REV")
      ("Revision"                . "REV")
      ("Comentario-rev"          . "Ingrese comentario revision")
      ("No_total_planos"         . "Ingrese numero total de planos")
      ("Nombre_Plano"            . "Ingrese nombre plano")
     )
  )

  ;; B. RESPALDAR DATOS EXISTENTES EN RAM
  (setq existingProps nil)
  (setq num (vla-NumCustomInfo props))
  (setq i 0)
  (while (< i num)
    (vla-GetCustomByIndex props i 'k 'v)
    ;; Guardamos como: ("CLAVE_MAYUSCULA" "ClaveOriginal" . "Valor")
    (if (not (assoc (strcase k) existingProps))
      (setq existingProps (append existingProps (list (cons (strcase k) (cons k v)))))
    )
    (setq i (1+ i))
  )

  ;; C. LIMPIAR EL LIENZO (Evita duplicados y desorden)
  (while (> (vla-NumCustomInfo props) 0)
    (vl-catch-all-apply 'vla-RemoveCustomByIndex (list props 0))
  )

  ;; D. INYECTAR PROPIEDADES EN EL ORDEN MAESTRO
  (foreach prop listaProps
    (setq propName (car prop))
    (setq propDefault (cdr prop))
    
    ;; Buscar si el archivo ya tenía esta propiedad (Sin importar mayúsculas)
    (setq existingData (assoc (strcase propName) existingProps))
    
    (if existingData
      (progn
        (setq valToAdd (cddr existingData)) ;; Rescatar valor antiguo
        ;; Eliminar de la lista de respaldo para que no se duplique luego
        (setq existingProps (vl-remove existingData existingProps))
      )
      ;; Si es nueva, poner valor por defecto
      (setq valToAdd propDefault)
    )
    
    (vl-catch-all-apply 'vla-AddCustomInfo (list props propName valToAdd))
  )

  ;; E. REINYECTAR PROPIEDADES HUÉRFANAS (Otras que el usuario haya creado a mano)
  (foreach remaining existingProps
    (vl-catch-all-apply 'vla-AddCustomInfo (list props (cadr remaining) (cddr remaining)))
  )

  (princ "\n[SINCAL] Diccionario de propiedades jerarquizado y verificado.")
)

;;; =========================================================================
;;; 3. INYECCIÓN DE ESCALAS EN METROS (Anti-Bug "Is Referenced")
;;; =========================================================================
(defun SINCAL:GenerarEscalas (/ SINCAL:ExisteEscala SINCAL:CrearEscala listaEscalas origCmdEcho)
  (setq origCmdEcho (getvar "CMDECHO"))
  (setvar "CMDECHO" 0)

  (defun SINCAL:ExisteEscala (nombre / dict exists entdata)
    (setq exists nil)
    (if (setq dict (dictsearch (namedobjdict) "ACAD_SCALELIST"))
      (foreach item dict
        (if (and (= (car item) 350) (not exists))
          (progn
            (setq entdata (entget (cdr item)))
            (if (= (strcase (cdr (assoc 300 entdata))) (strcase nombre))
              (setq exists T)
            )
          )
        )
      )
    )
    exists
  )

  (defun SINCAL:CrearEscala (nombre proporcion)
    (if (SINCAL:ExisteEscala nombre)
      (vl-catch-all-apply 'vl-cmdf (list "_.-SCALELISTEDIT" "_Add" nombre "_Y" proporcion "_Exit"))
      (vl-catch-all-apply 'vl-cmdf (list "_.-SCALELISTEDIT" "_Add" nombre proporcion "_Exit"))
    )
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
  
  (command) 
  (command)

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