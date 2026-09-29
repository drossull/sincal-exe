"""Preferencias visuales locales; nunca se guardan en el proyecto CAD."""
import json
import os
from pathlib import Path
from sincal.runtime import RUTA_DATOS_USUARIO
from sincal.ui.cadence_palettes import FAMILIES


def preferences_path():
    return Path(RUTA_DATOS_USUARIO) / "ui_preferences.json"


def load_preferences(path=None):
    defaults = {"family": "cadence", "mode": "dark", "panels_expanded": True,
                "reduced_motion": False}
    try:
        data = json.loads(Path(path or preferences_path()).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if data.get("family") in {"cadence", *FAMILIES}:
                defaults["family"] = data["family"]
            if data.get("mode") in {"dark", "light", "system"}:
                defaults["mode"] = data["mode"]
            for key in ("panels_expanded", "reduced_motion"):
                if isinstance(data.get(key), bool):
                    defaults[key] = data[key]
    except (OSError, ValueError, TypeError):
        pass
    return defaults


def save_preferences(data, path=None):
    target = Path(path or preferences_path())
    temporary = target.with_suffix(".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)
        return True
    except OSError:
        return False
