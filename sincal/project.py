"""Estado compartido y presentación legible de un proyecto SINCAL."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sincal.runtime import ruta_datos
from sincal.sessions import atomic_json_write, sha256_file


PROJECT_STATE_SCHEMA = 1
EXPECTED_ROOTS = (
    "parametros_generales", "elementos_comunes", "cepas", "estribos",
    "tableros", "materiales", "planos", "meta",
)
IDENTIFICATION_FIELDS = ("ot", "revision", "structure_name")


@dataclass
class ProjectContext:
    """Fuente única del JSON activo, sin alterar nunca el archivo original."""

    state_path: Path | None = None
    path: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    sha256: str = ""
    identification: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    loaded_at: str = ""

    def __post_init__(self):
        self.state_path = Path(self.state_path or ruta_datos("project_state.json"))
        self.identification = self._clean_identification(self.identification)

    @property
    def active(self) -> bool:
        return bool(self.data)

    @property
    def filename(self) -> str:
        return os.path.basename(self.path) if self.path else "Instantánea de sesión"

    @property
    def complete_identification(self) -> bool:
        return all(self.identification.get(key, "").strip() for key in IDENTIFICATION_FIELDS)

    def load(self, path: str, identification: dict | None = None) -> "ProjectContext":
        source_path = os.path.abspath(path)
        with open(source_path, "r", encoding="utf-8") as source:
            data = json.load(source)
        if not isinstance(data, dict):
            raise ValueError("El JSON del proyecto debe contener un objeto en su nivel principal.")
        stored = self.identification_for(source_path)
        stored.update({
            key: value for key, value in self._clean_identification(identification).items()
            if value
        })
        return self.activate_snapshot(
            data, source_path, sha256_file(source_path), stored, remember=True)

    def activate_snapshot(
        self, data: dict, path: str = "", source_hash: str = "",
        identification: dict | None = None, remember: bool = True,
    ) -> "ProjectContext":
        if not isinstance(data, dict):
            raise ValueError("La instantánea del proyecto no contiene un objeto JSON.")
        self.path = str(path or "")
        self.data = data
        self.sha256 = str(source_hash or sha256_file(self.path))
        self.identification = self._clean_identification(identification)
        self.warnings = validate_project_data(data)
        self.loaded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if remember and self.path:
            self._remember_current()
        return self

    def update_identification(self, **values) -> None:
        current = dict(self.identification)
        current.update(values)
        self.identification = self._clean_identification(current)
        if self.path:
            self._remember_current()

    def clear(self, forget_last: bool = False) -> None:
        self.path = ""
        self.data = {}
        self.sha256 = ""
        self.identification = self._clean_identification(None)
        self.warnings = []
        self.loaded_at = ""
        if forget_last:
            state = self._read_state()
            state["last_project_path"] = ""
            atomic_json_write(self.state_path, state, backup=False)

    def last_project_path(self) -> str:
        return str(self._read_state().get("last_project_path") or "")

    def identification_for(self, path: str) -> dict[str, str]:
        record = self._read_state().get("projects", {}).get(_path_key(path), {})
        return self._clean_identification(record.get("identification"))

    def _remember_current(self) -> None:
        state = self._read_state()
        projects = state.setdefault("projects", {})
        projects[_path_key(self.path)] = {
            "path": self.path,
            "sha256": self.sha256,
            "identification": self.identification,
            "updated_at": self.loaded_at,
        }
        state["last_project_path"] = self.path
        atomic_json_write(self.state_path, state, backup=False)

    def _read_state(self) -> dict:
        try:
            with open(self.state_path, "r", encoding="utf-8") as source:
                state = json.load(source)
            if int(state.get("schema_version", 0)) != PROJECT_STATE_SCHEMA:
                return _empty_state()
            if not isinstance(state.get("projects"), dict):
                return _empty_state()
            return state
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return _empty_state()

    @staticmethod
    def _clean_identification(values: dict | None) -> dict[str, str]:
        values = values or {}
        return {key: str(values.get(key) or "").strip() for key in IDENTIFICATION_FIELDS}


def _empty_state() -> dict:
    return {
        "schema_version": PROJECT_STATE_SCHEMA,
        "last_project_path": "",
        "projects": {},
    }


def _path_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path or ""))


def validate_project_data(data: dict) -> list[str]:
    warnings = []
    for key in EXPECTED_ROOTS:
        if key not in data:
            warnings.append(f"Falta el bloque «{human_label(key)}».")
    for key in ("parametros_generales", "elementos_comunes", "cepas", "estribos"):
        if key in data and not isinstance(data[key], dict):
            warnings.append(f"El bloque «{human_label(key)}» no tiene el formato esperado.")
    if "tableros" in data and not isinstance(data["tableros"], list):
        warnings.append("El bloque «Tableros» debe ser una lista.")
    return warnings


def human_label(key: str) -> str:
    replacements = {
        "izq": "izquierdo", "der": "derecho", "num": "número",
        "cg": "cortagotera", "pav": "pavimento", "mm": "mm",
        "stud": "stud", "deltaZ": "delta Z", "ifc": "IFC",
    }
    words = []
    for word in str(key).replace("-", "_").split("_"):
        words.append(replacements.get(word, word))
    return " ".join(words).strip().capitalize()


def _number(value: float, decimals: int = 3) -> str:
    if float(value).is_integer():
        raw = f"{int(value):,}"
    else:
        raw = f"{value:,.{decimals}f}".rstrip("0").rstrip(".")
    return raw.replace(",", "\u00a0").replace(".", ",")


def format_project_value(path: str, value: Any) -> str:
    """Presenta unidades sin cambiar el valor almacenado en el JSON."""
    if value is None or value == "":
        return "No definido"
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return str(value)

    key = path.lower()
    if any(token in key for token in ("coord_norte", "coord_este", "coord_cota")):
        return f"{_number(value)} PTL"
    if any(token in key for token in ("angulo", "rotacion")):
        return f"{_number(value)}°"
    if "pend" in key:
        return f"{_number(value, 5)} · {_number(value * 100, 3)} %"
    nondimensional = (
        "cantidad", "num_", "numero", "tipo_viga", "tipo_losa", "version",
        "modo_", "usar_", "incluir_", "excluir_", "filas", "cols",
    )
    if any(token in key for token in nondimensional):
        return _number(value)
    dimensional = (
        "ancho", "largo", "longitud", "espesor", "altura", "alto", "offset",
        "separacion", "distancia", "diametro", "profundidad", "avance",
        "excentricidad", "medida", "origin_", "deformacion", "correccion_altura",
    )
    if any(token in key for token in dimensional):
        return f"{_number(value)} mm · {_number(value / 1000.0)} m"
    return _number(value)


def _rows(mapping: dict, prefix: str = "") -> list[tuple[str, str, str]]:
    rows = []
    for key, value in mapping.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            rows.extend(_rows(value, path))
        elif isinstance(value, list):
            for index, item in enumerate(value, 1):
                item_path = f"{path}[{index}]"
                if isinstance(item, dict):
                    rows.extend(_rows(item, item_path))
                else:
                    rows.append((item_path, f"{human_label(key)} {index}", format_project_value(item_path, item)))
        else:
            rows.append((path, human_label(key), format_project_value(path, value)))
    return rows


def _split_estribos(data: dict, suffix: str) -> dict:
    result = {}
    ending = f"_{suffix}"
    embedded = f"_{suffix}_"
    for key, value in data.items():
        if key.endswith(ending):
            result[key[:-len(ending)]] = value
        elif embedded in key:
            result[key.replace(embedded, "_", 1)] = value
    return result


def project_sections(data: dict) -> list[dict]:
    """Ordena desde el resumen del puente hasta su metadato más particular."""
    general = data.get("parametros_generales") or {}
    common = data.get("elementos_comunes") or {}
    abutments = data.get("estribos") or {}
    cepas = data.get("cepas") or {}
    decks = data.get("tableros") or []

    entry = _split_estribos(abutments, "entrada")
    exit_ = _split_estribos(abutments, "salida")
    used_abutment_keys = set()
    for key in abutments:
        if key.endswith("_entrada") or "_entrada_" in key or key.endswith("_salida") or "_salida_" in key:
            used_abutment_keys.add(key)
    shared_abutments = {key: value for key, value in abutments.items() if key not in used_abutment_keys}

    summary = {
        "version_json": data.get("version", "No definido"),
        "cantidad_tableros": len(decks) if isinstance(decks, list) else 0,
        "cantidad_cepas": len(cepas.get("lista", [])) if isinstance(cepas, dict) else 0,
        "tipo_estribo_entrada": abutments.get("tipo_estribo_entrada", "No definido"),
        "tipo_estribo_salida": abutments.get("tipo_estribo_salida", "No definido"),
        "angulo_esviaje_puente": general.get("angulo_esviaje_puente", "No definido"),
    }
    sections = [
        _section("resumen", "Resumen del proyecto", [("Síntesis", summary)]),
        _section("generales", "Parámetros generales", [("Sistema local y geometría", general)]),
    ]

    common_groups = [(human_label(key), value if isinstance(value, dict) else {key: value})
                     for key, value in common.items()]
    if isinstance(decks, list):
        for index, deck in enumerate(decks, 1):
            name = deck.get("nombre_grupo_tablero", f"Tablero {index}") if isinstance(deck, dict) else f"Tablero {index}"
            common_groups.append((f"Tablero {index} · {name}", deck if isinstance(deck, dict) else {"valor": deck}))
    sections.append(_section("superestructura", "Superestructura", common_groups))
    sections.append(_section("estribo_entrada", "Estribo de entrada", [("Configuración", entry)]))
    sections.append(_section("estribo_salida", "Estribo de salida", [("Configuración", exit_)]))

    cepa_groups = []
    if isinstance(cepas, dict):
        if isinstance(cepas.get("parametros_globales"), dict):
            cepa_groups.append(("Parámetros globales", cepas["parametros_globales"]))
        for index, cepa in enumerate(cepas.get("lista", []), 1):
            name = cepa.get("nombre", f"Cepa {index}") if isinstance(cepa, dict) else f"Cepa {index}"
            cepa_groups.append((f"Cepa {index} · {name}", cepa if isinstance(cepa, dict) else {"valor": cepa}))
    sections.append(_section("cepas", "Cepas", cepa_groups))
    sections.append(_section("materiales", "Materiales", [("Especificaciones", data.get("materiales") or {})]))
    sections.append(_section("planos", "Planos y configuración", [
        ("Planos", data.get("planos") or {}),
        ("Parámetros comunes de estribos", shared_abutments),
    ]))
    sections.append(_section("metadatos", "Metadatos", [
        ("Metadatos del archivo", data.get("meta") or {}),
    ]))

    known = {"version", *EXPECTED_ROOTS}
    unknown = {key: value for key, value in data.items() if key not in known}
    if unknown:
        sections[-1]["groups"].append(_group("Otros datos", unknown))
    return sections


def _group(title: str, values: dict) -> dict:
    return {"title": title, "rows": _rows(values)}


def _section(anchor: str, title: str, groups: Iterable[tuple[str, dict]]) -> dict:
    return {
        "anchor": anchor,
        "title": title,
        "groups": [_group(group_title, values) for group_title, values in groups if values],
    }


def project_text(context: ProjectContext) -> str:
    identity = context.identification
    lines = [
        "SINCAL SUITE — CONSULTA DE PROYECTO",
        "=" * 44,
        f"OT: {identity.get('ot') or 'No definido'}",
        f"Revisión: {identity.get('revision') or 'No definido'}",
        f"Nombre de estructura: {identity.get('structure_name') or 'No definido'}",
        f"Archivo JSON: {context.path or 'Instantánea de sesión'}",
        f"SHA-256: {context.sha256 or 'No disponible'}",
        "Coordenadas del JSON: sistema local PTL; no se vinculan al módulo Ubicación.",
        "",
    ]
    for section in project_sections(context.data):
        lines.extend((section["title"].upper(), "-" * len(section["title"])))
        for group in section["groups"]:
            lines.append(f"[{group['title']}]")
            for _path, label, value in group["rows"]:
                lines.append(f"{label}: {value}")
            lines.append("")
    if context.warnings:
        lines.append("ADVERTENCIAS")
        lines.extend(f"- {warning}" for warning in context.warnings)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
