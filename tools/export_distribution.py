"""Exporta únicamente los recursos autorizados al repositorio público."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sincal_runtime import (  # noqa: E402
    RECURSOS_EXACTOS,
    RECURSOS_POR_CARPETA,
    es_recurso_actualizable,
)

MARKER_FILE = ".sincal-distribution"
MANIFEST_FILE = "manifest.json"
REQUIRED_RESOURCES = {
    "lisps/SINCAL.lsp",
    "masters/FORMATOS ANOTATIVOS ACAD_2025.dwg",
}


def _safe_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    target = (root / Path(*relative.split("/"))).resolve()
    if os.path.commonpath((str(root), str(target))) != str(root):
        raise ValueError(f"Ruta fuera del repositorio de distribución: {relative}")
    return target


def discover_resources(source: Path) -> dict[str, Path]:
    source = source.resolve()
    resources: dict[str, Path] = {}

    for relative in RECURSOS_EXACTOS:
        path = _safe_path(source, relative)
        if path.is_file():
            resources[relative] = path

    for prefix, extensions in RECURSOS_POR_CARPETA.items():
        folder = _safe_path(source, prefix.rstrip("/"))
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"No se permiten enlaces simbólicos: {path}")
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            relative = path.relative_to(source).as_posix()
            if es_recurso_actualizable(relative):
                resources[relative] = path

    missing = sorted(REQUIRED_RESOURCES - set(resources))
    if missing:
        raise ValueError("Faltan recursos esenciales: " + ", ".join(missing))
    return dict(sorted(resources.items()))


def discover_published_resources(destination: Path) -> dict[str, Path]:
    if not destination.exists():
        return {}
    return {
        relative: path
        for relative, path in discover_resources_without_requirements(destination).items()
    }


def discover_resources_without_requirements(source: Path) -> dict[str, Path]:
    source = source.resolve()
    resources: dict[str, Path] = {}
    for relative in RECURSOS_EXACTOS:
        path = _safe_path(source, relative)
        if path.is_file():
            resources[relative] = path
    for prefix, extensions in RECURSOS_POR_CARPETA.items():
        folder = _safe_path(source, prefix.rstrip("/"))
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"No se permiten enlaces simbólicos: {path}")
            if path.is_file() and path.suffix.lower() in extensions:
                relative = path.relative_to(source).as_posix()
                if es_recurso_actualizable(relative):
                    resources[relative] = path
    return dict(sorted(resources.items()))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_version(source: Path) -> str:
    with (source / "version.json").open(encoding="utf-8") as version_file:
        return str(json.load(version_file)["version"])


def _write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def export_distribution(
    source: Path,
    destination: Path,
    *,
    source_commit: str = "",
) -> dict:
    source = source.resolve()
    destination = destination.resolve()
    if source == destination:
        raise ValueError("Origen y destino de distribución no pueden ser iguales.")

    resources = discover_resources(source)
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / MARKER_FILE
    published = discover_published_resources(destination)
    if published and not marker.is_file():
        raise ValueError(
            f"El destino contiene recursos pero no el marcador {MARKER_FILE}; "
            "se cancela para evitar borrar el repositorio equivocado."
        )
    marker.write_text(
        "Repositorio público generado por SINCAL. No contiene el código fuente.\n",
        encoding="utf-8",
    )

    for relative, source_path in resources.items():
        target = _safe_path(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)

    removed = []
    for relative, old_path in published.items():
        if relative not in resources:
            old_path.unlink()
            removed.append(relative)

    for prefix in sorted(RECURSOS_POR_CARPETA, key=len, reverse=True):
        folder = _safe_path(destination, prefix.rstrip("/"))
        if not folder.is_dir():
            continue
        for child in sorted(folder.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if child.is_dir() and not any(child.iterdir()):
                child.rmdir()
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()

    manifest_resources = {
        relative: {
            "sha256": _sha256(_safe_path(destination, relative)),
            "size": source_path.stat().st_size,
        }
        for relative, source_path in resources.items()
    }
    manifest = {
        "schema": 1,
        "product": "SINCAL Suite 1.0",
        "release": _read_version(source),
        "source_commit": source_commit,
        "resources": manifest_resources,
    }
    _write_json(destination / MANIFEST_FILE, manifest)
    return {
        "copied": tuple(resources),
        "removed": tuple(sorted(removed)),
        "manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-commit", default="")
    args = parser.parse_args()
    result = export_distribution(
        args.source,
        args.destination,
        source_commit=args.source_commit,
    )
    print(
        f"Distribución exportada: {len(result['copied'])} recursos; "
        f"{len(result['removed'])} eliminados."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
