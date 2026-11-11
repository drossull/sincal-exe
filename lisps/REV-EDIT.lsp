;;; REV-EDIT / PROPS-EDIT -- editor nativo de revisiones y propiedades.
;;; La DLL se instala con SINCAL; actualizar solo LISPs no instala el editor.
(vl-load-com)

(defun SRG:BinaryName (/ app fso version result)
  (if (wcmatch (strcase (getvar "PROGRAM")) "*ZW*")
    (progn
      (setq app (vlax-get-acad-object)
            fso (vlax-create-object "Scripting.FileSystemObject")
            version (vl-catch-all-apply 'vlax-invoke-method
              (list fso 'GetFileVersion (strcat (vla-get-Path app) "/zwcad.exe"))))
      (vlax-release-object fso)
      (if (and (not (vl-catch-all-error-p version)) (> (atoi version) 0))
        (strcat "Sincal.RevisionGrip.ZWCAD." (itoa (+ 2000 (atoi version))) ".dll")))
    (strcat "Sincal.RevisionGrip.AutoCAD.R" (substr (getvar "ACADVER") 1 4) ".dll")))

(defun SRG:Load (report / name path result)
  (cond
    ((getcname "SINCAL_REV_EDIT") T)
    ((and (setq name (SRG:BinaryName))
          (setq path (findfile (strcat (getenv "APPDATA") "/Estandar SINCAL/" name))))
      (setq result (vl-catch-all-apply 'vl-cmdf (list "_.NETLOAD" path)))
      (if (and (not (vl-catch-all-error-p result)) (getcname "SINCAL_REV_EDIT"))
        T
        (progn
          (if report (princ "\nREV-EDIT: no se pudo cargar el complemento. Revisa la version CAD y el mensaje de NETLOAD."))
          nil)))
    (T (if report (princ "\nREV-EDIT: falta el complemento para esta version CAD. Instala la version de SINCAL que incluye el editor y ejecuta Preparar integracion CAD.")) nil)))

(defun c:REV-EDIT ()
  (if (SRG:Load T) (vl-cmdf "SINCAL_REV_EDIT"))
  (princ))

(defun c:PROPS-EDIT ()
  (if (SRG:Load T)
    (if (getcname "SINCAL_PROPS_EDIT")
      (vl-cmdf "SINCAL_PROPS_EDIT")
      (princ "\nPROPS-EDIT: actualiza el complemento de SINCAL, prepara la integracion CAD y reinicia CAD para cargar la pestana de propiedades.")))
  (princ))

;; La carga registra el pinzamiento una vez por proceso, sin recorrer dibujos.
;; Core Console no usa interfaz ni pinzamientos.
(if (= (getvar "PROGRAM") "acad") (vl-catch-all-apply 'SRG:Load (list nil)))
(if (wcmatch (strcase (getvar "PROGRAM")) "*ZW*") (vl-catch-all-apply 'SRG:Load (list nil)))
(princ)
