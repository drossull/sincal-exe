;;; SINCALISP: catalogo informativo de comandos distribuidos con SINCAL.
;;; Mantener una entrada por comando/alias; tests/test_sincalisp.py comprueba
;;; cobertura contra lisps/ y startup/. No carga ni ejecuta otros LISP.
;;; DCL temporal autocontenido: se distribuye como un solo recurso .lsp.
;;; ASCII deliberado para CAD con LISPSYS=0 y distintas paginas de codigos.

(defun SCL:Catalog ()
  '(
    ("ACTUALIZAR-MARCAS" "Repara los vinculos de las marcas con las filas de su tabla." "lisps/MARCAS-SC.lsp")
    ("BTORIENT" "Rota el bloque seleccionado para alinearlo mediante dos puntos." "lisps/BTORIENT.lsp")
    ("BV" "Bloquea todos los viewports de la presentacion actual." "lisps/BV.lsp")
    ("C-FIN" "Extrae coordenadas finales de un bloque a propiedades del dibujo y guarda el DWG." "lisps/SINCAL_PROPS.lsp")
    ("C-INICIO" "Extrae coordenadas iniciales de un bloque a propiedades del dibujo y guarda el DWG." "lisps/SINCAL_PROPS.lsp")
    ("C0" "Asigna color PorCapa (ByLayer) a los objetos seleccionados." "startup/SINCAL_STARTUP.lsp")
    ("C1" "Asigna color ACI 1 (rojo) a los objetos seleccionados." "startup/SINCAL_STARTUP.lsp")
    ("C2" "Asigna color ACI 2 (amarillo) a los objetos seleccionados." "startup/SINCAL_STARTUP.lsp")
    ("C3" "Asigna color ACI 3 (verde) a los objetos seleccionados." "startup/SINCAL_STARTUP.lsp")
    ("C4" "Asigna color ACI 4 (cian) a los objetos seleccionados." "startup/SINCAL_STARTUP.lsp")
    ("C5" "Asigna color ACI 5 (azul) a los objetos seleccionados." "startup/SINCAL_STARTUP.lsp")
    ("C6" "Asigna color ACI 6 (magenta) a los objetos seleccionados." "startup/SINCAL_STARTUP.lsp")
    ("C7" "Asigna color ACI 7 (blanco/negro segun el fondo) a la seleccion." "startup/SINCAL_STARTUP.lsp")
    ("C8" "Asigna color ACI 8 (gris oscuro) a los objetos seleccionados." "startup/SINCAL_STARTUP.lsp")
    ("C9" "Asigna color ACI 9 (gris claro) a los objetos seleccionados." "startup/SINCAL_STARTUP.lsp")
    ("CEVIADA" "Acota elementos esviados y agrega la longitud proyectada mediante un campo." "lisps/CEVIADA.lsp")
    ("COPY-PROPS" "Copia las propiedades personalizadas del dibujo para pegarlas en otro." "lisps/SINCAL_PROPS.lsp")
    ("CPOL" "Dibuja una polilinea simetrica indicando su centro y uno de sus extremos." "lisps/CPOL.lsp")
    ("CSV-SC" "Importa armaduras CSV/XSR a una tabla editable con estilo TENSIONES." "lisps/CSV-SC.lsp")
    ("CUSTOM-PROPS" "Permite editar las propiedades personalizadas del plano." "lisps/SINCAL_PROPS.lsp")
    ("DEL-VIN" "BORRA objetos de las zonas fijas de la vineta del layout; conserva viewports." "lisps/DEL-VIN.lsp")
    ("DIMEL" "Genera cotas en ES-ACOTADO a partir de intersecciones con una linea de corte." "lisps/DIMEL.lsp")
    ("DL2" "BORRA las presentaciones llamadas Layout2 y A1." "lisps/DL2.lsp")
    ("DUP" "Duplica los objetos seleccionados en su misma posicion." "lisps/DUP.lsp")
    ("DUPLICAR" "Alias de DUP: duplica la seleccion en su misma posicion." "lisps/DUP.lsp")
    ("EXTRIMOUT" "Recorta con un circulo y BORRA lo exterior en el espacio actual. Requiere Express Tools." "lisps/EXTRIMOUT.lsp")
    ("LAYORIGIN" "Restablece el origen interno del papel del layout, sin mover los objetos." "lisps/LAYORIGIN.lsp")
    ("MARCA-CONFIG" "Reinicia la configuracion guardada de marcas para pedirla en la siguiente insercion." "lisps/MARCAS-SC.lsp")
    ("MARCA-DE" "Inserta marca de despiece vinculada a tabla, con cantidad total y largo editables." "lisps/MARCAS-SC.lsp")
    ("MARCA-SC" "Inserta marca de vista vinculada a la tabla de armaduras." "lisps/MARCAS-SC.lsp")
    ("MARCA-UP" "Actualiza bloques de marcas antiguos; sustituye referencias compatibles." "lisps/MARCAS-SC.lsp")
    ("MC" "Cambia TEXT/MTEXT a justificacion Medio Centro sin desplazarlos visualmente." "lisps/MC.lsp")
    ("MPEND" "Rota multileaders desde la punta para alinearlos con una pendiente porcentual." "lisps/MPEND.lsp")
    ("P0" "Pega el portapapeles como bloque en 0,0,0 del espacio actual." "lisps/P0.lsp")
    ("PASTE-PROPS" "Pega las propiedades copiadas y solicita el nombre del plano." "lisps/SINCAL_PROPS.lsp")
    ("PLOTYA" "Genera un PDF junto al DWG con su mismo nombre y la configuracion de trazado actual." "lisps/PLOTYA.lsp")
    ("PND" "Muestra la pendiente XY absoluta entre los extremos de una linea o polilinea." "lisps/PND.lsp")
    ("PNDMAKE" "Rota un objeto completo a una pendiente porcentual en el plano XY del UCS." "lisps/PNDMAKE.lsp")
    ("PURGEALL" "Purga elementos y aplicaciones sin uso; elimina escalas no utilizadas." "lisps/PURGEALL.lsp")
    ("REASIGNAR-MARCA" "Vincula nuevamente una marca a la fila elegida de una tabla." "lisps/MARCAS-SC.lsp")
    ("REPARAR-PROPS" "Elimina propiedades personalizadas duplicadas, conserva valores y guarda el DWG." "lisps/SINCAL_PROPS.lsp")
    ("REVISAR-MARCAS" "Revisa las marcas y comunica problemas de vinculacion, sin repararlas." "lisps/MARCAS-SC.lsp")
    ("RMLAY" "Renombra la presentacion actual." "lisps/RMLAY.lsp")
    ("ROMAND" "Configura RomanD anotativo: romand.shx, altura 2.5, ancho 0.8, sin efectos." "lisps/ROMAND.lsp")
    ("RPUENTE" "Mide el radio de una curva o de tres puntos y permite marcar su centro." "lisps/RPUENTE.lsp")
    ("SEL-SC" "Permite escoger una unica escala anotativa para conservar en la seleccion." "lisps/SEL-SC.lsp")
    ("SETUP-A1" "Configura todas las presentaciones para PDF A1, escala 1:1 y plumillas SINCAL." "lisps/SETUP-A1.lsp")
    ("SINCAL" "Importa bloques, estilos y capas desde el master de formatos anotativos." "lisps/SINCAL.lsp")
    ("SINCAL-ESCALAS" "Crea escalas estandarizadas para dibujos trabajados en metros." "lisps/SINCAL_ESCALAS.lsp")
    ("SINCALISP" "Abre este catalogo alfabetico de comandos y sus descripciones." "lisps/SINCALISP.lsp")
    ("ST0" "Establece en cero la altura de TODOS los estilos de texto." "lisps/ST0.lsp")
    ("STO" "Alias de ST0 (letra O): pone en cero la altura de todos los estilos de texto." "lisps/ST0.lsp")
    ("TXT-JOIN" "Reconstruye TEXT fragmentados en MTEXT editable. No reconoce letras hechas de lineas." "lisps/TXT-JOIN.lsp")
    ("VG" "BORRA bloques con prefijo VINETA en Modelo y layouts y ejecuta PURGEALL." "lisps/VG.lsp")
    ("VPTOGGLE" "Enciende o apaga la capa de marcos llamada Viewport layer." "lisps/VPTOGGLE.lsp")
    ("VRAP" "Crea viewports en un layout a partir de areas indicadas previamente en Modelo." "lisps/VRAP.lsp")
    ("W08" "Establece factor de ancho 0.8 en TODOS los estilos de texto." "lisps/W08.lsp")
    ("ZE" "Hace zoom a la extension completa del dibujo en el espacio actual." "lisps/ZE.lsp")
    ("ZV" "Encuadra el tercio inferior derecho de la hoja del layout actual." "lisps/ZV.lsp")
  ))

(defun SCL:Rows (query / catalog names rows name entry)
  (setq catalog (SCL:Catalog) query (strcase query)
        names (acad_strlsort (mapcar 'car catalog)))
  (foreach name names
    (setq entry (assoc name catalog))
    (if (or (= query "")
            (vl-string-search query (strcase (strcat (car entry) " " (cadr entry) " " (caddr entry)))))
      (setq rows (cons entry rows))))
  (reverse rows))

(defun SCL:Select (index / entry)
  (setq entry (if (/= index "") (nth (atoi index) SCL:visible)))
  (set_tile "source" (if entry (strcat "Archivo: " (caddr entry)) ""))
  (set_tile "detail1" (if entry (substr (cadr entry) 1 90) "Sin coincidencias."))
  (set_tile "detail2" (if (and entry (> (strlen (cadr entry)) 90)) (substr (cadr entry) 91) "")))

(defun SCL:Refresh (query / entry)
  (setq SCL:visible (SCL:Rows query))
  (start_list "commands")
  (foreach entry SCL:visible
    (add_list (strcat (car entry) "\t" (cadr entry))))
  (end_list)
  (set_tile "count" (strcat (itoa (length SCL:visible)) " de " (itoa (length (SCL:Catalog))) " comandos"))
  (if SCL:visible (set_tile "commands" "0"))
  (SCL:Select (if SCL:visible "0" "")))

(defun SCL:Dcl ()
  '(
    "sincalisp : dialog { label = \"SINCALISP - Catalogo de comandos\"; initial_focus = \"search\";"
    ": text { label = \"Consulta informativa: selecciona una fila para ver su descripcion completa.\"; }"
    ": edit_box { key = \"search\"; label = \"Buscar comando o descripcion (Tab para filtrar):\"; edit_width = 55; }"
    ": list_box { key = \"commands\"; label = \"COMANDO                 DESCRIPCION\"; width = 112; height = 23; fixed_width = true; fixed_height = true; fixed_width_font = true; tabs = \"24\"; multiple_select = false; allow_accept = false; }"
    ": text { key = \"count\"; width = 100; fixed_width = true; }"
    ": boxed_column { label = \"Detalle del comando seleccionado\";"
    ": text { key = \"detail1\"; width = 100; fixed_width = true; }"
    ": text { key = \"detail2\"; width = 100; fixed_width = true; }"
    ": text { key = \"source\"; width = 100; fixed_width = true; } }"
    ": text { label = \"Esta ventana no ejecuta comandos ni modifica el dibujo.\"; }"
    ": button { key = \"close\"; label = \"Cerrar\"; is_default = true; is_cancel = true; fixed_width = true; width = 14; alignment = centered; }"
    "}"
  ))

(defun c:SINCALISP (/ *error* path stream dialog line SCL:visible)
  (defun *error* (msg)
    (if stream (progn (close stream) (setq stream nil)))
    (if (and dialog (> dialog 0)) (progn (unload_dialog dialog) (setq dialog nil)))
    (if path (progn (vl-file-delete path) (setq path nil)))
    (if (and msg (not (wcmatch (strcase msg) "*CANCEL*,*QUIT*,*EXIT*,*BREAK*")))
      (princ (strcat "\nSINCALISP: " msg)))
    (princ))
  (setq path (vl-filename-mktemp "SINCALISP-" nil ".dcl"))
  (cond
    ((not (setq stream (open path "w")))
      (princ "\nSINCALISP: no se pudo crear el cuadro temporal."))
    (T
      (foreach line (SCL:Dcl) (write-line line stream))
      (close stream) (setq stream nil)
      (setq dialog (load_dialog path))
      (if (and (> dialog 0) (new_dialog "sincalisp" dialog))
        (progn
          (SCL:Refresh "")
          (action_tile "search" "(SCL:Refresh $value)")
          (action_tile "commands" "(SCL:Select $value)")
          (action_tile "close" "(done_dialog 1)")
          (start_dialog))
        (princ "\nSINCALISP: no se pudo abrir el cuadro DCL."))))
  (*error* nil)
  (princ))

(princ "\nSINCALISP cargado: catalogo de comandos SINCAL y sus descripciones.")
(princ)
