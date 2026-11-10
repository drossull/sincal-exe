(defun c:ZE ()
  (command "_.ZOOM" "_Extents")
  (princ)
)

;; ZE sigue siendo autonomo para los lotes existentes de SINCAL.
;; El recorrido se ejecuta fuera del contexto LISP: activar otro documento
;; desde AutoLISP suspende la rutina en AutoCAD/ZWCAD.
(defun c:ZET (/ worker root log prog exe)
  (vl-load-com)
  (setq worker (findfile "scripts/ZE-TODOS.ps1"))
  (foreach root (list
      (if (getenv "LOCALAPPDATA") (strcat (getenv "LOCALAPPDATA") "/SINCAL/resources"))
      (if (getenv "ProgramFiles") (strcat (getenv "ProgramFiles") "/SINCAL"))
      (if (getenv "APPDATA") (strcat (getenv "APPDATA") "/Estandar SINCAL")))
    (if (and root (not worker))
      (setq worker (findfile (strcat root "/scripts/ZE-TODOS.ps1")))))
  (if worker
    (progn
      (setq log (vl-filename-mktemp "SINCAL-ZET-" nil ".log")
            prog (if (wcmatch (strcase (getvar "PROGRAM")) "*ZW*")
                   "ZWCAD.Application.2026"
                   (strcat "AutoCAD.Application."
                     (if (= (substr (getvar "ACADVER") 4 1) "0")
                       (substr (getvar "ACADVER") 1 2)
                       (substr (getvar "ACADVER") 1 4))))
            exe (strcat (getenv "WINDIR") "/System32/WindowsPowerShell/v1.0/powershell.exe"))
      (if (startapp exe (strcat
          "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File \""
          worker "\" -ProgId \"" prog "\" -WindowHandle "
          (itoa (vla-get-HWND (vlax-get-acad-object))) " -LogPath \"" log "\""))
        (princ (strcat "\nZET: encuadrando los dibujos abiertos. Registro: " log))
        (princ "\nZET: no se pudo iniciar el recorrido.")))
    (princ "\nZET: falta ZE-TODOS.ps1. Actualiza los recursos de SINCAL."))
  (princ))

(princ)
