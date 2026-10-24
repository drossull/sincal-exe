"""Rectángulos de referencia elegidos explícitamente en AutoCAD/ZWCAD.

El comando generado guía al dibujante, elemento por elemento, para marcar la
esquina superior izquierda y la esquina inferior derecha de cada rectángulo.
No busca entidades, no depende de capas, no recorre el dibujo y no modifica el
documento. Los puntos se convierten de UCS a WCS antes de escribir este
protocolo::

    SINCAL_SELECTED_MOLDAJE_V1
    META|INSUNITS|6
    META|SELECTION|OK
    META|ELEMENT|abutment
    META|INSTANCE|entrada
    META|VIEW|FR
    META|EXPECTED|2
    META|ELEMENTS|abutment.footing;abutment.front_wall
    RECTANGLE|abutment.footing|0;5;0|10;0;0
    RECTANGLE|abutment.front_wall|2;8;0|8;5;0

Cada registro conserva las dos esquinas WCS crudas. El parser expone cuatro
vértices WCS alineados con los ejes, sin convertir unidades. Corresponde al
servicio validar la coherencia de escala antes de generar armaduras.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
import re
from typing import Iterable, Mapping

from sincal.cad.moldajes import MoldajeCandidate, MoldajeContext


PROTOCOL_HEADER = "SINCAL_SELECTED_MOLDAJE_V1"
MAX_ELEMENTS = 32
_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
Point3D = tuple[float, float, float]
Rectangle3D = tuple[Point3D, Point3D, Point3D, Point3D]


@dataclass(frozen=True)
class SelectedMoldaje:
    """Resultado de la secuencia guiada de rectángulos.

    ``rectangles`` conserva el orden de ``elements``. ``candidate`` queda
    reservado para que el servicio cree la zapata sólo después de contrastar
    la escala con el JSON; ``INSUNITS`` por sí solo no prueba la escala real.
    """

    rectangles: dict[str, Rectangle3D]
    insunits: int | None
    selection: str
    candidate: MoldajeCandidate | None = None
    error: str | None = None

    @property
    def uses_metres(self) -> bool:
        return self.insunits == 6


def _lisp_string(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _protocol_value(value: object, label: str) -> str:
    result = str(value or "").strip()
    if any(character in result for character in "|\r\n"):
        raise ValueError(f"{label} contiene caracteres no permitidos.")
    return result


def _normalise_elements(elements: Iterable[Mapping[str, object]]) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in elements:
        if not isinstance(raw, Mapping):
            raise TypeError("Cada elemento debe contener key y label.")
        key = _protocol_value(raw.get("key"), "La clave del elemento")
        label = str(raw.get("label") or "").strip()
        if not key or not _KEY_RE.fullmatch(key):
            raise ValueError(f"Clave de elemento no permitida: {key!r}.")
        if not label:
            raise ValueError(f"El elemento {key!r} no tiene etiqueta.")
        folded = key.casefold()
        if folded in seen:
            raise ValueError(f"La secuencia repite el elemento {key!r}.")
        seen.add(folded)
        result.append((key, label))
    if not result:
        raise ValueError("Se requiere al menos un elemento para la vista.")
    if len(result) > MAX_ELEMENTS:
        raise ValueError(f"La vista admite como máximo {MAX_ELEMENTS} elementos.")
    return tuple(result)


def build_selection_lisp(
    output_path: str,
    context: MoldajeContext,
    elements: Iterable[Mapping[str, object]],
) -> str:
    """Crea ``c:SINCAL-SELECCIONAR-MOLDAJE`` para una vista y su secuencia.

    Cada elemento usa ``getpoint`` seguido de ``getcorner``. Una cancelación o
    un rectángulo degenerado invalida la secuencia completa: no se publican
    resultados parciales que pudieran usarse accidentalmente para generar.
    """

    if not isinstance(context, MoldajeContext):
        raise TypeError("context debe ser MoldajeContext.")
    path = str(output_path).strip()
    if not path or any(character in path for character in "\r\n\0"):
        raise ValueError("La ruta de salida no es válida.")

    sequence = _normalise_elements(elements)
    element = _protocol_value(context.element, "El elemento")
    instance = _protocol_value(context.instance, "La instancia")
    view = _protocol_value(context.view, "La vista")
    lisp_elements = " ".join(
        f'("{_lisp_string(key)}" "{_lisp_string(label)}")'
        for key, label in sequence
    )
    out = _lisp_string(path)
    partial = _lisp_string(f"{path}.part")
    prompt_instance = _lisp_string(instance or "seleccionada")
    prompt_view = _lisp_string(view or "actual")
    protocol_keys = ";".join(key for key, _label in sequence)

    return f'''(vl-load-com)
(defun sincal:number-text (value) (rtos value 2 15))
(defun sincal:point-text (point)
  (strcat (sincal:number-text (car point)) ";"
          (sincal:number-text (cadr point)) ";"
          (sincal:number-text (caddr point)))
)
(defun sincal:valid-rectangle-p (first opposite)
  (and first opposite
       (< (car first) (car opposite))
       (> (cadr first) (cadr opposite))
       (equal (caddr first) (caddr opposite) 0.000000001))
)
(defun sincal:safe-getpoint (message / result)
  (setq result (vl-catch-all-apply 'getpoint (list message)))
  (if (vl-catch-all-error-p result) nil result)
)
(defun sincal:safe-getcorner (first message / result)
  (setq result (vl-catch-all-apply 'getcorner (list first message)))
  (if (vl-catch-all-error-p result) nil result)
)
(defun c:SINCAL-SELECCIONAR-MOLDAJE (/ *error* tmp-path out state failure rectangles item key label first opposite first-wcs opposite-wcs)
  (defun *error* (message)
    (if out (progn (close out) (setq out nil)))
    (if (and tmp-path (findfile tmp-path)) (vl-file-delete tmp-path))
    (setq tmp-path "{partial}")
    (setq out (open tmp-path "w"))
    (if out
      (progn
        (write-line "{PROTOCOL_HEADER}" out)
        (write-line (strcat "META|INSUNITS|" (itoa (getvar "INSUNITS"))) out)
        (write-line "META|SELECTION|ERROR" out)
        (write-line "META|ELEMENT|{_lisp_string(element)}" out)
        (write-line "META|INSTANCE|{_lisp_string(instance)}" out)
        (write-line "META|VIEW|{_lisp_string(view)}" out)
        (write-line "META|EXPECTED|{len(sequence)}" out)
        (write-line "META|ELEMENTS|{protocol_keys}" out)
        (write-line "META|ERROR|COMMAND_ABORTED" out)
        (close out)
        (setq out nil)
        (if (findfile "{out}") (vl-file-delete "{out}"))
        (vl-file-rename tmp-path "{out}"))
    )
    (if message (princ (strcat "\n[SINCAL] Selección interrumpida: " message)))
    (princ)
  )
  (setq state "OK" failure "" rectangles '())
  (foreach item '({lisp_elements})
    (if (= state "OK")
      (progn
        (setq key (car item) label (cadr item))
        (setq first
          (sincal:safe-getpoint
            (strcat "\n[SINCAL] " label " — vista {prompt_view}, {prompt_instance}: marque la esquina SUPERIOR IZQUIERDA: ")))
        (if (not first)
          (setq state "CANCELLED" failure (strcat "Cancelado en " key "."))
          (progn
            (setq opposite
              (sincal:safe-getcorner first
                (strcat "\n[SINCAL] " label ": marque la esquina INFERIOR DERECHA: ")))
            (if (not opposite)
              (setq state "CANCELLED" failure (strcat "Cancelado en " key "."))
              (progn
                (setq first-wcs (trans first 1 0)
                      opposite-wcs (trans opposite 1 0))
                (if (sincal:valid-rectangle-p first-wcs opposite-wcs)
                  (setq rectangles
                    (append rectangles (list (list key first-wcs opposite-wcs))))
                  (setq state "INVALID"
                        failure (strcat key ": las esquinas no forman un rectángulo superior-izquierdo / inferior-derecho válido."))
                )
              )
            )
          )
        )
      )
    )
  )
  (setq tmp-path "{partial}")
  (if (findfile tmp-path) (vl-file-delete tmp-path))
  (setq out (open tmp-path "w"))
  (write-line "{PROTOCOL_HEADER}" out)
  (write-line (strcat "META|INSUNITS|" (itoa (getvar "INSUNITS"))) out)
  (write-line (strcat "META|SELECTION|" state) out)
  (write-line "META|ELEMENT|{_lisp_string(element)}" out)
  (write-line "META|INSTANCE|{_lisp_string(instance)}" out)
  (write-line "META|VIEW|{_lisp_string(view)}" out)
  (write-line "META|EXPECTED|{len(sequence)}" out)
  (write-line "META|ELEMENTS|{protocol_keys}" out)
  (if (= state "OK")
    (foreach item rectangles
      (write-line
        (strcat "RECTANGLE|" (car item) "|"
                (sincal:point-text (cadr item)) "|"
                (sincal:point-text (caddr item))) out)
    )
    (write-line (strcat "META|ERROR|" failure) out)
  )
  (close out)
  (setq out nil)
  (if (findfile "{out}") (vl-file-delete "{out}"))
  (vl-file-rename tmp-path "{out}")
  (if (= state "OK")
    (princ "\n[SINCAL] Rectángulos registrados. Vuelva a SINCAL.")
    (princ "\n[SINCAL] No se registró ningún rectángulo. Repita la selección desde SINCAL."))
  (princ)
)'''


def _parse_point(value: str, key: str) -> Point3D:
    try:
        coordinates = tuple(float(item.strip()) for item in value.split(";"))
    except ValueError as exc:
        raise ValueError(f"El rectángulo {key!r} contiene coordenadas no numéricas.") from exc
    if len(coordinates) != 3 or not all(isfinite(number) for number in coordinates):
        raise ValueError(f"El rectángulo {key!r} debe contener puntos WCS XYZ finitos.")
    return coordinates  # type: ignore[return-value]


def _rectangle(first: Point3D, opposite: Point3D, key: str) -> Rectangle3D:
    if not isclose(first[2], opposite[2], rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError(f"El rectángulo {key!r} no pertenece a un plano XY único.")
    if first[0] >= opposite[0] or first[1] <= opposite[1]:
        raise ValueError(
            f"El rectángulo {key!r} es degenerado o sus esquinas no corresponden a "
            "superior izquierda e inferior derecha."
        )
    z_value = first[2]
    return (
        first,
        (opposite[0], first[1], z_value),
        opposite,
        (first[0], opposite[1], z_value),
    )


def _validate_context(meta: Mapping[str, str], context: MoldajeContext) -> None:
    for key, expected in (
        ("ELEMENT", context.element),
        ("INSTANCE", context.instance),
        ("VIEW", context.view),
    ):
        actual = meta.get(key, "").strip()
        if expected and actual.casefold() != expected.strip().casefold():
            raise ValueError(
                f"El resultado corresponde a otra {key.lower()}: {actual!r}; se esperaba {expected!r}."
            )


def parse_selected_moldaje(text: str, context: MoldajeContext) -> SelectedMoldaje:
    """Lee la secuencia y devuelve rectángulos WCS sin aplicar escala.

    ``CANCELLED``, ``INVALID`` y ``ERROR`` son resultados seguros sin
    rectángulos ni candidato. Un protocolo marcado ``OK`` pero incompleto o
    geométricamente inválido se rechaza, pues podría producir armaduras en una
    posición equivocada.
    """

    if not isinstance(context, MoldajeContext):
        raise TypeError("context debe ser MoldajeContext.")
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if not lines or lines[0] != PROTOCOL_HEADER:
        raise ValueError("El resultado no tiene un encabezado de selección SINCAL válido.")

    meta: dict[str, str] = {}
    raw_rectangles: list[tuple[str, Point3D, Point3D]] = []
    seen_keys: set[str] = set()
    for line in lines[1:]:
        parts = line.split("|")
        record = parts[0].strip().upper()
        if record == "META" and len(parts) == 3:
            key = parts[1].strip().upper()
            if key in meta:
                raise ValueError(f"El resultado repite el metadato {key}.")
            meta[key] = parts[2].strip()
        elif record == "RECTANGLE" and len(parts) == 4:
            key = parts[1].strip()
            if not key or not _KEY_RE.fullmatch(key):
                raise ValueError(f"Clave de rectángulo no permitida: {key!r}.")
            folded = key.casefold()
            if folded in seen_keys:
                raise ValueError(f"El resultado repite el rectángulo {key!r}.")
            seen_keys.add(folded)
            raw_rectangles.append((key, _parse_point(parts[2], key), _parse_point(parts[3], key)))
        else:
            raise ValueError(f"Registro de selección no reconocido o incompleto: {line!r}.")

    _validate_context(meta, context)
    try:
        insunits = int(meta["INSUNITS"])
    except (KeyError, ValueError) as exc:
        raise ValueError("El resultado no informa un INSUNITS válido.") from exc
    selection = meta.get("SELECTION", "").strip().lower()
    error = meta.get("ERROR") or None
    if selection in {"cancelled", "invalid", "error"}:
        if raw_rectangles:
            raise ValueError("Una secuencia fallida no puede publicar rectángulos parciales.")
        return SelectedMoldaje({}, insunits, selection, None, error)
    if selection != "ok":
        raise ValueError("El estado de selección debe ser OK, CANCELLED, INVALID o ERROR.")
    if error:
        raise ValueError(f"Una selección OK no puede contener error: {error}.")

    try:
        expected = int(meta["EXPECTED"])
    except (KeyError, ValueError) as exc:
        raise ValueError("El resultado no informa la cantidad esperada de elementos.") from exc
    if expected < 1 or expected > MAX_ELEMENTS:
        raise ValueError("La cantidad esperada de elementos está fuera del rango permitido.")
    expected_keys = tuple(key for key in meta.get("ELEMENTS", "").split(";") if key)
    if len(expected_keys) != expected or any(not _KEY_RE.fullmatch(key) for key in expected_keys):
        raise ValueError("El resultado no identifica correctamente la secuencia esperada de elementos.")
    if len(raw_rectangles) != expected:
        raise ValueError(
            f"La selección está incompleta: se esperaban {expected} rectángulos y llegaron "
            f"{len(raw_rectangles)}."
        )
    received_keys = tuple(key for key, _first, _opposite in raw_rectangles)
    if tuple(key.casefold() for key in received_keys) != tuple(
        key.casefold() for key in expected_keys
    ):
        raise ValueError("Los rectángulos no corresponden a la secuencia de elementos solicitada.")

    rectangles = {
        key: _rectangle(first, opposite, key)
        for key, first, opposite in raw_rectangles
    }
    return SelectedMoldaje(rectangles, insunits, selection, None, None)
