"""Modelo paramétrico y auditable de armaduras de zapata.

Cada barra física se calcula una vez; sus apariciones en FR, AA, BB, CC y FF
son representaciones y no vuelven a sumar acero. La geometría usa metros y
los largos de fabricación se entregan en centímetros enteros.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Mapping

DENSIDAD_ACERO_KG_M3 = 7850.0
VISTAS_ZAPATA = ("FR", "AA", "BB", "CC", "FF")
CAPAS_ZAPATA = tuple(f"{vista}_ZAP" for vista in VISTAS_ZAPATA)
DIAMETROS_DISPONIBLES_MM = (12, 16, 18, 22, 25, 28, 32, 36)
LARGOS_TRASLAPO_CM = {12: 80, 16: 110, 18: 120, 22: 150, 25: 170, 28: 190, 32: 220, 36: 250}
LARGO_COMERCIAL_CM = 1200.0
# Same contract as SCM:ValidMark: digits with an optional ASCII letter suffix.
_MARCA_RE = re.compile(r"[0-9]+[A-Z]*", re.IGNORECASE | re.ASCII)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    message: str


@dataclass(frozen=True)
class ZapataGeometry:
    largo_m: float
    ancho_m: float
    alto_m: float
    esviaje_grados: float = 0.0

    @classmethod
    def from_centimetres(cls, largo_cm, ancho_cm, alto_cm, esviaje_grados=0.0):
        return cls(largo_cm / 100.0, ancho_cm / 100.0, alto_cm / 100.0, esviaje_grados)

    def validate(self):
        issues = []
        for label, value in (("Largo", self.largo_m), ("Ancho", self.ancho_m), ("Alto", self.alto_m)):
            if value <= 0:
                issues.append(ValidationIssue("error", f"{label} de zapata debe ser mayor que cero."))
        if abs(self.esviaje_grados) >= 90:
            issues.append(ValidationIssue("error", "El esviaje debe estar entre -90° y 90°."))
        return tuple(issues)


@dataclass(frozen=True)
class Cover:
    """Recubrimientos libres medidos hasta la superficie exterior del fierro."""
    inferior_m: float
    superior_m: float
    lateral_m: float

    @classmethod
    def from_centimetres(cls, inferior_cm, superior_cm, lateral_cm):
        return cls(inferior_cm / 100.0, superior_cm / 100.0, lateral_cm / 100.0)

    def validate(self, geometry):
        issues = []
        for label, value in (("inferior", self.inferior_m), ("superior", self.superior_m), ("lateral", self.lateral_m)):
            if value < 0:
                issues.append(ValidationIssue("error", f"El recubrimiento {label} no puede ser negativo."))
        if 2 * self.lateral_m >= min(geometry.largo_m, geometry.ancho_m):
            issues.append(ValidationIssue("error", "El recubrimiento lateral no deja espacio útil para barras."))
        if self.inferior_m + self.superior_m >= geometry.alto_m:
            issues.append(ValidationIssue("error", "Los recubrimientos superior e inferior superan el alto útil."))
        return tuple(issues)


@dataclass(frozen=True)
class RemovedPiece:
    """One explicit removal, bound to the selected piece's actual geometry."""
    id: str
    signature: str


def parse_removed_pieces(values, key):
    """Validate persisted removals without accepting arbitrary piece identities.

    The ID identifies one manufactured piece, not an entire family or a run
    of overlapping pieces. Its geometry signature is checked by the assembly
    after generating the current parameters.
    """
    if key not in ("mesh_x", "mesh_y", "suple", "lateral_x", "lateral_y"):
        raise ValueError("Familia desconocida para los fierros eliminados.")
    if not isinstance(values, (tuple, list)) or len(values) > 50000:
        raise ValueError("La lista de fierros eliminados no es válida.")
    location = r"(?:-1|1)" if key.startswith("lateral_") else r"(?:superior|inferior)"
    pattern = re.compile(re.escape(key) + ":" + location + r":[0-9]{1,6}:[0-9]{1,6}")
    result, seen = [], set()
    for value in values:
        if isinstance(value, RemovedPiece):
            identity, signature = value.id, value.signature
        elif isinstance(value, Mapping) and set(value) == {"id", "signature"}:
            identity, signature = value["id"], value["signature"]
        else:
            raise ValueError("Cada fierro eliminado debe conservar su identificador y firma.")
        if not isinstance(identity, str) or not pattern.fullmatch(identity):
            raise ValueError("El identificador del fierro eliminado no corresponde a su familia.")
        if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", signature):
            raise ValueError("La firma del fierro eliminado no es válida.")
        if identity in seen:
            raise ValueError("Un fierro figura eliminado más de una vez.")
        seen.add(identity)
        result.append(RemovedPiece(identity, signature.lower()))
    return tuple(result)


@dataclass(frozen=True)
class RebarRule:
    key: str
    label: str
    mark: str
    diameter_mm: float
    spacing_cm: float
    hook_cm: float
    level: str
    direction: str
    enabled: bool = True
    automatic: bool = True
    continuation_mark: str = ""
    terminal_mark: str = ""
    placement_multiplier: int = 1
    origin: str = "inicio"
    first_piece_cm: float = 0.0
    removed_pieces: tuple[RemovedPiece, ...] = ()

    def validate(self):
        issues = []
        try:
            parse_removed_pieces(self.removed_pieces, self.key)
        except ValueError as error:
            issues.append(ValidationIssue("error", str(error)))
        if not self.enabled:
            return tuple(issues)
        for label, mark in (("marca", self.mark), ("continuación", self.continuation_mark), ("terminal", self.terminal_mark)):
            if not isinstance(mark, str) or (
                    (label == "marca" or mark) and not _MARCA_RE.fullmatch(mark)):
                issues.append(ValidationIssue("error", f"{label.title()} inválida para {self.label}: '{mark}'."))
        if self.diameter_mm not in DIAMETROS_DISPONIBLES_MM:
            issues.append(ValidationIssue("error", f"El diámetro de {self.label} no tiene bloque fiXX disponible."))
        if self.automatic and self.spacing_cm <= 0:
            issues.append(ValidationIssue("error", f"El espaciamiento de {self.label} debe ser mayor que cero."))
        if self.hook_cm < 0:
            issues.append(ValidationIssue("error", f"El gancho de {self.label} no puede ser negativo."))
        if (isinstance(self.first_piece_cm, bool)
                or not isinstance(self.first_piece_cm, (int, float))
                or not math.isfinite(self.first_piece_cm)
                or not 0 <= self.first_piece_cm <= LARGO_COMERCIAL_CM):
            issues.append(ValidationIssue("error", f"El largo del primer fierro de {self.label} debe estar entre 0 y 1200 cm; 0 es automático."))
        elif self.first_piece_cm and not self.continuation_mark:
            issues.append(ValidationIssue("error", f"{self.label} no tiene un reparto de empalmes definido para ajustar el primer fierro."))
        if self.origin not in ("inicio", "final"):
            issues.append(ValidationIssue("error", f"Origen inválido para {self.label}."))
        return tuple(issues)


@dataclass(frozen=True)
class RebarLengthVariant:
    """A developed cut length and its count within one linked mark."""
    length_cm: float
    quantity: int


@dataclass(frozen=True)
class RebarMark:
    key: str
    mark: str
    element: str
    location: str
    diameter_mm: float
    quantity: int
    unit_length_cm: float
    total_length_cm: float
    views: tuple[str, ...]
    projection_notes: Mapping[str, str]
    hook_count: int = 0
    bend_radius_cm: float = 0.0
    piece_role: str = "completa"
    length_variants: tuple[RebarLengthVariant, ...] = ()
    shape_data: Mapping | None = None

    @property
    def area_m2(self):
        return math.pi * (self.diameter_mm / 2000.0) ** 2

    @property
    def kg_steel(self):
        return (self.total_length_cm / 100.0) * self.area_m2 * DENSIDAD_ACERO_KG_M3


@dataclass(frozen=True)
class ZapataSchedule:
    marks: tuple[RebarMark, ...]
    issues: tuple[ValidationIssue, ...]
    # Local straight-axis intervals that retain both physical splice partners.
    # None keeps compatibility with older/manual schedule constructors.
    splice_laps_m: Mapping[str, tuple[tuple[float, float], ...]] | None = None

    @property
    def is_valid(self):
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def total_kg(self):
        return sum(mark.kg_steel for mark in self.marks)


def automatic_hook_cm(height_cm):
    """50 % del alto, mínimo 100 cm y redondeo superior cada 10 cm."""
    return max(100.0, math.ceil((height_cm * 0.5) / 10.0) * 10.0)


def bend_radius_cm(diameter_mm):
    return 3.0 * diameter_mm / 10.0


def lap_length_cm(diameter_mm):
    try:
        return float(LARGOS_TRASLAPO_CM[int(diameter_mm)])
    except (KeyError, ValueError) as error:
        raise ValueError(f"No existe traslapo definido para fi{diameter_mm:g}.") from error


def distribution_positions_cm(span_cm, spacing_cm, origin="inicio", *, include_endpoints=False,
                              minimum_spacing_cm=0.0):
    """Keep the regular pitch and optionally close at both exact endpoints.

    The default retains the existing 10 cm remainder rule for other callers.
    Footing distributions request both bend tangencies explicitly. If their
    final residue is smaller than a bar diameter, share the last full interval
    and the residue equally so parallel bars do not occupy the same space.
    """
    if span_cm < 0 or spacing_cm <= 0:
        return ()
    if include_endpoints and (not math.isfinite(minimum_spacing_cm) or minimum_spacing_cm < 0):
        raise ValueError("La separación mínima del reparto no es válida.")
    positions = [index * spacing_cm for index in range(math.floor((span_cm + 1e-9) / spacing_cm) + 1)]
    remainder = span_cm - positions[-1]
    if remainder >= 10.0 - 1e-9 or (include_endpoints and remainder > 1e-9):
        if include_endpoints and remainder < minimum_spacing_cm - 1e-9:
            if len(positions) < 2:
                raise ValueError("No caben los dos fierros extremos sin superponerse.")
            positions[-1] = (positions[-2] + span_cm) / 2
        positions.append(span_cm)
    if include_endpoints and any(b - a < minimum_spacing_cm - 1e-9
                                 for a, b in zip(positions, positions[1:])):
        raise ValueError("No cabe el cierre del reparto sin superponer fierros.")
    if origin == "final":
        positions = [span_cm - value for value in reversed(positions)]
    return tuple(round(value, 9) for value in positions)


def default_zapata_rules():
    return (
        RebarRule("mesh_x", "Malla 1–2 · superior e inferior", "1", 22, 20, 0,
                  "superior e inferior", "X", continuation_mark="2", terminal_mark="2A", placement_multiplier=2),
        RebarRule("mesh_y", "Fierro 3 · superior e inferior", "3", 22, 20, 0,
                  "superior e inferior", "Y", placement_multiplier=2),
        RebarRule("suple", "Suple 3A · solo superior", "3A", 16, 20, 0,
                  "superior", "Y", enabled=False),
        RebarRule("lateral_x", "Laterales 4–5 · ambas caras", "4", 16, 20, 0,
                  "lateral", "X", continuation_mark="5", terminal_mark="5A", placement_multiplier=2),
        RebarRule("lateral_y", "Laterales 6 · ambos extremos", "6", 16, 20, 0,
                  "lateral", "Y", placement_multiplier=2),
    )


_VIEW_NOTES = {
    "mesh_x": {"FR": "longitud real", "AA": "bloque transversal", "BB": "bloque transversal", "CC": "bloque transversal", "FF": "longitud real; representa malla superior"},
    "mesh_y": {"FR": "bloque transversal", "AA": "longitud real", "BB": "longitud real", "CC": "longitud real", "FF": "longitud real; representa malla superior"},
    "suple": {"FR": "bloque transversal", "AA": "longitud real", "BB": "longitud real", "CC": "longitud real", "FF": "longitud real"},
    "lateral_x": {"AA": "círculo transversal", "BB": "círculo transversal", "CC": "círculo transversal", "FF": "longitud real"},
    "lateral_y": {"FR": "círculo transversal", "FF": "longitud real"},
}


def build_zapata_schedule(geometry, cover, rules):
    """Aggregate the same physical pieces used by details and every view."""
    from .assembly import build_footing_assembly
    return build_footing_assembly(geometry, cover, rules).schedule
