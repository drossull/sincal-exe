"""Órdenes CAD pequeñas para el asistente híbrido de armaduras.

Las funciones sólo construyen AutoLISP portable entre AutoCAD y ZWCAD. La
interfaz decide cuándo enviarlo al dibujo activo y cómo presentar el resultado.
"""

from __future__ import annotations

import re
from typing import Iterable

from sincal.cad.moldajes import MoldajeContext


_LAYER_RE = re.compile(r"^[A-Za-z0-9_ .-]+$")


def _normalise_layers(layers: Iterable[str]) -> tuple[str, ...]:
    result = []
    seen = set()
    for raw in layers:
        layer = str(raw).strip().upper()
        if not layer or layer in seen:
            continue
        if not _LAYER_RE.fullmatch(layer):
            raise ValueError(f"Nombre de capa no permitido: {raw!r}")
        seen.add(layer)
        result.append(layer)
    if not result:
        raise ValueError("Se requiere al menos una capa de moldaje.")
    return tuple(result)


def _lisp_string(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def build_prepare_layers_lisp(layers: Iterable[str]) -> str:
    """Crea capas de moldaje faltantes y conserva las ya existentes."""

    names = _normalise_layers(layers)
    layer_list = " ".join(f'"{_lisp_string(name)}"' for name in names)
    return f'''(vl-load-com)
(defun c:SINCAL-PREPARAR-ARMADURAS (/ doc collection name created item)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq collection (vla-get-Layers doc) created 0)
  (foreach name '({layer_list})
    (if (not (tblsearch "LAYER" name))
      (progn
        (setq item (vla-Add collection name))
        (vla-put-Color item 1)
        (setq created (1+ created))
      )
    )
  )
  (princ (strcat "\\n[SINCAL] Capas de moldaje listas. Nuevas: " (itoa created) "."))
  (princ)
)'''

def build_moldaje_scan_lisp(
    output_path: str,
    layers: Iterable[str],
    *,
    context: MoldajeContext | None = None,
    interactive: bool = False,
) -> str:
    """Construye un detector V2 global o limitado por selección del usuario."""

    names = _normalise_layers(layers)
    ctx = context or MoldajeContext()
    layer_list = " ".join(f'"{_lisp_string(name)}"' for name in names)
    layer_pattern = _lisp_string(",".join(names))
    selection = (
        '(progn (prompt "\\nSeleccione los moldajes del elemento y presione Enter: ") '
        '(ssget \'((0 . "LWPOLYLINE,POLYLINE"))))'
        if interactive else
        f'(ssget "_X" (list \'(0 . "LWPOLYLINE,POLYLINE") (cons 8 "{layer_pattern}")))'
    )
    out = _lisp_string(output_path)
    partial = _lisp_string(f"{output_path}.part")
    element = _lisp_string(ctx.element)
    instance = _lisp_string(ctx.instance)
    view = _lisp_string(ctx.view)
    return f'''(vl-load-com)
(defun sincal:allowed-layer-p (name) (if (member (strcase name) '({layer_list})) T nil))
(defun sincal:closed-p (data) (/ flags)
  (setq flags (cdr (assoc 70 data)))
  (and flags (/= 0 (logand 1 flags)))
)
(defun sincal:supported-poly-p (data / kind flags)
  (setq kind (cdr (assoc 0 data)) flags (cdr (assoc 70 data)))
  (or (= kind "LWPOLYLINE")
      (and (= kind "POLYLINE") (= 0 (logand (if flags flags 0) 88))))
)
(defun sincal:poly-data (ent / data kind cursor vertex result points bulges bulge)
  (setq data (entget ent) kind (cdr (assoc 0 data)) points '() bulges '())
  (if (= kind "LWPOLYLINE")
    (foreach pair data
      (if (= (car pair) 10)
        (progn
          (setq points (append points (list (cdr pair))))
          (setq bulges (append bulges (list 0.0)))
        )
        (if (and (= (car pair) 42) bulges)
          (setq bulges (append (reverse (cdr (reverse bulges))) (list (cdr pair))))
        )
      )
    )
    (progn
      (setq cursor (entnext ent))
      (while (and cursor (/= (cdr (assoc 0 (setq vertex (entget cursor)))) "SEQEND"))
        (if (= (cdr (assoc 0 vertex)) "VERTEX")
          (progn
            (setq points (append points (list (cdr (assoc 10 vertex)))))
            (setq bulge (cdr (assoc 42 vertex)))
            (setq bulges (append bulges (list (if bulge bulge 0.0))))
          )
        )
        (setq cursor (entnext cursor))
      )
    )
  )
  (list points bulges)
)
(defun sincal:points-text (points / text point)
  (setq text "")
  (foreach point points
    (setq text (strcat text (if (= text "") "" ";")
                       (rtos (car point) 2 9) "," (rtos (cadr point) 2 9)))
  )
  text
)
(defun sincal:bulges-text (bulges / text value)
  (setq text "")
  (foreach value bulges
    (setq text (strcat text (if (= text "") "" ";") (rtos value 2 12)))
  )
  text
)
(defun sincal:has-arcs-p (bulges / found)
  (setq found nil)
  (foreach value bulges (if (> (abs value) 0.000000001) (setq found T)))
  found
)
(defun c:SINCAL-ANALIZAR-MOLDAJES (/ *error* out tmp-path ss index ent data layer shape points bulges count closed arcs status obj area-result area handle)
  (defun *error* (message)
    (if out (progn (close out) (setq out nil)))
    (if (and tmp-path (findfile tmp-path)) (vl-file-delete tmp-path))
    (if (and message (/= message "Function cancelled") (/= message "quit / exit abort"))
      (princ (strcat "\\n[SINCAL] Error al analizar moldajes: " message)))
    (princ)
  )
  (setq ss {selection})
  (setq tmp-path "{partial}")
  (if (findfile tmp-path) (vl-file-delete tmp-path))
  (setq out (open tmp-path "w"))
  (write-line "SINCAL_MOLDAJES_V2" out)
  (write-line (strcat "META|INSUNITS|" (itoa (getvar "INSUNITS"))) out)
  (write-line "META|ELEMENT|{element}" out)
  (write-line "META|INSTANCE|{instance}" out)
  (write-line "META|VIEW|{view}" out)
  (write-line (strcat "META|SELECTION|" (if ss "OK" "CANCELLED")) out)
  (if ss
    (progn
      (setq index 0)
      (repeat (sslength ss)
        (setq ent (ssname ss index) data (entget ent) layer (strcase (cdr (assoc 8 data))))
        (if (and (sincal:allowed-layer-p layer) (sincal:supported-poly-p data))
          (progn
            (setq shape (sincal:poly-data ent)
                  points (car shape) bulges (cadr shape)
                  count (length points) closed (sincal:closed-p data)
                  arcs (sincal:has-arcs-p bulges) handle (cdr (assoc 5 data)))
            (cond
              ((< count 2) (setq status "INVALID"))
              ((and closed arcs) (setq status "ARC"))
              (closed (setq status "OK"))
              (arcs (setq status "OPEN_ARC"))
              (T (setq status "OPEN"))
            )
            (setq obj (vlax-ename->vla-object ent))
            (setq area-result (vl-catch-all-apply 'vla-get-Area (list obj)))
            (setq area (if (vl-catch-all-error-p area-result) 0.0 area-result))
            (write-line (strcat "CANDIDATE|" layer "|" handle "|" status "|"
                                (itoa count) "|" (rtos area 2 9)) out)
            (write-line (strcat "VERTICES|" layer "|" handle "|" (sincal:points-text points)) out)
            (write-line (strcat "GEOMETRY|" layer "|" handle "|"
                                (if closed "CLOSED" "OPEN") "|" (if arcs "1" "0")) out)
            (write-line (strcat "BULGES|" layer "|" handle "|" (sincal:bulges-text bulges)) out)
            (write-line (strcat "CONTEXT|" layer "|" handle "|{element}|{instance}|") out)
          )
        )
        (setq index (1+ index))
      )
    )
  )
  (close out)
  (setq out nil)
  (if (findfile "{out}") (vl-file-delete "{out}"))
  (vl-file-rename tmp-path "{out}")
  (princ "\\n[SINCAL] Análisis de moldajes terminado. Vuelva a SINCAL.")
  (princ)
)'''

