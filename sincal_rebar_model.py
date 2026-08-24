"""Modelo paramétrico y auditable de fierros para SINCAL.

El módulo no dibuja CAD. Describe barras físicas, sus cantidades y cómo se
representan en las vistas. Esto impide cubicar dos veces una barra que aparece
en más de una sección del plano.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Mapping


DENSIDAD_ACERO_KG_M3 = 7850.0
VISTAS_ZAPATA = ("FR", "AA", "BB", "CC", "DD", "EE")
CAPAS_ZAPATA = tuple(f"{vista}_ZAP" for vista in VISTAS_ZAPATA)
_MARCA_RE = re.compile(r"^[1-9][0-9]*[a-z]?$", re.IGNORECASE)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    message: str


@dataclass(frozen=True)
class ZapataGeometry:
    """Dimensiones físicas de una zapata, siempre expresadas en metros."""

    largo_m: float
    ancho_m: float
    alto_m: float
    esviaje_grados: float = 0.0

    @classmethod
    def from_centimetres(
        cls, largo_cm: float, ancho_cm: float, alto_cm: float, esviaje_grados: float = 0.0
    ) -> "ZapataGeometry":
        return cls(largo_cm / 100.0, ancho_cm / 100.0, alto_cm / 100.0, esviaje_grados)

    def validate(self) -> tuple[ValidationIssue, ...]:
        issues = []
        for label, value in (("Largo", self.largo_m), ("Ancho", self.ancho_m), ("Alto", self.alto_m)):
            if value <= 0:
                issues.append(ValidationIssue("error", f"{label} de zapata debe ser mayor que cero."))
        if abs(self.esviaje_grados) >= 90:
            issues.append(ValidationIssue("error", "El esviaje debe estar entre -90° y 90°."))
        return tuple(issues)


@dataclass(frozen=True)
class Cover:
    """Recubrimientos libres, siempre expresados en metros."""

    inferior_m: float
    superior_m: float
    lateral_m: float

    @classmethod
    def from_centimetres(cls, inferior_cm: float, superior_cm: float, lateral_cm: float) -> "Cover":
        return cls(inferior_cm / 100.0, superior_cm / 100.0, lateral_cm / 100.0)

    def validate(self, geometry: ZapataGeometry) -> tuple[ValidationIssue, ...]:
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
    """Regla editable de un grupo físico de barras."""

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

    def validate(self) -> tuple[ValidationIssue, ...]:
        if not self.enabled:
            return ()
        issues = []
        if not _MARCA_RE.match(self.mark.strip()):
            issues.append(ValidationIssue("error", f"Marca inválida para {self.label}: '{self.mark}'."))
        if self.diameter_mm <= 0:
            issues.append(ValidationIssue("error", f"El diámetro de {self.label} debe ser mayor que cero."))
        if self.automatic and self.spacing_cm <= 0:
            issues.append(ValidationIssue("error", f"El espaciamiento de {self.label} debe ser mayor que cero."))
        if self.hook_cm < 0:
            issues.append(ValidationIssue("error", f"El gancho de {self.label} no puede ser negativo."))
        return tuple(issues)


@dataclass(frozen=True)
class RebarMark:
    """Una familia física de barras lista para revisar y cubicar."""

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

    @property
    def area_m2(self) -> float:
        return math.pi * (self.diameter_mm / 2000.0) ** 2

    @property
    def kg_steel(self) -> float:
        return self.quantity * (self.unit_length_cm / 100.0) * self.area_m2 * DENSIDAD_ACERO_KG_M3


@dataclass(frozen=True)
class ZapataSchedule:
    marks: tuple[RebarMark, ...]
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def total_kg(self) -> float:
        return sum(mark.kg_steel for mark in self.marks)


def default_zapata_rules() -> tuple[RebarRule, ...]:
    """Reglas iniciales. Los valores deben revisarse antes de generar CAD."""
    return (
        RebarRule("sup_long", "Malla superior longitudinal", "1", 22, 15, 0, "superior", "longitudinal"),
        RebarRule("sup_trans", "Malla superior transversal", "2", 22, 15, 0, "superior", "transversal"),
        RebarRule("inf_long", "Malla inferior longitudinal", "3", 22, 15, 0, "inferior", "longitudinal"),
        RebarRule("inf_trans", "Malla inferior transversal", "4", 22, 15, 0, "inferior", "transversal"),
        RebarRule("lateral", "Barras laterales", "5", 16, 20, 0, "lateral", "longitudinal", enabled=False, automatic=False),
        RebarRule("suple", "Refuerzo suple", "6", 16, 20, 0, "suple", "longitudinal", enabled=False, automatic=False),
    )


def _projection_notes(rule: RebarRule) -> dict[str, str]:
    if rule.key == "sup_long":
        return {
            "FR": "junto al recubrimiento superior en elevación",
            "AA": "debajo de la malla superior transversal",
            "EE": "barra longitudinal superior en planta",
        }
    if rule.key == "sup_trans":
        return {
            "FR": "malla superior transversal visible",
            "AA": "sobre la malla superior longitudinal",
            "EE": "barra transversal superior en planta",
        }
    if rule.level == "inferior":
        return {
            "FR": "junto al recubrimiento inferior en elevación",
            "AA": "malla inferior bajo las barras superiores",
            "EE": "barra inferior en planta",
        }
    return {
        "FR": "según configuración constructiva",
        "AA": "según configuración constructiva",
        "EE": "según configuración constructiva",
    }


def build_zapata_schedule(
    geometry: ZapataGeometry, cover: Cover, rules: tuple[RebarRule, ...]
) -> ZapataSchedule:
    """Calcula marcas físicas de mallas de zapata sin depender de CAD.

    Las barras longitudinales recorren el largo y se distribuyen en el ancho;
    las transversales recorren el ancho y se distribuyen en el largo. El largo
    de gancho se agrega una sola vez, pues el estándar definido para esta etapa
    considera un gancho por barra.
    """
    issues = list(geometry.validate()) + list(cover.validate(geometry))
    marks = []
    used_marks: dict[str, float] = {}

    for rule in rules:
        issues.extend(rule.validate())
        if not rule.enabled:
            continue
        normalised_mark = rule.mark.strip().lower()
        previous_diameter = used_marks.get(normalised_mark)
        if previous_diameter is not None and previous_diameter != rule.diameter_mm:
            issues.append(ValidationIssue(
                "error", f"La marca {rule.mark} usa diámetros incompatibles ({previous_diameter:g} y {rule.diameter_mm:g} mm)."
            ))
        used_marks[normalised_mark] = rule.diameter_mm

        if not rule.automatic:
            issues.append(ValidationIssue(
                "warning", f"{rule.label} está habilitado, pero requiere definición manual antes de calcularse."
            ))
            continue

        if rule.direction == "longitudinal":
            run_m = geometry.largo_m - 2 * cover.lateral_m
            distribution_m = geometry.ancho_m - 2 * cover.lateral_m
        elif rule.direction == "transversal":
            run_m = geometry.ancho_m - 2 * cover.lateral_m
            distribution_m = geometry.largo_m - 2 * cover.lateral_m
        else:
            issues.append(ValidationIssue("error", f"Dirección no admitida para {rule.label}."))
            continue

        if run_m <= 0 or distribution_m < 0 or rule.spacing_cm <= 0:
            continue
        quantity = math.floor(distribution_m / (rule.spacing_cm / 100.0)) + 1
        unit_length_cm = run_m * 100.0 + rule.hook_cm
        marks.append(RebarMark(
            key=rule.key,
            mark=rule.mark.strip(),
            element="Zapata",
            location=f"Malla {rule.level}",
            diameter_mm=rule.diameter_mm,
            quantity=quantity,
            unit_length_cm=unit_length_cm,
            total_length_cm=quantity * unit_length_cm,
            views=("FR", "AA", "EE"),
            projection_notes=_projection_notes(rule),
        ))

    return ZapataSchedule(tuple(marks), tuple(issues))
