from pathlib import Path
import tempfile
from unittest.mock import patch

from tests.test_csv_sc import balanced_lisp


ROOT = Path(__file__).resolve().parents[1]


def test_repair_and_native_regression_lisp_are_balanced():
    for relative in ("lisps/ACTUALIZAR-VINETA.lsp", "tests/cad/actualizar_vineta_regression.lsp"):
        balanced_lisp((ROOT / relative).read_text(encoding="utf-8"))


def test_repair_is_distributed_and_loaded_by_cad_integration():
    from tools.export_distribution import discover_resources
    from sincal.resources import write_cad_loaders

    relative = "lisps/ACTUALIZAR-VINETA.lsp"
    assert relative in discover_resources(ROOT)
    with tempfile.TemporaryDirectory() as folder:
        with patch("sincal.resources.ruta_cad_usuario",
                   side_effect=lambda *parts: str(Path(folder).joinpath(*parts))):
            write_cad_loaders([relative])
        for loader in ("acaddoc.lsp", "zwcaddoc.lsp"):
            assert "/" + relative in (Path(folder) / loader).read_text(encoding="utf-8")
