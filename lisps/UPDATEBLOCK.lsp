;;; UPDATEBLOCK -- redefine desde el master sin borrar referencias ni purgar.
;;; Windows: AutoCAD / ZWCAD, ActiveX + ObjectDBX.
;;; Los atributos existentes conservan valores/campos. No ejecuta ATTSYNC.
;;; NIVEL_MM reconecta su formula a su propio BASE antes de sustituir el ATTDEF.
(vl-load-com)

(defun SUB:Fail (message) (princ (strcat "\nUPDATEBLOCK: " message)) (exit))

(defun SUB:Master (/ base path)
  (foreach base (list
      (if (getenv "LOCALAPPDATA") (strcat (getenv "LOCALAPPDATA") "/SINCAL/resources"))
      (if (getenv "ProgramFiles") (strcat (getenv "ProgramFiles") "/SINCAL"))
      (if (getenv "APPDATA") (strcat (getenv "APPDATA") "/Estandar SINCAL")))
    (if (and base (not path))
      (setq path (findfile (strcat base "/masters/FORMATOS ANOTATIVOS ACAD_2025.dwg")))))
  (if (not path) (setq path (findfile "FORMATOS ANOTATIVOS ACAD_2025.dwg")))
  (if (not path)
    (setq path (getfiled "Seleccione el master de formatos anotativos" "" "dwg" 0)))
  path)

(defun SUB:Dbx (/ prog result db programs)
  ;; No intentar cargar ObjectDBX de Autodesk dentro de ZWCAD.
  (setq programs
    (if (wcmatch (strcase (getvar "PROGRAM")) "*ZW*")
      '("ZWCAD.ZxDbDocument.2026" "ZWCAD.ZxDbDocument")
      (list (strcat "ObjectDBX.AxDbDocument." (itoa (atoi (getvar "ACADVER"))))) ))
  (foreach prog programs
    (if (not db)
      (progn
        (setq result (vl-catch-all-apply 'vla-GetInterfaceObject
                       (list (vlax-get-acad-object) prog)))
        (if (not (vl-catch-all-error-p result)) (setq db result)))))
  (if (not db) (SUB:Fail "No se pudo abrir el lector DWG del programa actual."))
  db)

(defun SUB:Name (obj)
  (if (vlax-property-available-p obj 'EffectiveName)
    (vla-get-EffectiveName obj) (vla-get-Name obj)))

(defun SUB:Dynamic (obj / props p)
  (if (and (vlax-property-available-p obj 'IsDynamicBlock)
           (= :vlax-true (vla-get-IsDynamicBlock obj)))
    (foreach p (vlax-invoke obj 'GetDynamicBlockProperties)
      (if (= :vlax-false (vla-get-ReadOnly p))
        (setq props (cons (cons (vla-get-PropertyName p) (vla-get-Value p)) props)))))
  props)

(defun SUB:FieldSignature (data depth / result item)
  (if (> depth 32) (SUB:Fail "Campo anidado demasiado profundo."))
  ;; Only the first group 1 is the evaluator. Later 1/301 groups can contain
  ;; evaluated cache values (notably in ZWCAD); formatting is in the code's \f.
  (setq result (list (assoc 2 data) (assoc 1 data)))
  (foreach item data
    (cond
      ((member (car item) '(3 331)) (setq result (cons item result)))
      ((= 360 (car item))
       (setq result (cons (list 360 (SUB:FieldSignature (entget (cdr item)) (1+ depth))) result)))))
  (reverse result))

(defun SUB:AttrValue (a / ext fields field)
  (setq ext (cdr (assoc 360 (entget (vlax-vla-object->ename a)))))
  (if (and ext (setq fields (dictsearch ext "ACAD_FIELD"))
           (setq field (dictsearch (cdr (assoc -1 fields)) "TEXT")))
    ;; ZWCAD can rebuild the field dictionary on REGEN. Compare expressions,
    ;; formats, child fields and referenced objects, not handles or cached text.
    (list 'field (SUB:FieldSignature field 0))
    (vla-get-TextString a)))

(defun SUB:Attributes (obj / values a)
  (if (= :vlax-true (vla-get-HasAttributes obj))
    (foreach a (vlax-invoke obj 'GetAttributes)
      ;; Keep attribute identity, literal values and field expressions.
      (setq values (cons (list (vla-get-Handle a) (vla-get-TagString a)
                              (SUB:AttrValue a)) values))))
  values)

(defun SUB:Placement (obj / data)
  (setq data (entget (vlax-vla-object->ename obj)))
  (mapcar '(lambda (code) (assoc code data)) '(5 8 10 41 42 43 50 67 210 410)))

(defun SUB:FieldReplace (text token value / pos start)
  (setq start 0)
  (while (setq pos (vl-string-search token text start))
    (setq text (strcat (substr text 1 pos) value
                       (substr text (+ pos (strlen token) 1)))
          start (+ pos (strlen value))))
  text)

(defun SUB:EntityData (entity / result)
  ;; A lost FIELD reference can be ENTITY NAME:0 rather than nil in ZWCAD.
  (setq result (vl-catch-all-apply 'entget (list entity)))
  (if (not (vl-catch-all-error-p result)) result))

(defun SUB:NivelField (field depth util / data code item idx target owner prefix child id eligible)
  ;; Expand both nested fields and ZWCAD's inline AcExpr representation. Object
  ;; indices are per FIELD; duplicate 331 entries are valid and retain order.
  (if (or (> depth 16) (not (setq data (SUB:EntityData field))))
    (progn (setq SUB:nbInvalid T) "")
    (progn
      (setq code "")
      (foreach item data
        (if (member (car item) '(2 3)) (setq code (strcat code (cdr item)))))
      (setq idx 0)
      (foreach item data
        (if (= 331 (car item))
          (progn
            (setq target (SUB:EntityData (cdr item))
                  owner (if target (SUB:EntityData (cdr (assoc 330 target))))
                  id (if target (vla-GetObjectIdString util
                        (vlax-ename->vla-object (cdr item)) :vlax-false) "0"))
            (setq eligible (or (not target)
                         (and (= "ATTDEF" (cdr (assoc 0 target)))
                              (= "BASE" (strcase (cdr (assoc 2 target))))
                              (equal "BLOCK_RECORD" (cdr (assoc 0 owner)))
                              (= "NIVEL_MM" (strcase (cdr (assoc 2 owner)))))))
            (if eligible
              (progn
                (if (not (member id SUB:nbTargets))
                  (setq SUB:nbTargets (cons id SUB:nbTargets)))
                ;; Record the actual BASE leaf, not an inline custom expression.
                (if (= code (strcat "\\AcObjProp.16.2 Object(%<\\_ObjIdx "
                                    (itoa idx) ">%,1).TextString"))
                  (setq SUB:nbLeaves (cons (list id field (cdr item)) SUB:nbLeaves)))))
            (setq code (SUB:FieldReplace code (strcat "%<\\_ObjIdx " (itoa idx) ">%")
                         (strcat "%<\\_ObjId " id ">%")))
            (setq idx (1+ idx)))))
      (setq idx 0)
      (foreach item data
        (if (= 360 (car item))
          (progn
            (setq child (SUB:NivelField (cdr item) (1+ depth) util)
                  code (SUB:FieldReplace code (strcat "%<\\_FldIdx " (itoa idx) ">%")
                          (strcat "%<" child ">%"))
                  idx (1+ idx)))))
      (if (or (vl-string-search "\\_FldIdx " code) (vl-string-search "\\_ObjIdx " code))
        (setq SUB:nbInvalid T))
      code)))

(defun SUB:RelinkNivelField (field target base / data result item state)
  ;; Keep the native FIELD tree/code/options. Rebuilding TextString causes
  ;; ZWCAD to create inline expressions that do not evaluate nested properties.
  (setq data (SUB:EntityData field) base (vlax-vla-object->ename base))
  (foreach item data
    (cond ((= 6 (car item)) (setq state (cdr item)))
          ((= 7 (car item)) (setq state nil)))
    (setq result (cons
      (if (and (equal target (cdr item))
               (or (= 331 (car item))
                   (and (= 330 (car item)) (equal "ObjectPropertyId" state))))
        (cons (car item) base) item) result)))
  (setq changed T)
  (if (not (entmod (reverse result)))
    (SUB:Fail "No se pudo reparar el vinculo BASE de NIVEL_MM. Se revierte.")))

(defun SUB:RepairNivelBase (doc obj / base level a count ext fields field code util id
                                    prefix suffix token pos matches target leaves leaf
                                    SUB:nbTargets SUB:nbLeaves SUB:nbInvalid)
  ;; Only the known NIVEL_MM formula is repaired. A literal NIVEL or a
  ;; customized/ambiguous field is left intact; BASE stays an editable attribute.
  (setq count 0 matches 0 SUB:nbTargets '("0"))
  (if (= :vlax-true (vla-get-HasAttributes obj))
    (foreach a (vlax-invoke obj 'GetAttributes)
      (cond
        ((= "BASE" (strcase (vla-get-TagString a))) (setq base a count (1+ count)))
        ((= "NIVEL" (strcase (vla-get-TagString a))) (setq level a count (1+ count))))))
  (if (and (= count 2) base level
           (setq ext (cdr (assoc 360 (entget (vlax-vla-object->ename level)))))
           (setq fields (dictsearch ext "ACAD_FIELD"))
           (setq field (dictsearch (cdr (assoc -1 fields)) "TEXT")))
    (progn
      (setq util (vla-get-Utility doc)
            code (SUB:NivelField (cdr (assoc -1 field)) 0 util))
      (if (/= "_text" (cdr (assoc 1 field))) (setq code (strcat "%<" code ">%")))
      ;; Recognize the complete known calculation, including the Y reference.
      ;; Only its BASE link changes; outer formatting and text remain verbatim.
      (setq prefix "%<\\AcExpr (%<\\AcObjProp.16.2 Object(%<\\_ObjId "
            suffix (strcat ".TextString>%+(%<\\AcObjProp.16.2 Object(%<\\_ObjId "
              (vla-GetObjectIdString util obj :vlax-false)
              ">%).Parameter(85).UpdatedY \\f \"%lu2%pr8%ds46\">%/1000))"))
      (foreach id SUB:nbTargets
        (setq token (strcat prefix id ">%,1)" suffix) pos 0)
        (while (setq pos (vl-string-search token code pos))
          (setq matches (1+ matches) target id pos (+ pos (strlen token)))))
      (foreach leaf SUB:nbLeaves
        (if (equal target (car leaf)) (setq leaves (cons leaf leaves))))
      (if (and (not SUB:nbInvalid) (= matches 1) (= (length leaves) 1))
        (progn
          ;; The outer _text field retains prefixes/suffixes such as "S.F. ".
          ;; Change only BASE's reference and its cached ObjectPropertyId.
          (setq leaf (car leaves))
          (SUB:RelinkNivelField (cadr leaf) (caddr leaf) base)
          (vla-Update level))))))

(defun SUB:References (doc name / result b obj)
  ;; Include nested references and every layout, not only visible inserts.
  (vlax-for b (vla-get-Blocks doc)
    (if (= :vlax-false (vla-get-IsXRef b))
      (vlax-for obj b
        (if (and (= "AcDbBlockReference" (vla-get-ObjectName obj))
                 (= (strcase name) (strcase (SUB:Name obj))))
          (setq result (cons (list obj (SUB:Placement obj)
                                   (SUB:Attributes obj) (SUB:Dynamic obj)) result))))))
  result)

(defun SUB:Restore (snapshots / obj old value row p)
  (foreach row snapshots
    (setq obj (car row))
    (foreach p (if (cadddr row) (vlax-invoke obj 'GetDynamicBlockProperties))
      (if (setq old (assoc (vla-get-PropertyName p) (cadddr row)))
        (progn
          (setq value (cdr old))
          (if (not (equal (vlax-variant-value value)
                         (vlax-variant-value (vla-get-Value p)) 1e-8))
            (vla-put-Value p value))
          (if (not (equal (vlax-variant-value value)
                         (vlax-variant-value (vla-get-Value p)) 1e-8))
            (SUB:Fail "Una propiedad dinamica antigua ya no admite su valor. Se revierte.")))))
    (if (or (not (equal (cadr row) (SUB:Placement obj) 1e-8))
            (not (equal (caddr row) (SUB:Attributes obj))))
      (SUB:Fail "No se conservaron la insercion o sus atributos. Se revierte."))))

(defun SUB:Redefine (doc db name / source objects temporary exported snapshots seed n)
  (setq source (vl-catch-all-apply 'vla-Item (list (vla-get-Blocks db) name)))
  (if (vl-catch-all-error-p source) (SUB:Fail "El bloque no existe en el master seleccionado."))
  (if (or (= :vlax-true (vla-get-IsXRef source))
          (= :vlax-true (vla-get-IsLayout source)))
    (SUB:Fail "El origen no es una definicion de bloque local."))
  (setq snapshots (SUB:References doc name))
  ;; Relink before replacing the source ATTDEF, including links already lost
  ;; by a previous redefinition. Verify retention against the repaired fields.
  (if (= "NIVEL_MM" (strcase name))
    (setq snapshots (mapcar '(lambda (row)
      (SUB:RepairNivelBase doc (car row))
      (list (car row) (cadr row) (SUB:Attributes (car row)) (cadddr row))) snapshots)))
  (setq seed (vl-filename-mktemp "SINCAL-UPDATEBLOCK-" nil ".dwg")
        exported seed n 0)
  ;; ZWCAD can reuse a name left by an interrupted run. Never overwrite it.
  (while (findfile exported)
    (setq n (1+ n) exported (strcat (vl-filename-directory seed) "/"
      (vl-filename-base seed) "_" (itoa n) ".dwg")))
  (setq
        SUB:tempfile exported
        temporary (vl-filename-base exported))
  (while (tblsearch "BLOCK" temporary) (setq temporary (strcat temporary "_")))
  ;; Rename only in the unsaved DBX database. Clone the entire block record,
  ;; including its dynamic extension dictionary, not just its visible entities.
  (vla-put-Name source temporary)
  (setq objects (vlax-make-safearray vlax-vbObject '(0 . 0)))
  (vlax-safearray-put-element objects 0 source)
  (vla-CopyObjects db objects (vla-get-Blocks doc))
  (setq changed T)
  (setq SUB:temporary (vla-Item (vla-get-Blocks doc) temporary))
  (command "_.-WBLOCK" exported temporary)
  (if (not (findfile exported)) (SUB:Fail "No se pudo exportar la definicion del master."))
  ;; Only our unreferenced staging definition is deleted; existing inserts stay.
  (vla-Delete SUB:temporary)
  (setq SUB:temporary nil)
  (command "_.-INSERT" (strcat name "=" exported))
  ;; Redefinition precedes the insertion-point prompt. Cancel that prompt:
  ;; no replacement reference is created, and handles remain unchanged.
  (command)
  (vla-Regen doc 1)
  (SUB:Restore snapshots)
  (length snapshots))

(defun c:UPDATEBLOCK (/ *error* doc pick obj name path db started changed
                       vars result SUB:tempfile SUB:temporary)
  (setq vars (mapcar '(lambda (v) (cons v (getvar v))) '(CMDECHO FILEDIA ATTREQ)))
  (defun *error* (message)
    (if started
      (progn (command-s "_.UNDO" "_End")
             (if changed (command-s "_.U"))))
    (if db (vlax-release-object db))
    (if SUB:tempfile (vl-file-delete SUB:tempfile))
    (foreach v vars (setvar (car v) (cdr v)))
    (if (and message (not (wcmatch (strcase message) "*CANCEL*,*BREAK*,*QUIT*")))
      (princ (strcat "\n" message)))
    (princ))
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (if (and (= 0 (getvar "BLOCKEDITOR"))
           (setq pick (entsel "\nSeleccione el bloque que desea actualizar desde el master: ")))
    (progn
      (setq obj (vlax-ename->vla-object (car pick)))
      (if (/= "AcDbBlockReference" (vla-get-ObjectName obj))
        (SUB:Fail "Seleccione una referencia de bloque."))
      (setq name (SUB:Name obj))
      (if (or (= :vlax-true (vla-get-IsXRef (vla-Item (vla-get-Blocks doc) name)))
              (= "*" (substr name 1 1)))
        (SUB:Fail "No se admiten referencias externas ni bloques anonimos sin nombre efectivo."))
      (if (setq path (SUB:Master))
        (progn
          (princ (strcat "\nMaster: " path "\nSe redefiniran TODAS las inserciones de " name "."
            "\nConserva atributos existentes; no agrega ni elimina atributos (sin ATTSYNC)."
            "\nLos bloques anidados existentes conservan su propia definicion."))
          (initget "Si No")
          (if (= "Si" (getkword "\nActualizar? [Si/No] <No>: "))
            (progn
              (if (= 0 (logand 1 (getvar "UNDOCTL")))
                (SUB:Fail "Active DESHACER antes de actualizar."))
              (setq db (SUB:Dbx))
              (vla-Open db path)
              (setvar "CMDECHO" 0) (setvar "FILEDIA" 0) (setvar "ATTREQ" 0)
              (command "_.UNDO" "_Begin")
              (setq started T changed nil)
              (setq result (SUB:Redefine doc db name))
              (command "_.UNDO" "_End")
              (setq started nil)
              (vlax-release-object db) (setq db nil)
              (vl-file-delete SUB:tempfile) (setq SUB:tempfile nil)
              (princ (strcat "\nUPDATEBLOCK: " name " actualizado; " (itoa result)
                             " inserciones conservadas. U permite deshacer.")))))))
    (princ "\nSeleccione un bloque fuera del editor de bloques."))
  (foreach v vars (setvar (car v) (cdr v)))
  (princ))

(princ)
