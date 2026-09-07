;;; ============================================================================
;;; SEL-SC.LSP
;;; Comando: SEL-SC
;;;
;;; Conserva una única escala anotativa en los objetos seleccionados.
;;; Compatible con AutoCAD 2025/2027 y ZWCAD 2026 (Windows).
;;;
;;; El comando usa -OBJECTSCALE para modificar los objetos: no edita
;;; directamente los diccionarios internos de datos anotativos.
;;; ============================================================================

(vl-load-com)

;; Devuelve las escalas anotativas asignadas a una entidad, o nil si no tiene.
;; Las escalas se obtienen del diccionario de contexto del propio objeto.
(defun DEA:EscalasDeObjeto (ent / datos dic-externo dic-contexto dic-escalas item escala resultado primero)
  (if
    (and
      (setq datos       (entget ent))
      (setq dic-externo (cdr (assoc 360 datos)))
      (setq dic-contexto
        (dictsearch dic-externo "AcDbContextDataManager")
      )
      (setq dic-escalas
        (dictsearch (cdr (assoc -1 dic-contexto)) "ACDB_ANNOTATIONSCALES")
      )
    )
    (progn
      (setq dic-escalas (cdr (assoc -1 dic-escalas))
            primero     T
      )
      (while (setq item (dictnext dic-escalas primero))
        (setq primero NIL)
        (if
          (and
            (assoc 340 item)
            (setq escala (assoc 300 (entget (cdr (assoc 340 item)))))
          )
          (setq resultado (cons (cdr escala) resultado))
        )
      )
      (reverse resultado)
    )
  )
)

;; Elimina duplicados sin modificar el orden de la lista recibida.
(defun DEA:Unicos (lista / resultado)
  (foreach elemento lista
    (if (not (member elemento resultado))
      (setq resultado (cons elemento resultado))
    )
  )
  (reverse resultado)
)

;; Construye un conjunto con los objetos que originalmente tenían una escala.
(defun DEA:ObjetosConEscala (registros escala / conjunto registro)
  (setq conjunto (ssadd))
  (foreach registro registros
    (if (member escala (cdr registro))
      (ssadd (car registro) conjunto)
    )
  )
  conjunto
)

;; Ejecuta el comando nativo de manera silenciosa y devuelve T si no falló.
(defun DEA:AplicarObjectScale (conjunto opcion escala / intento)
  (setq intento
    (vl-catch-all-apply
      'vl-cmdf
      (list "_.-OBJECTSCALE" conjunto "" opcion escala "")
    )
  )
  (not (vl-catch-all-error-p intento))
)

;; Solicita una opción válida de la lista mostrada al usuario.
(defun DEA:ElegirEscala (escalas / indice opcion cancelado)
  (princ "\nEscalas detectadas en los objetos anotativos seleccionados:")
  (setq indice 1)
  (foreach escala escalas
    (princ (strcat "\n  " (itoa indice) ". " escala))
    (setq indice (1+ indice))
  )
  (while
    (and
      (not cancelado)
      (or
        (null opcion)
        (< opcion 1)
        (> opcion (length escalas))
      )
    )
    (setq opcion
      (getint
        (strcat
          "\nNúmero de la escala que se conservará [1-"
          (itoa (length escalas))
          "] <Cancelar>: "
        )
      )
    )
    (if (null opcion)
      (progn
        (setq cancelado T)
      )
    )
  )
  (if cancelado
    (princ "\nOperación cancelada.")
    (nth (1- opcion) escalas)
  )
)

(defun c:SEL-SC (/ *error* seleccion indice entidad escalas registros todas escala-conservar escala objetos cambios omitidos)
  (defun *error* (mensaje)
    (if (= 8 (logand 8 (getvar "UNDOCTL")))
      (vl-cmdf "_.UNDO" "_End")
    )
    (if (and mensaje (not (wcmatch (strcase mensaje) "*CANCEL*,*EXIT*,*BREAK*")))
      (princ (strcat "\nError: " mensaje))
    )
    (princ)
  )

  ;; Aprovecha la preselección; si no existe, pide una selección normal.
  (setq seleccion (ssget "_I"))
  (if (null seleccion)
    (setq seleccion (ssget "\nSeleccione objetos anotativos: "))
  )

  (cond
    ((null seleccion)
      (princ "\nNo se seleccionaron objetos.")
    )
    (T
      ;; Se registran sólo los objetos que tienen al menos una escala anotativa.
      (setq indice 0
            registros NIL
            todas    NIL
            omitidos 0
      )
      (repeat (sslength seleccion)
        (setq entidad (ssname seleccion indice)
              escalas (DEA:EscalasDeObjeto entidad)
              indice  (1+ indice)
        )
        (if escalas
          (progn
            (setq registros (cons (cons entidad escalas) registros))
            (setq todas (append escalas todas))
          )
          (setq omitidos (1+ omitidos))
        )
      )
      (setq registros (reverse registros)
            todas    (vl-sort (DEA:Unicos todas) '(lambda (a b) (< (strcase a) (strcase b))))
      )
      (cond
        ((null registros)
          (princ "\nNingún objeto seleccionado contiene escalas anotativas modificables.")
        )
        (T
          (setq escala-conservar (DEA:ElegirEscala todas))
          (if escala-conservar
            (progn
              ;; Se agrega primero la escala elegida a todos los objetos válidos.
              ;; Así ningún objeto queda sin una representación anotativa.
              (vl-cmdf "_.UNDO" "_Begin")
              (setq objetos (ssadd))
              (foreach registro registros (ssadd (car registro) objetos))
              (setq cambios 0)
              (if (DEA:AplicarObjectScale objetos "_Add" escala-conservar)
                (setq cambios (1+ cambios))
              )

              ;; Cada escala sobrante se borra sólo en los objetos que la tenían.
              (foreach escala todas
                (if (/= escala escala-conservar)
                  (if
                    (DEA:AplicarObjectScale
                      (DEA:ObjetosConEscala registros escala)
                      "_Delete"
                      escala
                    )
                    (setq cambios (1+ cambios))
                  )
                )
              )
              (vl-cmdf "_.UNDO" "_End")
              (if (> cambios 0)
                (princ
                  (strcat
                    "\nListo: se conservó la escala \""
                    escala-conservar
                    "\" en "
                    (itoa (length registros))
                    " objeto(s) anotativo(s)."
                  )
                )
                (princ "\nNo fue posible aplicar los cambios mediante -OBJECTSCALE.")
              )
              (if (> omitidos 0)
                (princ (strcat " Se omitieron " (itoa omitidos) " objeto(s) no anotativos."))
              )
            )
          )
        )
      )
    )
  )
  (princ)
)

(princ "\nSEL-SC cargado. Escriba SEL-SC para usarlo.")
(princ)
