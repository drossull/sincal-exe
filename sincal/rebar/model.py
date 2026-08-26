"""Modelo paramétrico y auditable de armaduras de zapata.

Cada barra física se calcula una vez; sus apariciones en FR, AA, BB, CC y EE
son representaciones y no vuelven a sumar acero. La geometría usa metros y
los largos de fabricación se entregan en centímetros enteros.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Mapping

DENSIDAD_ACERO_KG_M3 = 7850.0
VISTAS_ZAPATA = ("FR", "AA", "BB", "CC", "DD", "EE")
CAPAS_ZAPATA = tuple(f"{vista}_ZAP" for vista in VISTAS_ZAPATA)
DIAMETROS_DISPONIBLES_MM = (12, 16, 18, 22, 25, 28, 32, 36)
LARGOS_TRASLAPO_CM = {12: 80, 16: 110, 18: 120, 22: 150, 25: 170, 28: 190, 32: 220, 36: 250}
LARGO_COMERCIAL_CM = 1200.0
_MARCA_RE = re.compile(r"^[1-9][0-9]*(?:-[A-Z0-9]+)?$", re.IGNORECASE)


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

    def validate(self):
        if not self.enabled:
            return ()
        issues = []
        for label, mark in (("marca", self.mark), ("continuación", self.continuation_mark), ("terminal", self.terminal_mark)):
            if mark and not _MARCA_RE.match(mark.strip()):
                issues.append(ValidationIssue("error", f"{label.title()} inválida para {self.label}: '{mark}'."))
        if self.diameter_mm not in DIAMETROS_DISPONIBLES_MM:
            issues.append(ValidationIssue("error", f"El diámetro de {self.label} no tiene bloque fiXX disponible."))
        if self.automatic and self.spacing_cm <= 0:
            issues.append(ValidationIssue("error", f"El espaciamiento de {self.label} debe ser mayor que cero."))
        if self.hook_cm < 0:
            issues.append(ValidationIssue("error", f"El gancho de {self.label} no puede ser negativo."))
        if self.origin not in ("inicio", "final"):
            issues.append(ValidationIssue("error", f"Origen inválido para {self.label}."))
        return tuple(issues)


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

    @property
    def area_m2(self):
        return math.pi * (self.diameter_mm / 2000.0) ** 2

    @property
    def kg_steel(self):
        return self.quantity * (self.unit_length_cm / 100.0) * self.area_m2 * DENSIDAD_ACERO_KG_M3


@dataclass(frozen=True)
class ZapataSchedule:
    marks: tuple[RebarMark, ...]
    issues: tuple[ValidationIssue, ...]

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


def distribution_positions_cm(span_cm, spacing_cm, origin="inicio"):
    """Separa fijo; agrega barra final sólo cuando el residuo es al menos 10 cm."""
    if span_cm < 0 or spacing_cm <= 0:
        return ()
    positions = [index * spacing_cm for index in range(math.floor((span_cm + 1e-9) / spacing_cm) + 1)]
    if span_cm - positions[-1] >= 10.0 - 1e-9:
        positions.append(span_cm)
    if origin == "final":
        positions = [span_cm - value for value in reversed(positions)]
    return tuple(round(value, 9) for value in positions)


def default_zapata_rules():
    return (
        RebarRule("mesh_x", "Malla 1–2 · superior e inferior", "1", 22, 20, 0,
                  "superior e inferior", "X", continuation_mark="2", terminal_mark="2-A", placement_multiplier=2),
        RebarRule("mesh_y", "Fierro 3 · superior e inferior", "3", 22, 20, 0,
                  "superior e inferior", "Y", placement_multiplier=2),
        RebarRule("suple", "Suple 3-A · solo superior", "3-A", 16, 20, 0,
                  "superior", "Y", enabled=False),
        RebarRule("lateral_x", "Laterales 4–5 · ambas caras", "4", 16, 20, 0,
                  "lateral", "X", continuation_mark="5", terminal_mark="5-A", placement_multiplier=2),
        RebarRule("lateral_y", "Laterales 6 · ambos extremos", "6", 16, 20, 0,
                  "lateral", "Y", placement_multiplier=2),
    )


_VIEW_NOTES = {
    "mesh_x": {"FR": "longitud real", "AA": "bloque transversal", "BB": "bloque transversal", "CC": "bloque transversal", "EE": "longitud real; representa malla superior"},
    "mesh_y": {"FR": "bloque transversal", "AA": "longitud real", "BB": "longitud real", "CC": "longitud real", "EE": "longitud real; representa malla superior"},
    "suple": {"FR": "bloque transversal", "AA": "longitud real", "BB": "longitud real", "CC": "longitud real", "EE": "longitud real"},
    "lateral_x": {"AA": "círculo transversal", "BB": "círculo transversal", "CC": "círculo transversal", "EE": "longitud real"},
    "lateral_y": {"FR": "círculo transversal", "EE": "longitud real"},
}


def _developed_two_hook_length_cm(run_cm, cover_cm, diameter_mm, hook_cm):
    radius = bend_radius_cm(diameter_mm)
    axis_cover = cover_cm + diameter_mm / 20.0
    tangent_run = run_cm - 2.0 * (axis_cover + radius)
    if tangent_run <= 0:
        return 0.0
    return tangent_run + 2.0 * (hook_cm + math.pi * radius / 2.0)


def _append_mark(marks, rule, mark, quantity, length_cm, hook_count, role):
    rounded = float(math.ceil(length_cm - 1e-9))
    notes = dict(_VIEW_NOTES[rule.key])
    marks.append(RebarMark(
        rule.key, mark, "Zapata", rule.label, rule.diameter_mm, quantity,
        rounded, quantity * rounded, tuple(notes), notes, hook_count,
        bend_radius_cm(rule.diameter_mm), role,
    ))


def _append_split_group(marks, issues, rule, placements, developed_cm):
    if developed_cm <= LARGO_COMERCIAL_CM + 1e-9:
        _append_mark(marks, rule, rule.mark, placements, developed_cm, 2, "completa")
        return
    try:
        lap_cm = lap_length_cm(rule.diameter_mm)
    except ValueError as error:
        issues.append(ValidationIssue("error", str(error)))
        return
    if not rule.continuation_mark:
        issues.append(ValidationIssue("error", f"{rule.label} supera 12 m y no tiene marca de continuación."))
        return
    effective_piece = LARGO_COMERCIAL_CM - lap_cm
    piece_count = max(2, math.ceil((developed_cm - lap_cm) / effective_piece))
    terminal = developed_cm - LARGO_COMERCIAL_CM * (piece_count - 1) + lap_cm * (piece_count - 1)
    _append_mark(marks, rule, rule.mark, placements, LARGO_COMERCIAL_CM, 1, "inicial")
    if piece_count == 2:
        _append_mark(marks, rule, rule.continuation_mark, placements, terminal, 1, "terminal")
    else:
        _append_mark(marks, rule, rule.continuation_mark, placements * (piece_count - 2), LARGO_COMERCIAL_CM, 0, "intermedia")
        _append_mark(marks, rule, rule.terminal_mark or f"{rule.continuation_mark}-A", placements, terminal, 1, "terminal")


def build_zapata_schedule(geometry, cover, rules):
    """Calcula las marcas 1–6 y 3-A sin duplicarlas por vista."""
    issues = list(geometry.validate()) + list(cover.validate(geometry))
    marks = []
    active = {rule.key: rule for rule in rules if rule.enabled}
    for rule in rules:
        issues.extend(rule.validate())
    if any(issue.severity == "error" for issue in issues):
        return ZapataSchedule((), tuple(issues))

    length_cm, width_cm, height_cm = geometry.largo_m * 100, geometry.ancho_m * 100, geometry.alto_m * 100
    cover_cm = cover.lateral_m * 100
    default_hook = automatic_hook_cm(height_cm)
    mesh_x, mesh_y = active.get("mesh_x"), active.get("mesh_y")

    for rule in rules:
        if not rule.enabled:
            continue
        hook_cm = rule.hook_cm or default_hook
        if rule.key in ("mesh_x", "suple"):
            reference = mesh_y or rule
            span = length_cm - 2 * (cover_cm + reference.diameter_mm / 20 + bend_radius_cm(reference.diameter_mm))
        elif rule.key == "mesh_y":
            reference = mesh_x or rule
            span = width_cm - 2 * (cover_cm + reference.diameter_mm / 20 + bend_radius_cm(reference.diameter_mm))
        else:
            reference = mesh_x or rule
            span = height_cm - (cover.inferior_m + cover.superior_m) * 100 - reference.diameter_mm / 10
        placements = len(distribution_positions_cm(span, rule.spacing_cm, rule.origin)) * rule.placement_multiplier
        if placements <= 0:
            issues.append(ValidationIssue("error", f"No existe rango útil para distribuir {rule.label}."))
            continue
        run = width_cm if rule.direction == "X" else length_cm
        developed = _developed_two_hook_length_cm(run, cover_cm, rule.diameter_mm, hook_cm)
        if developed <= 0:
            issues.append(ValidationIssue("error", f"La geometría no permite construir {rule.label}."))
        elif rule.continuation_mark:
            _append_split_group(marks, issues, rule, placements, developed)
        elif developed > LARGO_COMERCIAL_CM:
            issues.append(ValidationIssue("error", f"{rule.label} desarrolla {math.ceil(developed):g} cm y requiere empalme."))
        else:
            _append_mark(marks, rule, rule.mark, placements, developed, 2, "completa")
    return ZapataSchedule(tuple(marks), tuple(issues))
