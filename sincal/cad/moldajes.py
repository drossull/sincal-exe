"""Contrato de lectura entre los detectores CAD y la revisión estructural.

El formato V1 de zapatas sigue siendo válido. Los detectores generales pueden
añadir registros ``CONTEXT``, ``GEOMETRY`` y ``BULGES`` sin alterar la línea
``CANDIDATE`` que ya consumen las versiones publicadas de SINCAL.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping

from sincal.rebar.model import CAPAS_ZAPATA


@dataclass(frozen=True)
class MoldajeContext:
    """Identidad funcional del conjunto que se está leyendo en CAD."""

    element: str = ""
    instance: str = ""
    view: str = ""


@dataclass(frozen=True)
class MoldajeCandidate:
    layer: str
    handle: str
    status: str
    vertex_count: int
    area_m2: float
    vertices: tuple[tuple[float, float], ...] = ()
    closed: bool | None = None
    has_arcs: bool = False
    bulges: tuple[float, ...] = ()
    context: MoldajeContext = MoldajeContext()

    @property
    def is_valid(self) -> bool:
        """Conserva la validación V1 exigida por la zapata publicada."""
        return (
            self.status == "OK"
            and self.closed is not False
            and not self.has_arcs
            and self.vertex_count >= 3
            and self.area_m2 > 0
        )

    def is_usable(self, *, allow_open: bool = False, allow_arcs: bool = False) -> bool:
        """Valida el candidato según el contrato geométrico de un elemento.

        Los contornos abiertos no requieren área, pero sí al menos dos
        vértices. Los cerrados conservan el mínimo de tres vértices y un área
        positiva. ``MISSING`` e ``INVALID`` nunca son utilizables.
        """
        if not self.handle or self.status in {"MISSING", "INVALID", "ERROR"}:
            return False
        if self.has_arcs and not allow_arcs:
            return False
        if self.closed is False:
            return allow_open and self.vertex_count >= 2
        if self.closed is True:
            return self.vertex_count >= 3 and self.area_m2 > 0
        return self.is_valid

    @property
    def contour_kind(self) -> str:
        if self.closed is True:
            return "closed"
        if self.closed is False:
            return "open"
        return "unknown"

    @property
    def label(self) -> str:
        if self.closed is True and not self.has_arcs:
            return f"{self.handle} · {self.vertex_count} vértices · {self.area_m2:.2f} m² · {self.status}"
        shape = "abierta" if self.closed is False else "cerrada" if self.closed else "sin cierre"
        curve = " · arcos" if self.has_arcs else ""
        return (
            f"{self.handle} · {self.vertex_count} vértices · "
            f"{self.area_m2:.2f} m² · {shape}{curve} · {self.status}"
        )


@dataclass(frozen=True)
class MoldajeDetection:
    insunits: int | None
    candidates: tuple[MoldajeCandidate, ...]
    context: MoldajeContext = MoldajeContext()
    allowed_layers: tuple[str, ...] = ()
    protocol_version: int = 1

    def for_layer(self, layer: str) -> tuple[MoldajeCandidate, ...]:
        wanted = layer.strip().upper()
        return tuple(candidate for candidate in self.candidates if candidate.layer.upper() == wanted)

    def for_context(
        self, *, element: str | None = None, instance: str | None = None,
        view: str | None = None,
    ) -> tuple[MoldajeCandidate, ...]:
        """Filtra candidatos sin exigir que todos los campos estén presentes."""
        expected = (element, instance, view)
        return tuple(
            candidate for candidate in self.candidates
            if all(
                wanted is None or actual.casefold() == wanted.casefold()
                for actual, wanted in zip(
                    (candidate.context.element, candidate.context.instance, candidate.context.view),
                    expected,
                )
            )
        )

    @property
    def uses_metres(self) -> bool:
        return self.insunits == 6


def _normalise_context(value: MoldajeContext | Mapping[str, object] | None) -> MoldajeContext:
    if isinstance(value, MoldajeContext):
        return value
    if isinstance(value, Mapping):
        return MoldajeContext(
            element=str(value.get("element", "") or "").strip(),
            instance=str(value.get("instance", "") or "").strip(),
            view=str(value.get("view", "") or "").strip(),
        )
    return MoldajeContext()


def _merge_context(base: MoldajeContext, override: MoldajeContext) -> MoldajeContext:
    """Los campos no vacíos del segundo contexto tienen precedencia."""
    return MoldajeContext(
        element=override.element or base.element,
        instance=override.instance or base.instance,
        view=override.view or base.view,
    )


def _parse_bool(value: str) -> bool:
    return value.strip().upper() in {"1", "TRUE", "T", "YES", "SI", "SÍ", "ARC"}


def _parse_closure(value: str) -> bool | None:
    normalised = value.strip().upper()
    if normalised in {"CLOSED", "CERRADA", "1", "TRUE", "T"}:
        return True
    if normalised in {"OPEN", "ABIERTA", "0", "FALSE", "NIL"}:
        return False
    return None


def _infer_shape(status: str) -> tuple[bool | None, bool]:
    normalised = status.upper()
    if normalised in {"OPEN", "OPEN_ARC", "ARC_OPEN"}:
        return False, "ARC" in normalised
    if normalised in {"OK", "ARC"}:
        return True, normalised == "ARC"
    return None, "ARC" in normalised


def _parse_float_list(value: str) -> tuple[float, ...]:
    if not value.strip():
        return ()
    return tuple(float(item) for item in value.split(";") if item.strip())


def parse_moldaje_detection(
    text: str,
    allowed_layers: Iterable[str] | None = None,
    *,
    context: MoldajeContext | Mapping[str, object] | None = None,
) -> MoldajeDetection:
    """Lee la salida de un detector de moldajes V1 o V2.

    ``allowed_layers`` permite que el catálogo estructural defina sus capas en
    tiempo de ejecución. Omitirlo conserva exactamente el alcance histórico de
    zapata. El contexto entregado por el llamador prevalece sobre el declarado
    en el archivo, evitando que una salida antigua cambie la instancia activa.

    Extensiones V2 reconocidas::

        META|ELEMENT|zapata
        META|INSTANCE|entrada
        META|VIEW|FR
        CONTEXT|FR_ZAP|1A2B|zapata|entrada|FR
        GEOMETRY|FR_ZAP|1A2B|CLOSED|0
        BULGES|FR_ZAP|1A2B|0;0.25;0;0
    """
    configured_layers = tuple(
        dict.fromkeys(layer.strip().upper() for layer in (allowed_layers or CAPAS_ZAPATA) if layer.strip())
    )
    allowed = set(configured_layers)
    supplied_context = _normalise_context(context)
    meta_context = MoldajeContext()
    insunits = None
    protocol_version = 1
    candidates: list[MoldajeCandidate] = []
    vertices_by_key: dict[tuple[str, str], tuple[tuple[float, float], ...]] = {}
    bulges_by_key: dict[tuple[str, str], tuple[float, ...]] = {}
    geometry_by_key: dict[tuple[str, str], tuple[bool | None, bool]] = {}
    context_by_key: dict[tuple[str, str], MoldajeContext] = {}

    for raw_line in text.splitlines():
        parts = [part.strip() for part in raw_line.split("|")]
        if not parts or not parts[0]:
            continue
        record = parts[0].upper()
        if record == "SINCAL_MOLDAJES_V2":
            protocol_version = 2
        elif record == "META" and len(parts) == 3:
            key, value = parts[1].upper(), parts[2]
            if key == "INSUNITS":
                try:
                    insunits = int(value)
                except ValueError:
                    insunits = None
            elif key == "ELEMENT":
                meta_context = replace(meta_context, element=value)
            elif key == "INSTANCE":
                meta_context = replace(meta_context, instance=value)
            elif key == "VIEW":
                meta_context = replace(meta_context, view=value)
        elif record == "CANDIDATE" and len(parts) == 6:
            layer, handle, status = parts[1].upper(), parts[2].upper(), parts[3].upper()
            if layer not in allowed:
                continue
            try:
                closed, has_arcs = _infer_shape(status)
                candidates.append(MoldajeCandidate(
                    layer=layer,
                    handle=handle,
                    status=status,
                    vertex_count=int(parts[4]),
                    area_m2=float(parts[5]),
                    closed=closed,
                    has_arcs=has_arcs,
                ))
            except ValueError:
                continue
        elif record == "VERTICES" and len(parts) == 4:
            key = (parts[1].upper(), parts[2].upper())
            try:
                points = tuple(
                    tuple(float(coordinate) for coordinate in point.split(","))
                    for point in parts[3].split(";") if point
                )
                if all(len(point) == 2 for point in points):
                    vertices_by_key[key] = points
            except ValueError:
                continue
        elif record == "BULGES" and len(parts) == 4:
            key = (parts[1].upper(), parts[2].upper())
            try:
                bulges_by_key[key] = _parse_float_list(parts[3])
            except ValueError:
                continue
        elif record == "GEOMETRY" and len(parts) >= 5:
            key = (parts[1].upper(), parts[2].upper())
            geometry_by_key[key] = (_parse_closure(parts[3]), _parse_bool(parts[4]))
        elif record == "CONTEXT" and len(parts) == 6:
            key = (parts[1].upper(), parts[2].upper())
            context_by_key[key] = MoldajeContext(parts[3], parts[4], parts[5])

    detection_context = _merge_context(meta_context, supplied_context)
    enriched = []
    for candidate in candidates:
        key = (candidate.layer.upper(), candidate.handle.upper())
        closed, has_arcs = geometry_by_key.get(key, (candidate.closed, candidate.has_arcs))
        candidate_context = _merge_context(detection_context, context_by_key.get(key, MoldajeContext()))
        candidate_context = _merge_context(candidate_context, supplied_context)
        bulges = bulges_by_key.get(key, ())
        enriched.append(replace(
            candidate,
            vertices=vertices_by_key.get(key, ()),
            closed=closed,
            has_arcs=has_arcs or any(abs(value) > 1e-12 for value in bulges),
            bulges=bulges,
            context=candidate_context,
        ))

    return MoldajeDetection(
        insunits=insunits,
        candidates=tuple(enriched),
        context=detection_context,
        allowed_layers=configured_layers,
        protocol_version=protocol_version,
    )
