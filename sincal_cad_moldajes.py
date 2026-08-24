"""Contrato de lectura entre el detector AutoLISP y la revisión estructural."""

from __future__ import annotations

from dataclasses import dataclass

from sincal_rebar_model import CAPAS_ZAPATA


@dataclass(frozen=True)
class MoldajeCandidate:
    layer: str
    handle: str
    status: str
    vertex_count: int
    area_m2: float

    @property
    def is_valid(self) -> bool:
        return self.status == "OK" and self.vertex_count >= 3 and self.area_m2 > 0

    @property
    def label(self) -> str:
        return f"{self.handle} · {self.vertex_count} vértices · {self.area_m2:.2f} m² · {self.status}"


@dataclass(frozen=True)
class MoldajeDetection:
    insunits: int | None
    candidates: tuple[MoldajeCandidate, ...]

    def for_layer(self, layer: str) -> tuple[MoldajeCandidate, ...]:
        return tuple(candidate for candidate in self.candidates if candidate.layer == layer)

    @property
    def uses_metres(self) -> bool:
        return self.insunits == 6


def parse_moldaje_detection(text: str) -> MoldajeDetection:
    """Lee el formato de texto sencillo emitido por SINCAL-DETECTAR-ZAPATA."""
    insunits = None
    candidates = []
    for raw_line in text.splitlines():
        parts = [part.strip() for part in raw_line.split("|")]
        if not parts or not parts[0]:
            continue
        if parts[0] == "META" and len(parts) == 3 and parts[1] == "INSUNITS":
            try:
                insunits = int(parts[2])
            except ValueError:
                insunits = None
        elif parts[0] == "CANDIDATE" and len(parts) == 6:
            layer, handle, status = parts[1:4]
            if layer not in CAPAS_ZAPATA:
                continue
            try:
                candidates.append(MoldajeCandidate(
                    layer=layer,
                    handle=handle.upper(),
                    status=status.upper(),
                    vertex_count=int(parts[4]),
                    area_m2=float(parts[5]),
                ))
            except ValueError:
                continue
    return MoldajeDetection(insunits=insunits, candidates=tuple(candidates))
