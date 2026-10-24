"""Catálogo declarativo para el generador híbrido de armaduras.

Este módulo no depende de Tk ni de AutoCAD. Describe la jerarquía del puente,
las capas de moldaje esperadas, la presencia opcional de elementos y las
familias de recetas que el asistente puede ofrecer. La geometría y el cálculo
de cada receta pertenecen a módulos posteriores.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata
from typing import Any, Mapping


JsonMapping = Mapping[str, Any]
JsonPath = tuple[str, ...]


class ContourPolicy(str, Enum):
    """Tipo de polilínea que una vista de moldaje puede aceptar."""

    OPEN = "open"
    CLOSED = "closed"
    EITHER = "either"


class RecipeFamily(str, Enum):
    """Familias geométricas genéricas; no contienen criterios de diseño."""

    PARALLEL_BARS = "parallel_bars"
    ORTHOGONAL_MESH = "orthogonal_mesh"
    U_BARS = "u_bars"
    LONGITUDINAL_BARS = "longitudinal_bars"
    CLOSED_STIRRUPS = "closed_stirrups"
    TRANSVERSE_TIES = "transverse_ties"
    FACE_BARS = "face_bars"
    EDGE_BARS = "edge_bars"
    ADDITIONAL_BARS = "additional_bars"


class PresenceKind(str, Enum):
    REQUIRED = "required"
    JSON_FLAG = "json_flag"
    MANUAL = "manual"


class InstanceKind(str, Enum):
    FIXED = "fixed"
    LIST = "list"
    COUNT = "count"
    SINGLETON = "singleton"


def _json_value(data: JsonMapping, path: JsonPath, instance_key: str = "") -> Any:
    current: Any = data
    for raw_key in path:
        key = raw_key.format(instance=instance_key)
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _slug(value: Any, fallback: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or fallback


@dataclass(frozen=True)
class PresenceRule:
    """Regla declarativa para mostrar un elemento en una instancia."""

    kind: PresenceKind = PresenceKind.REQUIRED
    path: JsonPath = ()
    default: bool = False

    def resolve(self, data: JsonMapping, instance_key: str = "") -> bool:
        if self.kind is PresenceKind.REQUIRED:
            return True
        if self.kind is PresenceKind.MANUAL:
            return self.default
        value = _json_value(data, self.path, instance_key)
        return self.default if value is None else bool(value)

    @property
    def optional(self) -> bool:
        return self.kind is not PresenceKind.REQUIRED


@dataclass(frozen=True)
class LayerView:
    """Una vista de moldaje identificada por su capa CAD."""

    view: str
    layer: str
    contour: ContourPolicy = ContourPolicy.EITHER
    detail: bool = False


@dataclass(frozen=True)
class ElementSpec:
    key: str
    label: str
    structure_key: str
    folder_path: tuple[str, ...]
    layers: tuple[LayerView, ...]
    recipes: tuple[RecipeFamily, ...]
    presence: PresenceRule = PresenceRule()
    definition_pending: bool = False

    @property
    def optional(self) -> bool:
        return self.presence.optional

    @property
    def layer_names(self) -> tuple[str, ...]:
        return tuple(layer.layer for layer in self.layers)


@dataclass(frozen=True)
class ResolvedInstance:
    key: str
    label: str
    source_index: int | None = None


@dataclass(frozen=True)
class InstanceSource:
    kind: InstanceKind
    path: JsonPath = ()
    fixed: tuple[tuple[str, str], ...] = ()
    presence_path: JsonPath = ()
    name_key: str = "nombre"
    enabled_key: str = ""
    prefix: str = "Elemento"

    def resolve(self, data: JsonMapping) -> tuple[ResolvedInstance, ...]:
        if self.kind is InstanceKind.FIXED:
            result = []
            for index, (key, label) in enumerate(self.fixed):
                if self.presence_path and not _json_value(data, self.presence_path, key):
                    continue
                result.append(ResolvedInstance(key, label, index))
            return tuple(result)

        value = _json_value(data, self.path)
        if self.kind is InstanceKind.LIST:
            if not isinstance(value, (list, tuple)):
                return ()
            result = []
            for index, item in enumerate(value):
                if not isinstance(item, Mapping):
                    continue
                if self.enabled_key and not bool(item.get(self.enabled_key, False)):
                    continue
                fallback = f"{self.prefix}_{index + 1:02d}"
                label = str(item.get(self.name_key) or fallback)
                result.append(ResolvedInstance(_slug(label, fallback.lower()), label, index))
            return tuple(result)

        if self.kind is InstanceKind.COUNT:
            try:
                count = max(0, int(value))
            except (TypeError, ValueError):
                count = 0
            return tuple(
                ResolvedInstance(
                    f"{_slug(self.prefix, 'elemento')}_{index + 1:02d}",
                    f"{self.prefix} {index + 1}",
                    index,
                )
                for index in range(count)
            )

        if self.kind is InstanceKind.SINGLETON and isinstance(value, Mapping):
            return (ResolvedInstance(_slug(self.prefix, "elemento"), self.prefix, 0),)
        return ()


@dataclass(frozen=True)
class StructureSpec:
    key: str
    label: str
    folder: str
    instances: InstanceSource


@dataclass(frozen=True)
class BridgeRebarCatalog:
    structures: tuple[StructureSpec, ...]
    elements: tuple[ElementSpec, ...]

    def structure(self, key: str) -> StructureSpec:
        for item in self.structures:
            if item.key == key:
                return item
        raise KeyError(key)

    def element(self, key: str) -> ElementSpec:
        for item in self.elements:
            if item.key == key:
                return item
        raise KeyError(key)

    def resolve_instances(
        self, structure_key: str, data: JsonMapping
    ) -> tuple[ResolvedInstance, ...]:
        return self.structure(structure_key).instances.resolve(data)

    def elements_for(
        self,
        structure_key: str,
        data: JsonMapping | None = None,
        instance_key: str = "",
        present_only: bool = False,
    ) -> tuple[ElementSpec, ...]:
        items = tuple(
            element for element in self.elements
            if element.structure_key == structure_key
        )
        if not present_only:
            return items
        source = data or {}
        return tuple(
            element for element in items
            if element.presence.resolve(source, instance_key)
        )

    def layer_names(self) -> tuple[str, ...]:
        """Capas únicas, conservando el orden del catálogo."""
        seen: set[str] = set()
        result = []
        for element in self.elements:
            for name in element.layer_names:
                if name not in seen:
                    seen.add(name)
                    result.append(name)
        return tuple(result)


def _views(*names: str, contour: ContourPolicy = ContourPolicy.EITHER) -> tuple[LayerView, ...]:
    return tuple(LayerView(name.split("_", 1)[0], name, contour) for name in names)


def _detail(layer: str) -> tuple[LayerView, ...]:
    return (LayerView("DET", layer, ContourPolicy.EITHER, detail=True),)


REQUIRED = PresenceRule()
MANUAL_OPTIONAL = PresenceRule(PresenceKind.MANUAL, default=False)


STRUCTURES = (
    StructureSpec(
        "abutment", "ESTRIBO", "1-ESTRIBO",
        InstanceSource(
            InstanceKind.FIXED,
            fixed=(("entrada", "Estribo de entrada"), ("salida", "Estribo de salida")),
            presence_path=("estribos", "tipo_estribo_{instance}"),
        ),
    ),
    StructureSpec(
        "pier", "CEPA", "2-CEPA",
        InstanceSource(
            InstanceKind.LIST, path=("cepas", "lista"),
            name_key="nombre", prefix="Cepa",
        ),
    ),
    StructureSpec(
        "beam", "VIGA", "3-VIGA",
        InstanceSource(
            InstanceKind.COUNT,
            path=("elementos_comunes", "vigas", "num_vigas"),
            prefix="Viga",
        ),
    ),
    StructureSpec(
        "crossbeam", "TRAVESAÑO", "4-TRAVESAÑO",
        InstanceSource(
            InstanceKind.SINGLETON,
            path=("elementos_comunes", "travesanos"),
            prefix="Travesaños",
        ),
    ),
    StructureSpec(
        "slab", "LOSA", "5-LOSA",
        InstanceSource(
            InstanceKind.LIST, path=("tableros",), name_key="nombre_grupo_tablero",
            enabled_key="usar_grupo_tablero", prefix="Tablero",
        ),
    ),
)


ELEMENTS = (
    ElementSpec(
        "abutment.footing", "Zapata", "abutment", ("1-ESTRIBO", "1-1-ZAPATA"),
        _views("FR_ZAP", "AA_ZAP", "BB_ZAP", "CC_ZAP", "FF_ZAP"),
        (RecipeFamily.ORTHOGONAL_MESH, RecipeFamily.FACE_BARS, RecipeFamily.U_BARS),
    ),
    ElementSpec(
        "abutment.front_wall", "Muro frontal", "abutment",
        ("1-ESTRIBO", "1-2-MFRONTAL", "1-2-1-MURO"),
        _views("FR_MFR", "AA_MFR", "BB_MFR", "CC_MFR", "DD_MFR"),
        (RecipeFamily.ORTHOGONAL_MESH, RecipeFamily.FACE_BARS, RecipeFamily.EDGE_BARS),
    ),
    ElementSpec(
        "abutment.front_stop", "Tope de muro frontal", "abutment",
        ("1-ESTRIBO", "1-2-MFRONTAL", "1-2-2-TOPE"),
        _detail("DET_TOP"),
        (RecipeFamily.U_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.LONGITUDINAL_BARS),
    ),
    ElementSpec(
        "abutment.front_console", "Consola de muro frontal", "abutment",
        ("1-ESTRIBO", "1-2-MFRONTAL", "1-2-3-CONSOLA"),
        _views("FR_CON", "AA_CON", "BB_CON", "CC_CON"),
        (RecipeFamily.U_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.LONGITUDINAL_BARS),
        PresenceRule(PresenceKind.JSON_FLAG, ("estribos", "incluir_consola_frontal_{instance}")),
    ),
    ElementSpec(
        "abutment.back_wall", "Muro espaldar", "abutment",
        ("1-ESTRIBO", "1-3-MESPALDAR", "1-3-1-MURO"),
        _views("FR_ESP", "AA_ESP", "BB_ESP", "CC_ESP", "EE_ESP"),
        (RecipeFamily.ORTHOGONAL_MESH, RecipeFamily.FACE_BARS, RecipeFamily.EDGE_BARS),
    ),
    ElementSpec(
        "abutment.back_console", "Consola de muro espaldar", "abutment",
        ("1-ESTRIBO", "1-3-MESPALDAR", "1-3-2-CONSOLA"),
        _detail("DET_CON"),
        (RecipeFamily.U_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.LONGITUDINAL_BARS),
    ),
    ElementSpec(
        "abutment.left_wing", "Ala izquierda", "abutment",
        ("1-ESTRIBO", "1-4-ALA IZQ"),
        _views("BB_ALA_IZQ", "DD_ALA_IZQ", "EE_ALA_IZQ"),
        (RecipeFamily.ORTHOGONAL_MESH, RecipeFamily.FACE_BARS, RecipeFamily.EDGE_BARS),
    ),
    ElementSpec(
        "abutment.right_wing", "Ala derecha", "abutment",
        ("1-ESTRIBO", "1-5-ALA DER"),
        _views("CC_ALA_DER", "DD_ALA_DER", "EE_ALA_DER"),
        (RecipeFamily.ORTHOGONAL_MESH, RecipeFamily.FACE_BARS, RecipeFamily.EDGE_BARS),
    ),
    ElementSpec(
        "abutment.pile", "Pilote de estribo", "abutment",
        ("1-ESTRIBO", "1-6-PILOTE"),
        _views("FR_PIL", "AA_PIL", "BB_PIL", "CC_PIL") + _detail("DET_PIL"),
        (RecipeFamily.LONGITUDINAL_BARS, RecipeFamily.TRANSVERSE_TIES),
        PresenceRule(PresenceKind.JSON_FLAG, ("estribos", "incluir_pilotes_dado_estribo_{instance}")),
    ),
    ElementSpec(
        "abutment.counterfort", "Contrafuerte", "abutment",
        ("1-ESTRIBO", "1-7-CONTRAFUERTE"), (),
        (RecipeFamily.FACE_BARS, RecipeFamily.EDGE_BARS, RecipeFamily.U_BARS),
        PresenceRule(PresenceKind.JSON_FLAG, ("estribos", "incluir_contrafuertes_mura_ala_{instance}")),
        definition_pending=True,
    ),
    ElementSpec(
        "pier.cap", "Cabezal", "pier", ("2-CEPA", "2-1-CABEZAL"),
        _views("FR_CAB", "AA_CAB", "BB_CAB", "CC_CAB", "DD_CAB"),
        (RecipeFamily.LONGITUDINAL_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.FACE_BARS),
    ),
    ElementSpec(
        "pier.pile", "Pilote de cepa", "pier", ("2-CEPA", "2-2-PILOTE"),
        _views("FR_PIL", "AA_PIL", "BB_PIL", "CC_PIL") + _detail("DET_PIL"),
        (RecipeFamily.LONGITUDINAL_BARS, RecipeFamily.TRANSVERSE_TIES),
    ),
    ElementSpec(
        "pier.stop", "Tope sísmico", "pier", ("2-CEPA", "2-3-TOPE"),
        _detail("DET_TOP"),
        (RecipeFamily.U_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.LONGITUDINAL_BARS),
    ),
    ElementSpec(
        "pier.console", "Consola de cabezal", "pier", ("2-CEPA", "2-4-CONSOLA"),
        _views("AA_CON", "BB_CON", "CC_CON"),
        (RecipeFamily.U_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.LONGITUDINAL_BARS),
        MANUAL_OPTIONAL,
    ),
    ElementSpec(
        "beam.beam", "Viga", "beam", ("3-VIGA",),
        _views("EL_VIG", "AA_VIG", "BB_VIG", "CC_VIG"),
        (RecipeFamily.LONGITUDINAL_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.FACE_BARS),
    ),
    ElementSpec(
        "crossbeam.support", "Travesaño sobre apoyos", "crossbeam",
        ("4-TRAVESAÑO", "4-1-APOYOS"),
        _views("FR_TRAV", "AA_TRAV", "BB_TRAV"),
        (RecipeFamily.LONGITUDINAL_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.FACE_BARS),
    ),
    ElementSpec(
        "crossbeam.support_raise", "Recrecido sobre apoyos", "crossbeam",
        ("4-TRAVESAÑO", "4-1-APOYOS", "RECRECIDO"),
        _views("AA_REC", "BB_REC", "CC_REC"),
        (RecipeFamily.U_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.LONGITUDINAL_BARS),
    ),
    ElementSpec(
        "crossbeam.intermediate", "Travesaño intermedio", "crossbeam",
        ("4-TRAVESAÑO", "4-2-INTERMEDIO"),
        _views("FR_TRAV", "AA_TRAV", "BB_TRAV"),
        (RecipeFamily.LONGITUDINAL_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.FACE_BARS),
    ),
    ElementSpec(
        "crossbeam.intermediate_raise", "Recrecido intermedio", "crossbeam",
        ("4-TRAVESAÑO", "4-2-INTERMEDIO", "RECRECIDO"),
        _views("AA_REC", "BB_REC", "CC_REC"),
        (RecipeFamily.U_BARS, RecipeFamily.CLOSED_STIRRUPS, RecipeFamily.LONGITUDINAL_BARS),
        MANUAL_OPTIONAL,
    ),
    ElementSpec(
        "slab.slab", "Losa", "slab", ("5-LOSA",),
        _views("PLAN_LOS", "SECC_LOS"),
        (RecipeFamily.ORTHOGONAL_MESH, RecipeFamily.EDGE_BARS, RecipeFamily.ADDITIONAL_BARS),
    ),
)


BRIDGE_REBAR_CATALOG = BridgeRebarCatalog(STRUCTURES, ELEMENTS)
