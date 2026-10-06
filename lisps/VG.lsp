;;; VG: elimina referencias VIÑETA G130 en Modelo y layouts, luego PURGEALL.
;;; No modifica definiciones de otros bloques ni referencias externas.
(vl-load-com)

(defun VG:TargetP (obj / name)
  (and (= "AcDbBlockReference" (vla-get-ObjectName obj))
    (setq name (if (vlax-property-available-p obj 'EffectiveName)
                 (vla-get-EffectiveName obj) (vla-get-Name obj)))
    (= (strcase name) (strcat "VI" (chr 209) "ETA G130"))))

(defun VG:Remove (doc / layout obj targets count skipped result definition)
  (setq count 0 skipped 0)
  ;; Collect before deleting: mutating a COM collection during enumeration
  ;; can skip consecutive references.
  (vlax-for layout (vla-get-Layouts doc)
    (vlax-for obj (vla-get-Block layout)
      (if (VG:TargetP obj)
        (progn
          (setq definition (vla-Item (vla-get-Blocks doc) (vla-get-Name obj)))
          (if (= :vlax-false (vla-get-IsXRef definition))
            (setq targets (cons obj targets)))))))
  (foreach obj targets
    (if (= :vlax-true (vla-get-Lock (vla-Item (vla-get-Layers doc) (vla-get-Layer obj))))
      (setq skipped (1+ skipped))
      (progn
        (setq result (vl-catch-all-apply 'vla-Delete (list obj)))
        (if (vl-catch-all-error-p result)
          (setq skipped (1+ skipped))
          (setq count (1+ count))))))
  (list count skipped))

(defun VG:LoadPurge (/ path candidate)
  (if (not (member "C:PURGEALL" (atoms-family 1)))
    (progn
      (foreach candidate
        (list "PURGEALL.lsp" "lisps/PURGEALL.lsp"
          (strcat (getenv "APPDATA") "/Estandar SINCAL/lisps/PURGEALL.lsp"))
        (if (and (null path) (findfile candidate)) (setq path (findfile candidate))))
      (if path (load path))))
  (member "C:PURGEALL" (atoms-family 1)))

(defun c:VG (/ *error* doc opened result)
  (defun *error* (msg)
    (if opened (vl-catch-all-apply 'vla-EndUndoMark (list doc)))
    (if msg (princ (strcat "\n[VG] " msg ". Puede deshacer con UNDO.")))
    (princ))
  ;; Resolve dependency before any destructive action.
  (if (not (VG:LoadPurge))
    (princ "\n[VG] Falta PURGEALL.lsp. Actualice recursos SINCAL. No se elimino nada.")
    (progn
      (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
      (vla-StartUndoMark doc)
      (setq opened T result (VG:Remove doc))
      (princ (strcat "\n[VG] Eliminadas: " (itoa (car result))
        ". Omitidas por bloqueo/error: " (itoa (cadr result)) "."))
      (c:PURGEALL)
      (vla-EndUndoMark doc)
      (setq opened nil)
      (princ "\n[VG] Operacion terminada. El dibujo no se ha guardado automaticamente.")))
  (princ))

(princ "\nVG cargado: eliminar VIÑETA G130 y purgar el dibujo actual.")
(princ)
