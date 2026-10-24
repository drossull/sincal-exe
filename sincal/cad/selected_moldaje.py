"""Referencias geométricas elegidas explícitamente en AutoCAD/ZWCAD.

El comando generado guía al dibujante, elemento por elemento, para marcar dos
esquinas de un rectángulo o tres vértices consecutivos de un paralelogramo.
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
    PARALLELOGRAM|abutment.front_wall|2;8;0|8;9;0|9;5;0

Cada registro conserva los puntos WCS crudos. El parser expone siempre cuatro
vértices en ``rectangles`` por compatibilidad y declara su tipo en
``reference_modes``. No convierte unidades; corresponde al servicio validar
la coherencia de escala antes de generar armaduras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot, isclose, isfinite
import re
from typing import Iterable, Mapping

from sincal.cad.moldajes import MoldajeCandidate, MoldajeContext


PROTOCOL_HEADER = "SINCAL_SELECTED_MOLDAJE_V1"
MAX_ELEMENTS = 32
_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_REFERENCE_MODES = {"rectangle", "parallelogram"}
_GEOMETRY_TOLERANCE = 1e-9
Point3D = tuple[float, float, float]
Rectangle3D = tuple[Point3D, Point3D, Point3D, Point3D]


@dataclass(frozen=True)
class SelectedMoldaje:
    """Resultado de la secuencia guiada de referencias.

    ``rectangles`` conserva el orden de ``elements``. ``candidate`` queda
    reservado para que el servicio cree la zapata sólo después de contrastar
    la escala con el JSON; ``INSUNITS`` por sí solo no prueba la escala real.
    """

    rectangles: dict[str, Rectangle3D]
    insunits: int | None
    selection: str
    candidate: MoldajeCandidate | None = None
    error: str | None = None
    reference_modes: dict[str, str] = field(default_factory=dict)

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


def _normalise_elements(
    elements: Iterable[Mapping[str, object]],
) -> tuple[tuple[str, str, str], ...]:
    result: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for raw in elements:
        if not isinstance(raw, Mapping):
            raise TypeError("Cada elemento debe contener key y label.")
        key = _protocol_value(raw.get("key"), "La clave del elemento")
        label = str(raw.get("label") or "").strip()
        mode = str(raw.get("reference_mode") or "rectangle").strip().lower()
        if not key or not _KEY_RE.fullmatch(key):
            raise ValueError(f"Clave de elemento no permitida: {key!r}.")
        if not label:
            raise ValueError(f"El elemento {key!r} no tiene etiqueta.")
        if mode not in _REFERENCE_MODES:
            raise ValueError(
                f"Modo de referencia no permitido para {key!r}: {mode!r}. "
                "Usa rectangle o parallelogram."
            )
        folded = key.casefold()
        if folded in seen:
            raise ValueError(f"La secuencia repite el elemento {key!r}.")
        seen.add(folded)
        result.append((key, label, mode))
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

    Los rectángulos usan ``getpoint`` seguido de ``getcorner``. Los
    paralelogramos usan tres ``getpoint`` consecutivos. Una cancelación o una
    referencia degenerada invalida la secuencia completa: no se publican
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
        f'("{_lisp_string(key)}" "{_lisp_string(label)}" "{mode.upper()}")'
        for key, label, mode in sequence
    )
    out = _lisp_string(path)
    partial = _lisp_string(f"{path}.part")
    prompt_instance = _lisp_string(instance or "seleccionada")
    prompt_view = _lisp_string(view or "actual")
    protocol_keys = ";".join(key for key, _label, _mode in sequence)

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
(defun sincal:length2 (vector)
  (+ (* (car vector) (car vector)) (* (cadr vector) (cadr vector)))
)
(defun sincal:cross2 (first second)
  (- (* (car first) (cadr second)) (* (cadr first) (car second)))
)
(defun sincal:valid-parallelogram-p (first second third / top side cross)
  (setq top (mapcar '- second first)
        side (mapcar '- third second)
        cross (sincal:cross2 top side))
  (and first second third
       (equal (caddr first) (caddr second) 0.000000001)
       (equal (caddr second) (caddr third) 0.000000001)
       (> (sincal:length2 top) 0.000000000000000001)
       (> (sincal:length2 side) 0.000000000000000001)
       (< cross -0.000000000001))
)
(defun sincal:safe-getpoint (message / result)
  (setq result (vl-catch-all-apply 'getpoint (list message)))
  (if (vl-catch-all-error-p result) nil result)
)
(defun sincal:safe-getpoint-from (base message / result)
  (setq result (vl-catch-all-apply 'getpoint (list base message)))
  (if (vl-catch-all-error-p result) nil result)
)
(defun sincal:safe-getcorner (first message / result)
  (setq result (vl-catch-all-apply 'getcorner (list first message)))
  (if (vl-catch-all-error-p result) nil result)
)
(defun c:SINCAL-SELECCIONAR-MOLDAJE (/ *error* tmp-path out state failure references item key label mode first second third first-wcs second-wcs third-wcs)
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
    (if message (princ (strcat "\\n[SINCAL] Selección interrumpida: " message)))
    (princ)
  )
  (setq state "OK" failure "" references '())
  (foreach item '({lisp_elements})
    (if (= state "OK")
      (progn
        (setq key (car item) label (cadr item) mode (caddr item))
        (setq first
          (sincal:safe-getpoint
            (strcat "\\n[SINCAL] " label " — vista {prompt_view}, {prompt_instance}: marque la esquina SUPERIOR IZQUIERDA: ")))
        (if (not first)
          (setq state "CANCELLED" failure (strcat "Cancelado en " key "."))
          (if (= mode "PARALLELOGRAM")
            (progn
              (setq second
                (sincal:safe-getpoint-from first
                  (strcat "\\n[SINCAL] " label ": marque la esquina SUPERIOR DERECHA: ")))
              (if (not second)
                (setq state "CANCELLED" failure (strcat "Cancelado en " key " antes del segundo punto."))
                (progn
                  (setq third
                    (sincal:safe-getpoint-from second
                      (strcat "\\n[SINCAL] " label ": marque la esquina INFERIOR DERECHA: ")))
                  (if (not third)
                    (setq state "CANCELLED" failure (strcat "Cancelado en " key " antes del tercer punto."))
                    (progn
                      (setq first-wcs (trans first 1 0)
                            second-wcs (trans second 1 0)
                            third-wcs (trans third 1 0))
                      (if (sincal:valid-parallelogram-p first-wcs second-wcs third-wcs)
                        (setq references
                          (append references (list (list mode key first-wcs second-wcs third-wcs))))
                        (setq state "INVALID"
                              failure (strcat key ": los tres puntos no forman un paralelogramo válido en orden superior-izquierdo, superior-derecho, inferior-derecho."))
                      )
                    )
                  )
                )
              )
            )
            (progn
              (setq second
                (sincal:safe-getcorner first
                  (strcat "\\n[SINCAL] " label ": marque la esquina INFERIOR DERECHA: ")))
              (if (not second)
                (setq state "CANCELLED" failure (strcat "Cancelado en " key "."))
                (progn
                  (setq first-wcs (trans first 1 0)
                        second-wcs (trans second 1 0))
                  (if (sincal:valid-rectangle-p first-wcs second-wcs)
                    (setq references
                      (append references (list (list mode key first-wcs second-wcs))))
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
    (foreach item references
      (if (= (car item) "PARALLELOGRAM")
        (write-line
          (strcat "PARALLELOGRAM|" (cadr item) "|"
                  (sincal:point-text (caddr item)) "|"
                  (sincal:point-text (cadddr item)) "|"
                  (sincal:point-text (car (cddddr item)))) out)
        (write-line
          (strcat "RECTANGLE|" (cadr item) "|"
                  (sincal:point-text (caddr item)) "|"
                  (sincal:point-text (cadddr item))) out)
      )
    )
    (write-line (strcat "META|ERROR|" failure) out)
  )
  (close out)
  (setq out nil)
  (if (findfile "{out}") (vl-file-delete "{out}"))
  (vl-file-rename tmp-path "{out}")
  (if (= state "OK")
    (princ "\\n[SINCAL] Referencias registradas. Vuelva a SINCAL.")
    (princ "\\n[SINCAL] No se registró ninguna referencia. Repita la selección desde SINCAL."))
  (princ)
)'''


def _parse_point(value: str, key: str) -> Point3D:
    try:
        coordinates = tuple(float(item.strip()) for item in value.split(";"))
    except ValueError as exc:
        raise ValueError(f"La referencia {key!r} contiene coordenadas no numéricas.") from exc
    if len(coordinates) != 3 or not all(isfinite(number) for number in coordinates):
        raise ValueError(f"La referencia {key!r} debe contener puntos WCS XYZ finitos.")
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


def _parallelogram(
    first: Point3D,
    second: Point3D,
    third: Point3D,
    key: str,
) -> Rectangle3D:
    if not (
        isclose(first[2], second[2], rel_tol=1e-12, abs_tol=_GEOMETRY_TOLERANCE)
        and isclose(second[2], third[2], rel_tol=1e-12, abs_tol=_GEOMETRY_TOLERANCE)
    ):
        raise ValueError(f"El paralelogramo {key!r} no pertenece a un plano XY único.")

    top = (second[0] - first[0], second[1] - first[1])
    side = (third[0] - second[0], third[1] - second[1])
    top_length = hypot(*top)
    side_length = hypot(*side)
    if top_length <= _GEOMETRY_TOLERANCE or side_length <= _GEOMETRY_TOLERANCE:
        raise ValueError(f"El paralelogramo {key!r} es degenerado: dos puntos consecutivos coinciden.")
    cross = top[0] * side[1] - top[1] * side[0]
    cross_tolerance = max(
        _GEOMETRY_TOLERANCE ** 2,
        top_length * side_length * _GEOMETRY_TOLERANCE,
    )
    if abs(cross) <= cross_tolerance:
        raise ValueError(f"El paralelogramo {key!r} es degenerado: sus tres puntos son colineales.")
    if cross > 0:
        raise ValueError(
            f"El paralelogramo {key!r} tiene el orden contrario; marca superior izquierda, "
            "superior derecha e inferior derecha."
        )

    fourth = (
        first[0] + third[0] - second[0],
        first[1] + third[1] - second[1],
        first[2] + third[2] - second[2],
    )
    if not all(isfinite(value) for value in fourth):
        raise ValueError(f"El paralelogramo {key!r} produce un cuarto vértice no finito.")
    return (first, second, third, fourth)


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
    """Lee la secuencia y devuelve contornos WCS de cuatro puntos sin escala.

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
    raw_references: list[tuple[str, str, tuple[Point3D, ...]]] = []
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
                raise ValueError(f"El resultado repite la referencia {key!r}.")
            seen_keys.add(folded)
            raw_references.append((
                "rectangle",
                key,
                (_parse_point(parts[2], key), _parse_point(parts[3], key)),
            ))
        elif record == "PARALLELOGRAM" and len(parts) == 5:
            key = parts[1].strip()
            if not key or not _KEY_RE.fullmatch(key):
                raise ValueError(f"Clave de referencia no permitida: {key!r}.")
            folded = key.casefold()
            if folded in seen_keys:
                raise ValueError(f"El resultado repite la referencia {key!r}.")
            seen_keys.add(folded)
            raw_references.append((
                "parallelogram",
                key,
                (
                    _parse_point(parts[2], key),
                    _parse_point(parts[3], key),
                    _parse_point(parts[4], key),
                ),
            ))
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
        if raw_references:
            raise ValueError("Una secuencia fallida no puede publicar referencias parciales.")
        return SelectedMoldaje({}, insunits, selection, None, error, {})
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
    if len(raw_references) != expected:
        raise ValueError(
            f"La selección está incompleta: se esperaban {expected} referencias y llegaron "
            f"{len(raw_references)}."
        )
    received_keys = tuple(key for _mode, key, _points in raw_references)
    if tuple(key.casefold() for key in received_keys) != tuple(
        key.casefold() for key in expected_keys
    ):
        raise ValueError("Las referencias no corresponden a la secuencia de elementos solicitada.")

    rectangles: dict[str, Rectangle3D] = {}
    reference_modes: dict[str, str] = {}
    for mode, key, points in raw_references:
        if mode == "parallelogram":
            rectangles[key] = _parallelogram(points[0], points[1], points[2], key)
        else:
            rectangles[key] = _rectangle(points[0], points[1], key)
        reference_modes[key] = mode
    return SelectedMoldaje(
        rectangles, insunits, selection, None, None, reference_modes,
    )
