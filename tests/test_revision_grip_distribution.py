"""The native editor is installed with the release, outside remote resources."""
from pathlib import Path
from unittest.mock import patch

from sincal import resources, runtime


def test_materialize_native_editor_keeps_other_binaries_and_is_idempotent(tmp_path):
    installed = tmp_path / "installed"
    source = installed / "native" / "revision-grip"
    source.mkdir(parents=True)
    cad = tmp_path / "cad"
    cad.mkdir()
    names = ["Sincal.RevisionGrip.AutoCAD.R25.1.dll", "Sincal.RevisionGrip.ZWCAD.2026.dll"]
    for name in names:
        (source / name).write_bytes(b"MZ editor " + name.encode())
    (source / "unrelated.dll").write_bytes(b"do not copy")
    (cad / "unrelated.dll").write_bytes(b"user binary")
    with patch.object(resources, "ruta_recurso_instalado", side_effect=lambda *p: str(installed.joinpath(*p))), \
         patch.object(resources, "ruta_cad_usuario", side_effect=lambda *p: str(cad.joinpath(*p))):
        assert set(resources.materialize_revision_grip()) == set(names)
        assert all((cad / name).read_bytes() == (source / name).read_bytes() for name in names)
        before = {name: (cad / name).stat().st_mtime_ns for name in names}
        assert resources.materialize_revision_grip() == ()
        assert before == {name: (cad / name).stat().st_mtime_ns for name in names}
        assert (cad / "unrelated.dll").read_bytes() == b"user binary"
        (source / names[0]).write_bytes(b"MZ newer editor")
        assert resources.materialize_revision_grip() == (names[0],)
        assert (cad / names[0]).read_bytes() == b"MZ newer editor"
    for name in names:
        assert not runtime.es_recurso_actualizable("native/revision-grip/" + name)


def test_materialize_development_output_and_missing_plugin(tmp_path):
    cad = tmp_path / "cad"
    source = tmp_path / "src" / "Sincal.RevisionGrip" / "bin" / "distribution"
    with patch.object(resources, "ruta_recurso_instalado", side_effect=lambda *p: str(tmp_path.joinpath(*p))), \
         patch.object(resources, "ruta_cad_usuario", side_effect=lambda *p: str(cad.joinpath(*p))):
        assert resources.materialize_revision_grip() == ()
        source.mkdir(parents=True)
        name = "Sincal.RevisionGrip.AutoCAD.R26.0.dll"
        (source / name).write_bytes(b"MZ development")
        assert resources.materialize_revision_grip() == (name,)
        assert (cad / name).read_bytes() == b"MZ development"
