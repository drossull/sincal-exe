;;; ==========================================================================
;;; VPTOGGLE - Alternar visibilidad de la capa de marcos de viewport
;;; Compatible con AutoCAD y ZWCAD mediante Visual LISP / ActiveX.
;;; ==========================================================================

(defun c:VPTOGGLE (/ acadObj doc layers layerObj layerName result)
  (vl-load-com)
  (setq layerName "Viewport layer")

  (if (not (tblsearch "LAYER" layerName))
    (princ (strcat "\n[SINCAL] No existe la capa \"" layerName "\"; no se hicieron cambios."))
    (progn
      (setq acadObj (vlax-get-acad-object))
      (setq doc (vla-get-ActiveDocument acadObj))
      (setq layers (vla-get-Layers doc))
      (setq layerObj (vla-Item layers layerName))

      (if (= (vla-get-LayerOn layerObj) :vlax-false)
        (progn
          (setq result
            (vl-catch-all-apply 'vla-put-LayerOn (list layerObj :vlax-true)))
          (if (vl-catch-all-error-p result)
            (princ "\n[SINCAL] No fue posible encender la capa \"Viewport layer\".")
            (princ "\n[SINCAL] Capa \"Viewport layer\" visible.")
          )
        )
        (progn
          ;; Una capa actual no debe apagarse: se cambia primero a la capa 0.
          (if (= (strcase (getvar "CLAYER")) (strcase layerName))
            (setvar "CLAYER" "0")
          )
          (setq result
            (vl-catch-all-apply 'vla-put-LayerOn (list layerObj :vlax-false)))
          (if (vl-catch-all-error-p result)
            (princ "\n[SINCAL] No fue posible apagar la capa \"Viewport layer\".")
            (princ "\n[SINCAL] Capa \"Viewport layer\" oculta.")
          )
        )
      )

      (if (not (vl-catch-all-error-p result))
        (vl-catch-all-apply 'vla-Regen (list doc 1))
      )
    )
  )
  (princ)
)

(princ "\nComando VPTOGGLE cargado. Alterna la capa \"Viewport layer\".")
(princ)
